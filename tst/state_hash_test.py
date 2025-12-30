'''
MIT Licence: Copyright (c) 2025 Baya Systems <https://bayasystems.com>

Purple Tests
======================

This file tests that model state hash works for some state update options

- same state requires same hash value
- different state may have different hash value but implementation should make this
  extemely unlikely so this test disallows it

- set leaf at different levels of hierarchy, to value or to UnDefined
- set record to transient
- set union to leaf
- set union to record

- enum
- int
- bool
- modulo
- tuple
'''

import enum
import cli
from purple import (
    Model, Record,AtomicRuleSimulator, UnDefined, ReadUnDefined, UnSelected,
    Integer, Enumeration, Tuple, Boolean, ModuloInteger,
)


print('basic test with 3 ints')

class ThreeInts(Model):
    a: Integer[3]
    b: Integer[3]
    c: Integer[3]
    rules: [change_a, change_b, change_c]

    def change_a(self, v: Integer[4]):
        self.a = v if v < 3 else UnDefined
    def change_b(self, v: Integer[4]):
        self.b = v if v < 3 else UnDefined
    def change_c(self, v: Integer[4]):
        self.c = v if v < 3 else UnDefined


class Sim(AtomicRuleSimulator):
    show_print = False
    leaf_names = 'a b c'.split()

    def __init__(self, s):
        super().__init__(s)
        self.states_witnessed = dict()
        self.hashes_witnessed = dict()
        self.num_hash_matches = 0
        self.num_state_matches = 0

    def rd(self, name):
        v = self.system
        try:
            for n in name.split('.'):
                v = getattr(v, n)
        except ReadUnDefined:
            v = UnDefined
        except AttributeError:
            # special case for elements within union of records
            v = UnSelected
        if isinstance(v, Record):
            # special case for a mixed record/leaf union
            v = UnSelected
        return v

    def state_as_tuple(self):
        return tuple(self.rd(n) for n in self.leaf_names)

    def invoke_one_rule(self, show_print, print_header, num_guards):
        super().invoke_one_rule(show_print, print_header, num_guards)
        assert not self.deadlocked

        h = self.system._dp_model_state_hash
        s = self.state_as_tuple()
        if self.show_print:
            print(self.num_invocations, h, s)

        # check that if the state was seen before, the hash was the same
        prev_h = self.hashes_witnessed.get(s, None)
        if prev_h is None:
            self.hashes_witnessed[s] = h
        else:
            assert h == prev_h, f'hash mismatch {h} != {prev_h}'
            self.num_state_matches += 1

        # check that if the hash was seen before, the state was the same
        # this can fail in theory but hash desig should make it extremely unlikely
        prev_s = self.states_witnessed.get(h, None)
        if prev_s is None:
            self.states_witnessed[h] = s
        else:
            assert s == prev_s, f'state mismatch {s} != {prev_s}'
            self.num_hash_matches += 1


sim = Sim(ThreeInts())
sim.run(100 if cli.args.quick else 10000)
print('sim complete:', sim.num_invocations, sim.num_hash_matches, sim.num_state_matches)


print('hierarchical integer system')

class TopInts(Model):
    ti_0: ThreeInts
    ti_1: ThreeInts
    local: Integer[3] = 1
    modulo: ModuloInteger[3] = 2

    rules: [change_local, change_m]

    def change_local(self, v: Integer[3]):
        self.local = v
    def change_m(self, v: Integer[4]):
        self.modulo = v if v < 3 else UnDefined

class SimH(Sim):
    leaf_names = 'ti_0.a ti_0.b ti_0.c ti_1.a ti_1.b ti_1.c local modulo'.split()

sim = SimH(TopInts())
sim.run(1000 if cli.args.quick else 10000)
print('sim complete:', sim.num_invocations, sim.num_hash_matches, sim.num_state_matches)


print('richer system with enums, tuples and records')

MyEnum = Enumeration[enum.Enum('E', 'A, B, C')]

class MyRecord(Record):
    e: MyEnum
    b: Boolean

class Top(TopInts):
    r: MyRecord
    t: Tuple[MyRecord]

    rules: [change_e, change_b, change_r, append_t, pop_t]

    def change_e(self, v: MyEnum):
        self.r.e = v
    def change_b(self, v: Boolean):
        self.r.b = v
    def change_r(self, v: MyRecord):
        self.r = v
    def append_t(self, v: MyRecord):
        self.t.append(v)
    def pop_t(self, v: Integer[12]):
        # parameter is a cheap trick to make pops more likely than appends
        if self.t:
            self.t.pop(0)

class SimT(Sim):
    show_print = False
    leaf_names = '''
        ti_0.a ti_0.b ti_0.c
        ti_1.a ti_1.b ti_1.c
        local modulo
        r.e r.b
        t
    '''.split()

sim = SimT(Top())
sim.run(1000 if cli.args.quick else 100000)
print('sim complete:', sim.num_invocations, sim.num_hash_matches, sim.num_state_matches)


print('system with unions')

class MyOtherRecord(Record):
    z: MyEnum
    y: Boolean
    w: Boolean

class TopE(Model):
    g: (MyRecord | MyOtherRecord | MyEnum) = MyRecord(b = True)
    gtype: Integer[3] = 0
    f: MyEnum | Boolean

    rules: [
        change_e, change_b,
        change_z, change_y, change_w,
        change_f, change_g0, change_g1, change_g2,
    ]

    def change_e(self, v: MyEnum):
        self.guard(self.gtype == 0)
        self.g.e = v
    def change_b(self, v: Boolean):
        self.guard(self.gtype == 0)
        self.g.b = v
    def change_z(self, v: MyEnum):
        self.guard(self.gtype == 1)
        self.g.z = v
    def change_y(self, v: Boolean):
        self.guard(self.gtype == 1)
        self.g.y = v
    def change_w(self, v: Boolean):
        self.guard(self.gtype == 1)
        self.g.w = v
    def change_f(self, v: (MyEnum | Boolean)):
        self.f = v
    def change_g0(self, v: MyRecord):
        self.g = v
        self.gtype = 0
    def change_g1(self, v: MyOtherRecord):
        self.g = v
        self.gtype = 1
    def change_g2(self, v: MyEnum):
        self.g = v
        self.gtype = 2


class SimE(Sim):
    show_print = False
    leaf_names = 'g g.e g.b g.z g.y g.w gtype f'.split()

sim = SimE(TopE())
sim.run(1000 if cli.args.quick else 10000)
print('sim complete:', sim.num_invocations, sim.num_hash_matches, sim.num_state_matches)
