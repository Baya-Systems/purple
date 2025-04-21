'''
MIT Licence: Copyright (c) 2025 Baya Systems <https://bayasystems.com>

Purple Tests
======================

Multiple related Ports in in/out directions
'''

import enum
import random
from purple import Interface, Integer, Record, Port, ReversePort, Enumeration, Model, Boolean
import cli


class AXI(Interface):
    Burst = enum.Enum('AXI.Burst', dict(Fixed = 0, Incr = 1, Wrap = 2))
    Resp = enum.Enum('AXI.Resp', dict(Okay = 0, ExOkay = 1, DecErr = 2, SlvErr = 3))

    class AR(Record):
        _dp_stringifiers = dict(addr = hex, id = hex, burst = (lambda e: e.name))
        addr: Integer[...]
        length: Integer[...]
        burst: Enumeration[Burst]
        id: Integer[...]

    class R(Record):
        data: Integer[...]
        last: Boolean
        resp: Enumeration[Resp]
        id: Integer[...]

    class AW(Record):
        addr: Integer[...]
        length: Integer[...]
        burst: Enumeration[Burst]
        id: Integer[...]

    class W(Record):
        _dp_default_stringifier = hex
        data: Integer[...]
        last: Boolean
        strb: Integer[...]

    class B(Record):
        _dp_default_stringifier = hex
        _dp_stringifiers = dict(resp = (lambda e: f'{e.name}({e.value})'))
        resp: Enumeration[Resp]
        id: Integer[...]

    ar: Port[AR]
    r: ReversePort[R]

    aw: Port[AW]
    w: Port[W]
    b: ReversePort[B]


class Initiator(Model):
    _dp_stringifiers = dict(last_resp = (lambda e: f'{e.name}({e.value})'))

    axi_interface: AXI[_.r >> read_resp_handler, _.b >> write_resp_handler]
    last_rd_data: Integer[...]
    last_resp: Enumeration[AXI.Resp]

    def read_resp_handler(self, r: AXI.R):
        self.print('got a read response', r)
        self.last_resp = r.resp
        self.last_rd_data = r.data

    def write_resp_handler(self, b: AXI.B):
        self.print('got a write response', b)
        self.last_resp = b.resp


class Target(Model):
    axi_interface: AXI[_.ar >> read_handler, _.aw >> write_handler, _.w >> write_data_handler]
    last_wr_data: Integer[...]
    last_addr: Integer[...]

    def read_handler(self, ar: AXI.AR):
        self.print('got a read', ar)
        self.last_addr = ar.addr

    def write_handler(self, aw: AXI.AW):
        self.print('got a write', aw)
        self.last_addr = aw.addr

    def write_data_handler(self, w: AXI.W):
        self.print('got a write data', w)
        self.last_wr_data = w.data


class System(cli.Test.Top):
    initiator: Initiator
    target: Target[_.axi_interface << initiator.axi_interface]


@cli.Test(System())
def the_test(top):
    print('running test')
    yield

    print('some random reads')
    for _ in range(5):
        rd_req = AXI.AR(
            addr = random.randrange(100),
            length = random.randrange(8),
            burst = AXI.Burst.Incr,
            id = 17,
        )
        top.initiator.axi_interface.ar = rd_req
        yield

        assert top.target.last_addr == rd_req.addr
        yield

        for d in range(1 + rd_req.length):
            rd_resp = AXI.R(
                data = random.randrange(64),
                last = 1 if d == rd_req.length else 0,
                resp = AXI.Resp.Okay if random.random() < 0.8 else AXI.Resp.SlvErr,
                id = 17,
            )
            top.target.axi_interface.r = rd_resp
            yield

            assert top.initiator.last_rd_data == rd_resp.data
            assert top.initiator.last_resp == rd_resp.resp
            yield

    print('some random writes')
    for _ in range(5):
        wr_req = AXI.AW(
            addr = random.randrange(100),
            length = random.randrange(8),
            burst = AXI.Burst.Incr,
            id = 25,
        )
        top.initiator.axi_interface.aw = wr_req
        yield

        assert top.target.last_addr == wr_req.addr
        yield

        for d in range(1 + wr_req.length):
            wr_data = AXI.W(
                data = random.randrange(64),
                last = 1 if d == wr_req.length else 0,
                strb = 0xf,
            )
            top.initiator.axi_interface.w = wr_data
            yield

            assert top.target.last_wr_data == wr_data.data
            yield

        wr_resp = AXI.B(
            resp = AXI.Resp.Okay if random.random() < 0.5 else AXI.Resp.SlvErr,
            id = 25,
        )
        top.target.axi_interface.b = wr_resp
        yield

        assert top.initiator.last_resp == wr_resp.resp
        yield

    print('print entire system state')
    print(top)

    print('print entire system state nicely')
    print(top._dp_hierarchical_str())
