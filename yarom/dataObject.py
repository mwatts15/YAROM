import rdflib as R
import traceback
import logging as L
import hashlib
import random
from .mapper import *
from .dataUser import DataUser

# in general it should be possible to recover the entire object from its identifier: the object should be representable as a connected graph.
# However, this need not be a connected *RDF* graph. Indeed, graph literals may hold information which can yield triples which are not
# connected by an actual node

def _bnode_to_var(x):
    return "?" + x

def _serialize_rdflib_term(x, namespace_manager=None):
    if isinstance(x, R.BNode):
        return _bnode_to_var(x)
    elif isinstance(x, R.URIRef) and DataObject._is_variable(x):
        return DataObject._graph_variable_to_var(x)
    else:
        return x.n3(namespace_manager)

def _deserialize_rdflib_term(x):
    if isinstance(x, R.Literal):
        x = x.toPython()
        if isinstance(x, R.Literal):
            x = str(x)
    return x

def triples_to_bgp(trips, namespace_manager=None):
    # XXX: Collisions could result between the variable names of different objects
    g = ""
    for y in trips:
        g += " ".join(_serialize_rdflib_term(x, namespace_manager) for x in y) + " .\n"
    return g


class IdentifierMissingException(Exception):
    """ Indicates that an identifier should be set available for the object in question, but there is none """
    def __init__(self, dataObject="[unspecified object]", query=False, *args, **kwargs):
        mode = "query mode" if query else "non-query mode"
        super().__init__("An identifier should be provided for {} when used in {}".format(str(dataObject), mode), *args, **kwargs)

def get_hash_function(method_name):
    if method_name == "sha224":
        return hashlib.sha224
    elif method_name == "md5":
        return hashlib.md5
    elif method_name in hashlib.algorithms_available:
        return (lambda data: hashlib.new(method_name, data))

