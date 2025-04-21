'''
MIT Licence: Copyright (c) 2025 Baya Systems <https://bayasystems.com>

Purple Tests
======================

Array test

* transient
    * of-leaf
    * of-record
    * of-array
    * len() and "for x in anArray"
    * __init__ can take iterables (list, tuple, generator)
    * negative index
    * slices
    * concatenation
    * initial values can take iterables (list, tuple, generator) as well as a dict or an array transient
    * array-index leaf state

* static instantiation of array-of-record/leaf
'''

from purple import Record, Integer, ArrayIndex, FromArrayIndex
import cli
import random


OfLeafStandalone = 4 * Integer[5]

class OfLeaf(Record):
    x: 4 * Integer[5]

class SimpleRecord(Record):
    y: Integer[5]
    z: Integer[3]

OfRecordStandalone = 5 * SimpleRecord

class OfRecord(Record):
    x: 5 * SimpleRecord

OfArrayStandalone = 6 * OfLeafStandalone

class OfArray(Record):
    x: 6 * OfLeafStandalone


print('of-leaf-standalone')
for _ in range(10):
    r = OfLeafStandalone()
    last = None
    for __ in range(10):
        i = random.randrange(-4, 4)
        v = random.randrange(5)
        r[i] = v
        if last is not None:
            same_change = last[0] == i or last[0] + 4 == i or last[0] == i + 4
            assert r[last[0]] == (v if same_change else last[1])
        last = (i, v)

assert len(r) == 4
assert len(list(OfLeafStandalone._dp_all_possible_values())) == 5**4


print('of-leaf')
for _ in range(10):
    r = OfLeaf()
    last = None
    for __ in range(10):
        i = random.randrange(4)
        v = random.randrange(5)
        r.x[i] = v
        assert last is None or (r.x[last[0]] == (last[1] if last[0] != i else v))
        last = (i, v)

assert len(r.x) == 4
assert len(list(OfLeaf._dp_all_possible_values())) == 5**4


print('of-record-standalone')
for _ in range(10):
    r = OfRecordStandalone()
    last = None
    for __ in range(10):
        i = random.randrange(5)
        v = SimpleRecord(y = random.randrange(5), z = random.randrange(3))
        r[i] = v.copy()
        assert last is None or (r[last[0]] == (last[1] if last[0] != i else v))
        last = (i, v)

assert len(r) == 5
if not cli.args.quick:
    assert len(list(OfRecordStandalone._dp_all_possible_values())) == (5 * 3)**5


print('of-record')
for _ in range(10):
    r = OfRecord()
    last = None
    for __ in range(10):
        i = random.randrange(5)
        v = SimpleRecord(y = random.randrange(5), z = random.randrange(3))
        r.x[i] = v.copy()
        assert last is None or (r.x[last[0]] == (last[1] if last[0] != i else v))
        last = (i, v)

assert len(r.x) == 5
if not cli.args.quick:
    assert len(list(OfRecord._dp_all_possible_values())) == (5 * 3)**5


print('of-array-standalone')
rr = random.randrange
for _ in range(10):
    r = OfArrayStandalone()
    last = None
    for t in range(10):
        i = random.randrange(6)
        tt = t % 3
        if tt == 0:
            v = OfLeafStandalone(_0 = rr(5), _1 = rr(5), _2 = rr(5), _3 = rr(5))
        elif tt == 1:
            v = OfLeafStandalone(rr(5) for ___ in range(4))
        else:
            v = OfLeafStandalone([rr(5) for ___ in range(4)])
        r[i] = v.deep_copy()
        assert last is None or (r[last[0]] == (last[1] if last[0] != i else v))
        last = (i, v)

assert len(r) == 6
assert all(len(x) == 4 for x in r)


print('of-array')
for _ in range(10):
    r = OfArray()
    last = None
    for __ in range(10):
        i = random.randrange(-6, 6)
        v = OfLeafStandalone(_0 = rr(5), _1 = rr(5), _2 = rr(5), _3 = rr(5))
        r.x[i] = v.deep_copy()
        if last is not None:
            same_change = last[0] == i or last[0] + 6 == i or last[0] == i + 6
            assert r.x[last[0]] == (v if same_change else last[1])
        last = (i, v)

assert len(r.x) == 6
assert all(len(x) == 4 for x in r.x)


print('slicing')
len5 = OfRecordStandalone(dict(y = rr(5), z = rr(3)) for _ in range(5))
for len2,a,b in (
    (len5[:2], 0, 1),
    (len5[3:], 3, 4),
    (len5[1:3], 1, 2),
    (len5[:-3], 0, 1),
    (len5[-3:-1], 2, 3),
    (len5[-4::-1], 1, 0),
    (len5[:-3:-1], 4, 3),
    (len5[::-3], 4, 1),
):
    assert len(len2) == 2
    assert tuple(len2) == (len5[a], len5[b])


print('concatenation')
len5b = len5[1::2] + len5[::2]
assert len5b == OfRecordStandalone((len5[1], len5[3], len5[0], len5[2], len5[4]))

