import html.entities
import re
import unicodedata
from gzip import GzipFile
from io import BytesIO

from .functional import keep_lazy, keep_lazy_text, lazy
from .safestring import SafeText, mark_safe


@keep_lazy_text
def capfirst(x):
    """Capitalize the first letter of a string."""
    return x and str(x)[0].upper() + str(x)[1:]


# Set up regular expressions
re_words = re.compile(r'<.*?>|((?:\w[-\w]*|&.*?;)+)', re.S)
re_chars = re.compile(r'<.*?>|(.)', re.S)
re_tag = re.compile(r'<(/)?([^ ]+?)(?:(\s*/)| .*?)?>', re.S)
re_newlines = re.compile(r'\r\n|\r')  # Used in normalize_newlines
re_camel_case = re.compile(r'(((?<=[a-z])[A-Z])|([A-Z](?![A-Z]|$)))')


@keep_lazy_text
def wrap(text, width):
    """
    A word-wrap function that preserves existing line breaks. Expects that
    existing line breaks are posix newlines.

    Preserve all white space except added line breaks consume the space on
    which they break the line.

    Don't wrap long words, thus the output text may have lines longer than
    ``width``.
    """

    def _generator():
        for line in text.splitlines(True):  # True keeps trailing linebreaks
            max_width = min((line.endswith('\n') and width + 1 or width), width)
            while len(line) > max_width:
                space = line[:max_width + 1].rfind(' ') + 1
                if space == 0:
                    space = line.find(' ') + 1
                    if space == 0:
                        yield line
                        line = ''
                        break
                yield '%s\n' % line[:space - 1]
                line = line[space:]
                max_width = min((line.endswith('\n') and width + 1 or width), width)
            if line:
                yield line

    return ''.join(_generator())


@keep_lazy_text
def get_valid_filename(s):
    """
    Return the given string converted to a string that can be used for a clean
    filename. Remove leading and trailing spaces; convert other spaces to
    underscores; and remove anything that is not an alphanumeric, dash,
    underscore, or dot.
    >>> get_valid_filename("john's portrait in 2004.jpg")
    'johns_portrait_in_2004.jpg'
    """
    s = str(s).strip().replace(' ', '_')
    return re.sub(r'(?u)[^-\w.]', '', s)


@keep_lazy_text
def normalize_newlines(text):
    """Normalize CRLF and CR newlines to just LF."""
    return re_newlines.sub('\n', str(text))


@keep_lazy_text
def phone2numeric(phone):
    """Convert a phone number with letters into its numeric equivalent."""
    char2number = {
        'a': '2', 'b': '2', 'c': '2', 'd': '3', 'e': '3', 'f': '3', 'g': '4',
        'h': '4', 'i': '4', 'j': '5', 'k': '5', 'l': '5', 'm': '6', 'n': '6',
        'o': '6', 'p': '7', 'q': '7', 'r': '7', 's': '7', 't': '8', 'u': '8',
        'v': '8', 'w': '9', 'x': '9', 'y': '9', 'z': '9',
    }
    return ''.join(char2number.get(c, c) for c in phone.lower())


# From http://www.xhaus.com/alan/python/httpcomp.html#gzip
# Used with permission.
def compress_string(s):
    zbuf = BytesIO()
    with GzipFile(mode='wb', compresslevel=6, fileobj=zbuf, mtime=0) as zfile:
        zfile.write(s)
    return zbuf.getvalue()


class StreamingBuffer:
    def __init__(self):
        self.vals = []

    def write(self, val):
        self.vals.append(val)

    def read(self):
        if not self.vals:
            return b''
        ret = b''.join(self.vals)
        self.vals = []
        return ret

    def flush(self):
        return

    def close(self):
        return


# Like compress_string, but for iterators of strings.
def compress_sequence(sequence):
    buf = StreamingBuffer()
    with GzipFile(mode='wb', compresslevel=6, fileobj=buf, mtime=0) as zfile:
        # Output headers...
        yield buf.read()
        for item in sequence:
            zfile.write(item)
            data = buf.read()
            if data:
                yield data
    yield buf.read()


