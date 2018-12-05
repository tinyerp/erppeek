#!/usr/bin/env python
# -*- coding: utf-8 -*-
""" erppeek.py -- Odoo / OpenERP client library and command line tool

Author: Florent Xicluna
(derived from a script by Alan Bell)
"""
import _ast
import atexit
import csv
import functools
import json
import optparse
import os
import re
import shlex
import sys
import time
import traceback

PY2 = (sys.version_info[0] == 2)
if not PY2:             # Python 3
    from configparser import ConfigParser
    from threading import current_thread
    from urllib.request import Request, urlopen
    from xmlrpc.client import Fault, ServerProxy, MININT, MAXINT
else:                   # Python 2
    from ConfigParser import SafeConfigParser as ConfigParser
    from threading import currentThread as current_thread
    from urllib2 import Request, urlopen
    from xmlrpclib import Fault, ServerProxy, MININT, MAXINT

try:
    import requests
except ImportError:
    requests = None

__version__ = '1.7.1'
__all__ = ['Client', 'Model', 'Record', 'RecordList', 'Service',
           'format_exception', 'read_config', 'start_odoo_services']

CONF_FILE = 'erppeek.ini'
HIST_FILE = os.path.expanduser('~/.erppeek_history')
DEFAULT_URL = 'http://localhost:8069/xmlrpc'
DEFAULT_DB = 'odoo'
DEFAULT_USER = 'admin'
MAXCOL = [79, 179, 9999]    # Line length in verbose mode
_DEFAULT = object()

USAGE = """\
Usage (some commands):
    models(name)                    # List models matching pattern
    model(name)                     # Return a Model instance
    model(name).keys()              # List field names of the model
    model(name).fields(names=None)  # Return details for the fields
    model(name).field(name)         # Return details for the field
    model(name).browse(domain)
    model(name).browse(domain, offset=0, limit=None, order=None)
                                    # Return a RecordList

    rec = model(name).get(domain)   # Get the Record matching domain
    rec.some_field                  # Return the value of this field
    rec.read(fields=None)           # Return values for the fields

    client.login(user)              # Login with another user
    client.connect(env)             # Connect to another env.
    client.modules(name)            # List modules matching pattern
    client.upgrade(module1, module2, ...)
                                    # Upgrade the modules
"""

DOMAIN_OPERATORS = frozenset('!|&')
# Supported operators are:
#   =, !=, >, >=, <, <=, like, ilike, in, not like, not ilike, not in,
#   child_of, =like, =ilike, =?
_term_re = re.compile(
    r'([\w._]+)\s*'   r'(=(?:like|ilike|\?)|[<>]=?|!?=(?!=)'
    r'|(?<= )(?:like|ilike|in|not like|not ilike|not in|child_of))' r'\s*(.*)')
_fields_re = re.compile(r'(?:[^%]|^)%\(([^)]+)\)')

# Published object methods
_methods = {
    'db': ['create_database', 'duplicate_database', 'db_exist',
           'drop', 'dump', 'restore', 'rename', 'list', 'list_lang',
           'change_admin_password', 'server_version', 'migrate_databases'],
    'common': ['about', 'login', 'timezone_get',
               'authenticate', 'version', 'set_loglevel'],
    'object': ['execute', 'execute_kw', 'exec_workflow'],
    'report': ['render_report', 'report', 'report_get'],    # < 11.0
}
# New 6.1: (db) create_database db_exist,
#          (common) authenticate version set_loglevel
#          (object) execute_kw,  (report) render_report
# New 7.0: (db) duplicate_database

_obsolete_methods = {
    'db': ['create', 'get_progress'],                       # < 8.0
    'common': ['check_connectivity', 'get_available_updates', 'get_os_time',
               'get_migration_scripts', 'get_server_environment',
               'get_sqlcount', 'get_stats',
               'list_http_services', 'login_message'],      # < 8.0
    'wizard': ['execute', 'create'],                        # < 7.0
}
_cause_message = ("\nThe above exception was the direct cause "
                  "of the following exception:\n\n")
_pending_state = ('state', 'not in',
                  ['uninstallable', 'uninstalled', 'installed'])

if PY2:
    int_types = int, long

    class _DictWriter(csv.DictWriter):
        """Unicode CSV Writer, which encodes output to UTF-8."""

        def _dict_to_list(self, rowdict):
            rowlst = csv.DictWriter._dict_to_list(self, rowdict)
            return [cell.encode('utf-8') if hasattr(cell, 'encode') else cell
                    for cell in rowlst]
else:   # Python 3
    basestring = str
    int_types = int
    _DictWriter = csv.DictWriter


def _memoize(inst, attr, value, doc_values=None):
    if hasattr(value, '__get__') and not hasattr(value, '__self__'):
        value.__name__ = attr
        if doc_values is not None:
            value.__doc__ %= doc_values
        value = value.__get__(inst, type(inst))
    inst.__dict__[attr] = value
    return value


_ast_node_attrs = []
for (cls, attr) in [('Constant', 'value'),      # Python >= 3.7
                    ('NameConstant', 'value'),  # Python >= 3.4 (singletons)
                    ('Str', 's'),               # Python <= 3.7
                    ('Num', 'n')]:              # Python <= 3.7
    if hasattr(_ast, cls):
        _ast_node_attrs.append((getattr(_ast, cls), attr))


# Simplified ast.literal_eval which does not parse operators
def _convert(node, _consts={'None': None, 'True': True, 'False': False}):
    for (ast_class, node_attr) in _ast_node_attrs:
        if isinstance(node, ast_class):
            return getattr(node, node_attr)
    if isinstance(node, _ast.Tuple):
        return tuple(map(_convert, node.elts))
    if isinstance(node, _ast.List):
        return list(map(_convert, node.elts))
    if isinstance(node, _ast.Dict):
        return {_convert(k): _convert(v)
                for (k, v) in zip(node.keys, node.values)}
    if isinstance(node, _ast.Name) and node.id in _consts:
        return _consts[node.id]   # Python <= 3.3
    raise ValueError('malformed or disallowed expression')


def literal_eval(expression, _octal_digits=frozenset('01234567')):
    node = compile(expression, '<unknown>', 'eval', _ast.PyCF_ONLY_AST)
    if expression[:1] == '0' and expression[1:2] in _octal_digits:
        raise SyntaxError('unsupported octal notation')
    value = _convert(node.body)
    if isinstance(value, int_types) and not MININT <= value <= MAXINT:
        raise ValueError('overflow, int exceeds XML-RPC limits')
    return value


