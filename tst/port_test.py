'''
MIT Licence: Copyright (c) 2025 Baya Systems <https://bayasystems.com>

Purple Tests
======================

Initial test for ports
'''

from purple import Model, Record, Integer, Port, FIFO_Input_Port, ArrayIndex, HandlerArray, AddToState
import cli
import random


print('Basic push port')


class Producer(Model):
    port_out: Port[Integer[10]]


class Consumer(Model):
    last_value: Integer[10]
    port_in: Port[Integer[10]] >> port_in_handler

    def port_in_handler(self, v):
        self.last_value = v


class Top(cli.Test.Top):
    p: Producer
    c: Consumer[_.port_in << p.port_out]


@cli.Test(Top())
def the_test(top):
    for v in (1, 5, 7, 2, 4):
        top.p.port_out = v
        yield
        assert top.c.last_value == v
        yield


print("Basic pull port")


class Producer(Model):
    next_value: Integer[10]

    def port_out_handler(self):
        return self.next_value

    port_out: Port[Integer[10]] << port_out_handler


class Consumer(Model):
    port_in: Port[Integer[10]]


class Top(cli.Test.Top):
    c: Consumer
    p: Producer[_.port_out >> c.port_in]


@cli.Test(Top())
def the_test(top):
    for v in (1, 5, 7, 2, 4):
        top.p.next_value = v
        yield
        assert top.c.port_in == v
        yield


print("FIFO push (input) port")


class Producer(Model):
    port_out: Port[Integer[10]]


class Consumer(Model):
    port_in: FIFO_Input_Port[Integer[10]]


class Top(cli.Test.Top):
    p: Producer
    c: Consumer[_.port_in << p.port_out]


@cli.Test(Top())
def the_test(top):
    for v in (1, 5, 7, 2, 4):
        top.p.port_out = v
        yield
        assert top.c.port_in == v
        yield

    # guard on write-before-read
    for v in (1, 5, 7, 2, 4):
        top.p.port_out = v
        yield
        top.p.port_out = 6
        assert False, "rule invocation should have stopped on write"
        yield
        assert top.c.port_in == v
        yield

    # guard on read-twice
    for v in (1, 5, 7, 2, 4):
        top.p.port_out = v
        yield
        assert top.c.port_in == v
        yield
        a = top.c.port_in
        assert False, f'rule invocation should have stopped on read {a}'
        yield


print("Multiple bindings and array bindings")

num_targets = 6

class Request(Record):
    address: Integer[0, ...]

class Response(Record):
    source: Integer[0, ...]
    data: Integer[0, ...]


class Initiator(Model):
    last_resp: Response
    req_port: Port[Request]
    resp_port: Port[Response] >> resp_handler

    def resp_handler(self, resp):
        self.print(f'INIT: resp({resp.data}, {resp.source})')
        self.last_resp = resp


class Target(Model):
    node_id: ArrayIndex
    req_port: Port[Request] >> req_handler
    resp_port: Port[Response]

    def req_handler(self, req):
        print('FOUND REQ TAR', req.address, self.node_id)
        self.print(f'TGT_{self.node_id}: req({req.address})')
        assert req.address % num_targets == self.node_id
        self.resp_port = Response(data = req.address + self.node_id, source = self.node_id)


class IBridge(Model):
    # bridge has no function, just adds bindings
    req_port: Port[Request] >> req_handler
    resp_port: Port[Response]
    req_transport: Port[Request]
    resp_transport: Port[Response] >> resp_handler

    def req_handler(self, req):
        print('FOUND REQ IB', req.address)
        self.req_transport = req

    def resp_handler(self, resp):
        self.resp_port = resp


print('fabric')
class Fabric(Model):
    # initiator interface, routed to/from bridge
    initiator_to_bridge: Port[Request] >> req_from_initiator
    initiator_from_bridge: Port[Response]

    # bridge interface (initiator side)
    bridge_from_initiator: Port[Request]
    bridge_to_initiator: Port[Response] >> resp_to_initiator

    # bridge interface (target side)
    bridge_to_targets: Port[Request] >> req_from_bridge
    bridge_from_targets: Port[Response]

    # target interface
    targets_from_bridge: num_targets * Port[Request]
    targets_to_bridge: (num_targets * Port[Response])[ _[:] >> resp_to_bridge[:] ]

    def req_from_initiator(self, req):
        print('FOUND REQ FAB', req.address)
        self.bridge_from_initiator = req

    def resp_to_initiator(self, resp):
        self.initiator_from_bridge = resp

    def req_from_bridge(self, req):
        self.targets_from_bridge[req.address % num_targets] = req

    @HandlerArray
    def resp_to_bridge(self, index, resp):
        print('FOUND RESP FAB', index)
        assert index == resp.source
        self.bridge_from_targets = resp

print('top-level')
class MuchBinding(cli.Test.Top):
    initiator: Initiator
    ibridge: IBridge
    targets: num_targets * Target

    fabric: Fabric[
        _.initiator_to_bridge << initiator.req_port,
        _.bridge_from_initiator >> ibridge.req_port,
        _.bridge_to_targets << ibridge.req_transport,
        _.bridge_from_targets >> ibridge.resp_transport,
        _.bridge_to_initiator << ibridge.resp_port,
        _.initiator_from_bridge >> initiator.resp_port,
        _.targets_from_bridge[:] >> targets[:].req_port,
        _.targets_to_bridge[:] << targets[:].resp_port,
    ]


@cli.Test(MuchBinding())
def the_test(top):
    print('testing to see if all the bindings worked')
    yield

    for x in range(20):
        addr = random.randrange(100)
        top.initiator.req_port = Request(address = addr)
        yield

        t = addr % num_targets
        assert top.initiator.last_resp.data == addr + t
        yield
