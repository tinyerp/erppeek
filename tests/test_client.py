# -*- coding: utf-8 -*-
import mock
from mock import call, sentinel, ANY

import erppeek
from ._common import XmlRpcTestCase, OBJ

AUTH = sentinel.AUTH
ID1, ID2 = 4001, 4002
STABLE = ['uninstallable', 'uninstalled', 'installed']


def _skip_test(test_case):
    pass


class IdentDict(object):
    def __init__(self, _id):
        self._id = _id

    def __repr__(self):
        return 'IdentDict(%s)' % (self._id,)

    def __getitem__(self, key):
        return (key == 'id') and self._id or ('v_%s_%s' % (key, self._id))

    def __eq__(self, other):
        return self._id == other._id
DIC1 = IdentDict(ID1)
DIC2 = IdentDict(ID2)


class TestService(XmlRpcTestCase):
    """Test the Service class."""
    protocol = 'xmlrpc'

    def _patch_service(self):
        return mock.patch('erppeek.ServerProxy._ServerProxy__request').start()

    def _get_client(self):
        client = mock.Mock()
        client._server = 'http://127.0.0.1:8069/%s' % self.protocol
        proxy = getattr(erppeek.Client, '_proxy_%s' % self.protocol)
        client._proxy = proxy.__get__(client, erppeek.Client)
        return client

    def test_service(self):
        client = self._get_client()
        svc_alpha = erppeek.Service(client, 'alpha', ['beta'])

        self.assertIn('alpha', str(svc_alpha.beta))
        self.assertRaises(AttributeError, getattr, svc_alpha, 'theta')
        if self.protocol == 'xmlrpc':
            self.assertIn('_ServerProxy__request', str(svc_alpha.beta(42)))
            self.assertCalls(call('beta', (42,)), "().__str__")
        else:
            self.assertCalls()
        self.assertOutput('')

    def test_service_openerp(self):
        client = self._get_client()

        def get_proxy(name, methods=None):
            if methods is None:
                methods = erppeek._methods.get(name, ())
            return erppeek.Service(client, name, methods, verbose=False)

        self.assertIn('common', str(get_proxy('common').login))
        login = get_proxy('common').login('aaa')
        with self.assertRaises(AttributeError):
            get_proxy('common').non_existent
        if self.protocol == 'xmlrpc':
            self.assertIn('_ServerProxy__request', str(login))
            self.assertCalls(call('login', ('aaa',)), 'call().__str__')
        else:
            self.assertEqual(login, 'JSON_RESULT',)
            self.assertCalls(ANY)
        self.assertOutput('')

    def test_service_openerp_client(self, server_version=11.0):
        server = 'http://127.0.0.1:8069/%s' % self.protocol
        return_values = [str(server_version), ['newdb'], 1]
        if self.protocol == 'jsonrpc':
            return_values = [{'result': rv} for rv in return_values]
        self.service.side_effect = return_values
        client = erppeek.Client(server, 'newdb', 'usr', 'pss')

        self.service.return_value = ANY
        self.assertIsInstance(client.db, erppeek.Service)
        self.assertIsInstance(client.common, erppeek.Service)
        self.assertIsInstance(client._object, erppeek.Service)
        if server_version >= 11.0:
            self.assertIs(client._report, None)
            self.assertIs(client._wizard, None)
        elif server_version >= 7.0:
            self.assertIsInstance(client._report, erppeek.Service)
            self.assertIs(client._wizard, None)
        else:
            self.assertIsInstance(client._report, erppeek.Service)
            self.assertIsInstance(client._wizard, erppeek.Service)

        self.assertIn('/%s|db' % self.protocol, str(client.db.create_database))
        self.assertIn('/%s|db' % self.protocol, str(client.db.db_exist))
        if server_version >= 8.0:
            self.assertRaises(AttributeError, getattr,
                              client.db, 'create')
            self.assertRaises(AttributeError, getattr,
                              client.db, 'get_progress')
        else:
            self.assertIn('/%s|db' % self.protocol, str(client.db.create))
            self.assertIn('/%s|db' % self.protocol, str(client.db.get_progress))

        self.assertCalls(ANY, ANY, ANY)
        self.assertOutput('')

    def test_service_openerp_50_to_70(self):
        self.test_service_openerp_client(server_version=7.0)
        self.test_service_openerp_client(server_version=6.1)
        self.test_service_openerp_client(server_version=6.0)
        self.test_service_openerp_client(server_version=5.0)

    def test_service_odoo_80_90(self):
        self.test_service_openerp_client(server_version=9.0)
        self.test_service_openerp_client(server_version=8.0)

    def test_service_odoo_10_11(self):
        self.test_service_openerp_client(server_version=11.0)
        self.test_service_openerp_client(server_version=10.0)


