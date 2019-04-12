from anthill.framework.handlers.base import JSONHandler
from .settings import token_settings


jwt_response_payload_handler = token_settings.JWT_RESPONSE_PAYLOAD_HANDLER


class JSONWebTokenHandler(JSONHandler):
    """
    Base JSONWebToken Handler that various JWT interactions inherit from.
    """
    async def post(self):
        pass


class ObtainJSONWebToken(JSONWebTokenHandler):
    """
    JSONWebToken Handler that receives a POST with a user's username and password.
    Returns a JSON Web Token that can be used for authenticated requests.
    """


class VerifyJSONWebToken(JSONWebTokenHandler):
    """
    JSONWebToken Handler that checks the veracity of a token, returning the token
    if it is valid.
    """


class RefreshJSONWebToken(JSONWebTokenHandler):
    """
    JSONWebToken Handler that returns a refreshed token (with new expiration)
    based on existing token.

    If 'orig_iat' field (original issued-at-time) is found, will first check
    if it's within expiration window, then copy it to the new token
    """
