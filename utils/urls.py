from anthill.framework.apps.builder import app
from .functional import lazy
from .module_loading import import_string
from tornado.web import URLSpec
from typing import Union, Optional
import functools
import re


def reverse(name: str, *args, **kwargs) -> str:
    """Returns a URL path for handler named ``name``."""
    url = app.reverse_url(name, *args, **kwargs)
    return url.rstrip('?')


reverse_lazy = lazy(reverse, str)


def to_urlspec(route: Union[URLSpec, list]) -> URLSpec:
    if isinstance(route, (list, tuple)):
        assert len(route) in (2, 3, 4)
        return URLSpec(*route)
    return route


def to_list(route: Union[URLSpec, list]) -> list:
    if isinstance(route, URLSpec):
        return [
            route.regex.pattern,
            route.target,
            route.kwargs,
            route.name
        ]
    assert len(route) in (2, 3, 4)
    return route


def include(routes: Union[str, list], namespace: Optional[str] = None) -> list:
    new_routes = []
    if isinstance(routes, str):
        routes = import_string(routes)
    for route in routes:
        route = to_urlspec(route)
        if isinstance(route.target, (list, tuple)):  # Other include
            for r in route.target:
                r = to_list(r)
                if len(r) == 4 and r[3] and namespace:
                    r[3] = ':'.join([namespace, r[3]])
                r[0] = '/'.join([
                    route.regex.pattern.rstrip('/$'),
                    re.sub(r'^(\^)?/', '', r[0])
                ])
                new_routes.append(URLSpec(*r))
        else:
            if route.name and namespace:
                route.name = ':'.join([namespace, route.name])
            new_routes.append(route)
    return new_routes


def root(pattern, namespace):
    def decorator(route_patterns):
        @functools.wraps(route_patterns)
        def wrapper():
            return [
                URLSpec(pattern, include(route_patterns(), namespace=namespace)),
            ]
        return wrapper
    return decorator


def build_absolute_uri(host_url: str, path: Optional[str] = None) -> str:
    """Build absolute URI with given (optional) path."""
    path = path or ''
    if path.startswith('http://') or path.startswith('https://'):
        return path
    if host_url.endswith('/') and path.startswith('/'):
        path = path[1:]
    return host_url + path
