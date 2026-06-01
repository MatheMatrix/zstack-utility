from kvmagent.plugins.imagestore import ImageStoreClient


TEST_IPV6_ADDRESS = '2001:db8::10'
TEST_IPV4_ADDRESS = '192.168.10.10'
TEST_IMAGE_PATH = 'zstore://image-name/image-id'
TEST_PRIMARY_PATH = '/zstack_ps/rootVolumes/volume.qcow2'


def test_imagestore_client_registry_url_wraps_ipv6_only_once():
    client = ImageStoreClient()

    assert client._build_registry_url(TEST_IPV4_ADDRESS) == '192.168.10.10:8000'
    assert client._build_registry_url(TEST_IPV6_ADDRESS) == '[2001:db8::10]:8000'
    assert client._build_registry_url('[2001:db8::10]') == '[2001:db8::10]:8000'


def test_download_from_imagestore_uses_bracketed_ipv6_registry_url(monkeypatch):
    client = ImageStoreClient()
    commands = []

    monkeypatch.setattr(client, '_check_zstore_cli', lambda: None)
    monkeypatch.setattr(
        'kvmagent.plugins.imagestore.shell.call',
        lambda command: commands.append(command) or '',
    )

    client.download_from_imagestore(
        None,
        TEST_IPV6_ADDRESS,
        TEST_IMAGE_PATH,
        TEST_PRIMARY_PATH,
    )

    assert len(commands) == 1
    assert ' -url [2001:db8::10]:8000 ' in commands[0]