def is_list_of_dict(iterator):
    """Return True if the first non-false item is a dict."""
    for item in iterator:
        if item:
            return isinstance(item, dict)
    return False


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
    which formats the error and traceback received by XML-RPC/JSON-RPC.
    If `chain` is True, then the original exception is printed too.
    """
    values = _format_exception(exc_type, exc, tb, limit=limit)
    server_error = None
    if issubclass(exc_type, Error):             # Client-side
        values = [str(exc) + '\n']
    elif issubclass(exc_type, ServerError):     # JSON-RPC
        server_error = exc.args[0]['data']
    elif (issubclass(exc_type, Fault) and       # XML-RPC
          isinstance(exc.faultCode, basestring)):
        (message, tb) = (exc.faultCode, exc.faultString)
        exc_name = exc_type.__name__
        warning = message.startswith('warning --')
        if warning:
            message = re.sub(r'\((.*), None\)$',
                             lambda m: literal_eval(m.group(1)),
                             message.split(None, 2)[2])
        else:       # ValidationError, etc ...
            parts = message.rsplit('\n', 1)
            if parts[-1] == 'None':
                warning, message = True, parts[0]
                last_line = tb.rstrip().rsplit('\n', 1)[-1]
                if last_line.startswith('odoo.exceptions'):
                    exc_name = last_line.split(':', 1)[0]
        server_error = {
            'exception_type': 'warning' if warning else 'internal_error',
            'name': exc_name,
            'arguments': (message,),
            'debug': tb,
        }
    if server_error:
        # Format readable XML-RPC and JSON-RPC errors
        message = server_error['arguments'][0]
        fault = '%s: %s' % (server_error['name'], message)
        if (server_error['exception_type'] != 'internal_error' or
                message.startswith('FATAL:')):
            server_tb = None
        else:
            server_tb = server_error['debug']
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
    ``database``, ``username`` and (optional) ``password``.  Default values
    are read from the ``[DEFAULT]`` section.  If the ``password`` is not in
    the configuration file, it is requested on login.
    Return a tuple ``(server, db, user, password or None)``.
    Without argument, it returns the list of configured environments.
    """
    p = ConfigParser()
    with open(Client._config_file) as f:
        p.readfp(f) if PY2 else p.read_file(f)
    if section is None:
        return p.sections()
    env = dict(p.items(section))
    scheme = env.get('scheme', 'http')
    if scheme == 'local':
        server = shlex.split(env.get('options', ''))
    else:
        protocol = env.get('protocol', 'xmlrpc')
        server = '%s://%s:%s/%s' % (scheme, env['host'], env['port'], protocol)
    return (server, env['database'], env['username'], env.get('password'))


def start_odoo_services(options=None, appname=None):
    """Initialize the Odoo services.

    Import the ``odoo`` Python package and load the Odoo services.
    The argument `options` receives the command line arguments
    for ``odoo``.  Example:

      ``['-c', '/path/to/odoo-server.conf', '--without-demo', 'all']``.

    Return the ``odoo`` package.
    """
    try:
        import openerp as odoo
    except ImportError:
        import odoo
    odoo._api_v7 = odoo.release.version_info < (8,)
    if not (odoo._api_v7 and odoo.osv.osv.service):
        os.putenv('TZ', 'UTC')
        if appname is not None:
            os.putenv('PGAPPNAME', appname)
        odoo.tools.config.parse_config(options or [])
        if odoo.release.version_info < (7,):
            odoo.netsvc.init_logger()
            odoo.osv.osv.start_object_proxy()
            odoo.service.web_services.start_web_services()
        elif odoo._api_v7:
            odoo.service.start_internal()
        else:   # Odoo v8
            odoo.api.Environment.reset()

        try:
            odoo._manager_class = odoo.modules.registry.RegistryManager
            odoo._get_pool = odoo._manager_class.get
        except AttributeError:  # Odoo >= 10
            odoo._manager_class = odoo.modules.registry.Registry
            odoo._get_pool = odoo._manager_class

        def close_all():
            for db in odoo._manager_class.registries.keys():
                odoo.sql_db.close_db(db)
        atexit.register(close_all)

    return odoo


def issearchdomain(arg):
    """Check if the argument is a search domain.

    Examples:
      - ``[('name', '=', 'mushroom'), ('state', '!=', 'draft')]``
      - ``['name = mushroom', 'state != draft']``
      - ``[]``
    """
    return isinstance(arg, list) and not (arg and (
        # Not a list of ids: [1, 2, 3]
        isinstance(arg[0], int_types) or
        # Not a list of ids as str: ['1', '2', '3']
        (isinstance(arg[0], basestring) and arg[0].isdigit())))


def searchargs(params, kwargs=None, context=None, api_v9=False):
    """Compute the 'search' parameters."""
    if not params:
        return ([],)
    domain = params[0]
    if not isinstance(domain, list):
        return params
    for (idx, term) in enumerate(domain):
        if isinstance(term, basestring) and term not in DOMAIN_OPERATORS:
            m = _term_re.match(term.strip())
            if not m:
                raise ValueError('Cannot parse term %r' % term)
            (field, operator, value) = m.groups()
            try:
                value = literal_eval(value)
            except Exception:
                # Interpret the value as a string
                pass
            domain[idx] = (field, operator, value)
    params = (domain,) + params[1:]
    if (kwargs or context) and len(params) == 1:
        args = (kwargs.pop('offset', 0),
                kwargs.pop('limit', None),
                kwargs.pop('order', None))
        if context:
            # Order of the arguments was different with Odoo 9 and older
            params += args + ((context,) if api_v9 else (False, context))
        elif any(args):
            params += args
    return params


if requests:
    def http_post(url, data, headers={'Content-Type': 'application/json'}):
        resp = requests.post(url, data=data, headers=headers)
        return resp.json()
else:
    def http_post(url, data, headers={'Content-Type': 'application/json'}):
        request = Request(url, data=data, headers=headers)
        resp = urlopen(request)
        return json.load(resp)


