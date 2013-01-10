===================================================
ERPpeek, a versatile tool for browsing OpenERP data
===================================================

Download and install the latest release::

    pip install -U erppeek

.. contents::
   :local:
   :backlinks: top

Documentation and tutorial: http://erppeek.readthedocs.org


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
- full API accessible on the ``Client`` object for OpenERP 5.0 through 7.0
- the module can be imported and used as a library: ``from erppeek import Client``
- supports Python 3 and Python 2 (>= 2.5)



.. _command-line:

Command line arguments
----------------------

There are few arguments to query OpenERP models from the command line.
Although it is quite limited::

    $ erppeek --help
    Usage: erppeek [options] [search_term_or_id [search_term_or_id ...]]

    Inspect data on OpenERP objects.  Use interactively or query a model (-m)
    and pass search terms or ids as positional parameters after the options.

    Options:
      --version             show program\'s version number and exit
      -h, --help            show this help message and exit
      -l, --list            list sections of the configuration
      --env=ENV             read connection settings from the given section
      -c CONFIG, --config=CONFIG
                            specify alternate config file (default: 'erppeek.ini')
      --server=SERVER       full URL to the XML-RPC server (default: http://localhost:8069)
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
    [{'id': 1, 'lang': 'en_US', 'name': 'Your Company'}]

::

    $ erppeek -d demo -m res.groups -f full_name 'id > 0'
    [{'full_name': 'Administration / Access Rights', 'id': 1},
     {'full_name': 'Administration / Configuration', 'id': 2},
     {'full_name': 'Human Resources / Employee', 'id': 3},
     {'full_name': 'Usability / Multi Companies', 'id': 4},
     {'full_name': 'Usability / Extended View', 'id': 5},
     {'full_name': 'Usability / Technical Features', 'id': 6},
     {'full_name': 'Sales Management / User', 'id': 7},
     {'full_name': 'Sales Management / Manager', 'id': 8},
     {'full_name': 'Partner Manager', 'id': 9}]



.. _interactive-mode:

Interactive use
---------------

Edit ``erppeek.ini`` and declare the environment(s)::

    [DEFAULT]
    scheme = http
    host = localhost
    port = 8069
    database = openerp
    username = admin
    options = -c /path/to/openerp-server.conf --without-demo all

    [demo]
    username = demo
    password = demo

    [local]
    scheme = local


Connect to the OpenERP server::

    erppeek --list
    erppeek --env demo


This is a sample session::

    >>> model('res.users')
    <Model 'res.users'>
    >>> client.ResUsers is model('res.users')
    True
    >>> client.ResUsers.count()
    4
    >>> read('ir.cron', ['active = False'], 'active function')
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
