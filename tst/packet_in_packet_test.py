'''
MIT Licence: Copyright (c) 2025 Baya Systems <https://bayasystems.com>

Purple Tests
======================

This file is a test for Unions with message classes supporting different payloads

Simulation of encapsulation of WXYZ/DTF/Virtual-wire in ABC

WXYZ
    message passing protocol with 32-bit words formed into packets
    packets start with source/destination IDs and opcode, then a "SAI" word then any number of data words

DTF-Data:
    protocol with 25 header bits and 64 data bits in a packet

DTF-Control:
    protocol with 2 bits in a packet

Virtual-wire:
    protocol with 64 virtual wire data values and a few bits indicating which set of wires

ABC:
    link protocol where a 64-bit header is sent, optionally followed by a 64-bit data word
    presence of data word is encoded in header opcode
    this simulation uses ABC to move WXYZ, DTF and V-wire
    there is space in the ABC header to hide some bits, so DTF-control does not need ABC.data

Note that this simulation heavily uses random numbers, to reduce the number of
rules and simplify the coding.

FIXME
- this doesn't work for purple metaclass, but does work for normal classes
  there is a simple workaround
  do we need to iterate up through all levels of scope rather than doing one
  level then jumping to locals then globals?
    def A:
        class C:
            pass
        class E:
            class F:
                print('F', C)  ## can see C
        class G:
            CC: C
            class H(Record):
                print('H', C, CC)  ## cannot see C, but can see CC
        class J(Record):
            print('J', C)      ## can see C
'''

from purple import (
    Record,
    Boolean,
    Enumeration,
    BitVector,
    FieldLocation,
    Model,
    Port,
    Integer,
    AtomicRuleSimulator,
    Tuple,
)

import random
import enum
from cli import args


print('Declaring pure-functional WXYZ messages')

class WXYZ:
    Opcode = enum.Enum('WXYZ_Opcode', dict(Rd = 0, Wr = 1, Msg = 0x57))
    SAI = enum.Enum('WXYZ_SAI', dict(Trusted = 0, OS_W = 0x99, BIOS = 0x33))

    class Data32(Record):
        data: BitVector[32]

    class Header(Record):
        header: BitVector[8]
        opcode: Enumeration[Opcode]
        source: BitVector[8]
        destination: BitVector[8]

    class ID_MSBs(Record):
        source: BitVector[8]
        destination: BitVector[8]

    class SAI_Value(Record):
        sai: Enumeration[SAI]

    Word32 = Data32 | Header | ID_MSBs | SAI_Value

    class Flit32(Record):
        eom: Boolean
        posted_not_nonposted: Boolean
        word: Word32

    class Bit_Accurate_Flit32(Record):
        eom: Boolean
        posted_not_nonposted: Boolean
        word: BitVector[32]


print('Declaring pure-functional ABC messages')

class ABC:
    Opcode = enum.Enum('ABC_Opcode', dict(WithData = 0x15, HeaderOnly = 0x14))
    ID = enum.Enum('ABC_ID', dict(source = 4, destination = 6))

    class DTF_Data(Record):
        header: BitVector[25]
        data: BitVector[64]

    class DTF_Control(Record):
        active: Boolean
        sync: Boolean

    class Virtual_Wire(Record):
        wire_set: BitVector[2]
        toggles: BitVector[64]

    class WXYZ(Record):
        eom: Boolean
        data_msbs_present: Boolean
        time_alert: Boolean
        data_lsbs: WXYZ.Word32
        data_msbs: WXYZ.Word32

    class Bit_Accurate_WXYZ(Record):
        eom: Boolean
        data_msbs_present: Boolean
        time_alert: Boolean
        data_lsbs: BitVector[32]
        data_msbs: BitVector[32]

    class Credit_Return(Record):
        pass

    Payload = DTF_Data | DTF_Control | Virtual_Wire | WXYZ | Credit_Return

    class Packet(Record):
        src: Enumeration[ID]
        dst: Enumeration[ID]
        opcode: Enumeration[Opcode]
        channel: BitVector[4]
        credit: BitVector[4]
        credit_channel: BitVector[4]
        payload: Payload

    class Bit_Accurate_Packet(Record):
        header: BitVector[64]
        data: BitVector[64]


print('Declaring pure-functional system hierarchy')

