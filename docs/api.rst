===========
ERPpeek API
===========

.. module:: erppeek

The library provides few objects to access the OpenObject model and the
associated services provided by the OpenERP XML-RPC API.

The signature of the methods mimic the standard methods provided by the
:class:`osv.osv` OpenERP class.  This is intended to help the developer when
developping addons.  What is experimented at the interactive prompt should
be portable in the application with little effort.

.. contents::
   :local:


.. _client-and-services:

Client and Services
-------------------

The :class:`Client` object provides thin wrappers around XML-RPC services
and their methods.  Additional helpers are provided to explore the models and
list or install OpenERP addons.


.. autoclass:: Client

.. automethod:: Client.from_config

.. automethod:: Client.login

.. note::

   In interactive mode, a method :attr:`Client.connect(env=None)` exists, to
   connect to another environment, and recreate the :func:`globals()`.


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

.. method:: Client.create(obj, values, context=None)

   Create a new record for the model.
   The argument `values` is a dictionary of values for the new record.
   Return the object ``id``.

.. method:: Client.copy(obj, id, default=None, context=None)

   Copy a record and return the new ``id``.
   The optional argument `default` is a mapping which overrides some values
   of the new record.

.. method:: Client.write(obj, ids, values, context=None)

   Update the record(s) with the content of the `values` dictionary.

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

Those methods give more control on the OpenERP objects: workflows, wizards
and reports.  Please refer to the OpenERP documentation for details.


.. automethod:: Client.execute(obj, method, *params, **kwargs)

.. method:: Client.execute_kw(obj, ids, params, kwargs=None)

   Wrapper around ``object.execute_kw`` RPC method.

   Does not exist if server is OpenERP 5.

.. automethod:: Client.exec_workflow

.. automethod:: Client.wizard

.. method:: Client.report(obj, ids, datas=None, context=None)

   Wrapper around ``report.report`` RPC method.

.. method:: Client.render_report(obj, ids, datas=None, context=None)

   Wrapper around ``report.render_report`` RPC method.

   Does not exist if server is OpenERP 5.

.. method:: Client.report_get(report_id)

   Wrapper around ``report.report_get`` RPC method.


XML-RPC Services
~~~~~~~~~~~~~~~~

The nake XML-RPC services are exposed too.  There are five services.
The :attr:`~Client.db` and the :attr:`~Client.common` services expose few
methods which might be helpful for server administration.  Use the
:func:`dir` function to introspect them.  The three other services should
not be used directly: they are in the private namespace, starting with
``_`` because their methods are wrapped and  exposed on the :class:`Client`
object itself.  Please refer to the OpenERP documentation for more details.


.. attribute:: Client.db

   Expose the ``db`` :class:`Service`.

   Examples: :meth:`Client.db.list` or :meth:`Client.db.server_version`
   RPC methods.

.. attribute:: Client.common

   Expose the ``common`` :class:`Service`.

   Example: :meth:`Client.common.login_message` RPC method.

.. data:: Client._object

   Expose the ``object`` :class:`Service`.

.. attribute:: Client._wizard

   Expose the ``wizard`` :class:`Service`.

.. attribute:: Client._report

   Expose the ``report`` :class:`Service`.

.. autoclass:: Service
   :members:
   :undoc-members:


Manage addons
~~~~~~~~~~~~~

These helpers are convenient to list, install or upgrade addons from a
Python script or interactively in a Python session.

.. automethod:: Client.modules

.. automethod:: Client.install

.. automethod:: Client.upgrade

.. automethod:: Client.uninstall


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

.. autoclass:: Model

   .. automethod:: keys

   .. automethod:: fields

   .. automethod:: field

   .. automethod:: access

   .. method:: browse(domain, context=None)
   .. automethod:: browse(domain, offset=0, limit=None, order=None, context=None)

   .. automethod:: create

..
   :members: keys, fields, field, access, create, browse

.. autoclass:: RecordList

   .. method:: read(fields=None, context=None)

      Wrapper for the :meth:`Record.read` method.

      Return a :class:`RecordList` if `fields` is the name of a single
      ``many2one`` field, else return a :class:`list`.
      See :meth:`Client.read` for details.

   .. method:: unlink(context=None)

      Wrapper for the :meth:`Record.unlink` method.

   .. method:: write(values, context=None)

      Wrapper for the :meth:`Record.write` method.

.. autoclass:: Record
   :members:
   :undoc-members:


Utilities
---------

.. autofunction:: lowercase(s)

.. autofunction:: mixedcase(s)

.. autofunction:: issearchdomain

.. autofunction:: searchargs

.. autofunction:: read_config
