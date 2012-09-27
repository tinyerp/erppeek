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
import time
import traceback
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


__version__ = '1.3'
__all__ = ['Client', 'Model', 'Record', 'RecordList', 'Service',
           'format_exception', 'read_config']

CONF_FILE = 'erppeek.ini'
HIST_FILE = os.path.expanduser('~/.erppeek_history')
DEFAULT_URL = 'http://localhost:8069'
DEFAULT_DB = 'openerp'
DEFAULT_USER = 'admin'
MAXCOL = [79, 179, 9999]    # Line length in verbose mode

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

    models(name)                    # List models matching pattern
    model(name)                     # Return a Model instance
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
# Supported operators are:
#   =, !=, >, >=, <, <=, like, ilike, in, not like, not ilike, not in, child_of
#   =like, =ilike (6.0), =? (6.0)
_term_re = re.compile(
    '([\w._]+)\s*'  '(=(?:like|ilike|\?)|[<>!]=|[<>=]'
    '|(?<= )(?:like|ilike|in|not like|not ilike|not in|child_of))'  '\s*(.*)')
_fields_re = re.compile(r'(?:[^%]|^)%\(([^)]+)\)')

# Published object methods
_methods = {
    'db': ['create', 'drop', 'dump', 'restore', 'rename',
           'get_progress', 'list', 'list_lang',
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
#  - 'common': ['get_available_updates', 'get_migration_scripts',
#               'set_loglevel']
_cause_message = ("\nThe above exception was the direct cause "
                  "of the following exception:\n\n")


def mixedcase(s, _cache={}):
    """Convert to MixedCase.

    >>> mixedcase('res.company')
    'ResCompany'
    """
    try:
        return _cache[s]
    except KeyError:
        _cache[s] = s = ''.join([w.capitalize() for w in s.split('.')])
    return s


def lowercase(s, _sub=re.compile('[A-Z]').sub,
              _repl=(lambda m: '.' + m.group(0).lower()), _cache={}):
    """Convert to lowercase with dots.

    >>> lowercase('ResCompany')
    'res.company'
    """
    try:
        return _cache[s]
    except KeyError:
        _cache[s] = s = _sub(_repl, s).lstrip('.')
        return s


def format_exception(exc_type, exc, tb, limit=None, chain=True,
                     _format_exception=traceback.format_exception):
    """Format a stack trace and the exception information.

    This wrapper is a replacement of ``traceback.format_exception``
    which formats the error and traceback received by XML-RPC.
    If `chain` is True, then the original exception is printed too.
    """
    values = _format_exception(exc_type, exc, tb, limit=limit)
    if ((issubclass(exc_type, Fault) and
         isinstance(exc.faultCode, basestring))):
        # Format readable 'Fault' errors
        etype, _, msg = exc.faultCode.partition('--')
        server_tb = None
        if etype.strip() != 'warning':
            msg = exc.faultCode
            if not msg.startswith('FATAL:'):
                server_tb = exc.faultString
        fault = '%s: %s\n' % (exc_type.__name__, msg.strip())
        if chain:
            values = [server_tb or fault, _cause_message] + values
            values[-1] = fault
        else:
            values = [server_tb or fault]
    return values


def read_config(section=None):
    """Read the environment settings from the configuration file.

    The config file ``erppeek.ini`` contains a `section` for each environment.
    Each section provides parameters for the connection: ``host``, ``port``,
    ``database``, ``user`` and (optional) ``password``.  Default values are
    read from the ``[DEFAULT]`` section.  If the ``password`` is not in the
    configuration file, it is requested on login.
    Return a tuple ``(server, db, user, password or None)``.
    Without argument, it returns the list of configured environments.
    """
    p = configparser.SafeConfigParser()
    with open(Client._config_file) as f:
        p.readfp(f)
    if section is None:
        return p.sections()
    env = dict(p.items(section))
    scheme = env.get('scheme', 'http')
    server = '%s://%s:%s' % (scheme, env['host'], env['port'])
    return (server, env['database'], env['username'], env.get('password'))


def issearchdomain(arg):
    """Check if the argument is a search domain.

    Examples:
      - ``[('name', '=', 'mushroom'), ('state', '!=', 'draft')]``
      - ``['name = mushroom', 'state != draft']``
      - ``[]``
    """
    # These ones are supported but discouraged:
    # - 'state != draft'
    # - ('state', '!=', 'draft')
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
    """A wrapper around XML-RPC endpoints.

    The connected endpoints are exposed on the Client instance.
    The `server` argument is the URL of the server (scheme+host+port).
    The `endpoint` argument is the last part of the URL
    (examples: ``"object"``, ``"db"``).  The `methods` is the list of methods
    which should be exposed on this endpoint.  Use ``dir(...)`` on the
    instance to list them.
    """
    def __init__(self, server, endpoint, methods, verbose=False):
        uri = server + '/xmlrpc/' + endpoint
        ServerProxy.__init__(self, uri, allow_none=True)
        self._endpoint = endpoint
        self._methods = sorted(methods)
        self._verbose = verbose

    def __repr__(self):
        rname = '%s%s' % (self._ServerProxy__host, self._ServerProxy__handler)
        return '<Service %s>' % rname
    __str__ = __repr__

    def __dir__(self):
        return self._methods

    def __getattr__(self, name):
        if name not in self._methods:
            raise AttributeError("'Service' object has no attribute %r" % name)
        if self._verbose:
            def sanitize(args, _pos=(self._endpoint == 'db') and 999 or 2):
                if len(args) > _pos:
                    args = list(args)
                    args[_pos] = '*'
                return args
            maxcol = MAXCOL[min(len(MAXCOL), self._verbose) - 1]

            def wrapper(self, *args):
                snt = ', '.join([repr(arg) for arg in sanitize(args)])
                snt = '%s.%s(%s)' % (self._endpoint, name, snt)
                if len(snt) > maxcol:
                    suffix = '... L=%s' % len(snt)
                    snt = snt[:maxcol - len(suffix)] + suffix
                print('--> ' + snt)
                res = self._ServerProxy__request(name, args)
                rcv = str(res)
                if len(rcv) > maxcol:
                    suffix = '... L=%s' % len(rcv)
                    rcv = rcv[:maxcol - len(suffix)] + suffix
                print('<-- ' + rcv)
                return res
        else:
            wrapper = lambda s, *args: s._ServerProxy__request(name, args)
        wrapper.__name__ = name
        return wrapper.__get__(self, type(self))


class Client(object):
    """Connection to an OpenERP instance.

    This is the top level object.
    The `server` is the URL of the instance, like ``http://localhost:8069``.
    The `db` is the name of the database and the `user` should exist in the
    table ``res.users``.  If the `password` is not provided, it will be
    asked on login.
    """
    _config_file = os.path.join(os.path.curdir, CONF_FILE)

    def __init__(self, server, db=None, user=None, password=None,
                 verbose=False):
        self._server = server
        self._db = ()
        self._environment = None
        self.user = None
        self._execute = None
        self._models = {}
        major_version = None

        def get_proxy(name):
            if major_version in ('5.0', None):
                methods = _methods[name]
            else:
                # Only for OpenERP >= 6
                methods = _methods[name] + _methods_6_1[name]
            return Service(server, name, methods, verbose=verbose)
        self.server_version = ver = get_proxy('db').server_version()
        self.major_version = major_version = '.'.join(ver.split('.', 2)[:2])
        # Create the XML-RPC proxies
        self.db = get_proxy('db')
        self.common = get_proxy('common')
        self._object = get_proxy('object')
        self._wizard = get_proxy('wizard')
        self._report = get_proxy('report')
        if db:
            # Try to login
            self._login(user, password=password, database=db)

    @classmethod
    def from_config(cls, environment, verbose=False):
        """Create a connection to a defined environment.

        Read the settings from the section ``[environment]`` in the
        ``erppeek.ini`` file and return a connected :class:`Client`.
        See :func:`read_config` for details of the configuration file format.
        """
        server, db, user, password = read_config(environment)
        client = cls(server, db, user, password, verbose=verbose)
        client._environment = environment
        return client

    def __repr__(self):
        return "<Client '%s#%s'>" % (self._server, self._db)

    def login(self, user, password=None, database=None):
        """Switch `user` and (optionally) `database`.

        If the `password` is not available, it will be asked.
        """
        previous_db = self._db
        if database:
            dbs = self.db.list()
            if database not in dbs:
                print("Error: Database '%s' does not exist: %s" %
                      (database, dbs))
                return
            self._db = database
        elif not previous_db:
            print('Error: Not connected')
            return
        (uid, password) = self._auth(user, password)
        if uid:
            self.user = user
            if database and previous_db != database:
                self._environment = None
        else:
            if previous_db:
                self._db = previous_db
            print('Error: Invalid username or password')
            return

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
    connect = None
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
        assert self._db
        cache_key = (self._server, self._db, user)
        if password:
            # If password is explicit, call the 'login' method
            uid = None
        else:
            # Read from cache
            uid, password = self._login.cache.get(cache_key) or (None, None)
            # Read from table 'res.users'
            if not uid and self.access('res.users', 'write'):
                obj = self.read('res.users',
                                [('login', '=', user)], 'id password')
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
    def _set_interactive(cls):
        # Don't call multiple times
        del Client._set_interactive
        global_names = ['wizard', 'exec_workflow', 'read', 'search', 'count',
                        'model', 'models', 'keys', 'fields', 'field', 'access']

        def connect(self, env=None):
            """Connect to another environment and replace the globals()."""
            if env:
                client = self.from_config(env, verbose=self.db._verbose)
            else:
                client = self
                env = self._environment or self._db
            g = globals()
            g['client'] = client
            # Tweak prompt
            sys.ps1 = '%s >>> ' % (env,)
            sys.ps2 = '%s ... ' % (env,)
            # Logged in?
            if client.user:
                g['do'] = client.execute
                for name in global_names:
                    g[name] = getattr(client, name)
                print('Logged in as %r' % (client.user,))
            else:
                g['do'] = None
                g.update(dict.fromkeys(global_names))

        def login(self, user, password=None, database=None):
            """Switch `user` and (optionally) `database`."""
            if self._login(user, password=password, database=database):
                # Register the new globals()
                self.connect()

        # Set hooks to recreate the globals()
        cls.login = login
        cls.connect = connect

    def create_database(self, passwd, database, demo=False, lang='en_US',
                        user_password='admin'):
        """Create a new database.

        The superadmin `passwd` and the `database` name are mandatory.
        By default, `demo` data are not loaded and `lang` is ``en_US``.
        Wait for the thread to finish and login if successful.
        """
        thread_id = self.db.create(passwd, database, demo, lang, user_password)
        progress = 0
        try:
            while progress < 1:
                time.sleep(3)
                progress, users = self.db.get_progress(passwd, thread_id)
            # [1.0, [{'login': 'admin', 'password': 'admin',
            #         'name': 'Administrator'}]]
            self.login(users[0]['login'], users[0]['password'],
                       database=database)
        except KeyboardInterrupt:
            print({'id': thread_id, 'progress': progress})

    def execute(self, obj, method, *params, **kwargs):
        """Wrapper around ``object.execute`` RPC method.

        Argument `method` is the name of an ``osv.osv`` method or
        a method available on this `obj`.
        Method `params` are allowed.  If needed, keyword
        arguments are collected in `kwargs`.
        """
        assert isinstance(obj, basestring)
        assert isinstance(method, basestring) and method != 'browse'
        context = kwargs.pop('context', None)
        ordered = None
        if method in ('read', 'name_get'):
            assert params
            if issearchdomain(params[0]):
                # Combine search+read
                search_params = searchargs(params[:1], kwargs, context)
                ordered = len(search_params) > 3 and search_params[3]
                ids = self._execute(obj, 'search', *search_params)
            elif isinstance(params[0], list):
                ordered = kwargs.pop('order', False) and params[0]
                ids = set(params[0])
                ids.discard(False)
                if not ids:
                    return [False] * len(ordered)
                ids = sorted(ids)
            else:
                ids = params[0]
            if not ids:
                return []
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
        elif method == 'perm_read':
            # broken with a single id (verified with 5.0 and 6.1)
            if params and isinstance(params[0], int_types):
                params = ([params[0]],) + params[1:]
        if context:
            params = params + (context,)
        # Ignore extra keyword arguments
        for item in kwargs.items():
            print('Ignoring: %s = %r' % item)
        res = self._execute(obj, method, *params)
        if res and ordered:
            # The results are not in the same order as the ids
            # when received from the server
            assert len(res) == len(set(ids))
            resdic = dict([(val['id'], val) for val in res])
            if isinstance(ordered, list):
                res = [id_ and resdic[id_] for id_ in ordered]
            else:
                res = [resdic[id_] for id_ in ids]
        return res

    def exec_workflow(self, obj, signal, obj_id):
        """Wrapper around ``object.exec_workflow`` RPC method.

        Argument `obj` is the name of the model.  The `signal`
        is sent to the object identified by its integer ``id`` `obj_id`.
        """
        assert isinstance(obj, basestring) and isinstance(signal, basestring)
        return self._exec_workflow(obj, signal, obj_id)

    def wizard(self, name, datas=None, action='init', context=None):
        """Wrapper around ``wizard.create`` and ``wizard.execute``
        RPC methods.

        If only `name` is provided, a new wizard is created and its ``id`` is
        returned.  If `action` is not ``"init"``, then the action is executed.
        In this case the `name` is either an ``id`` or a string.
        If the `name` is a string, the wizard is created before the execution.
        The optional `datas` argument provides data for the action.
        The optional `context` argument is passed to the RPC method.
        """
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
        # First, update the list of modules
        updated, added = self.execute('ir.module.module', 'update_list')
        if added:
            print('%s module(s) added to the list' % added)
        # Find modules
        ids = modules and self.search('ir.module.module',
                                      [('name', 'in', modules)])
        if ids:
            # Click upgrade/install/uninstall button
            self.execute('ir.module.module', button, ids)
        mods = self.read('ir.module.module',
                         [('state', 'not in', STABLE_STATES)], 'name state')
        if not mods:
            if modules:
                print('Module(s) not found: %s' % ', '.join(modules))
            else:
                print('%s module(s) updated' % updated)
            return
        print('%s module(s) selected' % len(ids))
        print('%s module(s) to process:' % len(mods))
        for mod in mods:
            print('  %(state)s\t%(name)s' % mod)

        # Empty the models' cache
        self._models.clear()

        # Apply scheduled upgrades
        if self.major_version == '5.0':
            # Wizard "Apply Scheduled Upgrades"
            rv = self.wizard('module.upgrade', action='start')
            if 'config' not in [state[0] for state in rv.get('state', ())]:
                # Something bad happened
                return rv
        else:
            self.execute('base.module.upgrade', 'upgrade_module', [])

    def upgrade(self, *modules):
        """Press the button ``Upgrade``."""
        return self._upgrade(modules, button='button_upgrade')

    def install(self, *modules):
        """Press the button ``Install``."""
        return self._upgrade(modules, button='button_install')

    def uninstall(self, *modules):
        """Press the button ``Uninstall``."""
        return self._upgrade(modules, button='button_uninstall')

    def search(self, obj, *params, **kwargs):
        """Filter the records in the `domain`, return the ``ids``."""
        return self.execute(obj, 'search', *params, **kwargs)

    def count(self, obj, domain=None):
        """Count the records in the `domain`."""
        return self.execute(obj, 'search_count', domain or [])

    def read(self, obj, *params, **kwargs):
        """Wrapper for ``client.execute(obj, 'read', [...], ('a', 'b'))``.

        The first argument `obj` is the model name (example: ``"res.partner"``)

        The second argument, `domain`, accepts:
         - ``[('name', '=', 'mushroom'), ('state', '!=', 'draft')]``
         - ``['name = mushroom', 'state != draft']``
         - ``[]``
         - a list of ids ``[1, 2, 3]`` or a single id ``42``

        The third argument, `fields`, accepts:
         - a single field: ``'first_name'``
         - a tuple of fields: ``('street', 'city')``
         - a space separated string: ``'street city'``
         - a format spec: ``'%(street)s %(city)s'``

        If `fields` is omitted, all fields are read.

        If `domain` is a single id, then:
         - return a single value if a single field is requested.
         - return a string if a format spec is passed in the `fields` argument.
         - else, return a dictionary.

        If `domain` is not a single id, the returned value is a list of items.
        Each item complies with the rules of the previous paragraph.

        The optional keyword arguments `offset`, `limit` and `order` are
        used to restrict the search.  The `order` is also used to order the
        results returned.  Note: the low-level RPC method ``read`` itself does
        not preserve the order of the results.
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
                return [(d and fmt % d) for d in res]
            return fmt % res
        if fmt == ():
            if isinstance(res, list):
                return [(d and d[fields[0]]) for d in res]
            return res[fields[0]]
        return res

    def _model(self, name):
        try:
            return self._models[name]
        except KeyError:
            # m = Model(self, name)
            m = object.__new__(Model)
        m._init(self, name)
        self._models[name] = m
        return m

    def models(self, name=''):
        """Return a dictionary of models.

        The argument `name` is a pattern to filter the models returned.
        If omitted, all models are returned.
        Keys are camel case names of the models.
        Values are instances of :class:`Model`.

        The return value can be used to declare the models in the global
        namespace:

        >>> globals().update(client.models('res.'))
        """
        domain = [('model', 'like', name)]
        models = self.execute('ir.model', 'read', domain, ('model',))
        names = [m['model'] for m in models]
        return dict([(mixedcase(name), self._model(name)) for name in names])

    def model(self, name):
        """Return a :class:`Model` instance.

        The argument `name` is the name of the model.
        """
        try:
            return self._models[name]
        except KeyError:
            models = self.models(name)
        if name in self._models:
            return self._models[name]
        if models:
            errmsg = 'Model not found.  These models exist:'
        else:
            errmsg = 'Model not found: %s' % (name,)
        print('\n * '.join([errmsg] + [str(m) for m in models.values()]))

    def modules(self, name='', installed=None):
        """Return a dictionary of modules.

        The optional argument `name` is a pattern to filter the modules.
        If the boolean argument `installed` is :const:`True`, the modules
        which are "Not Installed" or "Not Installable" are omitted.  If
        the argument is :const:`False`, only these modules are returned.
        If argument `installed` is omitted, all modules are returned.
        The return value is a dictionary where module names are grouped in
        lists according to their ``state``.
        """
        domain = [('name', 'like', name)]
        if installed is not None:
            op = installed and 'not in' or 'in'
            domain.append(('state', op, ['uninstalled', 'uninstallable']))
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
        """Wrapper for :meth:`Model.keys` method."""
        return self.model(obj).keys()

    def fields(self, obj, names=None):
        """Wrapper for :meth:`Model.fields` method."""
        return self.model(obj).fields(names=names)

    def field(self, obj, name):
        """Wrapper for :meth:`Model.field` method."""
        return self.model(obj).field(name)

    def access(self, obj, mode='read'):
        """Wrapper for :meth:`Model.access` method."""
        try:
            self._execute('ir.model.access', 'check', obj, mode)
            return True
        except (TypeError, Fault):
            return False

    def __getattr__(self, method):
        if not method.islower():
            rv = self.model(lowercase(method))
            self.__dict__[method] = rv
            return rv
        if method.startswith('__'):
            raise AttributeError("'Client' object has no attribute %r" %
                                 method)

        # miscellaneous object methods
        def wrapper(self, obj, *params, **kwargs):
            """Wrapper for client.execute(obj, %r, *params, **kwargs)."""
            return self.execute(obj, method, *params, **kwargs)
        wrapper.__name__ = method
        wrapper.__doc__ %= method
        return wrapper.__get__(self, type(self))


class Model(object):
    """The class for OpenERP models."""

    def __new__(cls, client, name):
        return client.model(name)

    def _init(self, client, name):
        self.client = client
        self._name = name
        self._execute = functools.partial(client.execute, name)
        self.search = functools.partial(client.search, name)
        self.count = functools.partial(client.count, name)
        self.read = functools.partial(client.read, name)

    def __repr__(self):
        return "<Model '%s'>" % (self._name,)

    def _get_keys(self):
        obj_keys = self._execute('fields_get_keys')
        obj_keys.sort()
        return obj_keys

    def _get_fields(self):
        return self._execute('fields_get')

    def keys(self):
        """Return the keys of the model."""
        return self._keys

    def fields(self, names=None):
        """Return a dictionary of the fields of the model.

        Optional argument `names` is a sequence of field names or
        a space separated string of these names.
        If omitted, all fields are returned.
        """
        if names is None:
            return self._fields
        if isinstance(names, basestring):
            names = names.split()
        return dict([(k, v) for (k, v) in self._fields.items() if k in names])

    def field(self, name):
        """Return the field properties for field `name`."""
        return self._fields[name]

    def access(self, mode="read"):
        """Check if the user has access to this model.

        Optional argument `mode` is the access mode to check.  Valid values
        are ``read``, ``write``, ``create`` and ``unlink``. If omitted,
        the ``read`` mode is checked.  Return a boolean.
        """
        return self.client.access(self._name, mode)

    def browse(self, domain, *params, **kwargs):
        """Return a :class:`Record` or a :class:`RecordList`.

        The argument `domain` accepts a single integer ``id``, a list of ids
        or a search domain.
        If it is a single integer, the return value is a :class:`Record`.
        Otherwise, the return value is a :class:`RecordList`.
        """
        context = kwargs.pop('context', None)
        if isinstance(domain, int_types):
            assert not params and not kwargs
            return Record(self, domain, context=context)
        if issearchdomain(domain):
            params = searchargs((domain,) + params, kwargs, context)
            domain = self._execute('search', *params)
            # Ignore extra keyword arguments
            for item in kwargs.items():
                print('Ignoring: %s = %r' % item)
        else:
            assert not params and not kwargs
        return RecordList(self, domain, context=context)

    def get(self, domain, context=None):
        """Return a single :class:`Record`.

        The argument `domain` accepts a single integer ``id`` or a
        search domain.  The return value is a :class:`Record` or None.
        If multiple records are found, a ``ValueError`` is raised.
        """
        if isinstance(domain, int_types):
            return Record(self, domain, context=context)
        assert issearchdomain(domain)
        params = searchargs((domain,), context=context)
        ids = self._execute('search', *params)
        if len(ids) > 1:
            raise ValueError('domain matches too many records (%d)' % len(ids))
        return ids and Record(self, ids[0], context=context) or None

    def create(self, values, context=None):
        """Create a :class:`Record`.

        The argument `values` is a dictionary of values which are used to
        create the record.  The newly created :class:`Record` is returned.
        """
        values = self._unbrowse_values(values)
        new_id = self._execute('create', values, context=context)
        return Record(self, new_id, context=context)

    def _browse_values(self, values, context=None):
        """Wrap the values of a Record.

        The argument `values` is a dictionary of values read from a Record.
        When the field type is relational (many2one, one2many or many2many),
        the value is wrapped in a Record or a RecordList.
        Return a dictionary with the same keys as the `values` argument.
        """
        for key, value in values.items():
            if key == 'id':
                continue
            field = self._fields[key]
            field_type = field['type']
            if field_type == 'many2one':
                if value:
                    rel_model = self.client.model(field['relation'])
                    values[key] = Record(rel_model, value, context=context)
            elif field_type in ('one2many', 'many2many'):
                rel_model = self.client.model(field['relation'])
                values[key] = RecordList(rel_model, value, context=context)
            elif field_type == 'reference':
                if value:
                    res_model, res_id = value.split(',')
                    values[key] = Record(self.client.model(res_model), int(res_id))
        return values

    def _unbrowse_values(self, values):
        """Unwrap the id of Record and RecordList."""
        new_values = values.copy()
        for key, value in values.items():
            field_type = self._fields[key]['type']
            if isinstance(value, (Record, RecordList)):
                if field_type == 'reference':
                    new_values[key] = '%s,%s' % (value._model_name, value.id)
                else:
                    new_values[key] = value = value.id
            if field_type in ('one2many', 'many2many'):
                if not value:
                    new_values[key] = [(6, 0, [])]
                elif isinstance(value[0], (int, long)):
                    new_values[key] = [(6, 0, value)]
        return new_values

    def __getattr__(self, attr):
        if attr in ('_keys', '_fields'):
            self.__dict__[attr] = rv = getattr(self, '_get' + attr)()
            return rv
        if attr.startswith('__'):
            raise AttributeError("'Model' object has no attribute %r" % attr)

        def wrapper(self, *params, **kwargs):
            """Wrapper for client.execute(%r, %r, *params, **kwargs)."""
            return self._execute(attr, *params, **kwargs)
        wrapper.__name__ = attr
        wrapper.__doc__ %= (self._name, attr)
        self.__dict__[attr] = mobj = wrapper.__get__(self, type(self))
        return mobj


class RecordList(object):
    """A sequence of OpenERP :class:`Record`."""

    def __init__(self, res_model, ids, context=None):
        _ids = []
        for id_ in ids:
            if isinstance(id_, list):
                _ids.append(id_[0])
            else:
                _ids.append(id_)
        # Bypass the __setattr__ method
        self.__dict__.update({
            # 'client': res_model.client,
            'id': _ids,
            '_model_name': res_model._name,
            '_model': res_model,
            '_idnames': ids,
            '_context': context,
        })

    def __repr__(self):
        if len(self.id) > 16:
            ids = 'length=%d' % len(self.id)
        else:
            ids = self.id
        return "<RecordList '%s,%s'>" % (self._model_name, ids)

    def __dir__(self):
        return ['__getitem__', 'read', 'write', 'unlink',
                'id', '_context', '_idnames', '_model', '_model_name']

    def __len__(self):
        return len(self.id)

    def read(self, fields=None, context=None):
        """Wrapper for :meth:`Record.read` method."""
        if context is None and self._context:
            context = self._context

        client = self._model.client
        if self.id:
            values = client.read(self._model_name, self.id,
                                 fields, order=True, context=context)
            if values and isinstance(values[0], dict):
                browse_values = self._model._browse_values
                return [browse_values(v) for v in values]
        else:
            values = []

        if isinstance(fields, basestring):
            field = self._model._fields.get(fields)
            if field:
                if field['type'] == 'many2one':
                    rel_model = client.model(field['relation'])
                    return RecordList(rel_model, values, context=context)
                if field['type'] in ('one2many', 'many2many'):
                    rel_model = client.model(field['relation'])
                    return [RecordList(rel_model, v) for v in values]
                if field['type'] == 'reference':
                    records = []
                    for value in values:
                        if value:
                            res_model, res_id = value.split(',')
                            rel_model = client.model(res_model)
                            value = Record(rel_model, int(res_id))
                        records.append(value)
                    return records
        return values

    def write(self, values, context=None):
        """Write the `values` in the :class:`RecordList`."""
        if context is None and self._context:
            context = self._context
        values = self._model._unbrowse_values(values)
        rv = self._model._execute('write', self.id, values, context=context)
        return rv

    def __getitem__(self, key):
        idname = self._idnames[key]
        if idname is False:
            return False
        cls = isinstance(key, slice) and RecordList or Record
        return cls(self._model, idname, context=self._context)

    def __getattr__(self, attr):
        context = self._context
        if attr in self._model._keys:
            return self.read(attr, context=context)
        if attr.startswith('__'):
            errmsg = "'RecordList' object has no attribute %r" % attr
            raise AttributeError(errmsg)
        if attr == '_ids':
            # deprecated since 1.2.1
            warnings.warn("Attribute 'RecordList._ids' is deprecated, "
                          "use 'RecordList.id' instead.")
            return self.id
        model_name = self._model_name
        execute = self._model._execute

        def wrapper(self, *params, **kwargs):
            """Wrapper for client.execute(%r, %r, [...], *params, **kwargs)."""
            if context:
                kwargs.setdefault('context', context)
            return execute(attr, self.id, *params, **kwargs)
        wrapper.__name__ = attr
        wrapper.__doc__ %= (model_name, attr)
        self.__dict__[attr] = mobj = wrapper.__get__(self, type(self))
        return mobj

    def __setattr__(self, attr, value):
        if attr in self._model._keys or attr == 'id':
            msg = "attribute %r is read-only; use 'RecordList.write' instead."
        else:
            msg = "has no attribute %r"
        raise AttributeError("'RecordList' object %s" % msg % attr)


class Record(object):
    """A class for all OpenERP records.

    It maps any OpenERP object.
    The fields can be accessed through attributes.  The changes are immediately
    saved in the database.
    The ``many2one``, ``one2many`` and ``many2many`` attributes are followed
    when the record is read.  However when writing in these relational fields,
    use the appropriate syntax described in the official OpenERP documentation.
    The attributes are evaluated lazily, and they are cached in the record.
    The cache is invalidated if the :meth:`~Record.write` or the
    :meth:`~Record.unlink` method is called.
    """
    def __init__(self, res_model, res_id, context=None):
        if isinstance(res_id, list):
            (res_id, res_name) = res_id
            self.__dict__['_name'] = res_name
        # Bypass the __setattr__ method
        self.__dict__.update({
            'id': res_id,
            '_model_name': res_model._name,
            '_model': res_model,
            '_context': context,
        })

    def __repr__(self):
        return "<Record '%s,%d'>" % (self._model_name, self.id)

    def __str__(self):
        return self._name

    def _get_name(self):
        try:
            (id_name,) = self._model._execute('name_get', [self.id])
            name = '[%d] %s' % (self.id, id_name[1])
        except Exception:
            name = '[%d] -' % (self.id,)
        return name

    @property
    def _keys(self):
        return self._model._keys

    @property
    def _fields(self):
        return self._model._fields

    def _clear_cache(self):
        for key in self._model._keys:
            if key != 'id' and key in self.__dict__:
                delattr(self, key)

    def _update(self, values):
        new_values = self._model._browse_values(values, context=self._context)
        self.__dict__.update(new_values)
        return new_values

    def read(self, fields=None, context=None):
        """Read the `fields` of the :class:`Record`.

        The argument `fields` accepts different kinds of values.
        See :meth:`Client.read` for details.
        """
        if context is None and self._context:
            context = self._context
        rv = self._model.read(self.id, fields, context=context)
        if isinstance(rv, dict):
            return self._update(rv)
        elif isinstance(fields, basestring) and '%(' not in fields:
            return self._update({fields: rv})[fields]
        return rv

    def perm_read(self, context=None):
        """Read the metadata of the :class:`Record`.

        Return a dictionary of values.
        See :meth:`Client.perm_read` for details.
        """
        rv = self._model._execute('perm_read', [self.id], context=context)
        return rv and rv[0] or None

    def write(self, values, context=None):
        """Write the `values` in the :class:`Record`."""
        if context is None and self._context:
            context = self._context
        values = self._model._unbrowse_values(values)
        rv = self._model._execute('write', [self.id], values, context=context)
        self._clear_cache()
        return rv

    def unlink(self, context=None):
        """Delete the current :class:`Record` from the database."""
        if context is None and self._context:
            context = self._context
        rv = self._model._execute('unlink', [self.id], context=context)
        self._clear_cache()
        return rv

    def copy(self, default=None, context=None):
        """Copy a record and return the new :class:`Record`.

        The optional argument `default` is a mapping which overrides some
        values of the new record.
        """
        if context is None and self._context:
            context = self._context
        if default:
            default = self._model._unbrowse_values(default)
        new_id = self._model._execute('copy', self.id, default, context=context)
        return Record(self._model, new_id)

    def _send(self, signal):
        """Trigger workflow `signal` for this :class:`Record`."""
        return self._model.exec_workflow(signal, self.id)

    def __dir__(self):
        return ['read', 'write', 'copy', 'unlink', '_send',
                'id', '_context', '_model', '_model_name',
                '_name', '_keys', '_fields'] + self._model._keys

    def __getattr__(self, attr):
        context = self._context
        if attr in self._model._keys:
            return self.read(attr, context=context)
        if attr == '_name':
            self.__dict__['_name'] = name = self._get_name()
            return name
        if attr.startswith('__'):
            raise AttributeError("'Record' object has no attribute %r" % attr)
        if attr == 'client':
            # deprecated since 1.2.1
            warnings.warn("Attribute 'Record.client' is deprecated, "
                          "use 'Record._model.client' instead.")
            return self._model.client

        def wrapper(self, *params, **kwargs):
            """Wrapper for client.execute(%r, %r, %d, *params, **kwargs)."""
            if context:
                kwargs.setdefault('context', context)
            res = self._model._execute(attr, [self.id], *params, **kwargs)
            if isinstance(res, list) and len(res) == 1:
                return res[0]
            return res
        wrapper.__name__ = attr
        wrapper.__doc__ %= (self._model_name, attr, self.id)
        self.__dict__[attr] = mobj = wrapper.__get__(self, type(self))
        return mobj

    def __setattr__(self, attr, value):
        if attr not in self._model._keys:
            raise AttributeError("'Record' object has no attribute %r" % attr)
        if attr == 'id':
            raise AttributeError("'Record' object attribute 'id' is read-only")
        self.write({attr: value})
        if attr in self.__dict__:
            delattr(self, attr)


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
        import readline as rl
        import rlcompleter
    except ImportError:
        pass
    else:
        import atexit
        rl.parse_and_bind('tab: complete')
        if os.path.exists(HIST_FILE):
            rl.read_history_file(HIST_FILE)
            if rl.get_history_length() < 0:
                rl.set_history_length(int(os.environ.get('HISTSIZE', 500)))
            # better append instead of replace?
            atexit.register(rl.write_history_file, HIST_FILE)

    class Console(code.InteractiveConsole):
        def runcode(self, code):
            try:
                _exec(code, globals())
            except SystemExit:
                raise
            except:
                # Print readable 'Fault' errors
                # Work around http://bugs.python.org/issue12643
                exc_type, exc, tb = sys.exc_info()
                msg = ''.join(format_exception(exc_type, exc, tb, chain=False))
                print(msg.strip())

    warnings.simplefilter('always', UserWarning)
    # Key UP to avoid an empty line
    Console().interact('\033[A')


def main():
    description = ('Inspect data on OpenERP objects.  Use interactively '
                   'or query a model (-m) and pass search terms or '
                   'ids as positional parameters after the options.')
    parser = optparse.OptionParser(
        usage='%prog [options] [search_term_or_id [search_term_or_id ...]]',
        version=__version__,
        description=description)
    parser.add_option(
        '-l', '--list', action='store_true', dest='list_env',
        help='list sections of the configuration')
    parser.add_option(
        '--env',
        help='read connection settings from the given section')
    parser.add_option(
        '-c', '--config', default=CONF_FILE,
        help='specify alternate config file (default: %r)' % CONF_FILE)
    parser.add_option(
        '--server', default=DEFAULT_URL,
        help='full URL to the XML-RPC server (default: %s)' % DEFAULT_URL)
    parser.add_option('-d', '--db', default=DEFAULT_DB, help='database')
    parser.add_option('-u', '--user', default=DEFAULT_USER, help='username')
    parser.add_option(
        '-p', '--password', default=None,
        help='password, or it will be requested on login')
    parser.add_option(
        '-m', '--model',
        help='the type of object to find')
    parser.add_option(
        '-f', '--fields', action='append',
        help='restrict the output to certain fields (multiple allowed)')
    parser.add_option(
        '-i', '--interact', action='store_true',
        help='use interactively; default when no model is queried')
    parser.add_option(
        '-v', '--verbose', default=0, action='count',
        help='verbose')

    (args, domain) = parser.parse_args()

    Client._config_file = os.path.join(os.path.curdir, args.config)
    if args.list_env:
        print('Available settings:  ' + ' '.join(read_config()))
        return

    if (args.interact or not args.model):
        Client._set_interactive()
        print(USAGE)

    if args.env:
        client = Client.from_config(args.env, verbose=args.verbose)
    else:
        client = Client(args.server, args.db, args.user, args.password,
                        verbose=args.verbose)

    if args.model and domain and client.user:
        data = client.execute(args.model, 'read', domain, args.fields)
        pprint(data)

    if client.connect is not None:
        # Set the globals()
        client.connect()
        # Enter interactive mode
        _interact()

if __name__ == '__main__':
    main()
