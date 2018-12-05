===========
ERPpeek API
===========

.. module:: erppeek

The library provides few objects to access the OpenObject model and the
associated services of `the Odoo API`_.

The signature of the methods mimics the standard methods provided by the
:class:`osv.Model` Odoo class.  This is intended to help the developer when
developping addons.  What is experimented at the interactive prompt should
be portable in the application with little effort.

.. contents::
   :local:


.. _client-and-services:

Client and Services
-------------------

The :class:`Client` object provides thin wrappers around Odoo RPC services
and their methods.  Additional helpers are provided to explore the models and
list or install Odoo add-ons.


.. autoclass:: Client

.. automethod:: Client.from_config

.. automethod:: Client.create_database

.. automethod:: Client.clone_database

.. automethod:: Client.login

.. attribute:: Client.context

   Default context used for all the methods (default ``None``).
   In :ref:`interactive mode <interactive-mode>`, this default context
   contains the language of the shell environment (variable ``LANG``).
   Do not update the context, either copy it or replace it::

       # Set language to German
       client.context = {'lang': 'de_DE', 'preferred_color': 'blue'}
       # ... do something

       # Switch to Italian
       client.context = dict(client.context, lang='it_IT')
       # ... do something

       # and AVOID (because it changes the context of existing records)
       client.context['lang'] = 'fr_FR'


.. note::

   In :ref:`interactive mode <interactive-mode>`, a method
   :attr:`Client.connect(env=None)` exists, to connect to another environment,
   and recreate the :func:`globals()`.


.. note::

   In :ref:`interactive mode <interactive-mode>`, when connected to the local
   Odoo server, the `get_pool(db_name=None)` function helps to grab a model
   registry for the current database.  The cursor factory is available on the
   registry as ``get_pool().cursor()`` (Odoo) or ``get_pool().db.cursor()``
   (OpenERP <= 7).


Objects
~~~~~~~

..
   .. method:: Client.search(obj, domain, context=None)
.. automethod:: Client.search(obj, domain, offset=0, limit=None, order=None, context=None)

.. automethod:: Client.count(obj, domain, context=None)

..
   .. method:: Client.read(obj, ids, fields=None)
               Client.read(obj, domain, fields=None)
.. automethod:: Client.read(obj, domain, fields=None, offset=0, limit=None, order=None, context=None)

.. method:: Client.perm_read(obj, ids, context=None, details=True)

   Lookup metadata about the records in the `ids` list.
   Return a list of dictionaries with the following keys:

    * ``id``: object id
    * ``create_uid``: user who created the record
    * ``create_date``: date when the record was created
    * ``write_uid``: last user who changed the record
    * ``write_date``: date of the last change to the record
    * ``xmlid``: External ID to use to refer to this record (if there is one),
      in format ``module.name`` (not available with OpenERP 5)

   If `details` is True, the ``create_uid`` and ``write_uid`` contain the
   name of the user.

.. method:: Client.write(obj, ids, values, context=None)

   Update the record(s) with the content of the `values` dictionary.

.. method:: Client.create(obj, values, context=None)

   Create a new record for the model.
   The argument `values` is a dictionary of values for the new record.
   Return the object ``id``.

.. method:: Client.copy(obj, id, default=None, context=None)

   Copy a record and return the new ``id``.
   The optional argument `default` is a mapping which overrides some values
   of the new record.

.. method:: Client.unlink(obj, ids, context=None)

   Delete records with the given `ids`

.. automethod:: Client.models

.. automethod:: Client.model


.. automethod:: Client.keys

.. automethod:: Client.fields

.. automethod:: Client.field

.. automethod:: Client.access


Advanced methods
~~~~~~~~~~~~~~~~

Those methods give more control on the Odoo objects: workflows and reports.
Please refer to `the Odoo documentation`_ for details.


.. automethod:: Client.execute(obj, method, *params, **kwargs)

.. method:: Client.execute_kw(obj, ids, params, kwargs=None)

   Wrapper around ``object.execute_kw`` RPC method.

   Does not exist if server is OpenERP 5.

.. automethod:: Client.exec_workflow

.. method:: Client.report(obj, ids, datas=None, context=None)

   Wrapper around ``report.report`` RPC method.

   Removed in Odoo 11.

.. method:: Client.render_report(obj, ids, datas=None, context=None)

   Wrapper around ``report.render_report`` RPC method.

   Does not exist if server is OpenERP 5.

   Removed in Odoo 11.

