import json
from unittest.mock import MagicMock, mock_open, patch

from zstacklib.utils import http
from zbsprimarystorage import zbsagent


def test_reads_physical_server_serial_number_from_sysfs():
    serial_file = mock_open(read_data="  PS-SN-001\n")
    with patch.object(zbsagent, "_physical_server_serial_number", None), \
            patch("builtins.open", serial_file), \
            patch.object(zbsagent.shell, "call") as shell_call:
        assert zbsagent.read_physical_server_serial_number() == "PS-SN-001"
        assert zbsagent.read_physical_server_serial_number() == "PS-SN-001"
    serial_file.assert_called_once_with('/sys/class/dmi/id/product_serial')
    shell_call.assert_not_called()


def test_falls_back_to_dmidecode_for_physical_server_serial_number():
    with patch.object(zbsagent, "_physical_server_serial_number", None), \
            patch("builtins.open", side_effect=IOError), \
            patch.object(zbsagent.shell, "call", return_value="PS-SN-002\n"):
        assert zbsagent.read_physical_server_serial_number() == "PS-SN-002"


def test_sync_metadata_reports_physical_server_serial_number():
    agent = zbsagent.ZbsAgent.__new__(zbsagent.ZbsAgent)
    address = MagicMock()
    address.address = "10.0.0.10"
    mds_status = json.dumps({
        "result": [{"externalAddr": "10.0.0.10:10200"}],
        "error": {"message": ""},
    })
    request = {
        http.REQUEST_BODY: json.dumps({
            "addr": "10.0.0.10",
            "agentVersion": "5.5.38",
        })
    }

    with patch.object(zbsagent.zbsutils, "query_mds_status_info", return_value=mds_status), \
            patch.object(zbsagent.iproute, "query_addresses", return_value=[address]), \
            patch.object(zbsagent.zbsutils, "is_support_get_volume_clients", return_value=True), \
            patch.object(zbsagent, "read_physical_server_serial_number", return_value="PS-SN-001"):
        response = json.loads(agent.sync_metadata(request))

    assert response["success"] is True
    assert response["externalAddr"] == "10.0.0.10:10200"
    assert response["physicalServerSerialNumber"] == "PS-SN-001"
