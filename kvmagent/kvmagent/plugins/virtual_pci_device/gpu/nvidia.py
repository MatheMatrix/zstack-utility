import os
import uuid
import subprocess
import psutil
import threading
import time
from zstacklib.utils import shell, thread, log
from zstacklib.utils.bash import bash_roe
from kvmagent.plugins.virtual_pci_device.virtualization import VirtualizationHandler

# Constants
TENSOR_FUSION_WORKER_PATH = "/usr/local/bin/tensor-fusion-worker"
SHARED_MEMORY_PATH_PREFIX = "/dev/shm/"
SHARED_MEMORY_SIZE = 512 # MB

# Global state management
tensor_fusion_workers = {}  # {device_id: TensorFusionWorkerInfo}
device_allocation_lock = threading.Lock()

logger = log.get_logger(__name__)

class TensorFusionWorkerInfo:
    """TensorFusion Worker Information"""
    def __init__(self, uuid, pid, shared_memory_path, allocated_memory, pci_address, cuda_device_index):
        self.uuid = uuid
        self.pid = pid
        self.shared_memory_path = shared_memory_path
        self.allocated_memory = allocated_memory
        self.pci_address = pci_address
        self.cuda_device_index = cuda_device_index
        self.shared_memory_size = SHARED_MEMORY_SIZE


# class NvidiaSriovVirtualHandler(VirtualizationHandler):
#     """NVIDIA SRIOV Virtualization Handler"""
#     def get_all_devices(self, request):
#         # TODO: Allocate a SR-IOV VF
#         pass
#
#     def slice_device(self, config):
#         # TODO: Implement NVIDIA GPU SR-IOV slicing logic
#         pass
#
#     def reset_device(self):
#         # TODO: Reset NVIDIA GPU SR-IOV
#         pass
#
#
# class NvidiaMdevVirtualHandler(VirtualizationHandler):
#     """NVIDIA MDEV Virtualization Handler"""
#
#     def get_all_devices(self):
#         """Get all running tensorfusion processes, generate vgpu based on input variables"""
#         pass
#
#     def slice_device(self, config):
#         # TODO: Implement NVIDIA GPU MDEV slicing logic
#         pass
#
#     def reset_device(self):
#         # TODO: Reset NVIDIA GPU MDEV
#         pass


