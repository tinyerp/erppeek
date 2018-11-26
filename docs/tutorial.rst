.. currentmodule:: erppeek

========
Tutorial
========

This tutorial demonstrates some features of ERPpeek in the interactive shell.

It assumes an Odoo or OpenERP server is installed.
The shell is a true Python shell.  We have access to all the features and
modules of the Python interpreter.

.. contents:: Steps:
   :local:
   :backlinks: top


First connection
----------------

The server is freshly installed and does not have an Odoo database yet.
The tutorial creates its own database ``demo`` to play with.

Open the ERPpeek shell::

    $ erppeek

It assumes that the server is running locally, and listens on default
port ``8069``.

If our configuration is different, then we use arguments, like::

    $ erppeek --server http://192.168.0.42:8069

It connects using the XML-RPC protocol. If you want to use the JSON-RPC
protocol instead, then pass the full URL with ``/jsonrpc`` path::

    $ erppeek --server http://127.0.0.1:8069/jsonrpc


On login, it prints few lines about the commands available.

.. sourcecode:: pycon

    $ erppeek
    Usage (some commands):
        models(name)                    # List models matching pattern
        model(name)                     # Return a Model instance
        model(name).keys()              # List field names of the model
        model(name).fields(names=None)  # Return details for the fields
        model(name).field(name)         # Return details for the field
        model(name).browse(domain)
        model(name).browse(domain, offset=0, limit=None, order=None)
                                        # Return a RecordList

        rec = model(name).get(domain)   # Get the Record matching domain
        rec.some_field                  # Return the value of this field
        rec.read(fields=None)           # Return values for the fields

        client.login(user)              # Login with another user
        client.connect(env)             # Connect to another env.
        client.modules(name)            # List modules matching pattern
        client.upgrade(module1, module2, ...)
                                        # Upgrade the modules

As we'll see later, the most interesting method here is probably
:meth:`~Client.model` which returns a :class:`Model` object with nice
wrappers.

And it confirms that the default database is not available::

    ...
    Error: Database 'odoo' does not exist: []

Though, we have a connected client, ready to use::

    >>> client
    <Client 'http://localhost:8069/xmlrpc#()'>
    >>> client.server_version
    '6.1'
    >>> #


Create a database
-----------------

We create the database ``"demo"`` for this tutorial.
We need to know the superadmin password before to continue.
This is the ``admin_passwd`` in the ``odoo-server.conf`` file.
Default password is ``"admin"``.

.. note:: This password gives full control on the databases. Set a strong
          password in the configuration to prevent unauthorized access.


.. sourcecode:: pycon

    >>> client.create_database('super_password', 'demo')
    Logged in as 'admin'
    >>> client
    <Client 'http://localhost:8069/xmlrpc#demo'>
    >>> client.db.list()
    ['demo']
    >>> client.user
    'admin'
    >>> client.modules(installed=True)
    {'installed': ['base', 'web', 'web_mobile', 'web_tests']}
    >>> len(client.modules()['uninstalled'])
    202
    >>> #

.. note::

   Create an ``erppeek.ini`` file in the current directory to declare all our
   environments.  Example::

       [DEFAULT]
       host = localhost
       port = 8069

       [demo]
       database = demo
       username = joe

   Then we connect to any environment with ``erppeek --env demo`` or switch
   during an interactive session with ``client.connect('demo')``.


Clone a database
----------------

It is sometimes useful to clone a database (testing, backup, migration, ...).
A shortcut is available for that, the required parameters are the new
database name and the superadmin password.


.. sourcecode:: pycon

    >>> client.clone_database('super_password', 'demo_test')
    Logged in as 'admin'
    >>> client
    <Client 'http://localhost:8069/xmlrpc#demo_test'>
    >>> client.db.list()
    ['demo', 'demo_test']
    >>> client.user
    'admin'
    >>> client.modules(installed=True)
    {'installed': ['base', 'web', 'web_mobile', 'web_tests']}
    >>> len(client.modules()['uninstalled'])
    202
    >>> #


Find the users
--------------

We have created the database ``"demo"`` for the tests.
We are connected to this database as ``'admin'``.

