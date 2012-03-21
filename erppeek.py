#!/usr/bin/env python
# -*- coding: utf-8 -*-
""" erppeek.py -- OpenERP command line tool

Authors: Alan Bell, Florent Xicluna
"""
from __future__ import with_statement

import xmlrpclib
import ConfigParser
import functools
import optparse
import os
from pprint import pprint
import re
import sys

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


__all__ = ['Client', 'read_config']

USE_PPRINT = True

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

ini_path = os.path.splitext(__file__)[0] + '.ini'

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
    p = ConfigParser.SafeConfigParser()
    with open(ini_path) as f:
        p.readfp(f)
    if section is None:
        return p.sections()
    server = 'http://%s:%s' % (p.get(section, 'host'), p.get(section, 'port'))
    db = p.get(section, 'database')
    user = p.get(section, 'username')
    password = p.get(section, 'password')
    return (server, db, user, password)


def faultmanagement(f):
    @functools.wraps(f)
    def wrapper(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except xmlrpclib.Fault, exc:
            if not isinstance(exc.faultCode, basestring):
                raise
            exctype, sep, msg = exc.faultCode.partition('--')
            if exctype.strip() != 'warning':
                msg = exc.faultCode
                if not msg.startswith('FATAL:'):
                    msg += '\n' + exc.faultString
            if f.__name__ == '__init__':
                # Raise an error if the instance is not created
                raise RuntimeError(msg.strip())
            else:
                print '%s: %s' % (type(exc).__name__, msg.strip())
    return wrapper


def issearchdomain(arg):
    """Check if the argument is a search domain.

    Examples:
      - [('name', '=', 'mushroom'), ('state', '!=', 'draft')]
      - ['name = mushroom', 'state != draft']
      - []
    """
    return isinstance(arg, list) and not (arg and (
            # Not a list of ids: [1, 2, 3]
            isinstance(arg[0], (int, long)) or
            # Not a list of ids as str: ['1', '2', '3']
            (isinstance(arg[0], basestring) and arg[0].isdigit())))


def searchargs(params, kwargs=None):
    """Compute the 'search' parameters."""
    if not params:
        return ([],)
    elif not isinstance(params[0], list):
        return params
    domain = params[0]
    for idx, term in enumerate(domain):
        if isinstance(term, basestring):
            if term in DOMAIN_OPERATORS:
                continue
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
    if kwargs and len(params) == 1:
        params = (domain,
                  kwargs.pop('offset', 0),
                  kwargs.pop('limit', None),
                  kwargs.pop('order', None),
                  kwargs.pop('context', None))
    else:
        params = (domain,) + params[1:]
    return params


class Client(object):

    @faultmanagement
    def __init__(self, server, db, user, password):
        def get_proxy(name, prefix=server + '/xmlrpc/'):
            return xmlrpclib.ServerProxy(prefix + name, allow_none=True)
        self.db = get_proxy('db')
        self.common = get_proxy('common')
        self._object = get_proxy('object')
        self._wizard = get_proxy('wizard')
        self._report = get_proxy('report')
        self._server = server
        self._db = db
        self.server_version = ver = self.db.server_version()
        self.major_version = major_version = '.'.join(ver.split('.', 2)[:2])
        m_db = _methods['db'][:]
        m_common = _methods['common'][:]
        # Set the special value returned by dir(...)
        self.db.__dir__ = lambda m=m_db: m
        self.common.__dir__ = lambda m=m_common: m
        if major_version[:2] != '5.':
            # Only for OpenERP >= 6
            m_db += _methods_6_1['db']
            m_common += _methods_6_1['common']
        # Try to login
        self._login(user, password)

    @faultmanagement
    def login(self, user, password=None):
        if password is None:
            from getpass import getpass
            password = getpass('Password for %r: ' % user)
        uid = self.common.login(self._db, user, password)
        if uid is False:
            print 'Error: Invalid username or password'
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
        if self.major_version[:2] != '5.':
            # Only for OpenERP >= 6
            self.execute_kw = authenticated(self._object.execute_kw)
            self.render_report = authenticated(self._report.render_report)
        return uid

    # Needed for interactive use
    _login = login

    @classmethod
    def from_config(cls, environment):
        return cls(*read_config(environment))

    @property
    def server(self):
        return self._server

    def __repr__(self):
        return "<Client '%s#%s'>" % (self._server, self._db)

    @faultmanagement
    def execute(self, obj, method, *params, **kwargs):
        if method in ('read', 'name_get') and params and issearchdomain(params[0]):
            # Combine search+read
            ids = self._execute(obj, 'search', *searchargs(params[:1], kwargs))
            params = (ids,) + params[1:]
        elif method == 'search':
            # Accept keyword arguments for the search method
            params = searchargs(params, kwargs)
        elif method == 'search_count':
            params = searchargs(params)
        if method == 'read':
            if len(params) == 1:
                params = (params[0], kwargs.pop('fields', None))
            if len(params) > 1 and isinstance(params[1], basestring):
                # transform: "zip city" --> ("zip", "city")
                params = (params[0], params[1].split()) + params[2:]
        if method == 'read' and len(params) == 1:
            params = (params[0], kwargs.pop('fields', None))
        # Ignore extra keyword arguments
        for item in kwargs.items():
            print 'Ignoring: %s = %r' % item
        return self._execute(obj, method, *params)

    @faultmanagement
    def exec_workflow(self, obj, signal, obj_id):
        return self._exec_workflow(obj, signal, obj_id)

    @faultmanagement
    def wizard(self, name, datas=None, action='init', context=None):
        if isinstance(name, (int, long)):
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
        print '%s module(s) selected' % len(ids)
        print '%s module(s) to update:' % len(mods)
        for mod in mods:
            print '  %(state)s\t%(name)s' % mod

        if self.major_version[:2] == '5.':
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
        return self.execute(obj, 'read', *params, **kwargs)

    def model(self, name):
        models = self.execute('ir.model', 'read', [('model', 'like', name)], ('model',))
        if models:
            return sorted([m['model'] for m in models])

    def modules(self, name, installed=None):
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


def _displayhook(value, _printer=pprint,
                 __builtin__=__import__('__builtin__')):
    # Pretty-format the output
    if value is None:
        return
    _printer(value)
    __builtin__._ = value


def _connect(env):
    client = Client.from_config(env)
    # Tweak prompt
    sys.ps1 = '%s >>> ' % env
    sys.ps2 = '%s ... ' % env
    return client


def main():
    parser = optparse.OptionParser(
            usage='%prog [options] [id [id ...]]',
            description='Inspect data on OpenERP objects')
    parser.add_option('-l', '--list', action='store_true', dest='list_env',
            help='list sections of %r' % ini_path)
    parser.add_option('--env',
            help='read connection settings from the given '
                 'section of %r' % ini_path)
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
    parser.add_option('-s', '--search', action='append', dest='search',
            help='search condition (multiple allowed); alternatively, pass '
                 'multiple IDs as positional parameters after the options')
    parser.add_option('-f', action='append', dest='fields',
            help='restrict the output to certain fields (multiple allowed)')
    parser.add_option('-i', action='store_true', dest='inspect',
            help='use interactively')

    (args, ids) = parser.parse_args()

    if args.list_env:
        print 'Available settings: ', ' '.join(read_config())
        return None, None

    if args.env:
        client = _connect(args.env)
    else:
        client = Client(args.server, args.db, args.user, args.password)

    if args.inspect or not args.model:
        try:
            # completion and history features
            __import__('readline')
        except ImportError:
            pass
        os.environ['PYTHONINSPECT'] = '1'
        if USE_PPRINT:
            sys.displayhook = _displayhook

    if not args.model:
        return client, None

    # do some searching if they pass in a search query, this will return a
    # bunch of IDs to pretty print or alternatively the user can pass in a
    # bunch of IDs on the command line to print
    searchquery = []
    if args.search:
        # print "search parsing"
        searchquery = searchargs((args.search,))[0]
        # print searchquery
        ids = client.execute(args.model, 'search', searchquery)

    if ids is None:
        data = None
    elif args.fields:
        data = client.execute(args.model, 'read', ids, args.fields)
    else:
        data = client.execute(args.model, 'read', ids)

    return (args.inspect and client), data


def _interactive_client():
    # Don't call multiple times
    del globals()['_interactive_client']

    def connect(env=None):
        g = globals()
        if env:
            client = _connect(env)
            g['client'] = client
        else:
            client = g['client']
        g['do'] = client.execute
        global_names = ('wizard', 'exec_workflow', 'read', 'search',
                        'count', 'model', 'keys', 'fields', 'field')
        for name in global_names:
            g[name] = getattr(client, name, None)

    def login(self, user):
        uid = self._login(user)
        if uid:
            self.connect()

    Client.login = login
    Client.connect = staticmethod(connect)
    connect()


if __name__ == '__main__':
    client, data = main()
    if data is not None:
        pprint(data)
    if client:
        # interactive usage
        _interactive_client()
        print USAGE