# Expression to match some_token and some_token="with spaces" (and similarly
# for single-quoted strings).
smart_split_re = re.compile(r"""
    ((?:
        [^\s'"]*
        (?:
            (?:"(?:[^"\\]|\\.)*" | '(?:[^'\\]|\\.)*')
            [^\s'"]*
        )+
    ) | \S+)
""", re.VERBOSE)


def smart_split(text):
    r"""
    Generator that splits a string by spaces, leaving quoted phrases together.
    Supports both single and double quotes, and supports escaping quotes with
    backslashes. In the output, strings will keep their initial and trailing
    quote marks and escaped quotes will remain escaped (the results can then
    be further processed with unescape_string_literal()).

    >>> list(smart_split(r'This is "a person\'s" test.'))
    ['This', 'is', '"a person\\\'s"', 'test.']
    >>> list(smart_split(r"Another 'person\'s' test."))
    ['Another', "'person\\'s'", 'test.']
    >>> list(smart_split(r'A "\"funky\" style" test.'))
    ['A', '"\\"funky\\" style"', 'test.']
    """
    for bit in smart_split_re.finditer(str(text)):
        yield bit.group(0)


def _replace_entity(match):
    text = match.group(1)
    if text[0] == '#':
        text = text[1:]
        try:
            if text[0] in 'xX':
                c = int(text[1:], 16)
            else:
                c = int(text)
            return chr(c)
        except ValueError:
            return match.group(0)
    else:
        try:
            return chr(html.entities.name2codepoint[text])
        except (ValueError, KeyError):
            return match.group(0)


_entity_re = re.compile(r"&(#?[xX]?(?:[0-9a-fA-F]+|\w{1,8}));")


@keep_lazy_text
def unescape_entities(text):
    return _entity_re.sub(_replace_entity, str(text))


@keep_lazy_text
def unescape_string_literal(s):
    r"""
    Convert quoted string literals to unquoted strings with escaped quotes and
    backslashes unquoted::

        >>> unescape_string_literal('"abc"')
        'abc'
        >>> unescape_string_literal("'abc'")
        'abc'
        >>> unescape_string_literal('"a \"bc\""')
        'a "bc"'
        >>> unescape_string_literal("'\'ab\' c'")
        "'ab' c"
    """
    if s[0] not in "\"'" or s[-1] != s[0]:
        raise ValueError("Not a string literal: %r" % s)
    quote = s[0]
    return s[1:-1].replace(r'\%s' % quote, quote).replace(r'\\', '\\')


@keep_lazy(str, SafeText)
def slugify(value, allow_unicode=False):
    """
    Convert to ASCII if 'allow_unicode' is False. Convert spaces to hyphens.
    Remove characters that aren't alphanumerics, underscores, or hyphens.
    Convert to lowercase. Also strip leading and trailing whitespace.
    """
    value = str(value)
    if allow_unicode:
        value = unicodedata.normalize('NFKC', value)
    else:
        value = unicodedata.normalize('NFKD', value).encode('ascii', 'ignore').decode('ascii')
    value = re.sub(r'[^\w\s-]', '', value).strip().lower()
    return mark_safe(re.sub(r'[-\s]+', '-', value))


def camel_case_to_spaces(value):
    """
    Split CamelCase and convert to lower case. Strip surrounding whitespace.
    """
    return re_camel_case.sub(r' \1', value).strip().lower()


def _format_lazy(format_string, *args, **kwargs):
    """
    Apply str.format() on 'format_string' where format_string, args,
    and/or kwargs might be lazy.
    """
    return format_string.format(*args, **kwargs)


format_lazy = lazy(_format_lazy, str)


def class_name(cls, path=True):
    if path:
        return '.'.join([cls.__module__, cls.__name__])
    return cls.__name__
