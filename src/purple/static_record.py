'''
MIT Licence: Copyright (c) 2025 Baya Systems <https://bayasystems.com>

Purple implementation
======================

Purple hierarchical state type with no ports or rules
That is, something that can also be a transient object outside any system with static state
'''

from . import model


class StaticRecord(model.Model):
    _dp_class_cache = dict()

    def copy(self):
        return self._dp_record_class(**{k:self._dp_raw_getattr(k) for k in self._dp_state_types})

    def deep_copy(self):
        return self._dp_record_class._dp_transient_deep_copy(self)

    @classmethod
    def make_class(cls, record_cls):
        ''' convert a Record (transient) type to a Model (static) type
        '''
        try:
            return cls._dp_class_cache[record_cls]

        except KeyError:
            # construct a new type
            classname = record_cls.__name__ + 'Static'
            bases = cls, record_cls
            namespace = type(cls).__prepare__(classname, bases)
            static_cls = type(cls)(classname, bases, namespace)

            static_cls._dp_record_class = record_cls
            cls._dp_class_cache[record_cls] = static_cls
            return static_cls
