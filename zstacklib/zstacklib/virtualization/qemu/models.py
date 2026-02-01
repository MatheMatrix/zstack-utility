# Copyright (c) ZStack.io, Inc.

"""
QEMU data models and constants.

Provides data classes for QEMU operations.
"""

from typing import Optional


# QGA channel states
QGA_CHANNEL_STATE_CONNECTED = 'connected'
QGA_CHANNEL_STATE_DISCONNECTED = 'disconnected'

# QGA state constants
QGA_STATE_RUNNING = "Running"
QGA_STATE_NOT_RUNNING = "NotRunning"

# QGA execution timeouts
QGA_EXEC_WAIT_INTERVAL = 1  # seconds between status checks
QGA_EXEC_WAIT_RETRY = 30   # maximum retries for command completion
ZS_TOOLS_WAIT_RETRY = 120  # Windows zs-tools wait timeout

# OS type constants
VM_OS_LINUX_KYLIN = "kylin"
VM_OS_LINUX_UOS = "uos"
VM_OS_LINUX_UBUNTU = "ubuntu"
VM_OS_LINUX_CENTOS = "centos"
VM_OS_LINUX_OPEN_SUSE = "opensuse-leap"
VM_OS_LINUX_SUSE_S = "sles"
VM_OS_LINUX_SUSE_D = "sled"
VM_OS_LINUX_ORACLE = "ol"
VM_OS_LINUX_REDHAT = "rhel"
VM_OS_WINDOWS = "mswindows"

# Linux OS list
LINUX_OS_LIST = [
    VM_OS_LINUX_KYLIN,
    VM_OS_LINUX_UOS,
    VM_OS_LINUX_UBUNTU,
    VM_OS_LINUX_CENTOS,
    VM_OS_LINUX_OPEN_SUSE,
    VM_OS_LINUX_SUSE_S,
    VM_OS_LINUX_SUSE_D,
    VM_OS_LINUX_ORACLE,
    VM_OS_LINUX_REDHAT,
]

# Windows zs-tools path
ZS_TOOLS_PATH_WIN = r"C:\Program Files\GuestTools\zs-tools\zs-tools.exe"


class QemuImgCheckResult(object):
    """Result of qemu-img check command.
    
    Attributes:
        image_end_offset: End offset of the image data.
        total_clusters: Total number of clusters in the image.
        check_errors: Number of errors found during check.
        allocated_clusters: Number of allocated clusters.
        filename: Path to the image file.
        format: Image format (e.g., 'qcow2', 'raw').
    """

    def __init__(
        self,
        image_end_offset,  # type: Optional[int]
        total_clusters,    # type: Optional[int]
        check_errors,      # type: Optional[int]
        allocated_clusters,  # type: Optional[int]
        filename,          # type: Optional[str]
        format             # type: Optional[str]
    ):
        # type: (...) -> None
        self.image_end_offset = image_end_offset
        self.total_clusters = total_clusters
        self.check_errors = check_errors
        self.allocated_clusters = allocated_clusters
        self.filename = filename
        self.format = format

    def __repr__(self):
        # type: () -> str
        return (
            'QemuImgCheckResult(filename={!r}, format={!r}, '
            'total_clusters={}, allocated_clusters={}, check_errors={})'
        ).format(
            self.filename, self.format,
            self.total_clusters, self.allocated_clusters, self.check_errors
        )

    def has_errors(self):
        # type: () -> bool
        """Check if the image has any errors."""
        return self.check_errors is not None and self.check_errors > 0


class QgaInfo(object):
    """QEMU Guest Agent information.
    
    Attributes:
        version: QGA version string.
        supported_commands: Dict of command name to enabled status.
        os: Operating system ID (e.g., 'centos', 'ubuntu').
        os_version: Operating system version.
        os_id_like: ID_LIKE field from /etc/os-release.
        state: QGA state (Running or NotRunning).
    """

    def __init__(self):
        # type: () -> None
        self.version = None   # type: Optional[str]
        self.supported_commands = {}  # type: dict
        self.os = None        # type: Optional[str]
        self.os_version = None  # type: Optional[str]
        self.os_id_like = None  # type: Optional[str]
        self.state = QGA_STATE_NOT_RUNNING  # type: str

    def is_running(self):
        # type: () -> bool
        """Check if QGA is running."""
        return self.state == QGA_STATE_RUNNING

    def is_windows(self):
        # type: () -> bool
        """Check if the guest OS is Windows."""
        return self.os is not None and VM_OS_WINDOWS in self.os

    def is_linux(self):
        # type: () -> bool
        """Check if the guest OS is Linux."""
        return self.os is not None and self.os in LINUX_OS_LIST

    def supports_command(self, command):
        # type: (str) -> bool
        """Check if a QGA command is supported and enabled."""
        return self.supported_commands.get(command, False)
