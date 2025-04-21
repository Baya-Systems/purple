''''
MIT Licence: Copyright (c) 2025 Baya Systems <https://bayasystems.com>

Purple implementation
======================

Purple Interface type


An interface is a collection of Ports, which can be bound to a matching interface
with a single declaration.

Interface (defined here) is a base class for interfaces

The actual port directions are not important; each port can be either pull or push,
input or output simply depending on whether bound to another port or a handler
on read-from and write-to.

What's important is that the entire Interface can be bound in one statement, for
which we need to know which ports within it have to have the direction of binding
reversed.
The binding declaration is what happens to normal ports; reversed ports get the
opposite.

It might be possible to mix pull and push ports within an interface but this
is not considered necessary.

FIXME
    support for other types of Port eg FIFO-input, or something defined by user
        ideally the port type is not part of the Interface but can be selected on instantiation
        although this may restrict legality of interface-interface bindings
    check bindings on declaration
        needs a concept of direction - can't bind manager to manager (like Port output-to-output)
'''

from . import model, port, parameterise


class ReversePortBase(model.Model):
    pass

@parameterise.Generic
def ReversePort(payload_type):
    return port.make_port_class(payload_type, ReversePortBase)


class Interface(model.Model):
    @classmethod
    def _dp_elaborate(cls, name, top_component, instantiating_component, hierarchical_name, initial_value):
        ''' convert bindings to actual instances

        the Interface elaboration will bind ports that are directly instantiated within it
        these should not have not been bound by anything else
        '''
        leaf_state = super()._dp_elaborate(
            name, top_component, instantiating_component, hierarchical_name, initial_value)
        self = instantiating_component._dp_raw_getattr(name)

        forward_ports = [
            self._dp_raw_getattr(n) for n,v in cls._dp_state_types.items() if issubclass(v, port.PortBase)]
        reverse_ports = [
            self._dp_raw_getattr(n) for n,v in cls._dp_state_types.items() if issubclass(v, ReversePortBase)]

        # iterate from top component towards this port through the hierarchy
        component = top_component
        intfc_name = self.name[1:]
        while component is not self:
            for b in component._dp_bindings:
                if b.lhs.name == intfc_name:
                    for p in forward_ports:
                        p._dp_port_bind_instance(component, (*b.rhs.name, p.name[-1]), b.left2right)
                    for p in reverse_ports:
                        p._dp_port_bind_instance(component, (*b.rhs.name, p.name[-1]), not b.left2right)
                elif b.rhs.name == intfc_name:
                    for p in forward_ports:
                        p._dp_port_bind_instance(component, (*b.lhs.name, p.name[-1]), not b.left2right)
                    for p in reverse_ports:
                        p._dp_port_bind_instance(component, (*b.lhs.name, p.name[-1]), b.left2right)
            component = component._dp_raw_getattr(intfc_name[0])
            intfc_name = intfc_name[1:]

        return leaf_state

    @classmethod
    def _dp_on_instantiation(cls, owner_class, name_in_owner):
        'FIXME this should look for the binding(s) and verify types match'
