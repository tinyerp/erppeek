
ERPpeek, a tool for browsing OpenERP data from the command line
===============================================================

There are two modes:
 (1) with command line arguments
 (2) as an interactive shell

It requires python 2.5, 2.6 or 2.7.
It supports OpenERP 5.0, 6.0 and 6.1


COMMAND LINE ARGUMENTS
----------------------

See the introduction on this page
http://www.theopensourcerer.com/2011/12/13/erppeek-a-tool-for-browsing-openerp-data-from-the-command-line/
 or
./erppeek.py --help



INTERACTIVE USE
---------------

Main commands are:

    do(obj, method, *params)        # Generic 'service.execute'

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
