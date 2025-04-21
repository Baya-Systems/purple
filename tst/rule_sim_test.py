'''
MIT Licence: Copyright (c) 2025 Baya Systems <https://bayasystems.com>

Purple Tests
======================

test for Atomic-Rule simulator class

almost the same as the clock test, but using the simulator rather than doing it manually

FIXME
    override rule selection
    cases where there are guards and deadlocks
    printout management and other hooks
    save/restore
    undo
    debug on exception
'''

from purple import Integer, Model, AtomicRuleSimulator


class SubModule(Model):
    counter_a: Integer[...] = 0
    counter_b: Integer[...] = 0

    rules: [increment_a, increment_b]

    def increment_a(self):
        self.counter_a = self.counter_a + 1

    def increment_b(self):
        self.counter_b = self.counter_b + 1


class Top(Model):
    sub: SubModule
    counter: Integer[...] = 0
    counter_b: Integer[...] = 0

    rules: [increment_counter, b_counter]

    def increment_counter(self):
        self.counter = self.counter + 1

    def b_counter(self):
        self.counter_b = self.counter_b + 1


system = Top('system')

sim = AtomicRuleSimulator(
    system = system,
)

counts = (0, 0, 0, 0)
num_invocations = 0

print('check all rules can fire')
while any(c == 0 for c in counts):
    sim.run(num_invocations = 1)
    counts = (system.counter, system.counter_b, system.sub.counter_a, system.sub.counter_b)
    num_invocations += 1

for _ in range(10):
    print('run 100 randomly-chosen rules')
    sim.run(num_invocations = 100)
    new_counts = (system.counter, system.counter_b, system.sub.counter_a, system.sub.counter_b)
    num_invocations += 100
    assert all(nc >= c for nc,c in zip(new_counts, counts))
    counts = new_counts

print(num_invocations, counts)
assert num_invocations == sum(counts)
