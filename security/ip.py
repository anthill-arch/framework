from anthill.framework.utils.ip import get_ip, has_ip
from anthill.framework.conf import settings
from anthill.framework.http import Http404
from functools import wraps, partial

INTERNAL_IPS = getattr(settings, 'INTERNAL_IPS', [])

__all__ = ['is_awailable', 'awailable', 'is_internal', 'internal']


def is_awailable(ip, pool):
    pool = pool or []
    for internal_network in pool:
        if has_ip(internal_network, ip):
            return True
    return False


def awailable(pool=None):
    def decorator(method):
        @wraps(method)
        def wrapper(self, *args, **kwargs):
            ip = get_ip(self.request)
            if not is_awailable(ip, pool):
                # Attacker shouldn't even know this page exists
                raise Http404
            return method(self, *args, **kwargs)

        return wrapper

    return decorator


is_internal = partial(is_awailable, pool=INTERNAL_IPS)
internal = awailable(pool=INTERNAL_IPS)
