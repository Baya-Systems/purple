'''
MIT Licence: Copyright (c) 2025 Baya Systems <https://bayasystems.com>

Purple Tests
======================

This file tests the Union class as transient (Record) objects

Leaf OR Leaf
Record containing (Leaf OR Leaf)
Record OR Record
Union OR Record
Record containing (Record OR Record)
Leaf OR Record
Record OR Leaf
Leaf OR Leaf OR Record OR Record
Record containing (Leaf OR Record)
Record containing (Record OR (Record containing (Record OR Record)))

in development
    ? are the last ones enough ?

to implement
    deep-copy (of union inside record)
    (Record containing Union) OR Something
    Something OR (Record containing Union)

Can I instantiate a Union class as a transient eg (MsgA | MsgB)(my_msg_b)
This should be OK, giving either an instance of MsgA or of MsgB depending on the copy-from
    and since it is shallow, this means just returning the copy_from

If I update() a Record class with a dict, same applies.

Can I derive subclasses from a Union?
What would this mean?
    object methods are useless because objects are never created
        but interesting to create a base class for eg a bunch of message types and create a union class from them
        worth testing, probably not in this file
    class methods could be added but not sure it is useful
    no state can be added
'''

import random
import enum
from purple import (
    Record, Integer, Boolean, Enumeration, ReadUnDefined, UnDefined, Union
)
import cli


# Leaf OR Leaf
my_enum = enum.Enum('my_enum', 'x y z')
LeafUnion = Integer[10] | Enumeration[my_enum]

assert issubclass(LeafUnion, Union)

apv_leaf = list(LeafUnion._dp_all_possible_values())
assert len(apv_leaf) == 10 + 3
assert all(x in apv_leaf for x in range(10))
assert all(x in apv_leaf for x in my_enum)

for value,allowed in ((5, True), (my_enum.y, True), (100, False)):
    try:
        t = LeafUnion(value)
    except:
        assert not allowed, f'LeafUnion {allowed} cast from {value}'
    else:
        assert allowed and t == value, f'LeafUnion {allowed} cast from {value} to {t}'


# Record containing (Leaf OR Leaf)
class Simple(Record):
    a: LeafUnion
    c: Boolean

apv_simple = list(Simple._dp_all_possible_values())
assert len(apv_simple) == (10 + 3) * 2

for values,allowed in (
    (dict(c = False), True),
    (dict(a = 5), True),
    (dict(a = 50), False),
    (dict(a = 7, c = False), True),
):
    try:
        t = Simple(**values)
    except:
        assert not allowed, f'Simple {allowed} update from {values}'
        continue
    else:
        assert allowed, f'Simple {allowed} update from {values} to {t}'
        assert ('a' not in values) or (t.a == values['a'])
        assert ('c' not in values) or (t.c == values['c'])


# Record containing (Leaf OR Leaf) with initial value
class SimpleInit(Record):
    a: LeafUnion
    b: LeafUnion = my_enum.z
    c: Boolean

for values,allowed in (
    (dict(a = 5), True),
    (dict(b = 5), True),
    (dict(a = 0, b = 5, c = True), True),
    (dict(a = 1, b = 3, c = False), True),
    (dict(a = -1, b = 3, c = False), False),
    (dict(a = my_enum.x, c = False), True),
):
    try:
        t = SimpleInit(**values)
    except:
        assert not allowed, f'SimpleInit {allowed} update from {values}'
        continue
    else:
        assert allowed, f'SimpleInit {allowed} update from {values} to {t}'
        assert ('a' not in values) or (t.a == values['a'])
        assert t.b == values.get('b', my_enum.z)
        assert ('c' not in values) or (t.c == values['c'])

    v = random.choice(apv_leaf)
    t.a = v
    assert t.a == v

    v = random.choice(apv_leaf)
    t.b = v
    assert t.b == v

    try:
        t.a = -1
    except:
        pass
    else:
        assert False

    try:
        t.b = -1
    except:
        pass
    else:
        assert False

    v = random.choice((0,1))
    t.c = v
    assert t.c == v


# (Record OR Record) OR Record
class MsgA(Record):
    h: Integer[256]

class MsgB(Record):
    h: Integer[8]
    j: Integer[8]

class MsgC(Record):
    a: Boolean
    b: Boolean
    c: Enumeration[my_enum]
    d: Integer[16]

GenericMsg = MsgA | MsgB | MsgC

num_msg_c = 2 * 2 * 3 * 16
num_generic_msg = 256 + 8 * 8 + num_msg_c
assert sum(1 for x in GenericMsg._dp_all_possible_values()) == num_generic_msg

for values,expected in (
    (dict(a = True), MsgC),
    (dict(a = True, b = False, c = my_enum.z), MsgC),
    (dict(h = 5), MsgA),
    (dict(h = -5), None),
    (dict(j = 5), MsgB),
    (dict(h = 7, j = 5), MsgB),
    (dict(h = 8, j = 5), None),
    (dict(), MsgA),
):
    try:
        t = GenericMsg(**values)
    except:
        assert expected is None, f'GenericMsg {expected} update from {values}'
        continue
    else:
        assert expected is type(t), f'GenericMsg {expected} update from {values} to {t}'

    # now we have a normal transient Record object so no need to test its behaviour here, just initial value

    if expected is MsgA:
        assert 'h' not in values or t.h == values['h']

    elif expected is MsgB:
        assert 'h' not in values or t.h == values['h']
        assert t.j == values['j']

    elif expected is MsgC:
        assert 'a' not in values or t.a == values['a']
        assert 'b' not in values or t.b == values['b']
        assert 'c' not in values or t.c == values['c']
        assert 'd' not in values or t.d == values['d']


