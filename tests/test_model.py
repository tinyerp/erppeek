# -*- coding: utf-8 -*-
import mock
from mock import sentinel, ANY

import erppeek
from ._common import XmlRpcTestCase, OBJ, callable


class TestCase(XmlRpcTestCase):
    server_version = '6.1'
    server = 'http://127.0.0.1:8069'
    database = 'database'
    user = 'user'
    password = 'passwd'
    uid = 1

    def obj_exec(self, *args):
        if args[4] == 'search':
            if args[3] == 'ir.model' and 'foo' in str(args[5]):
                return sentinel.FOO
            return [sentinel.ID1, sentinel.ID2]
        if args[4] == 'read':
            if args[5] is sentinel.FOO:
                return [{'model': 'foo.bar', 'id': 371}]

            class IdentDict(dict):
                def __init__(self, id_):
                    self._id = id_

                def __getitem__(self, key):
                    if key == 'id':
                        return self._id
                    return 'v_' + key
            if isinstance(args[5], int):
                return IdentDict(args[5])
            return [IdentDict(arg) for arg in args[5]]
        if args[4] == 'fields_get_keys':
            return ['id', 'name', 'message']
        if args[4] == 'fields_get':
            return dict.fromkeys(('id', 'name', 'message', 'spam'),
                                 {'type': sentinel.FIELD_TYPE})
        if args[4] in ('create', 'copy'):
            return sentinel.OTHER
        else:
            return [sentinel.OTHER]

    def setUp(self):
        super(TestCase, self).setUp()
        self.service.object.execute.side_effect = self.obj_exec
        self.model = self.client.model
        # preload 'foo.bar'
        self.model('foo.bar')
        self.service.reset_mock()


