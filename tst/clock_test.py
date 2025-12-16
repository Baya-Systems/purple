'''
MIT Licence: Copyright (c) 2025 Baya Systems <https://bayasystems.com>

Purple Tests
======================

test for Clock class

checks
    finding clocked rules by clock name
    multiple rules for one clock
    multiple clocks in a simulation
    unbound clock in submodule
    concurrency

FIXME
    arrays of subcomponents with clocks (known to work with *[x.y for x in z])
    methods with parameters (known to work)
    non-immediate visibility of changes
    guard in clocked-method
'''

from purple import Integer, Clock, Model


class ClockedSubModule(Model):
    counter_a: Integer[10] = 0
    counter_b: Integer[10] = 0

    def increment_a(self):
        self.counter_a = (self.counter_a + 1) % 10

    clk_a: Clock[increment_a]
    clk_b: Clock[increment_b]

    def increment_b(self):
        self.counter_b = (self.counter_b + 1) % 10


class ClockedTop(Model):
    sub: ClockedSubModule
    counter: Integer[10] = 0
    counter_b: Integer[10] = 0

    clk: Clock[increment_counter, sub.clk_a, check_counter]

    def increment_counter(self):
        assert self.counter == self.counter_b
        self.counter = (self.counter + 1) % 10

    def check_counter(self):
        assert self.counter == self.counter_b
        self.counter_b = (self.counter_b + 1) % 10


system = ClockedTop()

clk = next(system.find_clock(name = 'clk'))
clk.set_period_ps(1000)

clk_b = next(system.find_clock(component = system.sub))
clk_b.set_period_ps(3333)

for x in range(60):
    expected = x % 10
    witnessed = system.counter
    assert expected == witnessed, f'top: expected {expected} but got {witnessed}'
    witnessed = system.sub.counter_a
    assert expected == witnessed, f'sub: expected {expected} but got {witnessed}'
    clk.event(clk.rules)
assert clk.next_event_time_ps == 1000 * 60

for x in range(20):
    expected = x % 10
    witnessed = system.sub.counter_b
    assert expected == witnessed, f'sub-b: expected {expected} but got {witnessed}'
    assert system.counter == 0
    clk_b.event(clk_b.rules)
assert clk_b.next_event_time_ps == 3333 * 20

for x in range(2000):
    min_clk = min(clk, clk_b)
    min_clk.event(min_clk.rules)
    assert system.counter == system.counter_b

print(f'CLK:    next-t: {clk.next_event_time_ps}, events: {clk.num_events}')
print(f'CLK-B:  next-t: {clk_b.next_event_time_ps}, events: {clk_b.num_events}')

for c in clk,clk_b:
    assert c.next_event_time_ps == c.num_events * c.period_ps

assert -3500 < clk.next_event_time_ps - clk_b.next_event_time_ps < 3500