class NvidiaTensorFusionHandler(VirtualizationHandler):
    """NVIDIA TensorFusion Virtualization Handler"""

    def _scan_running_workers(self):
        """Scan all running TensorFusion worker processes"""
        scanned_workers = []

        try:
            for proc in psutil.process_iter():
                try:
                    cmdline = proc.cmdline()
                    if cmdline and TENSOR_FUSION_WORKER_PATH in ' '.join(cmdline):
                        worker_info = self._get_worker_info_from_process(proc.pid)
                        if worker_info:
                            scanned_workers.append(worker_info)
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                    continue
        except Exception as e:
            pass

        return scanned_workers

    def _find_worker_by_vm_uuid(self, vm_uuid):
        """Find existing TensorFusion worker for specific VM UUID"""
        expected_shared_memory_name = "tf_{}".format(vm_uuid)
        expected_shared_memory_path = "{}{}".format(SHARED_MEMORY_PATH_PREFIX, expected_shared_memory_name)

        # Check existing workers in global state first
        for device_uuid, worker_info in tensor_fusion_workers.items():
            if worker_info.shared_memory_path == expected_shared_memory_path:
                logger.info("Found existing TensorFusion worker in global state for VM %s with device UUID: %s",
                           vm_uuid, device_uuid)
                return worker_info

        # If not found in global state, scan running processes
        running_workers = self._scan_running_workers()
        for worker_info in running_workers:
            if worker_info.shared_memory_path == expected_shared_memory_path:
                # Add to global state for future reference
                tensor_fusion_workers[worker_info.uuid] = worker_info
                logger.info("Found existing TensorFusion worker in running processes for VM %s with device UUID: %s",
                           vm_uuid, worker_info.uuid)
                return worker_info

        return None

    def get_all_devices(self):
        """Get all running TensorFusion processes, generate vgpu based on input variables"""
        return self._scan_running_workers()

    def slice_device(self, slice_request):
        # Extract PCI address from the slice request
        pci_address = slice_request.get('pciAddress')
        vm_uuid = slice_request.get('vmUuid')

        if not pci_address:
            raise Exception("PCI address is required for TensorFusion device slicing")

        if not vm_uuid:
            raise Exception("vm uuid is required for TensorFusion device slicing")

        # Start TensorFusion worker process
        with device_allocation_lock:
            # First, check if there's already a worker for this VM
            existing_worker = self._find_worker_by_vm_uuid(vm_uuid)
            if existing_worker:
                logger.info("Reusing existing TensorFusion worker for VM %s", vm_uuid)
                return existing_worker

            # No existing worker found, create new one
            logger.info("No existing TensorFusion worker found for VM %s, creating new one", vm_uuid)
            # Get the CUDA device index corresponding to the PCI address
            cuda_device_index = self._get_nvidia_gpu_index_by_pci(pci_address)
            if cuda_device_index is None:
                raise Exception("Cannot find CUDA device index for PCI address: {}".format(pci_address))

            # Get memory size from reset_request
            memory_mb = slice_request.get('memoryMb')
            if memory_mb is None:
                raise Exception("Memory size is required for TensorFusion device slicing")

            # Generate device UUID for this worker
            device_uuid = str(uuid.uuid4())

            # Generate shared memory path using device UUID
            shared_memory_name = "tf_{}".format(vm_uuid)
            shared_memory_path = "{}{}".format(SHARED_MEMORY_PATH_PREFIX, shared_memory_name)

            # Build environment variables and command
            env_vars = {
                'CUDA_DEVICE_ORDER': 'PCI_BUS_ID',
                'CUDA_VISIBLE_DEVICES': str(cuda_device_index),
                'TF_CUDA_MEMORY_LIMIT': str(memory_mb),
                'TF_ENABLE_LOG': '1',
                'TF_DEVICE_UUID': device_uuid,
                'VM_UUID': vm_uuid
            }

            cmd_args = [
                TENSOR_FUSION_WORKER_PATH,
                '-n', 'shmem',
                '-m', "/{}".format(shared_memory_name),
                '-M', str(SHARED_MEMORY_SIZE)
            ]

            # Start worker process asynchronously
            worker_info = self._start_worker_async(
                cmd_args, env_vars, shared_memory_path,
                memory_mb, pci_address, cuda_device_index, device_uuid
            )

            # Save to global state using device UUID as key
            tensor_fusion_workers[device_uuid] = worker_info

            return worker_info

    def reset_device(self, reset_request):
        """Reset TensorFusion workers"""
        target_uuid = reset_request.get('uuid') if reset_request else None

        with device_allocation_lock:
            if target_uuid:
                # Reset specific worker by UUID
                worker_info = tensor_fusion_workers.get(target_uuid)
                if worker_info:
                    self._terminate_worker(worker_info)
                    del tensor_fusion_workers[target_uuid]
                else:
                    raise Exception("Worker with UUID {} not found".format(target_uuid))
            else:
                # Reset all workers if no UUID specified
                for device_uuid, worker_info in list(tensor_fusion_workers.items()):
                    self._terminate_worker(worker_info)
                    del tensor_fusion_workers[device_uuid]

    def reset_worker_by_shm_path(self, shm_path):
        """Terminate a TensorFusion worker by shared memory path"""
        logger.warn("[tensorfusion] start to reset %s", shm_path)
        for device_uuid, worker_info in list(tensor_fusion_workers.items()):
            logger.warn("[tensorfusion] uuid: %s, path: %s", device_uuid, worker_info.shared_memory_path)
            if worker_info.shared_memory_path == shm_path:
                self._terminate_worker(worker_info)
                del tensor_fusion_workers[device_uuid]
                break

    def get_mdev_spec(self, to):
        # TODO: HARDCODE
        """
        Mock method for TensorFusion MDEV specifications
        Returns hardcoded mdev specs for testing purposes
        """
        if to.type != "GPU_Video_Controller":
            return False

        # Define mock MDEV configurations
        MDEV_SPECS = [
            {
                'TypeId': '24G1',
                'Name': 'TensorFusion-24GB',
                'Description': 'TensorFusion 24GB Memory Single Instance',
                'Memory': '24579MB',
                'MaxInstances': '1',
                'DisplayResolution': '7680x4320',
                'FrameBufferSize': '24579MB',
                'MultiVgpu': 'No'
            },
            {
                'TypeId': '12G2',
                'Name': 'TensorFusion-12GB',
                'Description': 'TensorFusion 12GB Memory Dual Instance',
                'Memory': '12288MB',
                'MaxInstances': '2',
                'DisplayResolution': '5120x2880',
                'FrameBufferSize': '12288MB',
                'MultiVgpu': 'Yes'
            },
            {
                'TypeId': '8G3',
                'Name': 'TensorFusion-8GB',
                'Description': 'TensorFusion 8GB Memory Triple Instance',
                'Memory': '8192MB',
                'MaxInstances': '3',
                'DisplayResolution': '3840x2160',
                'FrameBufferSize': '8192MB',
                'MultiVgpu': 'Yes'
            },
            {
                'TypeId': '4G6',
                'Name': 'TensorFusion-4GB',
                'Description': 'TensorFusion 4GB Memory Six Instance',
                'Memory': '4096MB',
                'MaxInstances': '6',
                'DisplayResolution': '2560x1440',
                'FrameBufferSize': '4096MB',
                'MultiVgpu': 'Yes'
            }
        ]

        # Check if this is a TensorFusion capable device
        if not hasattr(to, 'mdevSpecifications'):
            to.mdevSpecifications = []

        # Add all mock specifications
        for spec in MDEV_SPECS:
            to.mdevSpecifications.append(spec)

        # Check marker file to determine virtualization status
        addr = to.pciDeviceAddress
        no_domain_addr = addr if len(addr.split(':')) != 3 else ':'.join(addr.split(':')[1:])
        marker_file = os.path.join('/var/run/zstack', 'tensor-fusion-mdev-' + no_domain_addr.replace(':', '_'))

        if os.path.exists(marker_file):
            to.virtStatus = "VFIO_MDEV_VIRTUALIZED"
            logger.debug("TensorFusion device %s is virtualized (marker file exists)", addr)
        else:
            to.virtStatus = "VFIO_MDEV_VIRTUALIZABLE"
            logger.debug("TensorFusion device %s is virtualizable (marker file not found)", addr)

        logger.info("Generated TensorFusion mock MDEV specs for device %s: %d configurations",
                   to.pciDeviceAddress if hasattr(to, 'pciDeviceAddress') else 'unknown',
                   len(MDEV_SPECS))

        return True



    def _terminate_worker(self, worker_info):
        """Terminate a single TensorFusion worker"""
        try:
            # Since worker processes are started with session independence,
            # try different termination methods.
            try:
                # First try to terminate the process group (if it exists)
                os.killpg(os.getpgid(worker_info.pid), 15)  # SIGTERM
            except OSError:
                try:
                    os.kill(worker_info.pid, 15)  # SIGTERM
                except OSError:
                    pass  # Process may already be dead

            # Clean up shared memory
            if os.path.exists(worker_info.shared_memory_path):
                os.unlink(worker_info.shared_memory_path)
        except Exception:
            pass  # Ignore cleanup errors

    def _get_nvidia_gpu_index_by_pci(self, pci_address):
        """Get NVIDIA GPU device index in CUDA based on PCI address"""
        try:
            # Use nvidia-smi to get mapping between CUDA index and PCI address
            cmd = "nvidia-smi --query-gpu=index,pci.bus_id --format=csv,noheader,nounits"
            ret, output, err = bash_roe(cmd)
            if ret != 0 or not output:
                return None

            output = output.strip()

            # Normalize input PCI address format
            normalized_pci = pci_address
            if len(pci_address.split(':')) == 2:
                normalized_pci = "0000:" + pci_address

            # Parse nvidia-smi output
            for line in output.split('\n'):
                if line.strip():
                    parts = line.split(',')
                    if len(parts) == 2:
                        cuda_idx = parts[0].replace(' ', '').strip()
                        pci_addr = parts[1].replace(' ', '').strip()

                        # nvidia-smi output PCI address format is usually 00000000:01:00.0
                        # Normalize to unified format for comparison
                        if pci_addr.startswith('00000000:'):
                            pci_addr = pci_addr[9:]  # Remove prefix 00000000:
                        # Ensure PCI address has domain prefix
                        if not pci_addr.startswith('0000:'):
                            pci_addr = "0000:" + pci_addr

                        if pci_addr == normalized_pci:
                            return int(cuda_idx)
            return None
        except Exception as e:
            return None


    def _start_worker_async(self, cmd_args, env_vars, shared_memory_path,
                          memory_mb, pci_address, cuda_device_index, device_uuid):
        """Start TensorFusion worker process asynchronously"""
        logger = log.get_logger(__name__)

        logger.info("Starting TensorFusion worker for device UUID: %s, PCI: %s, Memory: %sMB, CUDA Index: %s",
                   device_uuid, pci_address, memory_mb, cuda_device_index)
        logger.debug("Worker command args: %s", cmd_args)
        logger.debug("Worker environment vars: %s", env_vars)

        devnull = None
        log_file = None

        try:
            # Merge environment variables
            env = os.environ.copy()
            env.update(env_vars)

            # Create log directory if not exists
            log_dir = "/var/log/zstack"
            if not os.path.exists(log_dir):
                os.makedirs(log_dir)

            # Get vm_uuid from environment variables
            vm_uuid = env_vars.get('VM_UUID', device_uuid)

            # Create log file for this worker using vm_uuid
            log_file_path = os.path.join(log_dir, "tensor-fusion-worker-{}.log".format(vm_uuid))
            log_file = open(log_file_path, 'a')
            devnull = open(os.devnull, 'r')  # Only for stdin

            logger.info("Starting subprocess with log output to: %s", log_file_path)
            # Start process with complete independence from parent (Python2 compatible)
            process = subprocess.Popen(
                cmd_args,
                env=env,
                stdin=devnull,
                stdout=log_file,
                stderr=log_file,
                preexec_fn=os.setsid,  # Create new session and process group
                close_fds=True         # Close all file descriptors except stdin/stdout/stderr
            )

            # Get PID and immediately detach
            worker_pid = process.pid
            if worker_pid <= 0:
                raise Exception("Invalid process PID: %s" % worker_pid)

            logger.debug("Process started with PID: %s, verifying process status", worker_pid)

            # Wait briefly to ensure process doesn't immediately exit
            time.sleep(3)

            # Check if process is still running
            try:
                proc = psutil.Process(worker_pid)
                if not proc.is_running():
                    raise Exception("TensorFusion worker process (PID: %s) exited immediately after startup" % worker_pid)
                logger.debug("Process PID %s verified as running", worker_pid)
            except psutil.NoSuchProcess:
                raise Exception("TensorFusion worker process (PID: %s) not found after startup" % worker_pid)

            logger.info("TensorFusion worker process started successfully. PID: %s, Device UUID: %s",
                       worker_pid, device_uuid)

            # Create worker info object
            worker_info = TensorFusionWorkerInfo(
                uuid=device_uuid,
                pid=worker_pid,
                shared_memory_path=shared_memory_path,
                allocated_memory=memory_mb,
                pci_address=pci_address,
                cuda_device_index=cuda_device_index
            )

            logger.debug("Created TensorFusion worker info object for UUID: %s", device_uuid)
            return worker_info

        except Exception as e:
            logger.error("Failed to start TensorFusion worker for device UUID: %s, PCI: %s. Error: %s",
                        device_uuid, pci_address, str(e))
            raise Exception("Failed to start TensorFusion worker: {}".format(str(e)))

        finally:
            # Close file handles
            if devnull:
                devnull.close()
            if log_file:
                log_file.close()


    def _get_worker_info_from_process(self, pid):
        """Extract worker information from process PID"""
        try:
            proc = psutil.Process(pid)

            # Get environment variables
            env_vars = proc.environ()

            # Extract required environment variables
            cuda_visible_devices = env_vars.get('CUDA_VISIBLE_DEVICES', '-1')
            tf_cuda_memory_limit = env_vars.get('TF_CUDA_MEMORY_LIMIT', '-1')
            device_uuid = env_vars.get('TF_DEVICE_UUID')

            # If no UUID found in environment variables, generate one based on shared memory path
            if not device_uuid:
                shared_memory_path = self._get_shared_memory_path_from_psutil_process(proc)
                if shared_memory_path and shared_memory_path.startswith(SHARED_MEMORY_PATH_PREFIX):
                    # Extract UUID-like part from shared memory path
                    memory_name = shared_memory_path[len(SHARED_MEMORY_PATH_PREFIX):]
                    if memory_name.startswith('tf_'):
                        device_uuid = memory_name[3:]  # Remove 'tf_' prefix
                if not device_uuid:
                    device_uuid = str(uuid.uuid4())  # Fallback to new UUID

            # Try to parse CUDA device index
            try:
                cuda_device_index = int(cuda_visible_devices.split(',')[0])
            except (ValueError, IndexError):
                cuda_device_index = 0

            # Try to parse memory limit
            try:
                allocated_memory = int(tf_cuda_memory_limit)
            except ValueError:
                allocated_memory = 1024

            # Get PCI address from CUDA device index
            pci_address = self._get_pci_address_by_cuda_index(cuda_device_index)
            if not pci_address:
                pci_address = "unknown"

            # Get shared memory path from process command line
            shared_memory_path = self._get_shared_memory_path_from_psutil_process(proc)
            if not shared_memory_path:
                shared_memory_path = "{}unknown_{}".format(SHARED_MEMORY_PATH_PREFIX, pid)

            # Create worker info object
            worker_info = TensorFusionWorkerInfo(
                uuid=device_uuid,
                pid=pid,
                shared_memory_path=shared_memory_path,
                allocated_memory=allocated_memory,
                pci_address=pci_address,
                cuda_device_index=cuda_device_index
            )

            return worker_info

        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess, Exception):
            return None

    def _get_pci_address_by_cuda_index(self, cuda_index):
        """Get PCI address by CUDA device index"""
        try:
            cmd = "nvidia-smi --query-gpu=index,pci.bus_id --format=csv,noheader,nounits"
            ret, output, err = bash_roe(cmd)
            if ret != 0 or not output:
                return None

            output = output.strip()

            for line in output.split('\n'):
                if line.strip():
                    parts = line.split(', ')
                    if len(parts) == 2:
                        idx = parts[0].strip()
                        pci_addr = parts[1].strip()

                        if int(idx) == cuda_index:
                            # Normalize PCI address format
                            if pci_addr.startswith('00000000:'):
                                pci_addr = pci_addr[8:]
                            if len(pci_addr.split(':')) == 2:
                                pci_addr = "0000:" + pci_addr
                            return pci_addr
            return None
        except Exception as e:
            return None

    def _get_shared_memory_path_from_psutil_process(self, proc):
        """Extract shared memory path from process command line using psutil"""
        try:
            cmdline = proc.cmdline()

            # Look for -m argument followed by shared memory path
            for i, arg in enumerate(cmdline):
                if arg == '-m' and i + 1 < len(cmdline):
                    return cmdline[i + 1]

            return None
        except Exception as e:
            return None

TENSOR_FUSION_HANDLER = NvidiaTensorFusionHandler()
TENSOR_FUSION_HANDLER.get_all_devices()
