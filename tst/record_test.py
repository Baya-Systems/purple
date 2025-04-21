'''
MIT Licence: Copyright (c) 2025 Baya Systems <https://bayasystems.com>

Purple Tests
======================

This file tests the Record class (transient)

multiple levels of hierarchy (record-in-record)
    create record objects from full dicts
    create record objects from partial dicts
    create from other record
    create from initial-value (leaf or sub-record)
    get and set leaves
    get and set sub-record state at different hierarchical levels
    set leaf to Undef and cannot read it
    set sub-record to Undef and cannot read its leaves but can read it?
    test for equality (with/without undef?)
    iterate through all possible values
'''

from purple import (
    Record, Integer, Boolean, Enumeration, ReadUnDefined, UnDefined
)

import enum
import random


class SubSub(Record):
    first: Boolean
    second: Integer[10] = 3
    third: Enumeration['subsub-enum', 'A B C']

class Sub(Record):
    first: SubSub
    second: SubSub
    S_Enum = enum.Enum('sub-enum', 'W X Y')
    third: Enumeration [S_Enum] = S_Enum.Y

class Top(Record):
    a: SubSub
    b: Sub
    c: Sub
    d: Boolean
    e: Integer[20] = 7


print('cannot read undefined initial leaf values but can read hierarchical state')
top = Top()

try:
    z = top.d
except ReadUnDefined:
    pass
else:
    assert False

try:
    z = top.a.first
except ReadUnDefined:
    pass
else:
    assert False

try:
    z = top.b.second
except ReadUnDefined:
    raise

assert top.e == 7
assert top.a.second == 3
assert top.c.third == Sub.S_Enum.Y
assert top.b.second.second == 3


print('setting all leaf state to something else')
for x in top.a, top.b.first, top.b.second, top.c.first, top.c.second:
    x.first = False
    x.second = 0
    x.third = SubSub.third.A
for x in top.b, top.c:
    x.third = Sub.third.Y
top.d = False

print('checking all leaf state')
for x in top.a, top.b.first, top.b.second, top.c.first, top.c.second:
    assert x.first is False
    assert x.second == 0
    assert x.third == SubSub.third.A
for x in top.b, top.c:
    assert x.third == Sub.third.Y
assert top.d is False

print('modifying some leaf state')
top.a.first = True
top.b.first.second = 5
top.b.second.third = SubSub.third.C
top.c.first.first = True
top.c.second.second = 6
top.c.third = Sub.third.X
top.d = True

print('checking all leaf state again')
for x in top.a, top.b.first, top.b.second, top.c.first, top.c.second:
    assert x.first is (True if x in (top.a, top.c.first) else False)
    assert x.second == (5 if x is top.b.first else (6 if x is top.c.second else 0))
    assert x.third == (SubSub.third.C if x is top.b.second else SubSub.third.A)
for x in top.b, top.c:
    assert x.third == (Sub.third.X if x is top.c else Sub.third.Y)
assert top.d is True

print('set leaf and hierarchical state to undef')
top.a.second = UnDefined
top.b = UnDefined

print('fail to read undef')
try:
    z = top.a.second
except ReadUnDefined:
    pass
else:
    assert False

try:
    z = top.b.second
except ReadUnDefined:
    raise

try:
    z = top.b.third
except ReadUnDefined:
    pass
else:
    assert False


print('creating transient Record from dict and setting state to it')
my_subsub = SubSub(first = False, second = 8, third = SubSub.third.B)
top.b.second = my_subsub
top.a = SubSub(first = True, second = 9, third = SubSub.third.C)
my_sub = Sub(first = SubSub(), third = Sub.third.W)
top.c = my_sub

print('checking')
assert top.b.second.first is False
assert top.b.second.second == 8
assert top.b.second.third == SubSub.third.B
assert top.a.first is True
assert top.a.second == 9
assert top.a.third == SubSub.third.C
assert top.c.third == Sub.third.W

