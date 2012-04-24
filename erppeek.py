#!/usr/bin/env python
# -*- coding: utf-8 -*-
""" erppeek.py -- OpenERP command line tool

Author: Florent Xicluna
(derived from a script by Alan Bell)
"""
from __future__ import with_statement

import functools
import optparse
import os.path
from pprint import pprint
import re
import sys
import warnings
try:                    # Python 3
    import configparser
    from xmlrpc.client import Fault, ServerProxy
    basestring = str
    int_types = int
except ImportError:     # Python 2
    import ConfigParser as configparser
    from xmlrpclib import Fault, ServerProxy
    int_types = int, long

try:
    # first, try importing directly
    from ast import literal_eval
except ImportError:
    import _ast

    # Port of Python 2.6's ast.literal_eval for use under Python 2.5
    SAFE_CONSTANTS = {'None': None, 'True': True, 'False': False}

    def _convert(node):
        if isinstance(node, _ast.Str):
            return node.s
        elif isinstance(node, _ast.Num):
            return node.n
        elif isinstance(node, _ast.Tuple):
            return tuple(map(_convert, node.elts))
        elif isinstance(node, _ast.List):
            return list(map(_convert, node.elts))
        elif isinstance(node, _ast.Dict):
            return dict((_convert(k), _convert(v)) for k, v
                        in zip(node.keys, node.values))
        elif isinstance(node, _ast.Name):
            if node.id in SAFE_CONSTANTS:
                return SAFE_CONSTANTS[node.id]
        raise ValueError('malformed or disallowed expression')

    def literal_eval(node_or_string):
        if isinstance(node_or_string, basestring):
            node_or_string = compile(node_or_string,
                                     '<unknown>', 'eval', _ast.PyCF_ONLY_AST)
        if isinstance(node_or_string, _ast.Expression):
            node_or_string = node_or_string.body
        return _convert(node_or_string)


__version__ = '0.8'
__all__ = ['Client', 'read_config']

CONF_FILE = 'erppeek.ini'
DEFAULT_URL = 'http://localhost:8069'
DEFAULT_DB = 'openerp'
DEFAULT_USER = 'admin'
DEFAULT_PASSWORD = 'admin'

USAGE = """\
Usage (main commands):
    search(obj, domain)
    search(obj, domain, offset=0, limit=None, order=None)
                                    # Return a list of IDs
    count(obj, domain)              # Count the matching objects

    read(obj, ids, fields=None)
    read(obj, domain, fields=None)
    read(obj, domain, fields=None, offset=0, limit=None, order=None)
                                    # Return values for the fields

    model(name)                     # List models matching pattern
    keys(obj)                       # List field names of the model
    fields(obj, names=None)         # Return details for the fields
    field(obj, name)                # Return details for the field
    access(obj, mode='read')        # Check access on the model

    do(obj, method, *params)        # Generic 'object.execute'
    wizard(name)                    # Return the 'id' of a new wizard
    wizard(name_or_id, datas=None, action='init')
                                    # Generic 'wizard.execute'
    exec_workflow(obj, signal, id)  # Trigger workflow signal

    client                          # Client object, connected
    client.login(user)              # Login with another user
    client.connect(env)             # Connect to another env.
    client.modules(name)            # List modules matching pattern
    client.upgrade(module1, module2, ...)
                                    # Upgrade the modules
"""

STABLE_STATES = ('uninstallable', 'uninstalled', 'installed')
DOMAIN_OPERATORS = frozenset('!|&')
# Supported operators are
#   =, !=, >, >=, <, <=, like, ilike, in,
#   not like, not ilike, not in, child_of
# Not supported operators are
#  - redundant operators: '<>', '=like', '=ilike'
#  - future operator(s) (6.1): '=?'
_term_re = re.compile(
        '(\S+)\s*'
        '(=|!=|>|>=|<|<=|like|ilike|in|not like|not ilike|not in|child_of)'
        '\s*(.*)')
_fields_re = re.compile(r'(?:[^%]|^)%\(([^)]+)\)')