class DataObject(DataUser, metaclass=MappedClass):
    """ An object backed by the database

    Attributes
    -----------
    rdf_type : rdflib.term.URIRef
        The RDF type URI for objects of this type
    rdf_namespace : rdflib.namespace.Namespace
        The rdflib namespace (prefix for URIs) for objects from this class
    properties : list of Property
        Properties belonging to this object
    owner_properties : list of Property
        Properties belonging to parents of this object
    """

    _openSet = set()
    _closedSet = set()
    i = 0

    configuration_variables = {
            "rdf.namespace" : {
                "description" : "Namespaces for DataObject sub-classes will be based off of this. For example, a subclass named A would have a namespace '[rdf.namespace]A/'",
                "type" : R.Namespace,
                "directly_configureable" : True
                },
            "dataObject.identifier_hash" : {
                "description" : "The hash method used for object identifiers. Defaults to md5.",
                "type" : "sha224, md5, or one of the types accepted by hashlib.new()",
                "directly_configureable" : True
                },
            }
    identifier_hash_method = get_hash_function(DataUser.conf.get('dataObject.identifier_hash', 'md5'))

    @classmethod
    def openSet(self):
        """ The open set contains items that must be saved directly in order for their data to be written out """
        return self._openSet

    def __init__(self,ident=False,var=False,triples=False,key=False,generate_key=False,**kwargs):
        try:
            DataUser.__init__(self,**kwargs)
        except BadConf as e:
            raise Exception("You may need to connect to a database before continuing.")

        if not triples:
            self._triples = []
        else:
            self._triples = triples

        self.properties = []
        self.owner_properties = []

        if not isinstance(self, SimpleProperty):
            self.relate('rdf_type_property', self.rdf_type_object, RDFTypeProperty)

        self._id = False
        if ident:
            if isinstance(ident, R.URIRef):
                self._id = ident
            else:
                self._id = R.URIRef(ident)
        elif var:
            self._id_variable = R.Variable(var)
        elif key: # TODO: Support a key function that generates the key based on live values of the object (e.g., property values)
            self.setKey(key)
        elif generate_key:
            self.setKey(random.random())
        else:
            # Randomly generate an identifier if the derived class can't
            # come up with one from the start. Ensures we always have something
            # that functions as an identifier
            v = (random.random(), random.random())
            cname = self.__class__.__name__
            self._id_variable = self._graph_variable(cname + "_" + hashlib.md5(str(v).encode()).hexdigest())

        for x in self.__class__.dataObjectProperties:
            prop = x(owner=self)
            self.properties.append(prop)
            if hasattr(self, prop.linkName):
                raise Exception("Cannot attach property '{}'. A property must have a different name from any attributes in DataObject".format(prop.linkName))
            setattr(self, prop.linkName, prop)

        for x in self.properties:
            if x.linkName in kwargs:
                self.relate(x.linkName, kwargs[x.linkName])

    @property
    def _id_is_set(self):
        """ Indicates whether the identifier will return a URI appropriate for use by YAROM

        Sub-classes should not override this method.
        """
        return self._id != False

    @property
    def defined(self):
        return self._id != False

    @property
    def idl(self):
        if self._id:
            return self._id
        else:
            return self._id_variable
    @property
    def p(self):
        return self.owner_properties

    @property
    def o(self):
        return self.properties

    def setKey(self, key):
        if isinstance(key, str):
            self._id = self.make_identifier_direct(key)
        else:
            self._id = self.make_identifier(key)

    def relate(self, linkName, other, prop=False):
        cls = type(self)

        existing_property_names = [x.linkName for x in self.properties]
        if linkName in existing_property_names:
            p = getattr(self, linkName)
        else:
            if not prop:
                if isinstance(other, DataObject):
                    prop = makeObjectProperty(cls, linkName, value_type=type(other), multiple=True)
                else:
                    prop = makeDatatypeProperty(cls, linkName, multiple=True)
            p = prop(owner=self)
            self.properties.append(p)
            setattr(self, linkName, p)
        p.set(other)



    def get_defined_component(self):
        g = SV()(self)
        g.namespace_manager = self.namespace_manager
        return g

    def __eq__(self,other):
        return isinstance(other,DataObject) and (self.idl == other.idl)

    def __hash__(self):
        return hash(self.idl)

    def __lt__(self, other):
        return hash(self.identifier()) < hash(other.identifier())

    def __str__(self):
        return self.namespace_manager.normalizeUri(self.idl)

    def __repr__(self):
        return self.__str__()

    def _graph_variable(self,var_name):
        return R.Variable(var_name)

    @classmethod
    def object_from_id(cls,*args,**kwargs):
        return cls.oid(*args,**kwargs)

    @classmethod
    def addToOpenSet(cls,o):
        cls._openSet.add(o)

    @classmethod
    def removeFromOpenSet(cls,o):
        if o not in cls._closedSet:
            cls._openSet.remove(o)
            cls._closedSet.add(o)

    @classmethod
    def oid2(cls, identifier, rdf_type=False):
        """ Load an object from the database using its type tag """
        # XXX: This is a class method because we need to get the conf
        # We should be able to extract the type from the identifier
        if rdf_type:
            uri = rdf_type
        else:
            uri = identifier

        c = RDFTypeTable[uri]
        # if its our class name, then make our own object
        # if there's a part after that, that's the property name
        o = c(ident=identifier)
        return o

    @classmethod
    def oid(cls, identifier, rdf_type=False):
        """ Load an object from the database using its type tag """
        # XXX: This is a class method because we need to get the conf
        # We should be able to extract the type from the identifier
        if rdf_type:
            uri = rdf_type
        else:
            uri = identifier

        cn = cls.extract_class_name(uri)
        # if its our class name, then make our own object
        # if there's a part after that, that's the property name
        o = DataObjects[cn](ident=identifier)
        return o

    @classmethod
    def extract_class_name(cls, uri):
        ns = str(cls.conf['rdf.namespace'])
        if uri.startswith(ns):
            class_name = uri[len(ns):]
            name_end_idx = class_name.find('/')
            if name_end_idx > 0:
                class_name = class_name[:name_end_idx]
            return class_name
        else:
            raise ValueError("URI must be like '"+ns+"<className>' optionally followed by a hash code")
    @classmethod
    def extract_unique_part(cls, uri):
        if uri.startswith(cls.rdf_namespace):
            return uri[:len(cls.rdf_namespace)]
        else:
            raise Exception("This URI ({}) doesn't start with the appropriate namespace ({})".format(uri, cls.rdf_namespace))

    @classmethod
    def _is_variable(cls, uri):
        """ Is the uriref a graph variable? """
        if isinstance(uri, R.Variable):
            return True
        from urllib.parse import urlparse
        u = urlparse(uri)
        x = u.path.split('/')
        return len(x) >= 3 and (x[2] == 'variable')

    @classmethod
    def _graph_variable_to_var(cls, uri):
        return uri

    @classmethod
    def make_identifier(cls, data):
        return R.URIRef(cls.rdf_namespace["a"+cls.identifier_hash_method(str(data).encode()).hexdigest()])

    @classmethod
    def make_identifier_direct(cls, string):
        if not isinstance(string, str):
            raise Exception("make_identifier_direct only accepts strings")
        from urllib.parse import quote
        return R.URIRef(cls.rdf_namespace[quote(string)])

    def identifier(self, query=False):
        """
        The identifier for this object in the rdf graph.

        This identifier may be randomly generated, but an identifier returned from the
        graph can be used to retrieve the specific object that it refers to.

        Sub-classes of DataObject may override this to construct identifiers based
        on some other key.
        """
        if query and not self._id_is_set:
            return self._id_variable
        elif self._id_is_set:
            return self._id
        else:
            # XXX: Make no mistake: not having an identifier here is an error.
            # You may, however, need to sub-class DataObject to make an
            # appropriate identifier method.
            raise IdentifierMissingException(self.__class__, query)

    def triples(self, query=False, visited_list=False):
        """
        Should be overridden by derived classes to return appropriate triples

        Returns
        --------
        An iterable of triples
        """
        if visited_list == False:
            visited_list = set()

        if self.identifier(query=query) in visited_list:
            return
        else:
            visited_list.add(self.identifier(query=query))

        ident = self.identifier(query=query)
        yield (ident, R.RDF['type'], self.rdf_type)

        # For objects that are defined by triples, we can just release these.
        # However, they are still data objects, so they must have the above
        # triples released as well.
        for x in self._triples:
            yield x

        # Properties (of type Property) can be attached to an object
        # However, we won't require that there even is a property list in this
        # case.
        if hasattr(self, 'properties'):
            for x in self.properties:
                if x.hasValue():
                    yield (ident, x.link, x.identifier(query=query))
                    for y in x.triples(query=query, visited_list=visited_list):
                        yield y

    def graph_pattern(self, query=False, shorten=False):
        """ Get the graph pattern for this object.

        It should be as simple as converting the result of triples() into a BGP

        Parameters
        ----------
        query : bool
            Indicates whether or not the graph_pattern is to be used for querying
            (as in a SPARQL query) or for storage
        shorten : bool
            Indicates whether to shorten the URLs with the namespace manager
            attached to the ``self``
        """

        nm = None
        if shorten:
            nm = self.namespace_manager
        return triples_to_bgp(self.triples(query=query), namespace_manager=nm)

    def save(self):
        """ Write in-memory data to the database. Derived classes should call this to update the store. """
        self.add_statements(self.get_defined_component())

    def load(self):
        """ Load in data from the database. Derived classes should override this for their own data structures.

        ``load()`` returns an iterable object which yields DataObjects which have the same class as the object and have, for the Properties set, the same values

        :param self: An object which limits the set of objects which can be returned. Should have the configuration necessary to do the query
        """
        if not DataObject._is_variable(self.identifier(query=True)):
            yield self
        else:
            gp = self.graph_pattern(query=True)
            ident = self.identifier(query=True)
            q = "SELECT DISTINCT {0} where {{ {1} }}".format(ident.n3(), gp)
            qres = self.rdf.query(q)
            for g in qres:
                new_ident = g[0]
                new_object = self.object_from_id(new_ident)
                yield new_object

    def load2(self):
        for ident in _QueryDoer(self)():
            types = set()
            for rdf_type in self.rdf.objects(ident, R.RDF['type']):
                types.add(rdf_type)
            the_type = get_most_specific_rdf_type(types)
            yield DataObject.oid2(ident, the_type)

    def retract(self):
        """ Remove this object from the data store.

        Retract removes an object and everything it points to, transitively,
        which doesn't have pointers to it by something else.
        """
        self.retract_statements(self.get_defined_component())

    def __getitem__(self, x):
        try:
            return DataUser.__getitem__(self, x)
        except KeyError:
            raise Exception("You attempted to get the value `%s' from `%s'. It isn't here. Perhaps you misspelled the name of a Property?" % (x, self))

    def getOwners(self, property_name):
        """ Return the owners along a property pointing to this object """
        res = []
        for x in self.owner_properties:
            if isinstance(x, SimpleProperty):
                if str(x.linkName) == str(property_name):
                    res.append(x.owner)
        return res

