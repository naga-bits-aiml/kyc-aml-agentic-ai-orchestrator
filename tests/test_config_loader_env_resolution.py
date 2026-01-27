"""Simple test for environment variable placeholder resolution in ConfigLoader."""
import os
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from utilities.config_loader import ConfigLoader


def run_tests():
    # Clear test vars
    os.environ.pop('TEST_VAR_UNSET', None)
    os.environ.pop('TEST_VAR_EMPTY', None)
    os.environ.pop('TEST_VAR_SET', None)

    # Set one var to empty and one to a value
    os.environ['TEST_VAR_EMPTY'] = ''
    os.environ['TEST_VAR_SET'] = 'value123'

    cl = ConfigLoader()

    sample = {
        'a': '${TEST_VAR_UNSET:-default1}',    # unset -> default1
        'b': '${TEST_VAR_EMPTY:-default2}',    # empty -> default2 (:-)
        'c': '${TEST_VAR_EMPTY-default3}',     # empty -> '' (since - uses only unset)
        'd': '${TEST_VAR_SET:-default4}',      # set -> value123
        'e': '${TEST_VAR_SET-default5}',       # set -> value123
        'f': '${TEST_VAR_UNSET}',              # unset -> ''
        'g': 'prefix-${TEST_VAR_UNSET:-X}-suffix'  # embedded
    }

    resolved = cl._resolve_env_vars(sample)

    assert resolved['a'] == 'default1', f"a expected default1, got {resolved['a']}"
    assert resolved['b'] == 'default2', f"b expected default2, got {resolved['b']}"
    assert resolved['c'] == '', f"c expected empty string, got {resolved['c']}"
    assert resolved['d'] == 'value123', f"d expected value123, got {resolved['d']}"
    assert resolved['e'] == 'value123', f"e expected value123, got {resolved['e']}"
    assert resolved['f'] == '', f"f expected empty string, got {resolved['f']}"
    assert resolved['g'] == 'prefix-X-suffix', f"g expected prefix-X-suffix, got {resolved['g']}"

    print('All config loader env-resolution tests passed')


if __name__ == '__main__':
    run_tests()
