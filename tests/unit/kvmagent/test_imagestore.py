import importlib.util
import sys
from contextlib import nullcontext
from pathlib import Path
from unittest.mock import MagicMock

import pytest


def _load_imagestore_module():
    bash_module = sys.modules.get('zstacklib.utils.bash')
    if bash_module is not None and not hasattr(bash_module, 'bash_progress_1'):
        bash_module.bash_progress_1 = lambda *args, **kwargs: (0, '', None)

    repo_root = Path(__file__).resolve().parents[3]
    module_path = repo_root / 'kvmagent' / 'kvmagent' / 'plugins' / 'imagestore.py'
    spec = importlib.util.spec_from_file_location('imagestore_under_test', str(module_path))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if not hasattr(module, 'linux'):
        module.linux = sys.modules['zstacklib.utils.linux']
    return module


imagestore = _load_imagestore_module()
ImageStoreClient = imagestore.ImageStoreClient


TEST_IPV6_ADDRESS = '2001:db8::10'
TEST_IPV4_ADDRESS = '192.168.10.10'
TEST_IMAGE_PATH = 'zstore://image-name/image-id'
TEST_PRIMARY_PATH = '/zstack_ps/rootVolumes/volume.qcow2'
TEST_CBD_PATH = 'cbd:pool_physical/pool/volume'
TEST_CONFIGURED_CBD_PATH = TEST_CBD_PATH + '_zbs_:/etc/zbs/client.conf'


def test_imagestore_client_registry_url_wraps_ipv6_only_once():
    client = ImageStoreClient()

    assert client._build_registry_url(TEST_IPV4_ADDRESS) == '192.168.10.10:8000'
    assert client._build_registry_url(TEST_IPV6_ADDRESS) == '[2001:db8::10]:8000'
    assert client._build_registry_url('[2001:db8::10]') == '[2001:db8::10]:8000'


def test_download_from_imagestore_uses_bracketed_ipv6_registry_url(monkeypatch):
    client = ImageStoreClient()
    commands = []

    monkeypatch.setattr(client, '_check_zstore_cli', lambda: None)
    monkeypatch.setattr(imagestore.shell, 'call', lambda command: commands.append(command) or '')

    client.download_from_imagestore(
        None,
        TEST_IPV6_ADDRESS,
        TEST_IMAGE_PATH,
        TEST_PRIMARY_PATH,
    )

    assert len(commands) == 1
    assert ' -url [2001:db8::10]:8000 ' in commands[0]


def test_cbd_actual_path_appends_client_config_once():
    assert imagestore.get_cbd_actual_path(TEST_CBD_PATH) == TEST_CONFIGURED_CBD_PATH
    assert imagestore.get_cbd_actual_path(TEST_CONFIGURED_CBD_PATH) == TEST_CONFIGURED_CBD_PATH


def test_cbd_actual_path_leaves_other_protocols_unchanged():
    path = 'ceph://pool/volume'
    assert imagestore.get_cbd_actual_path(path) == path


@pytest.mark.parametrize('path', [TEST_CBD_PATH, TEST_CONFIGURED_CBD_PATH])
def test_zbs_cli_path_strips_physical_pool_and_client_config(path):
    assert imagestore.get_zbs_cli_path(path) == 'pool/volume'


def test_zbs_cli_path_accepts_native_zbs_path():
    assert imagestore.get_zbs_cli_path('zbs://pool/volume') == 'pool/volume'


@pytest.mark.parametrize('path', [
    'cbd:pool-only',
    'cbd:physical/logical-only',
    'zbs://logical-only',
    '/local/path',
])
def test_zbs_cli_path_rejects_invalid_path(path):
    with pytest.raises(ValueError, match='invalid'):
        imagestore.get_zbs_cli_path(path)


@pytest.mark.parametrize('delimiter', [',', ';', '\n', '\r', '\x00'])
def test_cbd_actual_path_rejects_protocol_delimiters(delimiter):
    with pytest.raises(ValueError, match='protocol delimiters'):
        imagestore.get_cbd_actual_path(TEST_CBD_PATH + delimiter + 'suffix')