def get_most_specific_rdf_type(types):
    """ Gets the most specific rdf_type.

    Returns the URI corresponding to the lowest in the DataObject class hierarchy
    from among the given URIs.
    """
    return sorted([RDFTypeTable[x] for x in types])[0].rdf_type

# Define a property by writing the get
class Property(DataObject):
    """ Store a value associated with a DataObject

    Properties can be be accessed like methods. A method call like::

        a.P()

    for a property ``P`` will return values appropriate to that property for ``a``,
    the `owner` of the property.

    Parameters
    ----------
    owner : yarom.dataObject.DataObject
        The owner of this property
    name : string
        The name of this property. Can be accessed as an attribute like::

            owner.name

    """

    # Indicates whether the Property is multi-valued
    multiple = False

    def __init__(self, name=False, owner=False, **kwargs):
        DataObject.__init__(self, **kwargs)
        self.owner = owner
        # XXX: Default implementation is a box for a value
        self._value = False

    def get(self,*args):
        """ Get the things which are on the other side of this property

        The return value must be iterable. For a ``get`` that just returns
        a single value, an easy way to make an iterable is to wrap the
        value in a tuple like ``(value,)``.

        Derived classes must override.
        """
        # This should run a query or return a cached value
        raise NotImplementedError()
    def set(self,*args,**kwargs):
        """ Set the value of this property

        Derived classes must override.
        """
        # This should set some values and call DataObject.save()
        raise NotImplementedError()

    def one(self):
        """ Returns a single value for the ``Property`` whether or not it is multivalued.
        """

        try:
            r = self.get()
            return next(iter(r))
        except StopIteration:
            return None

    def hasValue(self):
        """ Returns true if the Property has any values set on it.

        This may be defined differently for each property
        """
        return True

    def __call__(self,*args,**kwargs):
        """ If arguments are passed to the ``Property``, its ``set`` method
        is called. Otherwise, the ``get`` method is called. If the ``multiple``
        member for the ``Property`` is set to ``True``, then a Python set containing
        the associated values is returned. Otherwise, a single bare value is returned.
        """

        if len(args) > 0 or len(kwargs) > 0:
            self.set(*args,**kwargs)
            return self
        else:
            r = self.get(*args,**kwargs)
            if self.multiple:
                return set(r)
            else:
                try:
                    return next(iter(r))
                except StopIteration:
                    return None

    # Get the property (a relationship) itself

