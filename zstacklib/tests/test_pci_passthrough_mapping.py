"""Tests for PCI/mdev passthrough mapping optimization (ZSTAC-83709).

Covers early return when VM has no passthrough devices, avoiding
unnecessary QEMU monitor queries and 3x2s retry waste per VM.
"""

from unittest.mock import MagicMock, patch

from zstacklib.utils import pci


# ---------------------------------------------------------------------------
# Shared XML templates
# ---------------------------------------------------------------------------

VM_XML_NO_PASSTHROUGH = """\
<domain type='kvm'>
  <uuid>aabbccdd-1122-3344-5566-778899aabbcc</uuid>
  <devices>
    <disk type='file' device='disk'>
      <source file='/data/vm.qcow2'/>
      <target dev='vda' bus='virtio'/>
    </disk>
    <interface type='bridge'>
      <source bridge='br0'/>
    </interface>
  </devices>
</domain>"""

VM_XML_WITH_PCI_PASSTHROUGH = """\
<domain type='kvm'>
  <uuid>aabbccdd-1122-3344-5566-778899aabbcc</uuid>
  <devices>
    <disk type='file' device='disk'>
      <source file='/data/vm.qcow2'/>
      <target dev='vda' bus='virtio'/>
    </disk>
    <hostdev mode='subsystem' type='pci' managed='yes'>
      <source>
        <address domain='0x0000' bus='0x3b' slot='0x00' function='0x0'/>
      </source>
      <alias name='hostdev0'/>
      <address type='pci' domain='0x0000' bus='0x05' slot='0x00' function='0x0'/>
    </hostdev>
  </devices>
</domain>"""

VM_XML_WITH_MDEV_PASSTHROUGH = """\
<domain type='kvm'>
  <uuid>aabbccdd-1122-3344-5566-778899aabbcc</uuid>
  <devices>
    <hostdev mode='subsystem' type='mdev' managed='no' model='vfio-pci' display='off'>
      <source>
        <address uuid='a297db4a-f4c2-11e6-90f5-d3b88d6c9525'/>
      </source>
      <alias name='hostdev0'/>
      <address type='pci' domain='0x0000' bus='0x06' slot='0x00' function='0x0'/>
    </hostdev>
  </devices>
</domain>"""

VM_XML_WITH_BOTH = """\
<domain type='kvm'>
  <uuid>aabbccdd-1122-3344-5566-778899aabbcc</uuid>
  <devices>
    <hostdev mode='subsystem' type='pci' managed='yes'>
      <source>
        <address domain='0x0000' bus='0x3b' slot='0x00' function='0x0'/>
      </source>
      <alias name='hostdev0'/>
    </hostdev>
    <hostdev mode='subsystem' type='mdev' managed='no' model='vfio-pci'>
      <source>
        <address uuid='a297db4a-f4c2-11e6-90f5-d3b88d6c9525'/>
      </source>
      <alias name='hostdev1'/>
    </hostdev>
  </devices>
</domain>"""

VM_XML_HOSTDEV_WITHOUT_ALIAS = """\
<domain type='kvm'>
  <uuid>aabbccdd-1122-3344-5566-778899aabbcc</uuid>
  <devices>
    <hostdev mode='subsystem' type='pci' managed='yes'>
      <source>
        <address domain='0x0000' bus='0x3b' slot='0x00' function='0x0'/>
      </source>
    </hostdev>
  </devices>
</domain>"""

VM_XML_NO_DEVICES = """\
<domain type='kvm'>
  <uuid>aabbccdd-1122-3344-5566-778899aabbcc</uuid>
</domain>"""


def _make_vm_dom(xml, uuid_str="aabbccdd112233445566778899aabbcc"):
    """Create a mock libvirt domain returning *xml* from XMLDesc()."""
    dom = MagicMock()
    dom.UUIDString.return_value = uuid_str
    dom.XMLDesc.return_value = xml
    return dom


# ===================================================================
# PCI early return
# ===================================================================