Where is the table for the users?

.. sourcecode:: pycon

    >>> client
    <Client 'http://localhost:8069/xmlrpc#demo'>
    >>> models('user')
    {'ResUsers': <Model 'res.users'>, 'ResWidgetUser': <Model 'res.widget.user'>}

We've listed two models which matches the name, ``res.users`` and
``res.widget.user``.  We reach the users' model using the :meth:`~Client.model`
method and we want to introspect its fields.
Fortunately, the :class:`Model` class provides methods to retrieve all
the details.

.. sourcecode:: pycon

    >>> model('res.users')
    <Model 'res.users'>
    >>> print(model('res.users').keys())
    ['action_id', 'active', 'company_id', 'company_ids', 'context_lang',
     'context_tz', 'date', 'groups_id', 'id', 'login', 'menu_id', 'menu_tips',
     'name', 'new_password', 'password', 'signature', 'user_email', 'view']
    >>> model('res.users').field('view')
    {'digits': [16, 2],
     'fnct_inv': '_set_interface_type',
     'fnct_inv_arg': False,
     'fnct_search': False,
     'func_obj': False,
     'function': '_get_interface_type',
     'help': 'OpenERP offers a simplified and an extended user interface. If\
     you use OpenERP for the first time we strongly advise you to select the\
     simplified interface, which has less features but is easier to use. You\
     can switch to the other interface from the User/Preferences menu at any\
     time.',
     'selection': [['simple', 'Simplified'], ['extended', 'Extended']],
     'store': False,
     'string': 'Interface',
     'type': 'selection'}
    >>> #

Let's examine the ``'admin'`` user in details.

.. sourcecode:: pycon

    >>> model('res.users').count()
    1
    >>> admin_user = model('res.users').browse(1)
    >>> admin_user.groups_id
    <RecordList 'res.groups,[1, 2, 3]'>
    >>> admin_user.groups_id.name
    ['Access Rights', 'Configuration', 'Employee']
    >>> admin_user.groups_id.full_name
    ['Administration / Access Rights',
     'Administration / Configuration',
     'Human Resources / Employee']
    >>> admin_user.perm_read()
    {'create_date': False,
     'create_uid': False,
     'id': 1,
     'write_date': '2012-09-01 09:01:36.631090',
     'write_uid': [1, 'Administrator'],
     'xmlid': 'base.user_admin'}


Create a new user
-----------------

Now we want a non-admin user to continue the exploration.
Let's create ``Joe``.

.. sourcecode:: pycon

    >>> model('res.users').create({'login': 'joe'})
    Fault: Integrity Error

    The operation cannot be completed, probably due to the following:
    - deletion: you may be trying to delete a record while other records still reference it
    - creation/update: a mandatory field is not correctly set

    [object with reference: name - name]
    >>> #

It seems we've forgotten some mandatory data.  Let's give him a ``name``.

.. sourcecode:: pycon

    >>> model('res.users').create({'login': 'joe', 'name': 'Joe'})
    <Record 'res.users,3'>
    >>> joe_user = _
    >>> joe_user.groups_id.full_name
    ['Human Resources / Employee', 'Partner Manager']

The user ``Joe`` does not have a password: we cannot login as ``joe``.
We set a password for ``Joe`` and we try again.

.. sourcecode:: pycon

    >>> client.login('joe')
    Password for 'joe':
    Error: Invalid username or password
    >>> client.user
    'admin'
    >>> joe_user.password = 'bar'
    >>> client.login('joe')
    Logged in as 'joe'
    >>> client.user
    'joe'
    >>> #

Success!


Explore the model
-----------------

We keep connected as user ``Joe`` and we explore the world around us.

.. sourcecode:: pycon

    >>> client.user
    'joe'
    >>> all_models = sorted(models().values(), key=str)
    >>> len(all_models)
    92

Among these 92 objects, some of them are ``read-only``, others are
``read-write``.  We can also filter the ``non-empty`` models.

