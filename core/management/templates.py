from anthill.framework.core.management import Command, Option, InvalidCommand
from anthill.framework.core.management.utils import handle_extensions
from anthill.framework.utils.version import get_docs_version
from anthill.framework.utils import archive
import anthill.framework
from tornado.escape import to_unicode
from tornado.template import Template
import cgi
import mimetypes
import os
import posixpath
import shutil
import stat
import tempfile
from importlib import import_module
from os import path
from urllib.request import urlretrieve


class TemplateCommand(Command):
    """
    Copy either an Anthill application layout template or an Anthill project
    layout template into the specified directory.

    :param app_or_project: The string 'app' or 'project'.
    :param name: The name of the application or project.
    :param directory: The directory to which the template should be copied.
    :param options: The additional variables passed to project or app templates
    """
    # The supported URL schemes
    url_schemes = ['http', 'https', 'ftp']
    # Rewrite the following suffixes when determining the target filename.
    rewrite_template_suffixes = (
        # Allow shipping invalid .py files without byte-compilation.
        ('.py-tpl', '.py'),
    )

    def get_options(self):
        options = (
            Option('name', help='Name of the application or project.'),
            Option('directory', nargs='?', help='Optional destination directory'),
            Option('--template', help='The path or URL to load the template from.'),
            Option(
                '--extension', '-e', dest='extensions', action='append', default=['py'],
                help='The file extension(s) to render (default: "py"). '
                     'Separate multiple extensions with commas, or use '
                     '-e multiple times.'),
            Option(
                '--name', '-n', dest='files', action='append', default=[],
                help='The file name(s) to render. Separate multiple file names '
                     'with commas, or use -n multiple times.')
        )
        return options

    def run(self, app_or_project, name, target=None, **options):
        self.app_or_project = app_or_project
        self.paths_to_remove = []

        self.validate_name(name, app_or_project)

        # if some directory is given, make sure it's nicely expanded
        if target is None:
            top_dir = path.join(os.getcwd(), name)
            try:
                os.makedirs(top_dir)
            except FileExistsError:
                raise InvalidCommand("'%s' already exists" % top_dir)
            except OSError as e:
                raise InvalidCommand(e)
        else:
            top_dir = os.path.abspath(path.expanduser(target))
            if not os.path.exists(top_dir):
                raise InvalidCommand("Destination directory '%s' does not "
                                     "exist, please create it first." % top_dir)

        extensions = tuple(handle_extensions(options['extensions']))
        extra_files = []
        for file in options['files']:
            extra_files.extend(map(lambda x: x.strip(), file.split(',')))

        self.stdout.write("Rendering %s template files with "
                          "extensions: %s\n" % (app_or_project, ', '.join(extensions)))
        self.stdout.write("Rendering %s template files with "
                          "filenames: %s\n" % (app_or_project, ', '.join(extra_files)))

        base_name = '%s_name' % app_or_project
        base_subdir = '%s_template' % app_or_project
        base_directory = '%s_directory' % app_or_project
        camel_case_name = 'camel_case_%s_name' % app_or_project
        camel_case_value = ''.join(x for x in name.title() if x != '_')

        context = {
            base_name: name,
            base_directory: top_dir,
            camel_case_name: camel_case_value,
            'docs_version': get_docs_version(),
            'anthill_version': anthill.framework.__version__,
        }
        context = dict(context, **options)

        template_dir = self.handle_template(options['template'], base_subdir)
        prefix_length = len(template_dir) + 1

        for root, dirs, files in os.walk(template_dir):

            path_rest = root[prefix_length:]
            relative_dir = path_rest.replace(base_name, name)
            if relative_dir:
                target_dir = path.join(top_dir, relative_dir)
                if not path.exists(target_dir):
                    os.mkdir(target_dir)

            for dirname in dirs[:]:
                if dirname.startswith('.') or dirname == '__pycache__':
                    dirs.remove(dirname)

            for filename in files:
                if filename.endswith(('.pyo', '.pyc', '.py.class')):
                    # Ignore some files as they cause various breakages.
                    continue
                old_path = path.join(root, filename)
                new_path = path.join(top_dir, relative_dir,
                                     filename.replace(base_name, name))
                for old_suffix, new_suffix in self.rewrite_template_suffixes:
                    if new_path.endswith(old_suffix):
                        new_path = new_path[:-len(old_suffix)] + new_suffix
                        break  # Only rewrite once

                if path.exists(new_path):
                    raise InvalidCommand("%s already exists, overlaying a "
                                         "project or app into an existing "
                                         "directory won't replace conflicting "
                                         "files" % new_path)

                # Only render the Python files, as we don't want to
                # accidentally render Anthill templates files
                if new_path.endswith(extensions) or filename in extra_files:
                    with open(old_path, 'r', encoding='utf-8') as template_file:
                        content = template_file.read()
                    template = Template(content)
                    content = template.generate(**context)
                    with open(new_path, 'w', encoding='utf-8') as new_file:
                        new_file.write(to_unicode(content))
                else:
                    shutil.copyfile(old_path, new_path)

                self.stdout.write("Creating %s\n" % new_path)
                try:
                    shutil.copymode(old_path, new_path)
                    self.make_writeable(new_path)
                except OSError:
                    self.stderr.write(
                        "Notice: Couldn't set permission bits on %s. You're "
                        "probably using an uncommon filesystem setup. No "
                        "problem." % new_path)

        if self.paths_to_remove:
            self.stdout.write("Cleaning up temporary files.\n")
            for path_to_remove in self.paths_to_remove:
                if path.isfile(path_to_remove):
                    os.remove(path_to_remove)
                else:
                    shutil.rmtree(path_to_remove)

    def handle_template(self, template, subdir):
        """
        Determine where the app or project templates are.
        Use anthill.__path__[0] as the default because the Anthill install
        directory isn't known.
        """
        if template is None:
            return path.join(anthill.framework.__path__[0], 'conf', subdir)
        else:
            if template.startswith('file://'):
                template = template[7:]
            expanded_template = path.expanduser(template)
            expanded_template = path.normpath(expanded_template)
            if path.isdir(expanded_template):
                return expanded_template
            if self.is_url(template):
                # downloads the file and returns the path
                absolute_path = self.download(template)
            else:
                absolute_path = path.abspath(expanded_template)
            if path.exists(absolute_path):
                return self.extract(absolute_path)

        raise InvalidCommand("couldn't handle %s template %s." %
                             (self.app_or_project, template))

    # noinspection PyMethodMayBeStatic
    def validate_name(self, name, app_or_project):
        a_or_an = 'an' if app_or_project == 'app' else 'a'
        if name is None:
            raise InvalidCommand('you must provide {an} {app} name'.format(
                an=a_or_an,
                app=app_or_project,
            ))
        # Check it's a valid directory name.
        if not name.isidentifier():
            raise InvalidCommand(
                "'{name}' is not a valid {app} name. Please make sure the "
                "name is a valid identifier.".format(
                    name=name,
                    app=app_or_project,
                )
            )
        # Check it cannot be imported.
        try:
            import_module(name)
        except ImportError:
            pass
        else:
            raise InvalidCommand(
                "'{name}' conflicts with the name of an existing Python "
                "module and cannot be used as {an} {app} name. Please try "
                "another name.".format(
                    name=name,
                    an=a_or_an,
                    app=app_or_project,
                )
            )

    def download(self, url):
        """
        Download the given URL and return the file name.
        """

        def cleanup_url(url):
            tmp = url.rstrip('/')
            filename = tmp.split('/')[-1]
            if url.endswith('/'):
                display_url = tmp + '/'
            else:
                display_url = url
            return filename, display_url

        prefix = 'anthill_%s_template_' % self.app_or_project
        tempdir = tempfile.mkdtemp(prefix=prefix, suffix='_download')
        self.paths_to_remove.append(tempdir)
        filename, display_url = cleanup_url(url)

        self.stdout.write("Downloading %s\n" % display_url)
        try:
            the_path, info = urlretrieve(url, path.join(tempdir, filename))
        except IOError as e:
            raise InvalidCommand("couldn't download URL %s to %s: %s" %
                                 (url, filename, e))

        used_name = the_path.split('/')[-1]

        # Trying to get better name from response headers
        content_disposition = info.get('content-disposition')
        if content_disposition:
            _, params = cgi.parse_header(content_disposition)
            guessed_filename = params.get('filename') or used_name
        else:
            guessed_filename = used_name

        # Falling back to content type guessing
        ext = self.splitext(guessed_filename)[1]
        content_type = info.get('content-type')
        if not ext and content_type:
            ext = mimetypes.guess_extension(content_type)
            if ext:
                guessed_filename += ext

        # Move the temporary file to a filename that has better
        # chances of being recognized by the archive utils
        if used_name != guessed_filename:
            guessed_path = path.join(tempdir, guessed_filename)
            shutil.move(the_path, guessed_path)
            return guessed_path

        # Giving up
        return the_path

    # noinspection PyMethodMayBeStatic
    def splitext(self, the_path):
        """
        Like os.path.splitext, but takes off .tar, too
        """
        base, ext = posixpath.splitext(the_path)
        if base.lower().endswith('.tar'):
            ext = base[-4:] + ext
            base = base[:-4]
        return base, ext

    def extract(self, filename):
        """
        Extract the given file to a temporarily and return
        the path of the directory with the extracted content.
        """
        prefix = 'anthill_%s_template_' % self.app_or_project
        tempdir = tempfile.mkdtemp(prefix=prefix, suffix='_extract')
        self.paths_to_remove.append(tempdir)
        self.stdout.write("Extracting %s\n" % filename)
        try:
            archive.extract(filename, tempdir)
            return tempdir
        except (archive.ArchiveException, IOError) as e:
            raise InvalidCommand("couldn't extract file %s to %s: %s" %
                                 (filename, tempdir, e))

    def is_url(self, template):
        """Return True if the name looks like a URL."""
        if ':' not in template:
            return False
        scheme = template.split(':', 1)[0].lower()
        return scheme in self.url_schemes

    # noinspection PyMethodMayBeStatic
    def make_writeable(self, filename):
        """
        Make sure that the file is writeable.
        Useful if our source is read-only.
        """
        if not os.access(filename, os.W_OK):
            st = os.stat(filename)
            new_permissions = stat.S_IMODE(st.st_mode) | stat.S_IWUSR
            os.chmod(filename, new_permissions)
