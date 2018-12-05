Changelog
---------


1.7.1 (2018-12-05)
~~~~~~~~~~~~~~~~~~

* Add support for the JSON-RPC protocol.  It is enabled if the ``--server``
  argument contains the full path to the ``/jsonrpc`` endpoint.
  As an alternative, you can specify the ``protocol`` in the configuration
  file.

* Change the return value of :meth:`Model.browse` method if search domain is
  an empty list.  It returns an empty ``RecordList`` except if some other
  argument is provided (e.g.
  ``all_users = model('res.users').browse([], limit=None)``).
  Compatibility tip: you can restore the old behavior with
  ``Model._browse_compat = True``.

* Change the return value of ``Client.read()`` and ``Model.read()`` methods
  if search domain is an empty list:  it returns ``False``.

* Improve error formatting for recent Odoo versions, in interactive mode.

* Refactor the construction of ``Service`` proxies.

* Drop compatibility with Python 2.6.


1.7 (2018-11-22)
~~~~~~~~~~~~~~~~

* Fully support Odoo 10 and Odoo 11.

* New method ``Client.clone_database`` based on ``Client.db.duplicate_database``.

* Optional ``login`` and ``country_code`` arguments for
  ``Client.create_database`` in Odoo 9+.

* Use the ``context`` for the ``search`` methods.

* Service ``Client._report`` is removed in Odoo 11. Methods ``Client.report``,
  ``Client.report_get`` and ``Client.render_report`` are removed too.

* More robust Python 2 detection logic.


1.6.3 (2015-12-30)
~~~~~~~~~~~~~~~~~~

* Do not parse long integers which overflow in XML-RPC.


1.6.2 (2015-09-17)
~~~~~~~~~~~~~~~~~~

* Add an optional ``transport`` argument to the ``Client`` constructor.
  This is useful for tweaking the SSL context or adding an optional
  timeout parameter.

* Implement ``==`` comparison for ``RecordList`` instances.

* Uninstall dependent add-ons in a single call.

* Do not install/uninstall add-ons if other actions are pending.

* Do not hang when the ``Client`` constructor receives invalid
  arguments.

* Fix ``str(record)`` and ``print(record)`` with non-ASCII names.


1.6.1 (2014-11-12)
~~~~~~~~~~~~~~~~~~

* Support using ``--env`` and ``--user`` together to connect with a
  different user.

* Adapt for Odoo 8.0 after change ``cc4fba6`` on October 2014.

* Do not interpret digits with leading ``0`` as octal in search domain.


1.6 (2014-09-23)
~~~~~~~~~~~~~~~~

* Compatible with Odoo 8.0.

* New attribute ``Client.context`` to set the default context for
  high-level ``Model`` and ``Record`` methods.

* Use blocking RPC call in ``Client.create_database``.  Asynchronous
  method is removed in Odoo.

* Return the interactive namespace with ``main(interact=False)``.
  It helps to integrate with third-party libraries, such as IPython.

* Remove a duplicate ``Logged in as ...`` line in interactive mode.

* Remove the ``search+name_get`` undocumented feature which has
  wrong behavior when applied to an empty ``RecordList``.

* Do not prevent login if access to ``Client.db.list()`` is denied.


1.6b1 (2014-06-09)
~~~~~~~~~~~~~~~~~~

* When a function or a method fails, raise an ``erppeek.Error`` instead
  of printing a message and returning ``None``.

* Switch to local mode when the command line argument points at the
  server configuration, like ``-c path/to/openerp-server.conf``.

* Local mode compatible with Odoo trunk: support both the old and the
  new API.

* Use shell-like parsing for ``options =`` setting in local mode.

* Function ``start_openerp_services`` is replaced with
  ``start_odoo_services``: it is still compatible with OpenERP 6.1 and 7
  and it accepts a list of options in the first argument, similar to
  ``sys.argv[1:]``.

* Search domains require square brackets.  Usage without square brackets
  was deprecated since 0.5, with ``UserWarning`` alerts.

* Implement addition of ``RecordList`` of the same model.

* Drop compatibility with Python 2.5.


1.5.3 (2014-05-26)
~~~~~~~~~~~~~~~~~~

* Change command line output to CSV format.

* Translate command line output according to LANG environment variable.

