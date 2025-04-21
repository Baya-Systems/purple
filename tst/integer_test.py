'''
MIT Licence: Copyright (c) 2025 Baya Systems <https://bayasystems.com>

Purple Tests
======================

This file tests the Integer leaf class
    transient or in system
    bounded and unbounded
'''

from purple import Record, Integer
import cli
import random


class RCT(Record):
    unbounded: Integer[...] = 0
    unboundedb: Integer[None] = -124
    to_23: Integer[23] = 10
    from_n6_to_0: Integer[-6]
    from_5_to_10: Integer[5, 10]
    from_n_to_7: Integer[..., 7]
    from_n3_to_p: Integer[-3, ...]


class Top(cli.Test.Top):
    v: RCT = dict(unbounded = -15, from_5_to_10 = 6)

@cli.Test(Top())
def the_test(top):
    print('testing different sorts of static state integers')
    yield

    v = top.v
    assert v.unbounded == -15
    assert v.unboundedb == -124
    assert v.to_23 == 10
    assert v.from_5_to_10 == 6
    yield

    for nm,rr in (
        ('unbounded', (-10000, 10000)),
        ('unboundedb', (-10000, 10000)),
        ('to_23', (0, 23)),
        ('from_n6_to_0', (-5, 1)),
        ('from_5_to_10', (5, 10)),
        ('from_n_to_7', (-10000, 7)),
        ('from_n3_to_p', (-3, 10000)),
    ):
        for _ in range(20):
            x = random.randrange(*rr)
            setattr(v, nm, x)
            yield

            assert getattr(v, nm) == x
            yield

    v.to_23 = 5
    v.to_23 += 4
    yield

    assert v.to_23 == 9
    yield


print('testing different sorts of integers in a transient record')

v_transient = RCT()
v = v_transient

for nm,rr in (
    ('unbounded', (-10000, 10000)),
    ('unboundedb', (-10000, 10000)),
    ('to_23', (0, 23)),
    ('from_n6_to_0', (-5, 1)),
    ('from_5_to_10', (5, 10)),
    ('from_n_to_7', (-10000, 7)),
    ('from_n3_to_p', (-3, 10000)),
):
    for _ in range(20):
        x = random.randrange(*rr)
        setattr(v, nm, x)
        assert getattr(v, nm) == x

v.to_23 = 5
v.to_23 += 4
assert v.to_23 == 9
assert v is v_transient

v2 = v.copy()
v3 = v.deep_copy()
assert v2 is not v and v2 == v
assert v3 is not v and v3 == v
assert v2 is not v3 and v2 == v3

v2.to_23 = 20
assert v2 is not v and v2 != v
assert v3 is not v and v3 == v
assert v2 is not v3 and v2 != v3

def test_apv(cls, expected):
    try:
        apv = list(cls._dp_all_possible_values())
    except:
        assert expected is None
    else:
        assert len(apv) == expected

test_apv(RCT, None)
test_apv(Integer[...], None)
test_apv(Integer[None], None)
test_apv(Integer[23], 23)
test_apv(Integer[-6], 6)
test_apv(Integer[5, 10], 5)
test_apv(Integer[..., 7], None)
test_apv(Integer[-3, ...], None)
