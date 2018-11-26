==========================================================
ERPpeek, a versatile tool for browsing Odoo / OpenERP data
==========================================================

Download and install the latest release::

    pip install -U erppeek

.. contents::
   :local:
   :backlinks: top

Documentation and tutorial: http://erppeek.readthedocs.org

CI tests: https://travis-ci.org/tinyerp/erppeek


Overview
--------

ERPpeek carries three completing uses:

(1) with command line arguments
(2) as an interactive shell
(3) as a client library


Key features:

- single executable ``erppeek.py``, no external dependency
- wrappers for ``search+read``, for data model introspection, etc...
- simpler syntax for ``domain`` and ``fields``
- full API accessible on the ``Client`` object for OpenERP 5.0 through Odoo 11.0
- the module can be imported and used as a library: ``from erppeek import Client``
- supports Python 3 and Python 2.7



.. _command-line:

Command line arguments
----------------------

There are few arguments to query Odoo models from the command line.
Although it is quite limited::

    $ erppeek --help
    Usage: erppeek [options] [search_term_or_id [search_term_or_id ...]]

    Inspect data on Odoo objects.  Use interactively or query a model (-m)
    and pass search terms or ids as positional parameters after the options.

    Options:
      --version             show program's version number and exit
      -h, --help            show this help message and exit
      -l, --list            list sections of the configuration
      --env=ENV             read connection settings from the given section
      -c CONFIG, --config=CONFIG
                            specify alternate config file (default: 'erppeek.ini')
      --server=SERVER       full URL of the server (default: http://localhost:8069/xmlrpc)
      -d DB, --db=DB        database
      -u USER, --user=USER  username
      -p PASSWORD, --password=PASSWORD
                            password, or it will be requested on login
      -m MODEL, --model=MODEL
                            the type of object to find
      -f FIELDS, --fields=FIELDS
                            restrict the output to certain fields (multiple allowed)
      -i, --interact        use interactively; default when no model is queried
      -v, --verbose         verbose
    $ #


Example::

    $ erppeek -d demo -m res.partner -f name -f lang 1
    "name","lang"
    "Your Company","en_US"

::

    $ erppeek -d demo -m res.groups -f full_name 'id > 0'
    "full_name"
    "Administration / Access Rights"
    "Administration / Configuration"
    "Human Resources / Employee"
    "Usability / Multi Companies"
    "Usability / Extended View"
    "Usability / Technical Features"
    "Sales Management / User"
    "Sales Management / Manager"
    "Partner Manager"



.. _interactive-mode:

Interactive use
---------------

Edit ``erppeek.ini`` and declare the environment(s)::

    [DEFAULT]
    scheme = http
    host = localhost
    port = 8069
    database = odoo
    username = admin

    [demo]
    username = demo
    password = demo
    protocol = xmlrpc

    [demo_jsonrpc]
    username = demo
    password = demo
    protocol = jsonrpc

    [local]
    scheme = local
    options = -c /path/to/odoo-server.conf --without-demo all


Connect to the Odoo server::

    erppeek --list
    erppeek --env demo


This is a sample session::

    >>> model('res.users')
    <Model 'res.users'>
    >>> model('res.users').count()
    4
    >>> model('ir.cron').read(['active = False'], 'active function')
    [{'active': False, 'function': 'run_mail_scheduler', 'id': 1},
     {'active': False, 'function': 'run_bdr_scheduler', 'id': 2},
     {'active': False, 'function': 'scheduled_fetch_new_scans', 'id': 9}]
    >>> #
    >>> client.modules('delivery')
    {'uninstalled': ['delivery', 'sale_delivery_report']}
    >>> client.upgrade('base')
    1 module(s) selected
    42 module(s) to process:
      to upgrade    account
      to upgrade    account_chart
      to upgrade    account_tax_include
      to upgrade    base
      ...
    >>> #


.. note::

   Use the ``--verbose`` switch to see what happens behind the scene.
   Lines are truncated at 79 chars.  Use ``-vv`` or ``-vvv`` to print
   more.


.. note::

   To preserve the history of commands when closing the session, first
   create an empty file in your home directory:
   ``touch ~/.erppeek_history``
