'''
MIT Licence: Copyright (c) 2025 Baya Systems <https://bayasystems.com>

Purple implementation
======================

union class for Purple models

No object of a Union class ever exists, but the Union class itself
is needed for recording all options that can be created

Need to be able to build StaticRecord from a Union, or is there a StaticUnion?

Union classes will test True for equality if they have the same option set,
but may have different priority (order) among option classes
'''

from . import common, metaclass


class UnionInitialValue:
    def __init__(self, preferrered_option_class, initial_val_for_preferred):
        self.preferred = preferrered_option_class
        self.initial_value = initial_val_for_preferred
    def __getitem__(self, i):
        return (self.preferred, self.initial_value)[i]


class Union(common.PurpleComponent, metaclass = metaclass.UnionMetaClass):
    _dp_union_class_options = frozenset(),
    _dp_union_ordered_options = []

    def __init__(self, *a, **ka):
        assert False, f'should never create an instance of a Union class ({type(self)})'

    @classmethod
    def _dp_all_possible_values(cls):
        # FIXME maybe something dodgy here, for a Union inside a Record
        # the Record a-p-v will iterate over all the Union's values
        # but will call -dp-transient-init for each one to place it into the record
        # and the Union -dp-transient-init might return a different object, eg if there are
        # 2 leaves that can cast the same value to different outcomes
        for option_cls in cls._dp_union_ordered_options:
            yield from option_cls._dp_all_possible_values()

    @classmethod
    def _dp_transient_init(cls, default, changes, owner, name):
        '''called by Record() when creating a new transient

        if this method is called, cls is a union subclass and default is a Union-initial-value

        changes is one of
            an object of a (record) option cls
                return the object (shallow copy)
            an object castable to a leaf option cls
                return the post-cast value
            a dict
                must match default
                apply changes sparsely to copy of default
            UniqueObject (means no changes)
                same as dict but ultimate in sparseness
            UnDefined
                copy default replacing everything with undef
        '''
        default_opt_cls, default_obj = default
        if changes is common.UnDefined:
            changes = {n:changes for n in default_opt_cls._dp_state_types}

        for opt in (default_opt_cls, *cls._dp_union_ordered_options):
            try:
                return opt._dp_transient_init(default_obj, changes, owner, name)
            except Exception as ex:
                # FIXME WAY TOO LAX
                pass
        raise ValueError

    @classmethod
    def _dp_transient_setattr(cls, owner, name, value):
        for option_cls in cls._dp_union_ordered_options:
            try:
                return option_cls._dp_transient_setattr(owner, name, value)
            except:
                # FIXME
                continue
        raise ValueError

    @classmethod
    def _dp_transient_update(cls, owner, name_in_owner, current_value, changes):
        ''' a transient record (owner) wants to apply changes to current-value

        changes must be a dict for hierarchical in-place changes
        if not a dict, Union._dp_transient_setattr() will have been called
        '''
        current_value._dp_transient_update(owner, name_in_owner, current_value, changes)

    @classmethod
    def _dp_class_matches(cls, other_cls):
        return other_cls in cls._dp_union_class_options

    @classmethod
    def _dp_merge_initial_value(cls, owner_initial_value, base_initial_value):
        ''' makes the initial values for an instance of cls in owner-cls

        called repeatedly, for every base of the owner class where the instance is declared
            because each instance can override the initial values or even change the element type

        stores the last selected option class and favours it when new mods are offered

        owner_initial_value is created here and is like a tuple(preferred_option_cls, option_cls_initial_value)
            or UniqueObject the first time this is called

        base_initial_value can be
            a Union-initial-value from a base class
            UniqueObject if no modifications
            an object of a union record option class (includes undef, unsel)
            an object castable by a union leaf class (includes undef, unsel)
            a dict of modifications (maybe hierarchical)
        '''
        if owner_initial_value is common.UniqueObject:
            owner_iv = common.UniqueObject
            if isinstance(base_initial_value, UnionInitialValue):
                preferred_opt, base_iv = base_initial_value
                options = (preferred_opt,)
            else:
                options = cls._dp_union_ordered_options
                base_iv = base_initial_value
        else:
            if isinstance(base_initial_value, UnionInitialValue):
                preferred_opt, base_iv = base_initial_value
                owner_iv = owner_initial_value[1] if owner_initial_value[0] is preferred_opt else common.UniqueObject
                options = (preferred_opt,)
            else:
                base_iv = base_initial_value
                preferred_opt, owner_iv = owner_initial_value
                options = (preferred_opt, *cls._dp_union_ordered_options)

        for opt in options:
            try:
                new_iv = opt._dp_merge_initial_value(owner_iv, base_iv)
                return UnionInitialValue(opt, new_iv)
            except Exception as ex:
                # FIXME TOO LENIENT
                pass

        assert False

    @classmethod
    def _dp_union_hierarchial_lines(cls, owner, name, num_indents):
        current = owner._dp_raw_getattr(name)
        instances = owner._dp_union_instances[name]
        lines = []

        if all(x is common.UniqueObject for x in instances):
            # all options are leaves, only show the currently selected option
            lines.append([num_indents, name, owner.__str__(name)])

        else:
            # not all options are leaves
            lines.append([num_indents, name])
            num_indents += 1

            if current not in instances:
                # currently a leaf, but there are non-leaf options too
                lines.append([num_indents, '_', owner.__str__(name)])

            for opt_cls,inst in zip(cls._dp_union_ordered_options, instances):
                if inst is not common.UniqueObject:
                    lines.append([num_indents, opt_cls.__name__])
                    lines.extend(inst._dp_hierarchical_lines(True, num_indents + 1))

        return lines

    @classmethod
    def _dp_transient_deep_copy(cls, self):
        ''' a transient record is deep-copying itself and contains a union
        self is going to be the current value, an object of one of the
        union option types or an immutable leaf object cast by one of them
        '''
        if type(self) in cls._dp_union_class_options:
            return self._dp_transient_deep_copy(self)
        else:
            return self

    @classmethod
    def _dp_copy_initial_value(cls, source_iv):
        opt_cls, source = source_iv
        return UnionInitialValue(opt_cls, opt_cls._dp_copy_initial_value(source))

    @classmethod
    def _dp_get_union_options(cls):
        return cls._dp_union_ordered_options

    @classmethod
    def _dp_elaborate(cls,
        name, top_component, instantiating_component, hierarchical_name, initial_value
    ):
        ''' elaborate does 2 things
        creates a component
            hierarchically, so that component is fully elaborated
            includes state for all union options, one of which is selected
        returns the leaf state for system-top

        if inside a Record that is one option within another union, initial-value
        can be "un-selected"
        unselected option classes are elaborated, and this function creates all-unselected
        initial-values for them, using their merge-initial-value(unique, unsel)
        '''
        if initial_value is common.UnSelected:
            selected = cls._dp_union_ordered_options[0]
        else:
            selected = initial_value[0]

        # storage for static Record state within the Union
        # which needs to exist permanently although maximum one of the options is not UnSelected
        # note that static Leaf state is stored in the normal attribute of the owner when not UnSelected
        # (and does not exist when UnSelected)
        instance_list = []
        instantiating_component._dp_union_instances[name] = instance_list
        all_leaf_state = ()

        is_a_leaf = ((instantiating_component, name))
        contains_a_leaf = False
        for opt in cls._dp_union_ordered_options:
            # initialise no more then one option class to UnSelected
            if opt is selected and initial_value is not common.UnSelected:
                iv = initial_value[1]
            else:
                iv = opt._dp_merge_initial_value(common.UniqueObject, common.UnSelected)
            leaf_state = opt._dp_elaborate(name, top_component, instantiating_component, hierarchical_name, iv)
            new_instance = instantiating_component._dp_raw_getattr(name)
            if leaf_state and any(s == is_a_leaf for s in leaf_state):
                assert len(leaf_state) == 1
                contains_a_leaf = True
                instance_list.append(common.UniqueObject)
            else:
                all_leaf_state += leaf_state
                instance_list.append(new_instance)
            if opt is selected:
                start_instance = new_instance

        instantiating_component._dp_raw_setattr(name, start_instance)

        if contains_a_leaf:
            all_leaf_state += is_a_leaf
        return all_leaf_state

    @classmethod
    def _dp_instance_setattr_leaf_changes(cls, owner, name, current, value):
        for opt,inst in zip(cls._dp_union_ordered_options, owner._dp_union_instances[name]):
            try:
                leaf_updates = opt._dp_instance_setattr_leaf_changes(owner, name, inst, value)
                break
            except Exception as ex:
                # FIXME TOO LENIENT
                continue
        else:
            assert False, 'failed to set any static union option to value given'

        if inst is not current:
            # changing option-type or changing leaf-value
            if current in owner._dp_union_instances[name]:
                # attribute changing, and current is a record, so current must be de-selected
                leaf_updates += current._dp_instance_setattr_leaf_changes(owner, name, current, common.UnSelected)
            if inst is not common.UniqueObject:
                # attribute changing, and future is a record, so set attribute in owner
                leaf_updates += ((owner, name, inst),)

        return leaf_updates

    @classmethod
    def make_class(cls, option_class):
        ordered_options = cls._dp_union_ordered_options + option_class._dp_get_union_options()

        filtered_ordered_options = []
        for opt in ordered_options:
            if opt not in filtered_ordered_options:
                filtered_ordered_options.append(opt)

        cls_name = 'Union_FIXME'

        return type(cls)(cls_name, (Union,), dict(
            _dp_union_class_options = frozenset(filtered_ordered_options),
            _dp_union_ordered_options = filtered_ordered_options,
        ))
