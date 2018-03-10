# This library is free software; you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as
# published by the Free Software Foundation; either version 3 of the
# License, or (at your option) any later version.
#
# This library is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this library; if not, see
# <http://www.gnu.org/licenses/>.


"""
sibilant.parse

Sibilant's s-expression parser, with run-time modifiable reader macros.

author: Christopher O'Brien  <obriencj@gmail.com>
license: LGPL v.3
"""


from . import symbol, keyword, cons, nil, is_pair, setcdr
from . import SibilantSyntaxError

from contextlib import contextmanager
from fractions import Fraction as fraction
from functools import partial
from io import StringIO
from re import compile as regex


__all__ = (
    "ReaderSyntaxError",
    "SourceStream", "source_open", "source_str", "source_stream",
    "Reader", "default_reader",
)


_symbol_fraction = symbol("fraction")
_symbol_quasiquote = symbol("quasiquote")
_symbol_quote = symbol("quote")
_symbol_splice = symbol("splice")
_symbol_unquote = symbol("unquote")
_symbol_unquote_splicing = symbol("unquote-splicing")


IN_PROGRESS = keyword("work-in-progress")
VALUE = keyword("value")
DOT = keyword("dot")
SKIP = keyword("skip")
CLOSE_PAREN = keyword("close-pair")
EOF = keyword("eof")


_integer_re = regex(r"-?\d+").match
_bin_re = regex(r"0b[01]+").match
_oct_re = regex(r"0o[0-7]+").match
_hex_re = regex(r"0x[\da-f]+").match
_float_re = regex(r"-?((\d*\.\d+|\d+\.\d*)(e-?\d+)?|(\d+e-?\d+))").match
_fraction_re = regex(r"-?\d+/\d+").match
_complex_re = regex(r"-?\d*\.?\d+\+\d*\.?\d*[ij]").match
_keyword_re = regex(r"^(:.+|.+:)$").match


_as_integer = int
_as_bin = partial(int, base=2)
_as_oct = partial(int, base=8)
_as_hex = partial(int, base=16)
_as_float = float


def _as_fraction(s):

    # this will raise a type error if s cannot be parsed into a
    # fraction
    s = fraction(s)

    # the fraction type cannot be stored in a const pool, so we have
    # to turn it into a source form of (fraction NUMERATOR
    # DENOMINATOR) instead. We take the integer values from the
    # parsing attempt above, so that we end up with integers in the
    # const pool rather than the literal string, which should make for
    # faster instantiation of the fraction (parsing once at compile
    # rather than parsing over and over every time we evaluate this
    # code)
    return cons(_symbol_fraction, s.numerator, s.denominator, nil)


def _as_complex(s):
    if s[-1] == "i":
        return complex(s[:-1] + "j")
    else:
        return complex(s)


class ReaderSyntaxError(SibilantSyntaxError):
    """
    An error in sibilant syntax during read time
    """


