from anthill.framework.utils.functional import lazy
from tornado import locale


class LocaleWrapper:
    def __getattr__(self, real_name):
        from anthill.framework.conf import settings
        setattr(self, 'default_locale', locale.get(settings.LOCALE))
        if real_name is 'default_locale':
            return self.default_locale
        return getattr(self.default_locale, real_name)


locale_wrapper = LocaleWrapper()


def default_locale():
    return locale_wrapper.default_locale


def translate(message, plural_message=None, count=None):
    return locale_wrapper.translate(message, plural_message, count)


# noinspection SpellCheckingInspection
def pgettext(context, message, plural_message=None, count=None):
    return locale_wrapper.pgettext(context, message, plural_message, count)


translate_lazy = lazy(translate, str)
# noinspection SpellCheckingInspection
pgettext_lazy = lazy(pgettext, str)