class TestServiceJsonRpc(TestService):
    """Test the Service class with JSON-RPC."""
    protocol = 'jsonrpc'

    def _patch_service(self):
        return mock.patch('erppeek.http_post', return_value={'result': 'JSON_RESULT'}).start()


class TestCreateClient(XmlRpcTestCase):
    """Test the Client class."""
    server_version = '6.1'
    startup_calls = (
        call(ANY, 'db', ANY, verbose=ANY),
        'db.server_version',
        call(ANY, 'db', ANY, verbose=ANY),
        call(ANY, 'common', ANY, verbose=ANY),
        call(ANY, 'object', ANY, verbose=ANY),
        call(ANY, 'report', ANY, verbose=ANY),
        call(ANY, 'wizard', ANY, verbose=ANY),
        'db.list',
    )

    def test_create(self):
        self.service.db.list.return_value = ['newdb']
        self.service.common.login.return_value = 1

        client = erppeek.Client('http://127.0.0.1:8069', 'newdb', 'usr', 'pss')
        expected_calls = self.startup_calls + (
            ('common.login', 'newdb', 'usr', 'pss'),)
        self.assertIsInstance(client, erppeek.Client)
        self.assertCalls(*expected_calls)
        self.assertEqual(
            client._login.cache,
            {('http://127.0.0.1:8069/xmlrpc', 'newdb', 'usr'): (1, 'pss')})
        self.assertOutput('')

    def test_create_getpass(self):
        getpass = mock.patch('getpass.getpass',
                             return_value='password').start()
        self.service.db.list.return_value = ['database']
        expected_calls = self.startup_calls + (
            ('common.login', 'database', 'usr', 'password'),)

        # A: Invalid login
        self.assertRaises(erppeek.Error, erppeek.Client,
                          'http://127.0.0.1:8069', 'database', 'usr')
        self.assertCalls(*expected_calls)
        self.assertEqual(getpass.call_count, 1)

        # B: Valid login
        self.service.common.login.return_value = 17
        getpass.reset_mock()

        client = erppeek.Client('http://127.0.0.1:8069', 'database', 'usr')
        self.assertIsInstance(client, erppeek.Client)
        self.assertCalls(*expected_calls)
        self.assertEqual(getpass.call_count, 1)

    def test_create_with_cache(self):
        self.service.db.list.return_value = ['database']
        self.assertFalse(erppeek.Client._login.cache)
        erppeek.Client._login.cache[
            ('http://127.0.0.1:8069/xmlrpc', 'database', 'usr')] = (1, 'password')

        client = erppeek.Client('http://127.0.0.1:8069', 'database', 'usr')
        expected_calls = self.startup_calls + (
            ('object.execute', 'database', 1, 'password',
             'res.users', 'fields_get_keys'),)
        self.assertIsInstance(client, erppeek.Client)
        self.assertCalls(*expected_calls)
        self.assertOutput('')

    def test_create_from_config(self):
        env_tuple = ('http://127.0.0.1:8069', 'database', 'usr', None)
        read_config = mock.patch('erppeek.read_config',
                                 return_value=env_tuple).start()
        getpass = mock.patch('getpass.getpass',
                             return_value='password').start()
        self.service.db.list.return_value = ['database']
        expected_calls = self.startup_calls + (
            ('common.login', 'database', 'usr', 'password'),)

        # A: Invalid login
        self.assertRaises(erppeek.Error, erppeek.Client.from_config, 'test')
        self.assertCalls(*expected_calls)
        self.assertEqual(read_config.call_count, 1)
        self.assertEqual(getpass.call_count, 1)

        # B: Valid login
        self.service.common.login.return_value = 17
        read_config.reset_mock()
        getpass.reset_mock()

        client = erppeek.Client.from_config('test')
        self.assertIsInstance(client, erppeek.Client)
        self.assertCalls(*expected_calls)
        self.assertEqual(read_config.call_count, 1)
        self.assertEqual(getpass.call_count, 1)

    def test_create_invalid(self):
        # Without mock
        self.service.stop()

        self.assertRaises(EnvironmentError, erppeek.Client, 'dsadas')
        self.assertOutput('')


