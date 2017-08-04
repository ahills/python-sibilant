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
unittest for sibilant.ast

author: Christopher O'Brien  <obriencj@gmail.com>
license: LGPL v.3
"""


from fractions import Fraction as fraction
from unittest import TestCase

from sibilant import cons, nil, symbol
from sibilant.ast import *


def simplify(src_str, positions=None):
    if positions is None:
        positions = dict()
    return compose_from_str(src_str).simplify(positions)


class TestCompose(TestCase):

    def test_symbol(self):
        src = "lambda"
        col = compose_from_str(src)
        exp = Symbol((1, 0), "lambda")

        self.assertEqual(col, exp)


    def test_number(self):
        src = "123"
        col = compose_from_str(src)
        exp = Integer((1, 0), "123")

        self.assertEqual(col, exp)

        src = "1.5"
        col = compose_from_str(src)
        exp = Decimal((1, 0), "1.5")

        self.assertEqual(col, exp)

        src = "8+1j"
        col = compose_from_str(src)
        exp = Complex((1, 0), "8+1j")

        self.assertEqual(col, exp)


    def test_fraction(self):
        src = "1/2"
        col = compose_from_str(src)
        exp = Fraction((1, 0), "1/2")

        self.assertEqual(col, exp)


    def test_string(self):
        src = '""'
        col = compose_from_str(src)
        exp = String((1, 0), "")

        self.assertEqual(col, exp)

        src = '"hello world"'
        col = compose_from_str(src)
        exp = String((1, 0), "hello world")

        self.assertEqual(col, exp)


    def test_quote_symbol(self):
        src = "'foo"
        col = compose_from_str(src)
        exp = Quote((1, 0), Symbol((1, 1), "foo"))

        self.assertEqual(col, exp)


    def test_quasi(self):
        src = "`bar"
        col = compose_from_str(src)
        exp = Quasi((1, 0), Symbol((1, 1), "bar"))

        self.assertEqual(col, exp)


    def test_unquote(self):
        src = ",baz"
        col = compose_from_str(src)
        exp = Unquote((1, 0), Symbol((1, 1), "baz"))

        self.assertEqual(col, exp)


    def test_splice(self):
        src = "@qux"
        col = compose_from_str(src)
        exp = Splice((1, 0), Symbol((1, 1), "qux"))

        self.assertEqual(col, exp)


    def test_quote_unquote_splice(self):
        src = "`(,@foo)"
        col = compose_from_str(src)
        exp = Quasi((1, 0),
                    List((1, 1),
                         Unquote((1, 2),
                                 Splice((1, 3),
                                        Symbol((1, 4), "foo")))))

        self.assertEqual(col, exp)


    def test_quote_list(self):
        src = "'(testing a thing)"
        col = compose_from_str(src)
        exp = Quote((1, 0),
                    List((1, 1),
                         Symbol((1, 2), "testing"),
                         Symbol((1, 10), "a"),
                         Symbol((1, 12), "thing")))

        self.assertEqual(col, exp)
        self.assertTrue(col.expression.proper)


    def test_quote_dot(self):
        src = "'(testing . 123)"
        col = compose_from_str(src)

        exp = Quote((1, 0),
                    List((1, 1),
                         Symbol((1, 2), "testing"),
                         Integer((1, 12), "123")))
        exp.expression.proper = False

        self.assertEqual(col, exp)
        self.assertFalse(col.expression.proper)


class TestSimplify(TestCase):

    def test_number(self):
        src = "123"
        col = simplify(src)
        self.assertEqual(col, 123)

        src = "-123"
        col = simplify(src)
        self.assertEqual(col, -123)

        src = "1.5"
        col = simplify(src)
        self.assertEqual(col, 1.5)

        src = ".5"
        col = simplify(src)
        self.assertEqual(col, 0.5)

        src = "1."
        col = simplify(src)
        self.assertEqual(col, 1.0)

        src = "-1.5"
        col = simplify(src)
        self.assertEqual(col, -1.5)

        src = "-.5"
        col = simplify(src)
        self.assertEqual(col, -0.5)

        src = "-1."
        col = simplify(src)
        self.assertEqual(col, -1.0)

        src = "8+1j"
        col = simplify(src)
        self.assertEqual(col, complex("8+1j"))

        src = "3+i"
        col = simplify(src)
        self.assertEqual(col, complex("3+j"))

        src = "-1.1+2j"
        col = simplify(src)
        self.assertEqual(col, complex("-1.1+2j"))


    def test_fraction(self):
        src = "1/2"
        col = simplify(src)
        self.assertEqual(col, cons(symbol("fraction"), "1/2", nil))

        src = "-1/2"
        col = simplify(src)
        self.assertEqual(col, cons(symbol("fraction"), "-1/2", nil))


    def test_string(self):
        src = '""'
        col = simplify(src)
        self.assertEqual(col, "")

        src = ' "" '
        col = simplify(src)
        self.assertEqual(col, "")

        src = '"hello world"'
        col = simplify(src)
        self.assertEqual(col, "hello world")

        src = ' "hello world" '
        col = simplify(src)
        self.assertEqual(col, "hello world")


    def test_literal(self):
        src = "None"
        col = simplify(src)
        self.assertEqual(col, None)

        src = "#t"
        col = simplify(src)
        self.assertEqual(col, True)

        src = "True"
        col = simplify(src)
        self.assertEqual(col, True)

        src = "#f"
        col = simplify(src)
        self.assertEqual(col, False)

        src = "False"
        col = simplify(src)
        self.assertEqual(col, False)

        src = "..."
        col = simplify(src)
        self.assertEqual(col, ...)


    def test_dot(self):

        src = "(1.4)"
        col = simplify(src)
        val = cons(1.4, nil)
        self.assertEqual(col, val)
        self.assertEqual(src, str(val))

        src = "(1. 4)"
        col = simplify(src)
        val = cons(1.0, 4, nil)
        self.assertEqual(col, val)
        # this can't pass, because 1. becomes 1.0
        # self.assertEqual(src, str(val))

        src = "(1 .4)"
        col = simplify(src)
        val = cons(1, 0.4, nil)
        self.assertEqual(col, val)
        # this can't pass, because .4 becomes 0.4
        # self.assertEqual(src, str(val))

        src = "(1 . 4)"
        col = simplify(src)
        val = cons(1, 4)
        self.assertEqual(col, val)
        self.assertEqual(src, str(val))


    def test_unquote_splice(self):
        src = "`(1 2 ,@(3 4))"
        col = simplify(src)
        val = cons(symbol("quasiquote"),
                   cons(1, 2,
                        cons(symbol("unquote-splicing"),
                             cons(3, 4,
                                  nil),
                             nil),
                        nil),
                   nil)
        self.assertEqual(col, val)


#
# The end.
