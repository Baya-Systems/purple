'''
MIT Licence: Copyright (c) 2025 Baya Systems <https://bayasystems.com>

Purple Tests
======================

Counter test

Tests in place
    with/without initial value
    out-of-bounds guard and error
    multiple changes per invocation
    reasonable integer operations work even if not setting
    2 processes allowed to add/sub in the same cycle
    negative test can't both set
    negative test can't incr when the other sets
    3 processes allowed to add/sub in the same cycle
'''

import random

from purple import (
    Clock,
    ClockedSimulator,
    Counter,
    CounterOutOfRange,
    GuardFailed,
    Integer,
    Model,
    NonDeterministicLeafChange,
)

import cli


class OneRule(cli.Test.Top):
    c: Counter[20]
    d: Counter[dict(limit = 5, out_of_range_is_error = True)] = 2

@cli.Test(OneRule())
def test_one_rule(top):
    print('Single (atomic) rule')
    assert top.d == 2
    cli.expect_undef(top, 'c')
    top.c = 13
    yield

    assert top.c == 13
    top.d += 1
    yield

    assert top.d == 3
    yield

    try:
        top.d += 57
    except CounterOutOfRange:
        pass
    else:
        assert False
    yield

    try:
        top.c = -1
    except GuardFailed:
        pass
    else:
        assert False
    yield

    assert top.c == 13
    assert top.d == 3
    top.c = 10
    top.c += 4
    yield

    assert top.c == 14
    top.c -= 6
    yield

    assert top.c == 8
    top.c += 2
    top.c = 19
    yield

    assert top.c == 19
    top.c -= 11
    top.c = 3
    top.c -= 2
    yield

    assert top.c == 1
    top.c = 11
    top.c += 3
    top.c = 2
    yield

    assert top.c == 2
    top.c *= 7
    yield

    assert top.c == 14
    assert top.c ^ 5 == 11
    yield


class TwoRules(Model):
    counter: Counter[10] = 5
    last_a: Integer[-4, 5] = 0
    last_b: Integer[-4, 5] = 0
    last_c: Integer[...] = 5
    cycle: Integer[...] = 0
    cycle_a: Integer[...] = 0
    cycle_b: Integer[...] = 0
    clk: Clock[process_a, process_b, check]

    def check(self):
        last_a = 0 if self.cycle_a < self.cycle else self.last_a
        last_b = 0 if self.cycle_b < self.cycle else self.last_b
        assert self.counter == self.last_c + last_a + last_b
        assert self.counter >= 0
        assert self.counter < 10
        self.last_c = self.counter
        self.cycle += 1

    def process_a(self):
        # guarded if we go out of bounds, even if this only happens on merge with b
        if random.random() < 0.75:
            self.last_a = self.change_counter()
            self.cycle_a = self.cycle + 1

    def process_b(self):
        # guarded if we go out of bounds, even if this only happens on merge with a
        if random.random() < 0.75:
            self.last_b = self.change_counter()
            self.cycle_b = self.cycle + 1

    def change_counter(self):
        incr = random.randrange(5)
        if random.random() < 0.5:
            self.counter += incr
            return incr
        else:
            self.counter -= incr
            return -incr

print('Two concurrent (clocked) rules')
system = TwoRules()
sim = ClockedSimulator(system, dict(frequency_GHz = 1.0, name = 'clk'))
sim.run(cycles = 100)


class NegativeTestBothSet(Model):
    counter: Counter[10] = 5
    clk: Clock[process_a, process_b]

    def process_a(self):
        if random.random() < 0.1:
            self.counter = 4

    def process_b(self):
        if random.random() < 0.4:
            self.counter = 3

print('Negative test both-set')
system = NegativeTestBothSet()
sim = ClockedSimulator(system, dict(frequency_GHz = 1.0, name = 'clk'))
try:
    sim.run(cycles = 100)
except NonDeterministicLeafChange:
    pass


class NegativeTestSetAndIncr(Model):
    counter: Counter[10] = 5
    clk: Clock[process_a, process_b]

    def process_a(self):
        if random.random() < 0.05:
            self.counter += 1

    def process_b(self):
        if random.random() < 0.5:
            self.counter = 5

print('Negative test set-and-incr')
system = NegativeTestBothSet()
sim = ClockedSimulator(system, dict(frequency_GHz = 1.0, name = 'clk'))
try:
    sim.run(cycles = 100)
except NonDeterministicLeafChange:
    pass


class ThreeRules(Model):
    counter: Counter[10] = 5
    last_a: Integer[-4, 5] = 0
    last_b: Integer[-4, 5] = 0
    last_c: Integer[-4, 5] = 0
    last_cnt: Integer[...] = 5
    cycle: Integer[...] = 0
    cycle_a: Integer[...] = 0
    cycle_b: Integer[...] = 0
    cycle_c: Integer[...] = 0
    clk: Clock[process_a, process_b, process_c, check]

    def check(self):
        last_a = 0 if self.cycle_a < self.cycle else self.last_a
        last_b = 0 if self.cycle_b < self.cycle else self.last_b
        last_c = 0 if self.cycle_c < self.cycle else self.last_c
        assert self.counter == self.last_cnt + last_a + last_b + last_c
        assert self.counter >= 0
        assert self.counter < 10
        self.last_cnt = self.counter
        self.cycle += 1

    def process_a(self):
        # guarded if we go out of bounds, even if this only happens on merge with b
        if random.random() < 0.75:
            self.last_a = self.change_counter()
            self.cycle_a = self.cycle + 1

    def process_b(self):
        # guarded if we go out of bounds, even if this only happens on merge with a
        if random.random() < 0.75:
            self.last_b = self.change_counter()
            self.cycle_b = self.cycle + 1

    def process_c(self):
        # guarded if we go out of bounds, even if this only happens on merge with a
        if random.random() < 0.75:
            self.last_c = self.change_counter()
            self.cycle_c = self.cycle + 1

    def change_counter(self):
        incr = random.randrange(5)
        if random.random() < 0.5:
            self.counter += incr
            return incr
        else:
            self.counter -= incr
            return -incr

print('Three concurrent (clocked) rules')
system = ThreeRules()
sim = ClockedSimulator(system, dict(frequency_GHz = 1.0, name = 'clk'))
sim.run(cycles = 100)
