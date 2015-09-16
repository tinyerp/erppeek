.. currentmodule:: erppeek

=================
Developer's notes
=================


Source code
-----------

* `Source code <https://github.com/tinyerp/erppeek>`_ and
  `issue tracker <https://github.com/tinyerp/erppeek/issues>`_ on GitHub.
* `Continuous tests <http://travis-ci.org/tinyerp/erppeek>`_ against Python
  2.6 through 3.5 and PyPy, on `Travis-CI platform
  <http://about.travis-ci.org/>`_.


Third-party integration
-----------------------

This module can be used with other Python libraries to achieve more
complex tasks.

For example:

* write unit tests using the standard `unittest
  <http://docs.python.org/library/unittest.html>`_ framework.
* write BDD tests using the `Gherkin language <http://packages.python.org/
  behave/gherkin.html#gherkin-feature-testing-language>`_, and a library
  like `Behave <http://packages.python.org/behave/>`_.
* build an interface for Odoo, using a framework like
  `Flask <http://flask.pocoo.org/>`_ (HTML, JSON, SOAP, ...).


Changes
-------

.. include:: ../CHANGES.rst
   :start-line: 3