# Published object methods
_methods = {
    'db': ['create', 'drop', 'dump', 'restore', 'rename', 'list', 'list_lang',
           'change_admin_password', 'server_version', 'migrate_databases'],
    'common': ['about', 'login', 'timezone_get', 'get_server_environment',
               'login_message', 'check_connectivity'],
    'object': ['execute', 'exec_workflow'],
    'wizard': ['execute', 'create'],
    'report': ['report', 'report_get'],
}
_methods_6_1 = {
    'db': ['create_database', 'db_exist'],
    'common': ['get_stats', 'list_http_services', 'version',
               'authenticate', 'get_os_time', 'get_sqlcount'],
    'object': ['execute_kw'],
    'wizard': [],
    'report': ['render_report'],
}
# Hidden methods:
#  - (not in 6.1) 'common': ['logout', 'ir_get', 'ir_set', 'ir_del']
#  - (not in 6.1) 'object': ['obj_list']
#  - 'db': ['get_progress']
#  - 'common': ['get_available_updates', 'get_migration_scripts', 'set_loglevel']


def read_config(section=None):
    p = configparser.SafeConfigParser()
    with open(Client._config_file) as f:
        p.readfp(f)
    if section is None:
        return p.sections()
    server = 'http://%s:%s' % (p.get(section, 'host'), p.get(section, 'port'))
    db = p.get(section, 'database')
    user = p.get(section, 'username')
    if p.has_option(section, 'password'):
        password = p.get(section, 'password')
    else:
        password = None
    return (server, db, user, password)


def issearchdomain(arg):
    """Check if the argument is a search domain.

    Examples:
      - [('name', '=', 'mushroom'), ('state', '!=', 'draft')]
      - ['name = mushroom', 'state != draft']
      - []
      - 'state != draft'
      - ('state', '!=', 'draft')
    """
    return isinstance(arg, (list, tuple, basestring)) and not (arg and (
            # Not a list of ids: [1, 2, 3]
            isinstance(arg[0], int_types) or
            # Not a list of ids as str: ['1', '2', '3']
            (isinstance(arg[0], basestring) and arg[0].isdigit())))


def searchargs(params, kwargs=None, context=None):
    """Compute the 'search' parameters."""
    if not params:
        return ([],)
    domain = params[0]
    if isinstance(domain, (basestring, tuple)):
        domain = [domain]
        warnings.warn('Domain should be a list: %s' % domain)
    elif not isinstance(domain, list):
        return params
    for idx, term in enumerate(domain):
        if isinstance(term, basestring) and term not in DOMAIN_OPERATORS:
            m = _term_re.match(term.strip())
            if not m:
                raise ValueError("Cannot parse term %r" % term)
            (field, operator, value) = m.groups()
            try:
                value = literal_eval(value)
            except Exception:
                # Interpret the value as a string
                pass
            domain[idx] = (field, operator, value)
    if (kwargs or context) and len(params) == 1:
        params = (domain,
                  kwargs.pop('offset', 0),
                  kwargs.pop('limit', None),
                  kwargs.pop('order', None),
                  context)
    else:
        params = (domain,) + params[1:]
    return params


class Service(ServerProxy):
    def __init__(self, server, endpoint, methods):
        uri = server + '/xmlrpc/' + endpoint
        ServerProxy.__init__(self, uri, allow_none=True)
        self._methods = sorted(methods)

    def __repr__(self):
        rname = '%s%s' % (self._ServerProxy__host, self._ServerProxy__handler)
        return '<Service %s>' % rname
    __str__ = __repr__

    def __dir__(self):
        return self._methods

    def __getattr__(self, name):
        if name in self._methods:
            wrapper = lambda s, *args: s._ServerProxy__request(name, args)
            wrapper.__name__ = name
            return wrapper.__get__(self, type(self))
        raise AttributeError("'Service' object has no attribute %r" % name)


