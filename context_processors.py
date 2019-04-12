from anthill.framework.conf import settings
from anthill.framework.utils.module_loading import import_string
from anthill.framework.core.exceptions import ImproperlyConfigured
from tornado.web import RequestHandler
import logging
import inspect

logger = logging.getLogger('anthill.handlers')

CONTEXT_PROCESSORS = getattr(settings, 'CONTEXT_PROCESSORS', [])


async def build_context_from_context_processors(handler: RequestHandler) -> dict:
    """Build extra context for current handler on every request."""
    ctx = {}
    for ctx_processor in CONTEXT_PROCESSORS:
        f = import_string(ctx_processor)
        # Context processor can be either co routine or plain function
        result = await f(handler) if inspect.iscoroutinefunction(f) else f(handler)
        if not isinstance(handler, RequestHandler):
            raise ImproperlyConfigured(
                'Context processor `%s` got `%s` object, '
                'but need `RequestHandler`' % (f.__name__, handler.__class__.__name__)
            )
        if not isinstance(result, dict):
            raise ImproperlyConfigured(
                'Context processor `%s` must return dict object, '
                'but `%s` returned' % (f.__name__, type(result)))
        if not result:
            logging.warning('Empty result for context processor `%s`' % f.__name__)
        ctx.update(result)
    return ctx


def datetime(handler):
    from anthill.framework.utils import timezone
    return {
        'now': timezone.now()
    }
