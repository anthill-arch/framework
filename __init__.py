from anthill.framework.utils.version import get_version

VERSION = (0, 0, 1, 'alpha', 1)

__version__ = get_version(VERSION)


def setup():
    """
    Configure the settings (this happens as a side effect of accessing the
    first setting), configure logging and default locale.
    """
    from anthill.framework.conf import settings
    from anthill.framework.utils.log import configure_logging
    from tornado.locale import set_default_locale, load_gettext_translations

    configure_logging(settings.LOGGING_CONFIG, settings.LOGGING)

    if settings.USE_I18N:
        set_default_locale(settings.LOCALE)
        load_gettext_translations('locale', 'messages')
