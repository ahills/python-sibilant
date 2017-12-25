/*
  This library is free software; you can redistribute it and/or modify
  it under the terms of the GNU Lesser General Public License as
  published by the Free Software Foundation; either version 3 of the
  License, or (at your option) any later version.

  This library is distributed in the hope that it will be useful, but
  WITHOUT ANY WARRANTY; without even the implied warranty of
  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
  Lesser General Public License for more details.

  You should have received a copy of the GNU Lesser General Public
  License along with this library; if not, see
  <http://www.gnu.org/licenses/>.
*/


#include "ctypes.h"


#define DOCSTR "Native Sibilant core types"


#ifndef offsetof
#define offsetof(TYPE, MEMBER) ((size_t) &((TYPE *)0)->MEMBER)
#endif


#if 1
#define DEBUGMSG(msg, obj) {					\
    printf("** " msg " ");					\
    (obj) && PyObject_Print(((PyObject *) (obj)), stdout, 0);	\
    printf("\n");						\
  }
#else
#define DEBUGMSG(msg, obj) {}
#endif


/* === interned atom === */


#define ATOM_NAME(o) (((SibInternedAtom *)self)->name)


static PyObject *_str_split = NULL;
static PyObject *_str_rsplit = NULL;


static PyObject *atom_new(PyObject *name,
			  PyObject *intern,
			  PyTypeObject *type) {

  SibInternedAtom *n = NULL;

  if(! name) {
    PyErr_SetString(PyExc_TypeError, "interned atom requires a name");
    return NULL;

  } else if (! PyUnicode_CheckExact(name)) {
    name = PyObject_Str(name);

  } else{
    Py_INCREF(name);
  }

  n = (SibInternedAtom *) PyDict_GetItem(intern, name);

  if (! n) {
    n = (SibInternedAtom *) PyObject_New(SibInternedAtom, type);
    n->name = name;
    n->weakrefs = NULL;

    // DEBUGMSG("allocating and interning new atom", n);

    PyDict_SetItem(intern, name, (PyObject *) n);

    // make the intern a borrowed ref. This allows refcount to drop to
    // zero, at which point the deallocation of the symbol will clear
    // it from the intern dict.
    Py_DECREF(n);

  } else {
    // DEBUGMSG("returning previously interned atom", n);

    Py_INCREF(n);
    Py_DECREF(name);
  }

  return (PyObject *) n;
}


static PyObject *atom_repr(PyObject *self) {
  return PyUnicode_FromFormat("<%s %R>",
			      self->ob_type->tp_name,
			      ATOM_NAME(self));
}


static PyObject *atom_str(PyObject *self) {
  PyObject *name = ATOM_NAME(self);
  Py_INCREF(name);
  return name;
}


static void atom_rewrap(PyObject *vals, unaryfunc conv) {
  for (int index = PyList_Size(vals); index--; ) {
    PyList_SetItem(vals, index, conv(PyList_GET_ITEM(vals, index)));
  }
}


/* === symbol === */


static PyObject *intern_syms = NULL;


PyObject *sib_symbol(PyObject *name) {
  return atom_new(name, intern_syms, &SibSymbolType);
}


static void symbol_dealloc(PyObject *self) {
  SibInternedAtom *s = (SibInternedAtom *) self;

  if (s->weakrefs != NULL)
    PyObject_ClearWeakRefs(self);

  PyDict_DelItem(intern_syms, s->name);

  Py_DECREF(s->name);
  Py_TYPE(self)->tp_free(self);
}


static PyObject *symbol_new(PyTypeObject *type,
			    PyObject *args, PyObject *kwds) {

  PyObject *name = NULL;

  if (kwds && PyDict_Size(kwds)) {
    PyErr_SetString(PyExc_TypeError, "symbol takes no named arguments");
    return NULL;
  }

  if (! PyArg_ParseTuple(args, "O:symbol", &name))
    return NULL;

  return sib_symbol(name);
}


static PyObject *symbol_split(PyObject *self,
			      PyObject *args, PyObject *kwds) {

  PyObject *name = ATOM_NAME(self);
  PyObject *method = NULL;
  PyObject *result = NULL;

  method = PyObject_GetAttr(name, _str_split);
  if (! method)
    return NULL;

  result = PyObject_Call(method, args, kwds);
  Py_CLEAR(method);
  if (! result)
    return NULL;

  atom_rewrap(result, sib_symbol);
  return result;
}


