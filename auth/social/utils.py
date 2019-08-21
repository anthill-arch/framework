from .core.utils import setting_name, get_strategy, module_member
from .core.backends.utils import get_backend
from anthill.framework.conf import settings
from functools import wraps


BACKENDS = settings.AUTHENTICATION_BACKENDS
STRATEGY = getattr(settings, setting_name('STRATEGY'),
                   'anthill.framework.auth.social.strategy.TornadoStrategy')
STORAGE = getattr(settings, setting_name('STORAGE'),
                  'anthill.framework.auth.social.models.TornadoStorage')
Strategy = module_member(STRATEGY)
Storage = module_member(STORAGE)


def load_strategy(request_handler=None):
    return get_strategy(STRATEGY, STORAGE, request_handler)


def load_backend(strategy, name, redirect_uri):
    Backend = get_backend(BACKENDS, name)
    return Backend(strategy, redirect_uri)


def psa(redirect_uri=None):
    def decorator(func):
        @wraps(func)
        def wrapper(self, backend, *args, **kwargs):
            uri = redirect_uri
            if uri and not uri.startswith('/'):
                uri = self.reverse_url(uri, backend)
            self.strategy = load_strategy(self)
            self.backend = load_backend(self.strategy, backend, uri)
            return func(self, backend, *args, **kwargs)
        return wrapper
    return decorator