class TestSampleSession(XmlRpcTestCase):
    server_version = '6.1'
    server = 'http://127.0.0.1:8069'
    database = 'database'
    user = 'user'
    password = 'passwd'
    uid = 1

    def test_simple(self):
        self.service.object.execute.side_effect = [
            42, [{'model': 'res.users'}], 4, sentinel.IDS, sentinel.CRON]

        c = self.client
        res_users = c.model('res.users')
        self.assertIs(c.ResUsers, res_users)
        self.assertEqual(c.ResUsers.count(), 4)
        self.assertEqual(c.read('ir.cron', ['active = False'],
                         'active function'), sentinel.CRON)
        self.assertCalls(
            OBJ('ir.model', 'search', [('model', 'like', 'res.users')]),
            OBJ('ir.model', 'read', 42, ('model',)),
            OBJ('res.users', 'search_count', []),
            OBJ('ir.cron', 'search', [('active', '=', False)]),
            OBJ('ir.cron', 'read', sentinel.IDS, ['active', 'function']),
        )
        self.assertOutput('')

    def test_list_modules(self):
        self.service.object.execute.side_effect = [
            ['delivery_a', 'delivery_b'],
            [{'state': 'not installed', 'name': 'dummy'}]]

        modules = self.client.modules('delivery')
        self.assertIsInstance(modules, dict)
        self.assertIn('not installed', modules)
        imm = ('object.execute', AUTH, 'ir.module.module')
        self.assertCalls(
            imm + ('search', [('name', 'like', 'delivery')]),
            imm + ('read', ['delivery_a', 'delivery_b'], ['name', 'state']),
        )
        self.assertOutput('')

    def test_module_upgrade(self):
        self.service.object.execute.side_effect = [
            (42, 0), [42], [], ANY, [42],
            [{'id': 42, 'state': ANY, 'name': ANY}], ANY]

        result = self.client.upgrade('dummy')
        self.assertIsNone(result)
        imm = ('object.execute', AUTH, 'ir.module.module')
        bmu = ('object.execute', AUTH, 'base.module.upgrade')
        self.assertCalls(
            imm + ('update_list',),
            imm + ('search', [('name', 'in', ('dummy',))]),
            imm + ('search', [('state', 'not in', STABLE)]),
            imm + ('button_upgrade', [42]),
            imm + ('search', [('state', 'not in', STABLE)]),
            imm + ('read', [42], ['name', 'state']),
            bmu + ('upgrade_module', []),
        )
        self.assertOutput(ANY)


class TestSampleSession50(TestSampleSession):
    server_version = '5.0'

    def test_module_upgrade(self):
        self.service.object.execute.side_effect = [
            (42, 0), [42], [], ANY, [42],
            [{'id': 42, 'state': ANY, 'name': ANY}]]
        self.service.wizard.create.return_value = 17
        self.service.wizard.execute.return_value = {'state': (['config'],)}

        result = self.client.upgrade('dummy')
        self.assertIsNone(result)
        imm = ('object.execute', AUTH, 'ir.module.module')
        self.assertCalls(
            imm + ('update_list',),
            imm + ('search', [('name', 'in', ('dummy',))]),
            imm + ('search', [('state', 'not in', STABLE)]),
            imm + ('button_upgrade', [42]),
            imm + ('search', [('state', 'not in', STABLE)]),
            imm + ('read', [42], ['name', 'state']),
            ('wizard.create', AUTH, 'module.upgrade'),
            ('wizard.execute', AUTH, 17, {}, 'start', None),
        )
        self.assertOutput(ANY)


