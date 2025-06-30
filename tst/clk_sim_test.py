'''
MIT Licence: Copyright (c) 2025 Baya Systems <https://bayasystems.com>

Purple Tests
======================

test for Clock simulator class

almost the same as the clock test, but using the simulator rather than doing it manually

FIXME
    save/restore
    printout management and other hooks
    undo
    debug on exception
'''

from purple import Integer, Model, Record, Clock, ClockedSimulator


class Record_SubComp(Record):
    a: Integer[...] = 5


class ClockedSubModule(Model):
    x: Record_SubComp
    counter_a: Integer[...] = 0
    counter_b: Integer[...] = 0

    def increment_a(self):
        self.counter_a = self.counter_a + 1

    clk_a: Clock[increment_a]
    clk_b: Clock[increment_b]

    def increment_b(self):
        self.counter_b = self.counter_b + 1


class ClockedTop(Model):
    sub: ClockedSubModule
    counter: Integer[...] = 0
    counter_b: Integer[...] = 0

    clk: Clock[increment_counter, sub.clk_a, check_counter]

    def increment_counter(self):
        assert self.counter == self.counter_b
        self.counter = self.counter + 1

    def check_counter(self):
        assert self.counter == self.counter_b
        self.counter_b = self.counter_b + 1


system = ClockedTop('system')

sim = ClockedSimulator(
    system,
    dict(frequency_GHz = 1.0, name = 'clk'),
    dict(period_ps = 3333, component_name = ('system', 'sub')),
)

print('run for time, 100 cycles of faster clock')
sim.run(duration_ps = 99 * 1000 + 1)
assert system.counter == 100, f'counter = {system.counter}'
assert system.counter_b == 100
assert system.sub.counter_a == 100
assert system.sub.counter_b == 30

print('run for 100 cycles of faster clock')
sim.run(cycles_of_fastest_clock = 100)
assert system.counter == 200, f'counter = {system.counter}'
assert system.counter_b == 200
assert system.sub.counter_a == 200
assert system.sub.counter_b == 60
