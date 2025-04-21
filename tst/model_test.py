'''
MIT Licence: Copyright (c) 2025 Baya Systems <https://bayasystems.com>

Purple Tests
======================

This file tests the Model class

    construct a hierarchy using class declarations
    instantiate a Model
    get and set leaf state
'''

from purple import (
    Model, Integer, Boolean, Enumeration, ReadUnDefined, UnDefined
)


class SubSub(Model):
    first: Boolean
    second: Integer[10]
    SS_Enum = Enumeration['subsub-enum', 'A B C']
    third: SS_Enum

class Sub(Model):
    first: SubSub
    second: SubSub
    S_Enum = Enumeration['sub-enum', 'W X Y']
    third: S_Enum

class Top(Model):
    a: SubSub
    b: Sub
    c: Sub
    d: Boolean
    rules: [run_test]

    def run_test(self):
        the_test()

top = Top()
the_rule = next(top.find_rule(component = top))


print('cannot read initial leaf state but can read hierarchical state')
try:
    z = top.d
except ReadUnDefined as exc:
    print(exc)
else:
    assert False

try:
    z = top.b.third
except ReadUnDefined:
    pass
else:
    assert False

try:
    z = top.b.second
except ReadUnDefined:
    raise


def the_test():
    print('setting all leaf state to something')
    for x in top.a, top.b.first, top.b.second, top.c.first, top.c.second:
        x.first = False
        x.second = 0
        x.third = SubSub.third.A
    for x in top.b, top.c:
        x.third = Sub.third.Y
    top.d = False
the_rule.invoke()

def the_test():
    print('checking all leaf state')
    for x in top.a, top.b.first, top.b.second, top.c.first, top.c.second:
        assert x.first is False
        assert x.second == 0
        assert x.third == SubSub.third.A
    for x in top.b, top.c:
        assert x.third == Sub.third.Y
    assert top.d is False
the_rule.invoke()

def the_test():
    print('modifying some leaf state')
    top.a.first = True
    top.b.first.second = 5
    top.b.second.third = SubSub.third.C
    top.c.first.first = True
    top.c.second.second = 6
    top.c.third = Sub.third.X
    top.d = True
the_rule.invoke()

def the_test():
    print('checking all leaf state again')
    for x in top.a, top.b.first, top.b.second, top.c.first, top.c.second:
        assert x.first is (True if x in (top.a, top.c.first) else False)
        assert x.second == (5 if x is top.b.first else (6 if x is top.c.second else 0))
        assert x.third == (SubSub.third.C if x is top.b.second else SubSub.third.A)
    for x in top.b, top.c:
        assert x.third == (Sub.third.X if x is top.c else Sub.third.Y)
    assert top.d is True
the_rule.invoke()

def the_test():
    print('set leaf to undef')
    top.a.second = UnDefined
the_rule.invoke()

def the_test():
    print('fail to read undef')
    try:
        z = top.a.second
    except ReadUnDefined:
        pass
    else:
        assert False, str(z)
the_rule.invoke()



print('simple inheritance testing')
# FIXME test type override
# test binding override
# test rule removal

class ThirdBase(Model):
    third_b: Integer[...] = 3
    rules: [r3]
    def r3(self): self.print('r3')

class SecondBase(ThirdBase):
    second_b: Integer[...] = 2

class FirstBase(SecondBase):
    third_b = 4
    first_b: Integer[...] = 1
    rules: [r1]
    def r1(self): self.print('r1')

class Top(FirstBase):
    top_b: Integer[...] = 0
    rules: [r0]
    def r0(self): self.print('r0')

top = ThirdBase()
assert top.third_b == 3
assert next(top.find_rule()).method_name == 'r3'

top = Top()
assert top.top_b == 0
assert top.first_b == 1
assert top.second_b == 2
assert set(r.method_name for r in top.find_rule()) == {'r0', 'r1', 'r3'}
assert top.third_b == 4



try:
    print('check detection of bad annotation')
    class Bad(Model):
        name_of_unimported: Tuple[Boolean]
except:
    pass
else:
    assert False
