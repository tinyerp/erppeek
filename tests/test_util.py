# -*- coding: utf-8 -*-
import unittest2

from erppeek import issearchdomain, searchargs


class TestUtils(unittest2.TestCase):

    def test_issearchdomain(self):
        self.assertFalse(issearchdomain(None))
        self.assertFalse(issearchdomain(42))
        self.assertFalse(issearchdomain('42'))
        self.assertFalse(issearchdomain([1, 42]))
        self.assertFalse(issearchdomain(['1', '42']))

        self.assertTrue(issearchdomain([('name', '=', 'mushroom'),
                                        ('state', '!=', 'draft')]))
        self.assertTrue(issearchdomain(['name = mushroom', 'state != draft']))
        self.assertTrue(issearchdomain([]))

        # Removed with 1.6
        self.assertFalse(issearchdomain('state != draft'))
        self.assertFalse(issearchdomain(('state', '!=', 'draft')))

    def test_searchargs(self):
        domain = [('name', '=', 'mushroom'), ('state', '!=', 'draft')]

        self.assertEqual(searchargs(([],)), ([],))
        self.assertEqual(searchargs((domain,)), (domain,))
        self.assertEqual(searchargs((['name = mushroom', 'state != draft'],)),
                         (domain,))

        self.assertEqual(searchargs((['status=Running'],)),
                         ([('status', '=', 'Running')],))
        self.assertEqual(searchargs((['state="in_use"'],)),
                         ([('state', '=', 'in_use')],))
        self.assertEqual(searchargs((['spam.ham in(1, 2)'],)),
                         ([('spam.ham', 'in', (1, 2))],))
        self.assertEqual(searchargs((['spam in(1, 2)'],)),
                         ([('spam', 'in', (1, 2))],))

        # Standard comparison operators
        self.assertEqual(searchargs((['ham=2'],)), ([('ham', '=', 2)],))
        self.assertEqual(searchargs((['ham!=2'],)), ([('ham', '!=', 2)],))
        self.assertEqual(searchargs((['ham>2'],)), ([('ham', '>', 2)],))
        self.assertEqual(searchargs((['ham>=2'],)), ([('ham', '>=', 2)],))
        self.assertEqual(searchargs((['ham<2'],)), ([('ham', '<', 2)],))
        self.assertEqual(searchargs((['ham<=2'],)), ([('ham', '<=', 2)],))

        # Operators rarely used
        self.assertEqual(searchargs((['status =like Running'],)),
                         ([('status', '=like', 'Running')],))
        self.assertEqual(searchargs((['status=like Running'],)),
                         ([('status', '=like', 'Running')],))
        self.assertEqual(searchargs((['status =ilike Running'],)),
                         ([('status', '=ilike', 'Running')],))
        self.assertEqual(searchargs((['status =? Running'],)),
                         ([('status', '=?', 'Running')],))
        self.assertEqual(searchargs((['status=?Running'],)),
                         ([('status', '=?', 'Running')],))

    def test_searchargs_date(self):
        # Do not interpret dates as integers
        self.assertEqual(searchargs((['create_date > "2001-12-31"'],)),
                         ([('create_date', '>', '2001-12-31')],))
        self.assertEqual(searchargs((['create_date > 2001-12-31'],)),
                         ([('create_date', '>', '2001-12-31')],))

        self.assertEqual(searchargs((['create_date > 2001-12-31 23:59:00'],)),
                         ([('create_date', '>', '2001-12-31 23:59:00')],))

        # Not a date, but it should be parsed as string too
        self.assertEqual(searchargs((['port_nr != 122-2'],)),
                         ([('port_nr', '!=', '122-2')],))

    def test_searchargs_digits(self):
        # Do not convert digits to octal
        self.assertEqual(searchargs((['code = 042'],)), ([('code', '=', '042')],))
        self.assertEqual(searchargs((['code > 042'],)), ([('code', '>', '042')],))
        self.assertEqual(searchargs((['code > 420'],)), ([('code', '>', 420)],))

        # Standard octal notation is supported
        self.assertEqual(searchargs((['code = 0o42'],)), ([('code', '=', 34)],))

        # Other numeric literals are still supported
        self.assertEqual(searchargs((['duration = 0'],)), ([('duration', '=', 0)],))
        self.assertEqual(searchargs((['price < 0.42'],)), ([('price', '<', 0.42)],))

        # Overflow for integers, not for float
        self.assertEqual(searchargs((['phone = 41261234567'],)),
                         ([('phone', '=', '41261234567')],))
        self.assertEqual(searchargs((['elapsed = 67891234567.0'],)),
                         ([('elapsed', '=', 67891234567.0)],))

    def test_searchargs_invalid(self):

        # No longer recognized as a search domain, since 1.6
        self.assertEqual(searchargs(('state != draft',)), ('state != draft',))
        self.assertEqual(searchargs((('state', '!=', 'draft'),)),
                         (('state', '!=', 'draft'),))

        # Operator == is a typo
        self.assertRaises(ValueError, searchargs, (['ham==2'],))
        self.assertRaises(ValueError, searchargs, (['ham == 2'],))

        self.assertRaises(ValueError, searchargs, (['spam.hamin(1, 2)'],))
        self.assertRaises(ValueError, searchargs, (['spam.hamin (1, 2)'],))
        self.assertRaises(ValueError, searchargs, (['spamin (1, 2)'],))
        self.assertRaises(ValueError, searchargs, (['[id = 1540]'],))
