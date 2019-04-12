from anthill.framework.sessions.backends.base import (
    CreateError, SessionBase, UpdateError,
)
from anthill.framework.utils.functional import cached_property
from anthill.framework.utils import timezone
import logging

logger = logging.getLogger('anthill.application')


class SessionStore(SessionBase):
    """
    Implement database session store.
    """

    def __init__(self, session_key=None):
        super().__init__(session_key)

    @classmethod
    def get_model_class(cls):
        from anthill.framework.sessions.models import Session
        return Session

    @cached_property
    def model(self):
        return self.get_model_class()

    def _get_session_from_db(self):
        try:
            return self.model.query.filter(
                self.model.session_key == self.session_key,
                self.model.expire_date > timezone.now()
            ).first()
        except Exception as e:
            logger.warning(str(e))
            self._session_key = None

    def create_model_instance(self, data):
        """
        Return a new instance of the session model object, which represents the
        current session state. Intended to be used for saving the session data
        to the database.
        """
        return self.model(
            session_key=self._get_or_create_session_key(),
            session_data=self.encode(data),
            expire_date=self.get_expiry_date(),
        )

    def exists(self, session_key):
        return self.model.query.get(session_key) is not None

    def create(self):
        while True:
            self._session_key = self._get_new_session_key()
            try:
                # Save immediately to ensure we have a unique entry in the
                # database.
                self.save(must_create=True)
            except CreateError:
                # Key wasn't unique. Try again.
                continue
            self.modified = True
            return

    def save(self, must_create=False):
        """
        Save the current session data to the database. If 'must_create' is
        True, raise a database error if the saving operation doesn't create a
        new entry (as opposed to possibly updating an existing entry).
        """
        if self.session_key is None:
            return self.create()
        data = self._get_session(no_load=must_create)
        obj = self.create_model_instance(data)
        obj.save(force_insert=must_create)

    def delete(self, session_key=None):
        if session_key is None:
            if self.session_key is None:
                return
            session_key = self.session_key
        self.model.query.get(session_key).delete()

    def load(self):
        s = self._get_session_from_db()
        return self.decode(s.session_data) if s else {}

    @classmethod
    def clear_expired(cls):
        model = cls.get_model_class()
        model.query.filter(model.expire_date < timezone.now()).delete()
