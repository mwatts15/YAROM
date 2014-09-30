# -*- coding: utf-8 -*-

"""
yarom
==========

OpenWorm Unified Data Abstract Layer.

Most statements correspond to some action on the database.
Some of these actions may be complex, but intuitively ``a.B()``, the Query form,
will query against the database for the value or values that are related to ``a`` through ``B``;
on the other hand, ``a.B(c)``, the Update form, will add a statement to the database that ``a``
relates to ``c`` through ``B``. For the Update form, a Relationship object describing the
relationship stated is returned as a side-effect of the update.

The Update form can also be accessed through the set() method of a Property and the Query form through the get()
method like::

    a.B.set(c)

and::

    a.B.get()

The get() method also allows for parameterizing the query in ways specific to the Property.

Relationship objects are key to the :class:`Evidence class <.Evidence>` for sourcing statements.
Relationships can themselves be members in a relationship, allowing for fairly complex hierarchical statements to
be made about entities.

Notes:

- Of course, when these methods communicate with an external database, they may fail due to the database being
  unavailable and the user should be notified if a connection cannot be established in a reasonable time. Also, some
  objects are created by querying the database; these may be made out-of-date in that case.

- ``a : {x_0,...,x_n}`` means ``a`` could have the value of any one of ``x_0`` through ``x_n``

Classes
-------

.. automodule:: yarom.dataObject
.. automodule:: yarom.dataUser
.. automodule:: yarom.data
.. automodule:: yarom.configure
"""

__version__ = '0.5.0-alhpa'
__author__ = 'Mark Watts'

import traceback
from .configure import Configuration,Configureable,ConfigValue,BadConf
from .data import Data
from .dataUser import DataUser
from .mapper import MappedClass, oid
from .quantity import Quantity

__import__('__main__').connected = False

def config():
    return Configureable.conf

def loadConfig(f):
    """ Load configuration for the module """
    Configureable.conf = Data.open(f)
    return Configureable.conf

def disconnect(c=False):
    """ Close the database """
    m = __import__('__main__')
    if not m.connected:
        return

    if c == False:
        c = Configureable.conf
    # Note that `c' could be set in one of the previous branches;
    # don't try to simplify this logic.
    if c != False:
        c.closeDatabase()
    m.connected = False

def loadData(data, dataFormat):
    if data:
        config()['rdf.graph'].parse(data, format=dataFormat)

def connect(configFile=False,
            conf=False,
            do_logging=False,
            data=False,
            dataFormat='n3'):
    """ Load desired configuration and open the database """
    import logging
    import atexit
    import sys
    import importlib
    m = __import__('__main__')
    if m.connected == True:
        print "yarom already connected"
        return

    if do_logging:
        logging.basicConfig(level=logging.DEBUG)

    if conf:
        Configureable.conf = conf
        if not isinstance(conf, Data):
            # Initializes a Data object with
            # the Configureable.conf
            Configureable.conf = Data()
    elif configFile:
        loadConfig(configFile)
    else:
        try:
            from pkg_resources import Requirement, resource_filename
            filename = resource_filename(Requirement.parse("yarom"),"yarom/default.conf")
            Configureable.conf = Data.open(filename)
        except:
            logging.info("Couldn't load default configuration")
            traceback.print_exc()
            Configureable.conf = Data()

    Configureable.conf.openDatabase()
    logging.info("Connected to database")

    # have to register the right one to disconnect...
    atexit.register(disconnect)
    from .dataObject import DataObject, Property, SimpleProperty

    MappedClass.setUpDB()
    m.connected = True
    if data:
        loadData(data, dataFormat)