static PyObject *symbol_rsplit(PyObject *self,
			       PyObject *args, PyObject *kwds) {

  PyObject *name = ATOM_NAME(self);
  PyObject *method = NULL;
  PyObject *result = NULL;

  method = PyObject_GetAttr(name, _str_rsplit);
  if (! method)
    return NULL;

  result = PyObject_Call(method, args, kwds);
  Py_CLEAR(method);
  if (! result)
    return NULL;

  atom_rewrap(result, sib_symbol);
  return result;
}


static PyMethodDef symbol_methods[] = {
  { "split", (PyCFunction) symbol_split, METH_VARARGS|METH_KEYWORDS,
    "S.split(sep=None, maxsplit=-1) -> list of keywords" },

  { "rsplit", (PyCFunction) symbol_rsplit, METH_VARARGS|METH_KEYWORDS,
    "S.rsplit(sep=None, maxsplit=-1) -> list of keywords" },

  { NULL, NULL, 0, NULL },
};


PyTypeObject SibSymbolType = {
  PyVarObject_HEAD_INIT(NULL, 0)

  "symbol",
  sizeof(SibInternedAtom),
  0,

  .tp_flags = Py_TPFLAGS_DEFAULT,
  .tp_methods = symbol_methods,
  .tp_new = symbol_new,
  .tp_dealloc = symbol_dealloc,
  .tp_weaklistoffset = offsetof(SibInternedAtom, weakrefs),

  .tp_repr = atom_repr,
  .tp_str = atom_str,
};


/* === keyword === */


static PyObject *intern_kwds = NULL;
static PyObject *_str_strip = NULL;
static PyObject *_str_colon = NULL;


PyObject *sib_keyword(PyObject *name) {
  PyObject *clean;
  PyObject *result;

  if(! name) {
    PyErr_SetString(PyExc_TypeError, "keywrod requires a name");
    return NULL;

  } else if (! PyUnicode_CheckExact(name)) {
    name = PyObject_Str(name);

  } else{
    Py_INCREF(name);
  }

  clean = PyObject_CallMethodObjArgs(name, _str_strip, _str_colon, NULL);
  result = atom_new(clean, intern_kwds, &SibKeywordType);

  Py_DECREF(name);
  Py_DECREF(clean);

  return result;
}


static PyObject *keyword_new(PyTypeObject *type,
			     PyObject *args, PyObject *kwds) {

  PyObject *name = NULL;

  if (kwds && PyDict_Size(kwds)) {
    PyErr_SetString(PyExc_TypeError, "keyword takes no named arguments");
    return NULL;
  }

  if (! PyArg_ParseTuple(args, "O:keyword", &name))
    return NULL;

  return sib_keyword(name);
}


static void keyword_dealloc(PyObject *self) {
  SibInternedAtom *s = (SibInternedAtom *) self;

  if (s->weakrefs != NULL)
    PyObject_ClearWeakRefs(self);

  PyDict_DelItem(intern_kwds, s->name);

  Py_DECREF(s->name);
  Py_TYPE(self)->tp_free(self);
}


static PyObject *keyword_split(PyObject *self,
			       PyObject *args, PyObject *kwds) {

  PyObject *name = ATOM_NAME(self);
  PyObject *method = NULL;
  PyObject *result = NULL;

  method = PyObject_GetAttr(name, _str_split);
  if (! method)
    return NULL;

  result = PyObject_Call(method, args, kwds);
  Py_CLEAR(method);
  if (! result)
    return NULL;

  atom_rewrap(result, sib_keyword);
  return result;
}


static PyObject *keyword_rsplit(PyObject *self,
				PyObject *args, PyObject *kwds) {

  PyObject *name = ATOM_NAME(self);
  PyObject *method = NULL;
  PyObject *result = NULL;

  method = PyObject_GetAttr(name, _str_rsplit);
  if (! method)
    return NULL;

  result = PyObject_Call(method, args, kwds);
  Py_CLEAR(method);
  if (! result)
    return NULL;

  atom_rewrap(result, sib_keyword);
  return result;
}