class SimpleProperty(Property):
    """ A property that has one or more links to literals or DataObjects """

    def __init__(self,**kwargs):

        # The 'linkName' must be made up from the class name if one isn't set
        # before initialization (typically in mapper._create_property)
        if not hasattr(self, 'linkName'):
            self.__class__.linkName = self.__class__.__name__ + "property"

        Property.__init__(self, name=self.linkName, **kwargs)

        # The 'value_property' is the URI used in the RDF graph pointing
        # from this property to its value. It is a different value for
        # each property type.
        self.value_property = self.rdf_namespace['value']

        # 'v' holds values that have been set on this SimpleProperty. It acts
        # as a sort of staging area before saving the values to the graph.
        self._v = []

        v = (random.random(), random.random())
        self._value = Variable("_" + hashlib.md5(str(v).encode()).hexdigest())

    def hasValue(self):
        """ Returns true if the ``Property`` has had ``load`` called previously and some value was available or if ``set`` has been called previously """
        return len(self._v) > 0

    def _get(self):
        for x in self._v:
            yield x

    @property
    def value(self):
        return self._value

    @property
    def values(self):
        return self._v

    def setValue(self, v):
        self.set(v)

    @classmethod
    def _id_hash(cls, value):
        assert(isinstance(value, str))
        return hashlib.md5(value.encode()).hexdigest()

    def get(self):
        """ If the ``Property`` has had ``load`` or ``set`` called previously, returns
        the resulting values. Also queries the configured rdf graph for values
        which are set for the ``Property``'s owner.
        """

        v = Variable("var"+str(id(self)))
        self.set(v)
        results = _QueryDoer(v, self.rdf)()
        self.unset(v)

        if self.property_type == 'ObjectProperty':
            for ident in results:
                types = set()
                for rdf_type in self.rdf.objects(ident, R.RDF['type']):
                    types.add(rdf_type)
                the_type = get_most_specific_rdf_type(types)
                yield DataObject.oid2(ident, the_type)
        else:
            for val in results:
                yield _deserialize_rdflib_term(val)

    def unset(self, v):
        idx = self._v.index(v)
        if idx >= 0:
            actual_val = self._v[idx]
            actual_val.p.remove(self)
            self._v.remove(actual_val)
        else:
            raise Exception("Can't find value {}".format(v))

    def set(self,v):
        import bisect
        if not hasattr(v, "idl"):
            v = PropertyValue(v)

        v.p.append(self)

        if self.multiple:
            bisect.insort(self._v, v)
        else:
            self._v = [v]

    def triples(self,*args,**kwargs):
        """ Yields the triples for describing a simple property """

        query=kwargs.get('query',False)

        if not (query or self.hasValue()):
            return

        if not kwargs.get('visited_list', False):
            kwargs['visited_list'] = set()

        if self.identifier(query=query) in kwargs['visited_list']:
            return
        else:
            kwargs['visited_list'].add(self.identifier(query=query))


        ident = self.identifier(query=query)

        def yield_triples_helper(propertyValue):
            try:
                yield (ident, self.value_property, propertyValue.identifier(query=query))
                for t in propertyValue.triples(*args, **kwargs):
                    yield t
            except Exception:
                traceback.print_exc()

        if query and (len(self._v) == 0):
            part = self._id_hash(self.identifier(query=query))
            v = Variable(part+"_value")
            for t in yield_triples_helper(v):
                yield t

            for x in self.owner.triples(*args, **kwargs):
                yield x
        elif len(self._v) > 0:
            for x in Property.triples(self,*args, **kwargs):
                yield x

            if self.multiple:
                for x in self._v:
                    for triple in yield_triples_helper(x):
                        yield triple
            else:
                for triple in yield_triples_helper(self._v[0]):
                    yield triple


    def identifier(self,query=False):
        """ Return the URI for this object

        Parameters
        ----------
        query: bool
            Indicates whether the identifier is to be used in a query or not
        """
        if self._id_is_set:
            return DataObject.identifier(self,query=query)
        vlen = len(self._v)

        if vlen > 0:
            value_data = "".join(str(x.identifier(query=query)) for x in self._v if self is not x)
            return self.make_identifier((self.link, value_data))
        return DataObject.identifier(self,query=query)

    def __eq__(self, other):
        return isinstance(other, self.__class__) and self.link == other.link

    def __hash__(self):
        return hash(self.link)

    def __str__(self):
        return str(self.linkName + "(" + str(" ".join(repr(x) for x in self._v)) + ")")

    #def __str__(self):
        #return str(self.linkName + "=" + "`" + str(self._val) + "'")