class WXYZ_Source_and_Sink(Model):
    ''' creates WXYZ packets and sends them; checks same ones are received

    each WXYZ packet is a sequence of 32-but words plus a couple of single-bit qualifiers
    the words in the packet follow this (simplified) sequence:
        1. MSBs of source and destination
        2. opcode, other header information and LSBs of source/destination
        3. security (SAI) information
        4. any number of data words

    each source/sink does exclusively posted or exclusively non-posted packets

    code is structured a little strangely in order to simplify derivation of bit-accurate version
    '''
    StateEnum = enum.Enum('WXYZmessage', 'MSBs Hdr SAI Data')
    posted_not_nonposted: Boolean

    to_packer: Port[WXYZ.Flit32]
    source_msg_state: Enumeration[StateEnum] = StateEnum.MSBs
    flits_outstanding: Tuple[WXYZ.Flit32]

    from_unpacker: Port[WXYZ.Flit32] >> from_unpacker_handler
    sink_msg_state: Enumeration[StateEnum] = StateEnum.MSBs
    msg_count: Integer[...] = 0

    rules: [make_flit]

    def make_flit(self):
        if self.source_msg_state is self.StateEnum.MSBs:
            word_type = 'id_msbs'
            word = WXYZ.ID_MSBs(
                source = random.randrange(6),
                destination = random.randrange(6),
            )
            eom = False
            self.source_msg_state = self.StateEnum.Hdr

        elif self.source_msg_state is self.StateEnum.Hdr:
            word_type = 'header'
            word = WXYZ.Header(
                header = random.randrange(4),
                opcode = random.choice(list(WXYZ.Opcode)),
                source = random.randrange(6),
                destination = random.randrange(6),
            )
            eom = False
            self.source_msg_state = self.StateEnum.SAI

        elif self.source_msg_state is self.StateEnum.SAI:
            word_type = 'sai'
            word = WXYZ.SAI_Value(
                sai = random.choice(list(WXYZ.SAI)),
            )
            eom = False
            self.source_msg_state = self.StateEnum.Data

        else:
            word_type = 'data32'
            word = WXYZ.Data32(
                data = random.randrange(16),
            )
            eom = random.random() < 0.4
            self.source_msg_state = self.StateEnum.MSBs if eom else self.StateEnum.Data

        pure_functional_flit = WXYZ.Flit32(
            eom = eom,
            posted_not_nonposted = self.posted_not_nonposted,
            word = word,
        )
        flit_to_send = self.make_flit_to_send(word_type, pure_functional_flit)
        self.flits_outstanding.append(flit_to_send)
        self.to_packer = flit_to_send

    def make_flit_to_send(self, word_typename, pure_functional_flit):
        # overridden in bit-accurate version
        return pure_functional_flit

    def from_unpacker_handler(self, flit):
        assert self.posted_not_nonposted == flit.posted_not_nonposted
        assert flit == self.flits_outstanding.pop()
        pnnp = 'PC' if flit.posted_not_nonposted else 'NP'

        if self.sink_msg_state == self.StateEnum.MSBs:
            word = self.parse_word(WXYZ.ID_MSBs, 'id_msbs', flit.word)
            self.print(pnnp, 'WXYZ sink ID-MSBs:', word.source, word.destination)
            self.sink_msg_state = self.StateEnum.Hdr

        elif self.sink_msg_state == self.StateEnum.Hdr:
            word = self.parse_word(WXYZ.Header, 'header', flit.word)
            self.print(pnnp, 'WXYZ sink Hdr:', word.source, word.destination, word.opcode, word.header)
            self.sink_msg_state = self.StateEnum.SAI

        elif self.sink_msg_state == self.StateEnum.SAI:
            word = self.parse_word(WXYZ.SAI_Value, 'sai', flit.word)
            self.print(pnnp, 'WXYZ sink SAI:', word.sai)
            self.sink_msg_state = self.StateEnum.Data

        else:
            word = self.parse_word(WXYZ.Data32, 'data32', flit.word)
            self.print(pnnp, 'WXYZ sink Data:', word.data, flit.eom)
            if flit.eom:
                self.sink_msg_state = self.StateEnum.MSBs
                self.msg_count += 1
            else:
                self.sink_msg_state = self.StateEnum.Data

    def parse_word(self, word_type, word_typename, pure_functional_word):
        # overridden in bit-accurate version
        return pure_functional_word


