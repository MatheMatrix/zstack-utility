from enum import Enum
import json
import os
try:
    from shlex import quote
except ImportError:
    from pipes import quote

from zstacklib.utils import linux, shell

class FileSystemType(Enum):
    EXT4 = "ext4"
    XFS = "xfs"


class FileSystemInfoFields(Enum):
    UUID = "uuid"
    LABEL = "label"
    LENGTH = "length"
    TYPE = "type"
    OFFSET = "offset"
    USAGE = "usage"
    DEVICE = "device"


class MountPointInfoFields(Enum):
    SOURCE = "source"
    TARGET = "target"
    FSTYPE = "fstype"
    OPTIONS = "options"
    VFS_OPTIONS = "vfs-options"
    FS_OPTIONS = "fs-options"
    LABEL = "label"
    UUID = "uuid"
    PARTLABEL = "partlabel"
    PARTUUID = "partuuid"
    MAJ_MIN = "maj:min"
    SIZE = "size"
    AVAIL = "avail"
    USED = "used"
    USE_PERCENT = "use%"
    FSROOT = "fsroot"
    TID = "tid"
    ID = "id"
    OPT_FIELDS = "opt-fields"
    PROPAGATION = "propagation"
    FREQ = "freq"
    PASSNO = "passno"


class FileSystemCommandWrapper:
    """Wrapper for filesystem commands"""

    @staticmethod
    def parse_findmnt_output(raw_json):
        # type: (str) -> list[dict[str, str]] | None
        if not raw_json.strip():
            return None
        output_json = json.loads(raw_json.strip())
        mount_points = output_json.get("filesystems", []) # type: list[dict[str, str]]
        if len(mount_points) == 0:
            return None
        return mount_points

    @staticmethod
    def parse_wipefs_output(raw_json):
        # type: (str) -> list[dict[str, str]] | None
        if not raw_json.strip():
            return None
        output_json = json.loads(raw_json.strip())
        filesystems = output_json.get("signatures", []) # type: list[dict[str, str]]
        if len(filesystems) == 0:
            return None
        return filesystems

    @staticmethod
    def partprobe(device_path=None):
        # type: (str|None) -> None
        args = []
        if device_path:
            args.append(device_path)
        cmd = shell.ShellCmd("partprobe %s" % ' '.join(quote(arg) for arg in args))
        cmd(is_exception=True)

    @staticmethod
    def check_block_device_superblock(device_path):
        # type: (str) -> bool
        """ Check if block device has existing filesystem signatures
        Args:
            device_path (str): Path to the block device
        Returns:
            bool: True if filesystem signatures exist, False otherwise
        Raises:
            Exception: If the device path does not exist or command fails
        """
        if not os.path.exists(device_path):
            raise Exception("Device path %s does not exist" % device_path)
        cmd = shell.ShellCmd("wipefs --noheadings --no-act --output TYPE %s" % quote(device_path))
        cmd(is_exception=True)
        if cmd.stdout.strip() != "":
            return True
        return False
    
    @staticmethod
    def wipe_block_device_superblock(device_path, force=False):
        # type: (str, bool) -> None
        if not force and FileSystemCommandWrapper.check_block_device_superblock(device_path):
            raise Exception("Device %s has existing filesystem signatures, refuse to wipe without force" % device_path)

        cmd = shell.ShellCmd("wipefs --all --force %s" % quote(device_path))
        cmd(is_exception=True)

    @staticmethod
    def get_filesystem_object(device_path):
        # type: (str) -> dict[str, str] | None
        fields = [field for field in FileSystemInfoFields._value2member_map_]
        cmd = shell.ShellCmd("wipefs --json --no-act --output %s %s" % (','.join(quote(field) for field in fields), quote(device_path)))
        cmd(is_exception=True)
        filesystems = FileSystemCommandWrapper.parse_wipefs_output(cmd.stdout)
        if not filesystems:
            return None
        obj = filesystems.pop()
        if obj.get(FileSystemInfoFields.USAGE.value) != "filesystem":
            return None
        return obj

    @staticmethod
    def create_filesystem(device_path, fs_type, force=False):
        # type: (str, FileSystemType, bool) -> str
        args = []
        args.extend(["-t", fs_type.value])
        if force:
            args.append("-f")
        args.append(device_path)
        cmd = shell.ShellCmd("mkfs %s" % ' '.join(quote(arg) for arg in args))
        cmd(is_exception=True)
        return device_path

    @staticmethod
    def get_block_mount_points(filesystem_uuid):
        # type: (str) -> list[dict[str, str]] | None
        fields = [field for field in MountPointInfoFields._value2member_map_]
        cmd = shell.ShellCmd("findmnt --json --bytes --output %s --source UUID=%s"
                             % (','.join(fields), quote(filesystem_uuid)))
        cmd(is_exception=False)
        if cmd.return_code != 0 or not cmd.stdout.strip():
            return None
        return FileSystemCommandWrapper.parse_findmnt_output(cmd.stdout)

    @staticmethod
    def get_dir_mount_points(mount_path):
        # type: (str) -> list[dict[str, str]] | None
        fields = [field for field in MountPointInfoFields._value2member_map_]
        cmd = shell.ShellCmd("findmnt --json --bytes --output %s --mountpoint %s"
                             % (','.join(quote(field) for field in fields), quote(mount_path)))
        cmd(is_exception=False)
        if cmd.return_code != 0 or not cmd.stdout.strip():
            return None
        return FileSystemCommandWrapper.parse_findmnt_output(cmd.stdout)
    
    @staticmethod
    def get_mount_point(filesystem_uuid, mount_path):
        # type: (str, str) -> dict[str, str] | None
        fields = [field for field in MountPointInfoFields._value2member_map_]
        cmd = shell.ShellCmd("findmnt --json --bytes --output %s --source UUID=%s --mountpoint %s"
                             % (','.join(quote(field) for field in fields), quote(filesystem_uuid), quote(mount_path)))
        cmd(is_exception=False)
        if cmd.return_code != 0 or not cmd.stdout.strip():
            return None
        mount_points = FileSystemCommandWrapper.parse_findmnt_output(cmd.stdout)
        if not mount_points:
            return None
        return mount_points.pop()
        
    @staticmethod
    def mount_filesystem(filesystem_uuid, mount_path, force=False):
        # type: (str, str, bool) -> None
        if FileSystemCommandWrapper.get_mount_point(filesystem_uuid, mount_path):
            return
        if not os.path.exists(mount_path):
            os.makedirs(mount_path, 0o755)

        dir_mount_points = FileSystemCommandWrapper.get_dir_mount_points(mount_path)
        if dir_mount_points:
            if not force:
                raise Exception("Mount path %s is already used by another filesystem, refuse to mount without force"
                                % mount_path)
            # If force is True, we will umount all filesystems using this mount path before mounting the new filesystem
            FileSystemCommandWrapper.umount_filesystem(mount_path, force=True)
        linux.mount("UUID=%s" % filesystem_uuid, mount_path)

    @staticmethod
    def umount_filesystem(mount_path, force=False):
        # type: (str, bool) -> None
        dir_mount_points = FileSystemCommandWrapper.get_dir_mount_points(mount_path)
        if not dir_mount_points:
            return
        if len(dir_mount_points) > 1:
            if not force:
                raise Exception("Mount path %s is used by multiple filesystems, refuse to umount without force" % mount_path)
            for mp in dir_mount_points:
                linux.umount(mp.get(MountPointInfoFields.TARGET.value))
        else:
            linux.umount(mount_path)

    @staticmethod
    def extend_filesystem(device_path, new_size=None):
        # todo: support other filesystem types
        args = []
        if new_size:
            args.extend(["-D", str(new_size)])
        args.append(device_path)
        cmd = shell.ShellCmd("xfs_growfs %s" % ' '.join(quote(arg) for arg in args))
        cmd()
        if cmd.return_code != 0:
            raise Exception("Failed to extend filesystem on device %s: %s" % (device_path, cmd.stderr))

    @staticmethod
    def check_filesystem(directory, tmp_file=None):
        # type: (str, str|None) -> bool
        _tmp_file = tmp_file or ".tmp"
        _tmp_file_path = os.path.join(directory, _tmp_file)
        try:
            fd = os.open(_tmp_file_path, os.O_CREAT | os.O_WRONLY | os.O_EXCL, 0o600)
            os.close(fd)
            os.stat(_tmp_file_path)
            os.unlink(_tmp_file_path)
            return True
        except (OSError, IOError) as e:
            try:
                os.unlink(_tmp_file_path)
            except:
                pass
            return False
    
    @staticmethod
    def get_all_files(directory):
        # type: (str) -> list[str]
        files = []
        for root, _, filenames in os.walk(directory):
            for name in filenames:
                files.append(os.path.join(root, name))
        return files

    @staticmethod
    def _has_mountpoint(device):
        # type: (dict) -> bool
        """Recursively check if a device or any of its children has a mountpoint."""
        if device.get("mountpoint"):
            return True
        for child in device.get("children", []):
            if FileSystemCommandWrapper._has_mountpoint(child):
                return True
        return False

    @staticmethod
    def get_mounted_block_devices():
        # type: () -> list[str]
        """Get all top-level block devices that have a mountpoint at any level.

        Uses `lsblk --json --all` to list all block devices, then returns
        top-level devices where the device itself or any descendant has a
        non-null mountpoint.

        Returns:
            list of top-level device dicts from lsblk output that are mounted.
        """
        cmd = shell.ShellCmd("lsblk --json --all")
        cmd(is_exception=True)
        output = json.loads(cmd.stdout.strip())
        devices = output.get("blockdevices", [])
        return [dev.get("name") for dev in devices if FileSystemCommandWrapper._has_mountpoint(dev)]

    @staticmethod
    def is_block_device_mounted(device_path):
        cmd = shell.ShellCmd("lsblk --json %s" % quote(device_path))
        cmd(is_exception=True)
        output = json.loads(cmd.stdout.strip())
        devices = output.get("blockdevices", [])
        if not devices:
            raise Exception("Device %s not found" % device_path)
        device = devices.pop() # type: dict
        return FileSystemCommandWrapper._has_mountpoint(device)

    @staticmethod
    def remove_path(path, is_exception=True):
        # type: (str, bool) -> bool
        """Remove a file or directory (recursively) at the given path.

        Args:
            path: Absolute path to the file or directory to remove.
            is_exception: If True, raise on failure; otherwise swallow and return False.

        Returns:
            True if removed successfully, False otherwise.
        """
        import shutil
        try:
            if os.path.isdir(path):
                shutil.rmtree(path)
            else:
                os.remove(path)
            return True
        except Exception as e:
            if is_exception:
                raise
            return False
