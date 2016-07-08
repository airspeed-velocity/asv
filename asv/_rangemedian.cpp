// Licensed under a 3-clause BSD style license - see LICENSE.rst

// Fast range median distance computations for dataset `y`:
//
//    mu(l, r) = median(y[l:r+1])
//    dist(l, r) = sum(abs(x - mu(l, r)) for x in y[l:r+1])
//
// and an implementation of the find-best-partition dynamic program.
//
// We don't implement a rolling median computation, on the assumption that
// accesses are concentrated on small windows in the data.

#include <vector>
#include <queue>
#include <limits>
#include <map>
#include <algorithm>

#include <Python.h>

#define EXTERN_C_BEGIN extern "C" {
#define EXTERN_C_END }


//
// Median computation.
//

template <class const_iterator>
void compute_median(const_iterator start, const_iterator end, double *mu, double *dist)
{
    size_t n = end - start;
    std::vector<double> tmp;
    std::vector<double>::iterator nth;
    tmp.insert(tmp.end(), start, end);

    if (start >= end) {
        *mu = 0;
    }
    else {
        nth = tmp.begin() + n/2;
        std::nth_element(tmp.begin(), nth, tmp.end());

        if (n % 2 == 0) {
            *mu = (*nth + *std::max_element(tmp.begin(), nth)) / 2;
        }
        else {
            *mu = *nth;
        }
    }

    *dist = 0;
    for (const_iterator it = start; it < end; ++it) {
        *dist += fabs(*it - *mu);
    }
}


//
// Cache for cache[left,right] == (mu, dist)
//

class Cache
{
private:
    struct Item
    {
        size_t left, right;
        double mu, dist;
    };

    std::vector<Item> items_;

    size_t idx(size_t left, size_t right) const {
        // Enumeration of pairs
        size_t n = right - left;
        n = (n + left) * (n + left + 1) / 2 + n;
        return n % items_.size();
    }

public:
    Cache(size_t size) : items_(size) {
        std::vector<Item>::iterator it;
        for (it = items_.begin(); it < items_.end(); ++it) {
            it->left = -1;
        }
    }

    bool get(size_t left, size_t right, double *mu, double *dist) const {
        size_t i = idx(left, right);
        if (items_[i].left == left && items_[i].right == right) {
            *mu = items_[i].mu;
            *dist = items_[i].dist;
            return true;
        }
        return false;
    }

    void set(size_t left, size_t right, double mu, double dist) {
        size_t i = idx(left, right);
        items_[i].left = left;
        items_[i].right = right;
        items_[i].mu = mu;
        items_[i].dist = dist;
    }
};


//
// RangeMedian object.
//

typedef struct {
    PyObject_HEAD
    std::vector<double> *y;
    Cache *cache;
} RangeMedianObject;


PyObject *RangeMedian_new(PyTypeObject *type, PyObject *args, PyObject *kwds)
{
    RangeMedianObject *self;
    self = (RangeMedianObject*)type->tp_alloc(type, 0);
    self->y = NULL;
    self->cache = NULL;
    return (PyObject*)self;
}


int RangeMedian_init(RangeMedianObject *self, PyObject *args, PyObject *kwds)
{
    static const char *kwlist[] = {"y", NULL};
    PyObject *y_obj;
    Py_ssize_t size, k;

    if (!PyArg_ParseTupleAndKeywords(args, kwds, "O!", (char**)kwlist,
                                     &PyList_Type, &y_obj)) {
        return -1;
    }

    size = PyList_GET_SIZE(y_obj);

    try {
        self->y = new std::vector<double>(size);

        // Multiplier based on hardcoded constant sizes in step_detect.py, about
        // this many accesses expected --- but prefer primes due to a modulo
        // calculation in the cache.
        self->cache = new Cache(37*size + 401);
    }
    catch (std::bad_alloc) {
        PyErr_SetString(PyExc_MemoryError, "Allocating memory failed");
        return -1;
    }

    for (k = 0; k < size; ++k) {
        PyObject *x;

        x = PyNumber_Float(PyList_GET_ITEM(y_obj, k));
        if (x == NULL || !PyFloat_Check(x)) {
            Py_XDECREF(x);
            return -1;
        }
        (*self->y)[k] = PyFloat_AS_DOUBLE(x);
        Py_DECREF(x);
    }

    return 0;
}