def dispatch_jsonrpc(url, service_name, method, args):
    data = {
        'jsonrpc': '2.0',
        'method': 'call',
        'params': {'service': service_name, 'method': method, 'args': args},
        'id': '%04x%010x' % (os.getpid(), (int(time.time() * 1E6) % 2**40)),
    }
    resp = http_post(url, json.dumps(data).encode('ascii'))
    if resp.get('error'):
        raise ServerError(resp['error'])
    return resp['result']


class Error(Exception):
    """An ERPpeek error."""


class ServerError(Exception):
    """An error received from the server."""


class Service(object):
    """A wrapper around XML-RPC endpoints.

    The connected endpoints are exposed on the Client instance.
    The `server` argument is the URL of the server (scheme+host+port).
    If `server` is an ``odoo`` Python package, it is used to connect to the
    local server.  The `endpoint` argument is the name of the service
    (examples: ``"object"``, ``"db"``).  The `methods` is the list of methods
    which should be exposed on this endpoint.  Use ``dir(...)`` on the
    instance to list them.
    """
    _methods = ()

    def __init__(self, client, endpoint, methods, verbose=False):
        self._dispatch = client._proxy(endpoint)
        self._rpcpath = client._server
        self._endpoint = endpoint
        self._methods = methods
        self._verbose = verbose

    def __repr__(self):
        return "<Service '%s|%s'>" % (self._rpcpath, self._endpoint)
    __str__ = __repr__

    def __dir__(self):
        return sorted(self._methods)

    def __getattr__(self, name):
        if name not in self._methods:
            raise AttributeError("'Service' object has no attribute %r" % name)
        if self._verbose:
            def sanitize(args):
                if self._endpoint != 'db' and len(args) > 2:
                    args = list(args)
                    args[2] = '*'
                return args
            maxcol = MAXCOL[min(len(MAXCOL), self._verbose) - 1]

            def wrapper(self, *args):
                snt = ', '.join([repr(arg) for arg in sanitize(args)])
                snt = '%s.%s(%s)' % (self._endpoint, name, snt)
                if len(snt) > maxcol:
                    suffix = '... L=%s' % len(snt)
                    snt = snt[:maxcol - len(suffix)] + suffix
                print('--> ' + snt)
                res = self._dispatch(name, args)
                rcv = str(res)
                if len(rcv) > maxcol:
                    suffix = '... L=%s' % len(rcv)
                    rcv = rcv[:maxcol - len(suffix)] + suffix
                print('<-- ' + rcv)
                return res
        else:
            wrapper = lambda s, *args: s._dispatch(name, args)
        return _memoize(self, name, wrapper)

    def __del__(self):
        if hasattr(self, 'close'):
            self.close()


