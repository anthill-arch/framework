from anthill.framework.core.cache import cache
from anthill.framework.utils.asynchronous import thread_pool_exec as async_exec
from anthill.framework.utils.encoding import force_bytes, iri_to_uri
from anthill.framework.conf import settings
from anthill.framework.http import HttpNotAllowedError
from anthill.framework.utils.timezone import get_current_timezone_name
from functools import wraps, partial
import inspect
import hashlib
import re

__all__ = [
    'cached', 'cached_method', 'request_handler_cache_key',
    'patch_vary_headers'
]


def _cached(timeout, key, cache=cache, key_prefix=None, handler_method=False, http_method=None):
    def decorator(func):
        def get_key(handler):
            if callable(key):
                return key(handler, timeout, key_prefix, cache) if handler_method else key()
            return key

        def validate_http_method(handler):
            if handler_method and handler.request.method != http_method:
                raise HttpNotAllowedError(
                    'Not allowed method: %s' % handler.request.method)

        @wraps(func)
        def wrapper(*args, **kwargs):
            validate_http_method(args[0])
            k = get_key(args[0])
            result = cache.get(k)
            if result is None:
                result = func(*args, **kwargs)
                cache.set(k, result, timeout)
            return result

        @wraps(func)
        async def wrapper_async(*args, **kwargs):
            validate_http_method(args[0])
            k = get_key(args[0])
            result = await async_exec(cache.get, k)
            if result is None:
                result = await func(*args, **kwargs)
                await async_exec(cache.set, k, result, timeout)
            return result

        if inspect.iscoroutinefunction(func):
            return wrapper_async
        else:
            return wrapper

    return decorator


cached = partial(_cached, handler_method=False, http_method=None)
cached_method = partial(_cached, handler_method=True, http_method='GET')

_CC_DELIMITER_RE = re.compile(r'\s*,\s*')


def _i18n_cache_key_suffix(handler, cache_key):
    """If necessary, add the current locale or time zone to the cache key."""
    if settings.USE_I18N or settings.USE_L10N:
        cache_key += '.%s' % handler.locale.code
    if settings.USE_TZ:
        cache_key += '.%s' % get_current_timezone_name()
    return cache_key


def _generate_cache_key(handler, method, header_list, key_prefix):
    """Return a cache key from the headers given in the header list."""
    ctx = hashlib.md5()
    request = handler.request
    for header in header_list:
        value = request.headers.get(header)
        if value is not None:
            ctx.update(force_bytes(value))
    url = hashlib.md5(force_bytes(iri_to_uri(request.full_url())))
    cache_key = 'cache.cache_page.%s.%s.%s.%s' % (
        key_prefix, method, url.hexdigest(), ctx.hexdigest())
    return _i18n_cache_key_suffix(handler, cache_key)


def _generate_cache_header_key(key_prefix, handler):
    """Return a cache key for the header cache."""
    request = handler.request
    url = hashlib.md5(force_bytes(iri_to_uri(request.full_url())))
    cache_key = 'cache.cache_header.%s.%s' % (key_prefix, url.hexdigest())
    return _i18n_cache_key_suffix(handler, cache_key)


def request_handler_cache_key(handler, cache_timeout=None, key_prefix=None, cache=cache):
    """Return a cache key based on the request URL and query."""
    request, headers = handler.request, handler._headers
    if key_prefix is None:
        key_prefix = 'default'
    cache_key = _generate_cache_header_key(key_prefix, handler)
    header_list = cache.get(cache_key)
    if header_list is None:
        if 'Vary' in headers:
            header_list = _CC_DELIMITER_RE.split(headers['Vary'])
            cache.set(cache_key, header_list, cache_timeout)
        else:
            header_list = []
    return _generate_cache_key(handler, request.method, header_list, key_prefix)


def patch_vary_headers(oldheaders, newheaders):
    """
    Add (or update) the "Vary" header in the oldheaders.
    newheaders is a list of header names that should be in "Vary".
    Existing headers in "Vary" aren't removed.
    """
    # Note that we need to keep the original order intact, because cache
    # implementations may rely on the order of the Vary contents in, say,
    # computing an MD5 hash.
    if 'Vary' in oldheaders:
        vary_headers = _CC_DELIMITER_RE.split(oldheaders['Vary'])
    else:
        vary_headers = []
    # Use .lower() here so we treat headers as case-insensitive.
    existing_headers = set(map(str.lower, vary_headers))
    additional_headers = list(filter(
        lambda header: header.lower() not in existing_headers, newheaders))
    oldheaders['Vary'] = ', '.join(vary_headers + additional_headers)
