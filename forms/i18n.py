from anthill.framework.conf import settings
from tornado import locale


class Translations:
    """
    A translations object for WTForms that gets its messages from
    Anthill's translations providers.
    """

    def __init__(self, code=settings.LOCALE):
        self.locale = locale.get(code)

    def gettext(self, string):
        return self.locale.translate(string)

    def ngettext(self, singular, plural, n):
        return self.locale.translate(singular, plural, n)
