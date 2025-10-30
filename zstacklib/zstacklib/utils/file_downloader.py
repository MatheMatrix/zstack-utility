import os
import traceback
import urlparse
from enum import Enum

from kvmagent.kvmagent import logger
from zstacklib.utils import traceable_shell, linux, shell, plugin


class UrlScheme(Enum):
    """Supported URL schemes"""
    HTTP = 'http'
    HTTPS = 'https'
    FILE = 'file'
    SFTP = 'sftp'
    FTP = 'ftp'
    NFS = 'nfs'


class DownloadStrategy(object):
    """Abstract base class for download strategies"""

    def __init__(self, downloader):
        self.downloader = downloader

    def download(self):
        """Execute download operation, returns (success: bool, error_msg: str or None)"""
        raise NotImplementedError()


class HttpDownloadStrategy(DownloadStrategy):
    """Download strategy for HTTP/HTTPS/FTP protocols"""

    def download(self):
        try:
            cmd = self.downloader.cmd
            cmd.url = linux.shellquote(cmd.url)
            ret = self.downloader.use_wget(
                cmd.url,
                self.downloader.file_name,
                self.downloader.path,
                self.downloader.timeout
            )
            if ret != 0:
                linux.rm_file_force(self.downloader.install_path)
                return False, 'http/https/ftp download failed, [wget -O %s %s] returns value %s' % (
                    self.downloader.file_name, cmd.url, ret)
            return True, None
        except linux.LinuxError as e:
            linux.rm_file_force(self.downloader.install_path)
            traceback.format_exc()
            return False, str(e)


class SftpDownloadStrategy(DownloadStrategy):
    """Download strategy for SFTP protocol"""

    def download(self):
        ssh_pass_file = None
        url = urlparse.urlparse(self.downloader.cmd.url)
        port = (url.port, 22)[url.port is None]
        install_path = self.downloader.install_path

        class SftpDownloadDaemon(plugin.TaskDaemon):
            def _cancel(self):
                pass

            def _get_percent(self):
                return os.stat(install_path).st_size / (total_size / 100) if os.path.exists(install_path) else 0

            def __exit__(self, exc_type, exc_val, exc_tb):
                super(SftpDownloadDaemon, self).__exit__(exc_type, exc_val, exc_tb)
                if ssh_pass_file:
                    linux.rm_file_force(ssh_pass_file)
                if exc_val is not None:
                    linux.rm_file_force(install_path)
                    traceback.format_exc()

        try:
            with SftpDownloadDaemon(self.downloader.cmd, "DownloadImage"):
                sftp_cmd = "sftp -P %d -o BatchMode=no -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -b /dev/stdin %s@%s " \
                           "<<EOF\n%%s\nEOF\n" % (port, url.username, url.hostname)
                if url.password is not None:
                    ssh_pass_file = linux.write_to_temp_file(url.password)
                    sftp_cmd = 'sshpass -f %s %s' % (ssh_pass_file, sftp_cmd)

                total_size = int(shell.call(sftp_cmd % ("ls -l " + url.path)).splitlines()[1].split()[4])
                self.downloader.t_shell.call(sftp_cmd % ("reget %s %s" % (url.path, install_path)))
            return True, None
        except Exception:
            return False, "SFTP download failed"


class FileDownloadStrategy(DownloadStrategy):
    """Download strategy for local file system"""

    def download(self):
        src_path = self.downloader.cmd.url.lstrip('file:')
        src_path = os.path.normpath(src_path)
        if not os.path.isfile(src_path):
            raise Exception('cannot find the file[{src_path}]')

        logger.debug("src_path is: %s" % src_path)
        try:
            self.downloader.t_shell.call('yes | cp %s %s' % (src_path, linux.shellquote(self.downloader.install_path)))
            return True, None
        except shell.ShellError as e:
            linux.rm_file_force(self.downloader.install_path)
            return False, str(e)


class FileDownloader:
    """File Downloader - using Strategy Pattern"""

    # Strategy mapping table
    STRATEGY_MAP = {
        UrlScheme.HTTP: HttpDownloadStrategy,
        UrlScheme.HTTPS: HttpDownloadStrategy,
        UrlScheme.FTP: HttpDownloadStrategy,
        UrlScheme.SFTP: SftpDownloadStrategy,
        UrlScheme.FILE: FileDownloadStrategy,
    }

    def __init__(self, reporter, cmd):
        self.reporter = reporter
        self.cmd = cmd
        self.t_shell = traceable_shell.get_shell(cmd)
        self.path = os.path.dirname(self.cmd.installPath)
        self.file_name = os.path.basename(self.cmd.installPath)
        self.install_path = self.cmd.installPath
        self.timeout = self.cmd.timeout if self.cmd.timeout else 7200

        # Convert string to enum
        try:
            self.urlScheme = UrlScheme(self.cmd.urlScheme)
        except ValueError:
            self.urlScheme = None

    def use_wget(self, url, name, workdir, timeout):
        return linux.wget(url, workdir=workdir, rename=name, timeout=timeout, interval=2,
                          callback=self.reporter.progress_report, callback_data="report")

    def download(self):
        """Execute download using appropriate strategy"""

        # Validate URL scheme
        if self.urlScheme is None or self.urlScheme not in self.STRATEGY_MAP:
            supported = [scheme.value for scheme in self.STRATEGY_MAP.keys()]
            return False, 'unsupported url scheme[%s], only supports %s' % (self.cmd.urlScheme, supported)

        if not os.path.exists(self.path):
            os.makedirs(self.path, 0777)

        # Execute appropriate download strategy
        strategy_class = self.STRATEGY_MAP[self.urlScheme]
        strategy = strategy_class(self)
        return strategy.download()