* Pretty print the list of modules.

* Do not report ``Module(s) not found`` when trying to install a
  module already installed.


1.5.2 (2014-04-12)
~~~~~~~~~~~~~~~~~~

* Return an appropriate error message when the client is not connected.

* Two similar ``Record`` from different connections do not compare equal.

* Set the ``PGAPPNAME`` used for the PostgreSQL connection, in local mode.

* Close PostgreSQL connections on exit, in local mode.

* Implement the context manager protocol.


1.5.1 (2014-03-11)
~~~~~~~~~~~~~~~~~~

* When switching to a different environment, with ``Client.connect``,
  invalidate the previous connection to avoid mistakes (interactive mode).

* Avoid cluttering the globals in interactive mode.

* Close socket to avoid ``ResourceWarning`` on Python 3.

* The ``get_pool`` helper is only available in interactive mode and if
  the client is connected locally using the ``openerp`` package.

* Clear the last exception before entering interactive mode, only needed
  on Python 2.

* Fix the ``searchargs`` domain parser for compatibility with Python 3.4.


1.5 (2014-03-10)
~~~~~~~~~~~~~~~~

* Advertize the ``Model`` and ``Record`` paradigm in the ``usage`` printed
  in interactive mode: it's far more easier to use, and available since 1.0.

* In interactive mode, only inject four global names: ``client``, ``models``,
  ``model`` and ``do``.  Other methods are available on ``Model``
  and ``Client`` instances (``read`` ``search`` ``count`` ``keys`` ``fields``
  ``access`` ...).

* Always clear the ``Record`` cache when an arbitrary method is called on
  this ``Record``.

* Implement ``==`` comparison for ``Record`` instances.

* New computed attributes ``Record._external_id`` and
  ``RecordList._external_id``, and new method
  ``Model._get_external_ids(ids=None)``.

* Better parsing of dates in search terms.

* Reject invalid ``==`` operator in search terms.

* Now the ``str(...)`` of a ``Record`` is always retrieved with ``name_get``.
  Previously, the output was sometimes inconsistent.

* Fix ``TypeError`` when browsing duplicate ids.

* Fix error with ``Model.get(['field = value'], context={...})``.

* Workaround an issue with some models: always pass a list of ids
  to ``read``.

* Test the behaviour when ``read`` is called with a ``False`` id: it happens
  when browsing a ``RecordList`` for example.


1.4.5 (2013-03-20)
~~~~~~~~~~~~~~~~~~

* Extend ``Model.get`` to retrieve a record by ``xml_id``.

* Fix AttributeError when reading a mix of valid and invalid records.

* Fix ``dir()`` on ``Record`` and ``RecordList`` to return all declared
  fields, and do not report ``id`` field twice.

* Fix a crash with built-in OS X readline on Python 2.5 or 2.6.


1.4.4 (2013-03-05)
~~~~~~~~~~~~~~~~~~

* Remove deprecated ``Record.client``.

* Fix compatibility with Python 3.

* Add optional argument ``check`` to the ``Client.model`` method to
  bypass the verification in some cases, used to speed up the read methods.

* Do not crash when mixing non-existing and existing records: return
  always ``False`` for non-existing records.


1.4.3 (2013-01-10)
~~~~~~~~~~~~~~~~~~

* Compatible with OpenERP 7.

* Set the database name as thread attribute to print it in the log file
  (local mode only).

* Do not try to access private methods through RPC when resolving
  attributes of the ``Client`` or any ``Record`` or ``RecordList``.


1.4.2 (2012-12-19)
~~~~~~~~~~~~~~~~~~

* Add the ``get_pool`` helper when connected using the ``openerp`` library.

* Remove the leading slash on the ``server`` option, if present.

* Do not try to access private methods through RPC when reading attributes
  of the ``model(...)``.


1.4.1 (2012-10-05)
~~~~~~~~~~~~~~~~~~

* Fix reading ``many2one`` attribute on ``RecordList`` object in local mode.

* Fix occasional issue on login when switching database on the same server.

* Optimization: do not propagate the call to ``RecordList.write`` or
  ``RecordList.unlink`` if the list is empty.

* Clear the ``Record`` cache on ``Record._send``.

* Expose the method ``Record.refresh`` to clear the local cache.


