'''
MIT Licence: Copyright (c) 2025 Baya Systems <https://bayasystems.com>

Purple Tests
======================

Tuple-Leaf testing

A Tuple is a Leaf state element containing an ordered list of any number of entries

The entries are transient frozen record objects, all the same type
This is a somewhat informal thing, as the conceptual storage required for it is unbounded
May be slow in simulation if the number of elements is large
Never UnDefined but defaults to empty

Can be put in a (transient) Record but will it be frozen? (FIXME HOW TO DEAL WITH THIS)

Tests:
    * create empty
    * frozen entry class
    * state/len
    * create from iterable
    * state/iterate
    * state/index
    * state/pop
    * state/replace
    * state/insert
    * state/append
    * state/next
    * liquid entry class
    * state: more than one change in same rule (get current from invocation)
    * trans sanity check with no modifications

FIXME:
    * trans/pop
    * trans/replace
    * trans/insert
    * trans/append
'''

from purple import FrozenRecord, Record, Integer, Tuple
import cli


class Entry(FrozenRecord):
    a: Integer[4]
    b: Integer[5]
    c: Integer[6]


class Top1(cli.Test.Top):
    tt: Tuple[Entry]
    x: Integer[10]

def the_test(top, entry_cls, msg):
    print('starting', msg)
    yield

    assert len(top.tt) == 0
    yield

    top.tt = (entry_cls(a = 0), entry_cls(b = 2))
    yield

    assert len(top.tt) == 2
    assert top.tt[0].a == 0
    assert top.tt[1].b == 2
    yield

    top.tt = (entry_cls(a = 0, b = 1, c = i) for i in range(6))
    yield

    for e in top.tt:
        assert (e.a, e.b, e.c) == (0, 1, top.tt.index(e))
    yield

    assert top.tt.pop(2) == entry_cls(a = 0, b = 1, c = 2)
    yield

    assert len(top.tt) == 5
    assert top.tt[0] == entry_cls(a = 0, b = 1, c = 0)
    assert top.tt[1] == entry_cls(a = 0, b = 1, c = 1)
    assert top.tt[2] == entry_cls(a = 0, b = 1, c = 3)
    assert top.tt[3] == entry_cls(a = 0, b = 1, c = 4)
    assert top.tt[4] == entry_cls(a = 0, b = 1, c = 5)
    yield

    assert top.tt.pop(0) == entry_cls(a = 0, b = 1, c = 0)
    yield

    assert len(top.tt) == 4
    assert top.tt[0] == entry_cls(a = 0, b = 1, c = 1)
    assert top.tt[1] == entry_cls(a = 0, b = 1, c = 3)
    assert top.tt[2] == entry_cls(a = 0, b = 1, c = 4)
    assert top.tt[3] == entry_cls(a = 0, b = 1, c = 5)
    yield

    assert top.tt.pop(3) == entry_cls(a = 0, b = 1, c = 5)
    yield

    assert len(top.tt) == 3
    assert top.tt[0] == entry_cls(a = 0, b = 1, c = 1)
    assert top.tt[1] == entry_cls(a = 0, b = 1, c = 3)
    assert top.tt[2] == entry_cls(a = 0, b = 1, c = 4)
    yield

    assert len(top.tt) == 3
    assert top.tt.replace(1, entry_cls(a = 2, b = 0, c = 3)) == entry_cls(a = 0, b = 1, c = 3)
    yield

    top.tt.insert(0, entry_cls(a = 1, b = 1, c = 1))
    yield

    assert len(top.tt) == 4
    assert top.tt[0] == entry_cls(a = 1, b = 1, c = 1)
    assert top.tt[1] == entry_cls(a = 0, b = 1, c = 1)
    assert top.tt[2] == entry_cls(a = 2, b = 0, c = 3)
    assert top.tt[3] == entry_cls(a = 0, b = 1, c = 4)
    yield

    top.tt.append(entry_cls(a = 2, b = 2, c = 2))
    yield

    assert len(top.tt) == 5
    assert top.tt[0] == entry_cls(a = 1, b = 1, c = 1)
    assert top.tt[1] == entry_cls(a = 0, b = 1, c = 1)
    assert top.tt[2] == entry_cls(a = 2, b = 0, c = 3)
    assert top.tt[3] == entry_cls(a = 0, b = 1, c = 4)
    assert top.tt[4] == entry_cls(a = 2, b = 2, c = 2)
    assert 3 == next(i for i,e in enumerate(top.tt) if e.c == 4)
    assert 2 == next(i for i,e in enumerate(top.tt) if e.a == 2)
    yield

    print('done', msg)

cli.Test(Top1(), Entry, 'frozen-entry')(the_test)


class Entry2(Record):
    a: Integer[4]
    b: Integer[5]
    c: Integer[6]

class Top2(cli.Test.Top):
    tt: Tuple[Entry2]
    x: Integer[10]

cli.Test(Top2(), Entry2, 'liquid-entry')(the_test)


class Top3(cli.Test.Top):
    tt: Tuple[Entry2] = [Entry2(a = 0, b = 1, c = 2), Entry2(a = 1, b = 2, c = 3)]
    x: Integer[10]

@cli.Test(Top3())
def the_test(top):
    print('testing initial-value in instantiator')
    assert [x.a for x in top.tt] == [0, 1]
    assert [x.b for x in top.tt] == [1, 2]
    assert [x.c for x in top.tt] == [2, 3]
    yield

    print('testing 2 changes to same tuple in same rule')
    top.tt.append(Entry2(a = 3, b = 4, c = 5))
    top.tt.append(Entry2(a = 0, b = 0, c = 0))
    yield

    assert len(top.tt) == 4
    assert [x.a for x in top.tt] == [0, 1, 3, 0]
    assert [x.b for x in top.tt] == [1, 2, 4, 0]
    assert [x.c for x in top.tt] == [2, 3, 5, 0]
    yield

    print('testing 3 changes to same tuple in same rule')
    assert top.tt.pop(1) == Entry2(a = 1, b = 2, c = 3)
    assert top.tt.replace(0, Entry2(a = 2, b = 2, c = 2)) == Entry2(a = 0, b = 1, c = 2)
    top.tt.insert(2, Entry2(a = 3, b = 3, c = 3))
    yield

    assert len(top.tt) == 4
    assert [x.a for x in top.tt] == [2, 3, 3, 0]
    assert [x.b for x in top.tt] == [2, 4, 3, 0]
    assert [x.c for x in top.tt] == [2, 5, 3, 0]
    yield

    print('testing 2 pops from same tuple in same rule')
    assert top.tt.pop(0) == Entry2(a = 2, b = 2, c = 2)
    assert top.tt.pop(2) == Entry2(a = 0, b = 0, c = 0)
    yield

    assert len(top.tt) == 2
    assert [x.a for x in top.tt] == [3, 3]
    assert [x.b for x in top.tt] == [4, 3]
    assert [x.c for x in top.tt] == [5, 3]
    yield


class Trans(Record):
    tt: Tuple[Entry2] = [Entry2(a = 0, b = 1, c = 2), Entry2(a = 1, b = 2, c = 3)]
    x: Integer[10]

t1 = Trans()
t2 = Trans(tt = [Entry2(a = 1), Entry2(a = 2), Entry2(a = 3)])

assert t1 != t2
assert [e.a for e in t1.tt] == [0, 1]
assert [e.a for e in t2.tt] == [1, 2, 3]
