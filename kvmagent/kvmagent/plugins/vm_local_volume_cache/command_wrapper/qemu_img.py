import json
try:
    from shlex import quote
except ImportError:
    from pipes import quote
from subprocess import Popen
import threading
from typing import IO, Generator, Callable, Optional

from kvmagent.plugins.vm_local_volume_cache.command_wrapper.virsh import VirshCommandWrapper

from zstacklib.utils import linux, log, qemu_img, shell
from enum import Enum

from zstacklib.utils.jsonobject import JsonObject

DEFAULT_ZBS_CONF_PATH = "/etc/zbs/client.conf"
DEFAULT_ZBS_USER_NAME = "zbs"
PROTOCOL_CBD_PREFIX = "cbd:"

class BackingVolumeDeviceType(Enum):
    ISCSI = "iscsi"
    FILE = "file"
    CEPH = "ceph"
    SHAREDBLOCK = "sharedblock"
    SCSILUN = "scsilun"
    BLOCK = "block"
    MINISTORAGE = "mini"
    QUORUM = "quorum"
    SPOOL = "spool"
    VHOST = "vhost"
    CBD = "cbd"

class QemuImgOutputFormat(Enum):
    BLKDEBUG = "blkdebug"
    BLKLOGWRITES = "blklogwrites"
    BLKVERIFY = "blkverify"
    CBD = "cbd"
    COMPRESS = "compress"
    COPY_BEFORE_WRITE = "copy-before-write"
    COPY_ON_READ = "copy-on-read"
    FILE = "file"
    FTP = "ftp"
    FTPS = "ftps"
    GLUSTER = "gluster"
    HOST_CDROM = "host_cdrom"
    HOST_DEVICE = "host_device"
    HTTP = "http"
    HTTPS = "https"
    ISCSI = "iscsi"
    ISER = "iser"
    LUKS = "luks"
    NBD = "nbd"
    NULL_AIO = "null-aio"
    NULL_CO = "null-co"
    NVME = "nvme"
    PREALLOCATE = "preallocate"
    QCOW2 = "qcow2"
    QUORUM = "quorum"
    RAW = "raw"
    RBD = "rbd"
    SSH = "ssh"
    THROTTLE = "throttle"
    VHDX = "vhdx"
    VMDK = "vmdk"
    VPC = "vpc"

class QemuImgImageFormat(Enum):
    QCOW2 = "qcow2"
    RAW = "raw"

class BackingVolume(object):
    volume = None # type: JsonObject | None

    @property
    def volume_format(self):
        assert self.volume, "volume must be set"
        volume_format_str = self.volume.format # type: str | None
        if not volume_format_str:
            return QemuImgImageFormat.RAW
        return QemuImgImageFormat(volume_format_str)

    @property
    def output_format(self):
        raise NotImplementedError("output_format is not implemented for base BackingVolume class")

    @property
    def source_path(self):
        assert self.volume, "volume must be set"
        assert self.volume.installPath, "volume.installPath must be set"
        return self.volume.installPath # type: str

    def __init__(self, volume):
        # type: (JsonObject) -> None
        self.volume = volume

class IscsiBackingVolume(BackingVolume):
    device_type = BackingVolumeDeviceType.ISCSI

    target = None # type: str | None
    lun = None # type: str | None
    server_hostname = None # type: str | None
    server_port = None # type: str | None
    chap_username = None # type: str | None
    chap_password = None # type: str | None

    @property
    def volume_format(self):
        return QemuImgImageFormat.RAW

    @property
    def output_format(self):
        return QemuImgOutputFormat.ISCSI

    @property
    def source_path(self):
        base_url = "iscsi://%s:%s/%s/%s" % (
            self.server_hostname, self.server_port, self.target, self.lun)
        if self.chap_username and self.chap_password:
            return "%s?chapUsername=%s&chapPassword=%s" % (
                base_url, self.chap_username, self.chap_password)
        return base_url

    def __init__(self, volume):
        super().__init__(volume)
        self.__parse_iscsi_url()
    
    def __parse_iscsi_url(self):
        assert self.volume, "volume must be set"
        assert self.volume.installPath, "volume.installPath must be set"

        url = self.volume.installPath # type: str
        portal, self.target, self.lun = url.replace("iscsi://", "").split("/")
        self.server_hostname, self.server_port = portal.split(":")
        self.chap_username = self.volume.chapUsername
        self.chap_password = self.volume.chapPassword