1.4 (2012-10-01)
~~~~~~~~~~~~~~~~

* New: direct connection to a local server using the ``openerp`` library.
  Use ``scheme = local`` and ``options = -c /path/to/openerp-server.conf``
  in the configuration.


1.3.1 (2012-09-28)
~~~~~~~~~~~~~~~~~~

* Fix method ``Record._send``.


1.3 (2012-09-27)
~~~~~~~~~~~~~~~~

* Implement exception chaining in ``format_exception`` to print the
  original traceback.

* Return a list of ``Record`` objects when reading the ``reference`` field
  of a ``RecordList`` object.

* Fix reading attributes on ``RecordList`` with holes or gaps.

* Accessing an empty ``one2many`` or ``many2many`` attribute on a ``Record``
  returns a ``RecordList``.

* New method ``Model.get`` to retrieve a single ``Record``.  It raises a
  ``ValueError`` if multiple records are found.

* New method ``Record._send`` to send a workflow signal.


1.2.2 (2012-09-24)
~~~~~~~~~~~~~~~~~~

* Accept ``Record`` and ``RecordList`` attribute values when writing or
  creating records.

* Improve the methods ``write`` and ``create`` of ``Record`` and ``RecordList``
  objects to manage ``one2many`` and ``many2many`` fields.

* Return a ``Record`` when reading a ``reference`` field.  Implement the
  ``create`` and ``write`` methods for these fields.

* Remove undocumented alias ``Record.update``.


1.2.1 (2012-09-21)
~~~~~~~~~~~~~~~~~~

* Add the special operators ``=ilike``, ``=ilike``, ``=?`` and fix
  parsing of inequality operators ``>=`` and ``<=``.

* Fix the ``RecordList.id`` attribute, and deprecate ``RecordList._ids``.

* Deprecate the ``Record.client`` attribute: use ``Record._model.client``.

* Accessing an empty ``many2one`` attribute on a ``RecordList`` now returns
  a ``RecordList``.

* Fix ``TypeError`` when browsing non-existent records.


1.2 (2012-09-19)
~~~~~~~~~~~~~~~~

* Catch some malformed search domains before sending the RPC request.

* Preserve dictionary response when calling non standard ``Record`` methods.

* Expose the helper ``format_exception`` which formats the errors
  received through XML-RPC.

* Support XML-RPC through HTTPS with ``scheme = https`` in the
  ``erppeek.ini`` configuration file.

* Print an error message when ``client.upgrade(...)`` does not find any
  module to upgrade.


1.1 (2012-09-04)
~~~~~~~~~~~~~~~~

* When using arbitrary methods on ``Record``, wrap the ``id`` in
  a list ``[id]``.  It fixes a recurring issue with poorly tested
  methods.

* Do not read all records if the ``RecordList`` is empty.

* Fix the bad behaviour when switching to a different database.

* Order the results when using ``read`` method with ``order=`` argument.

* Reading attributes of the sequence ``<RecordList 'sea.fish,[2, 1, 2]'>`` will
  return an ordered sequence of three items.  Previously it used to return an
  unordered sequence of two items.

* Accept the ``%(...)s`` formatting for the fields parameter of the
  ``Record.read`` and the ``RecordList.read`` methods too.

* Add a tutorial to the documentation.


1.0 (2012-08-29)
~~~~~~~~~~~~~~~~

* Add the test suite for Python 2 and Python 3.

* Implement ``len()`` for ``RecordList`` objects.

* Connect to the server even if the database is missing.

* Expose the method ``Client.db.get_progress``.

* New method ``Client.create_database`` which wraps together
  ``Client.db.create``  and ``Client.db.get_progress``.

* Save the readline history in ``~/.erppeek_history``, only
  if the file already exists.

* Enable auto-completion using ``rlcompleter`` standard module.

* Raise an ``AttributeError`` when assigning to a missing or
  read-only attribute.


0.11 (2012-08-24)
~~~~~~~~~~~~~~~~~

* Enhance the ``Model.browse()`` method to accept the same
  keyword arguments as the ``Client.search()`` method.

* Fix the verbose level on ``Client.connect()``.

* Fix the ``Record.copy()`` method.