class Client(object):
    """Connection to an Odoo instance.

    This is the top level object.
    The `server` is the URL of the instance, like ``http://localhost:8069``.
    If `server` is an ``odoo``/``openerp`` Python package, it is used to
    connect to the local server (>= 6.1).

    The `db` is the name of the database and the `user` should exist in the
    table ``res.users``.  If the `password` is not provided, it will be
    asked on login.
    """
    _config_file = os.path.join(os.curdir, CONF_FILE)

    def __init__(self, server, db=None, user=None, password=None,
                 transport=None, verbose=False):
        self._set_services(server, transport, verbose)
        self.reset()
        self.context = None
        if db:    # Try to login
            self.login(user, password=password, database=db)

    def _set_services(self, server, transport, verbose):
        if isinstance(server, list):
            appname = os.path.basename(__file__).rstrip('co')
            server = start_odoo_services(server, appname=appname)
        elif isinstance(server, basestring) and server[-1:] == '/':
            server = server.rstrip('/')
        self._server = server

        if not isinstance(server, basestring):
            assert not transport, "Not supported"
            self._proxy = self._proxy_dispatch
        elif '/jsonrpc' in server:
            assert not transport, "Not supported"
            self._proxy = self._proxy_jsonrpc
        else:
            if '/xmlrpc' not in server:
                self._server = server + '/xmlrpc'
            self._proxy = self._proxy_xmlrpc
            self._transport = transport

        def get_service(name):
            methods = list(_methods[name]) if (name in _methods) else []
            if float_version < 8.0:
                methods += _obsolete_methods.get(name) or ()
            return Service(self, name, methods, verbose=verbose)

        float_version = 99.0
        self.server_version = ver = get_service('db').server_version()
        self.major_version = re.match(r'\d+\.?\d*', ver).group()
        float_version = float(self.major_version)
        # Create the RPC services
        self.db = get_service('db')
        self.common = get_service('common')
        self._object = get_service('object')
        self._report = get_service('report') if float_version < 11.0 else None
        self._wizard = get_service('wizard') if float_version < 7.0 else None
        self._searchargs = functools.partial(searchargs,
                                             api_v9=(float_version < 10.0))

    def _proxy_dispatch(self, name):
        if self._server._api_v7:
            return self._server.netsvc.ExportService.getService(name).dispatch
        return functools.partial(self._server.http.dispatch_rpc, name)

    def _proxy_xmlrpc(self, name):
        proxy = ServerProxy(self._server + '/' + name,
                            transport=self._transport, allow_none=True)
        return proxy._ServerProxy__request

    def _proxy_jsonrpc(self, name):
        return functools.partial(dispatch_jsonrpc, self._server, name)

    @classmethod
    def from_config(cls, environment, user=None, verbose=False):
        """Create a connection to a defined environment.

        Read the settings from the section ``[environment]`` in the
        ``erppeek.ini`` file and return a connected :class:`Client`.
        See :func:`read_config` for details of the configuration file format.
        """
        (server, db, conf_user, password) = read_config(environment)
        if user and user != conf_user:
            password = None
        client = cls(server, verbose=verbose)
        client._environment = environment
        client.login(user or conf_user, password=password, database=db)
        return client

    def reset(self):
        self.user = self._environment = None
        self._db, self._models = (), {}
        self._execute = self._exec_workflow = None

    def __repr__(self):
        return "<Client '%s#%s'>" % (self._server, self._db)

    def login(self, user, password=None, database=None):
        """Switch `user` and (optionally) `database`.

        If the `password` is not available, it will be asked.
        """
        if database:
            try:
                dbs = self.db.list()
            except Fault:
                pass    # AccessDenied: simply ignore this check
            else:
                if database not in dbs:
                    raise Error("Database '%s' does not exist: %s" %
                                (database, dbs))
            if not self._db:
                self._db = database
            # Used for logging, copied from odoo.sql_db.db_connect
            current_thread().dbname = database
        elif self._db:
            database = self._db
        else:
            raise Error('Not connected')
        (uid, password) = self._auth(database, user, password)
        if not uid:
            current_thread().dbname = self._db
            raise Error('Invalid username or password')
        if self._db != database:
            self.reset()
            self._db = database
        self.user = user

        # Authenticated endpoints
        def authenticated(method):
            return functools.partial(method, self._db, uid, password)
        self._execute = authenticated(self._object.execute)
        self._exec_workflow = authenticated(self._object.exec_workflow)
        if self.major_version != '5.0':
            # Only for Odoo and OpenERP >= 6
            self.execute_kw = authenticated(self._object.execute_kw)
        if self._report:        # Odoo <= 10
            self.report = authenticated(self._report.report)
            self.report_get = authenticated(self._report.report_get)
            if self.major_version != '5.0':
                self.render_report = authenticated(self._report.render_report)
        if self._wizard:        # OpenERP <= 6.1
            self._wizard_execute = authenticated(self._wizard.execute)
            self._wizard_create = authenticated(self._wizard.create)
        return uid

    # Needed for interactive use
    connect = None
    _login = login
    _login.cache = {}

    def _check_valid(self, database, uid, password):
        execute = self._object.execute
        try:
            execute(database, uid, password, 'res.users', 'fields_get_keys')
            return True
        except Fault:
            return False

    def _auth(self, database, user, password):
        assert database
        cache_key = (self._server, database, user)
        if password:
            # If password is explicit, call the 'login' method
            uid = None
        else:
            # Read from cache
            uid, password = self._login.cache.get(cache_key) or (None, None)
            # Read from table 'res.users'
            if ((not uid and self._db == database and
                 self.access('res.users', 'write'))):
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
            if not self._check_valid(database, uid, password):
                if cache_key in self._login.cache:
                    del self._login.cache[cache_key]
                uid = False
        elif uid is None:
            # Do a standard 'login'
            uid = self.common.login(database, user, password)
        if uid:
            # Update the cache
            self._login.cache[cache_key] = (uid, password)
        return (uid, password)

    @classmethod
    def _set_interactive(cls, global_vars={}):
        # Don't call multiple times
        del Client._set_interactive

        for name in ['__name__', '__doc__'] + __all__:
            global_vars[name] = globals()[name]

        def get_pool(db_name=None):
            """Return a model registry.

            Use get_pool().cursor() to grab a cursor on an Odoo database.
            With OpenERP, use get_pool().db.cursor() instead.
            """
            client = global_vars['client']
            return client._server._get_pool(db_name or client._db)

        def connect(self, env=None):
            """Connect to another environment and replace the globals()."""
            if env:
                # Safety measure: turn down the previous connection
                global_vars['client'].reset()
                client = self.from_config(env, verbose=self.db._verbose)
                return
            client = self
            env = client._environment or client._db
            try:  # copy the context to the new client
                client.context = dict(global_vars['client'].context)
            except (KeyError, TypeError):
                pass  # client not yet in globals(), or context is None
            global_vars['client'] = client
            if hasattr(client._server, 'modules'):
                global_vars['get_pool'] = get_pool
            # Tweak prompt
            sys.ps1 = '%s >>> ' % (env,)
            sys.ps2 = '%s ... ' % (env,)
            # Logged in?
            if client.user:
                global_vars['model'] = client.model
                global_vars['models'] = client.models
                global_vars['do'] = client.execute
                print('Logged in as %r' % (client.user,))
            else:
                global_vars.update({'model': None, 'models': None, 'do': None})

        def login(self, user, password=None, database=None):
            """Switch `user` and (optionally) `database`."""
            try:
                self._login(user, password=password, database=database)
            except Error as exc:
                print('%s: %s' % (exc.__class__.__name__, exc))
            else:
                # Register the new globals()
                self.connect()

        # Set hooks to recreate the globals()
        cls.login = login
        cls.connect = connect

        return global_vars

    def create_database(self, passwd, database, demo=False, lang='en_US',
                        user_password='admin', login='admin',
                        country_code=None):
        """Create a new database.

        The superadmin `passwd` and the `database` name are mandatory.
        By default, `demo` data are not loaded, `lang` is ``en_US``
        and no country is set into the database.
        Login if successful.
        """
        float_version = float(self.major_version)
        customize = (login != 'admin' or country_code)
        if customize and float_version < 9.0:
            raise Error("Custom 'login' and 'country_code' are not supported")

        if float_version < 6.1:
            thread_id = self.db.create(passwd, database, demo, lang,
                                       user_password)
            progress = 0
            try:
                while progress < 1:
                    time.sleep(3)
                    progress, users = self.db.get_progress(passwd, thread_id)
            except KeyboardInterrupt:
                return {'id': thread_id, 'progress': progress}
        elif not customize:
            self.db.create_database(passwd, database, demo, lang,
                                    user_password)
        else:
            self.db.create_database(passwd, database, demo, lang,
                                    user_password, login, country_code)
        return self.login(login, user_password, database=database)

    def clone_database(self, passwd, db_name):
        """Clone the current database.

        The superadmin `passwd` and `db_name` are mandatory.
        Login if successful.

        Supported since OpenERP 7.
        """
        self.db.duplicate_database(passwd, self._db, db_name)

        # Login with the current user into the new database
        (uid, password) = self._auth(self._db, self.user, None)
        return self.login(self.user, password, database=db_name)

    def execute(self, obj, method, *params, **kwargs):
        """Wrapper around ``object.execute`` RPC method.

        Argument `method` is the name of an ``osv.osv`` method or
        a method available on this `obj`.
        Method `params` are allowed.  If needed, keyword
        arguments are collected in `kwargs`.
        """
        assert self.user, 'Not connected'
        assert isinstance(obj, basestring)
        assert isinstance(method, basestring) and method != 'browse'
        context = kwargs.pop('context', None)
        ordered = single_id = False
        if method == 'read':
            assert params, 'Missing parameter'
            if not (params[0] and isinstance(params[0], list)):
                single_id = True
                ids = [params[0]] if params[0] else False
            elif issearchdomain(params[0]):
                # Combine search+read
                search_params = self._searchargs(params[:1], kwargs, context)
                ordered = len(search_params) > 3 and search_params[3]
                ids = self._execute(obj, 'search', *search_params)
            else:
                ordered = kwargs.pop('order', False) and params[0]
                ids = set(params[0]) - {False}
                if not ids and ordered:
                    return [False] * len(ordered)
                ids = sorted(ids)
            if not ids:
                return ids
            if len(params) > 1:
                params = (ids,) + params[1:]
            else:
                params = (ids, kwargs.pop('fields', None))
        elif method == 'search':
            # Accept keyword arguments for the search method
            params = self._searchargs(params, kwargs, context)
            context = None
        elif method == 'search_count':
            params = self._searchargs(params)
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
        if ordered:
            # The results are not in the same order as the ids
            # when received from the server
            resdic = {val['id']: val for val in res}
            if not isinstance(ordered, list):
                ordered = ids
            res = [resdic.get(id_, False) for id_ in ordered]
        return res[0] if single_id else res

    def exec_workflow(self, obj, signal, obj_id):
        """Wrapper around ``object.exec_workflow`` RPC method.

        Argument `obj` is the name of the model.  The `signal`
        is sent to the object identified by its integer ``id`` `obj_id`.
        """
        assert self.user, 'Not connected'
        assert isinstance(obj, basestring) and isinstance(signal, basestring)
        return self._exec_workflow(obj, signal, obj_id)

    def wizard(self, name, datas=None, action='init', context=_DEFAULT):
        """Wrapper around ``wizard.create`` and ``wizard.execute``
        RPC methods.

        If only `name` is provided, a new wizard is created and its ``id`` is
        returned.  If `action` is not ``"init"``, then the action is executed.
        In this case the `name` is either an ``id`` or a string.
        If the `name` is a string, the wizard is created before the execution.
        The optional `datas` argument provides data for the action.
        The optional `context` argument is passed to the RPC method.

        Removed in OpenERP 7.
        """
        if isinstance(name, int_types):
            wiz_id = name
        else:
            wiz_id = self._wizard_create(name)
        if datas is None:
            if action == 'init' and name != wiz_id:
                return wiz_id
            datas = {}
        if context is _DEFAULT:
            context = self.context
        return self._wizard_execute(wiz_id, datas, action, context)

    def _upgrade(self, modules, button):
        # First, update the list of modules
        ir_module = self.model('ir.module.module', False)
        updated, added = ir_module.update_list()
        if added:
            print('%s module(s) added to the list' % added)
        # Find modules
        ids = modules and ir_module.search([('name', 'in', modules)])
        if ids:
            # Safety check
            mods = ir_module.read([_pending_state], 'name state')
            if any(mod['name'] not in modules for mod in mods):
                raise Error('Pending actions:\n' + '\n'.join(
                    ('  %(state)s\t%(name)s' % mod) for mod in mods))
            if button == 'button_uninstall':
                # Safety check
                names = ir_module.read([('id', 'in', ids),
                                        'state != installed',
                                        'state != to upgrade',
                                        'state != to remove'], 'name')
                if names:
                    raise Error('Not installed: %s' % ', '.join(names))
                # A trick to uninstall dependent add-ons
                ir_module.write(ids, {'state': 'to remove'})
            try:
                # Click upgrade/install/uninstall button
                self.execute('ir.module.module', button, ids)
            except Exception:
                if button == 'button_uninstall':
                    ir_module.write(ids, {'state': 'installed'})
                raise
        mods = ir_module.read([_pending_state], 'name state')
        if not mods:
            if ids:
                print('Already up-to-date: %s' %
                      self.modules([('id', 'in', ids)]))
            elif modules:
                raise Error('Module(s) not found: %s' % ', '.join(modules))
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

    def _models_get(self, name):
        try:
            return self._models[name]
        except KeyError:
            self._models[name] = m = Model._new(self, name)
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
        return {mixedcase(mod): self._models_get(mod) for mod in names}

    def model(self, name, check=True):
        """Return a :class:`Model` instance.

        The argument `name` is the name of the model.  If the optional
        argument `check` is :const:`False`, no validity check is done.
        """
        try:
            return self._models[name] if check else self._models_get(name)
        except KeyError:
            models = self.models(name)
        if name in self._models:
            return self._models[name]
        if models:
            errmsg = 'Model not found.  These models exist:'
        else:
            errmsg = 'Model not found: %s' % (name,)
        raise Error('\n * '.join([errmsg] + [str(m) for m in models.values()]))

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
        if isinstance(name, basestring):
            domain = [('name', 'like', name)]
        else:
            domain = name
        if installed is not None:
            op = 'not in' if installed else 'in'
            domain.append(('state', op, ['uninstalled', 'uninstallable']))
        mods = self.read('ir.module.module', domain, 'name state')
        if mods:
            res = {}
            for mod in mods:
                if mod['state'] not in res:
                    res[mod['state']] = []
                res[mod['state']].append(mod['name'])
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
            return _memoize(self, method, self.model(lowercase(method)))
        if method.startswith('_'):
            errmsg = "'Client' object has no attribute %r" % method
            raise AttributeError(errmsg)

        # miscellaneous object methods
        def wrapper(self, obj, *params, **kwargs):
            """Wrapper for client.execute(obj, %r, *params, **kwargs)."""
            return self.execute(obj, method, *params, **kwargs)
        return _memoize(self, method, wrapper, method)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, tb):
        self.reset()