class TestGetPciPassthroughMappingEarlyReturn:
    """VM without PCI hostdev should return {} without querying QEMU."""

    @patch("zstacklib.utils.pci._query_pci_info_by_qmp")
    def test_no_pci_hostdev_skips_qemu_query(self, mock_qmp):
        dom = _make_vm_dom(VM_XML_NO_PASSTHROUGH)
        result = pci.get_pci_passthrough_mapping(dom)

        assert result == {}
        mock_qmp.assert_not_called()

    @patch("zstacklib.utils.pci._query_pci_info_by_qmp")
    def test_only_mdev_hostdev_skips_pci_query(self, mock_qmp):
        """VM with mdev but no PCI hostdev should still skip PCI query."""
        dom = _make_vm_dom(VM_XML_WITH_MDEV_PASSTHROUGH)
        result = pci.get_pci_passthrough_mapping(dom)

        assert result == {}
        mock_qmp.assert_not_called()

    @patch("zstacklib.utils.pci._query_pci_info_by_qmp")
    def test_hostdev_without_alias_skips_query(self, mock_qmp):
        """PCI hostdev without <alias> element produces empty aliases list."""
        dom = _make_vm_dom(VM_XML_HOSTDEV_WITHOUT_ALIAS)
        result = pci.get_pci_passthrough_mapping(dom)

        assert result == {}
        mock_qmp.assert_not_called()

    @patch("zstacklib.utils.pci._query_pci_info_by_qmp")
    def test_no_devices_element_returns_empty(self, mock_qmp):
        """VM XML without <devices> element should return {} without crash."""
        dom = _make_vm_dom(VM_XML_NO_DEVICES)
        result = pci.get_pci_passthrough_mapping(dom)

        assert result == {}
        mock_qmp.assert_not_called()

    @patch("time.sleep")
    @patch("zstacklib.utils.pci._query_pci_info_by_qmp")
    def test_with_pci_hostdev_calls_qemu_query(self, mock_qmp, _mock_sleep):
        """VM WITH PCI hostdev should still query QEMU."""
        mock_qmp.return_value = (0, '{"return": []}', "")
        dom = _make_vm_dom(VM_XML_WITH_PCI_PASSTHROUGH)
        pci.get_pci_passthrough_mapping(dom)

        mock_qmp.assert_called()


# ===================================================================
# mdev early return
# ===================================================================

class TestGetMdevPassthroughMappingEarlyReturn:
    """VM without mdev hostdev should return {} without querying QEMU."""

    @patch("zstacklib.utils.pci._query_pci_info_by_qmp")
    def test_no_mdev_hostdev_skips_qemu_query(self, mock_qmp):
        dom = _make_vm_dom(VM_XML_NO_PASSTHROUGH)
        result = pci.get_mdev_passthrough_mapping(dom)

        assert result == {}
        mock_qmp.assert_not_called()

    @patch("zstacklib.utils.pci._query_pci_info_by_qmp")
    def test_only_pci_hostdev_skips_mdev_query(self, mock_qmp):
        """VM with PCI but no mdev hostdev should skip mdev query."""
        dom = _make_vm_dom(VM_XML_WITH_PCI_PASSTHROUGH)
        result = pci.get_mdev_passthrough_mapping(dom)

        assert result == {}
        mock_qmp.assert_not_called()

    @patch("zstacklib.utils.pci._query_pci_info_by_qmp")
    def test_no_devices_element_returns_empty(self, mock_qmp):
        """VM XML without <devices> element should return {} without crash."""
        dom = _make_vm_dom(VM_XML_NO_DEVICES)
        result = pci.get_mdev_passthrough_mapping(dom)

        assert result == {}
        mock_qmp.assert_not_called()

    @patch("time.sleep")
    @patch("zstacklib.utils.pci._query_pci_info_by_qmp")
    def test_with_mdev_hostdev_calls_qemu_query(self, mock_qmp, _mock_sleep):
        """VM WITH mdev hostdev should still query QEMU."""
        mock_qmp.return_value = (0, '{"return": []}', "")
        dom = _make_vm_dom(VM_XML_WITH_MDEV_PASSTHROUGH)
        pci.get_mdev_passthrough_mapping(dom)

        mock_qmp.assert_called()


# ===================================================================
# Defense-in-depth: _query_vm_pci_address_mapping
# ===================================================================

class TestQueryVmPciAddressMappingEmptyAliases:
    """Shared query function should also bail on empty aliases."""

    @patch("zstacklib.utils.pci._query_pci_info_by_qmp")
    def test_empty_aliases_returns_immediately(self, mock_qmp):
        result = pci._query_vm_pci_address_mapping(
            "fake-uuid", [], {}, lambda *a: ("k", "v"))

        assert result == {}
        mock_qmp.assert_not_called()

    @patch("time.sleep")
    @patch("zstacklib.utils.pci._query_pci_info_by_qmp")
    def test_non_empty_aliases_queries_qemu(self, mock_qmp, _mock_sleep):
        mock_qmp.return_value = (0, '{"return": []}', "")
        builder = MagicMock(return_value=("k", "v"))
        pci._query_vm_pci_address_mapping(
            "fake-uuid", ["alias0"], {"alias0": "0000:3b:00.0"}, builder)

        mock_qmp.assert_called()


# ===================================================================
# Mixed scenario: each function filters only its own device type
# ===================================================================

