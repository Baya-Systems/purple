'''
MIT Licence: Copyright (c) 2025 Baya Systems <https://bayasystems.com>

Purple implementation
======================

Purple port

First version
    Derived from Model
    No pull-semantic FIFO-based
    No pull or push with overwriteable storage
    No direction (bi-directional)

FIXME Future features (none tested, some may be implemented)
    Registered_Output port type for clocked sims
    Port class naming
    Port-to-port binding at same level, eg
        port_a: Port[T] >> port_b
        port_a: Port[T] >> component_b.port_b
        where port_b is already declared
    Binding after declaration (not in __getitem__ or direct bind to/from port)
    Modifying bindings in subclasses
    Initial values
    Input and output check on bind
    Hierarchical ports
    Fan-in, fan-out
    Wrappers for FIFO, pull with state, push with state, etc
'''

from . import common, model, parameterise, state


class PortBase(model.Model):
    pass


@parameterise.Generic
def Port(payload_type):
    return make_port_class(payload_type, PortBase)


def make_port_class(payload_type, base_class):
    class BasicPort(base_class):
        _dp_port_payload_type = payload_type

        @classmethod
        def _dp_instance_checkattr(cls, self, name = []):
            # called when port is read from a rule
            return super()._dp_instance_checkattr(self._dp_port_get_current(), self.name)

        @classmethod
        def _dp_instance_setattr_leaf_changes(cls, owner, name, self, value):
            # called when the port is written to by a rule
            self._dp_port_set_current(value)
            return ()

        def _dp_port_get_current(self):
            bound_method = getattr(self, '_dp_port_in_method', None)
            if bound_method is None:
                raise common.UnBoundPort(f'Missing binding for input to {".".join(self.name)}')
            return bound_method()

        def _dp_port_set_current(self, value):
            bound_method = getattr(self, '_dp_port_out_method', None)
            if bound_method is None:
                raise common.UnBoundPort(f'Missing binding for output of {".".join(self.name)}')
            return bound_method(value)

        @classmethod
        def _dp_elaborate(cls, name, top_component, instantiating_component, hierarchical_name, initial_value):
            ''' convert bindings to actual instances

            binding of remote port may be done as lhs or as rhs but not both
            binding may be captured in instantiating component or something higher in the hierarchy,
            even up to the top
            '''
            leaf_state = super()._dp_elaborate(
                name, top_component, instantiating_component, hierarchical_name, initial_value)
            self = instantiating_component._dp_raw_getattr(name)

            # iterate from top component towards this port through the hierarchy
            component = top_component
            port_name = self.name[1:]
            while component is not self:
                for b in component._dp_bindings:
                    if b.lhs.name == port_name:
                        self._dp_port_bind_instance(component, b.rhs.name, b.left2right)
                    elif b.rhs.name == port_name:
                        self._dp_port_bind_instance(component, b.lhs.name, not b.left2right)
                component = component._dp_raw_getattr(port_name[0])
                port_name = port_name[1:]

            return leaf_state

        def _dp_port_bind_instance(self, owner, target_name, out_not_in):
            ''' port may be bound to
                    push method or push remote port
                    and/or
                    pull method or pull remote port

                remote port may not have been elaborated before this port: the later-instantiated one will succeed
                requires same BasicPort type, which implictly tests for matching payload types
            '''
            target = owner
            while target_name:
                try:
                    n0 = target_name[0]
                    if n0.isdigit():
                        target = target[int(n0)]
                    else:
                        target = target._dp_raw_getattr(n0)
                    target_name = target_name[1:]
                except (AttributeError, IndexError):
                    return

            if out_not_in:
                if isinstance(target, BasicPort):
                    # if not a port, target will be a bound method
                    target._dp_raw_setattr('_dp_port_in_method', self._dp_port_get_current)
                    target = target._dp_port_set_current
                self._dp_raw_setattr('_dp_port_out_method', target)
            else:
                if isinstance(target, BasicPort):
                    # if not a port, target will be a bound method
                    target._dp_raw_setattr('_dp_port_out_method', self._dp_port_set_current)
                    target = target._dp_port_get_current
                self._dp_raw_setattr('_dp_port_in_method', target)

        @classmethod
        def _dp_on_instantiation(cls, owner_class, name_in_owner):
            'FIXME this should look for the binding(s) and verify types match'

    return BasicPort


@parameterise.Generic
def FIFO_Input_Port(payload_type):
    # FIXME currrently limited to depth = 1; probably want a FIFO component to exist for more than 1
    port_base_class = Port[payload_type]

    class FIFO_Input_Port_FIXME(port_base_class):
        current: payload_type
        valid: state.Boolean = False

        # FIXME should give a declaration-time error if bound to an output Port or handler

        def _dp_port_get_current(self):
            self.guard(self.valid)
            self.valid = False
            return self.current

        def _dp_port_set_current(self, value):
            self.guard(not self.valid)
            self.valid = True
            self.current = value

    return FIFO_Input_Port_FIXME


@parameterise.Generic
def Registered_Output_Port(payload_type, initial_value = common.UniqueObject):
    # typically for clock-based designs
    port_base_class = Port[payload_type]

    class Base(port_base_class):
        def _dp_port_get_current(self):
            return self.current

        def _dp_port_set_current(self, value):
            self.current = value

    # cannot pass UniqueObject explicitly; it is used by Metaclass to detect special cases
    if initial_value is common.UniqueObject:
        class Registered_Output_Port_FIXME(Base):
            current: payload_type
    else:
        class Registered_Output_Port_FIXME(Base):
            current: payload_type = initial_value

    return Registered_Output_Port_FIXME
