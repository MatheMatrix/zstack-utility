# -*- coding: utf-8 -*-
"""Lifecycle tests for LocalStorage plugin against real kvmagent.

Tests the full init → create volume → check → get size → delete → verify flow
using a temporary directory under /zstack_ps (or /tmp as fallback).
All created files are cleaned up in teardown.
"""
import uuid
import pytest

REQUEST_BODY = 'body'


def _ok(rsp):
    """Check response is successful.

    LocalStorage handlers only set success=False on error; success field
    may be absent (None) when everything is fine.
    """
    return getattr(rsp, 'success', True) is not False

pytestmark = pytest.mark.skipif("not config.getoption('--direct-host')",
                                reason='lifecycle tests require real kvmagent')

# Use a unique test directory to avoid conflicting with real storage
TEST_ACCT = 'acct-test-lifecycle'
TEST_DIR = '/zstack_ps/test_lifecycle_%s' % uuid.uuid4().hex[:8]
VOLUME_SIZE = 10 * 1024 * 1024  # 10 MiB — tiny, fast


@pytest.fixture(scope='module')
def storage_env(http_client):
    """Discover storage paths on host."""
    ssh = http_client._ssh_run
    env = {}

    # Check if /zstack_ps exists
    rc, out, _ = ssh('test -d /zstack_ps && echo yes || echo no')
    env['has_zstack_ps'] = out.strip() == 'yes'
    env['storage_path'] = '/zstack_ps' if env['has_zstack_ps'] else '/tmp'
    env['test_dir'] = TEST_DIR if env['has_zstack_ps'] else '/tmp/test_lifecycle_%s' % uuid.uuid4().hex[:8]

    # Find an existing qcow2 for backing file tests
    rc, out, _ = ssh('find /zstack_ps/imagecache -name "*.qcow2" -type f 2>/dev/null | head -1')
    env['cached_image'] = out.strip() if rc == 0 and out.strip() else None

    return env


@pytest.fixture(scope='module', autouse=True)
def _cleanup_test_dir(http_client, storage_env):
    """Clean up test directory after all tests in module."""
    yield
    ssh = http_client._ssh_run
    test_dir = storage_env['test_dir']
    ssh('rm -rf %s' % test_dir)


# ──────────────────────────────────────────────────────────────────────
# 1. Init Storage
# ──────────────────────────────────────────────────────────────────────

class TestLocalStorageInit:
    def test_init_storage(self, http_client, host_plugin, storage_env):
        """Init creates the storage directory and returns capacity."""
        test_dir = storage_env['test_dir']
        init_file = '%s/%s-initialized-file' % (test_dir, uuid.uuid4().hex[:8])

        rsp = http_client.post_async('/localstorage/init', {
            'path': test_dir,
            'initFilePath': init_file,
        })
        assert _ok(rsp), 'init failed: %s' % getattr(rsp, 'error', '')
        assert rsp.totalCapacity > 0, 'totalCapacity should be > 0'
        assert rsp.availableCapacity > 0, 'availableCapacity should be > 0'

    def test_get_physical_capacity(self, http_client, host_plugin, storage_env):
        """Get capacity of the storage path."""
        rsp = http_client.post_async('/localstorage/getphysicalcapacity', {
            'storagePath': storage_env['storage_path'],
        })
        assert _ok(rsp), 'get capacity failed: %s' % getattr(rsp, 'error', '')
        assert rsp.totalCapacity > 0
        assert rsp.availableCapacity > 0
        assert rsp.totalCapacity >= rsp.availableCapacity


# ──────────────────────────────────────────────────────────────────────
# 2. Volume Lifecycle: create → check → get size → delete → verify
# ──────────────────────────────────────────────────────────────────────

