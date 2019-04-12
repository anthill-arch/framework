from anthill.framework.handlers.base import (
    ContextMixin, RequestHandler, TemplateMixin)
from anthill.framework.http import Http404
from anthill.framework.utils.translation import translate as _
from anthill.framework.utils.text import slugify
from anthill.framework.utils.asynchronous import thread_pool_exec
from anthill.framework.core.exceptions import ImproperlyConfigured
from anthill.framework.db import db


class SingleObjectMixin(ContextMixin):
    """
    Provide the ability to retrieve a single object for further manipulation.
    """
    model = None
    queryset = None
    slug_field = 'slug'
    context_object_name = None
    slug_url_kwarg = 'slug'
    pk_url_kwarg = 'pk'
    query_pk_and_slug = False

    async def get_object(self, queryset=None):
        """
        Return the object the handler is displaying.

        Require `self.queryset` and a `pk` or `slug` argument in the url entry.
        Subclasses can override this to return any object.
        """
        # Use a custom queryset if provided.
        if queryset is None:
            queryset = self.get_queryset()

        # Next, try looking up by primary key.
        pk = self.path_kwargs.get(self.pk_url_kwarg)
        slug = self.path_kwargs.get(self.slug_url_kwarg)
        if pk is not None:
            queryset = await thread_pool_exec(queryset.filter_by, pk=pk)

        # Next, try looking up by slug.
        if slug is not None and (pk is None or self.query_pk_and_slug):
            slug_field = self.get_slug_field()
            queryset = await thread_pool_exec(queryset.filter_by, **{slug_field: slug})

        # If none of those are defined, it's an error.
        if pk is None and slug is None:
            raise AttributeError(
                "Generic detail handler %s must be called with either an object "
                "pk or a slug in the url." % self.__class__.__name__)

        # Get the single item from the filtered queryset
        obj = await thread_pool_exec(queryset.one_or_none)
        if obj is None:
            raise Http404

        return obj

    def get_queryset(self):
        """
        Return the queryset that will be used to look up the object.

        This method is called by the default implementation of get_object() and
        may not be called if get_object() is overridden.
        """
        if self.queryset is None:
            if self.model:
                return self.model.query
            else:
                raise ImproperlyConfigured(
                    "%(cls)s is missing a queryset. Define "
                    "%(cls)s.model, %(cls)s.queryset, or override "
                    "%(cls)s.get_queryset()." % {
                        'cls': self.__class__.__name__
                    }
                )
        return self.queryset

    def get_slug_field(self):
        """Get the name of a slug field to be used to look up by slug."""
        return self.slug_field

    def get_context_object_name(self, obj):
        """Get the name to use for the object."""
        if self.context_object_name:
            return self.context_object_name
        elif isinstance(obj, db.Model):
            return slugify(obj.__class__.__name__)
        else:
            return None

    async def get_context_data(self, **kwargs):
        """Insert the single object into the context dict."""
        context = {}
        if self.object:
            context['object'] = self.object
            context_object_name = self.get_context_object_name(self.object)
            if context_object_name:
                context[context_object_name] = self.object
        context.update(kwargs)
        return await super().get_context_data(**context)


class SingleObjectTemplateMixin(TemplateMixin):
    template_name_field = None
    template_name_suffix = '_detail'

    def get_template_names(self):
        """
        Return a list of template names to be used for the request.
        Return the following list:

        * the value of ``template_name`` on the handler (if provided)
        * the contents of the ``template_name_field`` field on the
          object instance that the handler is operating upon (if available)
        * ``<model_name><template_name_suffix>.html``
        """
        try:
            names = super().get_template_names()
        except ImproperlyConfigured:
            # If template_name isn't specified, it's not a problem --
            # we just start with an empty list.
            names = []

            # If self.template_name_field is set, grab the value of the field
            # of that name from the object; this is the most specific template
            # name, if given.
            if self.object and self.template_name_field:
                name = getattr(self.object, self.template_name_field, None)
                if name:
                    names.insert(0, name)

            # The least-specific option is the default <model>_detail.html;
            # only use this if the object in question is a model.
            if isinstance(self.object, db.Model):
                names.append("%s%s.html" % (
                    slugify(self.object.__class__.__name__),
                    self.template_name_suffix
                ))
            elif getattr(self, 'model', None) is not None and issubclass(self.model, db.Model):
                names.append("%s%s.html" % (
                    slugify(self.model.__name__),
                    self.template_name_suffix
                ))

            # If we still haven't managed to find any template names, we should
            # re-raise the ImproperlyConfigured to alert the user.
            if not names:
                raise

        return names


class DetailHandler(SingleObjectMixin, SingleObjectTemplateMixin, RequestHandler):
    """A base handler for displaying a single object."""

    async def get(self, *args, **kwargs):
        # noinspection PyAttributeOutsideInit
        self.object = await self.get_object()
        context = await self.get_context_data(object=self.object)
        self.render(context)