# Record containing (Record OR Record)
class Tsprt(Record):
    m1: MsgC | MsgA | MsgB
    m2: GenericMsg = dict(h = 5, j = 7)
    n: Integer[5]

if not cli.args.quick:
    assert sum(1 for x in Tsprt._dp_all_possible_values()) == num_generic_msg * num_generic_msg * 5

for values,tm1,tm2 in (
    (dict(), MsgC, MsgB),
    (dict(m1 = MsgA(h = 5)), MsgA, MsgB),
    (dict(m2 = MsgA(h = 5), m1 = MsgA(h = 6)), MsgA, MsgA),
    (dict(m2 = MsgA(h = 5), n = 2, m1 = MsgA(h = 6)), MsgA, MsgA),
):
    try:
        t = Tsprt(**values)
    except:
        assert tm1 is None, f'Tsprt {m1,m2} update from {values}'
        continue
    else:
        assert tm1 is type(t.m1), f'Tsprt {m1} update from {values} to {t}'
        assert tm2 is type(t.m2), f'Tsprt {m2} update from {values} to {t}'

    for val in (
        MsgA(h = 3),
        MsgB(h = 2, j = 7),
        MsgC(a = False, b = True, c = my_enum.y, d = 10),
        MsgC(d = 10),
    ):
        t.m1 = val.copy()
        assert t.m1 is not val
        assert t.m1 == val
        t.m2 = t.m1.copy()
        assert t.m2 is not val
        assert t.m2 == val

    t.m1 = MsgB(j = 7)
    try:
        assert t.m1.h is UnDefined
    except ReadUnDefined:
        pass
    else:
        assert False

    t.m2 = UnDefined
    t.m1 = t.m2
    for m in t.m1,t.m2:
        assert type(m) is MsgA
        try:
            assert m.h is UnDefined
        except ReadUnDefined:
            pass
        else:
            assert False

    t.m1 = UnDefined
    t.m2 = t.m1
    for m in t.m1,t.m2:
        assert type(m) is MsgC
        try:
            assert m.b is UnDefined
        except ReadUnDefined:
            pass
        else:
            assert False


# Leaf OR Record
# Record OR Leaf
MixedUnion = Integer[7] | MsgC
MixedUnion2 = MsgC | Integer[7]

assert sum(1 for x in MixedUnion._dp_all_possible_values()) == 7 + num_msg_c
assert sum(1 for x in MixedUnion2._dp_all_possible_values()) == 7 + num_msg_c

assert MixedUnion() is UnDefined
assert type(MixedUnion2()) is MsgC

for UT in MixedUnion, MixedUnion2:
    for values,expected in (
        (dict(a = True, b = False, c = my_enum.z), MsgC),
        (dict(a = True, b = False), MsgC),
        (6, int),
        (dict(q = 57), None),
        (3, int),
        (90, None),
    ):
        try:
            if isinstance(values, dict):
                t = UT(**values)
            else:
                t = UT(values)
        except:
            assert expected is None, f'{UT} {expected} update from {values}'
            continue
        else:
            assert expected is type(t), f'{UT} {expected} update from {values} to {t}'

        # now we have a normal transient Record object or a plain Python int
        assert type(t) is MsgC or t == values
        assert type(t) is int or 'c' not in values or t.c == values['c']


# Record OR Leaf OR Leaf OR Record
MixedUnion3 = MsgC | Enumeration[my_enum] | Integer[20] | MsgB

assert sum(1 for x in MixedUnion3._dp_all_possible_values()) == num_msg_c + 3 + 20 + 8 * 8
assert type(MixedUnion3()) is MsgC

for values,expected in (
    (my_enum.z, my_enum),
    (dict(h = 0, j = 0), MsgB),
    (6, int),
    (dict(q = 57), None),
    (3, int),
    (90, None),
):
    try:
        if isinstance(values, dict):
            t = MixedUnion3(**values)
        else:
            t = MixedUnion3(values)
    except:
        assert expected is None, f'MixedUnion3 {expected} update from {values}'
        continue
    else:
        assert expected is type(t), f'MixedUnion3 {expected} update from {values} to {t}'

    # now we have a normal transient Record object or a plain Python int
    if type(t) not in (MsgC, MsgB):
        assert t == values
    elif type(t) is MsgC:
        assert 'c' not in values or t.c == values['c']
    elif type(t) is MsgB:
        assert 'j' not in values or t.j == values['j']


# Record containing (Leaf OR Record)
# Record containing (Record OR (Record containing (Record OR Record)))
class Tsprt2(Record):
    z1: MsgB | MsgC
    k: Enumeration[my_enum] = my_enum.z

class Hierarchical(Record):
    tsprt: Tsprt            = dict(m1 = dict(), m2 = dict(h = 7), n = 0)
    mixed: MixedUnion       = dict(a = True)
    cmplx: (Tsprt2 | Tsprt) = dict(z1 = dict(j = 3), k = my_enum.x)
    x: Integer[5]           = 0

t = Hierarchical()

assert type(t.tsprt.m1) is MsgC
assert type(t.tsprt.m2) is MsgB and t.tsprt.m2.h == 7 and t.tsprt.m2.j == 7
assert t.tsprt.n == 0

assert type(t.mixed) is MsgC
assert t.mixed.a is True

assert type(t.cmplx) is Tsprt2
assert type(t.cmplx.z1) is MsgB
assert t.cmplx.k == my_enum.x
assert t.cmplx.z1.j == 3

assert t.x == 0
