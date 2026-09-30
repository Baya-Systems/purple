'''
MIT Licence: Copyright (c) 2025 Baya Systems <https://bayasystems.com>

Purple Tests
======================

Tuple test for multiple changes
    in one rule
    in 2 or more concurrent (clocked) rules

Tests in place
    with/without initial value
    multiple changes per invocation
        set-entire-tuple
        append
        other: pop/replace/insert
        multiple append in same rule, other ops between
    negative test can't append/other/set with wrong element type
    2 processes allowed to "other" in the same cycle
        one of them can append
    negative test can't both set
    negative test can't both append
    negative test can't "other" when the other sets
    negative test cannot both "other" at same index
    3 processes allowed to "other" in the same cycle
        one of them can append

Tests to code
    FIXME in-place modifications to a Tuple that is part of a transient Record
        will need to replace the entire Tuple immediately
        putting a Tuple in a Record is supported, so this should work
        but I expect it will not
'''

import enum
import random

from purple import (
    Clock,
    ClockedSimulator,
    Tuple,
    Integer,
    Enumeration,
    Model,
    Record,
    NonDeterministicLeafChange,
)

import cli


Element = Integer[...]

class OneRule(cli.Test.Top):
    c: Tuple[Element]
    d: Tuple[Element] = (1, 2, 3)

@cli.Test(OneRule())
def test_one_rule(top):
    print('Single (atomic) rule')
    assert top.d == (1, 2, 3)
    assert top.c == ()
    top.c = (3, 2, 1)
    yield

    assert top.c == (3, 2, 1)
    top.d.append(4)
    yield

    assert top.d == (1, 2, 3, 4)
    top.c = (5, 6)
    top.c.append(7)
    yield

    assert top.c == (5, 6, 7)
    assert top.c.pop(1) == 6
    yield

    assert top.c == (5, 7)
    top.c.append(2)
    top.c = (9, 8)
    yield

    assert top.c == (9, 8)
    top.c.pop(0)
    top.c = (7, 6)
    top.c.pop(1)
    yield

    assert top.c == (7,)
    top.c = (11, 12)
    top.c.append(3)
    top.c = (1, 2)
    yield

    assert top.c == (1, 2)
    top.c.replace(0, 7)
    yield

    assert top.c == (7, 2)
    top.c.insert(1, 8)
    top.c.insert(1, 9)
    yield

    assert top.c == (7, 9, 8, 2)
    top.c.append(55)
    top.c.insert(1, 9)
    top.c.append(33)
    top.c.pop(4)
    top.c.append(22)
    top.c.replace(2, 99)
    top.c.append(11)
    yield

    assert top.c == (7, 9, 99, 8, 55, 33, 22, 11)
    try:
        top.c = (7, 9, 8, 2, 'a string')
    except ValueError:
        pass
    else:
        assert False
    yield

    top.c = (1, 2)
    try:
        top.c.append('a string')
    except ValueError:
        pass
    else:
        assert False
    yield

    try:
        top.c.insert(1, 'a string')
    except ValueError:
        pass
    else:
        assert False
    yield


Tops = enum.Enum('Tops', 'Set Pop Replace Insert Append')

class Change(Record):
    top: Enumeration[Tops]
    cycle: Integer[...] = -1
    new_element: Element
    index: Integer[...]

    def expected(self, previous):
        if self.top is Tops.Pop:
            return (*previous[:self.index], *previous[self.index + 1:])
        elif self.top is Tops.Insert:
            return (*previous[:self.index], self.new_element, *previous[self.index:])
        elif self.top is Tops.Replace:
            return (*previous[:self.index], self.new_element, *previous[self.index + 1:])
        elif self.top is Tops.Append:
            return (*previous, self.new_element)
        else:
            assert False


