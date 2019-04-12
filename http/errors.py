from tornado.web import HTTPError as GenericHTTPError


class HTTPError(GenericHTTPError):
    """Base HTTP exception class."""
    status_code = 500

    def __init__(self, log_message=None, *args, **kwargs):
        super().__init__(self.status_code, log_message, *args, **kwargs)


class HttpBadRequestError(HTTPError):
    status_code = 400


class HttpUnauthorizedError(HTTPError):
    status_code = 401


class HttpForbiddenError(HTTPError):
    status_code = 403


class HttpNotFoundError(HTTPError):
    status_code = 404


class HttpNotAllowedError(HTTPError):
    status_code = 405


class HttpGoneError(HTTPError):
    status_code = 410


HttpServerError = HTTPError
Http404 = HttpNotFoundError
