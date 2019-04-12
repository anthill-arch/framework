import jwt
import uuid
import warnings

from anthill.framework.auth import get_user_model

from calendar import timegm
from datetime import datetime

from anthill.framework.auth.token.jwt.settings import settings as token_settings


def get_username_field():
    try:
        username_field = get_user_model().USERNAME_FIELD
    except AttributeError:
        username_field = 'username'

    return username_field


def get_username(user):
    try:
        username = user.get_username()
    except AttributeError:
        username = user.username

    return username


def jwt_get_secret_key(payload=None):
    """
    For enhanced security you may want to use a secret key based on user.

    This way you have an option to logout only this user if:
        - token is compromised
        - password is changed
        - etc.
    """
    if token_settings.JWT_GET_USER_SECRET_KEY:
        User = get_user_model()
        user = User.query.get(payload.get('user_id'))
        key = str(token_settings.JWT_GET_USER_SECRET_KEY(user))
        return key
    return token_settings.JWT_SECRET_KEY


def jwt_payload_handler(user):
    username_field = get_username_field()
    username = get_username(user)

    warnings.warn(
        'The following fields will be removed in the future: '
        '`email` and `user_id`. ',
        DeprecationWarning
    )

    payload = {
        'user_id': user.id,
        'username': username,
        'exp': datetime.utcnow() + token_settings.JWT_EXPIRATION_DELTA
    }
    if hasattr(user, 'email'):
        payload['email'] = user.email
    if isinstance(user.id, uuid.UUID):
        payload['user_id'] = str(user.id)

    payload[username_field] = username

    # Include original issued at time for a brand new token,
    # to allow token refresh
    if token_settings.JWT_ALLOW_REFRESH:
        payload['orig_iat'] = timegm(datetime.utcnow().utctimetuple())

    if token_settings.JWT_AUDIENCE is not None:
        payload['aud'] = token_settings.JWT_AUDIENCE

    if token_settings.JWT_ISSUER is not None:
        payload['iss'] = token_settings.JWT_ISSUER

    return payload


def jwt_get_user_id_from_payload_handler(payload):
    """
    Override this function if user_id is formatted differently in payload
    """
    warnings.warn(
        'The following will be removed in the future. '
        'Use `JWT_PAYLOAD_GET_USERNAME_HANDLER` instead.',
        DeprecationWarning
    )

    return payload.get('user_id')


def jwt_get_username_from_payload_handler(payload):
    """
    Override this function if username is formatted differently in payload
    """
    return payload.get('username')


def jwt_encode_handler(payload):
    key = token_settings.JWT_PRIVATE_KEY or jwt_get_secret_key(payload)
    return jwt.encode(
        payload,
        key,
        token_settings.JWT_ALGORITHM
    ).decode('utf-8')


def jwt_decode_handler(token):
    options = {
        'verify_exp': token_settings.JWT_VERIFY_EXPIRATION,
    }
    # get user from token, BEFORE verification, to get user secret key
    unverified_payload = jwt.decode(token, None, False)
    secret_key = jwt_get_secret_key(unverified_payload)
    return jwt.decode(
        token,
        token_settings.JWT_PUBLIC_KEY or secret_key,
        token_settings.JWT_VERIFY,
        options=options,
        leeway=token_settings.JWT_LEEWAY,
        audience=token_settings.JWT_AUDIENCE,
        issuer=token_settings.JWT_ISSUER,
        algorithms=[token_settings.JWT_ALGORITHM]
    )


def jwt_response_payload_handler(token, user=None, request=None):
    """
    Returns the response data for both the login and refresh views.
    Override to return a custom response such as including the
    serialized representation of the User.

    Example:
    def jwt_response_payload_handler(token, user=None, request=None):
        return {
            'token': token,
            'user': UserSerializer(user, context={'request': request}).data
        }
    """
    return {
        'token': token
    }