class TestModel(TestCase):
    """Tests the Model class and methods."""

    def test_model(self):
        # Reset cache for this test
        self.client._models.clear()

        self.assertIsNone(self.client.model('mic.mac'))
        self.assertIsNone(self.client.MicMac)
        self.assertCalls(ANY, ANY, ANY, ANY)
        self.assertIn('Model not found', self.stdout.popvalue())
        self.assertOutput('')

        self.assertIs(self.client.model('foo.bar'),
                      erppeek.Model(self.client, 'foo.bar'))
        self.assertIs(self.client.model('foo.bar'),
                      self.client.FooBar)
        self.assertCalls(
            OBJ('ir.model', 'search', [('model', 'like', 'foo.bar')]),
            OBJ('ir.model', 'read', sentinel.FOO, ('model',)),
        )
        self.assertOutput('')

    def test_keys(self):
        self.assertTrue(self.client.FooBar.keys())
        self.assertTrue(self.model('foo.bar').keys())
        self.assertCalls(OBJ('foo.bar', 'fields_get_keys'))
        self.assertOutput('')

    def test_fields(self):
        self.assertEqual(self.model('foo.bar').fields('bis'), {})
        self.assertEqual(self.model('foo.bar').fields('alp bis'), {})
        self.assertEqual(self.model('foo.bar').fields('spam bis'),
                         {'spam': {'type': sentinel.FIELD_TYPE}})
        self.assertTrue(self.model('foo.bar').fields())

        self.assertRaises(TypeError, self.model('foo.bar').fields, 42)

        self.assertCalls(OBJ('foo.bar', 'fields_get'))
        self.assertOutput('')

    def test_field(self):
        self.assertTrue(self.model('foo.bar').field('spam'))

        self.assertRaises(TypeError, self.model('foo.bar').field)

        self.assertCalls(OBJ('foo.bar', 'fields_get'))
        self.assertOutput('')

    def test_access(self):
        self.assertTrue(self.model('foo.bar').access())
        self.assertCalls(OBJ('ir.model.access', 'check', 'foo.bar', 'read'))
        self.assertOutput('')

    def test_search(self):
        FooBar = self.model('foo.bar')

        FooBar.search(['name like Morice'])
        FooBar.search(['name like Morice'], limit=2)
        FooBar.search(['name like Morice'], offset=80, limit=99)
        FooBar.search(['name like Morice'], order='name ASC')
        FooBar.search(['name = mushroom', 'state != draft'])
        FooBar.search([('name', 'like', 'Morice')])
        FooBar._execute('search', [('name like Morice')])
        FooBar.search([])
        FooBar.search()
        domain = [('name', 'like', 'Morice')]
        domain2 = [('name', '=', 'mushroom'), ('state', '!=', 'draft')]
        self.assertCalls(
            OBJ('foo.bar', 'search', domain),
            OBJ('foo.bar', 'search', domain, 0, 2, None, None),
            OBJ('foo.bar', 'search', domain, 80, 99, None, None),
            OBJ('foo.bar', 'search', domain, 0, None, 'name ASC', None),
            OBJ('foo.bar', 'search', domain2),
            OBJ('foo.bar', 'search', domain),
            OBJ('foo.bar', 'search', domain),
            OBJ('foo.bar', 'search', []),
            OBJ('foo.bar', 'search', []),
        )
        self.assertOutput('')

        # UserWarning
        warn = mock.patch('warnings.warn').start()
        FooBar.search('name like Morice')
        self.assertCalls(OBJ('foo.bar', 'search', domain))
        warn.assert_called_once_with(
            "Domain should be a list: ['name like Morice']")

        FooBar.search(['name like Morice'], missingkey=42)
        self.assertCalls(OBJ('foo.bar', 'search', domain, 0, None, None, None))
        self.assertOutput('Ignoring: missingkey = 42\n')

        self.assertRaises(ValueError, FooBar.search, ['abc'])
        self.assertRaises(ValueError, FooBar.search, ['< id'])
        self.assertRaises(ValueError, FooBar.search, ['name Morice'])

        self.assertCalls()
        self.assertOutput('')

    def test_count(self):
        FooBar = self.model('foo.bar')
        searchterm = 'name like Morice'

        FooBar.count([searchterm])
        FooBar.count(['name = mushroom', 'state != draft'])
        FooBar.count([('name', 'like', 'Morice')])
        FooBar._execute('search_count', [searchterm])
        FooBar.count([])
        FooBar.count()
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

        warn = mock.patch('warnings.warn').start()
        FooBar.count(searchterm)
        self.assertCalls(OBJ('foo.bar', 'search_count', domain))
        warn.assert_called_once_with(
            "Domain should be a list: ['name like Morice']")

        self.assertRaises(TypeError, FooBar.count,
                          [searchterm], limit=2)
        self.assertRaises(TypeError, FooBar.count,
                          [searchterm], offset=80, limit=99)
        self.assertRaises(TypeError, FooBar.count,
                          [searchterm], order='name ASC')
        self.assertRaises(ValueError, FooBar.count, ['abc'])
        self.assertRaises(ValueError, FooBar.count, ['< id'])
        self.assertRaises(ValueError, FooBar.count, ['name Morice'])

        self.assertCalls()
        self.assertOutput('')

    def test_read(self):
        FooBar = self.model('foo.bar')

        def call_read(fields=None):
            return OBJ('foo.bar', 'read', [sentinel.ID1, sentinel.ID2], fields)

        FooBar.read(42)
        FooBar.read([42])
        FooBar.read([13, 17])
        FooBar.read([42], 'first_name')
        self.assertCalls(
            OBJ('foo.bar', 'read', 42, None),
            OBJ('foo.bar', 'read', [42], None),
            OBJ('foo.bar', 'read', [13, 17], None),
            OBJ('foo.bar', 'read', [42], ['first_name']),
        )
        self.assertOutput('')

        searchterm = 'name like Morice'
        FooBar.read([searchterm])
        FooBar.read([searchterm], limit=2)
        FooBar.read([searchterm], offset=80, limit=99)
        FooBar.read([searchterm], order='name ASC')
        FooBar.read([searchterm], 'birthdate city')
        FooBar.read([searchterm], 'birthdate city', limit=2)
        FooBar.read([searchterm], limit=2, fields=['birthdate', 'city'])
        FooBar.read([searchterm], order='name ASC')
        FooBar.read(['name = mushroom', 'state != draft'])
        FooBar.read([('name', 'like', 'Morice')])
        FooBar._execute('read', [searchterm])

        rv = FooBar.read([searchterm],
                         'aaa %(birthdate)s bbb %(city)s', offset=80, limit=99)
        self.assertEqual(rv, ['aaa v_birthdate bbb v_city'] * 2)

        domain = [('name', 'like', 'Morice')]
        domain2 = [('name', '=', 'mushroom'), ('state', '!=', 'draft')]
        self.assertCalls(
            OBJ('foo.bar', 'search', domain), call_read(),
            OBJ('foo.bar', 'search', domain, 0, 2, None, None), call_read(),
            OBJ('foo.bar', 'search', domain, 80, 99, None, None), call_read(),
            OBJ('foo.bar', 'search', domain, 0, None, 'name ASC', None),
            call_read(),
            OBJ('foo.bar', 'search', domain), call_read(['birthdate', 'city']),
            OBJ('foo.bar', 'search', domain, 0, 2, None, None),
            call_read(['birthdate', 'city']),
            OBJ('foo.bar', 'search', domain, 0, 2, None, None),
            call_read(['birthdate', 'city']),
            OBJ('foo.bar', 'search', domain, 0, None, 'name ASC', None),
            call_read(),
            OBJ('foo.bar', 'search', domain2), call_read(),
            OBJ('foo.bar', 'search', domain), call_read(),
            OBJ('foo.bar', 'search', domain), call_read(),
            OBJ('foo.bar', 'search', domain, 80, 99, None, None),
            call_read(['birthdate', 'city']),
        )
        self.assertOutput('')

        warn = mock.patch('warnings.warn').start()
        FooBar.read(searchterm)
        self.assertCalls(OBJ('foo.bar', 'search', domain), call_read())
        warn.assert_called_once_with(
            "Domain should be a list: ['name like Morice']")

        FooBar.read([searchterm], missingkey=42)
        self.assertCalls(OBJ('foo.bar', 'search', domain, 0, None, None, None),
                         call_read())
        self.assertOutput('Ignoring: missingkey = 42\n')

        self.assertRaises(AssertionError, FooBar.read)
        self.assertRaises(ValueError, FooBar.read, ['abc'])
        self.assertRaises(ValueError, FooBar.read, ['< id'])
        self.assertRaises(ValueError, FooBar.read, ['name Morice'])

        self.assertCalls()
        self.assertOutput('')

    def test_browse(self):
        FooBar = self.model('foo.bar')

        def call_read(fields=None):
            return OBJ('foo.bar', 'read', [sentinel.ID1, sentinel.ID2], fields)

        self.assertIsInstance(FooBar.browse(42), erppeek.Record)
        self.assertIsInstance(FooBar.browse([42]), erppeek.RecordList)
        self.assertEqual(len(FooBar.browse([13, 17])), 2)
        self.assertCalls()
        self.assertOutput('')

        searchterm = 'name like Morice'
        self.assertIsInstance(FooBar.browse([searchterm]), erppeek.RecordList)
        FooBar.browse([searchterm], limit=2)
        FooBar.browse([searchterm], offset=80, limit=99)
        FooBar.browse([searchterm], order='name ASC')
        FooBar.browse([searchterm], limit=2)
        FooBar.browse([searchterm], order='name ASC')
        FooBar.browse(['name = mushroom', 'state != draft'])
        FooBar.browse([('name', 'like', 'Morice')])

        domain = [('name', 'like', 'Morice')]
        domain2 = [('name', '=', 'mushroom'), ('state', '!=', 'draft')]
        self.assertCalls(
            OBJ('foo.bar', 'search', domain),
            OBJ('foo.bar', 'search', domain, 0, 2, None, None),
            OBJ('foo.bar', 'search', domain, 80, 99, None, None),
            OBJ('foo.bar', 'search', domain, 0, None, 'name ASC', None),
            OBJ('foo.bar', 'search', domain, 0, 2, None, None),
            OBJ('foo.bar', 'search', domain, 0, None, 'name ASC', None),
            OBJ('foo.bar', 'search', domain2),
            OBJ('foo.bar', 'search', domain),
        )
        self.assertOutput('')

        warn = mock.patch('warnings.warn').start()
        FooBar.browse(searchterm)
        self.assertCalls(OBJ('foo.bar', 'search', domain))
        warn.assert_called_once_with(
            "Domain should be a list: ['name like Morice']")

        FooBar.browse([searchterm], limit=2, fields=['birthdate', 'city'])
        FooBar.browse([searchterm], missingkey=42)
        self.assertCalls(
            OBJ('foo.bar', 'search', domain, 0, 2, None, None),
            OBJ('foo.bar', 'search', domain, 0, None, None, None))
        self.assertOutput("Ignoring: fields = ['birthdate', 'city']\n"
                          "Ignoring: missingkey = 42\n")

        self.assertRaises(TypeError, FooBar.browse)
        self.assertRaises(ValueError, FooBar.browse, ['abc'])
        self.assertRaises(ValueError, FooBar.browse, ['< id'])
        self.assertRaises(ValueError, FooBar.browse, ['name Morice'])

        self.assertCalls()
        self.assertOutput('')

    def test_method(self, method_name='method', single_id=True):
        FooBar = self.model('foo.bar')
        FooBar_method = getattr(FooBar, method_name)

        single_id = single_id and 42 or [42]

        FooBar_method(42)
        FooBar_method([42])
        FooBar_method([13, 17])
        FooBar._execute(method_name, [42])
        FooBar_method([])
        self.assertCalls(
            OBJ('foo.bar', method_name, single_id),
            OBJ('foo.bar', method_name, [42]),
            OBJ('foo.bar', method_name, [13, 17]),
            OBJ('foo.bar', method_name, [42]),
            OBJ('foo.bar', method_name, []),
        )
        self.assertOutput('')

    def test_standard_methods(self):
        for method in 'write create copy unlink'.split():
            self.test_method(method)

        self.test_method('perm_read', single_id=False)


