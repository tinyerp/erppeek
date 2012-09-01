# -*- coding: utf-8 -*-
import unittest2
import mock
from mock import call, sentinel

import erppeek

type_call = type(call)


try:
    basestring
except NameError:
    basestring = str


def callable(f):
    return hasattr(f, '__call__')


class PseudoFile(list):
    write = list.append

    def popvalue(self):
        rv = ''.join(self)
        del self[:]
        return rv


def OBJ(*args):
    return ('object.execute', sentinel.AUTH) + args


class XmlRpcTestCase(unittest2.TestCase):
    server_version = None
    server = None
    database = user = password = uid = None

    def setUp(self):
        self.maxDiff = 4096     # instead of 640
        self.addCleanup(mock.patch.stopall)
        self.stdout = mock.patch('sys.stdout', new=PseudoFile()).start()
        self.stderr = mock.patch('sys.stderr', new=PseudoFile()).start()

        # Clear the login cache
        mock.patch.dict('erppeek.Client._login.cache', clear=True).start()

        self.service = self._patch_service()
        if self.server and self.database:
            # create the client
            self.client = erppeek.Client(
                self.server, self.database, self.user, self.password)
            # reset the mock
            self.service.reset_mock()

    def _patch_service(self):
        def get_svc(server, name, *args, **kwargs):
            return getattr(svcs, name)
        patcher = mock.patch('erppeek.Service', side_effect=get_svc)
        svcs = patcher.start()
        svcs.stop = patcher.stop
        for svc_name in 'db common object wizard report'.split():
            svcs.attach_mock(mock.Mock(name=svc_name), svc_name)
        # Default values
        svcs.db.server_version.return_value = self.server_version
        svcs.db.list.return_value = [self.database]
        svcs.common.login.return_value = self.uid
        return svcs

    def assertCalls(self, *expected_args):
        expected_calls = []
        for expected in expected_args:
            if isinstance(expected, basestring):
                if expected[:4] == 'call':
                    expected = expected[4:].lstrip('.')
                assert expected[-2:] != '()'
                expected = type_call((expected,))
            elif not (expected is mock.ANY or isinstance(expected, type_call)):
                rpcmethod = expected[0]
                if len(expected) > 1 and expected[1] == sentinel.AUTH:
                    args = (self.database, self.uid, self.password)
                    args += expected[2:]
                else:
                    args = expected[1:]
                expected = getattr(call, rpcmethod)(*args)
            expected_calls.append(expected)
        mock_calls = self.service.mock_calls
        self.assertSequenceEqual(mock_calls, expected_calls)
        # Reset
        self.service.reset_mock()

    def assertOutput(self, stdout='', stderr=''):
        # compare with ANY to make sure output is not empty
        if stderr is mock.ANY:
            self.assertTrue(self.stderr.popvalue())
        else:
            self.assertMultiLineEqual(self.stderr.popvalue(), stderr)
        if stdout is mock.ANY:
            self.assertTrue(self.stdout.popvalue())
        else:
            self.assertMultiLineEqual(self.stdout.popvalue(), stdout)
