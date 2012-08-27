# -*- coding: utf-8 -*-
import sys

import mock
from mock import call, ANY

import erppeek
from ._common import XmlRpcTestCase


class TestInteract(XmlRpcTestCase):
    server_version = '6.1'
    startup_calls = (
        call(ANY, 'db', ANY, verbose=ANY),
        'db.server_version',
        call(ANY, 'db', ANY, verbose=ANY),
        call(ANY, 'common', ANY, verbose=ANY),
        call(ANY, 'object', ANY, verbose=ANY),
        call(ANY, 'wizard', ANY, verbose=ANY),
        call(ANY, 'report', ANY, verbose=ANY),
        'db.list',
    )

    def setUp(self):
        super(TestInteract, self).setUp()
        # Preserve this special attributes
        mock.patch('erppeek._interact', wraps=erppeek._interact).start()
        mock.patch('erppeek.Client._set_interactive', wraps=erppeek.Client._set_interactive).start()
        self.infunc = mock.patch('code.InteractiveConsole.raw_input').start()

    def test_main(self):
        env_tuple = ('http://127.0.0.1:8069', 'database', 'usr', None)
        mock.patch('sys.argv', new=['erppeek', '--env', 'demo']).start()
        read_config = mock.patch('erppeek.read_config',
                                 return_value=env_tuple).start()
        getpass = mock.patch('getpass.getpass',
                             return_value='password').start()
        self.service.db.list.return_value = ['database']
        self.service.common.login.return_value = 17
        self.service.object.execute.side_effect = TypeError
        self.infunc.side_effect = [
            "client\n",
            "read\n",
            "client.login('gaspard')\n",
            "23 + 19\n",
            EOFError('Finished')]

        # Launch interactive
        erppeek.main()

        self.assertEqual(sys.ps1, 'demo >>> ')
        self.assertEqual(sys.ps2, 'demo ... ')
        expected_calls = self.startup_calls + (
            ('common.login', 'database', 'usr', 'password'),
            ('object.execute', 'database', 17, 'password',
             'ir.model.access', 'check', 'res.users', 'write'),
            ('common.login', 'database', 'gaspard', 'password'),
        )
        self.assertCalls(*expected_calls)
        self.assertEqual(getpass.call_count, 2)
        self.assertEqual(read_config.call_count, 1)
        outlines = self.stdout.popvalue().splitlines()
        self.assertSequenceEqual(outlines[-5:], [
            "Logged in as 'usr'",
            "<Client 'http://127.0.0.1:8069#database'>",
            "<bound method Client.read of "
            "<Client 'http://127.0.0.1:8069#database'>>",
            "Logged in as 'gaspard'",
            "42",
        ])
        self.assertOutput(stderr='\x1b[A\n\n')
