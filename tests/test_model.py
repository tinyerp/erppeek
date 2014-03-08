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
        (model, method) = args[3:5]
        if method == 'search':
            if model.startswith('ir.model') and 'foo' in str(args[5]):
                return sentinel.FOO
            if args[5] == [('name', '=', 'Morice')]:
                return [1003]
            if 'missing' in str(args[5]):
                return []
            return [1001, 1002]
        if method == 'read':
            if args[5] is sentinel.FOO:
                if model == 'ir.model.data':
                    return [{'model': 'foo.bar', 'id': 1733, 'res_id': 42}]
                return [{'model': 'foo.bar', 'id': 371},
                        {'model': 'foo.other', 'id': 99},
                        {'model': 'ir.model.data', 'id': 17}]

            # We no longer read single ids
            self.assertIsInstance(args[5], list)

            class IdentDict(dict):
                def __init__(self, id_, fields=()):
                    self['id'] = id_
                    for f in fields:
                        self[f] = self[f]

                def __getitem__(self, key):
                    if key in self:
                        return dict.__getitem__(self, key)
                    return 'v_' + key
            if model == 'foo.bar' and args[6] is None:
                records = {}
                for res_id in set(args[5]):
                    rdic = IdentDict(res_id, ('name', 'message', 'spam'))
                    rdic['misc_id'] = 421
                    records[res_id] = rdic
                return [records[res_id] for res_id in args[5]]
            return [IdentDict(arg, args[6]) for arg in args[5]]
        if method == 'fields_get_keys':
            return ['id', 'name', 'message', 'misc_id']
        if method == 'fields_get':
            fields = dict.fromkeys(('id', 'name', 'message', 'spam',
                                    'birthdate', 'city'),
                                   {'type': sentinel.FIELD_TYPE})
            fields['misc_id'] = {'type': 'many2one', 'relation': 'foo.misc'}
            return fields
        if method in ('create', 'copy'):
            return 1999
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
            return OBJ('foo.bar', 'read', [1001, 1002], fields)

        FooBar.read(42)
        FooBar.read([42])
        FooBar.read([13, 17])
        FooBar.read([42], 'first_name')
        self.assertCalls(
            OBJ('foo.bar', 'read', [42], None),
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

    def test_get(self):
        FooBar = self.model('foo.bar')

        self.assertIsInstance(FooBar.get(42), erppeek.Record)
        self.assertCalls()
        self.assertOutput('')

        self.assertIsInstance(FooBar.get(['name = Morice']), erppeek.Record)
        self.assertIsNone(FooBar.get(['name = Blinky', 'missing = False']))

        # domain matches too many records (2)
        self.assertRaises(ValueError, FooBar.get, ['name like Morice'])

        self.assertCalls(
            OBJ('foo.bar', 'search', [('name', '=', 'Morice')], 0, None, None, None),
            OBJ('foo.bar', 'search', [('name', '=', 'Blinky'), ('missing', '=', False)], 0, None, None, None),
            OBJ('foo.bar', 'search', [('name', 'like', 'Morice')], 0, None, None, None),
        )
        self.assertOutput('')

        self.assertRaises(ValueError, FooBar.get, 'name = Morice')
        self.assertRaises(ValueError, FooBar.get, ['abc'])
        self.assertRaises(ValueError, FooBar.get, ['< id'])
        self.assertRaises(ValueError, FooBar.get, ['name Morice'])

        self.assertRaises(TypeError, FooBar.get)
        self.assertRaises(TypeError, FooBar.get, ['name = Morice'], limit=1)

        self.assertRaises(AssertionError, FooBar.get, [42])
        self.assertRaises(AssertionError, FooBar.get, [13, 17])

        self.assertCalls()
        self.assertOutput('')

    def test_get_xml_id(self):
        FooBar = self.model('foo.bar')
        BabarFoo = self.model('babar.foo', check=False)
        self.assertIsInstance(BabarFoo, erppeek.Model)

        self.assertIsNone(FooBar.get('base.missing_company'))
        self.assertIsInstance(FooBar.get('base.foo_company'), erppeek.Record)

        # model mismatch
        self.assertRaises(AssertionError, BabarFoo.get, 'base.foo_company')

        self.assertCalls(
            OBJ('ir.model.data', 'search', [('module', '=', 'base'), ('name', '=', 'missing_company')]),
            OBJ('ir.model.data', 'search', [('module', '=', 'base'), ('name', '=', 'foo_company')]),
            OBJ('ir.model.data', 'read', sentinel.FOO, ['model', 'res_id']),
            OBJ('ir.model.data', 'search', [('module', '=', 'base'), ('name', '=', 'foo_company')]),
            OBJ('ir.model.data', 'read', sentinel.FOO, ['model', 'res_id']),
        )

        self.assertOutput('')

    def test_create(self):
        FooBar = self.model('foo.bar')

        record42 = FooBar.browse(42)
        recordlist42 = FooBar.browse([4, 2])

        FooBar.create({'spam': 42})
        FooBar.create({'spam': record42})
        FooBar.create({'spam': recordlist42})
        FooBar._execute('create', {'spam': 42})
        FooBar.create({})
        self.assertCalls(
            OBJ('foo.bar', 'fields_get'),
            OBJ('foo.bar', 'create', {'spam': 42}),
            OBJ('foo.bar', 'create', {'spam': 42}),
            OBJ('foo.bar', 'create', {'spam': [4, 2]}),
            OBJ('foo.bar', 'create', {'spam': 42}),
            OBJ('foo.bar', 'create', {}),
        )
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
        for method in 'write', 'copy', 'unlink':
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
            OBJ('foo.bar', 'read', [42], None),
            OBJ('foo.bar', 'fields_get'),
            OBJ('foo.bar', 'read', [13, 17], None),
            OBJ('foo.bar', 'read', [42], ['message']),
            OBJ('foo.bar', 'read', [13, 17], ['message']),
            OBJ('foo.bar', 'read', [42], ['name', 'message']),
            OBJ('foo.bar', 'read', [13, 17], ['birthdate', 'city']),
        )
        self.assertOutput('')

    def test_write(self):
        records = self.model('foo.bar').browse([13, 17])
        rec = self.model('foo.bar').browse(42)

        rec.write({})
        rec.write({'spam': 42})
        rec.write({'spam': rec})
        rec.write({'spam': records})
        records.write({})
        records.write({'spam': 42})
        records.write({'spam': rec})
        records.write({'spam': records})
        self.assertCalls(
            OBJ('foo.bar', 'write', [42], {}),
            OBJ('foo.bar', 'fields_get'),
            OBJ('foo.bar', 'write', [42], {'spam': 42}),
            OBJ('foo.bar', 'write', [42], {'spam': 42}),
            OBJ('foo.bar', 'write', [42], {'spam': [13, 17]}),
            OBJ('foo.bar', 'write', [13, 17], {}),
            OBJ('foo.bar', 'write', [13, 17], {'spam': 42}),
            OBJ('foo.bar', 'write', [13, 17], {'spam': 42}),
            OBJ('foo.bar', 'write', [13, 17], {'spam': [13, 17]}),
        )
        self.assertOutput('')

    def test_copy(self):
        rec = self.model('foo.bar').browse(42)
        records = self.model('foo.bar').browse([13, 17])

        recopy = rec.copy()
        self.assertIsInstance(recopy, erppeek.Record)
        self.assertEqual(recopy.id, 1999)

        rec.copy({'spam': 42})
        rec.copy({'spam': rec})
        rec.copy({'spam': records})
        rec.copy({})
        self.assertCalls(
            OBJ('foo.bar', 'copy', 42, None),
            OBJ('foo.bar', 'fields_get'),
            OBJ('foo.bar', 'copy', 42, {'spam': 42}),
            OBJ('foo.bar', 'copy', 42, {'spam': 42}),
            OBJ('foo.bar', 'copy', 42, {'spam': [13, 17]}),
            OBJ('foo.bar', 'copy', 42, {}),
        )
        self.assertOutput('')

    def test_unlink(self):
        records = self.model('foo.bar').browse([13, 17])
        rec = self.model('foo.bar').browse(42)

        records.unlink()
        rec.unlink()
        self.assertCalls(
            OBJ('foo.bar', 'unlink', [13, 17]),
            OBJ('foo.bar', 'unlink', [42]),
        )
        self.assertOutput('')

    def test_perm_read(self):
        records = self.model('foo.bar').browse([13, 17])
        rec = self.model('foo.bar').browse(42)

        records.perm_read()
        rec.perm_read()
        self.assertCalls(
            OBJ('foo.bar', 'fields_get_keys'),
            OBJ('foo.bar', 'perm_read', [13, 17]),
            OBJ('foo.bar', 'perm_read', [42]),
        )
        self.assertOutput('')

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

        # Calling methods on empty RecordList
        self.assertEqual(empty.read(), [])
        self.assertIs(empty.write({'spam': 'ham'}), True)
        self.assertIs(empty.unlink(), True)
        self.assertCalls()

        self.assertEqual(empty.method(), [sentinel.OTHER])
        self.assertCalls(
            OBJ('foo.bar', 'method', []),
        )
        self.assertOutput('')

    def test_attr(self):
        records = self.model('foo.bar').browse([13, 17])
        rec = self.model('foo.bar').browse(42)

        # attribute "id" is always present
        self.assertEqual(rec.id, 42)
        self.assertEqual(records.id, [13, 17])

        # if the attribute is not a field, it could be a specific RPC method
        self.assertEqual(rec.missingattr(), sentinel.OTHER)
        self.assertEqual(records.missingattr(), [sentinel.OTHER])

        # existing fields can be read as attributes
        # attribute is writable on the Record object only
        self.assertFalse(callable(rec.message))
        rec.message = 'one giant leap for mankind'
        self.assertFalse(callable(rec.message))
        self.assertEqual(records.message, ['v_message', 'v_message'])

        self.assertCalls(
            OBJ('foo.bar', 'fields_get_keys'),
            OBJ('foo.bar', 'missingattr', [42]),
            OBJ('foo.bar', 'missingattr', [13, 17]),
            OBJ('foo.bar', 'read', [42], ['message']),
            OBJ('foo.bar', 'fields_get'),
            OBJ('foo.bar', 'write', [42], {'message': 'one giant leap for mankind'}),
            OBJ('foo.bar', 'read', [42], ['message']),
            OBJ('foo.bar', 'read', [13, 17], ['message']),
        )

        # attribute "id" is never writable
        self.assertRaises(AttributeError, setattr, rec, 'id', 42)
        self.assertRaises(AttributeError, setattr, records, 'id', 42)

        # `setattr` not allowed (except for existing fields on Record object)
        self.assertRaises(AttributeError, setattr, rec, 'missingattr', 42)
        self.assertRaises(AttributeError, setattr, records, 'message', 'one')
        self.assertRaises(AttributeError, setattr, records, 'missingattr', 42)

        # method can be forgotten (any use case?)
        del rec.missingattr, records.missingattr
        # Single attribute can be deleted from cache
        del rec.message

        # `del` not allowed for attributes or missing attr
        self.assertRaises(AttributeError, delattr, rec, 'missingattr2')
        self.assertRaises(AttributeError, delattr, records, 'message')
        self.assertRaises(AttributeError, delattr, records, 'missingattr2')

        self.assertCalls()
        self.assertOutput('')

    def test_equal(self):
        rec1 = self.model('foo.bar').get(42)
        rec2 = self.model('foo.bar').get(42)
        rec3 = self.model('foo.bar').get(2)
        rec4 = self.model('foo.other').get(42)
        records = self.model('foo.bar').browse([42])

        self.assertEqual(rec1.id, rec2.id)
        self.assertEqual(rec1, rec2)

        self.assertNotEqual(rec1.id, rec3.id)
        self.assertEqual(rec1.id, rec4.id)
        self.assertNotEqual(rec1, rec3)
        self.assertNotEqual(rec1, rec4)

        self.assertEqual(records.id, [42])
        self.assertNotEqual(rec1, records)

        self.assertCalls()
        self.assertOutput('')

    def test_read_duplicate(self):
        records = self.model('foo.bar').browse([17, 17])

        self.assertEqual(type(records), erppeek.RecordList)

        values = records.read()
        self.assertEqual(len(values), 2)
        self.assertEqual(*values)
        self.assertEqual(type(values[0]['misc_id']), erppeek.Record)

        values = records.read('message')
        self.assertEqual(values, ['v_message','v_message'])

        values = records.read('birthdate city')
        self.assertEqual(len(values), 2)
        self.assertEqual(*values)
        self.assertEqual(values[0], {'id': 17, 'city': 'v_city',
                                     'birthdate': 'v_birthdate'})

        self.assertCalls(
            OBJ('foo.bar', 'read', [17], None),
            OBJ('foo.bar', 'fields_get'),
            OBJ('foo.bar', 'read', [17], ['message']),
            OBJ('foo.bar', 'read', [17], ['birthdate', 'city']),
        )
        self.assertOutput('')