.. method:: Client.report_get(report_id)

   Wrapper around ``report.report_get`` RPC method.

   Removed in Odoo 11.

.. automethod:: Client.wizard

   Removed in OpenERP 7.


Odoo RPC Services
~~~~~~~~~~~~~~~~~

The nake Odoo services are exposed too.
The :attr:`~Client.db` and the :attr:`~Client.common` services expose few
methods which might be helpful for server administration.  Use the
:func:`dir` function to introspect them.  The :attr:``~Client._object``
service should not be used directly because its methods are wrapped and
exposed on the :class:`Client` object itself.
The two last services are deprecated and removed in recent versions of Odoo.
Please refer to `the Odoo documentation`_ for more details.


.. attribute:: Client.db

   Expose the ``db`` :class:`Service`.

   Examples: :meth:`Client.db.list` or :meth:`Client.db.server_version`
   RPC methods.

.. attribute:: Client.common

   Expose the ``common`` :class:`Service`.

   Example: :meth:`Client.common.login_message` RPC method.

.. data:: Client._object

   Expose the ``object`` :class:`Service`.

.. attribute:: Client._report

   Expose the ``report`` :class:`Service`.

   Removed in Odoo 11.

.. attribute:: Client._wizard

   Expose the ``wizard`` :class:`Service`.

   Removed in OpenERP 7.

.. autoclass:: Service
   :members:
   :undoc-members:

.. _the Odoo documentation:
.. _the Odoo API: http://doc.odoo.com/v6.1/developer/12_api.html#api


Manage addons
~~~~~~~~~~~~~

These helpers are convenient to list, install or upgrade addons from a
Python script or interactively in a Python session.

.. automethod:: Client.modules

.. automethod:: Client.install

.. automethod:: Client.upgrade

.. automethod:: Client.uninstall

.. note::

   It is not recommended to install or upgrade modules in offline mode when
   any web server is still running: the operation will not be signaled to
   other processes.  This restriction does not apply when connected through
   XML-RPC or JSON-RPC.


.. _model-and-records:

Model and Records
-----------------

In addition to the thin wrapper methods, the :class:`Client` provides a high
level API which encapsulates objects into `Active Records
<http://www.martinfowler.com/eaaCatalog/activeRecord.html>`_.

The :class:`Model` is instantiated using the :meth:`Client.model` method or
directly through camel case attributes.

Example: both ``client.model('res.company')`` and ``client.ResCompany`` return
the same :class:`Model`.

.. autoclass:: Model(client, model_name)

   .. automethod:: keys

   .. automethod:: fields

   .. automethod:: field

   .. automethod:: access

   ..
      .. method:: browse(domain, context=None)
   .. automethod:: browse(domain, offset=0, limit=None, order=None, context=None)

   .. note::

      To enable the unsafe behavior (ERPpeek <= 1.7) of ``model.browse([])`` (i.e.
      return all records), this class attribute can be set:
      ``Model._browse_compat = True``.

   .. automethod:: get(domain, context=None)

   .. automethod:: create

   .. automethod:: _get_external_ids

..
   search count read ...

.. autoclass:: RecordList(model, ids)

   .. method:: read(fields=None, context=None)

      Wrapper for the :meth:`Record.read` method.

      Return a :class:`RecordList` if `fields` is the name of a single
      ``many2one`` field, else return a :class:`list`.
      See :meth:`Client.read` for details.

   .. method:: perm_read(context=None)

      Wrapper for the :meth:`Record.perm_read` method.

   .. method:: write(values, context=None)

      Wrapper for the :meth:`Record.write` method.

   .. method:: unlink(context=None)

      Wrapper for the :meth:`Record.unlink` method.

   .. attribute:: _external_id

      Retrieve the External IDs of the :class:`RecordList`.

      Return the list of fully qualified External IDs of
      the :class:`RecordList`, with default value False if there's none.
      If multiple IDs exist for a record, only one of them is returned.

.. autoclass:: Record(model, id)
   :members: read, perm_read, write, copy, unlink, _send, _external_id, refresh
   :undoc-members:


Utilities
---------

.. autofunction:: lowercase(s)

.. autofunction:: mixedcase(s)

.. autofunction:: issearchdomain

.. autofunction:: searchargs

.. autofunction:: format_exception(type, value, tb, limit=None, chain=True)

.. autofunction:: read_config

.. autofunction:: start_odoo_services
