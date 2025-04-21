'''
MIT Licence: Copyright (c) 2025 Baya Systems <https://bayasystems.com>

Purple Tests
======================

Static-Record test

* model containing records containing records
* initial values overridden from model and from record
* set-state
    * leaf
    * static from transient (hierarchical and one-level)
    * static from other static (hierarchical and one-level)
    * set to undef (hierarchical and one-level)
* set transient field from static (shallow copy)
* update static record
* deep-copy of static to create transient
* equality test between static and transient
* iteration over all possible values
'''

from purple import Record, Integer, UnDefined
import cli


class OneLevel(Record):
    x: Integer[10] = 0
    y: Integer[10] = 1

class TwoLevel(Record):
    e: OneLevel
    f: OneLevel = dict(x = 5)
    g: Integer[10] = 4
    h: Integer[10]

class Top(cli.Test.Top):
    a: OneLevel
    b: OneLevel = dict(x = 9, y = 8)
    c: TwoLevel
    d: TwoLevel = dict(g = 3, f = dict(x = 6, y = 6), h = 8)


@cli.Test(Top())
def the_test(top):
    print('initial values for static state')
    assert top.a.x == 0 and top.a.y == 1
    assert top.b.x == 9 and top.b.y == 8

    assert top.c.g == 4
    assert top.c.f.x == 5
    assert top.c.f.y == 1
    cli.expect_undef(top.c, 'h')
    assert top.d.h == 8
    assert top.c.e.x == 0
    assert top.c.e.y == 1

    assert top.d.g == 3
    assert top.d.e.x == 0
    assert top.d.e.y == 1
    assert top.d.f.x == 6
    assert top.d.f.y == 6
    yield

    print('set leaf state')
    top.c.g = 0
    top.b.x = 7
    assert top.c.g == 0
    assert top.b.x == 7
    yield

    print('set record state from one-level transient')
    top.a = OneLevel(x = 2, y = 3)
    assert top.a.x == 2 and top.a.y == 3
    yield

    print('set record state from hierarchical transient, separate copies made')
    one_level = OneLevel(x = 2, y = 5)
    top.c = TwoLevel(g = 9, e = one_level, f = one_level)
    assert top.c.e.x == 2 and top.c.e.y == 5
    assert top.c.f.x == 2 and top.c.f.y == 5
    cli.expect_undef(top.c, 'h')
    top.c.e.x = 3
    top.c.f.y = 4
    assert top.c.e.x == 3 and top.c.e.y == 5
    assert top.c.f.x == 2 and top.c.f.y == 4
    yield

    print('create record one-level instance, copied leaves')
    one_level = OneLevel(x = 2, y = 5)
    top.c = TwoLevel(g = 9, e = one_level)
    one_copy = OneLevel(x = top.c.e.x, y = top.c.e.y) # FIXME should be top.c.e.copy()
    assert one_copy.x == 2 and one_copy.y == 5
    one_copy.x = 8
    assert top.c.e.x == 2 and top.c.e.y == 5
    top.c.e = one_copy
    assert top.c.e.x == 8 and top.c.e.y == 5
    top.c.e.y = 8
    assert one_copy.x == 8 and one_copy.y == 5
    yield

    print('create record two-level instance, shallow-copied sub-records')
    one_level = OneLevel(x = 2, y = 5)
    top.d = TwoLevel(g = 9, e = dict(x = 2, y = 5), f = dict(x = 1, y = 1), h = 4)
    two_copy = TwoLevel(e = top.d.e, f = top.d.f, g = top.d.g, h = top.d.h) # FIXME should be top.d.copy()
    assert two_copy.g == 9
    assert two_copy.e.y == 5
    two_copy.h = 8
    assert top.d.h == 4
    two_copy.f.y = 9
    assert top.d.f.y == 9
    top.c = two_copy
    assert top.c.f.y == 9 and top.c.h == 8
    two_copy.f.y = 7
    assert top.c.f.y == 9 and top.c.h == 8
    yield

    print('update static record')
    top.a.x = 0
    top.a.y = 1
    top.a.update(x = 2)
    assert top.a.x == 2 and top.a.y == 1
    top.a.update(x = 3, y = 4)
    assert top.a.x == 3 and top.a.y == 4
    top.c.update(e = OneLevel(x = 0, y = 1), f = OneLevel(x = 2, y = 3), g = 4, h = 5)
    assert top.c.f.x == 2
    assert top.c.h == 5
    top.c.h = UnDefined
    assert top.c.g == 4
    cli.expect_undef(top.c, 'h')
    top.c = UnDefined
    cli.expect_undef(top.c.e, 'x')
    yield

    print('deep copy into transient')
    top.a.x = 0
    top.a.y = 1
    one_level = top.a.copy()
    assert one_level.x == 0 and one_level.y == 1
    top.c.update(e = OneLevel(x = 0, y = UnDefined), f = OneLevel(x = 2, y = 3), g = UnDefined, h = 5)
    two_level = top.c.deep_copy()
    assert two_level.h == 5
    assert two_level.f.y == 3
    cli.expect_undef(two_level.e, 'y')
    cli.expect_undef(two_level, 'g')
    two_level.f.y = 4
    assert top.c.f.y == 3
    yield

    print('set static from static')
    top.c.update(e = OneLevel(x = 0, y = UnDefined), f = OneLevel(x = 2, y = 3), g = UnDefined, h = 5)
    top.d = top.c
    cli.expect_undef(top.d.e, 'y')
    assert top.d.e.x == 0
    top.d.e.y = 5
    assert top.d.e.y == 5
    cli.expect_undef(top.c.e, 'y')
    yield

    print('transient field from static record (shallow)')
    top.c.update(e = OneLevel(x = 0, y = UnDefined), f = OneLevel(x = 2, y = 3), g = UnDefined, h = 5)
    two_level = top.c.copy()
    top.d.f.update(x = 7, y = 6)
    two_level.e = top.d.f
    assert two_level.e.x == 7
    assert two_level.f.x == 2
    top.d.f.x = 6
    assert two_level.e.x == 6
    yield

    print('equality between transient and static')
    top.a.x = 0
    top.a.y = 1
    one_level = top.a.copy()
    assert one_level == top.a
    top.a.x = 5
    assert one_level != top.a
    top.c.update(e = OneLevel(x = 0, y = UnDefined), f = OneLevel(x = 2, y = 3), g = UnDefined, h = 5)
    two_level = top.c.copy()
    assert top.c == two_level
    two_level.f.y = 4
    assert top.c == two_level
    top.c.update(e = OneLevel(x = 0, y = UnDefined), f = OneLevel(x = 2, y = 3), g = UnDefined, h = 5)
    two_level = top.c.deep_copy()
    assert top.c == two_level
    two_level.f.y = 4
    assert top.c != two_level
    yield

    print('all possible values')
    ol_values = list(OneLevel._dp_all_possible_values())
    assert len(ol_values) == 100
    assert OneLevel(x = 3, y = 7) in ol_values
    if not cli.args.quick:
        tl_values = list(TwoLevel._dp_all_possible_values())
        assert len(tl_values) == 100 * 100 * 10 * 10
        assert TwoLevel(e = OneLevel(x = 0, y = 2), f = OneLevel(x = 2, y = 3), g = 9, h = 5) in tl_values