class TestClientApi(XmlRpcTestCase):
    """Test the Client API."""
    server_version = '6.1'
    server = 'http://127.0.0.1:8069'
    database = 'database'
    user = 'user'
    password = 'passwd'
    uid = 1

    def obj_exec(self, *args):
        if args[4] == 'search':
            return [ID2, ID1]
        if args[4] == 'read':
            return [IdentDict(res_id) for res_id in args[5][::-1]]
        return sentinel.OTHER

    def test_create_database(self):
        create_database = self.client.create_database
        self.client.db.list.side_effect = [['db1'], ['db2']]

        create_database('abc', 'db1')
        create_database('xyz', 'db2', user_password='secret', lang='fr_FR')

        self.assertCalls(
            call.db.create_database('abc', 'db1', False, 'en_US', 'admin'),
            call.db.list(),
            call.common.login('db1', 'admin', 'admin'),
            call.db.create_database('xyz', 'db2', False, 'fr_FR', 'secret'),
            call.db.list(),
            call.common.login('db2', 'admin', 'secret'),
        )
        self.assertOutput('')

        if float(self.server_version) < 9.0:
            self.assertRaises(erppeek.Error, create_database, 'xyz', 'db2', user_password='secret', lang='fr_FR', login='other_login', country_code='CA')
            self.assertRaises(erppeek.Error, create_database, 'xyz', 'db2', login='other_login')
            self.assertRaises(erppeek.Error, create_database, 'xyz', 'db2', country_code='CA')
            self.assertOutput('')
            return

        # Odoo 9
        self.client.db.list.side_effect = [['db2']]
        create_database('xyz', 'db2', user_password='secret', lang='fr_FR', login='other_login', country_code='CA')

        self.assertCalls(
            call.db.create_database('xyz', 'db2', False, 'fr_FR', 'secret', 'other_login', 'CA'),
            call.db.list(),
            call.common.login('db2', 'other_login', 'secret'),
        )
        self.assertOutput('')

    def test_search(self):
        search = self.client.search
        self.service.object.execute.side_effect = self.obj_exec

        searchterm = 'name like Morice'
        self.assertEqual(search('foo.bar', [searchterm]), [ID2, ID1])
        self.assertEqual(search('foo.bar', [searchterm], limit=2), [ID2, ID1])
        self.assertEqual(search('foo.bar', [searchterm], offset=80, limit=99),
                         [ID2, ID1])
        self.assertEqual(search('foo.bar', [searchterm], order='name ASC'),
                         [ID2, ID1])
        search('foo.bar', ['name = mushroom', 'state != draft'])
        search('foo.bar', [('name', 'like', 'Morice')])
        self.client.execute('foo.bar', 'search', [('name like Morice')])
        search('foo.bar', [])
        search('foo.bar')
        domain = [('name', 'like', 'Morice')]
        domain2 = [('name', '=', 'mushroom'), ('state', '!=', 'draft')]
        self.assertCalls(
            OBJ('foo.bar', 'search', domain),
            OBJ('foo.bar', 'search', domain, 0, 2, None),
            OBJ('foo.bar', 'search', domain, 80, 99, None),
            OBJ('foo.bar', 'search', domain, 0, None, 'name ASC'),
            OBJ('foo.bar', 'search', domain2),
            OBJ('foo.bar', 'search', domain),
            OBJ('foo.bar', 'search', domain),
            OBJ('foo.bar', 'search', []),
            OBJ('foo.bar', 'search', []),
        )
        self.assertOutput('')

        # No longer supported since 1.6
        search('foo.bar', 'name like Morice')
        self.assertCalls(OBJ('foo.bar', 'search', 'name like Morice'))

        search('foo.bar', ['name like Morice'], missingkey=42)
        self.assertCalls(OBJ('foo.bar', 'search', domain))
        self.assertOutput('Ignoring: missingkey = 42\n')

        self.assertRaises(TypeError, search)
        self.assertRaises(AssertionError, search, object())
        self.assertRaises(ValueError, search, 'foo.bar', ['abc'])
        self.assertRaises(ValueError, search, 'foo.bar', ['< id'])
        self.assertRaises(ValueError, search, 'foo.bar', ['name Morice'])

        self.assertCalls()
        self.assertOutput('')

    def test_count(self):
        count = self.client.count

        count('foo.bar', ['name like Morice'])
        count('foo.bar', ['name = mushroom', 'state != draft'])
        count('foo.bar', [('name', 'like', 'Morice')])
        self.client.execute('foo.bar', 'search_count', [('name like Morice')])
        count('foo.bar', [])
        count('foo.bar')
        domain = [('name', 'like', 'Morice')]
        domain2 = [('name', '=', 'mushroom'), ('state', '!=', 'draft')]
        self.assertCalls(
            OBJ('foo.bar', 'search_count', domain),
            OBJ('foo.bar', 'search_count', domain2),
            OBJ('foo.bar', 'search_count', domain),
            OBJ('foo.bar', 'search_count', domain),
            OBJ('foo.bar', 'search_count', []),
            OBJ('foo.bar', 'search_count', []),
        )
        self.assertOutput('')

        # No longer supported since 1.6
        count('foo.bar', 'name like Morice')
        self.assertCalls(OBJ('foo.bar', 'search_count', 'name like Morice'))

        self.assertRaises(TypeError, count)
        self.assertRaises(TypeError, count,
                          ['name like Morice'], limit=2)
        self.assertRaises(TypeError, count,
                          ['name like Morice'], offset=80, limit=99)
        self.assertRaises(TypeError, count,
                          ['name like Morice'], order='name ASC')
        self.assertRaises(AssertionError, count, object())
        self.assertRaises(ValueError, count, 'foo.bar', ['abc'])
        self.assertRaises(ValueError, count, 'foo.bar', ['< id'])
        self.assertRaises(ValueError, count, 'foo.bar', ['name Morice'])

        self.assertCalls()
        self.assertOutput('')

    def test_read_simple(self):
        read = self.client.read
        self.service.object.execute.side_effect = self.obj_exec

        read('foo.bar', 42)
        read('foo.bar', [42])
        read('foo.bar', [13, 17])
        read('foo.bar', [42], 'first_name')
        self.assertCalls(
            OBJ('foo.bar', 'read', [42], None),
            OBJ('foo.bar', 'read', [42], None),
            OBJ('foo.bar', 'read', [13, 17], None),
            OBJ('foo.bar', 'read', [42], ['first_name']),
        )
        self.assertOutput('')

    def test_read_complex(self):
        read = self.client.read
        self.service.object.execute.side_effect = self.obj_exec

        searchterm = 'name like Morice'
        self.assertEqual(read('foo.bar', [searchterm]), [DIC1, DIC2])
        self.assertEqual(read('foo.bar', [searchterm], limit=2), [DIC1, DIC2])
        self.assertEqual(read('foo.bar', [searchterm], offset=80, limit=99),
                         [DIC1, DIC2])
        self.assertEqual(read('foo.bar', [searchterm], order='name ASC'),
                         [DIC2, DIC1])
        read('foo.bar', [searchterm], 'birthdate city')
        read('foo.bar', [searchterm], 'birthdate city', limit=2)
        read('foo.bar', [searchterm], limit=2, fields=['birthdate', 'city'])
        read('foo.bar', [searchterm], order='name ASC')
        read('foo.bar', ['name = mushroom', 'state != draft'])
        read('foo.bar', [('name', 'like', 'Morice')])
        self.client.execute('foo.bar', 'read', ['name like Morice'])

        rv = read('foo.bar', ['name like Morice'],
                  'aaa %(birthdate)s bbb %(city)s', offset=80, limit=99)
        self.assertEqual(rv, ['aaa v_birthdate_4001 bbb v_city_4001',
                              'aaa v_birthdate_4002 bbb v_city_4002'])

        def call_read(fields=None):
            return OBJ('foo.bar', 'read', [ID2, ID1], fields)
        domain = [('name', 'like', 'Morice')]
        domain2 = [('name', '=', 'mushroom'), ('state', '!=', 'draft')]
        self.assertCalls(
            OBJ('foo.bar', 'search', domain), call_read(),
            OBJ('foo.bar', 'search', domain, 0, 2, None), call_read(),
            OBJ('foo.bar', 'search', domain, 80, 99, None), call_read(),
            OBJ('foo.bar', 'search', domain, 0, None, 'name ASC'),
            call_read(),
            OBJ('foo.bar', 'search', domain), call_read(['birthdate', 'city']),
            OBJ('foo.bar', 'search', domain, 0, 2, None),
            call_read(['birthdate', 'city']),
            OBJ('foo.bar', 'search', domain, 0, 2, None),
            call_read(['birthdate', 'city']),
            OBJ('foo.bar', 'search', domain, 0, None, 'name ASC'),
            call_read(),
            OBJ('foo.bar', 'search', domain2), call_read(),
            OBJ('foo.bar', 'search', domain), call_read(),
            OBJ('foo.bar', 'search', domain), call_read(),
            OBJ('foo.bar', 'search', domain, 80, 99, None),
            call_read(['birthdate', 'city']),
        )
        self.assertOutput('')

    def test_read_false(self):
        read = self.client.read
        self.service.object.execute.side_effect = self.obj_exec

        self.assertEqual(read('foo.bar', False), False)

        self.assertEqual(read('foo.bar', [False]), [])
        self.assertEqual(read('foo.bar', [False, False]), [])
        self.assertEqual(read('foo.bar', [False], 'first_name'), [])
        self.assertEqual(read('foo.bar', [False], order=True),
                         [False])
        self.assertEqual(read('foo.bar', [False, False], order=True),
                         [False, False])
        self.assertEqual(read('foo.bar', [False], 'first_name', order=True),
                         [False])
        self.assertEqual(read('foo.bar', [], 'first_name'), False)
        self.assertEqual(read('foo.bar', [], 'first_name', order=True), False)

        self.assertCalls()

        self.assertEqual(read('foo.bar', [False, 42]), [IdentDict(42)])
        self.assertEqual(read('foo.bar', [False, 13, 17, False]),
                         [IdentDict(17), IdentDict(13)])
        self.assertEqual(read('foo.bar', [13, False, 17], 'first_name'),
                         ['v_first_name_17', 'v_first_name_13'])
        self.assertEqual(read('foo.bar', [False, 42], order=True),
                         [False, IdentDict(42)])
        self.assertEqual(read('foo.bar', [False, 13, 17, False], order=True),
                         [False, IdentDict(13), IdentDict(17), False])
        self.assertEqual(read('foo.bar', [13, False, 17], 'city', order=True),
                         ['v_city_13', False, 'v_city_17'])

        self.assertCalls(
            OBJ('foo.bar', 'read', [42], None),
            OBJ('foo.bar', 'read', [13, 17], None),
            OBJ('foo.bar', 'read', [13, 17], ['first_name']),
            OBJ('foo.bar', 'read', [42], None),
            OBJ('foo.bar', 'read', [13, 17], None),
            OBJ('foo.bar', 'read', [13, 17], ['city']),
        )
        self.assertOutput('')

    def test_read_invalid(self):
        read = self.client.read
        self.service.object.execute.side_effect = self.obj_exec
        domain = [('name', 'like', 'Morice')]

        # No longer supported since 1.6
        read('foo.bar', 'name like Morice')

        read('foo.bar', ['name like Morice'], missingkey=42)

        self.assertCalls(
            OBJ('foo.bar', 'read', ['name like Morice'], None),
            OBJ('foo.bar', 'search', domain),
            OBJ('foo.bar', 'read', ANY, None))
        self.assertOutput('Ignoring: missingkey = 42\n')

        self.assertRaises(TypeError, read)
        self.assertRaises(AssertionError, read, object())
        self.assertRaises(AssertionError, read, 'foo.bar')
        self.assertRaises(ValueError, read, 'foo.bar', ['abc'])
        self.assertRaises(ValueError, read, 'foo.bar', ['< id'])
        self.assertRaises(ValueError, read, 'foo.bar', ['name Morice'])

        self.assertCalls()
        self.assertOutput('')

    def test_method(self, method_name='method', single_id=True):
        method = getattr(self.client, method_name)

        single_id = single_id and 42 or [42]

        method('foo.bar', 42)
        method('foo.bar', [42])
        method('foo.bar', [13, 17])
        self.client.execute('foo.bar', method_name, [42])
        method('foo.bar', [])
        self.assertCalls(
            OBJ('foo.bar', method_name, single_id),
            OBJ('foo.bar', method_name, [42]),
            OBJ('foo.bar', method_name, [13, 17]),
            OBJ('foo.bar', method_name, [42]),
            OBJ('foo.bar', method_name, []),
        )
        self.assertRaises(TypeError, method)
        self.assertRaises(AssertionError, method, object())
        self.assertOutput('')

    def test_standard_methods(self):
        for method in 'write', 'create', 'copy', 'unlink':
            self.test_method(method)

        self.test_method('perm_read', single_id=False)

    def test_model(self):
        self.service.object.execute.side_effect = self.obj_exec

        self.assertTrue(self.client.models('foo.bar'))
        self.assertCalls(
            OBJ('ir.model', 'search', [('model', 'like', 'foo.bar')]),
            OBJ('ir.model', 'read', [ID2, ID1], ('model',)),
        )
        self.assertOutput('')

        self.assertRaises(erppeek.Error, self.client.model, 'foo.bar')
        self.assertCalls(
            OBJ('ir.model', 'search', [('model', 'like', 'foo.bar')]),
            OBJ('ir.model', 'read', [ID2, ID1], ('model',)),
        )
        self.assertOutput('')

        self.service.object.execute.side_effect = [
            sentinel.IDS, [{'id': 13, 'model': 'foo.bar'}]]
        self.assertIsInstance(self.client.model('foo.bar'), erppeek.Model)
        self.assertIs(self.client.model('foo.bar'),
                      erppeek.Model(self.client, 'foo.bar'))
        self.assertIs(self.client.model('foo.bar'),
                      self.client.FooBar)
        self.assertCalls(
            OBJ('ir.model', 'search', [('model', 'like', 'foo.bar')]),
            OBJ('ir.model', 'read', sentinel.IDS, ('model',)),
        )
        self.assertOutput('')

    def test_keys(self):
        self.service.object.execute.side_effect = [
            sentinel.IDS, [{'model': 'foo.bar'}], ['spam']]
        self.assertTrue(self.client.keys('foo.bar'))
        self.assertCalls(
            OBJ('ir.model', 'search', [('model', 'like', 'foo.bar')]),
            OBJ('ir.model', 'read', sentinel.IDS, ('model',)),
            OBJ('foo.bar', 'fields_get_keys'),
        )
        self.assertOutput('')

    def test_fields(self):
        self.service.object.execute.side_effect = [
            sentinel.IDS, [{'model': 'foo.bar'}], {'spam': sentinel.FIELD}]
        self.assertTrue(self.client.fields('foo.bar'))
        self.assertCalls(
            OBJ('ir.model', 'search', [('model', 'like', 'foo.bar')]),
            OBJ('ir.model', 'read', sentinel.IDS, ('model',)),
            OBJ('foo.bar', 'fields_get'),
        )
        self.assertOutput('')

    def test_field(self):
        self.service.object.execute.side_effect = [
            sentinel.IDS, [{'model': 'foo.bar'}], {'spam': sentinel.FIELD}]
        self.assertTrue(self.client.field('foo.bar', 'spam'))

        self.assertRaises(TypeError, self.client.field)
        self.assertRaises(TypeError, self.client.field, 'foo.bar')
        self.assertCalls(
            OBJ('ir.model', 'search', [('model', 'like', 'foo.bar')]),
            OBJ('ir.model', 'read', sentinel.IDS, ('model',)),
            OBJ('foo.bar', 'fields_get'),
        )
        self.assertOutput('')

    def test_access(self):
        self.assertTrue(self.client.access('foo.bar'))
        self.assertCalls(OBJ('ir.model.access', 'check', 'foo.bar', 'read'))
        self.assertOutput('')

    def test_execute_kw(self):
        execute_kw = self.client.execute_kw

        execute_kw('foo.bar', 'any_method', 42)
        execute_kw('foo.bar', 'any_method', [42])
        execute_kw('foo.bar', 'any_method', [13, 17])
        self.assertCalls(
            ('object.execute_kw', AUTH, 'foo.bar', 'any_method', 42),
            ('object.execute_kw', AUTH, 'foo.bar', 'any_method', [42]),
            ('object.execute_kw', AUTH, 'foo.bar', 'any_method', [13, 17]),
        )
        self.assertOutput('')

    def test_exec_workflow(self):
        exec_workflow = self.client.exec_workflow

        self.assertTrue(exec_workflow('foo.bar', 'light', 42))

        self.assertRaises(TypeError, exec_workflow)
        self.assertRaises(TypeError, exec_workflow, 'foo.bar')
        self.assertRaises(TypeError, exec_workflow, 'foo.bar', 'rip')
        self.assertRaises(TypeError, exec_workflow, 'foo.bar', 'rip', 42, None)
        self.assertRaises(AssertionError, exec_workflow, 42, 'rip', 42)
        self.assertRaises(AssertionError, exec_workflow, 'foo.bar', 42, 42)

        self.assertCalls(
            ('object.exec_workflow', AUTH, 'foo.bar', 'light', 42),
        )
        self.assertOutput('')

    def test_wizard(self):
        wizard = self.client.wizard
        self.service.wizard.create.return_value = ID1

        self.assertTrue(wizard('foo.bar'))
        self.assertTrue(wizard('billy', action='shake'))
        self.assertTrue(wizard(42, action='kick'))

        self.assertRaises(TypeError, wizard)

        self.assertCalls(
            ('wizard.create', AUTH, 'foo.bar'),
            ('wizard.create', AUTH, 'billy'),
            ('wizard.execute', AUTH, ID1, {}, 'shake', None),
            ('wizard.execute', AUTH, 42, {}, 'kick', None),
        )
        self.assertOutput('')

    def test_report(self):
        self.assertTrue(self.client.report('foo.bar', sentinel.IDS))
        self.assertCalls(
            ('report.report', AUTH, 'foo.bar', sentinel.IDS),
        )
        self.assertOutput('')

    def test_render_report(self):
        self.assertTrue(self.client.render_report('foo.bar', sentinel.IDS))
        self.assertCalls(
            ('report.render_report', AUTH, 'foo.bar', sentinel.IDS),
        )
        self.assertOutput('')

    def test_report_get(self):
        self.assertTrue(self.client.report_get(ID1))
        self.assertCalls(
            ('report.report_get', AUTH, ID1),
        )
        self.assertOutput('')

    def _module_upgrade(self, button='upgrade'):
        execute_return = [
            [7, 0], [42], [], {'name': 'Upgrade'}, [4, 42, 5],
            [{'id': 4, 'state': ANY, 'name': ANY},
             {'id': 5, 'state': ANY, 'name': ANY},
             {'id': 42, 'state': ANY, 'name': ANY}], ANY]
        action = getattr(self.client, button)

        imm = ('object.execute', AUTH, 'ir.module.module')
        bmu = ('object.execute', AUTH, 'base.module.upgrade')
        expected_calls = [
            imm + ('update_list',),
            imm + ('search', [('name', 'in', ('dummy', 'spam'))]),
            imm + ('search', [('state', 'not in', STABLE)]),
            imm + ('button_' + button, [42]),
            imm + ('search', [('state', 'not in', STABLE)]),
            imm + ('read', [4, 42, 5], ['name', 'state']),
            bmu + ('upgrade_module', []),
        ]
        if button == 'uninstall':
            execute_return[3:3] = [[], ANY]
            expected_calls[3:3] = [
                imm + ('search', [('id', 'in', [42]),
                                  ('state', '!=', 'installed'),
                                  ('state', '!=', 'to upgrade'),
                                  ('state', '!=', 'to remove')]),
                imm + ('write', [42], {'state': 'to remove'}),
            ]

        self.service.object.execute.side_effect = execute_return
        result = action('dummy', 'spam')
        self.assertIsNone(result)
        self.assertCalls(*expected_calls)

        self.assertIn('to process', self.stdout.popvalue())
        self.assertOutput('')

    def test_module_upgrade(self):
        self._module_upgrade('install')
        self._module_upgrade('upgrade')
        self._module_upgrade('uninstall')


