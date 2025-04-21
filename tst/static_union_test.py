'''
MIT Licence: Copyright (c) 2025 Baya Systems <https://bayasystems.com>

Purple Tests
======================

This file tests the StaticUnion class (Unions inside Model state)


FIXME
    initial values
'''

import enum
import cli
from purple import Record, Integer, Enumeration

top_enum = enum.Enum('top', 't0 t1 t2 t3')


print('set and read back leaf')

class TopLeaf(cli.Test.Top):
    a: Enumeration[top_enum] | Integer[10]

@cli.Test(TopLeaf())
def the_test(top):
    for v in (0, top_enum.t2, 5, 4, top_enum.t1, top_enum.t3, 7):
        top.a = v
        yield

        assert top.a == v
        yield


print('set and read back record')

class M0(Record):
    a: Integer[10]
    b: Integer[6]

class M1(Record):
    c: Integer[8]
    d: Integer[8]

class TopRec(cli.Test.Top):
    x: M0 | M1

@cli.Test(TopRec())
def the_test(top):
    for v in (
        M0(a = 1, b = 1),
        M1(c = 3, d = 3),
        M1(c = 2,),
    ):
        top.x = v
        yield

        assert top.x == v
        assert top.x is not v
        yield


print('set and read back mixed')

class TopMix(cli.Test.Top):
    x: M0 | M1 | Enumeration[top_enum] | Integer[30]

top = TopMix()

@cli.Test(top)
def the_test(top):
    for v in (
        M0(a = 1, b = 1),
        M1(c = 3, d = 3),
        M1(c = 2,),
        top_enum.t2,
        25,
        M1(c = 2, d = 1),
    ):
        top.x = v
        yield

        assert top.x == v
        yield


print('update')

@cli.Test(top)
def the_test(top):
    top.x = M1(c = 3, d = 4)
    yield

    top.x.update(c = 2)
    yield

    assert top.x == M1(c = 2, d = 4)


print('hierarchy')

class RecUn(Record):
    # record containing union
    w: M0 | M1
    x: Integer[3]

class RecRecUn(Record):
    # record containing record containing union
    y: RecUn
    z: Integer[3]

class TopHier(cli.Test.Top):
    a: RecRecUn
    b: M0 | RecUn

@cli.Test(TopHier())
def the_test(top):
    for v,a_not_b in (
        (M0(a = 1, b = 0), False),
        (RecRecUn(y = RecUn(w = M1(c = 2, d = 1), x = 1), z = 0), True),
        (RecUn(w = M0(a = 1, b = 0), x = 2), False),
        (RecRecUn(y = RecUn(w = M0(a = 2, b = 2), x = 0), z = 2), True),
    ):
        if a_not_b:
            top.a = v
        else:
            top.b = v
        yield

        if a_not_b:
            assert top.a == v
            v.y.x = 1 - v.y.x
            assert top.a != v
        else:
            assert top.b == v
            vv = M1(c = 1, d = 0)
            assert top.b != vv
        yield

    print()
    print('printing system state:')
    print(top._dp_hierarchical_str())

    print()
    print('printing system state including unselected:')
    print(top._dp_hierarchical_str(True))
