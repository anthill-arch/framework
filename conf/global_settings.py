"""
Default service settings. Override these with settings in the module pointed to
by the ANTHILL_SETTINGS_MODULE environment variable.
"""

########
# CORE #
########

SECRET_KEY = None

DEBUG = False

INTERNAL_IPS = [
    '127.0.0.0/24',
    '192.168.0.0/16',
    '10.0.0.0/8',
    '172.16.0.0/12',
    'fd00::/8',
    '::1/128'
]

HTTPS = None

TIME_ZONE = 'UTC'
USE_TZ = False

LOCALE = 'en_US'
USE_I18N = False
USE_L10N = False
LOCALE_PATH = None

LOCATION = 'http://localhost:9600'
UNIX_SOCKET = None

ROUTES_CONF = None
MODELS_CONF = None
MANAGEMENT_CONF = None

APPLICATION_CLASS = None
APPLICATION_NAME = None
APPLICATION_VERBOSE_NAME = None
APPLICATION_DESCRIPTION = None
APPLICATION_ICON_CLASS = None
APPLICATION_COLOR = None

SERVICE_CLASS = None

CONTEXT_PROCESSORS = []

###########
# LOGGING #
###########

# The callable to use to configure logging
LOGGING_CONFIG = 'logging.config.dictConfig'

# Custom logging configuration.
LOGGING = {}

# The email backend to use.
# The default is to use the SMTP backend.
# Third-party backends can be specified by providing a Python path
# to a module that defines an EmailBackend class.
EMAIL_BACKEND = 'anthill.framework.core.mail.backends.smtp.EmailBackend'

# Host for sending email.
EMAIL_HOST = 'localhost'

# Port for sending email.
EMAIL_PORT = 25

# Whether to send SMTP 'Date' header in the local time zone or in UTC.
EMAIL_USE_LOCALTIME = False

# Optional SMTP authentication information for EMAIL_HOST.
EMAIL_HOST_USER = ''
EMAIL_HOST_PASSWORD = ''
EMAIL_USE_TLS = False
EMAIL_USE_SSL = False
EMAIL_SSL_CERTFILE = None
EMAIL_SSL_KEYFILE = None
EMAIL_TIMEOUT = None

# Subject-line prefix for email messages send with
# anthill.framework.core.mail.mail_admins or ...mail_managers.
# Make sure to include the trailing space.
EMAIL_SUBJECT_PREFIX = ''

# Default email address to use for various automated correspondence from
# the site managers.
DEFAULT_FROM_EMAIL = 'webmaster@localhost'

# Email address that error messages come from.
SERVER_EMAIL = 'root@localhost'

# Default file storage mechanism that holds media.
DEFAULT_FILE_STORAGE = 'anthill.framework.core.files.storage.FileSystemStorage'

# Absolute filesystem path to the directory that will hold user-uploaded files.
# Example: "/var/www/example.com/media/"
MEDIA_ROOT = ''

# URL that handles the media served from MEDIA_ROOT.
# Examples: "http://example.com/media/", "http://media.example.com/"
MEDIA_URL = ''

# List of upload handler classes to be applied in order.
FILE_UPLOAD_HANDLERS = [
    'anthill.framework.core.files.uploadhandler.MemoryFileUploadHandler',
    'anthill.framework.core.files.uploadhandler.TemporaryFileUploadHandler',
]

FILE_UPLOAD_MAX_BODY_SIZE = 1024 * 1024 * 16  # i.e. 16 MB

# Maximum size, in bytes, of a request before it will be streamed to the
# file system instead of into memory.
FILE_UPLOAD_MAX_MEMORY_SIZE = 2621440  # i.e. 2.5 MB

# Maximum size in bytes of request data (excluding file uploads) that will be
# read before a SuspiciousOperation (RequestDataTooBig) is raised.
DATA_UPLOAD_MAX_MEMORY_SIZE = 2621440  # i.e. 2.5 MB

# Directory in which upload streamed files will be temporarily saved. A value of
# `None` will make framework use the operating system's default temporary directory
# (i.e. "/tmp" on *nix systems).
FILE_UPLOAD_TEMP_DIR = None

# The numeric mode to set newly-uploaded files to. The value should be a mode
# you'd pass directly to os.chmod; see https://docs.python.org/3/library/os.html#files-and-directories.
FILE_UPLOAD_PERMISSIONS = None

# The numeric mode to assign to newly-created directories, when uploading files.
# The value should be a mode as you'd pass to os.chmod;
# see https://docs.python.org/3/library/os.html#files-and-directories.
FILE_UPLOAD_DIRECTORY_PERMISSIONS = None

#########
# CACHE #
#########

# The cache backends to use.
CACHES = {
    'default': {
        'BACKEND': 'anthill.framework.core.cache.backends.locmem.LocMemCache',
    }
}

# People who get code error notifications.
# In the format [('Full Name', 'email@example.com'), ('Full Name', 'anotheremail@example.com')]
ADMINS = []