class Client(object):
    _config_file = os.path.join(os.path.curdir, CONF_FILE)

    def __init__(self, server, db, user, password=None):
        self._server = server
        self._db = db
        self._environment = None
        self.user = None
        major_version = None
        self._execute = None

        def get_proxy(name):
            if major_version in ('5.0', None):
                methods = _methods[name]
            else:
                # Only for OpenERP >= 6
                methods = _methods[name] + _methods_6_1[name]
            return Service(server, name, methods)
        self.server_version = ver = get_proxy('db').server_version()
        self.major_version = major_version = '.'.join(ver.split('.', 2)[:2])
        # Create the XML-RPC proxies
        self.db = get_proxy('db')
        self.common = get_proxy('common')
        self._object = get_proxy('object')
        self._wizard = get_proxy('wizard')
        self._report = get_proxy('report')
        # Try to login
        self._login(user, password)

    @classmethod
    def from_config(cls, environment):
        client = cls(*read_config(environment))
        client._environment = environment
        return client

    def __repr__(self):
        return "<Client '%s#%s'>" % (self._server, self._db)

    def login(self, user, password=None):
        (uid, password) = self._auth(user, password)
        if uid is False:
            print('Error: Invalid username or password')
            return
        self.user = user

        # Authenticated endpoints
        def authenticated(method):
            return functools.partial(method, self._db, uid, password)
        self._execute = authenticated(self._object.execute)
        self._exec_workflow = authenticated(self._object.exec_workflow)
        self._wizard_execute = authenticated(self._wizard.execute)
        self._wizard_create = authenticated(self._wizard.create)
        self.report = authenticated(self._report.report)
        self.report_get = authenticated(self._report.report_get)
        if self.major_version != '5.0':
            # Only for OpenERP >= 6
            self.execute_kw = authenticated(self._object.execute_kw)
            self.render_report = authenticated(self._report.render_report)
        return uid

    # Needed for interactive use
    _login = login
    _login.cache = {}

    def _check_valid(self, uid, password):
        execute = self._object.execute
        try:
            execute(self._db, uid, password, 'res.users', 'fields_get_keys')
            return True
        except Fault:
            return False

    def _auth(self, user, password):
        cache_key = (self._server, self._db, user)
        if password:
            # If password is explicit, call the 'login' method
            uid = None
        else:
            # Read from cache
            uid, password = self._login.cache.get(cache_key) or (None, None)
            # Read from table 'res.users'
            if not uid and self.access('res.users', 'write'):
                obj = self.read('res.users', [('login', '=', user)], 'id password')
                if obj:
                    uid = obj[0]['id']
                    password = obj[0]['password']
                else:
                    # Invalid user
                    uid = False
            # Ask for password
            if not password and uid is not False:
                from getpass import getpass
                password = getpass('Password for %r: ' % user)
        if uid:
            # Check if password changed
            if not self._check_valid(uid, password):
                if cache_key in self._login.cache:
                    del self._login.cache[cache_key]
                uid = False
        elif uid is None:
            # Do a standard 'login'
            uid = self.common.login(self._db, user, password)
        if uid:
            # Update the cache
            self._login.cache[cache_key] = (uid, password)
        return (uid, password)

    @classmethod
    def _set_interactive(cls, write=False):
        g = globals()
        # Don't call multiple times
        del Client._set_interactive
        global_names = ['wizard', 'exec_workflow', 'read', 'search',
                'count', 'model', 'keys', 'fields', 'field', 'access']
        if write:
            global_names.extend(['write', 'create', 'copy', 'unlink'])

        def connect(self, env=None):
            if env:
                client = self.from_config(env)
            else:
                client = self
                env = self._environment or self._db
            g['client'] = client
            # Tweak prompt
            sys.ps1 = '%s >>> ' % env
            sys.ps2 = '%s ... ' % env
            # Logged in?
            if client.user:
                g['do'] = client.execute
                for name in global_names:
                    g[name] = getattr(client, name)
                print('Logged in as %r' % (client.user,))
            else:
                g['do'] = None
                g.update(dict.fromkeys(global_names))

        def login(self, user):
            if self._login(user):
                # If successful, register the new globals()
                self.connect()

        # Set hooks to recreate the globals()
        cls.login = login
        cls.connect = connect

    def execute(self, obj, method, *params, **kwargs):
        assert isinstance(obj, basestring) and isinstance(method, basestring)
        context = kwargs.pop('context', None)
        if method in ('read', 'name_get'):
            assert params
            if issearchdomain(params[0]):
                # Combine search+read
                search_params = searchargs(params[:1], kwargs, context)
                ids = self._execute(obj, 'search', *search_params)
            else:
                ids = params[0]
            if len(params) > 1:
                params = (ids,) + params[1:]
            elif method == 'read':
                params = (ids, kwargs.pop('fields', None))
            else:
                params = (ids,)
        elif method == 'search':
            # Accept keyword arguments for the search method
            params = searchargs(params, kwargs, context)
            context = None
        elif method == 'search_count':
            params = searchargs(params)
        if context:
            params = params + (context,)
        # Ignore extra keyword arguments
        for item in kwargs.items():
            print('Ignoring: %s = %r' % item)
        return self._execute(obj, method, *params)

    def exec_workflow(self, obj, signal, obj_id):
        assert isinstance(obj, basestring) and isinstance(signal, basestring)
        return self._exec_workflow(obj, signal, obj_id)

    def wizard(self, name, datas=None, action='init', context=None):
        if isinstance(name, int_types):
            wiz_id = name
        else:
            wiz_id = self._wizard_create(name)
        if datas is None:
            if action == 'init' and name != wiz_id:
                return wiz_id
            datas = {}
        return self._wizard_execute(wiz_id, datas, action, context)

    def _upgrade(self, modules, button):
        # Click upgrade/install/uninstall button
        ids = self.search('ir.module.module', [('name', 'in', modules)])
        if ids is None:
            return
        self.execute('ir.module.module', button, ids)
        mods = self.read('ir.module.module',
                         [('state', 'not in', STABLE_STATES)], 'name state')
        if not mods:
            return
        print('%s module(s) selected' % len(ids))
        print('%s module(s) to update:' % len(mods))
        for mod in mods:
            print('  %(state)s\t%(name)s' % mod)

        if self.major_version == '5.0':
            # Wizard "Apply Scheduled Upgrades"
            rv = self.wizard('module.upgrade', action='start')
            if 'config' not in [state[0] for state in rv.get('state', ())]:
                # Something bad happened
                return rv
        else:
            self.execute('base.module.upgrade', 'upgrade_module', [])

    def upgrade(self, *modules):
        # Button "Schedule Upgrade"
        return self._upgrade(modules, button='button_upgrade')

    def install(self, *modules):
        # Button "Schedule for Installation"
        return self._upgrade(modules, button='button_install')

    def uninstall(self, *modules):
        # Button "Uninstall (beta)"
        return self._upgrade(modules, button='button_uninstall')

    def search(self, obj, *params, **kwargs):
        return self.execute(obj, 'search', *params, **kwargs)

    def count(self, obj, domain=None):
        return self.execute(obj, 'search_count', domain or [])

    def read(self, obj, *params, **kwargs):
        """Wrapper for client.execute(obj, 'read', [...], ('a', 'b')).

        The first argument is the 'model' name (example: 'res.partner')

        The second argument, 'domain', accepts:
         - [('name', '=', 'mushroom'), ('state', '!=', 'draft')]
         - ['name = mushroom', 'state != draft']
         - []

        The third argument, 'fields', accepts:
         - ('street', 'city')
         - 'street city'
         - '%(street)s %(city)s'
        """
        fmt = None
        if len(params) > 1 and isinstance(params[1], basestring):
            fmt = ('%(' in params[1]) and params[1]
            if fmt:
                fields = _fields_re.findall(fmt)
            else:
                # transform: "zip city" --> ("zip", "city")
                fields = params[1].split()
                if len(fields) == 1:
                    fmt = ()    # marker
            params = (params[0], fields) + params[2:]
        res = self.execute(obj, 'read', *params, **kwargs)
        if not res:
            return res
        if fmt:
            if isinstance(res, list):
                return [fmt % d for d in res]
            return fmt % res
        if fmt == ():
            if isinstance(res, list):
                return [d[fields[0]] for d in res]
            return res[fields[0]]
        return res

    def model(self, name):
        domain = [('model', 'like', name)]
        models = self.execute('ir.model', 'read', domain, ('model',))
        if models:
            return sorted([m['model'] for m in models])

    def modules(self, name='', installed=None):
        domain = [('name', 'like', name)]
        if installed is not None:
            op = installed and '=' or '!='
            domain.append(('state', op, 'installed'))
        mods = self.read('ir.module.module', domain, 'name state')
        if mods:
            res = {}
            for mod in mods:
                if mod['state'] in res:
                    res[mod['state']].append(mod['name'])
                else:
                    res[mod['state']] = [mod['name']]
            return res

    def keys(self, obj):
        obj_keys = self.execute(obj, 'fields_get_keys')
        return obj_keys and sorted(obj_keys)

    def fields(self, obj, names=None):
        return self.execute(obj, 'fields_get', names)

    def field(self, obj, name):
        return self.execute(obj, 'fields_get', (name,))[name]

    def access(self, obj, mode='read'):
        try:
            self._execute('ir.model.access', 'check', obj, mode)
            return True
        except (TypeError, Fault):
            return False

    def __getattr__(self, method):
        if method.startswith('__'):
            raise AttributeError("'Client' object has no attribute %r" % method)
        # miscellaneous object methods
        def wrapper(self, obj, *params, **kwargs):
            """Wrapper for client.execute(obj, %r, *params, **kwargs)."""
            return self.execute(obj, method, *params, **kwargs)
        wrapper.__name__ = method
        wrapper.__doc__ %= method
        return wrapper.__get__(self, type(self))


