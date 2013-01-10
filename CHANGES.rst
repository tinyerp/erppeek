Changelog
---------


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