class RDFTypeProperty(SimpleProperty):
    link = R.RDF['type']
    linkName = "rdf_type"
    property_type = 'ObjectProperty'
    owner_type = DataObject
    multiple = True

class DatatypeProperty(SimpleProperty):
    pass

class ObjectProperty(SimpleProperty):
    pass

class Variable(object):
    def __init__(self, name):
        self.var = R.Variable(name)
        self.p = []
        self.o = []

    def identifier(self, *args, **kwargs):
        return self.var

    @property
    def defined(self):
        return False

    @property
    def idl(self):
        return self.var

    def triples(self, *args, **kwargs):
        return []

    def __hash__(self):
        return hash(self.var)

    def __str__(self):
        return str(self.var)

    def __repr__(self):
        return str(self)

    def __lt__(self, other):
        return self.var < other.var

class PropertyValue(object):
    """ Holds a literal value for a property """
    def __init__(self, value=None):
            self.value = R.Literal(value)
            self.p = []
            self.o = []

    def triples(self, *args, **kwargs):
        return []

    def identifier(self, query=False):
        return self.value

    @property
    def defined(self):
        return True

    @property
    def idl(self):
        return self.identifier()

    def __hash__(self):
        return hash(self.value)

    def __str__(self):
        return "<" + str(self.value) + ">"

    def __repr__(self):
        return str(self)

    def __lt__(self, other):
        return self.value < other.value

    def __eq__(self, other):
        if id(self) == id(other):
            return True
        elif isinstance(other, PropertyValue):
            return self.value == other.value
        else:
            return self.value == R.Literal(other)

