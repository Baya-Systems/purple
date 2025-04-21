'''
MIT Licence: Copyright (c) 2025 Baya Systems <https://bayasystems.com>

Purple Tests
======================

Bit-Vector-Leaf testing

Tests:
    * transient infinite width
    * static infinite width

FIXME:
    * transient fixed-width
    * static fixed-width
    * many operators
'''

from purple import BitVector, FieldLocation
import cli


def test_ops(bv_cls, no_negs = False):
    print('transient Bit-Vector tests', bv_cls)

    assert bv_cls(100) == 100

    assert bv_cls(100) + 10 == 110
    assert bv_cls(100) << 2 == 400
    assert bv_cls(100) // 3 == 33
    assert 33.33 < bv_cls(100) / 3 < 33.34
    assert 20 + bv_cls(100) == 120
    assert 20 << bv_cls(3) == 160
    assert hex(bv_cls(0xaa) & 0x5a) == '0xa'

    assert bv_cls(34) > 33
    assert bv_cls(34) < 35
    assert 37 >= bv_cls(34)

    assert bv_cls(0xaa)[1] == 1
    assert bv_cls(0xaa)[2] == 0

    assert hex(bv_cls(0xb5)[4:]) == '0xb'
    assert hex(bv_cls(0xb5)[:4]) == '0x5'
    assert hex(bv_cls(0x6b5)[4:8]) == '0xb'
    assert hex(bv_cls(0x6b5)[4:8]) == '0xb'
    assert hex(bv_cls(0x6b5)[4:4]) == '0x0'

    a = bv_cls(0x6b5)
    a[:4] = 9
    assert hex(a) == '0x6b9'
    a[8:] = 12
    assert hex(a) == '0xcb9'
    a[4:8] = 1
    assert hex(a) == '0xc19'
    a[4:4] = 0
    assert hex(a) == '0xc19'

    assert hex(bv_cls(0x6b5)[FieldLocation(start = 4, width = 4)]) == '0xb'

    a = bv_cls(0x6b5)
    a[FieldLocation(start = 0, width = 4)] = 9
    assert hex(a) == '0x6b9'

    bv_1 = bv_cls(0x88)
    bv_2 = bv_1
    bv_3 = +bv_1
    bv_2[:4] = 1
    bv_3[4:] = 1
    assert (hex(bv_1), hex(bv_2), hex(bv_3)) == ('0x81', '0x81', '0x18')

    assert no_negs or -bv_cls(100) == -100
    assert abs(bv_cls(100)) == 100
    assert no_negs or abs(bv_cls(-100)) == 100

    bv_1 = bv_cls(0x55)
    assert [hex(bv_1.aligned(x)) for x in range(7, -1, -1)] == \
        ['0x0', '0x40', '0x40', '0x50', '0x50', '0x54', '0x54', '0x55']

    for x,v in zip(range(7, -1, -1), ['0x0', '0x40', '0x40', '0x50', '0x50', '0x54', '0x54', '0x55']):
        bv_x = bv_cls(0x55)
        bv_y = bv_x
        bv_z = bv_x[:]
        bv_x.align(x)
        assert (hex(bv_x), hex(bv_y), hex(bv_z)) == (v, v, '0x55')

    for x,v in zip(range(7, -1, -1), ['0x5c', '0x5b', '0x5a', '0x59', '0x58', '0x57', '0x56', '0x55']):
        bv_x = bv_cls(0x55)
        bv_y = bv_x
        bv_z = bv_x[:]
        bv_x += x
        assert (hex(bv_x), hex(bv_y), hex(bv_z)) == (v, v, '0x55')

    assert [hex(bv_cls(x).xor_reduce()) for x in (0x55, 0x52, 0x1, 0x0, 0x1f)] == \
        ['0x0', '0x1', '0x1', '0x0', '0x1']

    assert [hex(bv_cls(x).or_reduce()) for x in (0x55, 0x52, 0x1, 0x0, 0x1f)] == \
        ['0x1', '0x1', '0x1', '0x0', '0x1']

    assert [hex(bv_cls(x).and_reduce()) for x in (0x55, 0x52, 0x1, 0x0, 0x1f)] == \
        ['0x0', '0x0', '0x1', '0x1', '0x1']

    assert [hex(bv_cls(x).and_reduce(5)) for x in (0x55, 0x52, 0x1, 0x0, 0x1f)] == \
        ['0x0', '0x0', '0x0', '0x0', '0x1']

    assert [hex(bv_cls(x).bit_count()) for x in (0x55, 0x52, 0x1, 0x0, 0x1f)] == \
        ['0x4', '0x3', '0x1', '0x0', '0x5']

    assert 'ab ' * bv_cls(3) == 'ab ab ab '

