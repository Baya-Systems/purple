'''
MIT Licence: Copyright (c) 2025 Baya Systems <https://bayasystems.com>

Purple implementation
======================

Purple Tuple type


A Tuple is a Leaf state element containing an ordered list of any number of entries

The entries are transient frozen record objects, all the same type
This is a somewhat informal thing, as the conceptual storage required for it is unbounded
May be slow in simulation if the number of elements is large
Never UnDefined but defaults to empty

Can be put in a (transient) Record
'''

from . import common, parameterise, record, leaf, array


class TupleObject(tuple):
    def __new__(cls, owner, name, iterable):
        self = super().__new__(cls, iterable)
        self.owner = owner
        self.name = name
        return self

    def pop(self, index = 0):
        setattr(self.owner, self.name, (*self[:index], *self[index+1:]))
        return self[index]

    def replace(self, index, value):
        setattr(self.owner, self.name, (*self[:index], value, *self[index+1:]))
        return self[index]

    def insert(self, index, value):
        setattr(self.owner, self.name, (*self[:index], value, *self[index:]))

    def append(self, value):
        setattr(self.owner, self.name, (*self, value))


@parameterise.Generic
def Tuple(entry_cls):
    frozen_entry_cls = entry_cls._dp_make_frozen_class()

    class TupleLeafState:
        _dp_class_cache_key = frozen_entry_cls
        param_entry_cls = entry_cls
        param_frozen_entry_cls = frozen_entry_cls
        entry_cls_is_leaf = issubclass(frozen_entry_cls, leaf.Leaf)

        @classmethod
        def _dp_check_and_cast_including_undef(cls, owner, name, value, allow_unsel = True):
            if value is common.UnSelected and allow_unsel:
                return value

            value = () if value is common.UnDefined else value
            fixed_value = []
            for v in value:
                if cls.entry_cls_is_leaf:
                    v_fixed = cls.param_entry_cls._dp_check_and_cast_including_undef(owner, name, v)
                elif isinstance(v, cls.param_frozen_entry_cls):
                    v_fixed = v
                elif isinstance(v, cls.param_entry_cls):
                    v_fixed = v.freeze()
                else:
                    # try to build a frozen value from whatever we have been given
                    # will fail if not a dict and the entry-class is not able to accept it
                    if isinstance(v, dict):
                        v_fixed = cls.param_frozen_entry_cls(**v)
                    else:
                        v_fixed = cls.param_frozen_entry_cls(v)

                fixed_value.append(v_fixed)

            return TupleObject(owner, name, fixed_value)

    cls_name = f'Tuple_{entry_cls.__name__}'
    return leaf.Leaf.subclass(cls_name, TupleLeafState)
