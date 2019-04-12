# This code comes from <http://stackoverflow.com/a/6798042/108197>, which is
# licensed under the Creative Commons Attribution-ShareAlike License version
# 3.0 Unported.
#
# That is an answer originally authored by the user
# <http://stackoverflow.com/users/500584/agf> to the question
# <http://stackoverflow.com/q/6760685/108197>.


class _Singleton(type):
    """A metaclass for a singleton class."""

    #: The known instances of the class instantiating this metaclass.
    _instances = {}

    def __call__(cls, *args, **kwargs):
        """Returns the singleton instance of the specified class."""
        if cls not in cls._instances:
            cls._instances[cls] = super(_Singleton, cls).__call__(*args, **kwargs)
        return cls._instances[cls]


class Singleton(_Singleton('SingletonMeta', (object,), {})):
    """Base class for a singleton class."""