class Reader(object):

    def __init__(self, nodefaults=False):
        self.reader_macros = {}
        self.atom_patterns = []
        self.terminating = ["\n", "\r", "\t", " "]
        self._terms = "".join(self.terminating)

        if not nodefaults:
            self._add_default_macros()
            self._add_default_atoms()


    def read(self, reader_stream):
        """
        Returns a cons cell, symbol, or numeric value. Returns None if no
        data left in stream. Raises ReaderSyntaxError to complain
        about syntactic difficulties in the stream.
        """

        event, pos, value = self._read(reader_stream)

        if event is VALUE:
            return value
        elif event is EOF:
            # TODO: could probably raise error?
            # TODO: soft-eof condition possible?
            return None
        else:
            raise reader_stream.error("invalid syntax", pos)


    def read_and_position(self, reader_stream):
        """
        Returns a cons cell, symbol, or numeric value. Returns None if no
        data left in stream. Raises ReaderSyntaxError to complain
        about syntactic difficulties in the stream.
        """

        event, pos, value = self._read(reader_stream)

        if event is VALUE:
            return value, pos
        elif event is EOF:
            # TODO: could probably raise error?
            return None, pos
        else:
            raise reader_stream.error("invalid syntax", pos)


    def _read(self, stream):
        while True:
            stream.skip_whitespace()

            position = stream.position()
            c = stream.read()
            if not c:
                return EOF, position, None

            macro = self.reader_macros.get(c, self._read_atom)

            try:
                event, value = macro(stream, c)

            except ValueError as ve:
                # this indicates a conversion issue occurred in the
                # reader macro, most likely in the default reader
                # macro of _read_atom
                raise stream.error(ve.args[0], position) from None

            if is_pair(value):
                value.set_position(position)

            if event is SKIP:
                continue
            else:
                break

        return event, position, value


    def set_event_macro(self, char, macro_fn, terminating=False):
        """
        Adds a character event macro to parser
        """

        for c in char:
            self.reader_macros[c] = macro_fn
            if terminating:
                self.terminating.append(c)

        self._terms = "".join(self.terminating)


    def get_event_macro(self, char):
        """
        Gets a character event macro from parser
        """

        try:
            return (self.reader_macros[char], char in self.terminating)
        except KeyError:
            return None


    def clear_event_macro(self, char):
        """
        Removes a character event macro from parser
        """

        if char in self.reader_macros:
            self.terminating.remove(char)
            self._terms = "".join(self.terminating)
            del self.reader_macros[char]


    @contextmanager
    def temporary_event_macro(self, char, macro_fn, terminating=False):
        """
        Context manager which applies a character event macro to the
        parser and clears is after the context exits.
        """

        old = self.get_event_macro(char)
        self.set_event_macro(char, macro_fn, terminating)

        yield self

        if old is None:
            self.clear_event_macro(char)
        else:
            self.set_event_macro(char, *old)


    def set_macro_character(self, char, macro_fn, terminating=False):
        """
        Adds a reader macro to the parser
        """

        def macro_adapter(stream, char):
            return VALUE, macro_fn(stream, char)

        self.set_event_macro(char, macro_adapter, terminating)


    def temporary_macro_character(self, char, macro_fn, terminating=False):
        """
        Context manager which applies a character macro to the
        parser and clears is after the context exits.
        """

        def macro_adapter(stream, char):
            return VALUE, macro_fn(stream, char)

        return self.temporary_event_macro(char, macro_adapter, terminating)


    def _add_default_macros(self):
        sm = self.set_event_macro

        sm("(", self._read_pair, True)
        sm(")", self._close_paren, True)
        sm('"', self._read_string, True)
        sm("'", self._read_quote, True)
        sm("`", self._read_quasiquote, True)
        sm(";", self._read_comment, True)


    def set_atom_pattern(self, namesym, match_fn, conversion_fn):
        for patt in self.atom_patterns:
            if patt[0] is namesym:
                patt[1] = match_fn
                patt[2] = conversion_fn
                break
        else:
            self.atom_patterns.insert(0, [namesym, match_fn, conversion_fn])


    def get_atom_pattern(self, namesym):
        for patt in self.atom_patterns:
            if patt[0] is namesym:
                return patt
        else:
            return None


    def clear_atom_pattern(self, namesym):
        for index, patt in self.atom_patterns:
            if patt[0] is namesym:
                del patt[0]
                break


    def set_atom_regex(self, namesym, regexstr, conversion_fn):
        match = partial(regex(regexstr).match)
        self.set_atom_pattern(namesym, match, conversion_fn)


    def _add_default_atoms(self):
        ap = self.set_atom_pattern

        ap(symbol("keyword"), _keyword_re, keyword)
        ap(symbol("int"), _integer_re, _as_integer)
        ap(symbol("hex"), _hex_re, _as_hex)
        ap(symbol("oct"), _oct_re, _as_oct)
        ap(symbol("binary"), _bin_re, _as_bin)
        ap(symbol("float"), _float_re, _as_float)
        ap(symbol("complex"), _complex_re, _as_complex)
        ap(symbol("fraction"), _fraction_re, _as_fraction)


    def _read_atom(self, stream, c):
        """
        The default character macro handler, for when nothing else has
        matched.
        """

        atom = c + stream.read_until(self._terms.__contains__)

        if atom == ".":
            return DOT, None

        for name, match, conv in self.atom_patterns:
            if match(atom):
                break
        else:
            conv = symbol

        return VALUE, conv(atom)


    def _read_pair(self, stream, char):
        """
        The character macro handler for pair notation
        """

        result = nil
        work = result

        while True:
            event, position, value = self._read(stream)

            if event is CLOSE_PAREN:
                break

            elif event is DOT:
                if result is nil:
                    # haven't put any items into the result yet, dot
                    # is therefore invalid.
                    raise stream.error("invalid dotted list",
                                       position)

                # improper list, the next item is the tail. Read it
                # and be done.
                event, position, value = self._read(stream)
                if event is not VALUE:
                    raise stream.error("invalid list syntax",
                                       position)
                else:
                    setcdr(work, value)

                # make sure that the list ends immediately after the
                # dotted value.
                close_event, close_pos, value = self._read(stream)
                if close_event is not CLOSE_PAREN:
                    raise stream.error("invalid use of dot in list",
                                       close_pos)
                else:
                    break

            elif event is EOF:
                raise stream.error("unexpected EOF")

            elif result is nil:
                # begin the list. This position will get overwritten.
                result = cons(value, nil)
                result.set_position(position)
                work = result

            else:
                # append to the current list
                new_work = cons(value, nil)
                new_work.set_position(position)
                setcdr(work, new_work)
                work = new_work

        return VALUE, result


    def _close_paren(self, stream, char):
        """
        The character macro handler for a closing parenthesis
        """

        return CLOSE_PAREN, None


    def _read_string(self, stream, char):
        """
        The character macro handler for string literals
        """

        def combine():
            is_escp = partial(str.__eq__, "\\")
            is_char = partial(str.__eq__, char)
            sr = partial(stream.read, 1)
            for C in iter(sr, ''):
                if is_char(C):
                    break
                yield C
                if is_escp(C):
                    yield sr()
            else:
                raise stream.error("Unexpected EOF")

        data = "".join(combine()).encode()
        return VALUE, data.decode("unicode-escape")


    def _read_quote(self, stream, char):
        """
        The character macro handler for quote
        """

        event, pos, child = self._read(stream)

        if event is not VALUE:
            msg = "invalid use of %s" % char
            raise stream.error(msg, pos)

        return VALUE, cons(_symbol_quote, child, nil)


    def _read_quasiquote(self, stream, char):
        """
        The character macro handler for quasiquote
        """

        with self.temporary_event_macro(",", self._read_unquote, True):
            event, pos, child = self._read(stream)

        if event is not VALUE:
            msg = "invalid use of %s" % char
            raise stream.error(msg, pos)

        return VALUE, cons(_symbol_quasiquote, child, nil)


    def _read_unquote(self, stream, char):
        """
        The character macro handler for unquote
        """

        with self.temporary_event_macro("@", self._read_splice, True):
            event, pos, child = self._read(stream)

        if event is not VALUE:
            msg = "invalid use of %s" % char
            raise stream.error(msg, pos)

        if is_pair(child) and child[0] is _symbol_splice:
            value = cons(_symbol_unquote_splicing, child[1])
        else:
            value = cons(_symbol_unquote, child, nil)

        return VALUE, value


    def _read_splice(self, stream, char):
        """
        The character macro handler for splice
        """

        event, pos, child = self._read(stream)

        if event is not VALUE:
            msg = "invalid use of %s" % char
            raise stream.error(msg, pos)

        return VALUE, cons(_symbol_splice, child, nil)


    def _read_comment(self, stream, char):
        """
        The character macro handler for comments
        """

        return SKIP, stream.readline()


