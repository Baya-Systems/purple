'''
MIT Licence: Copyright (c) 2025 Baya Systems <https://bayasystems.com>

Purple implementation
======================

Purple leaf state base type

Can be instantiated in a transient Record object or a static Record or Model
Is the same in both cases
'''

from . import common, metaclass


class Leaf(common.PurpleComponent, metaclass = metaclass.PurpleLeafMetaClass):
    _dp_initial_value = common.UnDefined

    @classmethod
    def _dp_merge_initial_value(cls, owner_initial_value, base_initial_value):
        if base_initial_value is not common.UniqueObject:
            candidate = base_initial_value
        elif owner_initial_value is common.UniqueObject:
            candidate = cls._dp_initial_value
        else:
            candidate = owner_initial_value

        # check that the candidate value is castable before returning it
        cls._dp_check_and_cast_including_undef(None, '', candidate)
        return candidate

    @classmethod
    def _dp_copy_initial_value(cls, source):
        # assumes that leaf sources are immutable (do not need copy)
        return source

    @classmethod
    def _dp_elaborate(cls, name, top_component, instantiating_component, hierarchical_name, initial_value):
        # leaf objects are just an attribute in the instantiating_component
        cast_value = cls._dp_check_and_cast_including_undef(instantiating_component, name, initial_value)
        instantiating_component._dp_raw_setattr(name, cast_value)
        return ((instantiating_component, name),)

    @classmethod
    def _dp_check_and_cast_including_undef(cls, owner, name, value, allow_unsel = True):
        if value is common.UnDefined:
            return value
        elif value is common.UnSelected and allow_unsel:
            return value
        else:
            return cls._dp_check_and_cast(owner, name, value)

    @classmethod
    def _dp_instance_setattr_leaf_changes(cls, owner, name, current, value):
        cast_value = cls._dp_check_and_cast_including_undef(owner, name, value)
        return ((owner, name, cast_value),)

    @classmethod
    def _dp_transient_setattr(cls, owner, name, value):
        cast_value = cls._dp_check_and_cast_including_undef(owner, name, value)
        owner._dp_raw_setattr(name, cast_value)

    @classmethod
    def _dp_transient_init(cls, default, changes, owner, name):
        if changes is common.UniqueObject:
            cast_value = cls._dp_check_and_cast_including_undef(owner, name, default)
        else:
            cast_value = cls._dp_check_and_cast_including_undef(owner, name, changes)
        return cast_value

    @classmethod
    def _dp_transient_deep_copy(cls, value):
        return value

    @classmethod
    def _dp_transient_update(cls, owner, name, current, value):
        cls._dp_transient_setattr(owner, name, value)

    @classmethod
    def _dp_instance_update_leaf_changes(cls, owner, name, current, value):
        return cls._dp_instance_setattr_leaf_changes(owner, name, current, value)

    @classmethod
    def subclass(cls, cls_name, vars_cls, *other_bases):
        return type(cls)(cls_name, (cls, *other_bases), vars(vars_cls).copy())
