"""Tornado SQLAlchemy ORM models for Social Auth."""

from sqlalchemy.orm import relationship, backref
from anthill.framework.auth.social.core.utils import setting_name
from social_sqlalchemy.storage import (
    SQLAlchemyUserMixin,
    SQLAlchemyAssociationMixin,
    SQLAlchemyNonceMixin,
    SQLAlchemyCodeMixin,
    SQLAlchemyPartialMixin,
    BaseSQLAlchemyStorage
)
from anthill.framework.db import db
from anthill.framework.auth import get_user_model
from anthill.framework.conf import settings


class TornadoStorage(BaseSQLAlchemyStorage):
    user = None
    nonce = None
    association = None
    code = None
    partial = None


def init_social():
    # noinspection PyPep8Naming
    UID_LENGTH = getattr(settings, setting_name('UID_LENGTH'), 255)
    # noinspection PyPep8Naming
    User = get_user_model()

    class _AppSession(db.Model):
        __abstract__ = True

        @classmethod
        def _session(cls):
            return db.session

    class UserSocialAuth(_AppSession, SQLAlchemyUserMixin):
        """Social Auth association model."""
        uid = db.Column(db.String(UID_LENGTH))
        user_id = db.Column(User.id.type, db.ForeignKey(User.id), nullable=False, index=True)
        user = relationship(User, backref=backref('social_auth', lazy='dynamic'))

        @classmethod
        def username_max_length(cls):
            return User.__table__.columns.get('username').type.length

        @classmethod
        def user_model(cls):
            return User

    class Nonce(_AppSession, SQLAlchemyNonceMixin):
        """One use numbers."""

    class Association(_AppSession, SQLAlchemyAssociationMixin):
        """OpenId account association."""

    class Code(_AppSession, SQLAlchemyCodeMixin):
        """Mail validation single one time use code."""

    class Partial(_AppSession, SQLAlchemyPartialMixin):
        """Partial pipeline storage."""

    # Set the references in the storage class
    TornadoStorage.user = UserSocialAuth
    TornadoStorage.nonce = Nonce
    TornadoStorage.association = Association
    TornadoStorage.code = Code
    TornadoStorage.partial = Partial
