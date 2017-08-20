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


from . import (
    ExpressionCodeSpace, Pseudop, Opcode,
)


class CPython35(ExpressionCodeSpace):
    """
    SpecialCodeSpace emitting bytecode compatible with CPython version
    3.5
    """

    def code_bytes(self, lnt):
        offset = 0
        coll = []

        labels = {}

        def add_label(name):
            labels[name] = offset

        jabs = []

        def mark_jabs(label_name):
            jabs.append((len(coll), label_name))

        jrel = []

        def mark_jrel(label_name):
            jrel.append((len(coll), label_name, offset))

        def set_position(line, col):
            lnt.append((offset, line, col))

        for opa in self.gen_opcode(add_label, set_position):
            op, *args = opa

            if op.hasjabs():
                # deal with jumps, so we can set their argument to
                # an appropriate label offset later

                assert args, "hasjabs without target label"
                mark_jabs(args[0])
                coll.append([op, 0, 0])
                offset += 3

            elif op.hasjrel():
                # relative jump!

                assert args, "hasjrel without target label"
                mark_jrel(args[0])
                coll.append([op, 0, 0])
                offset += 3

            else:
                coll.append((op, *args))
                offset += (1 + len(args))

        if jabs or jrel or labels:
            # Given our labels, modify jmp calls to point to the label
            apply_jump_labels(coll, jabs, jrel, labels)

        coll = ((c.value, *a) for c, *a in coll)
        return b''.join(bytes(c) for c in coll)


    def gen_opcode(self, declare_label, declare_position):
        """
        Given the pseudo operations added to this CodeSpace, the named
        variables declared and requested, yield the CPython opcodes
        and arguments to represent this code.
        """

        for op, *args in self.pseudops:
            if op is Pseudop.POSITION:
                declare_position(*args)

            elif op is Pseudop.CALL:
                n = args[0]
                yield Opcode.CALL_FUNCTION, n, 0

            elif op is Pseudop.CONST:
                i = _const_index(self.consts, args[0])
                yield Opcode.LOAD_CONST, i, 0

            elif op is Pseudop.GET_VAR:
                n = args[0]
                if n in self.cell_vars:
                    i = self.cell_vars.index(n)
                    yield Opcode.LOAD_DEREF, i, 0
                elif n in self.free_vars:
                    i = self.free_vars.index(n) + len(self.cell_vars)
                    yield Opcode.LOAD_DEREF, i, 0
                elif n in self.fast_vars:
                    i = self.fast_vars.index(n)
                    yield Opcode.LOAD_FAST, i, 0
                elif n in self.global_vars:
                    i = self.names.index(n)
                    yield Opcode.LOAD_GLOBAL, i, 0
                else:
                    assert False, "missing var %r" % n

            elif op is Pseudop.SET_VAR:
                n = args[0]
                if n in self.cell_vars:
                    i = self.cell_vars.index(n)
                    yield Opcode.STORE_DEREF, i, 0
                elif n in self.free_vars:
                    i = self.free_vars.index(n) + len(self.cell_vars)
                    yield Opcode.STORE_DEREF, i, 0
                elif n in self.fast_vars:
                    i = self.fast_vars.index(n)
                    yield Opcode.STORE_FAST, i, 0
                elif n in self.global_vars:
                    i = self.names.index(n)
                    yield Opcode.STORE_GLOBAL, i, 0
                else:
                    assert False, "missing var %r" % n

            elif op is Pseudop.DELETE_VAR:
                n = args[0]
                if n in self.cell_vars:
                    i = self.cell_vars.index(n)
                    yield Opcode.DELETE_DEREF, i, 0
                elif n in self.free_vars:
                    i = self.free_vars.index(n) + len(self.cell_vars)
                    yield Opcode.DELETE_DEREF, i, 0
                elif n in self.fast_vars:
                    i = self.fast_vars.index(n)
                    yield Opcode.DELETE_FAST, i, 0
                elif n in self.global_vars:
                    i = self.names.index(n)
                    yield Opcode.DELETE_GLOBAL, i, 0
                else:
                    assert False, "missing var %r" % n

            elif op is Pseudop.GET_GLOBAL:
                n = args[0]
                i = self.names.index(n)
                yield Opcode.LOAD_GLOBAL, i, 0

            elif op is Pseudop.GET_ATTR:
                n = args[0]
                i = self.names.index(n)
                yield Opcode.LOAD_ATTR, i, 0

            elif op is Pseudop.SET_ATTR:
                n = args[0]
                i = self.names.index(n)
                yield Opcode.STORE_ATTR, i, 0

            elif op is Pseudop.DEFINE_GLOBAL:
                n = args[0]
                if n in self.global_vars:
                    i = self.names.index(n)
                    yield Opcode.STORE_GLOBAL, i, 0
                else:
                    assert False, "missing global name %r" % n

            elif op is Pseudop.DEFINE_LOCAL:
                n = args[0]
                if n in self.cell_vars:
                    i = self.cell_vars.index(n)
                    yield Opcode.STORE_DEREF, i, 0
                elif n in self.free_vars:
                    i = self.free_vars.index(n) + len(self.cell_vars)
                    yield Opcode.STORE_DEREF, i, 0
                elif n in self.fast_vars:
                    i = self.fast_vars.index(n)
                    yield Opcode.STORE_FAST, i, 0
                else:
                    assert False, "missing local name %r" % n

            elif op is Pseudop.POP:
                yield Opcode.POP_TOP,

            elif op is Pseudop.LAMBDA:
                yield from self.helper_gen_lambda(*args)

            elif op is Pseudop.RET_VAL:
                yield Opcode.RETURN_VALUE,

            elif op is Pseudop.DUP:
                yield Opcode.DUP_TOP,

            elif op is Pseudop.LABEL:
                declare_label(args[0])

            elif op in (Pseudop.FAUX_PUSH,
                        Pseudop.DEBUG_STACK):
                pass

            elif op is Pseudop.JUMP:
                yield Opcode.JUMP_ABSOLUTE, args[0], 0

            elif op is Pseudop.JUMP_FORWARD:
                yield Opcode.JUMP_FORWARD, args[0], 0

            elif op is Pseudop.POP_JUMP_IF_TRUE:
                yield Opcode.POP_JUMP_IF_TRUE, args[0]

            elif op is Pseudop.POP_JUMP_IF_FALSE:
                yield Opcode.POP_JUMP_IF_FALSE, args[0]

            elif op is Pseudop.CALL_VARARGS:
                yield Opcode.CALL_FUNCTION_VAR, args[0], 0

            elif op is Pseudop.BUILD_TUPLE:
                yield Opcode.BUILD_TUPLE, args[0], 0

            elif op is Pseudop.BUILD_TUPLE_UNPACK:
                yield Opcode.BUILD_TUPLE_UNPACK, args[0], 0

            elif op is Pseudop.SETUP_WITH:
                yield Opcode.SETUP_WITH, args[0], 0

            elif op is Pseudop.WITH_CLEANUP_START:
                yield Opcode.WITH_CLEANUP_START,

            elif op is Pseudop.WITH_CLEANUP_FINISH:
                yield Opcode.WITH_CLEANUP_FINISH,

            elif op is Pseudop.SETUP_EXCEPT:
                yield Opcode.SETUP_EXCEPT, args[0], 0

            elif op is Pseudop.SETUP_FINALLY:
                yield Opcode.SETUP_FINALLY, args[0], 0

            elif op is Pseudop.POP_BLOCK:
                yield Opcode.POP_BLOCK,

            elif op is Pseudop.POP_EXCEPT:
                yield Opcode.POP_EXCEPT,

            elif op is Pseudop.END_FINALLY:
                yield Opcode.END_FINALLY,

            elif op is Pseudop.UNARY_POSITIVE:
                yield Opcode.UNARY_POSITIVE,

            elif op is Pseudop.UNARY_NEGATIVE:
                yield Opcode.UNARY_NEGATIVE,

            elif op is Pseudop.UNARY_NOT:
                yield Opcode.UNARY_NOT,

            elif op is Pseudop.UNARY_INVERT:
                yield Opcode.UNARY_INVERT,

            elif op is Pseudop.ITER:
                yield Opcode.GET_ITER,

            elif op is Pseudop.COMPARE_OP:
                yield Opcode.COMPARE_OP, args[0], 0

            elif op is Pseudop.ITEM:
                yield Opcode.BINARY_SUBSCR,

            elif op is Pseudop.BINARY_ADD:
                yield Opcode.BINARY_ADD,

            elif op is Pseudop.BINARY_SUBTRACT:
                yield Opcode.BINARY_SUBTRACT,

            elif op is Pseudop.BINARY_MULTIPLY:
                yield Opcode.BINARY_MULTIPLY,

            elif op is Pseudop.BINARY_MATRIX_MULTIPLY:
                yield Opcode.BINARY_MATRIX_MULTIPLY,

            elif op is Pseudop.BINARY_TRUE_DIVIDE:
                yield Opcode.BINARY_TRUE_DIVIDE,

            elif op is Pseudop.BINARY_FLOOR_DIVIDE:
                yield Opcode.BINARY_FLOOR_DIVIDE,

            elif op is Pseudop.BINARY_POWER:
                yield Opcode.BINARY_POWER,

            elif op is Pseudop.BINARY_MODULO:
                yield Opcode.BINARY_MODULO,

            elif op is Pseudop.BINARY_LSHIFT:
                yield Opcode.BINARY_LSHIFT,

            elif op is Pseudop.BINARY_RSHIFT:
                yield Opcode.BINARY_RSHIFT,

            elif op is Pseudop.BINARY_AND:
                yield Opcode.BINARY_AND,

            elif op is Pseudop.BINARY_XOR:
                yield Opcode.BINARY_XOR,

            elif op is Pseudop.BINARY_OR:
                yield Opcode.BINARY_OR,

            elif op is Pseudop.RAISE:
                yield Opcode.RAISE_VARARGS, args[0], 0

            elif op is Pseudop.ROT_TWO:
                yield Opcode.ROT_TWO,

            elif op is Pseudop.ROT_THREE:
                yield Opcode.ROT_THREE,

            else:
                assert False, "Unknown Pseudop %r" % op


    def helper_gen_lambda(self, code, default_count=0):
        """
        Helper to _gen_code that handles just lambda definitions
        """

        ci = self.consts.index(code)
        ni = self.consts.index(code.co_name)

        if code.co_freevars:
            # code is a closure, so we'll need to find the matching
            # free/cell vars and provide them.

            for f in code.co_freevars:
                if f in self.cell_vars:
                    fi = self.cell_vars.index(f)
                elif f in self.free_vars:
                    fi = len(self.cell_vars)
                    fi += self.free_vars.index(f)
                else:
                    assert False, "missing local var %r" % f

                yield Opcode.LOAD_CLOSURE, fi, 0

            yield Opcode.BUILD_TUPLE, len(code.co_freevars), 0
            yield Opcode.LOAD_CONST, ci, 0
            yield Opcode.LOAD_CONST, ni, 0
            yield Opcode.MAKE_CLOSURE, default_count, 0

        else:
            # not a closure, so just a pain ol' function
            yield Opcode.LOAD_CONST, ci, 0
            yield Opcode.LOAD_CONST, ni, 0
            yield Opcode.MAKE_FUNCTION, default_count, 0


    def lnt_compile(self, lnt, firstline=None):
        if not lnt:
            return (1 if firstline is None else firstline), b''

        firstline = lnt[0][1] if firstline is None else firstline
        gathered = []

        prev_offset = 0
        prev_line = firstline

        for offset, line, _col in lnt:
            if gathered and line == prev_line:
                continue

            d_offset = (offset - prev_offset)
            d_line = (line - prev_line)

            d_offset &= 0xff

            if d_line < 0:
                # before version 3.6, negative relative line numbers
                # weren't possible. Thus the line of a CALL_FUNCTION
                # is the line it closes on, rather than the line it
                # begins on. So we'll skip this lnt entry.
                continue

            if d_line < -128 or d_line > 127:
                dd_line = (d_line >> 8) & 0xff
                gathered.append(bytes([d_offset, dd_line]))

            d_line &= 0xff
            gathered.append(bytes([d_offset, d_line]))

            prev_offset = offset
            prev_line = line

        res = firstline, b''.join(gathered)
        return res


def _const_index(of_list, value):
    # have to use an `is` comparator, because the list.index method
    # will consider False and 0, and True and 1 to be equivalent,
    # breaking any constant pools containing those values.

    for index, found in enumerate(of_list):
        if found is value:
            return index
    else:
        assert False, "missing constant pool index for value %r" % value


def apply_jump_labels(coll, jabs, jrel, labels):
    for coll_offset, name in jabs:
        target = labels[name]

        coll_jmp = coll[coll_offset]

        coll_jmp[1] = target & 0xff
        coll_jmp[2] = (target >> 8) & 0xff

    for coll_offset, name, off in jrel:
        target = labels[name]
        target -= (off + 3)

        coll_jmp = coll[coll_offset]

        coll_jmp[1] = target & 0xff
        coll_jmp[2] = (target >> 8) & 0xff


#
# The end.
