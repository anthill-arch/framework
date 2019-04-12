from anthill.framework.handlers.base import (
    ContextMixin, RequestHandler, TemplateMixin)
from anthill.framework.core.exceptions import ImproperlyConfigured
from anthill.framework.handlers.detail import (
    SingleObjectMixin, SingleObjectTemplateMixin, DetailHandler)
from anthill.framework.forms.orm import model_form
from anthill.framework.utils.asynchronous import thread_pool_exec
from anthill.framework.db import db


class FormMixin(ContextMixin):
    """Provide a way to show and handle a form in a request."""

    initial = {}
    form_class = None
    success_url = None
    prefix = None

    def get_initial(self):
        """Return the initial data to use for forms on this handler."""
        return self.initial.copy()

    def get_prefix(self):
        """Return the prefix to use for forms."""
        return self.prefix or ''

    def get_form_class(self):
        """Return the form class to use."""
        return self.form_class

    def get_form(self, form_class=None):
        """Return an instance of the form to be used in this handler."""
        if form_class is None:
            form_class = self.get_form_class()
        return form_class(**self.get_form_kwargs())

    def get_form_kwargs(self):
        """Return the keyword arguments for instantiating the form."""
        kwargs = {
            'data': self.get_initial(),
            'prefix': self.get_prefix(),
        }

        if self.request.method in ('POST', 'PUT'):
            kwargs.update(formdata=dict(self.request.arguments, **self.request.files))
        return kwargs

    def get_success_url(self):
        """Return the URL to redirect to after processing a valid form."""
        if not self.success_url:
            raise ImproperlyConfigured("No URL to redirect to. Provide a success_url.")
        return str(self.success_url)  # success_url may be lazy

    async def form_valid(self, form):
        """If the form is valid, redirect to the supplied URL."""
        self.redirect(self.get_success_url())

    async def form_invalid(self, form):
        """If the form is invalid, render the invalid form."""
        context = await self.get_context_data(form=form)
        self.render(**context)

    async def get_context_data(self, **kwargs):
        """Insert the form into the context dict."""
        if 'form' not in kwargs:
            kwargs['form'] = self.get_form()
        return await super().get_context_data(**kwargs)


class ModelFormMixin(FormMixin, SingleObjectMixin):
    """Provide a way to show and handle a ModelForm in a request."""

    def get_model(self):
        if self.model is not None:
            # If a model has been explicitly provided, use it
            return self.model
        elif getattr(self, 'object', None) is not None:
            # If this handler is operating on a single object,
            # use the class of that object
            return self.object.__class__
        else:
            # Try to get a queryset and extract the model class
            # from that
            queryset = self.get_queryset()
            return queryset.one().__class__

    def get_form_class(self):
        """Return the form class to use in this handler."""
        if self.form_class:
            return self.form_class
        else:
            return model_form(self.get_model(), db_session=db.session)

    def get_form_kwargs(self):
        """Return the keyword arguments for instantiating the form."""
        kwargs = super().get_form_kwargs()
        if hasattr(self, 'object'):
            kwargs.update({'obj': self.object})
        return kwargs

    def get_success_url(self):
        """Return the URL to redirect to after processing a valid form."""
        if self.success_url:
            url = self.success_url.format(**self.object.__dict__)
        else:
            try:
                url = self.object.get_absolute_url()
            except AttributeError:
                raise ImproperlyConfigured(
                    "No URL to redirect to. Either provide an url or define "
                    "a get_absolute_url method on the Model.")
        return url

    async def form_valid(self, form):
        """If the form is valid, save the associated model."""
        if self.object is None:
            model = self.get_model()
            # noinspection PyAttributeOutsideInit
            self.object = model()
        form.populate_obj(self.object)
        await thread_pool_exec(self.object.save)
        await super().form_valid(form)


class CreateModelFormMixin(ModelFormMixin):
    pass


class UpdateModelFormMixin(ModelFormMixin):
    def get_form_class(self):
        """Return the form class to use in this handler."""
        form_class = super().get_form_class()
        setattr(form_class.Meta, 'all_fields_optional', True)
        setattr(form_class.Meta, 'assign_required', False)
        return form_class


class ProcessFormMixin:
    """Render a form on GET and processes it on POST."""

    async def get(self, *args, **kwargs):
        """Handle GET requests: instantiate a blank version of the form."""
        context = await self.get_context_data(**kwargs)
        self.render(**context)

    async def post(self, *args, **kwargs):
        """
        Handle POST requests: instantiate a form instance with the passed
        POST variables and then check if it's valid.
        """
        form = self.get_form()
        if form.validate():
            await self.form_valid(form)
        else:
            await self.form_invalid(form)

    # PUT is a valid HTTP verb for creating (with a known URL) or editing an
    # object, note that browsers only support POST for now.
    async def put(self, *args, **kwargs):
        await self.post(*args, **kwargs)


class ProcessFormHandler(ProcessFormMixin, RequestHandler):
    """Render a form on GET and processes it on POST."""


class BaseFormHandler(FormMixin, ProcessFormHandler):
    """A base handler for displaying a form."""


class FormHandler(TemplateMixin, BaseFormHandler):
    """A handler for displaying a form and rendering a template response."""


class BaseCreateHandler(CreateModelFormMixin, ProcessFormHandler):
    """
    Base handler for creating a new object instance.

    Using this base class requires subclassing to provide a response mixin.
    """

    async def get(self, *args, **kwargs):
        # noinspection PyAttributeOutsideInit
        self.object = None
        await super().get(*args, **kwargs)

    async def post(self, *args, **kwargs):
        # noinspection PyAttributeOutsideInit
        self.object = None
        await super().post(*args, **kwargs)


class CreateHandler(SingleObjectTemplateMixin, BaseCreateHandler):
    """
    Handler for creating a new object, with a response rendered by a template.
    """
    template_name_suffix = '_form'


class BaseUpdateHandler(UpdateModelFormMixin, ProcessFormHandler):
    """
    Base handler for updating an existing object.

    Using this base class requires subclassing to provide a response mixin.
    """

    async def get(self, *args, **kwargs):
        # noinspection PyAttributeOutsideInit
        self.object = await self.get_object()
        await super().get(*args, **kwargs)

    async def post(self, *args, **kwargs):
        # noinspection PyAttributeOutsideInit
        self.object = await self.get_object()
        await super().post(*args, **kwargs)


class UpdateHandler(SingleObjectTemplateMixin, BaseUpdateHandler):
    """Handler for updating an object, with a response rendered by a template."""
    template_name_suffix = '_form'


class DeletionMixin:
    """Provide the ability to delete objects."""
    success_url = None

    async def delete(self, *args, **kwargs):
        """
        Call the delete() method on the fetched object and then redirect to the
        success URL.
        """
        # noinspection PyAttributeOutsideInit
        self.object = await self.get_object()
        await thread_pool_exec(self.object.delete)
        self.redirect(self.get_success_url())

    # Add support for browsers which only accept GET and POST for now.
    async def post(self, *args, **kwargs):
        await self.delete(*args, **kwargs)

    def get_success_url(self):
        if self.success_url:
            return self.success_url.format(**self.object.__dict__)
        else:
            raise ImproperlyConfigured(
                "No URL to redirect to. Provide a success_url.")


class BaseDeleteHandler(DeletionMixin, DetailHandler):
    """
    Base handler for deleting an object.
    """


class DeleteHandler(BaseDeleteHandler):
    """
    Handler for deleting an object retrieved with self.get_object(), with a
    response rendered by a template.
    """
    template_name_suffix = '_confirm_delete'