class Model(object):
    """The class for Odoo models."""

    # Enable Model.browse([]) to return all records.
    # It was the default behavior before version 1.7.1
    _browse_compat = False

    def __new__(cls, client, name):
        return client.model(name)

    @classmethod
    def _new(cls, client, name):
        m = object.__new__(cls)
        (m.client, m._name) = (client, name)
        m._execute = functools.partial(client.execute, name)
        m.search = functools.partial(client.search, name)
        m.count = functools.partial(client.count, name)
        m.read = functools.partial(client.read, name)
        return m

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
        return {k: v for (k, v) in self._fields.items() if k in names}

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
        To get all the records, pass an empty list along with keyword
        argument ``limit=None``.
        """
        context = kwargs.pop('context', self.client.context)
        if isinstance(domain, int_types):
            assert not params and not kwargs
            return Record(self, domain, context=context)
        safe = (domain or params or self._browse_compat or
                set(kwargs) & {'limit', 'offset', 'order'})
        if safe and issearchdomain(domain):
            kwargs['context'] = context
            domain = self._execute('search', domain, *params, **kwargs)
        else:
            assert not params and not kwargs
        return RecordList(self, domain, context=context)

    def get(self, domain, context=_DEFAULT):
        """Return a single :class:`Record`.

        The argument `domain` accepts a single integer ``id`` or a search
        domain, or an external ID ``xml_id``.  The return value is a
        :class:`Record` or None.  If multiple records are found,
        a ``ValueError`` is raised.
        """
        if context is _DEFAULT:
            context = self.client.context
        if isinstance(domain, int_types):   # a single id
            return Record(self, domain, context=context)
        if isinstance(domain, basestring):  # lookup the xml_id
            (module, name) = domain.split('.')
            data = self._imd_read(
                [('module', '=', module), ('name', '=', name)], 'model res_id')
            assert not data or data[0]['model'] == self._name
            ids = [res['res_id'] for res in data]
        else:                               # a search domain
            assert issearchdomain(domain)
            ids = self._execute('search', domain, context=context)
        if len(ids) > 1:
            raise ValueError('domain matches too many records (%d)' % len(ids))
        return Record(self, ids[0], context=context) if ids else None

    def create(self, values, context=_DEFAULT):
        """Create a :class:`Record`.

        The argument `values` is a dictionary of values which are used to
        create the record.  Relationship fields `one2many` and `many2many`
        accept either a list of ids or a RecordList or the extended Odoo
        syntax.  Relationship fields `many2one` and `reference` accept
        either a Record or the Odoo syntax.

        The newly created :class:`Record` is returned.
        """
        if context is _DEFAULT:
            context = self.client.context
        values = self._unbrowse_values(values)
        new_id = self._execute('create', values, context=context)
        return Record(self, new_id, context=context)

    def _browse_values(self, values, context=_DEFAULT):
        """Wrap the values of a Record.

        The argument `values` is a dictionary of values read from a Record.
        When the field type is relational (many2one, one2many or many2many),
        the value is wrapped in a Record or a RecordList.
        Return a dictionary with the same keys as the `values` argument.
        """
        for (key, value) in values.items():
            if key == 'id' or hasattr(value, 'id'):
                continue
            field = self._fields[key]
            field_type = field['type']
            if field_type == 'many2one':
                if value:
                    rel_model = self.client.model(field['relation'], False)
                    values[key] = Record(rel_model, value, context=context)
            elif field_type in ('one2many', 'many2many'):
                rel_model = self.client.model(field['relation'], False)
                values[key] = RecordList(rel_model, value, context=context)
            elif value and field_type == 'reference':
                (res_model, res_id) = value.split(',')
                rel_model = self.client.model(res_model, False)
                values[key] = Record(rel_model, int(res_id), context=context)
        return values

    def _unbrowse_values(self, values):
        """Unwrap the id of Record and RecordList."""
        new_values = values.copy()
        for (key, value) in values.items():
            field_type = self._fields[key]['type']
            if hasattr(value, 'id'):
                if field_type == 'reference':
                    new_values[key] = '%s,%s' % (value._model_name, value.id)
                else:
                    new_values[key] = value = value.id
            if field_type in ('one2many', 'many2many'):
                if not value:
                    new_values[key] = [(6, 0, [])]
                elif isinstance(value[0], int_types):
                    new_values[key] = [(6, 0, value)]
        return new_values

    def _get_external_ids(self, ids=None):
        """Retrieve the External IDs of the records.

        Return a dictionary with keys being the fully qualified
        External IDs, and values the ``Record`` entries.
        """
        search_domain = [('model', '=', self._name)]
        if ids is not None:
            search_domain.append(('res_id', 'in', ids))
        existing = self._imd_read(search_domain, ['module', 'name', 'res_id'])
        res = {}
        for rec in existing:
            res['%(module)s.%(name)s' % rec] = self.get(rec['res_id'])
        return res

    def __getattr__(self, attr):
        if attr in ('_keys', '_fields'):
            return _memoize(self, attr, getattr(self, '_get' + attr)())
        if attr.startswith('_imd_'):
            imd = self.client.model('ir.model.data')
            return _memoize(self, attr, getattr(imd, attr[5:]))
        if attr.startswith('_'):
            raise AttributeError("'Model' object has no attribute %r" % attr)

        def wrapper(self, *params, **kwargs):
            """Wrapper for client.execute(%r, %r, *params, **kwargs)."""
            if 'context' not in kwargs:
                kwargs['context'] = self.client.context
            return self._execute(attr, *params, **kwargs)
        return _memoize(self, attr, wrapper, (self._name, attr))


class RecordList(object):
    """A sequence of Odoo :class:`Record`.

    It has a similar API as the :class:`Record` class, but for a list of
    records.  The attributes of the ``RecordList`` are read-only, and they
    return list of attribute values in the same order.  The ``many2one``,
    ``one2many`` and ``many2many`` attributes are wrapped in ``RecordList``
    and list of ``RecordList`` objects.  Use the method ``RecordList.write``
    to assign a single value to all the selected records.
    """

    def __init__(self, res_model, ids, context=_DEFAULT):
        idnames = list(ids)
        for (index, id_) in enumerate(ids):
            if isinstance(id_, (list, tuple)):
                ids[index] = id_ = id_[0]
            assert isinstance(id_, int_types), repr(id_)
        if context is _DEFAULT:
            context = res_model.client.context
        # Bypass the __setattr__ method
        self.__dict__.update({
            'id': ids,
            '_model_name': res_model._name,
            '_model': res_model,
            '_idnames': idnames,
            '_context': context,
            '_execute': res_model._execute,
        })

    def __repr__(self):
        if len(self.id) > 16:
            ids = 'length=%d' % len(self.id)
        else:
            ids = self.id
        return "<RecordList '%s,%s'>" % (self._model_name, ids)

    def __dir__(self):
        return ['__getitem__', 'read', 'write', 'unlink', '_context',
                '_idnames', '_model', '_model_name',
                '_external_id'] + self._model._keys

    def __len__(self):
        return len(self.id)

    def __add__(self, other):
        assert self._model is other._model, 'Model mismatch'
        ids = self._idnames + other._idnames
        return RecordList(self._model, ids, self._context)

    def read(self, fields=None, context=_DEFAULT):
        """Wrapper for :meth:`Record.read` method."""
        if context is _DEFAULT:
            context = self._context

        client = self._model.client
        if self.id:
            values = client.read(self._model_name, self.id,
                                 fields, order=True, context=context)
            if is_list_of_dict(values):
                browse_values = self._model._browse_values
                return [v and browse_values(v, context) for v in values]
        else:
            values = []

        if isinstance(fields, basestring):
            field = self._model._fields.get(fields)
            if field:
                if field['type'] == 'many2one':
                    rel_model = client.model(field['relation'], False)
                    return RecordList(rel_model, values, context=context)
                if field['type'] in ('one2many', 'many2many'):
                    rel_model = client.model(field['relation'], False)
                    return [RecordList(rel_model, v, context) for v in values]
                if field['type'] == 'reference':
                    records = []
                    for value in values:
                        if value:
                            (res_model, res_id) = value.split(',')
                            rel_model = client.model(res_model, False)
                            value = Record(rel_model, int(res_id), context)
                        records.append(value)
                    return records
        return values

    def write(self, values, context=_DEFAULT):
        """Wrapper for :meth:`Record.write` method."""
        if not self.id:
            return True
        if context is _DEFAULT:
            context = self._context
        values = self._model._unbrowse_values(values)
        rv = self._execute('write', self.id, values, context=context)
        return rv

    def unlink(self, context=_DEFAULT):
        """Wrapper for :meth:`Record.unlink` method."""
        if not self.id:
            return True
        if context is _DEFAULT:
            context = self._context
        rv = self._execute('unlink', self.id, context=context)
        return rv

    @property
    def _external_id(self):
        """Retrieve the External IDs of the :class:`RecordList`.

        Return the fully qualified External IDs with default value
        False if there's none.  If multiple IDs exist for a record,
        only one of them is returned (randomly).
        """
        xml_ids = {r.id: xml_id for (xml_id, r) in
                   self._model._get_external_ids(self.id).items()}
        return [xml_ids.get(res_id, False) for res_id in self.id]

    def __getitem__(self, key):
        idname = self._idnames[key]
        if idname is False:
            return False
        cls = RecordList if isinstance(key, slice) else Record
        return cls(self._model, idname, context=self._context)

    def __getattr__(self, attr):
        context = self._context
        if attr in self._model._keys:
            return self.read(attr, context=context)
        if attr.startswith('_'):
            errmsg = "'RecordList' object has no attribute %r" % attr
            raise AttributeError(errmsg)

        def wrapper(self, *params, **kwargs):
            """Wrapper for client.execute(%r, %r, [...], *params, **kwargs)."""
            if context is not None and 'context' not in kwargs:
                kwargs['context'] = context
            return self._execute(attr, self.id, *params, **kwargs)
        return _memoize(self, attr, wrapper, (self._model_name, attr))

    def __setattr__(self, attr, value):
        if attr in self._model._keys or attr == 'id':
            msg = "attribute %r is read-only; use 'RecordList.write' instead."
        else:
            msg = "has no attribute %r"
        raise AttributeError("'RecordList' object %s" % msg % attr)

    def __eq__(self, other):
        return (isinstance(other, RecordList) and
                self.id == other.id and self._model is other._model)


class Record(object):
    """A class for all Odoo records.

    It maps any Odoo object.
    The fields can be accessed through attributes.  The changes are immediately
    sent to the server.
    The ``many2one``, ``one2many`` and ``many2many`` attributes are wrapped in
    ``Record`` and ``RecordList`` objects.  These attributes support writing
    too.
    The attributes are evaluated lazily, and they are cached in the record.
    The Record's cache is invalidated if any attribute is changed.
    """
    def __init__(self, res_model, res_id, context=_DEFAULT):
        if isinstance(res_id, (list, tuple)):
            (res_id, res_name) = res_id
            self.__dict__['_name'] = res_name
        assert isinstance(res_id, int_types), repr(res_id)
        if context is _DEFAULT:
            context = res_model.client.context
        # Bypass the __setattr__ method
        self.__dict__.update({
            'id': res_id,
            '_model_name': res_model._name,
            '_model': res_model,
            '_context': context,
            '_cached_keys': set(),
            '_execute': res_model._execute,
        })

    def __repr__(self):
        return "<Record '%s,%d'>" % (self._model_name, self.id)

    def __str__(self):
        return self._name

    if PY2:
        __unicode__ = __str__

        def __str__(self):
            return self._name.encode('ascii', 'backslashreplace')

    def _get_name(self):
        try:
            (id_name,) = self._execute('name_get', [self.id])
            name = '%s' % (id_name[1],)
        except Exception:
            name = '%s,%d' % (self._model_name, self.id)
        return _memoize(self, '_name', name)

    @property
    def _keys(self):
        return self._model._keys

    @property
    def _fields(self):
        return self._model._fields

    def refresh(self):
        """Force refreshing the record's data."""
        self._cached_keys.discard('id')
        for key in self._cached_keys:
            delattr(self, key)
        self._cached_keys.clear()

    def _update(self, values):
        new_values = self._model._browse_values(values, context=self._context)
        self.__dict__.update(new_values)
        self._cached_keys.update(new_values)
        return new_values

    def read(self, fields=None, context=_DEFAULT):
        """Read the `fields` of the :class:`Record`.

        The argument `fields` accepts different kinds of values.
        See :meth:`Client.read` for details.
        """
        if context is _DEFAULT:
            context = self._context
        rv = self._model.read(self.id, fields, context=context)
        if isinstance(rv, dict):
            return self._update(rv)
        elif isinstance(fields, basestring) and '%(' not in fields:
            return self._update({fields: rv})[fields]
        return rv

    def perm_read(self, context=_DEFAULT):
        """Read the metadata of the :class:`Record`.

        Return a dictionary of values.
        See :meth:`Client.perm_read` for details.
        """
        if context is _DEFAULT:
            context = self._context
        rv = self._execute('perm_read', [self.id], context=context)
        return rv[0] if rv else None

    def write(self, values, context=_DEFAULT):
        """Write the `values` in the :class:`Record`.

        `values` is a dictionary of values.
        See :meth:`Model.create` for details.
        """
        if context is _DEFAULT:
            context = self._context
        values = self._model._unbrowse_values(values)
        rv = self._execute('write', [self.id], values, context=context)
        self.refresh()
        return rv

    def unlink(self, context=_DEFAULT):
        """Delete the current :class:`Record` from the database."""
        if context is _DEFAULT:
            context = self._context
        rv = self._execute('unlink', [self.id], context=context)
        self.refresh()
        return rv

    def copy(self, default=None, context=_DEFAULT):
        """Copy a record and return the new :class:`Record`.

        The optional argument `default` is a mapping which overrides some
        values of the new record.
        """
        if context is _DEFAULT:
            context = self._context
        if default:
            default = self._model._unbrowse_values(default)
        new_id = self._execute('copy', self.id, default, context=context)
        return Record(self._model, new_id, context=context)

    def _send(self, signal):
        """Trigger workflow `signal` for this :class:`Record`."""
        exec_workflow = self._model.client.exec_workflow
        rv = exec_workflow(self._model_name, signal, self.id)
        self.refresh()
        return rv

    @property
    def _external_id(self):
        """Retrieve the External ID of the :class:`Record`.

        Return the fully qualified External ID of the :class:`Record`,
        with default value False if there's none.  If multiple IDs
        exist, only one of them is returned (randomly).
        """
        xml_ids = self._model._get_external_ids([self.id])
        return list(xml_ids)[0] if xml_ids else False

    def _set_external_id(self, xml_id):
        """Set the External ID of this record."""
        (mod, name) = xml_id.split('.')
        obj = self._model_name
        domain = ['|', '&', ('model', '=', obj), ('res_id', '=', self.id),
                  '&', ('module', '=', mod), ('name', '=', name)]
        if self._model._imd_search(domain):
            raise ValueError('ID %r collides with another entry' % xml_id)
        vals = {'model': obj, 'res_id': self.id, 'module': mod, 'name': name}
        self._model._imd_create(vals)

    def __dir__(self):
        return ['read', 'write', 'copy', 'unlink', '_send', 'refresh',
                '_context', '_model', '_model_name', '_name', '_external_id',
                '_keys', '_fields'] + self._model._keys

    def __getattr__(self, attr):
        context = self._context
        if attr in self._model._keys:
            return self.read(attr, context=context)
        if attr == '_name':
            return self._get_name()
        if attr.startswith('_'):
            raise AttributeError("'Record' object has no attribute %r" % attr)

        def wrapper(self, *params, **kwargs):
            """Wrapper for client.execute(%r, %r, %d, *params, **kwargs)."""
            if context is not None and 'context' not in kwargs:
                kwargs['context'] = context
            res = self._execute(attr, [self.id], *params, **kwargs)
            self.refresh()
            if isinstance(res, list) and len(res) == 1:
                return res[0]
            return res
        return _memoize(self, attr, wrapper, (self._model_name, attr, self.id))

    def __setattr__(self, attr, value):
        if attr == '_external_id':
            return self._set_external_id(value)
        if attr not in self._model._keys:
            raise AttributeError("'Record' object has no attribute %r" % attr)
        if attr == 'id':
            raise AttributeError("'Record' object attribute 'id' is read-only")
        self.write({attr: value})

    def __eq__(self, other):
        return (isinstance(other, Record) and
                self.id == other.id and self._model is other._model)


