===================================================
ERPpeek, a versatile tool for browsing OpenERP data
===================================================

Download the `latest release <http://pypi.python.org/pypi/ERPpeek>`__ from PyPI::

    pip install erppeek

.. contents::


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
- full API accessible on the ``Client`` object for OpenERP 5.0 through 6.1
- the module can be imported and used as a library: ``from erppeek import Client``
- supports Python 3 and Python 2 (>= 2.5)


1. Command line arguments
-------------------------

See the `introduction on this page
<http://www.theopensourcerer.com/2011/12/13/erppeek-a-tool-for-browsing-openerp-data-from-the-command-line/>`__
or::

    erppeek --help


2. Interactive use
------------------

Edit ``erppeek.ini`` and declare the environment(s)::

   [DEFAULT]
   host = localhost
   port = 8069
   database = openerp
   username = admin

   [demo]
   username = demo
   password = demo


Connect to the OpenERP server::

    erppeek --list
    erppeek --env demo


This is a sample session::

    demo >>> model('users')
    ['res.users']
    demo >>> count('res.users')
    4
    demo >>> read('ir.cron', ['active = False'], 'active function')
    [{'active': False, 'function': 'run_mail_scheduler', 'id': 1},
     {'active': False, 'function': 'run_bdr_scheduler', 'id': 2},
     {'active': False, 'function': 'scheduled_fetch_new_scans', 'id': 9}]
    demo >>>
    demo >>> client.modules('delivery')
    {'uninstalled': ['delivery', 'sale_delivery_report']}
    demo >>> client.upgrade('base')
    1 module(s) selected
    42 module(s) to update:
      to upgrade    account
      to upgrade    account_chart
      to upgrade    account_tax_include
      to upgrade    base
      ...
    demo >>>


Main commands::

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
    access(obj, mode='read')        # Check access on the model

    do(obj, method, *params)        # Generic 'object.execute'
    wizard(name)                    # Return the 'id' of a new wizard
    wizard(name_or_id, datas=None, action='init')
                                    # Generic 'wizard.execute'
    exec_workflow(obj, signal, id)  # Trigger workflow signal

    client                          # Client object, connected
    client.login(user)              # Login with another user
    client.connect(env)             # Connect to another env.
    client.modules(name)            # List modules matching pattern
    client.upgrade(module1, module2, ...)
                                    # Upgrade the modules