static PyMethodDef keyword_methods[] = {
  { "split", (PyCFunction) keyword_split, METH_VARARGS|METH_KEYWORDS,
    "K.split(sep=None, maxsplit=-1) -> list of keywords" },

  { "rsplit", (PyCFunction) keyword_rsplit, METH_VARARGS|METH_KEYWORDS,
    "K.rsplit(sep=None, maxsplit=-1) -> list of keywords" },

  { NULL, NULL, 0, NULL },
};


PyTypeObject SibKeywordType = {
  PyVarObject_HEAD_INIT(NULL, 0)

  "keyword",
  sizeof(SibInternedAtom),
  0,

  .tp_flags = Py_TPFLAGS_DEFAULT,
  .tp_methods = keyword_methods,
  .tp_new = keyword_new,
  .tp_dealloc = keyword_dealloc,
  .tp_weaklistoffset = offsetof(SibInternedAtom, weakrefs),

  .tp_repr = atom_repr,
  .tp_str = atom_str,
};


/* === pair === */


#define CONS(h, t) sib_pair((h), (t))

#define CAR(p) (((SibPair *) (p))->head)

#define CDR(p) (((SibPair *) (p))->tail)

#define SETCAR(p, v) {				\
    Py_INCREF(v);				\
    Py_XDECREF(CAR(p));				\
    CAR(p) = v;					\
  }

#define SETCDR(p, v) {				\
    Py_INCREF(v);				\
    Py_XDECREF(CDR(p));				\
    CDR(p) = v;					\
  }


static PyObject *_str_empty = NULL;
static PyObject *_str_space = NULL;
static PyObject *_str_cons_paren = NULL;
static PyObject *_str_comma_space = NULL;
static PyObject *_str_open_paren = NULL;
static PyObject *_str_close_paren = NULL;
static PyObject *_str_recursive_true = NULL;
static PyObject *_str_space_elipsis = NULL;
static PyObject *_str_space_dot_space = NULL;
static PyObject *_str_quote = NULL;
static PyObject *_str_esc_quote = NULL;


static PyObject *pair_new(PyTypeObject *type,
			  PyObject *args, PyObject *kwds) {

  PyObject *head = NULL;
  PyObject *tail = NULL;

  if (kwds && PyDict_Size(kwds)) {
    PyErr_SetString(PyExc_TypeError, "pair takes no named arguments");
    return NULL;
  }

  if (! PyArg_ParseTuple(args, "OO:pair", &head, &tail))
    return NULL;

  return sib_pair(head, tail);
}


static void pair_dealloc(PyObject *self) {
  SibPair *s = (SibPair *) self;

  if (s->weakrefs != NULL)
    PyObject_ClearWeakRefs(self);

  Py_XDECREF(s->head);
  Py_XDECREF(s->tail);
  Py_XDECREF(s->position);

  Py_TYPE(self)->tp_free(self);
}


static Py_ssize_t pair_length(PyObject *self) {
  return 2;
}


static PyObject *pair_getitem(PyObject *self, Py_ssize_t index) {
  PyObject *result = NULL;

  switch(index) {
  case 0:
    result = CAR(self);
    break;
  case 1:
    result = CDR(self);
    break;
  default:
    PyErr_SetString(PyExc_IndexError, "pair index out of range");
  }

  Py_XINCREF(result);
  return result;
}


static int pair_setitem(PyObject *self, Py_ssize_t index, PyObject *val) {
  int result = 0;

  switch(index) {
  case 0:
    SETCAR(self, val);
    break;
  case 1:
    SETCDR(self, val);
    break;
  default:
    PyErr_SetString(PyExc_IndexError, "pair index out of range");
    result = -1;
  }

  return result;
}


static PySequenceMethods pair_as_sequence = {
  .sq_length = pair_length,
  .sq_item = pair_getitem,
  .sq_ass_item = pair_setitem,
};


static PyObject *pair_iter(PyObject *self) {
  SibPairIterator *i = NULL;

  i = (SibPairIterator *) PyObject_New(SibPairIterator, &SibPairIteratorType);
  Py_INCREF(self);
  i->pair = self;
  i->index = 0;

  return (PyObject *) i;
}