static void RangeMedian_dealloc(RangeMedianObject *self)
{
    delete self->y;
    delete self->cache;
    Py_TYPE(self)->tp_free((PyObject*)self);
}


static int RangeMedian_mu_dist(RangeMedianObject *self, Py_ssize_t left, Py_ssize_t right,
                               double *mu, double *dist)
{
    Py_ssize_t size = (Py_ssize_t)self->y->size();

    if (left < 0 || right < 0 || left >= size || right >= size) {
        PyErr_SetString(PyExc_ValueError, "argument out of range");
        return -1;
    }

    if (!self->cache->get(left, right, mu, dist)) {
        compute_median(self->y->begin() + left, self->y->begin() + right + 1, mu, dist);
        self->cache->set(left, right, *mu, *dist);
    }

    return 0;
}


static PyObject *RangeMedian_mu(RangeMedianObject *self, PyObject *args)
{
    Py_ssize_t left, right;
    double mu = 0, dist;

    if (!PyArg_ParseTuple(args, "nn", &left, &right)) {
        return NULL;
    }

    if (RangeMedian_mu_dist(self, left, right, &mu, &dist) == -1) {
        return NULL;
    }

    return PyFloat_FromDouble(mu);
}


static PyObject *RangeMedian_dist(RangeMedianObject *self, PyObject *args)
{
    Py_ssize_t left, right;
    double mu, dist = 0;

    if (!PyArg_ParseTuple(args, "nn", &left, &right)) {
        return NULL;
    }

    if (RangeMedian_mu_dist(self, left, right, &mu, &dist) == -1) {
        return NULL;
    }

    return PyFloat_FromDouble(dist);
}


static PyObject *RangeMedian_precompute(RangeMedianObject *self, PyObject *args)
{
    Py_ssize_t max_size, min_pos, max_pos;

    if (!PyArg_ParseTuple(args, "nnn", &max_size, &min_pos, &max_pos)) {
        return NULL;
    }

    // noop

    Py_RETURN_NONE;
}


static PyObject *RangeMedian_find_best_partition(RangeMedianObject *self, PyObject *args)
{
    Py_ssize_t min_size, max_size, min_pos, max_pos;
    double gamma;
    Py_ssize_t size;

    if (!PyArg_ParseTuple(args, "dnnnn", &gamma, &min_size, &max_size, &min_pos, &max_pos)) {
        return NULL;
    }

    size = self->y->size();

    if (!(0 < min_size && min_size <= max_size &&
          0 <= min_pos && min_pos <= max_pos && max_pos <= size)) {
        PyErr_SetString(PyExc_ValueError, "invalid input indices");
        return NULL;
    }

    double inf = std::numeric_limits<double>::infinity();

    std::vector<double> B(max_pos - min_pos + 1);
    std::vector<Py_ssize_t> p(max_pos - min_pos);

    B[0] = -gamma;

    for (Py_ssize_t right = min_pos; right < max_pos; ++right) {
        B[right + 1 - min_pos] = inf;

        Py_ssize_t aa = std::max(right + 1 - max_size, min_pos);
        Py_ssize_t bb = std::max(right + 1 - min_size + 1, min_pos);
        for (Py_ssize_t left = aa; left < bb; ++left) {
            double mu, dist;
            if (RangeMedian_mu_dist(self, left, right, &mu, &dist) == -1) {
                return NULL;
            }

            double b = B[left - min_pos] + gamma + dist;
            if (b <= B[right + 1 - min_pos]) {
                B[right + 1 - min_pos] = b;
                p[right - min_pos] = left - 1;
            }
        }
    }

    PyObject *p_list;

    p_list = PyList_New(p.size());
    if (p_list == NULL) {
        return NULL;
    }

    for (Py_ssize_t k = 0; k < (Py_ssize_t)p.size(); ++k) {
#if PY_MAJOR_VERSION >= 3
        PyObject *num = PyLong_FromSsize_t(p[k]);
#else
        PyObject *num = PyInt_FromSsize_t(p[k]);
#endif
        if (num == NULL) {
            Py_DECREF(p_list);
            return NULL;
        }
        PyList_SET_ITEM(p_list, k, num);
    }

    return p_list;
}


