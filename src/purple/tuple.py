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

from . import common, parameterise, record, leaf


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
        param_entry_cls = frozen_entry_cls
        freeze_new_entries = (frozen_entry_cls is not entry_cls)
        entry_cls_is_leaf = issubclass(frozen_entry_cls, leaf.Leaf)

        @classmethod
        def _dp_check_and_cast_including_undef(cls, owner, name, value, allow_unsel = True):
            if value is common.UnSelected and allow_unsel:
                return value
            else:
                if value is common.UnDefined:
                    v_frozen = ()
                elif cls.freeze_new_entries:
                    v_frozen =  [v.freeze() for v in value]
                else:
                    v_frozen = value
                v_checked = []
                for v in v_frozen:
                    if cls.entry_cls_is_leaf:
                        v = cls.param_entry_cls._dp_check_and_cast_including_undef(owner, name, v)
                    else:
                        assert isinstance(v, cls.param_entry_cls)
                    v_checked.append(v)
                return TupleObject(owner, name, v_checked)

    cls_name = f'Tuple_{entry_cls.__name__}'
    return leaf.Leaf.subclass(cls_name, TupleLeafState)
