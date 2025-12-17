'''
MIT Licence: Copyright (c) 2025 Baya Systems <https://bayasystems.com>

Purple Tests
======================

test for Clock simulator class

almost the same as the clock test, but using the simulator rather than doing it manually

FIXME
    guards
    local-guards
    rules with parameters
    save/restore
    printout management and other hooks
    undo
    debug on exception
'''

from purple import Integer, Model, Record, Clock, ClockedSimulator, Boolean


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

print('dual-clock hierarchical')
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
print('done')


class ClockedGuardsParams(Model):
    value: Integer[...] = 0
    previous_value: Integer[...] = 0
    last_amount: Integer[...] = 0
    second_value: Integer[...] = 0
    third_value: Integer[...] = 0

    clk: Clock[change_value, play_with_others]

    def change_value(self, amount: Integer[-3, 4]):
#        self.print(amount, self.previous_value)
        self.guard(-2 <= amount < 3)
        self.previous_value = self.value
        self.last_amount = amount
        self.value += amount

    def play_with_others(self, second_not_third: Boolean):
        # this is a test example which should be functionally the same as
        # play_with_others_reference_code()
        # the idea is that if some operation is guarded, the process can
        # continue and do other things
        with self.guards_limited_to_code_block():
            self.second_value += 1
            self.guard(second_not_third)

        with self.guards_limited_to_code_block():
            self.third_value += 1
            self.guard(not second_not_third)

    def play_with_others_reference_code(self, second_not_third: Boolean):
        if second_not_third:
            self.second_value += 1
        else:
            self.third_value += 1


system2 = ClockedGuardsParams('system')

class CSim(ClockedSimulator):
    def run(self, cycles):
        final_time_ps = self.sim_end_time(cycles = cycles)

        seen = set()
        s,t = 0,0
        for _ in self.run_one_step(final_time_ps, True, True):
            last_amount = self.system.last_amount
            seen.add(last_amount)
            assert -2 <= last_amount < 3
            assert self.system.previous_value + last_amount == self.system.value

            st_now = self.system.second_value, self.system.third_value
            assert st_now in ((s, t+1), (s+1, t))
            s,t = st_now

        assert seen == {-2, -1, 0, 1, 2}
        print('end state', s, t, self.system.value)

sim = CSim(system2, dict(frequency_GHz = 1.0, name = 'clk'))

print('guards and parameters')
print('run for time, 100 cycles of faster clock')
sim.run(cycles = 100)
