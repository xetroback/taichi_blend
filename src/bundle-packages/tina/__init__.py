import taichi as ti


setattr(ti, 'static', lambda x, *xs: [x] + list(xs) if xs else x) or setattr(
        ti.Matrix, 'element_wise_writeback_binary', (lambda f: lambda x, y, z:
        (y.__name__ != 'assign' or not setattr(y, '__name__', '_assign'))
        and f(x, y, z))(ti.Matrix.element_wise_writeback_binary)) or setattr(
        ti.Matrix, 'is_global', (lambda f: lambda x: len(x) and f(x))(
        ti.Matrix.is_global))


def V(*xs):
    return ti.Vector(xs)


def totuple(x):
    if x is None:
        x = []
    if isinstance(x, ti.Matrix):
        x = x.entries
    if isinstance(x, list):
        x = tuple(x)
    if not isinstance(x, tuple):
        x = x,
    if isinstance(x, tuple) and len(x) and x[0] is None:
        x = []
    return x


def tovector(x):
    return ti.Vector(totuple(x))


def vconcat(*xs):
    res = []
    for x in xs:
        if isinstance(x, ti.Matrix):
            res.extend(x.entries)
        else:
            res.append(x)
    return ti.Vector(res)


@ti.func
def clamp(x, xmin, xmax):
    return min(xmax, max(xmin, x))


@ti.func
def bilerp(f: ti.template(), pos):
    p = float(pos)
    I = int(ti.floor(p))
    x = p - I
    y = 1 - x
    ti.static_assert(len(f.meta.shape) == 2)
    return (f[I + V(1, 1)] * x[0] * x[1] +
            f[I + V(1, 0)] * x[0] * y[1] +
            f[I + V(0, 0)] * y[0] * y[1] +
            f[I + V(0, 1)] * y[0] * x[1])


def dtype_from_name(name):
    dtypes = 'i8 i16 i32 i64 u8 u16 u32 u64 f32 f64'.split()
    if name in dtypes:
        return getattr(ti, name)
    if name == 'float':
        return float
    if name == 'int':
        return int
    assert False, name


@eval('lambda x: x()')
class A:
    def __init__(self):
        self.nodes = {}

    def __getattr__(self, name):
        if name not in self.nodes:
            raise AttributeError(f'Cannot find any node matches name `{name}`')
        return self.nodes[name].original

    def register(self, cls):
        docs = cls.__doc__.strip().splitlines()

        node_name = None
        inputs = []
        outputs = []
        category = 'uncategorized'
        converter = getattr(cls, 'ns_convert', lambda *x: x)

        for line in docs:
            line = [l.strip() for l in line.split(':', 1)]
            if line[0] == 'Name':
                node_name = line[1].replace(' ', '_')
            if line[0] == 'Inputs':
                inputs = line[1].split()
            if line[0] == 'Output':
                outputs = line[1].split()
            if line[0] == 'Category':
                category = line[1]

        if node_name in self.nodes:
            raise KeyError(f'Node with name `{node_name}` already registered')

        type2socket = {
                'm': 'meta',
                'f': 'field',
                'of': 'object_field',
                'vf': 'vector_field',
                't': 'task',
                'a': 'any',
        }
        type2option = {
                'dt': 'enum',
                'i': 'int',
                'c': 'float',
                'b': 'bool',
                's': 'str',
                'so': 'search_object',
                'i2': 'vec_int_2',
                'i3': 'vec_int_3',
                'c2': 'vec_float_2',
                'c3': 'vec_float_3',
        }
        type2items = {
                'dt': 'float int i8 i16 i32 i64 u8 u16 u32 u64 f32 f64'.split(),
        }

        class Def:
            pass

        if len(inputs):
            name, type = inputs[-1].split(':', 1)
            if name.startswith('*') and name.endswith('s'):
                name = name[1:-1]
                inputs.pop()
                for i in range(2):
                    inputs.append(f'{name}{i}:{type}')

        lut = []
        iopt, isoc = 0, 0
        for i, arg in enumerate(inputs):
            name, type = arg.split(':', 1)
            if type in type2option:
                option = type2option[type]
                lut.append((True, iopt))
                iopt += 1
                setattr(Def, f'option_{iopt}', (name, option))
                if option == 'enum':
                    items = tuple(type2items[type])
                    setattr(Def, f'items_{iopt}', items)
            else:
                socket = type2socket[type]
                lut.append((False, isoc))
                isoc += 1
                setattr(Def, f'input_{isoc}', (name, socket))

        for i, arg in enumerate(outputs):
            name, type = arg.split(':', 1)
            socket = type2socket[type]
            setattr(Def, f'output_{i + 1}', (name, socket))

        def wrapped(self, inputs, options):
            # print('+++', inputs, options)
            args = []
            for isopt, index in lut:
                if isopt:
                    args.append(options[index])
                else:
                    args.append(inputs[index])
            # print('===', cls, args)
            args = converter(*args)
            return cls(*args)

        setattr(Def, 'category', category)
        setattr(Def, 'wrapped', wrapped)
        setattr(Def, 'original', cls)
        self.nodes[node_name] = Def

        return cls


from . import make_meta
from .make_meta import Meta, C


@ti.data_oriented
class IRun:
    @ti.kernel
    def run(self):
        raise NotImplementedError


@ti.data_oriented
class IField:
    is_taichi_class = True

    meta = Meta()

    @ti.func
    def _subscript(self, I):
        raise NotImplementedError

    def subscript(self, *indices):
        I = tovector(indices)
        return self._subscript(I)

    @ti.func
    def __iter__(self):
        for I in ti.grouped(ti.ndrange(*self.meta.shape)):
            yield I


from . import get_meta
from .get_meta import FMeta
from . import edit_meta
from . import specify_meta
from .declare_field import Field
from . import cache_field
from . import double_buffer
from . import bind_source
from . import declare_field
from . import constant_field
from . import uniform_field
from . import flatten_field
from . import bound_sample
from . import repeat_sample 
from . import mix_value
from . import lerp_value
from . import map_range
from . import multiply_value
from . import apply_function
from . import vector_component
from . import vector_length
from . import pack_vector
from . import field_index
from . import field_shuffle
from . import field_bilerp
from . import affine_transform
from . import chessboard_texture
from . import random_generator
from . import gaussian_dist
from . import field_laplacian
from . import field_gradient
from . import copy_field
from . import accumate_field
from . import merge_tasks
from . import repeat_task
from . import null_task
from . import canvas_visualize
from . import static_print


@A.register
def LaplacianBlur(x):
    '''
    Name: laplacian_blur
    Category: stencil
    Inputs: source:f
    Output: result:f
    '''
    return A.mix_value(x, A.field_laplacian(A.bound_sample(x)), 1, 1)


@A.register
def LaplacianStep(pos, vel, kappa):
    '''
    Name: laplacian_step
    Category: physics
    Inputs: pos:f vel:f kappa:c
    Output: vel:f
    '''
    return A.mix_value(vel, A.field_laplacian(A.bound_sample(pos)), 1, kappa)


@A.register
def PosAdvect(pos, vel, dt):
    '''
    Name: advect_position
    Category: physics
    Inputs: pos:f vel:f dt:c
    Output: pos:f
    '''
    return A.mix_value(pos, vel, 1, dt)


__all__ = ['ti', 'A', 'C', 'IRun', 'IField', 'Meta', 'Field', 'FMeta',
           'clamp', 'bilerp', 'totuple', 'tovector', 'V']