class WXYZ_Packer(Model):
    ''' packs 2 WXYZ 32-bit words together to form the content for a 64-bit ABC packet payload

    does not combine words from different packets: if the first of 2 words has end-of-message
    set, then this is forwarded immediately with an indication that MSBs are empty
    '''
    Type_ToChannel = ABC.WXYZ

    from_source: Port[WXYZ.Flit32] >> from_source_handler
    to_channel: Port[Type_ToChannel]

    stored_lsbs: WXYZ.Word32
    stored_lsbs_valid: Boolean = False

    def from_source_handler(self, flit):
        if self.stored_lsbs_valid:
            self.to_channel = self.Type_ToChannel(
                eom = flit.eom,
                data_msbs_present = True,
                time_alert = random.random() < 0.5,
                data_lsbs = self.stored_lsbs,
                data_msbs = flit.word,
            )
            self.stored_lsbs_valid = False

        elif flit.eom:
            self.to_channel = self.Type_ToChannel(
                eom = True,
                data_msbs_present = False,
                time_alert = random.random() < 0.5,
                data_lsbs = flit.word,
            )

        else:
            self.stored_lsbs = flit.word
            self.stored_lsbs_valid = True


class WXYZ_Unpacker(Model):
    ''' split 64-but ABC packet payload into a pair of WXYZ 32-bit words
    '''
    Type_ToSink = WXYZ.Flit32

    to_sink: Port[Type_ToSink]
    from_channel: Port[ABC.WXYZ] >> from_channel_handler

    posted_not_nonposted: Boolean
    waiting_flit: WXYZ.Flit32
    waiting_flit_valid: Boolean = False

    rules: [send_remainder]

    def send_remainder(self):
        self.guard(self.waiting_flit_valid)
        self.to_sink = self.waiting_flit
        self.waiting_flit_valid = False

    def from_channel_handler(self, payload):
        self.guard(not self.waiting_flit_valid)
        if payload.data_msbs_present:
            self.waiting_flit = self.Type_ToSink(
                eom = payload.eom,
                posted_not_nonposted = self.posted_not_nonposted,
                word = payload.data_msbs,
            )
            self.waiting_flit_valid = True
            eom = False
        else:
            assert payload.eom
            eom = True

        self.to_sink = self.Type_ToSink(
            eom = eom,
            posted_not_nonposted = self.posted_not_nonposted,
            word = payload.data_lsbs,
        )


class DTF_Data_Source_and_Sink(Model):
    ''' create DTF-data packets; check received packets match sent ones
    '''
    to_channel: Port[ABC.DTF_Data]
    from_channel: Port[ABC.DTF_Data] >> from_channel_handler

    msgs_outstanding: Tuple[ABC.DTF_Data]
    msg_count: Integer[...] = 0

    rules: [make_packet]

    def make_packet(self):
        msg = ABC.DTF_Data(
            header = random.randrange(3),
            data = random.randrange(8),
        )
        self.msgs_outstanding.append(msg)
        self.to_channel = msg

    def from_channel_handler(self, packet):
        self.print('DTF Data sink:', packet.header, packet.data)
        self.msg_count += 1
        original = self.msgs_outstanding.pop()
        assert packet == original, f'O: {original}  R: {packet}'


class DTF_Ctrl_Source_and_Sink(Model):
    ''' create DTF-control packets; check received packets match sent ones

    DTF-control packets are only 2-bit and fully contained within a ABC header,
    so do not require a ABC payload
    '''
    to_channel: Port[ABC.DTF_Control]
    from_channel: Port[ABC.DTF_Control] >> from_channel_handler

    msgs_outstanding: Tuple[ABC.DTF_Control]
    msg_count: Integer[...] = 0

    rules: [make_packet]

    def make_packet(self):
        msg = ABC.DTF_Control(
            active = random.choice((True, False)),
            sync = random.choice((True, False)),
        )
        self.msgs_outstanding.append(msg)
        self.to_channel = msg

    def from_channel_handler(self, packet):
        self.print('DTF Control sink:', packet.active, packet.sync)
        self.msg_count += 1
        assert packet == self.msgs_outstanding.pop()


