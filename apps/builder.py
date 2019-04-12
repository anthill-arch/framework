from anthill.framework.utils.module_loading import import_string
from anthill.framework.conf import settings
from anthill.framework.apps.cls import Application
import logging

logger = logging.getLogger('anthill.application')

__all__ = ['app']


class AppBuilder:
    default_application_class = Application

    def get_app_class(self):
        application_class = self.default_application_class
        try:
            application_class = import_string('apps.AnthillApplication')
        except ImportError as e1:
            if settings.APPLICATION_CLASS is not None:
                try:
                    application_class = import_string(settings.APPLICATION_CLASS)
                except ImportError as e2:
                    logger.warning(e2)
                    logger.warning(
                        'Cannot import application class: %s. '
                        'Default used.' % settings.APPLICATION_CLASS
                    )
        return application_class

    def create(self, **kwargs):
        application_class = self.get_app_class()
        instance = application_class(**kwargs)
        logger.info('Application `%s` loaded.' % instance.name)
        logger.info('Application version `%s`.' % instance.version)
        return instance


builder = AppBuilder()
app = builder.create()
app.setup()
