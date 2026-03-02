import json
from unittest.mock import MagicMock
from zstacklib.utils import http
from kvmagent.plugins import vm_plugin

def _make_req(body_dict=None):
    body = json.dumps(body_dict or {})
    return {http.REQUEST_BODY: body, http.REQUEST_HEADER: {}}

def _make_vm_plugin():
    plugin = vm_plugin.VmPlugin.__new__(vm_plugin.VmPlugin)
    plugin.config = {}
    return plugin

def test_debug_attach_iso():
    plugin = _make_vm_plugin()
    mock_vm = MagicMock()
    vm_plugin.get_vm_by_uuid = MagicMock(return_value=mock_vm)
    
    req = _make_req({'vmUuid': 'vm-uuid'})
    result = plugin.attach_iso(req)
    rsp = json.loads(result)
    if not rsp.get('success'):
        print(f"\n\nERROR: {rsp.get('error', 'UNKNOWN')}\n\n")
    assert rsp['success'] is True, f"Error: {rsp.get('error')}"