class Virtual_Wire_Source_and_Sink(Model):
    ''' create virtual-wire packets; check received packets match sent ones
    '''
    to_channel: Port[ABC.Virtual_Wire]
    from_channel: Port[ABC.Virtual_Wire] >> from_channel_handler

    msgs_outstanding: Tuple[ABC.Virtual_Wire]
    msg_count: Integer[...] = 0

    rules: [make_packet]

    def make_packet(self):
        msg = ABC.Virtual_Wire(
            wire_set = random.randrange(4),
            toggles = random.getrandbits(12),
        )
        self.msgs_outstanding.append(msg)
        self.to_channel = msg

    def from_channel_handler(self, packet):
        self.print('Virtual Wire sink:', packet.wire_set, packet.toggles)
        self.msg_count += 1
        assert packet == self.msgs_outstanding.pop()


class TX(Model):
    ''' multiplex all packet sources onto a single channel

    normally the protocol would be bi-directional and require credit flow control
    but this model is simplified

    incoming packets (pure-functional model) are encapsulated into ABC packets
    a ABC (sideband) packet always has a 64-bit header and may have a 64-bit data
    the presence of the data word is encoded in the ABC opcode

    this model first captures a packet to send, then sends it in a separate step
    '''
    to_channel: Port[ABC.Packet]
    next_packet: ABC.Packet
    next_packet_valid: Boolean = False

    from_wxyz_pc: Port[ABC.WXYZ]            >> from_wxyz_pc_handler
    from_wxyz_np: Port[ABC.WXYZ]            >> from_wxyz_np_handler
    from_dtf_data: Port[ABC.DTF_Data]       >> from_dtf_data_handler
    from_dtf_ctrl: Port[ABC.DTF_Control]    >> from_dtf_ctrl_handler
    from_vwire: Port[ABC.Virtual_Wire]      >> from_vwire_handler

    rules: [send]

    def set_next_packet(self, opcode, channel, type_name, payload):
        self.guard(not self.next_packet_valid)
        self.next_packet = ABC.Packet(payload = payload, **self.fill_values(opcode, channel))
        self.next_packet_valid = True

    def fill_values(self, opcode, channel):
        return dict(
            src = ABC.ID.source,
            dst = ABC.ID.destination,
            opcode = opcode,
            channel = channel,
            credit = random.randrange(16),
            credit_channel = random.randrange(16),
        )

    def from_wxyz_pc_handler(self, payload):
        self.set_next_packet(ABC.Opcode.WithData, 2, 'wxyz', payload)

    def from_wxyz_np_handler(self, payload):
        self.set_next_packet(ABC.Opcode.WithData, 3, 'wxyz', payload)

    def from_dtf_data_handler(self, payload):
        self.set_next_packet(ABC.Opcode.WithData, 6, 'dtf_data', payload)

    def from_dtf_ctrl_handler(self, payload):
        self.set_next_packet(ABC.Opcode.HeaderOnly, 6, 'dtf_control', payload)

    def from_vwire_handler(self, payload):
        self.set_next_packet(ABC.Opcode.WithData, 4, 'virtual_wire', payload)

    def send(self):
        self.guard(self.next_packet_valid)
        self.to_channel = self.next_packet
        self.next_packet_valid = False


class RX(Model):
    ''' receive ABC sideband packets from the channel, decode their type and send to
    the appropriate sink

    type is obtained from the channel and opcode fields of the ABC header
    '''
    to_wxyz_pc: Port[ABC.WXYZ]
    to_wxyz_np: Port[ABC.WXYZ]
    to_dtf_data: Port[ABC.DTF_Data]
    to_dtf_ctrl: Port[ABC.DTF_Control]
    to_vwire: Port[ABC.Virtual_Wire]
    from_channel: Port[ABC.Packet]          >> from_channel_handler

    def from_channel_handler(self, packet):
        if packet.channel == 2:
            self.to_wxyz_pc = packet.payload
        elif packet.channel == 3:
            self.to_wxyz_np = packet.payload
        elif packet.channel == 4:
            self.to_vwire = packet.payload
        elif packet.channel == 6:
            if packet.opcode is ABC.Opcode.WithData:
                self.to_dtf_data = packet.payload
            else:
                self.to_dtf_ctrl = packet.payload
        else:
            assert False