* Fix the ``Record.perm_read()`` method (workaround an OpenERP bug when
  dealing with single ids).

* Drop the ``--search`` argument, because the search terms can be passed as
  positional arguments after the options.  Explain it in the description.

* Fix the shell command.  Request the password interactively if it's not
  in the options and not in the configuration file.


0.10 (2012-08-23)
~~~~~~~~~~~~~~~~~

* Add the ``--verbose`` switch to log the XML-RPC messages.
  Lines are truncated at 79 chars.  Use ``-vv`` or ``-vvv``
  to truncate at 179 or 9999 chars respectively.

* Removed the ``--write`` switch because it's not really useful.
  Use :meth:`Record.write` or :meth:`client.write` for example.

* Stop raising RuntimeError when calling ``Client.model(name)``.
  Simply print the message if the name does not match.

* Fix ``RecordList.read()`` and ``Record.read()`` methods to accept the
  same diversity of ``fields`` arguments as the ``Client.read()`` method.

* ``RecordList.read()`` and ``Record.read()`` return instances of
  ``RecordList`` and ``Record`` for relational fields.

* Optimize: store the name of the ``Record`` when a relational field
  is accessed.

* Fix message wording on module install or upgrade.


0.9.2 (2012-08-22)
~~~~~~~~~~~~~~~~~~

* Fix ``Record.write()`` and ``Record.unlink()`` methods.

* Fix the caching of the ``Model`` keys and fields and the ``Record``
  name.


0.9.1 (2012-08-22)
~~~~~~~~~~~~~~~~~~

* Fix ``client.model()`` method.  Add ``models()`` to the ``globals()``
  in interactive mode.


0.9 (2012-08-22)
~~~~~~~~~~~~~~~~

* Add the Active Record pattern for convenience.  New classes :class:`Model`,
  :class:`RecordList` and :class:`Record`.  The :meth:`Client.model` method
  now returns a single :class:`Model` instance.  These models can be
  reached using camel case attribute too.  Example:
  ``client.model('res.company')`` and ``client.ResCompany`` return the same
  :class:`Model`.

* Refresh the list of modules before install or upgrade.

* List all modules which have ``state not in ('uninstalled', 'uninstallable')``
  when calling ``client.modules(installed=True)``.

* Add documentation.


0.8 (2012-04-24)
~~~~~~~~~~~~~~~~

* Fix ``help(client)`` and ``repr(...)``.

* Add basic safeguards for argument types.


0.7 (2012-04-04)
~~~~~~~~~~~~~~~~

* Fix RuntimeError on connection.


0.6 (2012-04-03)
~~~~~~~~~~~~~~~~

* Support Python 3.

* Return Client method instead of function when calling ``client.write``
  or similar.

* Fix the case where :meth:`~Client.read()` is called with a single id.


0.5 (2012-03-29)
~~~~~~~~~~~~~~~~

* Implement ``Client.__getattr__`` special attribute to call any object
  method, like ``client.write(obj, values)``.  This is somewhat
  redundant with ``client.execute(obj, 'write', values)`` and its
  interactive alias ``do(obj, 'write', values)``.

* Add ``--write`` switch to enable unsafe helpers: ``write``,
  ``create``, ``copy`` and ``unlink``.

* Tolerate domain without square brackets, but show a warning.

* Add long options ``--search`` for ``-s``, ``--interact`` for ``-i``.


0.4 (2012-03-28)
~~~~~~~~~~~~~~~~

* Workaround for ``sys.excepthook`` ignored, related to a
  `Python issue <http://bugs.python.org/issue12643>`__.


0.3 (2012-03-26)
~~~~~~~~~~~~~~~~

* Add ``--config`` and ``--version`` switches.

* Improve documentation with session examples.

* Move the project from Launchpad to GitHub.


0.2 (2012-03-24)
~~~~~~~~~~~~~~~~

* Allow to switch user or database: methods ``client.login`` and
  ``client.connect``.

* Allow ``context=`` keyword argument.

* Add ``access(...)`` method.

* Add ``%(...)s`` formatting for the fields parameter of the ``read(...)`` method.

* Refactor the interactive mode.

* Many improvements.

* Publish on PyPI.


0.1 (2012-03-14)
~~~~~~~~~~~~~~~~

* Initial release.