class TestMixedPassthroughDevices:
    """VM with both PCI and mdev hostdevs: each function filters only its type."""

    @patch("zstacklib.utils.pci._query_vm_pci_address_mapping")
    def test_pci_mapping_extracts_only_pci_aliases(self, mock_query):
        """get_pci_passthrough_mapping should pass only PCI hostdev aliases."""
        mock_query.return_value = {}
        dom = _make_vm_dom(VM_XML_WITH_BOTH)
        pci.get_pci_passthrough_mapping(dom)

        mock_query.assert_called_once()
        aliases = mock_query.call_args[0][1]
        assert aliases == ["hostdev0"], \
            "expected only PCI alias 'hostdev0', got {}".format(aliases)

    @patch("zstacklib.utils.pci._query_vm_pci_address_mapping")
    def test_mdev_mapping_extracts_only_mdev_aliases(self, mock_query):
        """get_mdev_passthrough_mapping should pass only mdev hostdev aliases."""
        mock_query.return_value = {}
        dom = _make_vm_dom(VM_XML_WITH_BOTH)
        pci.get_mdev_passthrough_mapping(dom)

        mock_query.assert_called_once()
        aliases = mock_query.call_args[0][1]
        assert aliases == ["hostdev1"], \
            "expected only mdev alias 'hostdev1', got {}".format(aliases)

    @patch("zstacklib.utils.pci._query_vm_pci_address_mapping")
    def test_pci_mapping_collects_host_address(self, mock_query):
        """alias_to_host should map PCI alias to the host source address."""
        mock_query.return_value = {}
        dom = _make_vm_dom(VM_XML_WITH_BOTH)
        pci.get_pci_passthrough_mapping(dom)

        alias_to_host = mock_query.call_args[0][2]
        assert "hostdev0" in alias_to_host
        assert alias_to_host["hostdev0"] == "0000:3b:00.0"
        assert "hostdev1" not in alias_to_host

    @patch("zstacklib.utils.pci._query_vm_pci_address_mapping")
    def test_mdev_mapping_collects_host_uuid(self, mock_query):
        """alias_to_host should map mdev alias to the source UUID (no dashes)."""
        mock_query.return_value = {}
        dom = _make_vm_dom(VM_XML_WITH_BOTH)
        pci.get_mdev_passthrough_mapping(dom)

        alias_to_host = mock_query.call_args[0][2]
        assert "hostdev1" in alias_to_host
        assert alias_to_host["hostdev1"] == "a297db4af4c211e690f5d3b88d6c9525"
        assert "hostdev0" not in alias_to_host


# ===================================================================
# Retry behavior
# ===================================================================

class TestRetryBehavior:
    """_query_vm_pci_address_mapping retry logic with non-empty aliases."""

    @patch("time.sleep")
    @patch("zstacklib.utils.pci._query_pci_info_by_qmp")
    def test_retries_on_empty_parse_result(self, mock_qmp, mock_sleep):
        """Should retry 3 times when QEMU returns data but no aliases match."""
        mock_qmp.return_value = (0, '{"return": []}', "")
        result = pci._query_vm_pci_address_mapping(
            "fake-uuid", ["alias0"], {"alias0": "0000:3b:00.0"},
            lambda *a: ("k", "v"))

        assert result == {}
        assert mock_qmp.call_count == 3
        assert mock_sleep.call_count == 2  # sleep between retries, not after last

    @patch("time.sleep")
    @patch("zstacklib.utils.pci._query_pci_info_by_qmp")
    def test_retries_on_qemu_command_failure(self, mock_qmp, mock_sleep):
        """Should retry when virsh qemu-monitor-command fails (r != 0)."""
        mock_qmp.return_value = (1, "", "connection refused")
        result = pci._query_vm_pci_address_mapping(
            "fake-uuid", ["alias0"], {"alias0": "0000:3b:00.0"},
            lambda *a: ("k", "v"))

        assert result == {}
        assert mock_qmp.call_count == 3

    @patch("time.sleep")
    @patch("zstacklib.utils.pci._query_pci_info_by_qmp")
    def test_returns_on_first_successful_parse(self, mock_qmp, mock_sleep):
        """Should return immediately when a matching mapping is found."""
        # Simulate QEMU output with a matching PCI device
        qemu_output = (
            "  Bus  0, device   5, function 0:\n"
            "    id \"hostdev0\"\n"
        )
        mock_qmp.return_value = (0, qemu_output, "")
        result = pci._query_vm_pci_address_mapping(
            "fake-uuid", ["hostdev0"], {"hostdev0": "0000:3b:00.0"},
            lambda dev_info, alias, a2h: (
                "{:04x}:{:02x}:{:02x}.{:x}".format(0, *dev_info), a2h[alias]))

        assert mock_qmp.call_count == 1
        mock_sleep.assert_not_called()
        assert "0000:3b:00.0" in result.values()