class Top(Model):
    pc = {'posted_not_nonposted': True}
    np = {'posted_not_nonposted': False}

    wxyz_source_and_sink_pc: WXYZ_Source_and_Sink = pc
    wxyz_packer_pc: WXYZ_Packer[_.from_source << wxyz_source_and_sink_pc.to_packer]
    wxyz_unpacker_pc: WXYZ_Unpacker[_.to_sink >> wxyz_source_and_sink_pc.from_unpacker] = pc

    wxyz_source_and_sink_np: WXYZ_Source_and_Sink = np
    wxyz_packer_np: WXYZ_Packer[_.from_source << wxyz_source_and_sink_np.to_packer]
    wxyz_unpacker_np: WXYZ_Unpacker[_.to_sink >> wxyz_source_and_sink_np.from_unpacker] = np

    dtf_data_source_and_sink: DTF_Data_Source_and_Sink
    dtf_ctrl_source_and_sink: DTF_Ctrl_Source_and_Sink
    vwire_source_and_sink: Virtual_Wire_Source_and_Sink

    tx: TX[
        _.from_wxyz_pc      << wxyz_packer_pc.to_channel,
        _.from_wxyz_np      << wxyz_packer_np.to_channel,
        _.from_dtf_data     << dtf_data_source_and_sink.to_channel,
        _.from_dtf_ctrl     << dtf_ctrl_source_and_sink.to_channel,
        _.from_vwire        << vwire_source_and_sink.to_channel,
    ]

    rx: RX[
        _.to_wxyz_pc        >> wxyz_unpacker_pc.from_channel,
        _.to_wxyz_np        >> wxyz_unpacker_np.from_channel,
        _.to_dtf_data       >> dtf_data_source_and_sink.from_channel,
        _.to_dtf_ctrl       >> dtf_ctrl_source_and_sink.from_channel,
        _.to_vwire          >> vwire_source_and_sink.from_channel,
    ]

    rx.from_channel << tx.to_channel,


print('Pure-functional simulation: elaboration')
system_pure_functional = Top()

print('Pure-functional simulation: check for stationary behaviour')
sim = AtomicRuleSimulator(system = system_pure_functional)
def get_nr_msgs():
   return {
       s:getattr(system_pure_functional, s.replace('_ss', '_source_and_sink')).msg_count
       for s in ('wxyz_ss_pc', 'wxyz_ss_np', 'dtf_data_ss', 'dtf_ctrl_ss', 'vwire_ss')
   }

nr_msgs = get_nr_msgs()
nr_rules = 250 if args.quick else 1000
tolpc = 90 if args.quick else 10
tolerance = 2.0 * (100 - tolpc) / 100, 2.0 * (100 + tolpc) / 100
for _ in range(10):
    print(f'   run {nr_rules} rules and check if within {tolpc}%')
    sim.run(num_invocations = nr_rules, show_print = False)
    new_nr_msgs = get_nr_msgs()
    print('   message counts:', new_nr_msgs)
    if all(n * tolerance[0] < new_nr_msgs[k] < n * tolerance[1] for k,n in nr_msgs.items()):
        break
    nr_msgs = new_nr_msgs
    nr_rules *= 2
else:
    assert False, 'did not converge'



print('Declaring bit-fields for bit-accurate simulation')

class Field:
    ''' define where a field is to be found within a wider BitVector

    can gather/scatter multiple field locations
    so may have multiple FieldLocation objects
    they are ordered LSB to MSB in the unified field and can be in
    any order in the wider BitVector

    the unified field value may be an enum
    '''
    def __init__(self, name, *bitfields, the_enum = None):
        self.name = name
        self.bitfields = tuple(FieldLocation(*b) for b in bitfields)
        self.width = sum(b.width for b in self.bitfields)
        self.enum = the_enum

    def add_to_bitvector(self, bv, value):
        int_value = BitVector[...](value if self.enum is None else value.value)
        lsb = 0
        for bf in self.bitfields:
            bv[bf] = int_value[lsb:]
            lsb += bf.width

    def extract_from_bitvector(self, bv):
        int_value = BitVector[...](0)
        lsb = 0
        for bf in self.bitfields:
            int_value[lsb:] = bv[bf]
            lsb += bf.width
        return int_value if self.enum is None else self.enum(int_value)