def test_cbt_backup_uses_shell_quoted_configured_cbd_target_without_mutating_input(monkeypatch, tmp_path):
    client = ImageStoreClient()
    disk = MagicMock(type_='file')
    disk.alias.name_ = 'virtio-disk0'
    vm = MagicMock(uuid='vm-uuid')
    vm._get_target_disk.return_value = (disk, None)
    unsafe_but_valid_path = TEST_CBD_PATH + "$(touch /tmp/not-executed)'quoted"
    volume_info = MagicMock(target=unsafe_but_valid_path)
    volume_info.volume = MagicMock()
    result_file = tmp_path / 'cbt-result.json'
    commands = []

    monkeypatch.setattr(imagestore.linux, 'create_temp_file', lambda: str(result_file))
    monkeypatch.setattr(imagestore.linux, 'rm_file_force', lambda _path: None)
    monkeypatch.setattr(imagestore.linux, 'ShowLibvirtErrorOnException', lambda _vm: nullcontext())

    def call(command):
        commands.append(command)
        result_file.write_text(
            '[{"device":"drive-virtio-disk0","mode":"full",'
            '"scratchNodeName":"scratch","nbdPort":"10888","bitmap":"bitmap"}]'
        )
        return ''

    monkeypatch.setattr(imagestore.shell, 'call', call)

    result = client.cbt_backup_volume(vm, [volume_info], '', '10888-10888')

    configured_path = imagestore.get_cbd_actual_path(unsafe_but_valid_path)
    assert len(result) == 1
    assert imagestore.linux.shellquote('drive-virtio-disk0,' + configured_path + ';') in commands[0]
    assert volume_info.target == unsafe_but_valid_path


def test_stop_cbt_backup_uses_configured_cbd_target(monkeypatch):
    client = ImageStoreClient()
    record = MagicMock(
        scratchNodeName='scratch', target=TEST_CBD_PATH,
        lastBitmapName='previous-bitmap', bitmapName='new-bitmap',
    )
    commands = []

    monkeypatch.setattr(imagestore.linux, 'ShowLibvirtErrorOnException', lambda _vm: nullcontext())
    monkeypatch.setattr(imagestore.shell, 'call', lambda command: commands.append(command) or '')

    client.stop_vm_cbt_backup_jobs('vm-uuid', [record])

    assert TEST_CONFIGURED_CBD_PATH in commands[0]
    assert '-rollback' not in commands[0]


def test_rollback_cbt_backup_carries_previous_and_new_bitmap(monkeypatch):
    client = ImageStoreClient()
    record = MagicMock(
        scratchNodeName='scratch', target=TEST_CBD_PATH,
        lastBitmapName='previous-bitmap', bitmapName='new-bitmap',
    )
    commands = []

    monkeypatch.setattr(imagestore.linux, 'ShowLibvirtErrorOnException', lambda _vm: nullcontext())
    monkeypatch.setattr(imagestore.shell, 'call', lambda command: commands.append(command) or '')

    client.rollback_vm_cbt_backup_jobs('vm-uuid', [record])

    assert '-rollback=true' in commands[0]
    assert "-bitmap 'previous-bitmap'" in commands[0]
    assert "-newbitmap 'new-bitmap'" in commands[0]
    assert TEST_CONFIGURED_CBD_PATH in commands[0]


def test_get_cbt_capabilities_queries_installed_cli(monkeypatch):
    client = ImageStoreClient()
    commands = []

    monkeypatch.setattr(
        imagestore.shell,
        'call',
        lambda command: commands.append(command) or '{"rollbackVolumeCbtBackup":true}',
    )

    capabilities = client.get_cbt_capabilities()

    assert capabilities['rollbackVolumeCbtBackup'] is True
    assert commands == [client.ZSTORE_CLI_PATH + ' cbtcapabilities']