class TwoRules(Model):
    # only guaranteed compatible processes in this test
    # pop/insert/replace with even/odd indices
    t: Tuple[Element] = (1, 2, 3, 4, 5, 6, 7)
    last_a: Change
    last_b: Change
    last_t: Tuple[Element] = (1, 2, 3, 4, 5, 6, 7)
    cycle: Integer[...] = 0
    clk: Clock[process_a, process_b, check]

    def check(self):
        a = self.last_a if self.last_a.cycle == self.cycle else None
        b = self.last_b if self.last_b.cycle == self.cycle else None
        if a and b:
            first = a if a.index > b.index else b
            second = b if a.index > b.index else a
            expected = first.expected(self.last_t)
            expected = second.expected(expected)
        elif a:
            expected = a.expected(self.last_t)
        elif b:
            expected = b.expected(self.last_t)
        else:
            expected = self.last_t

        assert self.t == expected, str(expected)
        self.last_t = self.t
        self.cycle += 1

    def process_a(self):
        if random.random() < 0.75 and (x := self.change_tuple(1)):
            self.last_a = x

    def process_b(self):
        if random.random() < 0.75 and (x := self.change_tuple(0)):
            self.last_b = x

    def change_tuple(self, lsb):
        index = random.randrange(len(self.t))
        if (index & 1) != lsb:
            return False
        rnd = random.random()
        if rnd < 0.5:
            ne = random.randrange(20)
            self.t.insert(index, ne)
            return Change(
                top = Tops.Insert,
                cycle = self.cycle + 1,
                new_element = ne,
                index = index,
            )
        elif rnd < 0.75:
            ne = random.randrange(20)
            self.t.replace(index, ne)
            return Change(
                top = Tops.Replace,
                cycle = self.cycle + 1,
                new_element = ne,
                index = index,
            )
        else:
            self.t.pop(index)
            return Change(
                top = Tops.Pop,
                cycle = self.cycle + 1,
                index = index,
            )

print('Two concurrent (clocked) rules')
system = TwoRules()
sim = ClockedSimulator(system, dict(frequency_GHz = 1.0, name = 'clk'))
sim.run(cycles = 200)



class NegativeTestBothSet(Model):
    t: Tuple[Element] = (1, 2, 3, 4)
    clk: Clock[process_a, process_b]

    def process_a(self):
        if random.random() < 0.1:
            self.t = (3, 4, 5)

    def process_b(self):
        if random.random() < 0.4:
            self.t = (3, 4, 5, 6)

print('Negative test both-set')
system = NegativeTestBothSet()
sim = ClockedSimulator(system, dict(frequency_GHz = 1.0, name = 'clk'))
try:
    sim.run(cycles = 100)
except NonDeterministicLeafChange:
    pass


class NegativeTestBothAppend(Model):
    t: Tuple[Element] = (1, 2, 3, 4)
    clk: Clock[process_a, process_b]

    def process_a(self):
        if random.random() < 0.1:
            self.t.append(4)

    def process_b(self):
        if random.random() < 0.4:
            self.t.append(7)

print('Negative test both-append')
system = NegativeTestBothAppend()
sim = ClockedSimulator(system, dict(frequency_GHz = 1.0, name = 'clk'))
try:
    sim.run(cycles = 100)
except NonDeterministicLeafChange:
    pass


class NegativeTestSetAndOther(Model):
    op = Tops.Append
    t: Tuple[Element] = (1, 2, 3, 4)
    clk: Clock[process_a, process_b]

    def process_a(self):
        if random.random() < 0.05:
            self.t = (3, 4, 5)

    def process_b(self):
        if random.random() < 0.5:
            if self.op is Tops.Append:
                self.t.append(8)
            elif self.op is Tops.Insert:
                self.t.insert(1, 34)
            elif self.op is Tops.Pop and self.t:
                self.t.pop()
            elif self.op is Tops.Replace:
                self.t.replace(2, 99)