wxyz_bitfields = dict(
    data32 = (
        Field('data', (0, 32)),
    ),
    header = (
        Field('header', (24, 8)),
        Field('opcode', (16, 8), the_enum = WXYZ.Opcode),
        Field('source', (0, 8)),
        Field('destination', (8, 8)),
    ),
    id_msbs = (
        Field('source', (0, 8)),
        Field('destination', (8, 8)),
    ),
    sai = (
        Field('sai', (8, 8), the_enum = WXYZ.SAI),
    ),
)

abc_header_bitfields = dict(
    common = (
        Field('src', (30, 3), the_enum = ABC.ID),
        Field('dst', (59, 3), the_enum = ABC.ID),
        Field('opcode', (0, 6), the_enum = ABC.Opcode),
        Field('channel', (6, 4)),
        Field('credit', (40, 4)),
        Field('credit_channel', (44, 4)),
    ),
    dtf_data = (
        Field('header', (48, 10), (12, 15)),
    ),
    dtf_control = (
        Field('active', (10, 1)),
        Field('sync', (11, 1)),
    ),
    virtual_wire = (
        Field('wire_set', (10, 2)),
    ),
    wxyz = (
        Field('eom', (10, 1)),
        Field('data_msbs_present', (11, 1)),
        Field('time_alert', (12, 1)),
    ),
    credit_return = (
    ),
)

abc_payload_bitfields = dict(
    dtf_data = (
        Field('data', (0, 64)),
    ),
    virtual_wire = (
        Field('toggles', (0, 64)),
    ),
    wxyz = (
        Field('data_lsbs', (0, 32)),
        Field('data_msbs', (32, 32)),
    ),
)


print('Declaring models for bit-accurate simulation')

class Bit_Accurate_WXYZ_Source_and_Sink(WXYZ_Source_and_Sink):
    to_packer: Port[WXYZ.Bit_Accurate_Flit32]
    flits_outstanding: Tuple[WXYZ.Bit_Accurate_Flit32]
    from_unpacker: Port[WXYZ.Bit_Accurate_Flit32]

    def make_flit_to_send(self, word_typename, pure_functional_flit):
        pure_functional_word = pure_functional_flit.word

        bv = BitVector[...](0)
        for field in wxyz_bitfields[word_typename]:
            value = getattr(pure_functional_word, field.name)
            field.add_to_bitvector(bv, value)

        return WXYZ.Bit_Accurate_Flit32(
            eom = pure_functional_flit.eom,
            posted_not_nonposted = self.posted_not_nonposted,
            word = bv,
        )

    def parse_word(self, word_type, word_typename, bit_accurate_word):
        return word_type(**{
            f.name:f.extract_from_bitvector(bit_accurate_word)
            for f in wxyz_bitfields[word_typename]
        })


class Bit_Accurate_WXYZ_Packer(WXYZ_Packer):
    Type_ToChannel = ABC.Bit_Accurate_WXYZ
    from_source: Port[WXYZ.Bit_Accurate_Flit32]
    to_channel: Port[Type_ToChannel]
    stored_lsbs: BitVector[32]


class Bit_Accurate_WXYZ_Unpacker(WXYZ_Unpacker):
    Type_ToSink = WXYZ.Bit_Accurate_Flit32
    to_sink: Port[Type_ToSink]
    from_channel: Port[ABC.Bit_Accurate_WXYZ]
    waiting_flit: Type_ToSink


class Bit_Accurate_TX(TX):
    to_channel: Port[ABC.Bit_Accurate_Packet]
    next_packet: ABC.Bit_Accurate_Packet

    from_wxyz_pc: Port[ABC.Bit_Accurate_WXYZ]
    from_wxyz_np: Port[ABC.Bit_Accurate_WXYZ]

    def abc_header(self, opcode, channel, type_name, payload):
        'convert the pure-functional payload to a 64-bit BitVector'
        bv = BitVector[64](0)

        # fields common to all payload types
        values = self.fill_values(opcode, channel)
        for field in abc_header_bitfields['common']:
            field.add_to_bitvector(bv, values[field.name])

        # fields specific to this type of payload
        for field in abc_header_bitfields[type_name]:
            field.add_to_bitvector(bv, getattr(payload, field.name))

        return bv

    def abc_data(self, type_name, payload):
        'convert the pure-functional payload to a 64-bit BitVector'
        bv = BitVector[64](0)
        copy_msbs = getattr(payload, 'data_msbs_present', True)

        for field in abc_payload_bitfields.get(type_name, []):
            if copy_msbs or field.name != 'data_msbs':
                field.add_to_bitvector(bv, getattr(payload, field.name))

        return bv

    def set_next_packet(self, opcode, channel, type_name, payload):
        self.guard(not self.next_packet_valid)
        self.next_packet = ABC.Bit_Accurate_Packet(
            header = self.abc_header(opcode, channel, type_name, payload),
            data = self.abc_data(type_name, payload),
        )
        self.next_packet_valid = True


