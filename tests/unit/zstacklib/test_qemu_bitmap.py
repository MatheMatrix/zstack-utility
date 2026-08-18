import json
import shlex
import importlib.util
import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest


def _load_qemu_module():
    bash_module = sys.modules['zstacklib.utils.bash']
    shell_module = sys.modules['zstacklib.utils.shell']
    bash_module.bash_roe = lambda *_args, **_kwargs: (
        0, 'QEMU emulator version 6.2.0 (qemu-kvm-6.2.0)', '')
    shell_module.call = lambda *_args, **_kwargs: '6.2.0'

    repo_root = Path(__file__).resolve().parents[3]
    module_path = repo_root / 'zstacklib' / 'zstacklib' / 'utils' / 'qemu.py'
    spec = importlib.util.spec_from_file_location('zstacklib.utils.qemu_bitmap_under_test', str(module_path))
    module = importlib.util.module_from_spec(spec)
    real_exists = os.path.exists
    with patch('os.path.exists', side_effect=lambda path: (
            path == '/usr/bin/qemu-system-x86_64' or real_exists(path))):
        spec.loader.exec_module(module)
    return module


qemu = _load_qemu_module()


def test_get_zbs_data_bitmap_parses_exists_extents_and_splits(monkeypatch):
    commands = []
    response = {
        'error': None,
        'result': [
            {'offset': 8388608, 'length': 65536, 'exists': 'true'},
            {'offset': 536870912, 'length': 131072, 'exists': True},
            {'offset': 900000000, 'length': 65536, 'exists': 'false'},
        ],
    }
    monkeypatch.setattr(qemu.linux, 'shellquote', shlex.quote)
    monkeypatch.setattr(qemu.shell, 'call', lambda command: commands.append(command) or json.dumps(response))

    result = qemu.get_zbs_data_bitmap('lpool1/volume with space', 65536)

    assert result == {8388608: 65536, 536870912: 65536, 536936448: 65536}
    assert commands == ["zbs query diff --path 'lpool1/volume with space' --format json"]


def test_get_zbs_data_bitmap_rejects_business_error_even_when_command_succeeds(monkeypatch):
    monkeypatch.setattr(qemu.linux, 'shellquote', shlex.quote)
    monkeypatch.setattr(
        qemu.shell,
        'call',
        lambda _command: '{"error":{"code":-1,"message":"file is not a regular volume"},"result":null}',
    )

    with pytest.raises(RuntimeError, match='file is not a regular volume'):
        qemu.get_zbs_data_bitmap('lpool1/clone-root', 65536)


def test_get_zbs_data_bitmap_rejects_invalid_result(monkeypatch):
    monkeypatch.setattr(qemu.linux, 'shellquote', shlex.quote)
    monkeypatch.setattr(qemu.shell, 'call', lambda _command: '{"error":null,"result":null}')

    with pytest.raises(ValueError, match='result must be a list'):
        qemu.get_zbs_data_bitmap('lpool1/volume', 65536)


def test_get_rbd_data_bitmap_splits_offset_extents(monkeypatch):
    monkeypatch.setattr(qemu.linux, 'shellquote', shlex.quote)
    monkeypatch.setattr(
        qemu.shell,
        'call',
        lambda _command: '[{"offset":4096,"length":8192,"exists":"true"}]',
    )

    assert qemu.get_rbd_data_bitmap('pool/image', 4096) == {4096: 4096, 8192: 4096}


def test_get_data_bitmap_can_select_only_top_qcow2_allocations(monkeypatch):
    monkeypatch.setattr(qemu, 'get_device_map', lambda _path, _option: json.dumps([
        {'start': 0, 'length': 4096, 'zero': False, 'data': True, 'depth': 1},
        {'start': 4096, 'length': 4096, 'zero': False, 'data': True, 'depth': 0},
    ]))

    assert qemu.get_data_bitmap('cbd:scratch', 4096, False, True, '-f qcow2', 0) == {4096: 4096}


def test_merge_data_bitmaps_unions_adjacent_contained_and_transitive_extents():
    result = qemu.merge_data_bitmaps([
        {0: 10, 30: 10},
        {5: 30, 40: 5},
    ], 16)

    assert result == {0: 16, 16: 16, 32: 13}


def test_merge_data_bitmaps_keeps_disjoint_extents():
    assert qemu.merge_data_bitmaps([{0: 5}, {10: 5}], 16) == {0: 5, 10: 5}
