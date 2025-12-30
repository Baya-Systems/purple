"""
MIT Licence: Copyright (c) 2025 Baya Systems <https://bayasystems.com>

Purple Tests
======================

Command line parsing for tests

Also any other commonly available test infrastructure
"""

from purple import ReadUnDefined, Model


def expect_undef(model, attr_name):
    try:
        z = getattr(model, attr_name)
    except ReadUnDefined:
        pass
    else:
        assert False, str(z)


class TestException:
    def __init__(self, etp, msg):
        self.expected_to_pass = etp
        self.message = msg

    def __enter__(self):
        pass

    def __exit__(self, exc_type, exc_value, traceback):
        if self.expected_to_pass and exc_type:
            print("should have passed:", self.message)
        elif (not self.expected_to_pass) and (not exc_type):
            assert False, "should have failed: " + self.message
        elif (not self.expected_to_pass) and exc_type:
            return True


def pretty_dict(d, i=""):
    for k, v in d.items():
        if isinstance(v, dict):
            print(f"{i}{k}:")
            pretty_dict(v, i + "   ")
        else:
            print(f"{i}{k}: {v}")


class Test:
    """decorator for a generator function which is iterated over from a rule
    that is, each next() on the generator is one rule invocation
    """

    class Top(Model):
        rules: [run]

        def run(self):
            Test.step()

    def __init__(self, top, *func_args, **find_rule_kwargs):
        self.top = top
        self.func_args = func_args
        self.rule = next(top.find_rule(**find_rule_kwargs))

    def __call__(self, coroutine_func):
        self.coroutine = coroutine_func(self.top, *self.func_args)
        self.complete = False
        while not self.complete:
            Test.current = self
            self.rule.invoke()

    @classmethod
    def step(cls):
        try:
            next(cls.current.coroutine)
        except StopIteration:
            cls.current.complete = True
