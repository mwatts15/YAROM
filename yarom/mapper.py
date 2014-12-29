import rdflib as R
from yarom import DataUser
import yarom as P
import traceback

__all__ = [ "MappedClass", "DataObjects", "DataObjectsParents" ]

DataObjects = dict()
DataObjectsParents = dict()

def makeDatatypeProperty(*args,**kwargs):
    """ Create a SimpleProperty that has a simple type (string,number,etc) as its value

    Parameters
    ----------
    linkName : string
        The name of this Property.
    """
    return _create_property(*args,property_type='DatatypeProperty',**kwargs)

def makeObjectProperty(*args,**kwargs):
    """ Create a SimpleProperty that has a complex DataObject as its value

    Parameters
    ----------
    linkName : string
        The name of this Property.
    value_type : type
        The type of DataObject fro values of this property
    """
    return _create_property(*args,property_type='ObjectProperty',**kwargs)

def _create_property(owner_class, linkName, property_type, value_type=False, multiple=False):
    #XXX This should actually get called for all of the properties when their owner
    #    classes are defined.
    #    The initialization, however, must happen with the owner object's creation
    owner_class_name = owner_class.__name__
    property_class_name = owner_class_name + "_" + linkName
    if value_type == False:
        value_type = P.DataObject

    c = None
    if property_class_name in DataObjects:
        c = DataObjects[property_class_name]
    else:
        x = None
        if property_type == 'ObjectProperty':
            value_rdf_type = value_type.rdf_type
            x = P.ObjectProperty
        else:
            value_rdf_type = False
            x = P.DatatypeProperty

        c = type(property_class_name,(x,),dict(linkName=linkName, property_type=property_type, value_rdf_type=value_rdf_type, owner_type=owner_class, multiple=multiple))

    owner_class.dataObjectProperties.append(c)

    return c

class MappedClass(type):
    """A type for DataObjects

    Sets up the graph with things needed for DataObjects
    """
    def __init__(cls, name, bases, dct):
        type.__init__(cls,name,bases,dct)

        cls.dataObjectProperties = []
        #print 'doing init for', cls
        for x in bases:
            try:
                cls.dataObjectProperties += x.dataObjectProperties
            except AttributeError:
                pass
        cls.register().map()

    @classmethod
    def setUpDB(self):
        pass

    @classmethod
    def makeClass(cls, name, bases, objectProperties=False, datatypeProperties=False):
        """ Intended to be used for setting up a class from the RDF graph, for instance. """
        # Need to distinguish datatype and object properties...
        if not datatypeProperties:
            datatypeProperties = []
        if not objectProperties:
            objectProperties = []
        MappedClass(name, bases, dict(objectProperties=objectProperties, datatypeProperties=datatypeProperties))

    @property
    def du(self):
        # This is just a little indirection to make sure we initialize the DataUser property before using it.
        # Initialization isn't done in __init__ because I wanted to make sure you could call `connect` before
        # or after declaring your classes
        if hasattr(self,'_du'):
            return self._du
        else:
            raise Exception("You should have called `map` to get here")

    @du.setter
    def du_set(self, value):
        assert(isinstance(value,DataUser))
        self._du = value

    def __lt__(cls, other):
        return issubclass(cls, other)

    def register(cls):
        """ Registers the class as a DataObject to be included in the configured rdf graph
        """
        DataObjects[cls.__name__] = cls
        DataObjectsParents[cls.__name__] = [x for x in cls.__bases__ if isinstance(x, MappedClass)]
        cls.parents = DataObjectsParents[cls.__name__]
        return cls

    def map(cls):
        """ Performs those actions necessary for storing the class and its instances in the graph
        """
        cls._du = DataUser()
        cls.rdf_type = cls.conf['rdf.namespace'][cls.__name__]
        cls.rdf_namespace = R.Namespace(cls.rdf_type + "/")

        cls.addParentsToGraph()

        cls.addObjectProperties()
        cls.addDatatypeProperties()

        cls.addPropertiesToGraph()
        cls.addNamespaceToManager()

        setattr(P, cls.__name__, cls)
        return cls

    @classmethod
    def remap(metacls):
        """ Calls `map` on all of the registered classes """
        classes = sorted(list(DataObjects.values()))
        for x in classes:
            x.map()

    def addNamespaceToManager(cls):
        cls.conf['rdf.namespace_manager'].bind(cls.__name__, cls.rdf_namespace)

    def addPropertiesToGraph(cls):
        deets = []
        for x in cls.dataObjectProperties:
            deets.append((x.rdf_type, cls.conf['rdf.namespace']['domain'], cls.rdf_type))
        cls.du.add_statements(deets)

    def addParentsToGraph(cls):
        deets = []
        for y in cls.parents:
            deets.append((cls.rdf_type, R.RDFS['subClassOf'], y.rdf_type))
        cls.du.add_statements(deets)

    def addObjectProperties(cls):
        try:
            if hasattr(cls, 'objectProperties'):
                assert(isinstance(cls.objectProperties,(tuple,list,set)))
                for x in cls.objectProperties:
                    if isinstance(x,tuple):
                        makeObjectProperty(cls,x[0], value_type=x[1])
                    else:
                        makeObjectProperty(cls,x)
        except:
            traceback.print_exc()

    def addDatatypeProperties(cls):
        # Also get all of the properites
        try:
            if hasattr(cls, 'datatypeProperties'):
                assert(isinstance(cls.datatypeProperties,(tuple,list,set)))
                for x in cls.datatypeProperties:
                    makeDatatypeProperty(cls,x)
        except:
            traceback.print_exc()

    def _cleanupGraph(cls):
        """ Cleans up the graph by removing statements that can't be connected to typed statement. """
        q = """
        DELETE { ?b ?x ?y }
        WHERE
        {
            ?b ?x ?y .
            FILTER (NOT EXISTS { ?b rdf:type ?c } ) .
        }
          """
        cls.du.rdf.update(q)