def _interact(global_vars, use_pprint=True, usage=USAGE):
    import code
    import pprint
    if PY2:
        import __builtin__ as builtins

        def _exec(code, g):
            exec('exec code in g')
    else:
        import builtins
        _exec = getattr(builtins, 'exec')

    if use_pprint:
        def displayhook(value, _printer=pprint.pprint, _builtins=builtins):
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
        rl.parse_and_bind('tab: complete')
        # IOError if file missing, or broken Apple readline
        rl.read_history_file(HIST_FILE)
    except Exception:
        pass
    else:
        if rl.get_history_length() < 0:
            rl.set_history_length(int(os.getenv('HISTSIZE', 500)))
        # better append instead of replace?
        atexit.register(rl.write_history_file, HIST_FILE)

    class Console(code.InteractiveConsole):
        def runcode(self, code):
            try:
                _exec(code, global_vars)
            except SystemExit:
                raise
            except:
                # Print readable 'Fault' errors
                # Work around http://bugs.python.org/issue12643
                (exc_type, exc, tb) = sys.exc_info()
                msg = ''.join(format_exception(exc_type, exc, tb, chain=False))
                print(msg.strip())

    sys.exc_clear() if hasattr(sys, 'exc_clear') else None  # Python 2.x
    # Key UP to avoid an empty line
    Console().interact('\033[A')