# Not-necessarily-technical managers of the site. They get broken link
# notifications and other various emails.
MANAGERS = ADMINS

DEFAULT_CHARSET = 'utf-8'

##############
# SQLALCHEMY #
##############

SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
SQLALCHEMY_BINDS = []
SQLALCHEMY_NATIVE_UNICODE = None
SQLALCHEMY_ECHO = False
SQLALCHEMY_RECORD_QUERIES = False

SQLALCHEMY_POOL_SIZE = None
SQLALCHEMY_POOL_TIMEOUT = None
SQLALCHEMY_POOL_RECYCLE = None
SQLALCHEMY_MAX_OVERFLOW = None

SQLALCHEMY_COMMIT_ON_TEARDOWN = False
SQLALCHEMY_TRACK_MODIFICATIONS = False

SQLALCHEMY_DUMPS = None

###########
# SIGNING #
###########

SIGNING_BACKEND = 'anthill.framework.core.signing.TimestampSigner'

##################
# AUTHENTICATION #
##################

AUTH_USER_MODEL = 'User'

AUTH_USER_PERMISSIONS = None

AUTHENTICATION_BACKENDS = [
    'anthill.framework.auth.backends.ModelBackend'
]

# The first hasher in this list is the preferred algorithm.
# Any password using different algorithms will be converted automatically
# upon login
PASSWORD_HASHERS = [
    'anthill.framework.auth.hashers.PBKDF2PasswordHasher',
    'anthill.framework.auth.hashers.PBKDF2SHA1PasswordHasher',
    'anthill.framework.auth.hashers.Argon2PasswordHasher',
    'anthill.framework.auth.hashers.BCryptSHA256PasswordHasher',
    'anthill.framework.auth.hashers.BCryptPasswordHasher',
]

AUTH_PASSWORD_VALIDATORS = []

##########
# SERVER #
##########

STATIC_PATH = None
STATIC_URL = '/static/'
STATIC_HANDLER_CLASS = 'anthill.framework.handlers.StaticFileHandler'

TEMPLATE_PATH = None
TEMPLATE_LOADER_CLASS = 'anthill.framework.core.template.Loader'

DEFAULT_HANDLER_CLASS = 'anthill.framework.handlers.Handler404'
DEFAULT_HANDLER_ARGS = None

COMPRESS_RESPONSE = False

LOGIN_URL = None

UI_MODULE = None

###########
# COOKIES #
###########

CSRF_COOKIES = False

##############
# WEBSOCKETS #
##############

WEBSOCKET_PING_INTERVAL = None
WEBSOCKET_PING_TIMEOUT = None
WEBSOCKET_MAX_MESSAGE_SIZE = None

# An integer from 0 to 9 or -1.
# A value of 1 is fastest and produces the least compression,
# while a value of 9 is slowest and produces the most.
# 0 is no compression. The default value is -1.
# Default value represents a default compromise between speed
# and compression (currently equivalent to level 6).
WEBSOCKET_COMPRESSION_LEVEL = -1

# Controls the amount of memory used for the internal compression state.
# Valid values range from 1 to 9. Higher values use more memory,
# but are faster and produce smaller output.
WEBSOCKET_MEM_LEVEL = None

#########
# GEOIP #
#########

GEOIP_PATH = None
GEOIP_CITY = None
GEOIP_COUNTRY = None

############
# GRAPHENE #
############

GRAPHENE = {}

HIDE_SERVER_VERSION = False

############
# SESSIONS #
############

# Cache to store session data if using the cache session backend.
SESSION_CACHE_ALIAS = 'default'
# Cookie name. This can be whatever you want.
SESSION_COOKIE_NAME = 'sessionid'
# Age of cookie, in seconds (default: 2 weeks).
SESSION_COOKIE_AGE = 60 * 60 * 24 * 7 * 2
# A string like "example.com", or None for standard domain cookie.
SESSION_COOKIE_DOMAIN = None
# Whether the session cookie should be secure (https:// only).
SESSION_COOKIE_SECURE = False
# The path of the session cookie.
SESSION_COOKIE_PATH = '/'
# Whether to use the non-RFC standard httpOnly flag (IE, FF3+, others)
SESSION_COOKIE_HTTPONLY = True
# Whether to save the session data on every request.
SESSION_SAVE_EVERY_REQUEST = False
# Whether a user's session cookie expires when the Web browser is closed.
SESSION_EXPIRE_AT_BROWSER_CLOSE = False
# The module to store session data
SESSION_ENGINE = 'anthill.framework.sessions.backends.cache'
# Directory to store session files if using the file session module.
# If None, the backend will use a sensible default.
SESSION_FILE_PATH = None
# class to serialize session data
SESSION_SERIALIZER = 'anthill.framework.sessions.serializers.JSONSerializer'

OUTPUT_TRANSFORMS = [
    'tornado.web.GZipContentEncoding',
]