class Bit_Accurate_RX(RX):
    to_wxyz_pc: Port[ABC.Bit_Accurate_WXYZ]
    to_wxyz_np: Port[ABC.Bit_Accurate_WXYZ]
    from_channel: Port[ABC.Bit_Accurate_Packet]

    def from_channel_handler(self, packet):
        common = self.parse_header(packet.header)
        channel = common['channel']

        if channel == 2:
            specific = self.parse_payload('wxyz', packet)
            self.to_wxyz_pc = ABC.Bit_Accurate_WXYZ(**specific)

        elif channel == 3:
            specific = self.parse_payload('wxyz', packet)
            self.to_wxyz_np = ABC.Bit_Accurate_WXYZ(**specific)

        elif channel == 4:
            specific = self.parse_payload('virtual_wire', packet)
            self.to_vwire = ABC.Virtual_Wire(**specific)

        elif channel == 6:
            if common['opcode'] is ABC.Opcode.WithData:
                specific = self.parse_payload('dtf_data', packet)
                self.to_dtf_data = ABC.DTF_Data(**specific)
            else:
                specific = self.parse_payload('dtf_control', packet)
                self.to_dtf_ctrl = ABC.DTF_Control(**specific)

        else:
            assert False, f'invalid channel {channel}'

    def parse_header(self, header):
        rv = {}
        for field in abc_header_bitfields['common']:
            rv[field.name] = field.extract_from_bitvector(header)
        return rv

    def parse_payload(self, type_name, packet):
        header = packet.header
        data = packet.data
        rv = {}
        for field in abc_header_bitfields[type_name]:
            rv[field.name] = field.extract_from_bitvector(header)
        for field in abc_payload_bitfields.get(type_name, []):
            rv[field.name] = field.extract_from_bitvector(data)
        return rv


class Bit_Accurate_Top(Top):
    wxyz_source_and_sink_pc: Bit_Accurate_WXYZ_Source_and_Sink = Top.pc
    wxyz_packer_pc: Bit_Accurate_WXYZ_Packer
    wxyz_unpacker_pc: Bit_Accurate_WXYZ_Unpacker = Top.pc

    wxyz_source_and_sink_np: Bit_Accurate_WXYZ_Source_and_Sink = Top.np
    wxyz_packer_np: Bit_Accurate_WXYZ_Packer
    wxyz_unpacker_np: Bit_Accurate_WXYZ_Unpacker = Top.np

    tx: Bit_Accurate_TX
    rx: Bit_Accurate_RX


print('Bit-accurate simulation: elaboration')
system_bit_accurate = Bit_Accurate_Top()

print('Pure-functional simulation: check for stationary behaviour')
sim = AtomicRuleSimulator(system = system_bit_accurate)
def get_nr_msgs():
   return {
       s:getattr(system_bit_accurate, s.replace('_ss', '_source_and_sink')).msg_count
       for s in ('wxyz_ss_pc', 'wxyz_ss_np', 'dtf_data_ss', 'dtf_ctrl_ss', 'vwire_ss')
   }

nr_msgs = get_nr_msgs()
nr_rules = 250 if args.quick else 1000
for _ in range(10):
    print(f'   run {nr_rules} rules and check if within {tolpc}%')
    sim.run(num_invocations = nr_rules, show_print = False)
    new_nr_msgs = get_nr_msgs()
    print('   message counts:', new_nr_msgs)
    if all(n * tolerance[0] < new_nr_msgs[k] < n * tolerance[1] for k,n in nr_msgs.items()):
        break
    nr_msgs = new_nr_msgs
    nr_rules *= 2
else:
    assert False, 'did not converge'