def _interact(use_pprint=True, usage=USAGE):
    import code
    try:
        import builtins
        _exec = getattr(builtins, 'exec')
    except ImportError:
        def _exec(code, g):
            exec('exec code in g')
        import __builtin__ as builtins
    # Do not run twice
    del globals()['_interact']

    def excepthook(exc_type, exc, tb, _original_hook=sys.excepthook):
        # Print readable 'Fault' errors
        if (issubclass(exc_type, Fault) and
            isinstance(exc.faultCode, basestring)):
            etype, _, msg = exc.faultCode.partition('--')
            if etype.strip() != 'warning':
                msg = exc.faultCode
                if not msg.startswith('FATAL:'):
                    msg += '\n' + exc.faultString
            print('%s: %s' % (exc_type.__name__, msg.strip()))
        else:
            _original_hook(exc_type, exc, tb)

    if use_pprint:
        def displayhook(value, _printer=pprint, _builtins=builtins):
            # Pretty-format the output
            if value is None:
                return
            _printer(value)
            _builtins._ = value
        sys.displayhook = displayhook

    class Usage(object):
        def __call__(self):
            print(usage)
        __repr__ = lambda s: usage
    builtins.usage = Usage()

    try:
        __import__('readline')
    except ImportError:
        pass

    class Console(code.InteractiveConsole):
        def runcode(self, code):
            try:
                _exec(code, globals())
            except SystemExit:
                raise
            except:
                # Work around http://bugs.python.org/issue12643
                excepthook(*sys.exc_info())

    warnings.simplefilter('always', UserWarning)
    # Key UP to avoid an empty line
    Console().interact('\033[A')


