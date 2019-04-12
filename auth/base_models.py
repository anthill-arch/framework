from anthill.framework.db import db
from anthill.framework.utils import timezone
from anthill.framework.utils.crypto import salted_hmac
from anthill.framework.auth import password_validation
from anthill.framework.auth.hashers import make_password, check_password
from anthill.framework.auth.backends.db.models import UserMixin
from anthill.framework.core.mail.asynchronous import send_mail
from sqlalchemy_utils.types import EmailType, PhoneNumberType


class BaseAbstractUser(db.Model):
    __abstract__ = True

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    created = db.Column(db.DateTime, nullable=False, default=timezone.now)
    last_login = db.Column(db.DateTime, nullable=True, default=None)
    password = db.Column(db.String)

    # Stores the raw password if set_password() is called so that it can
    # be passed to password_changed() after the model is saved.
    _password = None

    def get_username(self):
        """Return the identifying username for this User."""
        return getattr(self, self.USERNAME_FIELD)

    def __str__(self):
        return self.get_username()

    def __repr__(self):
        return '<User(name=%r)>' % self.get_username()

    @property
    def is_active(self):
        return True

    @property
    def is_superuser(self):
        return False

    @property
    def is_authenticated(self):
        return True

    @property
    def is_anonymous(self):
        return False

    def set_password(self, raw_password):
        self.password = make_password(raw_password)
        self._password = raw_password

    def check_password(self, raw_password):
        """
        Return a boolean of whether the raw_password was correct.
        Handles hashing formats behind the scenes.
        """

        def setter(raw_password):
            self.set_password(raw_password)
            # Password hash upgrades shouldn't be considered password changes.
            self._password = None
            self.save()

        return check_password(raw_password, self.password, setter=setter)

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if self._password is not None:
            password_validation.password_changed(self._password, self)
            self._password = None
        return self

    def get_session_auth_hash(self):
        """Return an HMAC of the password field."""
        key_salt = "anthill.framework.auth.models.BaseAbstractUser.get_session_auth_hash"
        return salted_hmac(key_salt, self.password).hexdigest()


class AbstractUser(UserMixin, BaseAbstractUser):
    __abstract__ = True

    username = db.Column(db.String(128), nullable=False, unique=True)
    email = db.Column(EmailType, nullable=False, unique=True)
    phone = db.Column(PhoneNumberType, nullable=True)
    is_superuser = db.Column(db.Boolean, nullable=False, default=False)
    is_active = db.Column(db.Boolean, nullable=False, default=True)

    USERNAME_FIELD = 'username'

    @property
    def is_authenticated(self):
        return True

    async def send_mail(self, subject, message, from_email=None, **kwargs):
        """Send an email to this user."""
        await send_mail(subject, message, from_email, [self.email], **kwargs)
