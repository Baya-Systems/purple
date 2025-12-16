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
BombEvent = enum.Enum('BombEvent', 'Prime CutBlue CutRed Hesitate')


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

    def rising_edge_event(self, initial_count: Integer[20, 100], event: Enumeration[BombEvent]):
        if self.state is BombState.Ready and event is BombEvent.Prime:
            self.count = initial_count
            self.state = BombState.Counting

        elif self.state is BombState.Counting:
            if event is BombEvent.CutBlue:
                self.state = BombState.Safe
                self.print('phew')
            elif event is BombEvent.CutRed:
                self.state = BombState.Exploded
                self.print('-----BADABOOM-----')
            else:
                self.count -= 1
                if self.count == 0:
                    self.state = BombState.Exploded
                    self.print('-----BOOM-----')


class Cim(ClockedSimulator):
    def __init__(self, system, clock_input):
        super().__init__(system, clock_input)
        assert len(self.clocks) == 1
        clk, clk_name = self.clocks[0]
        assert len(clk.rules_by_method) == 1
        rules = next(iter(clk.rules_by_method.values()))
        self.prime_rules = [r for r in rules if r.params['event'] is BombEvent.Prime]
        self.red_rules = [r for r in rules if r.params['event'] is BombEvent.CutRed]
        self.blue_rules = [r for r in rules if r.params['event'] is BombEvent.CutBlue]
        self.count_rules = [r for r in rules if r.params['event'] is BombEvent.Hesitate]
        self.primed = False

    def select_rules(self, clock, clock_name):
        '''prior to clock event, select maximum one rule for each method

        in this case there's only one method so just choose one rule at random
        which represents the input stimulus to the model
        respect the interface protocol: only prime it once
        '''
        if self.primed:
            if random.random() < 0.975:
                return [random.choice(self.count_rules)]
            elif random.random() < 0.5:
                return [random.choice(self.blue_rules)]
            else:
                return [random.choice(self.red_rules)]
        else:
            self.primed = True
            return [random.choice(self.prime_rules)]

print()
print('clocked bomb')
print('===========================')
countdown_expired = False
defused = False
triggered = False
for _ in range(20):
    system = ClockedBomb('bomb')
    sim = Cim(system, dict(frequency_GHz = 1.0, name = 'clk'))
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
