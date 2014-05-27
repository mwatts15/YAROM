# a class for modules that need outside objects to parameterize their behavior (because what are generics?)
# Modules inherit from this class and use their self['expected_configured_property']
class ConfigValue(object):
    def get(self):
        raise NotImplementedError

class _C(ConfigValue):
    def __init__(self, v):
        self.v = v
    def get(self):
        return self.v

class BadConf(BaseException):
    pass

class Configureable:
    def __getitem__(self, k):
        return self.conf.get(k)

    def __setitem__(self, k, v):
        self.conf[k] = v

    def get(self, pname, default=False):
        return self.conf.get(pname,default)

    def __init__(self, conf = False):
        if not conf:
            self.conf = Configure()
        elif isinstance(conf, Configure):
            self.conf = conf
        else:
            raise BadConf(self)

class Configure:
    # conf: is a configure instance to base this one on
    # dependencies are required for this class to be initialized (TODO)
    def __init__(self, dependencies={}):
        self._properties = {}

    def __setitem__(self, pname, value):
        if not isinstance(value, ConfigValue):
            value = _C(value)
        self._properties[pname] = value

    def __getitem__(self, pname):
        return self._properties[pname].get()

    def __contains__(self, thing):
        return (thing in self._properties)
    def get(self, pname, default=False):
        if pname in self._properties:
            return self._properties[pname].get()
        elif default:
            return default
        else:
            raise KeyError(pname)
