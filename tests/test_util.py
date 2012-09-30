# -*- coding: utf-8 -*-
from __future__ import with_statement

import unittest2
import mock

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
        self.assertTrue(issearchdomain('state != draft'))
        self.assertTrue(issearchdomain(('state', '!=', 'draft')))

    def test_searchargs(self):
        domain = [('name', '=', 'mushroom'), ('state', '!=', 'draft')]

        self.assertEqual(searchargs(([],)), ([],))
        self.assertEqual(searchargs((domain,)), (domain,))
        self.assertEqual(searchargs((['name = mushroom', 'state != draft'],)),
                         (domain,))

        with mock.patch('warnings.warn') as mock_warn:
            self.assertEqual(searchargs(('state != draft',)),
                             ([('state', '!=', 'draft')],))
            mock_warn.assert_called_once_with(
                "Domain should be a list: ['state != draft']")
            mock_warn.reset_mock()
            self.assertEqual(searchargs((('state', '!=', 'draft'),)),
                             ([('state', '!=', 'draft')],))
            mock_warn.assert_called_once_with(
                "Domain should be a list: [('state', '!=', 'draft')]")

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

        self.assertRaises(ValueError, searchargs, (['spam.hamin(1, 2)'],))
        self.assertRaises(ValueError, searchargs, (['spam.hamin (1, 2)'],))
        self.assertRaises(ValueError, searchargs, (['spamin (1, 2)'],))
        self.assertRaises(ValueError, searchargs, (['[id = 1540]'],))