def main():
    parser = optparse.OptionParser(
            usage='%prog [options] [id [id ...]]', version=__version__,
            description='Inspect data on OpenERP objects')
    parser.add_option('-l', '--list', action='store_true', dest='list_env',
            help='list sections of the configuration')
    parser.add_option('--env',
            help='read connection settings from the given section')
    parser.add_option('-c', '--config', default=CONF_FILE,
            help='specify alternate config file (default %r)' % CONF_FILE)
    parser.add_option('--server', default=DEFAULT_URL,
            help='full URL to the XML-RPC server '
                 '(default %s)' % DEFAULT_URL)
    parser.add_option('-d', '--db', default=DEFAULT_DB, help='database')
    parser.add_option('-u', '--user', default=DEFAULT_USER, help='username')
    parser.add_option('-p', '--password', default=DEFAULT_PASSWORD,
            help='password (yes this will be in your shell history and '
                 'ps from other users)')
    parser.add_option('-m', '--model',
            help='the type of object to find')
    parser.add_option('-s', '--search', action='append',
            help='search condition (multiple allowed); alternatively, pass '
                 'multiple IDs as positional parameters after the options')
    parser.add_option('-f', '--fields', action='append',
            help='restrict the output to certain fields (multiple allowed)')
    parser.add_option('-i', '--interact', action='store_true',
            help='use interactively')
    parser.add_option('--write', action='store_true',
            help='enable "write", "create", "copy" and "unlink" helpers')

    (args, ids) = parser.parse_args()

    Client._config_file = os.path.join(os.path.curdir, args.config)
    if args.list_env:
        print('Available settings:  ' + ' '.join(read_config()))
        return

    if (args.interact or not args.model):
        Client._set_interactive(write=args.write)
        print(USAGE)

    if args.env:
        client = Client.from_config(args.env)
    else:
        client = Client(args.server, args.db, args.user, args.password)

    if args.model:
        if args.search:
            (searchquery,) = searchargs((args.search,))
            ids = client.execute(args.model, 'search', searchquery)
        if ids is None:
            data = None
        elif args.fields:
            data = client.execute(args.model, 'read', ids, args.fields)
        else:
            data = client.execute(args.model, 'read', ids)
        pprint(data)

    if hasattr(client, 'connect'):
        # Set the globals()
        client.connect()
        # Enter interactive mode
        _interact()

if __name__ == '__main__':
    main()