class FileBackingVolume(BackingVolume):
    device_type = BackingVolumeDeviceType.FILE

    @property
    def output_format(self):
        return QemuImgOutputFormat(self.volume_format.value)
    
class CephBackingVolume(BackingVolume):
    device_type = BackingVolumeDeviceType.CEPH

    pool = None # type: str | None
    image = None # type: str | None
    secret_uuid = None # type: str | None
    secret_key = None # type: str | None
    mon_infos = None # type: list[tuple[str, int]] | None
    
    @property
    def volume_format(self):
        return QemuImgImageFormat.RAW

    @property
    def output_format(self):
        return QemuImgOutputFormat.RBD
    
    @property
    def source_path(self):
        assert self.volume, "volume must be set"
        assert self.mon_infos, "mon_infos must be set"

        portal_str = "rbd"
        img_info_str = "%s/%s" % (self.pool, self.image)
        mon_host_str = "mon_host=%s" % (";".join(["%s:%s" % (host, port) for host, port in self.mon_infos]))
        if self.secret_uuid and self.secret_key:
            auth_str = "id=%s:key=%s:auth_supported=cephx;none" % ("zstack", self.secret_key)
            return ":".join([portal_str, img_info_str, mon_host_str, auth_str])
        return ":".join([portal_str, img_info_str, mon_host_str])
            
    
    def __init__(self, volume):
        super().__init__(volume)
        self.__parse_ceph_url()

    def __parse_ceph_url(self):
        assert self.volume, "volume must be set"
        assert self.volume.installPath, "volume.installPath must be set"

        url = self.volume.installPath # type: str
        self.pool, self.image = url.replace("ceph://", "").split("/")
        self.secret_uuid = self.volume.secretUuid
        self.secret_key = self.__get_secret_key()
        self.mon_infos = self.__get_mon_info()

    def __get_mon_info(self):
        assert self.volume, "volume must be set"
        assert self.volume.monInfo, "volume.monInfo must be set"
        mon_infos = [(mon_info.hostname, mon_info.port) for mon_info in self.volume.monInfo] # type: list[tuple[str, int]]
        return mon_infos
    
    def __get_secret_key(self):
        assert self.secret_uuid, "secret_uuid must be set"
        return VirshCommandWrapper.get_secret_value(self.secret_uuid)

class ScsiLunBackingVolume(BackingVolume):
    device_type = BackingVolumeDeviceType.SCSILUN
    
    @property
    def volume_format(self):
        return QemuImgImageFormat.RAW

    @property
    def output_format(self):
        return QemuImgOutputFormat.RAW

class BlockBackingVolume(BackingVolume):
    device_type = BackingVolumeDeviceType.BLOCK
    @property
    def output_format(self):
        return QemuImgOutputFormat(self.volume_format.value)

class SpoolBackingVolume(BackingVolume):
    device_type = BackingVolumeDeviceType.SPOOL
    
    @property
    def output_format(self):
        return QemuImgOutputFormat(self.volume_format.value)

class CbdBackingVolume(BackingVolume):
    device_type = BackingVolumeDeviceType.CBD
    
    def make_cbd_conf(self, install_path):
        # type: (str) -> str
        return install_path[len(PROTOCOL_CBD_PREFIX):] + "_" + DEFAULT_ZBS_USER_NAME + "_:" + DEFAULT_ZBS_CONF_PATH

    @property
    def volume_format(self):
        return QemuImgImageFormat.RAW

    @property
    def output_format(self):
        return QemuImgOutputFormat.CBD
    
    @property
    def source_path(self):
        return self.make_cbd_conf(super().source_path)

supported_backing_volume_classes = {
    BackingVolumeDeviceType.ISCSI: IscsiBackingVolume,
    BackingVolumeDeviceType.FILE: FileBackingVolume,
    BackingVolumeDeviceType.CEPH: CephBackingVolume,
    BackingVolumeDeviceType.SCSILUN: ScsiLunBackingVolume,
    BackingVolumeDeviceType.BLOCK: BlockBackingVolume,
    BackingVolumeDeviceType.SPOOL: SpoolBackingVolume,
    BackingVolumeDeviceType.CBD: CbdBackingVolume
} # type: dict[BackingVolumeDeviceType, type[BackingVolume]]

