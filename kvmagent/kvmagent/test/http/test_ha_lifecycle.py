# -*- coding: utf-8 -*-
"""Lifecycle tests for HA Plugin against real kvmagent.

Safe operations: fencer state query, fencer rule CRUD (in-memory only).
No destructive operations (setup/cancel fencer, scan host).
"""
import uuid
import pytest

REQUEST_BODY = 'body'

pytestmark = pytest.mark.skipif("not config.getoption('--direct-host')",
                                reason='lifecycle tests require real kvmagent')


def _ok(rsp):
    """Check response is successful (field may be absent/None on success)."""
    return getattr(rsp, 'success', True) is not False


# ──────────────────────────────────────────────────────────────────────
# 1. VM Fencer Rule Lifecycle: get → add → get (verify) → remove → get
# ──────────────────────────────────────────────────────────────────────

class TestVmFencerRuleLifecycle:
    FENCER_NAME = 'test-fencer-%s' % uuid.uuid4().hex[:8]
    FAKE_VM_UUID = uuid.uuid4().hex

    @pytest.fixture(autouse=True)
    def _cleanup(self, http_client):
        """Remove test fencer rules after each test."""
        yield
        try:
            http_client.post_async('/remove/vm/fencer/rule/from/host', {
                'allowRules': [{'fencerName': self.FENCER_NAME, 'vmUuids': [self.FAKE_VM_UUID]}],
                'blockRules': [],
            })
        except Exception:
            pass

    def test_get_fencer_rules_empty(self, http_client, host_plugin):
        """Get fencer rules → should return allow/block dicts."""
        rsp = http_client.post_async('/get/vm/fencer/rule/', {})
        assert _ok(rsp), 'get fencer rule failed: %s' % getattr(rsp, 'error', '')
        assert rsp.allowRules is not None, 'allowRules should not be None'
        assert rsp.blockRules is not None, 'blockRules should not be None'

    def test_add_get_remove_fencer_rule(self, http_client, host_plugin):
        """Full lifecycle: add rule → get (verify present) → remove → get (verify gone)."""
        # ADD allow rule with fake VM UUID
        rsp = http_client.post_async('/add/vm/fencer/rule/to/host', {
            'allowRules': [{'fencerName': self.FENCER_NAME, 'vmUuids': [self.FAKE_VM_UUID]}],
            'blockRules': [],
        })
        assert _ok(rsp), 'add fencer rule failed: %s' % getattr(rsp, 'error', '')

        # GET and verify rule is present
        rsp = http_client.post_async('/get/vm/fencer/rule/', {})
        assert _ok(rsp)
        allow = rsp.allowRules
        # allowRules is a dict: {fencerName: [vmUuids]}
        rules_dict = allow.__dict__ if hasattr(allow, '__dict__') else {}
        assert self.FENCER_NAME in rules_dict, (
            'fencer %s should be in allowRules' % self.FENCER_NAME)
        vm_list = getattr(allow, self.FENCER_NAME, [])
        assert self.FAKE_VM_UUID in vm_list, (
            'VM %s should be in allow list' % self.FAKE_VM_UUID)

        # REMOVE the rule
        rsp = http_client.post_async('/remove/vm/fencer/rule/from/host', {
            'allowRules': [{'fencerName': self.FENCER_NAME, 'vmUuids': [self.FAKE_VM_UUID]}],
            'blockRules': [],
        })
        assert _ok(rsp), 'remove fencer rule failed: %s' % getattr(rsp, 'error', '')

        # GET and verify rule is removed
        rsp = http_client.post_async('/get/vm/fencer/rule/', {})
        assert _ok(rsp)
        allow = rsp.allowRules
        rules_dict = allow.__dict__ if hasattr(allow, '__dict__') else {}
        if self.FENCER_NAME in rules_dict:
            vm_list = getattr(allow, self.FENCER_NAME, [])
            assert self.FAKE_VM_UUID not in vm_list, (
                'VM %s should be removed from allow list' % self.FAKE_VM_UUID)

    def test_add_block_rule(self, http_client, host_plugin):
        """Add a block rule → verify in blockRules → remove."""
        # ADD block rule
        rsp = http_client.post_async('/add/vm/fencer/rule/to/host', {
            'allowRules': [],
            'blockRules': [{'fencerName': self.FENCER_NAME, 'vmUuids': [self.FAKE_VM_UUID]}],
        })
        assert _ok(rsp)

        # GET and verify
        rsp = http_client.post_async('/get/vm/fencer/rule/', {})
        assert _ok(rsp)
        block = rsp.blockRules
        rules_dict = block.__dict__ if hasattr(block, '__dict__') else {}
        assert self.FENCER_NAME in rules_dict
        vm_list = getattr(block, self.FENCER_NAME, [])
        assert self.FAKE_VM_UUID in vm_list

        # REMOVE block rule
        rsp = http_client.post_async('/remove/vm/fencer/rule/from/host', {
            'allowRules': [],
            'blockRules': [{'fencerName': self.FENCER_NAME, 'vmUuids': [self.FAKE_VM_UUID]}],
        })
        assert _ok(rsp)
