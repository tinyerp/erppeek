.. ERPpeek documentation master file, created by
   sphinx-quickstart on Tue Aug 21 09:47:49 2012.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.


ERPpeek's documentation
=======================

*A versatile tool for browsing Odoo / OpenERP data*

The ERPpeek library communicates with any `Odoo / OpenERP server`_ (>= 5.0)
using `the standard XML-RPC interface`_ or the new JSON-RPC interface.

It provides both a :ref:`fully featured low-level API <client-and-services>`,
and an encapsulation of the methods on :ref:`Active Record objects
<model-and-records>`.  Additional helpers are provided to explore the model
and administrate the server remotely.

The :doc:`intro` describes its primary uses as a :ref:`command line tool
<command-line>` or within an :ref:`interactive shell <interactive-mode>`.

The :doc:`tutorial` gives an in-depth look at the capabilities.



Contents:

.. toctree::
   :maxdepth: 2

   intro
   API <api>
   tutorial
   developer

* Online documentation: http://erppeek.readthedocs.org/
* Source code and issue tracker: https://github.com/tinyerp/erppeek

.. _Odoo / OpenERP server: http://doc.odoo.com/
.. _the standard XML-RPC interface: http://doc.odoo.com/v6.1/developer/12_api.html#api


Indices and tables
==================

* :ref:`genindex`
* :ref:`search`


Credits
=======

Authored and maintained by Florent Xicluna.

Derived from a script by Alan Bell.
