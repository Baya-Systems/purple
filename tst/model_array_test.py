'''
MIT Licence: Copyright (c) 2025 Baya Systems <https://bayasystems.com>

Purple Tests
======================

Array test for Model subclass

* array with rules
* array with ports
* hierarchical array with ports
'''

from purple import Model, Port, Integer, ArrayIndex, AddToState
import cli
import random


print('array of models with rules')

class Sub(Model):
    a: Integer[5] = 0
    b: ArrayIndex
    rules: [incr]

    def incr(self):
        self.a = (self.a + 1) % 5

class Top(Model):
    x: 4 * Sub

t = Top()
r = list((i, next(t.find_rule(component = t.x[i]))) for i in range(4))
for _ in range(40):
    index, rule = random.choice(r)
    expected = t.x[index].a + 1
    rule.invoke()
    assert expected % 5 == t.x[index].a
    assert t.x[index].b == index

print(list(xi.a for xi in t.x))


print('with ports')

class Sub2(Model):
    a: Integer[5] = 0
    p_out: Port[Integer[5]]
    p_in: Port[Integer[5]] >> add_up

    def add_up(self, v):
        self.a = (self.a + v) % 5

def the_test(top):
    print('testing', type(top).__name__, top.__doc__)
    yield

    for _ in range(40):
        v = random.randrange(5)
        src = random.randrange(3)
        dst = src + 1
        expected = top.x[dst].a + v
        top.x[src].p_out = v
        yield
        assert top.x[dst].a == expected % 5

    print(list(xi.a for xi in top.x))


class TopA(cli.Test.Top):
    'manual binding'
    x: 4 * Sub2
    bind0: x._0.p_out >> x._1.p_in
    bind1: x._1.p_out >> x._2.p_in
    bind2: x._2.p_out >> x._3.p_in

cli.Test(TopA())(the_test)


class TopB(cli.Test.Top):
    'index-based binding'
    x: 4 * Sub2
    for i in range(3):
        class Binder(AddToState(i = i)):
            bindx: TopB.x[i].p_out >> TopB.x[i + 1].p_in

cli.Test(TopB())(the_test)


class TopC(cli.Test.Top):
    'array-binding'
    x: 4 * Sub2[ _[:3].p_out >> _[1:].p_in ]

cli.Test(TopC())(the_test)


print('with arrays in arrays')

class Second(Model):
    a: Integer[5] = 0
    p_out: Port[Integer[5]]
    p_in: Port[Integer[5]] >> add_up

    def add_up(self, v):
        self.a = (self.a + v) % 5

class First(Model):
    chain: 4 * Second[ _[:3].p_out >> _[1:].p_in ]
    p_out: Port[Integer[5]] >> chain[0].p_in


class Zeroth(cli.Test.Top):
    stuff: 3 * First

@cli.Test(Zeroth())
def the_test(zeroth):
    print('test array of array')
    yield

    for _ in range(40):
        first = zeroth.stuff[random.randrange(3)]
        v = random.randrange(5)
        src = random.randrange(-1, 3)
        src_m = first if src < 0 else first.chain[src]
        dst_m = first.chain[src + 1]
        expected = dst_m.a + v
        src_m.p_out = v
        yield
        assert dst_m.a == expected % 5

    for c in zeroth.stuff:
        print(list(xi.a for xi in c.chain))
