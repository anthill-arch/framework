from anthill.framework.core.management import Command, Option, InvalidCommand
from anthill.framework.core.management.utils import popen_wrapper, find_command
import concurrent.futures
import codecs
import glob
import os


def has_bom(fn):
    with open(fn, 'rb') as f:
        sample = f.read(4)
    return sample.startswith((codecs.BOM_UTF8, codecs.BOM_UTF16_LE, codecs.BOM_UTF16_BE))


def is_writable(path):
    # Known side effect: updating file access/modified time to current time if
    # it is writable.
    try:
        with open(path, 'a'):
            os.utime(path, None)
    except (IOError, OSError):
        return False
    return True


class CompileMessages(Command):
    help = description = 'Compiles .po files to .mo files for use with builtin gettext support.'

    program = 'msgfmt'
    program_options = ['--check-format']

    def get_options(self):
        options = (
            Option('--locale', '-l', action='append', default=[],
                   help='Locale(s) to process (e.g. de_AT). Default is to process all. '
                        'Can be used multiple times.'),
            Option('--exclude', '-x', action='append', default=[],
                   help='Locales to exclude. Default is none. Can be used multiple times.'),
            Option('--use-fuzzy', '-f', dest='fuzzy', action='store_true',
                   help='Use fuzzy translations.'),
        )
        return options

    def run(self, locale, exclude, fuzzy):
        if fuzzy:
            self.program_options = self.program_options + ['-f']

        if find_command(self.program) is None:
            raise InvalidCommand("Can't find %s. Make sure you have GNU gettext "
                                 "tools 0.15 or newer installed." % self.program)

        basedirs = []
        if os.environ.get('ANTHILL_SETTINGS_MODULE'):
            from anthill.framework.conf import settings
            if settings.LOCALE_PATH is not None:
                basedirs.append(settings.LOCALE_PATH)

        # Walk entire tree, looking for locale directories
        for dirpath, dirnames, filenames in os.walk('.', topdown=True):
            for dirname in dirnames:
                if dirname == 'locale':
                    basedirs.append(os.path.join(dirpath, dirname))

        # Gather existing directories.
        basedirs = set(map(os.path.abspath, filter(os.path.isdir, basedirs)))

        if not basedirs:
            raise InvalidCommand("This script should be run from the Django Git "
                                 "checkout or your project or app tree, or with "
                                 "the settings module specified.")

        # Build locale list
        all_locales = []
        for basedir in basedirs:
            locale_dirs = filter(os.path.isdir, glob.glob('%s/*' % basedir))
            all_locales.extend(map(os.path.basename, locale_dirs))

        # Account for excluded locales
        locales = locale or all_locales
        locales = set(locales).difference(exclude)

        self.has_errors = False
        for basedir in basedirs:
            if locales:
                dirs = [os.path.join(basedir, l, 'LC_MESSAGES') for l in locales]
            else:
                dirs = [basedir]
            locations = []
            for ldir in dirs:
                for dirpath, dirnames, filenames in os.walk(ldir):
                    locations.extend((dirpath, f) for f in filenames if f.endswith('.po'))
            if locations:
                self.compile_messages(locations)

        if self.has_errors:
            raise InvalidCommand('compilemessages generated one or more errors.')

    def compile_messages(self, locations):
        """
        Locations is a list of tuples: [(directory, file), ...]
        """
        with concurrent.futures.ThreadPoolExecutor() as executor:
            futures = []
            for i, (dirpath, f) in enumerate(locations):
                self.stdout.write('processing file %s in %s\n' % (f, dirpath))
                po_path = os.path.join(dirpath, f)
                if has_bom(po_path):
                    self.stderr.write(
                        'The %s file has a BOM (Byte Order Mark). Django only '
                        'supports .po files encoded in UTF-8 and without any BOM.' % po_path
                    )
                    self.has_errors = True
                    continue
                base_path = os.path.splitext(po_path)[0]

                # Check writability on first location
                if i == 0 and not is_writable(base_path + '.mo'):
                    self.stderr.write(
                        'The po files under %s are in a seemingly not writable location. '
                        'mo files will not be updated/created.' % dirpath
                    )
                    self.has_errors = True
                    return

                args = [self.program] + self.program_options + [
                    '-o', base_path + '.mo', base_path + '.po'
                ]
                futures.append(executor.submit(popen_wrapper, args))

            for future in concurrent.futures.as_completed(futures):
                output, errors, status = future.result()
                if status:
                    if errors:
                        self.stderr.write("Execution of %s failed: %s" % (self.program, errors))
                    else:
                        self.stderr.write("Execution of %s failed" % self.program)
                    self.has_errors = True