class TestRecord(TestCase):
    """Tests the Model class and methods."""

    def test_read(self):
        records = self.model('foo.bar').browse([13, 17])
        rec = self.model('foo.bar').browse(42)

        self.assertIsInstance(records, erppeek.RecordList)
        self.assertIsInstance(rec, erppeek.Record)

        rec.read()
        records.read()
        rec.read('message')
        records.read('message')
        rec.read('name message')
        records.read('birthdate city')

        self.assertCalls(
            OBJ('foo.bar', 'read', 42, None),
            OBJ('foo.bar', 'read', [13, 17], None),
            OBJ('foo.bar', 'read', 42, ['message']),
            OBJ('foo.bar', 'read', [13, 17], ['message']),
            OBJ('foo.bar', 'fields_get'),
            OBJ('foo.bar', 'read', 42, ['name', 'message']),
            OBJ('foo.bar', 'read', [13, 17], ['birthdate', 'city']),
        )
        self.assertOutput('')

    def test_method(self, method_name='method'):
        records = self.model('foo.bar').browse([13, 17])
        rec = self.model('foo.bar').browse(42)
        records_method = getattr(records, method_name)
        rec_method = getattr(rec, method_name)

        records_method()
        rec_method()
        self.assertCalls(
            OBJ('foo.bar', 'fields_get_keys'),
            OBJ('foo.bar', method_name, [13, 17]),
            OBJ('foo.bar', method_name, [42]),
        )
        self.assertOutput('')

    def test_standard_methods(self):
        # write copy
        self.test_method('unlink')
        del self.model('foo.bar')._keys
        self.test_method('perm_read')

    def test_empty_recordlist(self):
        records = self.model('foo.bar').browse([13, 17])
        empty = records[42:]

        self.assertIsInstance(records, erppeek.RecordList)
        self.assertTrue(records)
        self.assertEqual(len(records), 2)
        self.assertEqual(records.name, ['v_name'] * 2)

        self.assertIsInstance(empty, erppeek.RecordList)
        self.assertFalse(empty)
        self.assertEqual(len(empty), 0)
        self.assertEqual(empty.name, [])

        self.assertCalls(
            OBJ('foo.bar', 'fields_get_keys'),
            OBJ('foo.bar', 'read', [13, 17], ['name']),
            OBJ('foo.bar', 'fields_get'),
        )
        self.assertOutput('')

    def test_attr(self):
        records = self.model('foo.bar').browse([13, 17])
        rec = self.model('foo.bar').browse(42)

        # existing fields can be read as attributes
        # attribute is writable on the Record object only
        self.assertFalse(callable(rec.message))
        rec.message = 'one giant leap for mankind'
        self.assertFalse(callable(rec.message))
        self.assertEqual(records.message, ['v_message', 'v_message'])

        # if the attribute is not a field, it could be a specific RPC method
        self.assertEqual(rec.missingattr(), sentinel.OTHER)
        self.assertEqual(records.missingattr(), [sentinel.OTHER])

        self.assertCalls(
            OBJ('foo.bar', 'fields_get_keys'),
            OBJ('foo.bar', 'read', 42, ['message']),
            OBJ('foo.bar', 'write', [42], {'message': 'one giant leap for mankind'}),
            OBJ('foo.bar', 'read', 42, ['message']),
            OBJ('foo.bar', 'read', [13, 17], ['message']),
            OBJ('foo.bar', 'fields_get'),
            OBJ('foo.bar', 'missingattr', [42]),
            OBJ('foo.bar', 'missingattr', [13, 17]),
        )

        # `setattr` not allowed (except for existing fields on Record object)
        self.assertRaises(AttributeError, setattr, rec, 'missingattr', 42)
        self.assertRaises(AttributeError, setattr, records, 'message', 'one')
        self.assertRaises(AttributeError, setattr, records, 'missingattr', 42)

        # method can be forgotten (any use case?)
        del rec.missingattr, records.missingattr

        # `del` not allowed for attributes or missing attr
        self.assertRaises(AttributeError, delattr, rec, 'message')
        self.assertRaises(AttributeError, delattr, records, 'message')
        self.assertRaises(AttributeError, delattr, rec, 'missingattr2')
        self.assertRaises(AttributeError, delattr, records, 'missingattr2')

        self.assertCalls()
        self.assertOutput('')