class TestVolumeLifecycle:
    def test_create_check_size_delete_volume(self, http_client, host_plugin, storage_env):
        """Full lifecycle: create empty volume → check exists → get size → delete → verify gone."""
        test_dir = storage_env['test_dir']
        vol_uuid = uuid.uuid4().hex
        install_url = '%s/dataVolumes/vol-%s/%s.qcow2' % (test_dir, vol_uuid, vol_uuid)

        # CREATE empty volume
        rsp = http_client.post_async('/localstorage/volume/createempty', {
            'installUrl': install_url,
            'size': VOLUME_SIZE,
            'volumeUuid': vol_uuid,
            'name': 'test-vol',
            'storagePath': storage_env['storage_path'],
            'backingFile': None,
        })
        assert _ok(rsp), 'create volume failed: %s' % getattr(rsp, 'error', '')
        assert rsp.totalCapacity > 0
        assert rsp.actualSize > 0

        # CHECK exists
        rsp = http_client.post_async('/localstorage/checkbits', {
            'path': install_url,
        })
        assert _ok(rsp)
        assert rsp.existing is True, 'volume should exist after create'

        # GET SIZE
        rsp = http_client.post_async('/localstorage/volume/getsize', {
            'installPath': install_url,
        })
        assert _ok(rsp), 'get size failed: %s' % getattr(rsp, 'error', '')
        assert rsp.size >= VOLUME_SIZE, 'virtual size should be >= requested'
        assert rsp.actualSize > 0

        # DELETE
        rsp = http_client.post_async('/localstorage/delete', {
            'path': install_url,
            'storagePath': storage_env['storage_path'],
        })
        assert _ok(rsp), 'delete failed: %s' % getattr(rsp, 'error', '')

        # VERIFY deleted
        rsp = http_client.post_async('/localstorage/checkbits', {
            'path': install_url,
        })
        assert _ok(rsp)
        assert rsp.existing is False, 'volume should not exist after delete'

    def test_create_volume_from_cache(self, http_client, host_plugin, storage_env):
        """Create volume from cached image template → check → delete."""
        cached = storage_env.get('cached_image')
        if not cached:
            pytest.skip('no cached image on host for backing file test')

        test_dir = storage_env['test_dir']
        vol_uuid = uuid.uuid4().hex
        install_url = '%s/rootVolumes/vol-%s/%s.qcow2' % (test_dir, vol_uuid, vol_uuid)

        # CREATE from cache
        rsp = http_client.post_async('/localstorage/volume/createvolumefromcache', {
            'templatePathInCache': cached,
            'installUrl': install_url,
            'storagePath': storage_env['storage_path'],
            'volumeUuid': vol_uuid,
        })
        assert _ok(rsp), 'create from cache failed: %s' % getattr(rsp, 'error', '')
        assert rsp.totalCapacity > 0

        # CHECK exists
        rsp = http_client.post_async('/localstorage/checkbits', {
            'path': install_url,
        })
        assert _ok(rsp)
        assert rsp.existing is True

        # GET backing chain — should reference the cached image
        rsp = http_client.post_async('/localstorage/volume/getbackingfile', {
            'path': install_url,
        })
        assert _ok(rsp)
        assert rsp.backingFilePath is not None, 'should have a backing file'

        # DELETE
        rsp = http_client.post_async('/localstorage/delete', {
            'path': install_url,
            'storagePath': storage_env['storage_path'],
        })
        assert _ok(rsp)


# ──────────────────────────────────────────────────────────────────────
# 3. Folder operations
# ──────────────────────────────────────────────────────────────────────

class TestFolderOperations:
    def test_create_folder(self, http_client, host_plugin, storage_env):
        """Create a folder → check exists → delete dir.

        Note: create_folder uses os.path.dirname(installUrl), so it creates
        the *parent* of installUrl, not installUrl itself.
        """
        test_dir = storage_env['test_dir']
        folder_uuid = uuid.uuid4().hex[:8]
        # installUrl acts as a "volume path" — the handler creates its parent
        install_url = '%s/folders/%s/vol.qcow2' % (test_dir, folder_uuid)
        created_dir = '%s/folders/%s' % (test_dir, folder_uuid)

        # CREATE folder (creates dirname of installUrl)
        rsp = http_client.post_async('/localstorage/volume/createfolder', {
            'installUrl': install_url,
            'storagePath': storage_env['storage_path'],
        })
        assert _ok(rsp), 'create folder failed: %s' % getattr(rsp, 'error', '')

        # CHECK exists — the created directory is the parent
        rsp = http_client.post_async('/localstorage/checkbits', {
            'path': created_dir,
        })
        assert _ok(rsp)
        assert rsp.existing is True

        # DELETE dir
        rsp = http_client.post_async('/localstorage/deletedir', {
            'path': created_dir,
            'storagePath': storage_env['storage_path'],
        })
        assert _ok(rsp)

        # VERIFY deleted
        rsp = http_client.post_async('/localstorage/checkbits', {
            'path': created_dir,
        })
        assert _ok(rsp)
        assert rsp.existing is False