for op in Tops:
    print('Negative test set-and-other', op)
    NegativeTestSetAndOther.op = op
    system = NegativeTestSetAndOther()
    sim = ClockedSimulator(system, dict(frequency_GHz = 1.0, name = 'clk'))
    try:
        sim.run(cycles = 100)
    except NonDeterministicLeafChange:
        pass


class NegativeSameIndex(Model):
    opa = Tops.Insert
    opb = Tops.Insert
    t: Tuple[Element] = (1, 2, 3, 4)
    clk: Clock[process_a, process_b]

    def process_a(self):
        if random.random() < 0.05:
            if self.opa is Tops.Insert:
                self.t.insert(1, 34)
            elif self.opa is Tops.Pop and len(self.t) > 1:
                self.t.pop(1)
            elif self.opa is Tops.Replace and len(self.t) > 1:
                self.t.replace(1, 99)

    def process_b(self):
        if random.random() < 0.5:
            if self.opb is Tops.Insert:
                self.t.insert(1, 34)
            elif self.opb is Tops.Pop and len(self.t) > 1:
                self.t.pop(1)
            elif self.opb is Tops.Replace and len(self.t) > 1:
                self.t.replace(1, 99)

for opa in Tops.Insert, Tops.Pop, Tops.Replace:
    for opb in Tops.Insert, Tops.Pop, Tops.Replace:
        print('Negative test set-and-other', opa, opb)
        NegativeSameIndex.opa = opa
        NegativeSameIndex.opb = opb
        system = NegativeSameIndex()
        sim = ClockedSimulator(system, dict(frequency_GHz = 1.0, name = 'clk'))
        try:
            sim.run(cycles = 100)
        except NonDeterministicLeafChange:
            pass




class ThreeRules(Model):
    # only guaranteed compatible processes in this test
    # pop/insert/replace with even/odd indices
    # append from one rule only
    t: Tuple[Element] = (1, 2, 3, 4, 5, 6, 7)
    last_a: Change
    last_b: Change
    last_c: Change
    last_t: Tuple[Element] = (1, 2, 3, 4, 5, 6, 7)
    cycle: Integer[...] = 0
    clk: Clock[process_a, process_b, process_c, check]

    def check(self):
        expected = self.last_t
        changes = []
        if self.last_a.cycle == self.cycle:
            changes.append(self.last_a)
        if self.last_b.cycle == self.cycle:
            changes.append(self.last_b)
        if self.last_c.cycle == self.cycle:
            changes.append(self.last_c)

        if changes:
            changes.sort(reverse = True, key = lambda x: x.index)
            for c in changes:
                expected = c.expected(expected)

        assert self.t == expected, str(expected)
        self.last_t = self.t
        self.cycle += 1

    def process_a(self):
        if random.random() < 0.75 and (x := self.change_tuple(1)):
            self.last_a = x

    def process_b(self):
        if random.random() < 0.75 and (x := self.change_tuple(0)):
            self.last_b = x

    def process_c(self):
        if random.random() < 0.75 and (x := self.change_tuple(2)):
            self.last_c = x

    def change_tuple(self, imod):
        index = random.randrange(len(self.t))
        if (index % 3) != imod:
            return False

        thresholds = [0.25, 0.5, 0.75] if imod == 0 else [0.0, 0.5, 0.75]
        rnd = random.random()
        ne = random.randrange(20)
        if rnd < thresholds[0]:
            self.t.append(ne)
            top = Tops.Append
        elif rnd < thresholds[1]:
            self.t.insert(index, ne)
            top = Tops.Insert
        elif rnd < thresholds[2]:
            ne = random.randrange(20)
            self.t.replace(index, ne)
            top = Tops.Replace
        else:
            self.t.pop(index)
            top = Tops.Pop

        return Change(
            cycle = self.cycle + 1,
            index = index,
            top = top,
            new_element = ne,
        )

print('Three concurrent (clocked) rules')
system = ThreeRules()
sim = ClockedSimulator(system, dict(frequency_GHz = 1.0, name = 'clk'))
sim.run(cycles = 200)
