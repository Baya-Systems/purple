'''
MIT Licence: Copyright (c) 2025 Baya Systems <https://bayasystems.com>

Purple implementation
======================

Purple parameterised component decorator

* allows use of square brackets for parameterisation of classes
* pre-processes class parameters to provide a range of options
* caches classes so that when created from equivalent parameters, there is only one class
  and it can be compared with == and "is"
'''

import inspect


class Generic:
    def __init__(self, generic_class_factory):
        self.generic_class_factory = generic_class_factory
        self.class_cache = dict()

    def __getitem__(self, index):
        if index is Ellipsis:
            args = tuple()
            kwargs = {}
        elif isinstance(index, tuple):
            if len(index) == 2 and isinstance(index[0], tuple) and isinstance(index[1], dict):
                args = index[0]
                kwargs = index[1]
            else:
                args = index
                kwargs = {}
        elif type(index) is dict:
            args = tuple()
            kwargs = index
        else:
            args = (index,)
            kwargs = {}

        component_class = self.generic_class_factory(*args, **kwargs)
        default_cache_key = self.make_default_class_cache_key(args, kwargs)
        class_cache_key = getattr(component_class, '_dp_class_cache_key', default_cache_key)

        if class_cache_key is None:
            return component_class

        try:
            cached_component_class = self.class_cache.get(class_cache_key, None)
        except TypeError:
            # may be an unhashable key
            return component_class

        if cached_component_class is None:
            self.class_cache[class_cache_key] = component_class
        else:
            component_class = cached_component_class

        return component_class

    def make_default_class_cache_key(self, args, kwargs):
        '''uses inspect.signature to determine the arguments used by the class factory

        some parameters have been given, need to add any defaults and create a hashable object
        this will be used for caching the leaf classes so that we only have one of each
        and therefore can compare them
        '''
        factory_signature = inspect.signature(self.generic_class_factory)
        bound_args = factory_signature.bind(*args, **kwargs)
        bound_args.apply_defaults()
        return tuple(bound_args.arguments.items())
