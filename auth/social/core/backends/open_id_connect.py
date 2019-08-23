from .oauth import BaseOAuth2
from .utils import cache
from ..exceptions import AuthTokenError
from calendar import timegm
from jose import jwk, jwt
from jose.jwt import JWTError, JWTClaimsError, ExpiredSignatureError
from jose.utils import base64url_decode
import json
import datetime
import six


class OpenIdConnectAssociation:
    """Use Association model to save the nonce by force."""

    def __init__(self, handle, secret='', issued=0, lifetime=0, assoc_type=''):
        self.handle = handle  # as nonce
        self.secret = secret.encode()  # not use
        self.issued = issued  # not use
        self.lifetime = lifetime  # not use
        self.assoc_type = assoc_type  # as state


class OpenIdConnectAuth(BaseOAuth2):
    """
    Base class for Open ID Connect backends.
    Currently only the code response type is supported.
    """
    # Override OIDC_ENDPOINT in your subclass to enable autoconfig of OIDC
    OIDC_ENDPOINT = None
    ID_TOKEN_MAX_AGE = 600
    DEFAULT_SCOPE = ['openid', 'profile', 'email']
    EXTRA_DATA = ['id_token', 'refresh_token', ('sub', 'id')]
    REDIRECT_STATE = False
    ACCESS_TOKEN_METHOD = 'POST'
    REVOKE_TOKEN_METHOD = 'GET'
    ID_KEY = 'sub'
    USERNAME_KEY = 'preferred_username'
    ID_TOKEN_ISSUER = ''
    ACCESS_TOKEN_URL = ''
    AUTHORIZATION_URL = ''
    REVOKE_TOKEN_URL = ''
    USERINFO_URL = ''
    JWKS_URI = ''
    JWT_DECODE_OPTIONS = dict()

    def __init__(self, *args, **kwargs):
        self.id_token = None
        super(OpenIdConnectAuth, self).__init__(*args, **kwargs)

    async def authorization_url(self):
        config = await self.oidc_config()
        return self.AUTHORIZATION_URL or config.get('authorization_endpoint')

    async def access_token_url(self):
        config = await self.oidc_config()
        return self.ACCESS_TOKEN_URL or config.get('token_endpoint')

    async def revoke_token_url(self, token, uid):
        config = await self.oidc_config()
        return self.REVOKE_TOKEN_URL or config.get('revocation_endpoint')

    async def id_token_issuer(self):
        config = await self.oidc_config()
        return self.ID_TOKEN_ISSUER or config.get('issuer')

    async def userinfo_url(self):
        config = await self.oidc_config()
        return self.USERINFO_URL or config.get('userinfo_endpoint')

    async def jwks_uri(self):
        config = await self.oidc_config()
        return self.JWKS_URI or config.get('jwks_uri')

    @cache(ttl=86400)
    async def oidc_config(self):
        return await self.get_json(self.OIDC_ENDPOINT +
                                   '/.well-known/openid-configuration')

    @cache(ttl=86400)
    async def get_jwks_keys(self):
        keys = await self.get_remote_jwks_keys()

        # Add client secret as oct key so it can be used for HMAC signatures
        # client_id, client_secret = self.get_key_and_secret()
        # keys.append({'key': client_secret, 'kty': 'oct'})
        return keys

    async def get_remote_jwks_keys(self):
        response = await self.request(await self.jwks_uri())
        return json.loads(response.text)['keys']

    def auth_params(self, state=None):
        """Return extra arguments needed on auth process."""
        params = super(OpenIdConnectAuth, self).auth_params(state)
        params['nonce'] = self.get_and_store_nonce(
            self.authorization_url(), state
        )
        return params

    def get_and_store_nonce(self, url, state):
        # Create a nonce
        nonce = self.strategy.random_string(64)
        # Store the nonce
        association = OpenIdConnectAssociation(nonce, assoc_type=state)
        self.strategy.storage.association.store(url, association)
        return nonce

    def get_nonce(self, nonce):
        try:
            return self.strategy.storage.association.get(
                server_url=self.authorization_url(),
                handle=nonce
            )[0]
        except IndexError:
            pass

    def remove_nonce(self, nonce_id):
        self.strategy.storage.association.remove([nonce_id])

    def validate_claims(self, id_token):
        utc_timestamp = timegm(datetime.datetime.utcnow().utctimetuple())

        if 'nbf' in id_token and utc_timestamp < id_token['nbf']:
            raise AuthTokenError(self, 'Incorrect id_token: nbf')

        # Verify the token was issued in the last 10 minutes
        iat_leeway = self.setting('ID_TOKEN_MAX_AGE', self.ID_TOKEN_MAX_AGE)
        if utc_timestamp > id_token['iat'] + iat_leeway:
            raise AuthTokenError(self, 'Incorrect id_token: iat')

        # Validate the nonce to ensure the request was not modified
        nonce = id_token.get('nonce')
        if not nonce:
            raise AuthTokenError(self, 'Incorrect id_token: nonce')

        nonce_obj = self.get_nonce(nonce)
        if nonce_obj:
            self.remove_nonce(nonce_obj.id)
        else:
            raise AuthTokenError(self, 'Incorrect id_token: nonce')

    async def find_valid_key(self, id_token):
        for key in await self.get_jwks_keys():
            rsakey = jwk.construct(key)
            message, encoded_sig = id_token.rsplit('.', 1)
            decoded_sig = base64url_decode(encoded_sig.encode('utf-8'))
            if rsakey.verify(message.encode('utf-8'), decoded_sig):
                return key

    async def validate_and_return_id_token(self, id_token, access_token):
        """
        Validates the id_token according to the steps at
        http://openid.net/specs/openid-connect-core-1_0.html#IDTokenValidation.
        """
        client_id, client_secret = self.get_key_and_secret()

        key = await self.find_valid_key(id_token)

        if not key:
            raise AuthTokenError(self, 'Signature verification failed')

        alg = key['alg']
        rsakey = jwk.construct(key)

        try:
            claims = jwt.decode(
                id_token,
                rsakey.to_pem().decode('utf-8'),
                algorithms=[alg],
                audience=client_id,
                issuer=await self.id_token_issuer(),
                access_token=access_token,
                options=self.JWT_DECODE_OPTIONS,
            )
        except ExpiredSignatureError:
            raise AuthTokenError(self, 'Signature has expired')
        except JWTClaimsError as error:
            raise AuthTokenError(self, str(error))
        except JWTError:
            raise AuthTokenError(self, 'Invalid signature')

        self.validate_claims(claims)

        return claims

    async def request_access_token(self, *args, **kwargs):
        """
        Retrieve the access token. Also, validate the id_token and
        store it (temporarily).
        """
        response = await self.get_json(*args, **kwargs)
        self.id_token = await self.validate_and_return_id_token(
            response['id_token'],
            response['access_token']
        )
        return response

    async def user_data(self, access_token, *args, **kwargs):
        return await self.get_json(await self.userinfo_url(), headers={
            'Authorization': 'Bearer {0}'.format(access_token)
        })

    def get_user_details(self, response):
        username_key = self.setting('USERNAME_KEY', default=self.USERNAME_KEY)
        return {
            'username': response.get(username_key),
            'email': response.get('email'),
            'fullname': response.get('name'),
            'first_name': response.get('given_name'),
            'last_name': response.get('family_name'),
        }
