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
Usage:
    do(obj, method, *params)        # Generic 'service.execute'

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
"""

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


def read_config(section):
    p = ConfigParser.SafeConfigParser()
    with open(ini_path) as f:
        p.readfp(f)
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
            m = _term_re.match(term.strip())
            if not m:
                continue
            (field, operator, value) = m.groups()
            try:
                value = literal_eval(value)
            except Exception:
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
        sock = xmlrpclib.ServerProxy(server + '/xmlrpc/common')
        uid = sock.login(db, user, password)
        if uid is False:
            raise RuntimeError('Invalid username or password')
        sock = xmlrpclib.ServerProxy(server + '/xmlrpc/object', allow_none=True)
        self._server = server
        self._execute = functools.partial(sock.execute, db, uid, password)

    @classmethod
    def from_config(cls, environment):
        return cls(*read_config(environment))

    @property
    def server(self):
        return self._server

    def __repr__(self):
        return "<Client '%s'>" % self._server

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

    def keys(self, obj):
        return sorted(self.execute(obj, 'fields_get_keys'))

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


def main():
    parser = optparse.OptionParser(
            usage='%prog [options] [id [id ...]]',
            description='Inspect data on OpenERP objects')
    parser.add_option('-m', '--model',
            help='the type of object to find')
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
    parser.add_option('-s', '--search', action='append', dest='search',
            help='search condition (multiple allowed); alternatively, pass '
                 'multiple IDs as positional parameters after the options')
    parser.add_option('-f', action='append', dest='fields',
            help='restrict the output to certain fields (multiple allowed)')
    parser.add_option('-i', action='store_true', dest='inspect',
            help='use interactively')

    (args, ids) = parser.parse_args()

    if args.env:
        client = Client.from_config(args.env)
        # Tweak prompt
        sys.ps1 = '%s >>> ' % args.env
        sys.ps2 = '%s ... ' % args.env
    else:
        client = Client(args.server, args.db, args.user, args.password)

    if args.inspect or not args.model:
        try:
            # completion and history features
            import readline
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


if __name__ == '__main__':
    client, data = main()
    if data is not None:
        pprint(data)
    if client:
        # interactive usage
        print USAGE
        do = client.execute
        read = client.read
        search = client.search
        count = client.count
        model = client.model
        keys = client.keys
        fields = client.fields
        field = client.field