# ===================================================================
# Multi-alias completion check (regression for "条件判断过宽")
# ===================================================================

def _make_qemu_output(device_entries):
    """Build QEMU 'info pci' output from (bus, device, func, alias) tuples."""
    lines = []
    for bus, device, func, alias in device_entries:
        lines.append("  Bus  {}, device   {}, function {}:".format(bus, device, func))
        lines.append('    id "{}"'.format(alias))
    return "\n".join(lines)


def _pci_builder(dev_info, alias, a2h):
    bus, device, function = dev_info
    vm_addr = "{:04x}:{:02x}:{:02x}.{:x}".format(0, bus, device, function)
    return vm_addr, a2h[alias]


class TestMultiAliasCompletionCheck:
    """Retry must wait for ALL aliases to be resolved, not just the first."""

    @patch("time.sleep")
    @patch("zstacklib.utils.pci._query_pci_info_by_qmp")
    def test_partial_result_triggers_retry(self, mock_qmp, mock_sleep):
        """With 3 aliases, finding only 1 should NOT exit early."""
        partial_output = _make_qemu_output([(0, 5, 0, "hostdev0")])
        full_output = _make_qemu_output([
            (0, 5, 0, "hostdev0"),
            (0, 6, 0, "hostdev1"),
            (0, 7, 0, "hostdev2"),
        ])
        mock_qmp.side_effect = [
            (0, partial_output, ""),
            (0, full_output, ""),
        ]
        aliases = ["hostdev0", "hostdev1", "hostdev2"]
        a2h = {
            "hostdev0": "0000:3b:00.0",
            "hostdev1": "0000:3c:00.0",
            "hostdev2": "0000:3d:00.0",
        }

        result = pci._query_vm_pci_address_mapping("fake-uuid", aliases, a2h, _pci_builder)

        assert mock_qmp.call_count == 2, "should retry after partial result"
        assert len(result) == 3, "expected all 3 mappings, got {}".format(len(result))
        assert set(result.values()) == {"0000:3b:00.0", "0000:3c:00.0", "0000:3d:00.0"}

    @patch("time.sleep")
    @patch("zstacklib.utils.pci._query_pci_info_by_qmp")
    def test_accumulates_across_retries(self, mock_qmp, mock_sleep):
        """Mappings from earlier retries are preserved even if later ones add more."""
        output_ab = _make_qemu_output([
            (0, 5, 0, "hostdev0"),
            (0, 6, 0, "hostdev1"),
        ])
        output_c_only = _make_qemu_output([(0, 7, 0, "hostdev2")])
        mock_qmp.side_effect = [
            (0, output_ab, ""),
            (0, output_c_only, ""),
        ]
        aliases = ["hostdev0", "hostdev1", "hostdev2"]
        a2h = {
            "hostdev0": "0000:3b:00.0",
            "hostdev1": "0000:3c:00.0",
            "hostdev2": "0000:3d:00.0",
        }

        result = pci._query_vm_pci_address_mapping("fake-uuid", aliases, a2h, _pci_builder)

        assert mock_qmp.call_count == 2
        assert len(result) == 3, "should accumulate across retries"

    @patch("time.sleep")
    @patch("zstacklib.utils.pci._query_pci_info_by_qmp")
    def test_returns_partial_after_exhausting_retries(self, mock_qmp, mock_sleep):
        """When retries are exhausted, return whatever partial mapping we have."""
        partial_output = _make_qemu_output([(0, 5, 0, "hostdev0")])
        mock_qmp.return_value = (0, partial_output, "")

        aliases = ["hostdev0", "hostdev1"]
        a2h = {"hostdev0": "0000:3b:00.0", "hostdev1": "0000:3c:00.0"}

        result = pci._query_vm_pci_address_mapping("fake-uuid", aliases, a2h, _pci_builder)

        assert mock_qmp.call_count == 3, "should exhaust all retries"
        assert len(result) == 1, "should return partial result"
        assert "0000:3b:00.0" in result.values()

    @patch("time.sleep")
    @patch("zstacklib.utils.pci._query_pci_info_by_qmp")
    def test_single_alias_returns_immediately(self, mock_qmp, mock_sleep):
        """Single alias: finding it means all aliases resolved, no extra retry."""
        output = _make_qemu_output([(0, 5, 0, "hostdev0")])
        mock_qmp.return_value = (0, output, "")

        result = pci._query_vm_pci_address_mapping(
            "fake-uuid", ["hostdev0"], {"hostdev0": "0000:3b:00.0"}, _pci_builder)

        assert mock_qmp.call_count == 1
        mock_sleep.assert_not_called()
        assert len(result) == 1
