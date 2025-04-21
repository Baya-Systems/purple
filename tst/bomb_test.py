'''
MIT Licence: Copyright (c) 2025 Baya Systems <https://bayasystems.com>

Purple Tests
======================

Demo
'''

from purple import Integer, Enumeration, Model, AtomicRuleSimulator, Clock, ClockedSimulator
import enum
import random


BombState = enum.Enum('BombState', 'Ready Counting Exploded Safe')


class Bomb(Model):
    state: Enumeration[BombState] = BombState.Ready
    count: Integer[100]

    rules: [prime, countdown, cut_blue_wire, cut_red_wire]

    def prime(self, countdown_duration: Integer[10, 100]):
        self.guard(self.state is BombState.Ready)
        self.count = countdown_duration
        self.state = BombState.Counting

    def countdown(self):
        self.guard(self.state is BombState.Counting)
        self.count -= 1
        if self.count == 0:
            self.state = BombState.Exploded
            self.print('-----BOOM-----')

    def cut_blue_wire(self):
        self.guard(self.state is BombState.Counting)
        self.state = BombState.Safe
        self.print('phew')

    def cut_red_wire(self):
        self.guard(self.state is BombState.Counting)
        self.state = BombState.Exploded
        self.print('-----BADABOOM-----')


class Sim(AtomicRuleSimulator):
    def make_rule_pool(self):
        # increase number of countdown rule to make it more likely
        countdown = next(r for r in self.all_rules if r.method_name == 'countdown')
        return self.all_rules + tuple(countdown for _ in range(80))

print()
print('atomic-rule bomb')
print('===========================')
countdown_expired = False
defused = False
triggered = False
for _ in range(20):
    system = Bomb()
    sim = Sim(system)
    while not sim.deadlocked:
        sim.run(num_invocations = 200)
    if system.state is BombState.Safe:
        defused = True
    elif system.state is BombState.Exploded:
        if system.count > 0:
            triggered = True
        else:
            countdown_expired = True
    else:
        assert False, 'unexpected end state'
assert defused and triggered
assert countdown_expired


class ClockedBomb(Model):
    state: Enumeration[BombState] = BombState.Ready
    count: Integer[100]

    clk: Clock[rising_edge_event]

    def rising_edge_event(self):
        if self.state is BombState.Ready:
            self.count = random.randrange(20, 100)
            self.state = BombState.Counting

        elif self.state is BombState.Counting:
            if random.random() < 0.975:
                self.count -= 1
                if self.count == 0:
                    self.state = BombState.Exploded
                    self.print('-----BOOM-----')

            elif random.random() < 0.5:
                self.state = BombState.Safe
                self.print('phew')

            else:
                self.state = BombState.Exploded
                self.print('-----BADABOOM-----')


print()
print('clocked bomb')
print('===========================')
countdown_expired = False
defused = False
triggered = False
for _ in range(20):
    system = ClockedBomb('bomb')
    sim = ClockedSimulator(system, dict(frequency_GHz = 1.0, name = 'clk'))
    while True:
        sim.run(cycles = 200)
        if system.state is not BombState.Counting:
            break
    if system.state is BombState.Safe:
        defused = True
    elif system.state is BombState.Exploded:
        if system.count > 0:
            triggered = True
        else:
            countdown_expired = True
    else:
        assert False, 'unexpected end state'
assert defused and triggered
assert countdown_expired
