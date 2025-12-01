'''
Hygon Device Plugin - standalone Hygon CCP device management plugin

@author: malin
@date: 2025
'''

from kvmagent import kvmagent
from zstacklib.utils import jsonobject, bash, http, linux
from zstacklib.utils import log
from zstacklib.utils.bash import *
import os
import functools

logger = log.get_logger(__name__)


def require_hygon_tools(response_class):
    """
    Decorator to check if Hygon tools are available before executing endpoint methods.

    This decorator eliminates the need for manual "if not self.tools_available" checks
    in each endpoint method.

    Args:
        response_class: The response class to instantiate if tools are unavailable

    Usage:
        @require_hygon_tools(GetHygonCcpDevicesResponse)
        @kvmagent.replyerror
        @in_bash
        def get_hygon_ccp_devices(self, req):
            # Method implementation without manual tool checking
            ...
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(self, *args, **kwargs):
            if not self.tools_available:
                rsp = response_class()
                rsp.success = False
                rsp.error = "Hygon tools not available. Required tools: %s, %s" % (
                    self.HCT_CCP_BIND_SCRIPT,
                    self.HCTCONFIG_SCRIPT
                )
                return jsonobject.dumps(rsp)
            return func(self, *args, **kwargs)
        return wrapper
    return decorator


class GetHygonCcpDevicesResponse(kvmagent.AgentResponse):
    def __init__(self):
        super(GetHygonCcpDevicesResponse, self).__init__()
        self.devices = []


class GenerateHygonMdevDevicesRsp(kvmagent.AgentResponse):
    def __init__(self):
        super(GenerateHygonMdevDevicesRsp, self).__init__()
        self.mdevBindings = []


class UngenerateHygonMdevDevicesRsp(kvmagent.AgentResponse):
    def __init__(self):
        super(UngenerateHygonMdevDevicesRsp, self).__init__()


class HygonDevicePlugin(kvmagent.KvmAgent):
    """
    Hygon CCP Device Plugin

    Manages Hygon CCP (Cryptographic Co-Processor) devices and their mdev virtualization.
    This plugin is loaded independently and only activates if Hygon tools are available.
    """

    # Hygon tool paths (hardcoded, following project style)
    HCT_CCP_BIND_SCRIPT = "/opt/hygon/hct/hct/script/hct_ccp_bind.py"
    HCTCONFIG_SCRIPT = "/opt/hygon/hct/hct/script/hctconfig"

    # HTTP endpoints
    GET_HYGON_CCP_DEVICES = "/hygonccpdevice/get"
    GENERATE_HYGON_MDEV_DEVICES = "/hygonmdevdevice/generate"
    UNGENERATE_HYGON_MDEV_DEVICES = "/hygonmdevdevice/ungenerate"

    # Hygon CCP Device IDs (from hct_ccp_bind.py output)
    # These IDs are used to verify we're detecting genuine Hygon CCP devices
    HYGON_VENDOR_NAME = "Chengdu Haiguang IC Design Co., Ltd."
    HYGON_CCP_DEVICE_IDS = {
        "1456": "PSPCCP Command DMA Processor",
        "1468": "NTBCCP"
    }

    # Mdev use flag constants (from sysfs vendor/use attribute)
    MDEV_USED_BY_VM = 1  # Passthrough to vm

    def __init__(self):
        self.config = None
        self.tools_available = False

    def configure(self, config):
        self.config = config

    def start(self):
        """Initialize plugin and register HTTP routes if tools are available"""
        self.tools_available = self._check_tools_availability()

        if not self.tools_available:
            logger.warning("Hygon tools not available, plugin will not handle requests")
            return

        # Register HTTP routes
        http_server = kvmagent.get_http_server()
        http_server.register_async_uri(self.GET_HYGON_CCP_DEVICES, self.get_hygon_ccp_devices)
        http_server.register_async_uri(self.GENERATE_HYGON_MDEV_DEVICES, self.generate_hygon_mdev_devices)
        http_server.register_async_uri(self.UNGENERATE_HYGON_MDEV_DEVICES, self.ungenerate_hygon_mdev_devices)

        logger.info("Hygon device plugin started successfully")

    def stop(self):
        """Cleanup when plugin stops"""
        pass

    def _check_tools_availability(self):
        """Check if Hygon tools (hct_ccp_bind.py and hctconfig) are available"""
        hct_exists = os.path.exists(self.HCT_CCP_BIND_SCRIPT)
        hctconfig_exists = os.path.exists(self.HCTCONFIG_SCRIPT)

        if hct_exists and hctconfig_exists:
            logger.debug("Hygon tools are available: %s and %s" % (self.HCT_CCP_BIND_SCRIPT, self.HCTCONFIG_SCRIPT))
            return True
        else:
            missing = []
            if not hct_exists:
                missing.append(self.HCT_CCP_BIND_SCRIPT)
            if not hctconfig_exists:
                missing.append(self.HCTCONFIG_SCRIPT)
            logger.debug("Hygon tools not available. Missing: %s" % ", ".join(missing))
            return False

    def _check_hygon_ccp_devices_exist(self):
        """
        Check if genuine Hygon CCP devices exist on the system

        This method performs a more rigorous check than simple grep to avoid false positives.
        It validates both vendor name and device IDs to ensure we only detect Hygon CCP devices.

        Checks performed:
            1. Search for Hygon vendor name in lspci output
            2. Verify device IDs match known Hygon CCP device types (PSPCCP/NTBCCP)

        lspci Output Format:
            05:00.2 Encryption controller: Chengdu Haiguang IC Design Co., Ltd. PSPCCP Command DMA Processor
            06:00.1 Encryption controller: Chengdu Haiguang IC Design Co., Ltd. NTBCCP

        Returns:
            bool: True if Hygon CCP devices found, False otherwise
        """
        # First, check if there are any devices from Hygon vendor
        r, o, e = bash_roe("timeout 60 lspci | grep '%s'" % self.HYGON_VENDOR_NAME)
        if r == 124:
            logger.warn("lspci command timeout after 60s when checking vendor: %s" % self.HYGON_VENDOR_NAME)
            return False
        if r != 0 or not o.strip():
            logger.debug("No devices found from vendor: %s" % self.HYGON_VENDOR_NAME)
            return False

        # Second, verify that these devices are CCP devices by checking device IDs
        # Use lspci -nn to get numeric device IDs
        r, o, e = bash_roe("timeout 60 lspci -nn | grep '%s'" % self.HYGON_VENDOR_NAME)
        if r == 124:
            logger.warn("lspci -nn command timeout after 60s when checking vendor: %s" % self.HYGON_VENDOR_NAME)
            return False
        if r != 0:
            logger.debug("Failed to get detailed device info via lspci -nn for vendor: %s" % self.HYGON_VENDOR_NAME)
            return False

        # Check if any line contains known CCP device IDs
        lines = o.strip().split('\n')
        for line in lines:
            for device_id in self.HYGON_CCP_DEVICE_IDS.keys():
                if device_id in line:
                    logger.debug("Found Hygon CCP device (ID: %s) in: %s" % (device_id, line))
                    return True

        logger.debug("Found vendor devices but none match known CCP device IDs: %s" % list(self.HYGON_CCP_DEVICE_IDS.keys()))
        return False

    def _parse_ccp_devices(self):
        """
        Parse CCP devices from hct_ccp_bind.py -s output

        Script Command:
            python /opt/hygon/hct/hct/script/hct_ccp_bind.py -s

        Expected Output Format:
            The script outputs device information grouped by categories.
            We focus on "Crypto devices" sections (both DPDK-compatible and kernel driver).

            Example output:
            -----------------------------------------------------------------------
            Crypto devices using DPDK-compatible driver
            ===========================================
            0000:06:00.1 'NTBCCP 1468' drv=hct unused=vfio-pci
            0000:23:00.2 'PSPCCP Command DMA Processor 1456' drv=hct unused=vfio-pci
            0000:24:00.1 'NTBCCP 1468' drv=hct unused=vfio-pci

            Crypto devices using kernel driver
            ==================================
            0000:05:00.2 'PSPCCP Command DMA Processor 1456' drv=ccp unused=vfio-pci,hct
            -----------------------------------------------------------------------

        Parsing Logic:
            Each device line format: <PCI_BDF> '<Device_Type> <Device_ID>' drv=<driver> unused=<unused>
            - parts[0]: PCI Bus:Device.Function (e.g., "0000:06:00.1")
            - parts[1]: Device type with leading quote (e.g., "'NTBCCP" or "'PSPCCP")
            - parts[2]: Device ID with trailing quote (e.g., "1468'" or "1456'")
            - parts[3]: Driver status (e.g., "drv=hct" or "drv=ccp")

            Lines with fewer than 4 parts are skipped (headers, empty lines, etc.)

        Returns:
            list: List of CCP device dictionaries with keys:
                - pciBdf (str): PCI address (e.g., "0000:06:00.1")
                - deviceType (str): Device type with quote (e.g., "'NTBCCP")
                - deviceId (str): Device ID with quote (e.g., "1468'")
                - driverStatus (str): Current driver binding (e.g., "drv=hct")

        Raises:
            Exception: If failed to execute hct_ccp_bind.py or parse output
        """
        r, o, e = bash_roe("timeout 60 python %s -s" % self.HCT_CCP_BIND_SCRIPT)
        if r == 124:
            raise Exception("hct_ccp_bind.py -s timeout after 60s")
        if r != 0:
            raise Exception("failed to get CCP devices: %s" % e)

        devices = []
        lines = o.strip().split('\n')
        for line in lines:
            line = line.strip()
            if not line:
                continue

            parts = line.split()

            # Strict validation: only accept genuine device lines
            # Valid format: 0000:06:00.1 'NTBCCP 1468' drv=hct unused=vfio-pci
            if (
                len(parts) < 4
                or ":" not in parts[0]              # PCI BDF must contain ':'
                or not parts[1].startswith("'")     # deviceType must start with '
                or not parts[2].endswith("'")       # deviceId must end with '
                or not parts[3].startswith("drv=")  # driverStatus must start with 'drv='
            ):
                logger.debug("skip non-device line from script output: %s" % line)
                continue

            devices.append({
                'pciBdf': parts[0],
                'deviceType': parts[1],
                'deviceId': parts[2],
                'driverStatus': parts[3]
            })
        return devices

    @require_hygon_tools(GetHygonCcpDevicesResponse)
    @kvmagent.replyerror
    @in_bash
    def get_hygon_ccp_devices(self, req):
        """
        Get Hygon CCP devices list

        This endpoint queries the host for available Hygon CCP devices using hct_ccp_bind.py.

        Scripts Used:
            1. lspci | grep 'Chengdu Haiguang IC Design Co., Ltd.'
               - Check for Hygon vendor devices
               - Prevents false positives from devices with "CCP" in other names

            2. lspci -nn | grep 'Chengdu Haiguang IC Design Co., Ltd.'
               - Get numeric device IDs: [1d94:1456] or [1d94:1468]
               - Validates device IDs against known CCP types:
                 * 1456: PSPCCP Command DMA Processor
                 * 1468: NTBCCP
               - Only proceed if genuine Hygon CCP devices found

            3. python /opt/hygon/hct/hct/script/hct_ccp_bind.py -s
               - Lists all CCP devices with detailed information
               - See _parse_ccp_devices() for output format details

            4. python /opt/hygon/hct/hct/script/hct_ccp_bind.py --get_master_pspccp
               - Returns the PCI address of the master PSP device
               - Output format: Single line with PCI BDF (e.g., "0000:05:00.2")
               - Used to mark which device is the master PSP

        Response Format:
            {
                "success": true,
                "error": "",
                "devices": [
                    {
                        "pciBdf": "0000:06:00.1",
                        "deviceType": "'NTBCCP",
                        "deviceId": "1468'",
                        "driverStatus": "drv=hct",
                        "isMasterPsp": false,
                        "vendorIdx": null,
                        "state": "Enabled"
                    },
                    ...
                ]
            }
        """
        cmd = jsonobject.loads(req[http.REQUEST_BODY])
        rsp = GetHygonCcpDevicesResponse()

        # Check if there are genuine Hygon CCP devices
        # This performs vendor and device ID validation to avoid false positives
        if not self._check_hygon_ccp_devices_exist():
            # No Hygon CCP devices found
            rsp.devices = []
            return jsonobject.dumps(rsp)

        # Parse CCP devices using helper method
        try:
            ccp_device_list = self._parse_ccp_devices()
        except Exception as e:
            rsp.success = False
            rsp.error = str(e)
            return jsonobject.dumps(rsp)

        # Check if parsing returned any devices (TOCTOU protection)
        if not ccp_device_list:
            rsp.devices = []
            return jsonobject.dumps(rsp)

        # Convert to JsonObject format
        devices = []
        for device_info in ccp_device_list:
            device = jsonobject.JSONObject()
            device.pciBdf = device_info['pciBdf']
            device.deviceType = device_info['deviceType']
            device.deviceId = device_info['deviceId']
            device.driverStatus = device_info['driverStatus']
            device.isMasterPsp = False
            device.vendorIdx = None
            device.state = "Enabled"
            devices.append(device)

        # Get Master PSP via hct_ccp_bind.py --get_master_pspccp
        r, o, e = bash_roe("timeout 60 python %s --get_master_pspccp" % self.HCT_CCP_BIND_SCRIPT)
        if r == 124:
            logger.warning("hct_ccp_bind.py --get_master_pspccp timeout after 60s")
        elif r == 0 and o.strip():
            master_psp = o.strip()
            for device in devices:
                if device.pciBdf == master_psp:
                    device.isMasterPsp = True
                    break
        else:
            logger.warning("failed to get master PSP: %s" % e)

        rsp.devices = devices
        return jsonobject.dumps(rsp)

    @require_hygon_tools(GenerateHygonMdevDevicesRsp)
    @kvmagent.replyerror
    @in_bash
    def generate_hygon_mdev_devices(self, req):
        """
        Generate Hygon mdev devices

        This endpoint calls hctconfig to generate mdev (mediated device) instances
        from Hygon CCP physical devices for VM assignment.

        Script Command:
            bash /opt/hygon/hct/hct/script/hctconfig start -p <maxProgress> -q <maxQemuNum>

            Parameters:
                -p <maxProgress>: Max host processes per CCP device (default: 128)
                    - Creates (CCP_NUM * maxProgress) mdev devices for host processes
                    - These mdev devices have vendor/use=0 (host process usage)
                    - Example: 3 CCP devices * 128 = 384 mdev devices for host

                -q <maxQemuNum>: Max VMs per CCP device (default: 0)
                    - Creates (CCP_NUM * maxQemuNum) mdev devices for VMs
                    - These mdev devices have vendor/use=1 (VM usage)
                    - Example: 3 CCP devices * 64 = 192 mdev devices for VMs

            This command creates mdev devices under /sys/bus/mdev/devices/

        Mdev Device Sysfs Structure:
            /sys/bus/mdev/devices/<mdev_uuid>/
                vendor/
                    use    - Device usage flag (0: host process, 1: VM, 2: reserved)
                    idx    - Vendor index mapping to physical CCP device

            Example:
                /sys/bus/mdev/devices/12345678-1234-1234-1234-123456789abc/
                    vendor/use  -> contains "1" (VM device)
                    vendor/idx  -> contains "0" (maps to first hct-bound CCP device)

        Vendor Index Mapping Logic:
            The vendor_idx corresponds to the index of CCP devices bound to 'hct' driver.
            This matches: hct_ccp_bind.py -s | grep "drv=hct" | nl -v 0

            Example:
                If hct_ccp_bind.py -s shows:
                    0000:06:00.1 'NTBCCP 1468' drv=hct unused=vfio-pci    -> vendor_idx=0
                    0000:23:00.2 'PSPCCP...' drv=hct unused=vfio-pci      -> vendor_idx=1
                    0000:05:00.2 'PSPCCP...' drv=ccp unused=vfio-pci,hct  -> (skipped, drv=ccp)

        Response Format:
            {
                "success": true,
                "error": "",
                "mdevBindings": [
                    {
                        "mdevUuid": "12345678-1234-1234-1234-123456789abc",
                        "ccpDeviceUuid": null,  // Set by backend based on pciBdf
                        "pciBdf": "0000:06:00.1",
                        "vendorIdx": 0,
                        "useFlag": 1
                    },
                    ...
                ]
            }
        """
        cmd = jsonobject.loads(req[http.REQUEST_BODY])
        rsp = GenerateHygonMdevDevicesRsp()

        max_progress = cmd.maxProgress if hasattr(cmd, 'maxProgress') else 0
        max_qemu_num = cmd.maxQemuNum if hasattr(cmd, 'maxQemuNum') else 64

        # Call hctconfig start -p {maxProgress} -q {maxQemuNum}
        r, o, e = bash_roe("timeout 60 bash %s start -p %d -q %d" % (self.HCTCONFIG_SCRIPT, max_progress, max_qemu_num))
        if r == 124:
            rsp.success = False
            rsp.error = "hctconfig start timeout after 60s"
            return jsonobject.dumps(rsp)
        if r != 0:
            rsp.success = False
            rsp.error = "failed to start hctconfig: %s" % e
            return jsonobject.dumps(rsp)

        # Parse CCP devices using helper method
        try:
            ccp_devices_by_idx = self._parse_ccp_devices()
        except Exception as e:
            rsp.success = False
            rsp.error = str(e)
            return jsonobject.dumps(rsp)

        # Build vendor_idx to pciBdf mapping (only for devices bound to hct driver)
        # IMPORTANT: Sort by pciBdf to ensure stable vendor_idx mapping across multiple calls
        # If the script output order changes, unsorted mapping would break existing VM bindings
        vendor_idx_to_pci_bdf = {}
        hct_devices = [d for d in ccp_devices_by_idx if d['driverStatus'] == 'drv=hct']
        hct_devices_sorted = sorted(hct_devices, key=lambda x: x['pciBdf'])
        for idx, device_info in enumerate(hct_devices_sorted):
            vendor_idx_to_pci_bdf[idx] = device_info['pciBdf']

        logger.debug("Built vendor_idx to pciBdf mapping: %s" % vendor_idx_to_pci_bdf)

        # Collect mdev bindings
        mdev_bindings = self._collect_mdev_bindings(vendor_idx_to_pci_bdf)
        rsp.mdevBindings = mdev_bindings

        return jsonobject.dumps(rsp)

    def _collect_mdev_bindings(self, vendor_idx_to_pci_bdf):
        """
        Collect mdev device bindings from /sys/bus/mdev/devices/

        Only processes mdev devices that belong to Hygon CCP devices based on vendor_idx mapping.
        Other mdev devices (GPU, SR-IOV, etc.) in /sys/bus/mdev/devices/ are silently skipped.

        Args:
            vendor_idx_to_pci_bdf: Mapping from vendor_idx to PCI BDF (only for Hygon CCP devices)

        Returns:
            list: List of mdev binding JsonObjects for Hygon CCP devices only
        """
        mdev_devices_path = "/sys/bus/mdev/devices"
        mdev_bindings = []

        if not os.path.exists(mdev_devices_path):
            return mdev_bindings

        # Get the set of valid vendor_idx values for quick lookup
        valid_vendor_indices = set(vendor_idx_to_pci_bdf.keys())
        logger.debug("Valid Hygon CCP vendor indices: %s" % valid_vendor_indices)

        for mdev_uuid in os.listdir(mdev_devices_path):
            mdev_path = os.path.join(mdev_devices_path, mdev_uuid)
            vendor_use_path = os.path.join(mdev_path, "vendor", "use")
            vendor_idx_path = os.path.join(mdev_path, "vendor", "idx")

            if not os.path.exists(vendor_use_path) or not os.path.exists(vendor_idx_path):
                # This mdev device doesn't have vendor-specific attributes
                # (not a Hygon CCP device), skip silently
                continue

            try:
                with open(vendor_use_path, 'r') as f:
                    use_flag = int(f.read().strip())
                if use_flag != self.MDEV_USED_BY_VM:  # Only VM devices (use=1)
                    continue

                with open(vendor_idx_path, 'r') as f:
                    vendor_idx = int(f.read().strip())

                # Filter: only process mdev devices with vendor_idx in our Hygon CCP mapping
                # Other mdev devices (GPU, SR-IOV, etc.) are silently skipped
                if vendor_idx not in valid_vendor_indices:
                    logger.debug("skip mdev device[uuid:%s] vendor_idx=%d (not a Hygon CCP device)" % (mdev_uuid, vendor_idx))
                    continue

                # Map vendor_idx to PCI BDF (guaranteed to succeed at this point)
                pci_bdf = vendor_idx_to_pci_bdf[vendor_idx]

                binding = jsonobject.JSONObject()
                binding.mdevUuid = mdev_uuid
                binding.ccpDeviceUuid = None  # Will be set by backend based on pciBdf
                binding.pciBdf = pci_bdf  # Add pciBdf for backend mapping
                binding.vendorIdx = vendor_idx
                binding.useFlag = use_flag
                mdev_bindings.append(binding)

            except IOError as e:
                logger.warn("failed to read mdev device[uuid:%s] vendor info from path[use:%s, idx:%s], IO error: %s" %
                           (mdev_uuid, vendor_use_path, vendor_idx_path, str(e)))
                continue
            except ValueError as e:
                logger.warn("failed to parse mdev device[uuid:%s] vendor info, value error: %s" % (mdev_uuid, str(e)))
                continue
            except Exception as e:
                logger.warn("failed to process mdev device[uuid:%s], unexpected error: %s" % (mdev_uuid, str(e)))
                continue

        return mdev_bindings

    @require_hygon_tools(UngenerateHygonMdevDevicesRsp)
    @kvmagent.replyerror
    @in_bash
    def ungenerate_hygon_mdev_devices(self, req):
        """
        Ungenerate (remove) Hygon mdev devices

        This endpoint calls hctconfig stop to remove all mdev instances.

        Script Command:
            bash /opt/hygon/hct/hct/script/hctconfig stop

            This command:
                - Removes all mdev devices created under /sys/bus/mdev/devices/
                - Cleans up CCP device virtualization resources
                - Should be called before detaching or reconfiguring CCP devices

        Response Format:
            {
                "success": true,
                "error": ""
            }
        """
        cmd = jsonobject.loads(req[http.REQUEST_BODY])
        rsp = UngenerateHygonMdevDevicesRsp()

        # Call hctconfig stop
        r, o, e = bash_roe("timeout 60 bash %s stop" % self.HCTCONFIG_SCRIPT)
        if r == 124:
            rsp.success = False
            rsp.error = "hctconfig stop timeout after 60s"
            return jsonobject.dumps(rsp)
        if r != 0:
            rsp.success = False
            rsp.error = "failed to stop hctconfig: %s" % e
            return jsonobject.dumps(rsp)

        return jsonobject.dumps(rsp)
