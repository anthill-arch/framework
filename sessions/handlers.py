from anthill.framework.utils.cache import patch_vary_headers
from anthill.framework.core.exceptions import SuspiciousOperation
from anthill.framework.sessions.backends.base import UpdateError
from anthill.framework.conf import settings
from importlib import import_module
import time


class SessionHandlerMixin:
    # noinspection PyAttributeOutsideInit
    def init_session(self):
        session_engine = import_module(settings.SESSION_ENGINE)
        self.SessionStore = session_engine.SessionStore

    # noinspection PyAttributeOutsideInit
    def setup_session(self):
        session_key = self.get_cookie(settings.SESSION_COOKIE_NAME)
        self.session = self.SessionStore(session_key)

    @property
    def _is_websocket(self):
        return hasattr(self, 'ws_connection')

    def update_session(self):
        # If session was modified, or if the configuration is to save the
        # session every time, save the changes and set a session cookie or delete
        # the session cookie if the session has been emptied.
        try:
            accessed = self.session.accessed
            modified = self.session.modified
            empty = self.session.is_empty()
        except AttributeError:
            pass
        else:
            # First check if we need to delete this cookie.
            # The session should be deleted only if the session is entirely empty
            if settings.SESSION_COOKIE_NAME in self.cookies and empty and not self._is_websocket:
                self.clear_cookie(
                    settings.SESSION_COOKIE_NAME,
                    path=settings.SESSION_COOKIE_PATH,
                    domain=settings.SESSION_COOKIE_DOMAIN,
                )
            else:
                if accessed:
                    patch_vary_headers(self._headers, ('Cookie',))
                if (modified or settings.SESSION_SAVE_EVERY_REQUEST) and not empty:
                    if self.session.get_expire_at_browser_close():
                        max_age = None
                        expires = None
                    else:
                        max_age = self.session.get_expiry_age()
                        expires = time.time() + max_age
                    # Save the session data and refresh the client cookie.
                    # Skip session save for 500 responses.
                    if self._status_code != 500:
                        try:
                            self.session.save()
                        except UpdateError:
                            raise SuspiciousOperation(
                                "The request's session was deleted before the "
                                "request completed. The user may have logged "
                                "out in a concurrent request, for example."
                            )
                        if not self._is_websocket:
                            self.set_cookie(
                                settings.SESSION_COOKIE_NAME,
                                self.session.session_key,
                                max_age=max_age,
                                expires=expires,
                                domain=settings.SESSION_COOKIE_DOMAIN,
                                path=settings.SESSION_COOKIE_PATH,
                                secure=settings.SESSION_COOKIE_SECURE or None,
                                httponly=settings.SESSION_COOKIE_HTTPONLY or None
                            )