len6 = len5[1:4] + len5[::2]
assert len6 == (6 * SimpleRecord)((len5[1], len5[2], len5[3], len5[0], len5[2], len5[4]))


print('initial-values')
for iv in (
    dict(_0 = 4, _1 = 3, _2 = 2, _3 = 1),
    (4 * Integer[5])((4,3,2,1)),
    (4,3,2,1),
    [4,3,2,1],
    range(4, 0, -1),
    (4 - x for x in range(4)),
):
    class OfLeaf(Record):
        x: 4 * Integer[5] = iv

    assert tuple(OfLeaf().x) == (4, 3, 2, 1)


print('initial-values-hierarchical')
class OfLeaf(Record):
    x: 4 * Integer[5] = (1,2,1,2)

class OfArrayDD(Record):
    x: 3 * OfLeaf = dict(
        _2 = dict(
            x = dict(_1 = 4)
        )
    )

a = OfArrayDD()
assert a.x[2].x[1] == 4
assert a.x[2].x[0] == 1
assert a.x[1].x[1] == 2


class OfArrayTD(Record):
    x: 3 * OfLeaf = (
        dict(x = dict()),
        dict(x = dict(_3 = 4)),
        dict(x = dict()),
    )

a = OfArrayTD()
assert a.x[1].x[3] == 4
assert a.x[2].x[3] == 2
assert a.x[1].x[1] == 2


class OfArrayDT(Record):
    x: 3 * OfLeaf = dict(_1 = dict(x = (3,4,3,4)))

a = OfArrayDT()
assert a.x[1].x[3] == 4
assert a.x[2].x[3] == 2
assert a.x[1].x[0] == 3


class OfArrayTT(Record):
    x: 3 * OfLeaf = (
        dict(x = (3,4,3,4)),
        dict(x = (1,2,1,2)),
        dict(x = (1,2,1,2)),
    )

a = OfArrayTT()
assert a.x[0].x[3] == 4
assert a.x[2].x[3] == 2
assert a.x[1].x[0] == 1


class OfArrayTR(Record):
    x: 3 * OfLeaf = (
        dict(x = (4 * Integer[5])((3,4,3,4))),
        dict(x = (1,2,1,2)),
        dict(x = (4 * Integer[5])((1,2,1,2))),
    )

a = OfArrayTR()
assert a.x[0].x[3] == 4
assert a.x[2].x[3] == 2
assert a.x[1].x[0] == 1


print('static-array-of-record/leaf')

class Top(cli.Test.Top):
    of_leaf_standalone: OfLeafStandalone
    of_leaf: OfLeaf
    of_record_standalone: OfRecordStandalone
    of_record: OfRecord
    of_array_standalone: OfArrayStandalone
    of_array_dd: OfArrayDD
    of_array_td: OfArrayTD
    of_array_dt: OfArrayDT
    of_array_tt: OfArrayTT
    of_array_tr: OfArrayTR

@cli.Test(Top())
def run(top):
    print('up and running')
    yield

    top.of_leaf_standalone[2] = 4
    top.of_leaf.x[1] = 1
    top.of_record_standalone[0].z = 2
    top.of_record.x[3] = SimpleRecord(y = 4, z = 0)
    yield

    assert top.of_leaf_standalone[2] == 4
    assert top.of_leaf.x[1] == 1
    assert top.of_record_standalone[0].z == 2
    assert top.of_record.x[3] == SimpleRecord(y = 4, z = 0)
    yield

    top.of_array_standalone[5][1] = 2
    top.of_array_standalone[4][1] = 3
    top.of_array_standalone[5][2] = 4
    yield

    assert top.of_array_standalone[5][1] == 2
    assert top.of_array_standalone[4][1] == 3
    assert top.of_array_standalone[5][2] == 4
    yield

    for my_array in (
        top.of_array_dd,
        top.of_array_td,
        top.of_array_dt,
        top.of_array_tt,
        top.of_array_tr,
    ):
        i0 = random.randrange(3)
        i1 = random.randrange(4)
        v = random.randrange(5)
        my_array.x[i0].x[i1] = v
        yield

        assert my_array.x[i0].x[i1] == v
        yield


print('static-array-of-record/leaf-with-initialisation')
print('FIXME not yet implemented')


print('array-index')

class WithIndex(Record):
    a: Integer[10]
    b: ArrayIndex

StandaloneWithIndex = 10 * WithIndex

ac = StandaloneWithIndex()
for i in range(10):
    assert ac[i].b == i

class RecordWithIndex(Record):
    a: 5 * WithIndex = dict(_2 = dict(a = 7))
    b: Integer[6] = 5

rc = RecordWithIndex()
for i in range(5):
    assert rc.b == 5
    assert rc.a[i].b == i
assert rc.a[2].a == 7


class WithIndex2(Record):
    a: Integer[10]
    b: FromArrayIndex[lambda x, y: y + x * 100]

class RecordWithIndex2(Record):
    a: 5 * WithIndex2
    b: ArrayIndex

class Nest(Record):
   a: 3 * RecordWithIndex2

nn = Nest()
for i in range(3):
    assert nn.a[i].b == i
    for j in range(5):
        assert nn.a[i].a[j].b == j + 100 * i
