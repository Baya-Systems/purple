'''
MIT Licence: Copyright (c) 2025 Baya Systems <https://bayasystems.com>

Purple Tests
======================

Rule test

Tests
    with parameters (single and multi)
    with guards
    override base class rule method
    get rule from base class
    rule in sub-model
    add to base class rules
    remove base class rules
    print
'''

import random
import io
import contextlib
from purple import Model, Integer
from purple.state import Boolean


class RuleTest(Model):
    counter: Integer[10] = 0
    rules: [increment_counter, set_counter, up_down_counter]

    def increment_counter(self):
        self.counter = (self.counter + 1) % 10

    def set_counter(self, a: Integer[10]):
        self.counter = a

    def up_down_counter(self, up_n_down: Boolean, a: Integer[10]):
        if up_n_down:
            self.counter = (a + self.counter)  % 10
        else:
            self.counter = (self.counter - a)  % 10
        self.guard(self.counter != 5)
        self.print('up' if up_n_down else 'down', a, 'to', self.counter)

system = RuleTest()

increment = next(system.find_rule(method_name = 'increment_counter'))
for x in range(30):
    expected = x % 10
    witnessed = system.counter
    assert expected == witnessed, f'expected {expected} but got {witnessed}'
    increment.invoke()

for _ in range(30):
    v = random.randrange(10)
    setv = next(system.find_rule(method_name = 'set_counter', params = dict(a = v)))
    setv.invoke()
    assert system.counter == v

for x in range(100):
    p = dict(a = random.randrange(10), up_n_down = random.random() < 0.5)
    the_rule = next(system.find_rule(method_name = 'up_down_counter', params = p))
    with contextlib.redirect_stdout(io.StringIO()) as str_stdout:
        the_rule.invoke()
    vnew = (v + p['a']) if p['up_n_down'] else (v - p['a'])
    printout = str_stdout.getvalue()
    if vnew % 10 != 5:
        v = vnew
        assert printout
        if x % 10 == 0:
            print('example print >>>', printout, end = '')
    else:
        assert not printout
    assert system.counter == v % 10


class SubModel(Model):
    x: Boolean = True
    rules: [toggle]
    def toggle(self):
        self.x = not self.x

class RuleTest2(RuleTest):
    subm: SubModel
    counter: Integer[10] = 7
    rules: [reset]
    non_rules: [up_down_counter]

    def increment_counter(self):
        self.counter = (self.counter + 3) % 10

    def reset(self):
        self.subm.x = True
        self.counter = 7

system2 = RuleTest2()

increment = next(system2.find_rule(method_name = 'increment_counter'))
for x in range(7, 90, 3):
    expected = x % 10
    witnessed = system2.counter
    assert expected == witnessed, f'expected {expected} but got {witnessed}'
    increment.invoke()

for _ in range(30):
    v = random.randrange(10)
    setv = next(system2.find_rule(method_name = 'set_counter', params = dict(a = v)))
    setv.invoke()
    assert system2.counter == v

for _ in range(30):
    p = dict(a = random.randrange(10), up_n_down = random.random() < 0.5)
    try:
        the_rule = next(system2.find_rule(method_name = 'up_down_counter', params = p))
    except StopIteration:
        pass
    else:
        assert False

toggle = next(system2.find_rule(method_name = 'toggle'))
for x in range(1, 10):
    expected = (x & 1) == 1
    witnessed = system2.subm.x
    assert expected == witnessed, f'expected {expected} but got {witnessed}'
    toggle.invoke()

setv = next(system2.find_rule(method_name = 'set_counter', params = dict(a = 0)))
setv.invoke()
while system2.subm.x:
    toggle.invoke()
reset = next(system2.find_rule(method_name = 'reset'))
reset.invoke()
assert system2.counter == 7
assert system2.subm.x