//
// RangeMedian type.
//

static PyMethodDef RangeMedian_methods[] = {
    {"mu", (PyCFunction)RangeMedian_mu, METH_VARARGS, NULL},
    {"dist", (PyCFunction)RangeMedian_dist, METH_VARARGS, NULL},
    {"precompute", (PyCFunction)RangeMedian_precompute, METH_VARARGS, NULL},
    {"find_best_partition", (PyCFunction)RangeMedian_find_best_partition, METH_VARARGS, NULL},
    {NULL, NULL}
};

static PyTypeObject RangeMedianType = {
#if PY_MAJOR_VERSION >= 3
    PyVarObject_HEAD_INIT(NULL, 0)
#else
    PyObject_HEAD_INIT(NULL)
    0,
#endif
    "RangeMedian",
    sizeof(RangeMedianObject),
    0,
    (destructor)RangeMedian_dealloc, // tp_dealloc
    0,                          // tp_print
    0,                          // tp_getattr
    0,                          // tp_setattr
    0,                          // tp_compare / tp_reserved
    0,                          // tp_repr
    0,                          // tp_as_number
    0,                          // tp_as_sequence
    0,                          // tp_as_mapping
    0,                          // tp_hash
    0,                          // tp_call
    0,                          // tp_str
    0,                          // tp_getattro
    0,                          // tp_setattro
    0,                          // tp_as_buffer
    Py_TPFLAGS_DEFAULT,         // tp_flags
    NULL,                       // tp_doc
    0,                          // tp_traverse
    0,                          // tp_clear
    0,                          // tp_richcompare
    0,                          // tp_weaklistoffset
    0,                          // tp_iter
    0,                          // tp_iternext
    RangeMedian_methods,        // tp_methods
    0,                          // tp_members
    0,                          // tp_getset
    0,                          // tp_base
    0,                          // tp_dict
    0,                          // tp_descr_get
    0,                          // tp_descr_set
    0,                          // tp_dictoffset
    (initproc)RangeMedian_init, // tp_init
    0,                          // tp_alloc
    RangeMedian_new,            // tp_new
    0,                          // tp_free
    0,                          // tp_is_gc
    0,                          // tp_bases
    0,                          // tp_mro
    0,                          // tp_cache
    0,                          // tp_subclasses
    0,                          // tp_weaklist
    0,                          // tp_del
    0,                          // tp_version_tag
};


static PyTypeObject *RangeMedian_init_type(PyObject *m)
{
#if PY_MAJOR_VERSION < 3
    RangeMedianType.ob_type = &PyType_Type;
#endif

    if (PyType_Ready(&RangeMedianType) < 0) {
        return NULL;
    }

    if (PyModule_AddObject(m, "RangeMedian", (PyObject *)&RangeMedianType) == -1) {
        return NULL;
    }

    return &RangeMedianType;
}


//
// Module initialization.
//

EXTERN_C_BEGIN

#if PY_MAJOR_VERSION >= 3

static struct PyModuleDef moduledef = {
        PyModuleDef_HEAD_INIT,
        "_rangemedian",
        NULL,
        0,
        NULL,
        NULL,
        NULL,
        NULL,
        NULL
};

PyObject *PyInit__rangemedian(void)
{
    PyObject *m;

    m = PyModule_Create(&moduledef);
    if (m == NULL) {
        return NULL;
    }

    if (RangeMedian_init_type(m) == NULL) {
        return NULL;
    }

    return m;
}

#else

PyMODINIT_FUNC init_rangemedian(void)
{
    PyObject *m;

    m = Py_InitModule("_rangemedian", NULL);
    if (m == NULL) {
        return;
    }

    RangeMedian_init_type(m);
}

#endif

EXTERN_C_END
