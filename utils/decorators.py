from functools import update_wrapper
from tornado.web import (
    url, RedirectHandler, RequestHandler, authenticated as _authenticated)
from functools import wraps, partial
from tornado.gen import sleep
from inspect import iscoroutinefunction
import logging


# noinspection PyPep8Naming
class classonlymethod(classmethod):
    def __get__(self, instance, cls=None):
        if instance is not None:
            raise AttributeError("This method is available only on the class, not on instances.")
        return super().__get__(instance, cls)


def _update_method_wrapper(_wrapper, decorator):
    # _multi_decorate()'s bound_method isn't available in this scope. Cheat by
    # using it on a dummy function.
    @decorator
    def dummy(*args, **kwargs):
        pass

    update_wrapper(_wrapper, dummy)


def _multi_decorate(decorators, method):
    """
    Decorate `method` with one or more function decorators. `decorators` can be
    a single decorator or an iterable of decorators.
    """
    if hasattr(decorators, '__iter__'):
        # Apply a list/tuple of decorators if 'decorators' is one. Decorator
        # functions are applied so that the call order is the same as the
        # order in which they appear in the iterable.
        decorators = decorators[::-1]
    else:
        decorators = [decorators]

    def _wrapper(self, *args, **kwargs):
        # bound_method has the signature that 'decorator' expects i.e. no
        # 'self' argument.
        bound_method = method.__get__(self, type(self))
        for dec in decorators:
            bound_method = dec(bound_method)
        return bound_method(*args, **kwargs)

    # Copy any attributes that a decorator adds to the function it decorates.
    for dec in decorators:
        _update_method_wrapper(_wrapper, dec)
    # Preserve any existing attributes of 'method', including the name.
    update_wrapper(_wrapper, method)
    return _wrapper


def method_decorator(decorator, name=''):
    """
    Convert a function decorator into a method decorator
    """

    # 'obj' can be a class or a function. If 'obj' is a function at the time it
    # is passed to _dec,  it will eventually be a method of the class it is
    # defined on. If 'obj' is a class, the 'name' is required to be the name
    # of the method that will be decorated.
    def _dec(obj):
        if not isinstance(obj, type):
            return _multi_decorate(decorator, obj)
        if not (name and hasattr(obj, name)):
            raise ValueError(
                "The keyword argument `name` must be the name of a method "
                "of the decorated class: %s. Got '%s' instead." % (obj, name)
            )
        method = getattr(obj, name)
        if not callable(method):
            raise TypeError(
                "Cannot decorate '%s' as it isn't a callable attribute of "
                "%s (%s)." % (name, obj, method)
            )
        _wrapper = _multi_decorate(decorator, method)
        setattr(obj, name, _wrapper)
        return obj

    # Don't worry about making _dec look similar to a list/tuple as it's rather
    # meaningless.
    if not hasattr(decorator, '__iter__'):
        update_wrapper(_dec, decorator)
    # Change the name to aid debugging.
    obj = decorator if hasattr(decorator, '__name__') else decorator.__class__
    _dec.__name__ = 'method_decorator(%s)' % obj.__name__
    return _dec


class Route:
    """
    Decorates RequestHandlers and builds up a list of routables handlers
    Tech Notes (or "What the *@# is really happening here?")
    --------------------------------------------------------
    Everytime @route('...') is called, we instantiate a new route object which
    saves off the passed in URI. Then, since it's a decorator, the function is
    passed to the route.__call__ method as an argument. We save a reference to
    that handler with our uri in our class level routes list then return that
    class to be instantiated as normal.
    Later, we can call the classmethod route.get_routes to return that list of
    tuples which can be handed directly to the tornado.web.Application
    instantiation.

    Example:

    @route('/some/path')
    class SomeRequestHandler(RequestHandler):
        def get(self):
            goto = self.reverse_url('other')
            self.redirect(goto)

    # so you can do myapp.reverse_url('other')

    @route('/some/other/path', name='other')
    class SomeOtherRequestHandler(RequestHandler):
        def get(self):
            goto = self.reverse_url('SomeRequestHandler')
            self.redirect(goto)

    # for passing uri parameters

    @route(r'/some/(?P<parameterized>\w+)/path')
    class SomeParameterizedRequestHandler(RequestHandler):
        def get(self, parameterized):
            goto = self.reverse_url(parameterized)
            self.redirect(goto)

    my_routes = route.get_routes()
    """
    _routes = []

    def __init__(self, uri, name=None):
        self._uri = uri
        self.name = name

    def __call__(self, _handler):
        """Gets called when we class decorate"""
        name = self.name or _handler.__name__
        self._routes.append(url(self._uri, _handler, name=name))
        return _handler

    @classmethod
    def get_routes(cls):
        return cls._routes