class TestClientApi50(TestClientApi):
    """Test the Client API for OpenERP 5."""
    server_version = '5.0'

    test_execute_kw = test_render_report = _skip_test

    def test_create_database(self):
        create_database = self.client.create_database
        mock.patch('time.sleep').start()
        self.client.db.create.return_value = ID1
        self.client.db.get_progress.return_value = \
            [1, [{'login': 'admin', 'password': 'PP'}]]
        self.client.db.list.side_effect = [['db1'], ['db2']]

        create_database('abc', 'db1')
        create_database('xyz', 'db2', user_password='secret', lang='fr_FR')

        self.assertCalls(
            call.db.create('abc', 'db1', False, 'en_US', 'admin'),
            call.db.get_progress('abc', ID1),
            call.db.list(),
            call.common.login('db1', 'admin', 'admin'),
            call.db.create('xyz', 'db2', False, 'fr_FR', 'secret'),
            call.db.get_progress('xyz', ID1),
            call.db.list(),
            call.common.login('db2', 'admin', 'secret'),
        )
        self.assertOutput('')

    def _module_upgrade(self, button='upgrade'):
        execute_return = [
            [7, 0], [42], [], {'name': 'Upgrade'}, [4, 42, 5],
            [{'id': 4, 'state': ANY, 'name': ANY},
             {'id': 5, 'state': ANY, 'name': ANY},
             {'id': 42, 'state': ANY, 'name': ANY}]]
        self.service.wizard.create.return_value = 17
        self.service.wizard.execute.return_value = {'state': (['config'],)}
        action = getattr(self.client, button)

        imm = ('object.execute', AUTH, 'ir.module.module')
        expected_calls = [
            imm + ('update_list',),
            imm + ('search', [('name', 'in', ('dummy', 'spam'))]),
            imm + ('search', [('state', 'not in', STABLE)]),
            imm + ('button_' + button, [42]),
            imm + ('search', [('state', 'not in', STABLE)]),
            imm + ('read', [4, 42, 5], ['name', 'state']),
            ('wizard.create', AUTH, 'module.upgrade'),
            ('wizard.execute', AUTH, 17, {}, 'start', None),
        ]
        if button == 'uninstall':
            execute_return[3:3] = [[], ANY]
            expected_calls[3:3] = [
                imm + ('search', [('id', 'in', [42]),
                                  ('state', '!=', 'installed'),
                                  ('state', '!=', 'to upgrade'),
                                  ('state', '!=', 'to remove')]),
                imm + ('write', [42], {'state': 'to remove'}),
            ]

        self.service.object.execute.side_effect = execute_return
        result = action('dummy', 'spam')
        self.assertIsNone(result)
        self.assertCalls(*expected_calls)

        self.assertIn('to process', self.stdout.popvalue())
        self.assertOutput('')


class TestClientApi90(TestClientApi):
    """Test the Client API for Odoo 9."""
    server_version = '9.0'
    test_wizard = _skip_test


class TestClientApi11(TestClientApi):
    """Test the Client API for Odoo 11."""
    server_version = '11.0'
    test_wizard = _skip_test
    test_report = test_render_report = test_report_get = _skip_test