static PyObject *pair_repr(PyObject *self) {
  PyObject *tmp = NULL;
  PyObject *col = PyList_New(0);
  PyObject *found = PyDict_New();
  size_t index = 0;

  PyObject *rest = self;
  PyObject *rest_id;

  PyList_Append(col, _str_cons_paren);

  while (rest->ob_type == &SibPairType) {
    rest_id = PyLong_FromVoidPtr(rest);

    if (PyDict_Contains(found, rest_id)) {
      PyList_Append(col, _str_recursive_true);

      if (rest != self) {
	tmp = PyDict_GetItem(found, rest_id);
	PyList_Insert(col, PyLong_AsSize_t(tmp) - 1, _str_cons_paren);
	PyList_Append(col, _str_close_paren);
      }
      Py_DECREF(rest_id);
      rest = NULL;
      break;

    } else {
      index += 2;

      tmp = PyLong_FromSize_t(index);
      PyDict_SetItem(found, rest_id, tmp);
      Py_DECREF(tmp);

      tmp = PyObject_Repr(CAR(rest));
      PyList_Append(col, tmp);
      PyList_Append(col, _str_comma_space);
      Py_DECREF(tmp);

      rest = CDR(rest);
      Py_DECREF(rest_id);
    }
  }

  if (rest) {
    PyList_Append(col, PyObject_Repr(rest));
  }

  PyList_Append(col, _str_close_paren);

  tmp = PyUnicode_Join(_str_empty, col);
  Py_DECREF(col);
  Py_DECREF(found);

  return tmp;
}


static PyObject *quoted(PyObject *u) {
  PyObject *tmp, *result;

  tmp = PyUnicode_Replace(u, _str_quote, _str_esc_quote, -1);
  result = PyUnicode_FromFormat("\"%U\"", tmp);
  Py_DECREF(tmp);

  return result;
}


static PyObject *pair_str(PyObject *self) {
  PyObject *tmp = NULL;
  PyObject *col = PyList_New(0);
  PyObject *found = PySet_New(NULL);

  PyObject *rest = NULL;
  PyObject *rest_id = NULL;

  for (rest = self; !Sib_Nilp(rest); rest = CDR(rest)) {
    if (rest->ob_type == &SibPairType) {
      rest_id = PyLong_FromVoidPtr(rest);

      if (PySet_Contains(found, rest_id)) {
	PyList_Append(col, _str_space_elipsis);
	break;

      } else {
	PySet_Add(found, rest_id);
	PyList_Append(col, _str_space);

	tmp = CAR(rest);
	if (PyUnicode_CheckExact(tmp)) {
	  tmp = quoted(tmp);
	} else {
	  tmp = PyObject_Str(tmp);
	}

	PyList_Append(col, tmp);
	Py_DECREF(tmp);
      }

    } else {
      /* end of improper list */
      PyList_Append(col, _str_space_dot_space);
      tmp = PyObject_Str(rest);
      PyList_Append(col, tmp);
      Py_DECREF(tmp);
      break;
    }
  }

  Py_INCREF(_str_open_paren);
  PyList_SetItem(col, 0, _str_open_paren);
  PyList_Append(col, _str_close_paren);

  tmp = PyUnicode_Join(_str_empty, col);
  Py_DECREF(col);
  Py_DECREF(found);

  return tmp;
}


PyTypeObject SibPairType = {
  PyVarObject_HEAD_INIT(NULL, 0)

  "pair",
  sizeof(SibPair),
  0,

  .tp_flags = Py_TPFLAGS_DEFAULT,
  .tp_new = pair_new,
  .tp_dealloc = pair_dealloc,
  .tp_weaklistoffset = offsetof(SibPair, weakrefs),

  .tp_iter = pair_iter,
  .tp_as_sequence = &pair_as_sequence,

  .tp_repr = pair_repr,
  .tp_str = pair_str,
};


PyObject *sib_pair(PyObject *head, PyObject *tail) {
  SibPair *self = NULL;

  if (! (head && tail)) {
    PyErr_SetString(PyExc_TypeError, "pair requires a head and a tail");
    return NULL;
  }

  self = PyObject_New(SibPair, &SibPairType);
  self->position = NULL;
  self->weakrefs = NULL;

  Py_INCREF(head);
  self->head = head;

  Py_INCREF(tail);
  self->tail = tail;

  // DEBUGMSG("made a pair", self);
  // DEBUGMSG(" head is", CAR(self));
  // DEBUGMSG(" tail is", CDR(self));

  return (PyObject *) self;
}


/* -- PairIteratorType -- */


static void piter_dealloc(PyObject *self) {
  SibPairIterator *s = (SibPairIterator *) self;
  Py_XDECREF(s->pair);
  Py_TYPE(self)->tp_free(self);
}


