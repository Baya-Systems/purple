'''
MIT Licence: Copyright (c) 2025 Baya Systems <https://bayasystems.com>

Purple Tests
======================

Test runner
'''

import importlib
import pathlib
import contextlib
import cli

assert __name__ == '__main__'

def run():
    importlib.import_module(cli.args.test_name + '_test')


try:
    if cli.args.stdout == 'stdout':
        run()
    else:
        with open(pathlib.Path(cli.args.stdout), 'a') as redirect:
            with contextlib.redirect_stdout(redirect):
                run()

except Exception as exc:
    if cli.args.keep_going:
        print('===============', cli.args.test_name, 'FAIL')
    else:
        print('===============', cli.args.test_name, 'FAIL', exc)
        raise

else:
    print('===============', cli.args.test_name, 'PASS')
