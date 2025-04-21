'''
MIT Licence: Copyright (c) 2025 Baya Systems <https://bayasystems.com>

Purple Tests
======================

This file tests the ModuloInteger leaf class (transient or in system)
'''

from purple import (
    Model, Record, ModuloInteger
)

import random


class RCT(Record):
    first: ModuloInteger[23] = 10
    second: ModuloInteger[5]


class Top(Model):
    d: ModuloInteger[4]
    e: ModuloInteger[7] = 7

    rules: [run]
    def run(self):
        assert self.e == 0
        for _ in range(20):
            r,m = test(7)
            self.e = r
            assert self.e == m and self.e >= 0
        for _ in range(20):
            r,m = test(4)
            self.d = r
            assert self.d == m

rc = RCT()
top = Top()
run = next(top.find_rule(component = top))

def test(modu):
    raw = random.randrange(-10 * modu, 10 * modu)
    ptv = raw + 20 * modu
    return raw, (ptv % modu)

print('test in-system')
run.invoke()

print('test in transient record')
assert rc.first == 10
for _ in range(20):
    r,m = test(23)
    rc.first = r
    assert rc.first == m and rc.first >= 0, f'{rc.first} {r} {m}'
for _ in range(20):
    r,m = test(5)
    rc.second = r
    assert rc.second == m


print('operators')
rc.second = 12
assert rc.second == 2
assert rc.second * 7 == 4
assert 7 * rc.second == 14
rc.second += 1
assert rc.second == 3
assert -rc.second == 2
assert rc.second
rc.second = 0
assert not rc.second
