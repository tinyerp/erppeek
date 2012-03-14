
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

 * Edit "erppeek.ini" to declare your environment(s)
 * Run the script
    ./erppeek.py --list
    ./erppeek.py --env demo


Main commands are:

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

    do(obj, method, *params)        # Generic 'object.execute'
    wizard(name)                    # Return the 'id' of a new wizard
    wizard(name_or_id, datas=None, action='init')
                                    # Generic 'wizard.execute'
    exec_workflow(obj, signal, id)  # Trigger workflow signal

    client                          # Client object, connected
    client.modules(name)            # List modules matching pattern
    client.upgrade(module1, module2, ...)
                                    # Upgrade the modules