static PyObject *piter_iternext(PyObject *self) {
  SibPairIterator *s = (SibPairIterator *) self;
  PyObject *pair = s->pair;
  PyObject *result = NULL;

  if (pair) {
    switch(s->index) {
    case 0:
      result = CAR(pair);
      s->index = 1;
      break;
    case 1:
      result = CDR(pair);
      s->index = 2;
    default:
      Py_CLEAR(s->pair);
    }
  }

  Py_XINCREF(result);
  return result;
}


PyTypeObject SibPairIteratorType = {
  PyVarObject_HEAD_INIT(NULL, 0)

  "pair_iterator",
  sizeof(SibPairIterator),
  0,

  .tp_flags = Py_TPFLAGS_DEFAULT,
  .tp_dealloc = piter_dealloc,
  .tp_iter = PyObject_SelfIter,
  .tp_iternext = piter_iternext,
};


/* --- NilType --- */


static PyObject *_str_nil = NULL;


static PyObject *nil_new(PyTypeObject *type,
			 PyObject *args, PyObject *kwds) {

  if (PyTuple_Size(args) || (kwds && PyDict_Size(kwds))) {
    PyErr_SetString(PyExc_TypeError, "NilType takes no arguments");
    return NULL;
  }

  Py_INCREF(Sib_Nil);
  return Sib_Nil;
}


static void nil_dealloc(PyObject *self) {
  ;
}


static PyObject *nil_repr(PyObject *self) {
  Py_INCREF(_str_nil);
  return _str_nil;
}


static PyObject *nil_iter(PyObject *self) {
  SibPairIterator *i = NULL;

  i = (SibPairIterator *) PyObject_New(SibPairIterator, &SibPairIteratorType);
  i->index = 0;
  i->pair = NULL;

  return (PyObject *) i;
}


static Py_ssize_t nil_length(PyObject *selfs) {
  return 0;
}


static PyObject *nil_getitem(PyObject *self, Py_ssize_t index) {
  PyErr_SetString(PyExc_IndexError, "nil has no items");
  return NULL;
}


static int nil_setitem(PyObject *self, Py_ssize_t index, PyObject *val) {
  PyErr_SetString(PyExc_IndexError, "nil has no items");
  return -1;
}


static PySequenceMethods nil_as_sequence = {
  .sq_length = nil_length,
  .sq_item = nil_getitem,
  .sq_ass_item = nil_setitem,
};


static int nil_bool(PyObject *v) {
  return 0;
}


static PyNumberMethods nil_as_number = {
  .nb_bool = (inquiry) nil_bool,
};


PyTypeObject SibNilType = {
  PyVarObject_HEAD_INIT(NULL, 0)

  "NilType",
  sizeof(SibPair),
  0,

  .tp_flags = Py_TPFLAGS_DEFAULT,
  .tp_base = &SibPairType,
  .tp_new = nil_new,
  .tp_dealloc = nil_dealloc,
  .tp_weaklistoffset = offsetof(SibPair, weakrefs),

  .tp_repr = nil_repr,
  .tp_str = nil_repr,
  .tp_iter = nil_iter,
  .tp_as_number = &nil_as_number,
  .tp_as_sequence = &nil_as_sequence,
};


SibPair _SibNil = {
  {
    _PyObject_EXTRA_INIT
    1, &SibNilType,
  },
  .head = NULL,
  .tail = NULL,
  .position = NULL,
  .weakrefs = NULL,
};


/* -- module -- */


static PyObject *m_cons(PyObject *mod, PyObject *args, PyObject *kwds) {
  PyObject *pair = NULL;

  return pair;
}


static PyObject *m_car(PyObject *mod, PyObject *args) {
  PyObject *pair = NULL;
  PyObject *result;

  if (! PyArg_ParseTuple(args, "O!:car", &SibPairType, &pair))
    return NULL;

  if (Sib_Nilp(pair)) {
    PyErr_SetString(PyExc_TypeError, "cannot get car of nil");
    return NULL;
  }

  result = CAR(pair);
  Py_INCREF(result);
  return result;
}


