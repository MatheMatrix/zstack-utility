from unittest import TestCase

from kvmagent.plugins import host_plugin


class TestHuaweiGpuInfo(TestCase):
    def setUp(self):
        self.originals = []
        self.product_output = ""
        self.replace(host_plugin, "bash_ro", lambda cmd: (0, "NPU ID: 0"))
        self.replace(host_plugin, "bash_roe", self.bash_roe)
        self.replace(host_plugin.gpu, "get_huawei_gpu_npu_id_cmd", lambda: "npu-list")
        self.replace(host_plugin.gpu, "get_huawei_npu_id", lambda output: ["0"])
        self.replace(host_plugin.gpu, "get_huawei_gpu_basic_info_cmd", lambda npu_id: "board-info")
        self.replace(
            host_plugin.gpu,
            "parse_huawei_gpu_output_by_npu_id",
            lambda output: [{"pciAddress": "0000:17:00.0"}],
        )
        self.replace(host_plugin.gpu, "check_huawei_npu_is_isolated", lambda npu_id, npu_ids: False)
        self.replace(host_plugin.gpu, "get_huawei_gpu_product_name_cmd", lambda npu_ids: "product-info")
        self.replace(host_plugin.gpu, "get_huawei_gpu_aios_rank_table_dict", lambda npu_ids: {})

    def tearDown(self):
        for target, name, original in reversed(self.originals):
            setattr(target, name, original)

    def replace(self, target, name, value):
        self.originals.append((target, name, getattr(target, name)))
        setattr(target, name, value)

    def bash_roe(self, cmd, *args, **kwargs):
        if cmd == "product-info":
            return 0, self.product_output, ""
        return 0, "", ""

    def collect(self, product_output):
        self.product_output = product_output
        device = host_plugin.PciDeviceTO()
        device.pciDeviceAddress = "0000:17:00.0"
        device.device = "Device d500"
        device.name = "Huawei Device d500"

        host = host_plugin.HostPlugin.__new__(host_plugin.HostPlugin)
        host._collect_huawei_gpu_info(device)

        return device

    def test_product_type_updates_device_and_name(self):
        device = self.collect("Product Type : Atlas 300I Pro")

        self.assertEqual("Atlas 300I Pro", device.device)
        self.assertEqual("Atlas 300I Pro", device.name)

    def test_unsupported_product_query_preserves_lspci_identity(self):
        device = self.collect("This command is not support")

        self.assertEqual("Device d500", device.device)
        self.assertEqual("Huawei Device d500", device.name)