route = Route


def route_redirect(from_, to, name=None):
    """
    route_redirect provided by Peter Bengtsson via the Tornado mailing list
    and then improved by Ben Darnell.
    Use it as follows to redirect other paths into your decorated handler.

    Example:

    from anthill.framework.utils.decorators import route, route_redirect

    route_redirect('/smartphone$', '/smartphone/')
    route_redirect('/iphone/$', '/smartphone/iphone/', name='iphone_shortcut')
    @route('/smartphone/$')
    class SmartphoneHandler(RequestHandler):
       def get(self):
           ...
    """
    route.get_routes().append(
        url(from_, RedirectHandler, dict(url=to), name=name))


def generic_route(uri, template, handler=None):
    """Maps a template to a route."""
    h_ = handler or RequestHandler

    @route(uri, name=uri)
    class GenericHandler(h_):
        _template = template

        def get(self):
            return self.render(self._template)

    return GenericHandler


def auth_generic_route(uri, template, handler):
    """
    Provides authenticated mapping of template render to route.
    :param: uri: the route path
    :param: template: the template path to render
    :param: handler: a subclass of tornado.web.RequestHandler that provides all
            the necessary methods for resolving current_user
    """

    @route(uri, name=uri)
    class AuthHandler(handler):
        _template = template

        @_authenticated
        def get(self):
            return self.render(self._template)

    return AuthHandler


def authenticated(methods=None):
    """
    Extension for tornado.web.authenticated decorator.
    :param methods: http method names list for tornado.web.authenticated decorator to apply
    """

    def decorator(wrapped):
        if issubclass(wrapped, RequestHandler):
            supported_methods = RequestHandler.SUPPORTED_METHODS
            for method_name in map(lambda x: x.lower(), methods or supported_methods):
                method = getattr(wrapped, method_name)
                setattr(wrapped, method_name, _authenticated(method))
            return wrapped
        else:
            _authenticated(wrapped)

    return decorator


def retry(max_retries=3, delay=3, on_exception=None, on_finish=None,
          raise_exception=False, exception_types=None):
    exception_types = exception_types or (Exception,)
    if not isinstance(exception_types, (tuple,)):
        raise ValueError(
            '`exception_types` must be a tuple, %s passed.' % type(exception_types))

    max_retries = max_retries or 9999

    def decorator(func):

        @wraps(func)
        async def wrapper(*args, **kwargs):
            exc = None
            for retries_count in range(1, max_retries + 1):
                try:
                    result = await func(*args, **kwargs)
                except exception_types as e:
                    exc = e
                    if on_exception is not None:
                        on_exception(func, e)
                    if delay:
                        await sleep(delay)
                else:
                    return result
            if on_finish is not None:
                on_finish(func, max_retries)
            if raise_exception:
                raise exc

        return wrapper

    return decorator


class ClassDecorator:
    """General class based decorator."""

    def __call__(self, func):
        if iscoroutinefunction(func):
            wrapper = self.async_wrapper
        else:
            wrapper = self.wrapper
        wrapper = wraps(func)(wrapper)
        wrapper = partial(wrapper, func)
        wrapper = self.transform_wrapper(wrapper)
        return wrapper

    # noinspection PyMethodMayBeStatic
    def transform_wrapper(self, wrapper):
        return wrapper

    # noinspection PyMethodMayBeStatic
    def wrapper(self, func, *args, **kwargs):
        return func(*args, **kwargs)

    # noinspection PyMethodMayBeStatic
    async def async_wrapper(self, func, *args, **kwargs):
        return await func(*args, **kwargs)
