# a class for modules that need outside objects to parameterize their behavior (because what are generics?)
# Modules inherit from this class and use their self['expected_configured_property']
import traceback
class ConfigValue(object):
    def get(self):
        raise NotImplementedError

class _C(ConfigValue):
    def __init__(self, v):
        self.v = v
    def get(self):
        return self.v
    def __str__(self):
        return str(self.v)
    def __repr__(self):
        return str(self.v)


class BadConf(Exception):
    pass

class _link(ConfigValue):
    def __init__(self,members,c):
        self.members = members
        self.conf = c
    def get(self):
        return self.conf[self.members[0]]

class Configuration(object):
    """ Configuration """
    # conf: is a configure instance to base this one on
    # dependencies are required for this class to be initialized (TODO)

    def __init__(self, **kwargs):
        for x in kwargs:
            if not isinstance(kwargs[x],ConfigValue):
                kwargs[x] = _C(kwargs[x])
        self._properties = kwargs

    def __setitem__(self, pname, value):
        if not isinstance(value, ConfigValue):
            value = _C(value)
        if (pname in self._properties) and isinstance(self._properties[pname], _link):
            for x in self._properties[pname].members:
                self._properties[x] = value
        else:
            self._properties[pname] = value

    def __getitem__(self, pname):
        return self._properties[pname].get()

    def __iter__(self):
        return iter(self._properties)

    def link(self,*names):
        """ Call link() with the names of configuration values that should
        always be the same to link them together
        """
        l = _link(names,self)
        for n in names:
            self._properties[n] = l

    def __contains__(self, thing):
        return (thing in self._properties)

    def __str__(self):
        return "\n".join("%s = %s" %(k,self._properties[k]) for k in self._properties)

    def __len__(self):
        return len(self._properties)

    @classmethod
    def open(cls,file_name):
        import json
        f = open(file_name)
        c = Configuration()
        d = json.load(f)
        for k in d:
            value = d[k]
            if isinstance(value,basestring):
                if value.startswith("BASE/"):
                    from pkg_resources import Requirement, resource_filename
                    value = value[4:]
                    value = resource_filename(Requirement.parse('yarom'), value)
                    d[k] = value
            c[k] = _C(d[k])
        f.close()
        c['configure.file_location'] = file_name
        return c

    def copy(self,other):
        if isinstance(other,Configuration):
            self._properties = dict(other._properties)
        elif isinstance(other,dict):
            for x in other:
                self[x] = other[x]
        return self

    def get(self, pname, default=None):
        if pname in self._properties:
            return self._properties[pname].get()
        elif (default is not None):
            return default
        else:
            print self._properties
            raise KeyError(pname)

class Configureable(object):
    """ An object which can accept configuration """
    conf = False
    def __init__(self, conf=False):
        if conf:
            self.conf = conf
        elif Configureable.conf:
            self.conf = Configureable.conf
        else:
            self.conf = Configuration()

    def __getitem__(self,k):
        return self.conf.get(k)

    def __setitem__(self,k,v):
        self.conf[k] = v

    def get(self, pname, default=False):
        return self.conf.get(pname,default)
