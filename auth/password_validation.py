from anthill.framework.conf import settings
from anthill.framework.core.exceptions import ImproperlyConfigured, ValidationError
from anthill.framework.utils.module_loading import import_string
import functools
import gzip
import os


@functools.lru_cache(maxsize=None)
def get_default_password_validators():
    return get_password_validators(settings.AUTH_PASSWORD_VALIDATORS)


def get_password_validators(validator_config):
    validators = []
    for validator in validator_config:
        try:
            klass = import_string(validator['NAME'])
        except ImportError:
            msg = "The module in NAME could not be imported: %s." \
                  "Check your AUTH_PASSWORD_VALIDATORS setting."
            raise ImproperlyConfigured(msg % validator['NAME'])
        validators.append(klass(**validator.get('OPTIONS', {})))

    return validators


def validate_password(password, user=None, password_validators=None):
    """
    Validate whether the password meets all validator requirements.

    If the password is valid, return ``None``.
    If the password is invalid, raise ValidationError with all error messages.
    """
    errors = []
    if password_validators is None:
        password_validators = get_default_password_validators()
    for validator in password_validators:
        try:
            validator.validate(password, user)
        except ValidationError as error:
            errors.append(error)
    if errors:
        raise ValidationError(errors)


def password_changed(password, user=None, password_validators=None):
    """
    Inform all validators that have implemented a password_changed() method
    that the password has been changed.
    """
    if password_validators is None:
        password_validators = get_default_password_validators()
    for validator in password_validators:
        password_changed_method = getattr(validator, 'password_changed', lambda *a: None)
        password_changed_method(password, user)


def password_validators_help_texts(password_validators=None):
    """
    Return a list of all help texts of all configured validators.
    """
    help_texts = []
    if password_validators is None:
        password_validators = get_default_password_validators()
    for validator in password_validators:
        help_texts.append(validator.get_help_text())
    return help_texts


class MinimumLengthValidator:
    """
    Validate whether the password is of a minimum length.
    """

    def __init__(self, min_length=8):
        self.min_length = min_length

    def validate(self, password, user=None):
        if len(password) < self.min_length:
            raise ValidationError(
                "This password is too short. It must contain at least %(min_length)d characters.",
                code='password_too_short',
                params={'min_length': self.min_length},
            )

    def get_help_text(self):
        return "Your password must contain at least %(min_length)d characters." % {'min_length': self.min_length}


class CommonPasswordValidator:
    """
    Validate whether the password is a common password.

    The password is rejected if it occurs in a provided list, which may be gzipped.
    The list ships with contains 1000 common passwords, created by Mark Burnett:
    https://xato.net/passwords/more-top-worst-passwords/
    """
    DEFAULT_PASSWORD_LIST_PATH = os.path.join(
        os.path.dirname(os.path.realpath(__file__)), 'common-passwords.txt.gz'
    )

    def __init__(self, password_list_path=DEFAULT_PASSWORD_LIST_PATH):
        try:
            with gzip.open(password_list_path) as f:
                common_passwords_lines = f.read().decode().splitlines()
        except IOError:
            with open(password_list_path) as f:
                common_passwords_lines = f.readlines()

        self.passwords = {p.strip() for p in common_passwords_lines}

    def validate(self, password, user=None):
        if password.lower().strip() in self.passwords:
            raise ValidationError(
                "This password is too common.",
                code='password_too_common',
            )

    def get_help_text(self):
        return "Your password can't be a commonly used password."


class NumericPasswordValidator:
    """
    Validate whether the password is alphanumeric.
    """

    def validate(self, password, user=None):
        if password.isdigit():
            raise ValidationError(
                "This password is entirely numeric.",
                code='password_entirely_numeric',
            )

    def get_help_text(self):
        return "Your password can't be entirely numeric."