.. sourcecode:: pycon

    >>> # Read-only models
    >>> len([m for m in all_models if not m.access('write')])
    44
    >>> #
    >>> # Writable but cannot delete
    >>> [m for m in all_models if m.access('write') and not m.access('unlink')]
    [<Model 'ir.property'>]
    >>> #
    >>> # Unreadable models
    >>> [m for m in all_models if not m.access('read')]
    [<Model 'ir.actions.todo'>,
     <Model 'ir.actions.todo.category'>,
     <Model 'res.payterm'>]
    >>> #
    >>> # Now print the number of entries in all (readable) models
    >>> for m in all_models:
    ...     mcount = m.access() and m.count()
    ...     if not mcount:
    ...         continue
    ...     print('%4d  %s' % (mcount, m))
    ... 
      81  <Model 'ir.actions.act_window'>
      14  <Model 'ir.actions.act_window.view'>
      85  <Model 'ir.actions.act_window_close'>
      85  <Model 'ir.actions.actions'>
       4  <Model 'ir.actions.report.xml'>
       3  <Model 'ir.config_parameter'>
       2  <Model 'ir.cron'>
       1  <Model 'ir.mail_server'>
      92  <Model 'ir.model'>
     126  <Model 'ir.model.access'>
    1941  <Model 'ir.model.data'>
     658  <Model 'ir.model.fields'>
      32  <Model 'ir.module.category'>
     207  <Model 'ir.module.module'>
     432  <Model 'ir.module.module.dependency'>
       8  <Model 'ir.rule'>
      63  <Model 'ir.ui.menu'>
     185  <Model 'ir.ui.view'>
       1  <Model 'ir.ui.view_sc'>
      72  <Model 'ir.values'>
       1  <Model 'res.bank'>
       1  <Model 'res.company'>
     253  <Model 'res.country'>
      51  <Model 'res.country.state'>
      48  <Model 'res.currency'>
      49  <Model 'res.currency.rate'>
       9  <Model 'res.groups'>
       1  <Model 'res.lang'>
       1  <Model 'res.partner'>
       1  <Model 'res.partner.address'>
       1  <Model 'res.partner.bank.type'>
       1  <Model 'res.partner.bank.type.field'>
       5  <Model 'res.partner.title'>
       1  <Model 'res.request.link'>
       2  <Model 'res.users'>
       6  <Model 'res.widget'>
       1  <Model 'res.widget.user'>
    >>> #
    >>> # Show the content of a model
    >>> config_params = model('ir.config_parameter').browse([], limit=None)
    >>> config_params.read()
    [{'id': 1, 'key': 'web.base.url', 'value': 'http://localhost:8069'},
     {'id': 2, 'key': 'database.create_date', 'value': '2012-09-01 09:01:12'},
     {'id': 3,
      'key': 'database.uuid',
      'value': '52fc9630-f49e-2222-e622-08002763afeb'}]


Browse the records
------------------

Query the ``"res.country"`` model::

    >>> model('res.country').keys()
    ['address_format', 'code', 'name']
    >>> model('res.country').browse(['name like public'])
    <RecordList 'res.country,[41, 42, 57, 62, 116, 144]'>
    >>> model('res.country').browse(['name like public']).name
    ['Central African Republic',
     'Congo, Democratic Republic of the',
     'Czech Republic',
     'Dominican Republic',
     'Kyrgyz Republic (Kyrgyzstan)',
     'Macedonia, the former Yugoslav Republic of']
    >>> model('res.country').browse(['code > Y'], order='code ASC').read('code name')
    [{'code': 'YE', 'id': 247, 'name': 'Yemen'},
     {'code': 'YT', 'id': 248, 'name': 'Mayotte'},
     {'code': 'YU', 'id': 249, 'name': 'Yugoslavia'},
     {'code': 'ZA', 'id': 250, 'name': 'South Africa'},
     {'code': 'ZM', 'id': 251, 'name': 'Zambia'},
     {'code': 'ZR', 'id': 252, 'name': 'Zaire'},
     {'code': 'ZW', 'id': 253, 'name': 'Zimbabwe'}]
    >>> #

..
    model('res.country').browse(['code > Y'], order='code ASC').read('%(code)s %(name)s')

... the tutorial is done.

Jump to the :doc:`api` for further details.