class ObjectCollection(DataObject):
    """
    A convenience class for working with a collection of objects

    Example::

        v = values('unc-13 neurons and muscles')
        n = P.Neuron()
        m = P.Muscle()
        n.receptor('UNC-13')
        m.receptor('UNC-13')
        for x in n.load():
            v.value(x)
        for x in m.load():
            v.value(x)
        # Save the group for later use
        v.save()
        ...
        # get the list back
        u = values('unc-13 neurons and muscles')
        nm = list(u.value())


    Parameters
    ----------
    group_name : string
        A name of the group of objects

    Attributes
    ----------
    name : DatatypeProperty
        The name of the group of objects
    group_name : DataObject
        an alias for ``name``
    value : ObjectProperty
        An object in the group
    add : ObjectProperty
        an alias for ``value``

    """
    objectProperties = ['member']
    datatypeProperties = ['name']
    def __init__(self,group_name,**kwargs):
        DataObject.__init__(self,key=group_name,**kwargs)
        self.add = self.member
        self.group_name = self.name
        self.name(group_name)

    def identifier(self, query=False):
        return self.make_identifier(self.group_name)

class QN(tuple):
    def __new__(cls):
        return tuple.__new__(cls, ([],[]))

    @property
    def subpaths(self):
        return self[0]
    @subpaths.setter
    def subpaths(self, toset):
        del self[0][:]
        self[0].extend(toset)

    @property
    def path(self):
        return self[1]

class QINV(R.URIRef):
    pass