test_ops(BitVector[...])
test_ops(BitVector[None])
test_ops(BitVector[100], True)

try:
    apv = list(BitVector[...]._dp_all_possible_values())
except Exception as ex:
    print(ex)
    pass
else:
    assert False, str(apv)


class Top(cli.Test.Top):
    b: BitVector[...]

def the_test(top):
    print('testing static bit-vector', top._dp_state_types['b'])
    yield

    top.b = 0x57
    yield

    assert top.b == 0x57
    assert top.b + 1 == 0x58
    assert top.b & 0xf0 == 0x50
    assert top.b[4:8] == 0x5
    yield

    assert top.b == 0x57
    assert top.b[4:8] == 0x5
    assert top.b[0:4] == BitVector[...](0x7)
    assert top.b[0:4] + 2 == 0x9
    yield

    top.b[4:8] = 0x9
    yield

    assert top.b == 0x97
    assert top.b[4:8] == 0x9
    assert top.b[0:4] == 0x7
    yield

    top.b[4] = 0
    top.b[5] = 1
    yield

    assert top.b == 0xa7
    yield

    top.b.align(2)
    yield

    assert top.b == 0xa4
    yield

    top.b <<= 2
    yield

    assert top.b == 0x290, hex(top.b)
    yield

cli.Test(Top())(the_test)


print('negative testing for transient width-limited cases')

for x in range(-10, 10):
    with cli.TestException(0 <= x < 8, 'transient out of bounds'):
        a = BitVector[3](x)

a = BitVector[3](4)
for x in range(-10, 10):
    with cli.TestException(-4 <= x < 4, 'transient add out of bounds'):
        b = a + x

with cli.TestException(False, 'cannot negate'):
    b = -BitVector[3](4)

with cli.TestException(False, 'cannot negate'):
    b = -BitVector[3](1)

with cli.TestException(True, 'can invert'):
    b = print('8-bit inverted 4 is', ~BitVector[8](4))

a = BitVector[3](4)
for x in range(-10, 10):
    with cli.TestException(-4 <= x < 4, 'transient inplace add out of bounds'):
        b = a[:]
        b += x

a = BitVector[8](4)
for x in range(256):
    with cli.TestException(True, 'transient logic out of bounds'):
        b = a[:]
        b ^= x
        b = a[:]
        b &= x
        b = a[:]
        b |= x
        b = a & x
        b = a | x
        b = a ^ x

a = BitVector[8](4)
for x in range(3, 20):
    with cli.TestException(x < 10, 'transient setitem out of bounds'):
        b = a[:]
        b[x-3: x] = 2



class Top(cli.Test.Top):
    a: BitVector[8]

@cli.Test(Top())
def the_test(top):
    print('negative testing for static width-limited cases')
    yield

    with cli.TestException(True, 'set OK'):
        top.a = 255
    yield

    with cli.TestException(False, 'set too big'):
        top.a = 257
    yield

    with cli.TestException(True, 'add OK'):
        top.a = 10
        yield
        top.a += 34
        b = 500 + a
    yield

    with cli.TestException(False, 'add too big'):
        top.a = 100
        yield
        top.a += 170
    yield

    with cli.TestException(True, 'negate OK'):
        top.a = 0xb5
        yield
        b = ~top.a
        yield
        assert b == 0x4a
        yield
        top.a = 0x4a
        yield
        b = ~top.a
        yield
        assert b == 0xb5
    yield

    with cli.TestException(True, 'setitem OK'):
        top.a = 0
        yield
        top.a[3:7] = 0x9
        yield
        assert top.a == 0x48
        yield
        top.a[6:10] = 0x3
        yield
        assert top.a == 0xc8
    yield

    with cli.TestException(False, 'setitem too big'):
        top.a[6:10] = 0x7
    yield