class QemuImgCommandWrapper(object):

    @staticmethod
    def qcow2_create(image_path, virtual_size, cluster_size=None, extended_l2=True, block_cache=True):
        # type: (str, int, int|str|None, bool, bool) -> None
        args = ["-o"]
        options = []
        if cluster_size:
            options.append("cluster_size=%s" % cluster_size)
        if extended_l2:
            options.append("extended_l2=on")
        if block_cache:
            options.append("block_cache=on")
        args.append(",".join(options))
        linux.qcow2_create_with_option(image_path, virtual_size, opt=" ".join(args))

    @staticmethod
    def get_qcow2_virtual_size(image_path):
        # type: (str) -> int
        virtual_size, _ = linux.qcow2_size_and_actual_size(image_path)
        return virtual_size if virtual_size else 0
    
    @staticmethod
    def get_qcow2_actual_size(image_path):
        # type: (str) -> int
        _, actual_size = linux.qcow2_size_and_actual_size(image_path)
        return actual_size
    
    @staticmethod
    def get_qcow2_cluster_size(image_path):
        # type: (str) -> int
        return linux.qcow2_get_cluster_size(image_path)
    
    @staticmethod
    def get_img_fmt(image_path):
        # type: (str) -> str
        return linux.get_img_fmt(image_path)
    
    @staticmethod
    def get_qcow2_bitmaps(image_path):
        # type: (str) -> list[dict]
        cmd = shell.ShellCmd("%s --output=json %s" % (qemu_img.subcmd('info'), quote(image_path)))
        cmd(False)
        if cmd.return_code != 0:
            raise Exception("failed to get qcow2 bitmaps for image[%s], because %s" % (image_path, cmd.stderr))
        info = json.loads(cmd.stdout)
        return info.get("format-specific",{}).get("data",{}).get("bitmaps",[])
    
    @staticmethod
    def _parse_flush_progress(stdout_stream, stderr_stream):
        # type: (IO[str], IO[str]) -> Generator[float, None, None]
        buf = ""
        while True:
            ch = stdout_stream.read(1)
            if not ch:
                # EOF, process finished                    
                if buf.strip():
                    try:
                        progress = float(buf.strip().replace("(", "").replace(")", "").split("/").pop(0))
                        yield progress
                    except (ValueError, IndexError):
                        pass
                stderr = stderr_stream.read()
                if stderr:
                   raise Exception("failed to flush qcow2 image, stderr: %s" % stderr)
                break
            if ch == '\r' or ch == '\n':
                line = buf.strip()
                buf = ""
                if not line:
                    continue
                try:
                    progress = float(line.replace("(", "").replace(")", "").split("/").pop(0))
                    yield progress
                except (ValueError, IndexError):
                    pass

            else:
                buf += ch

    @staticmethod
    def _flush_progress_monitor(process, on_progress):
        # type: (Popen[str], Callable[[Optional[float], Optional[str]], None]) -> None
        assert process.stdout
        assert process.stderr
        progress = None
        try:
            for _progress in QemuImgCommandWrapper._parse_flush_progress(process.stdout, process.stderr):
                update_progress = _progress != progress
                progress = _progress
                if update_progress:
                    on_progress(progress, None)
            on_progress(100.0, None)
        except Exception as e:
            on_progress(None, str(e))
        finally:
            process.wait()

    @staticmethod
    def flush_qcow2_to_backing_volume(qcow2_path, output_format, source_path, bitmap_name=None, on_progress=None):
        # type: (str, QemuImgOutputFormat, str, Optional[str], Optional[Callable[[Optional[float], Optional[str]], None]]) -> None

        args = ["-W", "-p", "-n"]
        args.extend(["-f", QemuImgImageFormat.QCOW2.value])
        args.extend(["-O", output_format.value])

        if bitmap_name:
            args.extend(["--bitmap", bitmap_name])
        # sub process has been create while ShellCmd initialization
        cmd = shell.ShellCmd("%s %s %s %s" % (qemu_img.subcmd('convert'), " ".join(quote(arg) for arg in args), quote(qcow2_path), quote(source_path)))
        if on_progress:
            log.get_logger(__name__).debug(cmd.cmd)
            # cmd.process is created, so it's safe to start the progress monitor thread before calling cmd()
            callback_thread = threading.Thread(target=QemuImgCommandWrapper._flush_progress_monitor, args=(cmd.process, on_progress))
            callback_thread.daemon = True
            callback_thread.start()
            callback_thread.join()
        else:
            cmd(True)