def main(interact=_interact):
    description = ('Inspect data on Odoo objects.  Use interactively '
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
        '-c', '--config', default=None,
        help='specify alternate config file (default: %r)' % CONF_FILE)
    parser.add_option(
        '--server', default=None,
        help='full URL of the server (default: %s)' % DEFAULT_URL)
    parser.add_option('-d', '--db', default=DEFAULT_DB, help='database')
    parser.add_option('-u', '--user', default=None, help='username')
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

    Client._config_file = os.path.join(os.curdir, args.config or CONF_FILE)
    if args.list_env:
        print('Available settings:  ' + ' '.join(read_config()))
        return

    if (args.interact or not args.model):
        global_vars = Client._set_interactive()
        print(USAGE)

    if args.env:
        client = Client.from_config(args.env,
                                    user=args.user, verbose=args.verbose)
    else:
        if not args.server:
            args.server = ['-c', args.config] if args.config else DEFAULT_URL
        if not args.user:
            args.user = DEFAULT_USER
        client = Client(args.server, args.db, args.user, args.password,
                        verbose=args.verbose)
    client.context = {'lang': (os.getenv('LANG') or 'en_US').split('.')[0]}

    if args.model and client.user:
        data = client.execute(args.model, 'read', domain, args.fields)
        if not args.fields:
            args.fields = ['id']
            if data:
                args.fields.extend([fld for fld in data[0] if fld != 'id'])
        writer = _DictWriter(sys.stdout, args.fields, "", "ignore",
                             quoting=csv.QUOTE_NONNUMERIC)
        writer.writeheader()
        writer.writerows(data or ())

    if client.connect is not None:
        if not client.user:
            client.connect()
        # Enter interactive mode
        return interact(global_vars) if interact else global_vars

if __name__ == '__main__':
    main()
