Changelog
---------


0.8 (2012-04-24)
~~~~~~~~~~~~~~~~

* Fix help(client) and repr(...).

* Add basic safeguards for argument types.


0.7 (2012-04-04)
~~~~~~~~~~~~~~~~

* Fix RuntimeError on connection.


0.6 (2012-04-03)
~~~~~~~~~~~~~~~~

* Support Python 3.

* Return Client method instead of function when calling ``client.write``
  or similar.

* Fix the case where read() is called with a single id.


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
