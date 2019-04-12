# For more details about ui modules, see
# http://www.tornadoweb.org/en/stable/guide/templates.html#ui-modules
from tornado.web import TemplateModule as BaseTemplateModule

__all__ = ['TemplateModule']


class TemplateModule(BaseTemplateModule):
    template_name = None

    def render(self, template_name=None, **kwargs):
        template_name = template_name or self.template_name
        return super(TemplateModule, self).render(template_name, **kwargs)