print('checking undefs')
for cc in top.c.first, top.c.second:
    try:
        z = cc.first
    except ReadUnDefined:
        pass
    else:
        assert False

    assert cc.second == 3

    try:
        z = cc.third
    except ReadUnDefined:
        pass
    else:
        assert False

print('creating transient Record from Record and setting state to it')
my_subsub = SubSub(first = UnDefined, second = 4, third = SubSub.third.A)
my_sub = Sub(first = my_subsub, third = Sub.third.W)
assert my_sub.third == Sub.third.W
assert my_sub.first.second == 4
top.b = my_sub

print('checking')
assert top.b.first.second == 4
assert top.b.first.third == SubSub.third.A
assert top.b.third == Sub.third.W

try:
    z = top.b.second.first
except ReadUnDefined:
    pass
else:
    assert False

try:
    z = top.b.first.first
except ReadUnDefined:
    pass
else:
    assert False

print('creating transient record with some defaults')
tt = Top(e = 5)
assert tt.e == 5
assert tt.a.second == 3

tt = Top(
    b = Sub(third = Sub.third.W, first = SubSub(first = False)),
    c = Sub(second = SubSub(first = True, second = 1)),
)
assert tt.e == 7
assert tt.b.third is Sub.third.W
assert tt.b.first.first is False
assert tt.b.first.second == 3
assert tt.c.third is Sub.third.Y
assert tt.c.second.first is True
assert tt.c.second.second == 1

print('calling update')
tt.update(e = 6)
assert tt.e == 6
tt.update(e = 5, b = Sub(third = Sub.third.X, first = SubSub(first = True)))
assert tt.e == 5
assert tt.b.first.first
assert tt.b.third is Sub.third.X

print('hierarchical defaults')
class NewTop(Top):
    a: SubSub = dict(second = 9, third = SubSub.third.C)

nt = NewTop()
assert nt.e == 7
assert nt.a.second == 9
assert nt.a.third == SubSub.third.C
assert nt.b.third == Sub.third.Y


print('equality test')
my_subsub = SubSub(first = UnDefined, second = 4, third = SubSub.third.A)
my_sub = Sub(first = my_subsub, third = Sub.third.W)
assert top.b == my_sub
assert top.b.first == my_subsub
my_subsub = SubSub(first = UnDefined, second = 2, third = SubSub.third.A)
my_sub = Sub(first = my_subsub, third = Sub.third.W)
assert top.b != my_sub


print('shallow copy')
top.c.third = Sub.third.W
c_copy = top.c.copy()
assert c_copy == top.c
c_copy.third = Sub.third.X  # first-level leaf state
assert c_copy != top.c

top.c.third = Sub.third.W
top_copy = top.copy()
assert top_copy == top
top_copy.c.third = Sub.third.Y  # second-level leaf state changes in both
assert top_copy == top


print('deep copy')
top.c.third = Sub.third.W
c_copy = top.c.deep_copy()
assert c_copy == top.c
c_copy.third = Sub.third.X  # first-level leaf state
assert c_copy != top.c

top.c.third = Sub.third.W
top_copy = top.deep_copy()
assert top_copy == top
top_copy.c.third = Sub.third.Y  # second-level leaf state changes in both
assert top_copy != top


class EmptyRecord(Record):
    pass

class OneLeafRecord(Record):
    a: Boolean

print('iteration over all possible values')
d = list(EmptyRecord._dp_all_possible_values())
assert(len(d)) == 1
d = list(OneLeafRecord._dp_all_possible_values())
assert(len(d)) == 2
assert d[0].a in (True, False)
assert d[1].a in (True, False)
assert d[0].a != d[1].a

dss = list(SubSub._dp_all_possible_values())
dsslen = 2 * 10 * 3
for x in range(10):
    data = random.choice(dss)
    top.a = data
    assert top.a.first == data.first
    assert top.a.second == data.second
    assert top.a.third == data.third

assert(len(dss)) == dsslen
ds = list(Sub._dp_all_possible_values())
assert(len(ds)) == dsslen * dsslen * 3
for x in range(10):
    data = random.choice(ds)
    top.b = data
    assert top.b.first == data.first
    assert top.b.second.third == data.second.third
