'''
MIT Licence: Copyright (c) 2025 Baya Systems <https://bayasystems.com>

Purple Tests
======================

Smoke test
'''

from purple import Model, Integer


class SmokeTest(Model):
    counter: Integer[10] = 0
    rules: [increment_counter]

    def increment_counter(self):
        self.counter = (self.counter + 1) % 10


system = SmokeTest()

increment = next(system.find_rule(component = system))
assert increment.method_name == 'increment_counter'
assert not increment.params

assert increment is next(system.find_rule(method_name = 'increment_counter'))

for x in range(30):
    expected = x % 10
    witnessed = system.counter
    assert expected == witnessed, f'expected {expected} but got {witnessed}'
    increment.invoke()
