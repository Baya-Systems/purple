'''
MIT Licence: Copyright (c) 2025 Baya Systems <https://bayasystems.com>

Purple Tests
======================

Frozen-Record testing

Tests:
    * create a frozen-record with Leaf entries
    * unable to modify it
    * freeze a normal record
    * frozen record with record entries
    * freeze a normal record (hierarchical)
    * put a frozen inside a normal record

FIXME:
    * frozen inside transient union (use model?)
'''

from purple import Record, FrozenRecord, Integer, Enumeration
import cli
import enum


MyE = enum.Enum('my-enum', 'a b c d')


print('with leaves')

class IceBranch(FrozenRecord):
    a: Integer[10]
    b: Integer[15]
    c: Enumeration[MyE]

bf = IceBranch(a = 6, b = 7, c = MyE.d)
assert bf.b == 7
with cli.TestException(False, 'change leaf in frozen'):
    bf.c = MyE.a
with cli.TestException(False, 'update frozen'):
    bf.update(a = 4)


class Branch(Record):
    a: Integer[10]
    b: Integer[15]
    c: Enumeration[MyE]

bw = Branch(a = 6, b = 7, c = MyE.d)
assert bw.b == 7
with cli.TestException(True, 'change leaf in liquid'):
    bw.c = MyE.a
    assert bw.c is MyE.a
with cli.TestException(True, 'update liquid'):
    bw.update(a = 4)
    assert bw.a == 4


print('freeze a liquid leaf-record')

bf2 = bw.freeze()
assert bf2.b == 7
with cli.TestException(False, 'change leaf in frozen'):
    bf2.c = MyE.a
with cli.TestException(False, 'update frozen'):
    bf2.update(a = 4)

assert bf2 == IceBranch(a = 4, b = 7, c = MyE.a)
assert bf2 == bw


print('record in frozen record')

class Sub(Record):
    a: Enumeration[MyE]

class IceMain(FrozenRecord):
    x: Sub
    y: Integer[10]

m = IceMain(x = dict(a = MyE.b), y = 5)
n = IceMain(x = Sub(a = MyE.c), y = 5)
assert m != n

for mn in m, n:
    with cli.TestException(False, 'update sub-element'):
        mn.x.a = MyE.c


print('record in record')

class Sub(Record):
    a: Enumeration[MyE]

class Main(Record):
    x: Sub
    y: Integer[10]

m = Main(x = dict(a = MyE.b), y = 5)
n = Main(x = Sub(a = MyE.c), y = 5)
assert m != n

for mn in m, n:
    with cli.TestException(True, 'update record sub-element'):
        mn.x.a = MyE.c

    mno = mn.freeze()
    with cli.TestException(False, 'update frozen record sub-element'):
        mno.x.a = MyE.c


print('frozen in liquid')

class IceSub(FrozenRecord):
    a: Enumeration[MyE]

class Main(Record):
    x: IceSub
    y: Integer[10]

m = Main(x = dict(a = MyE.b), y = 5)
n = Main(x = IceSub(a = MyE.c), y = 5)
assert m != n

for mn in m, n:
    with cli.TestException(False, 'update frozen sub-element'):
        mn.x.a = MyE.c
        print('REALLY')
    mn.y = 6

    mno = mn.freeze()
    with cli.TestException(False, 'update frozen sub-element after freezing'):
        mno.x.a = MyE.c