static PyObject *m_setcar(PyObject *mod, PyObject *args) {
  PyObject *pair = NULL;
  PyObject *val = NULL;

  if (! PyArg_ParseTuple(args, "O!O:setcar", &SibPairType, &pair, &val))
    return NULL;

  if (Sib_Nilp(pair)) {
    PyErr_SetString(PyExc_TypeError, "cannot set car of nil");
    return NULL;
  }

  SETCAR(pair, val);
  Py_RETURN_NONE;
}


static PyObject *m_setcdr(PyObject *mod, PyObject *args) {
  PyObject *pair = NULL;
  PyObject *val = NULL;

  if (! PyArg_ParseTuple(args, "O!O:setcdr", &SibPairType, &pair, &val))
    return NULL;

  if (Sib_Nilp(pair)) {
    PyErr_SetString(PyExc_TypeError, "cannot set cdr of nil");
    return NULL;
  }

  SETCDR(pair, val);
  Py_RETURN_NONE;
}


static PyObject *m_cdr(PyObject *mod, PyObject *args) {
  PyObject *pair = NULL;
  PyObject *result;

  if (! PyArg_ParseTuple(args, "O!:cdr", &SibPairType, &pair))
    return NULL;

  if (Sib_Nilp(pair)) {
    PyErr_SetString(PyExc_TypeError, "cannot get cdr of nil");
    return NULL;
  }

  result = CDR(pair);
  Py_INCREF(result);
  return result;
}


static PyMethodDef methods[] = {
  { "cons", (PyCFunction) m_cons, METH_VARARGS|METH_KEYWORDS,
    "cons(head, *tail, recursive=Fasle)" },

  { "car", m_car, METH_VARARGS,
    "car(P)" },

  { "cdr", m_cdr, METH_VARARGS,
    "cdr(P)" },

  { "setcar", m_setcar, METH_VARARGS,
    "setcar(P, head)" },

  { "setcdr", m_setcdr, METH_VARARGS,
    "setcdr(P, tail)" },

  { NULL, NULL, 0, NULL },
};


static struct PyModuleDef ctypes = {
  .m_base = PyModuleDef_HEAD_INIT,
  .m_name = "sibilant.ctypes",
  .m_doc = DOCSTR,
  .m_size = -1,
  .m_methods = methods,
  .m_slots = NULL,
  .m_traverse = NULL,
  .m_clear = NULL,
  .m_free = NULL,
};


#define STR_CONST(which, val) {			\
    if (! (which))				\
      which = PyUnicode_FromString(val);	\
  }


PyMODINIT_FUNC PyInit_ctypes(void) {

  PyObject *mod, *dict;

  if (PyType_Ready(&SibPairType) < 0)
    return NULL;

  if (PyType_Ready(&SibNilType) < 0)
    return NULL;

  if (PyType_Ready(&SibKeywordType) < 0)
    return NULL;

  if (PyType_Ready(&SibSymbolType) < 0)
    return NULL;

  STR_CONST(_str_nil, "nil");
  STR_CONST(_str_split, "split");
  STR_CONST(_str_rsplit, "rsplit");
  STR_CONST(_str_strip, "strip");
  STR_CONST(_str_colon, ":");

  STR_CONST(_str_empty, "");
  STR_CONST(_str_space, " ");
  STR_CONST(_str_cons_paren, "cons(");
  STR_CONST(_str_comma_space, ", ");
  STR_CONST(_str_open_paren, "(");
  STR_CONST(_str_close_paren, ")");
  STR_CONST(_str_recursive_true, "recursive=True");
  STR_CONST(_str_space_elipsis, " ...");
  STR_CONST(_str_space_dot_space, " . ");
  STR_CONST(_str_quote, "\"");
  STR_CONST(_str_esc_quote, "\\\"");

  if (! intern_syms) {
    intern_syms = PyDict_New();
    if (! intern_syms)
      return NULL;
  }

  if (! intern_kwds) {
    intern_kwds = PyDict_New();
    if (! intern_kwds)
      return NULL;
  }

  mod = PyModule_Create(&ctypes);
  if (! mod)
    return NULL;

  dict = PyModule_GetDict(mod);
  PyDict_SetItemString(dict, "nil", Sib_Nil);
  PyDict_SetItemString(dict, "pair", (PyObject *) &SibPairType);
  PyDict_SetItemString(dict, "symbol", (PyObject *) &SibSymbolType);
  PyDict_SetItemString(dict, "keyword", (PyObject *) &SibKeywordType);

  return mod;
}


/* The end. */