class QU(object):
    def __init__(self, start):
        self.seen = list()
        self.lean = list()
        self.paths = list()
        self.start = start

    def b(self, CUR, LIST, IS_INV):
        ret = []
        is_good = False
        #print("b(", ",".join((str(x) for x in [CUR.idl, LIST, IS_INV])), ")")
        for e in LIST:
            if IS_INV:
                p = [e.owner]
            else:
                p = e.values

            for x in p:
                if IS_INV:
                    self.lean.append((x.idl, e.link, None))
                else:
                    self.lean.append((None, e.link, x.idl))

                subpath = self.g(x)
                if len(self.lean) > 0:
                    self.lean.pop()

                if subpath[0]:
                    is_good = True
                    subpath[1].path.insert(0, (CUR.idl, e, x.idl))
                    ret.insert(0, subpath[1])
        return is_good, ret

    def k(self):
        pass

    def g(self, current_node):
        #print((" "*len(self.seen)*4)+"AT {} WITH {}".format(current_node, [x.idl for x in self.seen]))

        if current_node.defined:
            if len(self.lean) > 0:
                tmp = list(self.lean)
                self.paths.append(tmp)
            return True, QN()
        else:
            if current_node in self.seen:
                return False, QN()
            else:
                self.seen.append(current_node)

            retp = self.b(current_node, current_node.p, True)
            reto = self.b(current_node, current_node.o, False)

            self.seen.pop()
            subpaths = retp[1]+reto[1]
            if (len(subpaths) == 1):
                ret = subpaths[0]
            else:
                ret = QN()
                ret.subpaths = subpaths
            return (retp[0] or reto[0], ret)

    def __call__(self):
        #print("AT {} WITH {}".format(current_node.idl, [x.idl for x in seen]))
        self.g(self.start)
        return self.paths

class _QueryDoer(object):
    def __init__(self, q, graph=None):
        self.query_object = q

        if graph is not None:
            self.graph = graph
        elif isinstance(q, DataObject):
            self.graph = q.rdf
        else:
            raise Exception("Can't get a graph to query. Either provide one to _QueryDoer or provide a DataObject as the query object.")

    def do_query(self):
        qu = QU(self.query_object)
        h = self.hoc(qu())
        return self.qpr(self.graph, h)

    def hoc(self,l):
        res = dict()
        for x in l:
            if len(x) > 0:
                tmp = res.get(x[0], [])
                tmp.append(x[1:])
                res[x[0]] = tmp

        for x in res:
            res[x] = self.hoc(res[x])

        return res

    def qpr(self, g, h, i=0):
        join_args = []
        for x in h:
            sub_answers = set()
            sub = h[x]
            idx = x.index(None)
            if idx == 2:
                other_idx = 0
            else:
                other_idx = 2

            if isinstance(x[other_idx], R.Variable):
                for z in self.qpr(g, sub, i+1):
                    if idx == 2:
                        qx = (z, x[1], None)
                    else:
                        qx = (None, x[1], z)

                    for y in g.triples(qx):
                        sub_answers.add(y[idx])
            else:
                for y in g.triples(x):
                    sub_answers.add(y[idx])
            join_args.append(sub_answers)

        if len(join_args) > 0:
            res = join_args[0]
            for x in join_args[1:]:
                res = res & x
            return res
        else:
            return set()

    def __call__(self):
        return self.do_query()

class SV(object):
    def __init__(self):
        self.seen = set()
        self.results = R.Graph()

    def g(self, current_node):
        if current_node in self.seen:
            return
        else:
            self.seen.add(current_node)

        if not current_node.defined:
            return

        for e in current_node.p:
            p = e.owner
            if p.defined:
                self.results.add((p.idl, e.link, current_node.idl))
                self.g(p)

        for e in current_node.o:
            for val in e.values:
                if val.defined:
                    self.results.add((current_node.idl, e.link, val.idl))
                    self.g(val)

    def __call__(self, current_node):
        self.g(current_node)
        return self.results