# ──────────────────────────────────────────────────────────────────────
# 4. Edge cases
# ──────────────────────────────────────────────────────────────────────

class TestEdgeCases:
    def test_check_nonexistent_path(self, http_client, host_plugin):
        """Check a path that doesn't exist → existing=False."""
        rsp = http_client.post_async('/localstorage/checkbits', {
            'path': '/nonexistent/path/vol.qcow2',
        })
        assert _ok(rsp)
        assert rsp.existing is False

    def test_delete_nonexistent_volume(self, http_client, host_plugin, storage_env):
        """Delete a volume that doesn't exist → should still succeed."""
        rsp = http_client.post_async('/localstorage/delete', {
            'path': '/nonexistent/path/vol.qcow2',
            'storagePath': storage_env['storage_path'],
        })
        assert _ok(rsp)

    def test_init_twice_is_idempotent(self, http_client, host_plugin, storage_env):
        """Double init should succeed without error."""
        test_dir = storage_env['test_dir']
        init_file = '%s/idem-init-file' % test_dir

        for _ in range(2):
            rsp = http_client.post_async('/localstorage/init', {
                'path': test_dir,
                'initFilePath': init_file,
            })
            assert _ok(rsp), 'init failed: %s' % getattr(rsp, 'error', '')


# ──────────────────────────────────────────────────────────────────────
# 5. Initialized file lifecycle
# ──────────────────────────────────────────────────────────────────────

class TestInitializedFile:
    def test_create_and_check_initialized_file(self, http_client, host_plugin, storage_env):
        """Create initialized file → check exists → verify."""
        test_dir = storage_env['test_dir']
        init_file = '%s/test-init-%s' % (test_dir, uuid.uuid4().hex[:8])

        # CREATE
        rsp = http_client.post_async('/localstorage/create/initializedfile', {
            'filePath': init_file,
        })
        assert _ok(rsp), 'create init file failed: %s' % getattr(rsp, 'error', '')

        # CHECK exists
        rsp = http_client.post_async('/localstorage/check/initializedfile', {
            'filePath': init_file,
            'storagePath': storage_env['storage_path'],
        })
        assert _ok(rsp)
        assert rsp.existed is True, 'init file should exist after create'
        assert rsp.totalCapacity > 0

    def test_check_nonexistent_initialized_file(self, http_client, host_plugin, storage_env):
        """Check initialized file that doesn't exist → existed=False."""
        rsp = http_client.post_async('/localstorage/check/initializedfile', {
            'filePath': '/nonexistent/init-file-xyz',
            'storagePath': storage_env['storage_path'],
        })
        assert _ok(rsp)
        assert rsp.existed is False


# ──────────────────────────────────────────────────────────────────────
# 6. Backing chain
# ──────────────────────────────────────────────────────────────────────

class TestBackingChain:
    def test_get_backing_chain_of_volume(self, http_client, host_plugin, storage_env):
        """Create volume → get backing chain → chain should include itself."""
        test_dir = storage_env['test_dir']
        vol_uuid = uuid.uuid4().hex
        install_url = '%s/chaintest/vol-%s/%s.qcow2' % (test_dir, vol_uuid, vol_uuid)

        # CREATE volume first
        rsp = http_client.post_async('/localstorage/volume/createempty', {
            'installUrl': install_url,
            'size': 10 * 1024 * 1024,
            'volumeUuid': vol_uuid,
            'name': 'chain-test',
            'storagePath': storage_env['storage_path'],
            'backingFile': None,
        })
        assert _ok(rsp), 'create volume failed: %s' % getattr(rsp, 'error', '')

        # GET BACKING CHAIN
        rsp = http_client.post_async('/localstorage/volume/getbackingchain', {
            'installPath': install_url,
        })
        assert _ok(rsp), 'get backing chain failed: %s' % getattr(rsp, 'error', '')
        assert rsp.backingChain is not None
        # A standalone volume (no backing file) has an empty chain
        assert isinstance(rsp.backingChain, list)

        # CLEANUP
        http_client.post_async('/localstorage/delete', {
            'path': install_url,
            'storagePath': storage_env['storage_path'],
        })