@contextmanager
def source_open(filename, auto_skip_exec=True):
    with open(filename, "rt") as fs:
        reader = SourceStream(fs, filename=filename,
                              auto_skip_exec=auto_skip_exec)
        yield reader


def source_str(source_str, filename, auto_skip_exec=True):
    return SourceStream(StringIO(source_str), filename,
                        auto_skip_exec=auto_skip_exec)


def source_stream(source_stream, filename, auto_skip_exec=True):
    return SourceStream(source_stream, filename,
                        auto_skip_exec=auto_skip_exec)


class SourceStream(object):

    def __init__(self, stream, filename, auto_skip_exec=True):

        if not stream.seekable():
            raise TypeError("SourceStream's stream argument must be seekable")

        self.filename = filename
        self.stream = stream

        self.lin = 1
        self.col = 0

        if auto_skip_exec:
            self.skip_exec()


    def position(self):
        """
        The line and column of the next character to be read.

        Line numbers start from 1, columns start from 0
        """

        return self.lin, self.col


    def error(self, message, position=None):
        if position is None:
            position = self.lin, self.col

        return ReaderSyntaxError(message, position, filename=self.filename)


    def read(self, count=1):
        """
        This analyzes each actual read in order to perform line and column
        position counting.
        """

        assert count >= 1, "nonsense read value"

        # see if we can fulfill the count from the read-ahead
        data = self.stream.read(count)

        lin = self.lin
        col = self.col

        for c in data:
            if c == "\n":
                lin += 1
                col = 0
                continue
            elif c == "\r":
                col = 0
                continue
            else:
                col += 1
                continue

        self.lin = lin
        self.col = col

        return data


    def readline(self):
        data = self.stream.readline()
        self.lin += 1
        self.col = 0
        return data


    def peek(self, count=1):
        s = self.stream
        pos = s.tell()
        data = s.read(count)
        s.seek(pos, 0)
        return data


    def __iter__(self):
        return iter(partial(self.read, 1), '')


    def skip_exec(self):
        if self.peek(2) == "#!":
            self.readline()


    def skip_whitespace(self):
        return self.read_until(lambda c: not c.isspace())


    def read_until(self, testf):
        s = self.stream
        pos = s.tell()

        i = 0
        for i, char in enumerate(iter(partial(s.read, 1), ''), 1):
            if testf(char):
                i -= 1
                break

        s.seek(pos, 0)
        return self.read(i) if i else ""


default_reader = Reader()


#
# The end.
