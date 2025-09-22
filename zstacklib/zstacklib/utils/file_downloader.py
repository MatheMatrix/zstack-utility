import os
import traceback
import urlparse

from kvmagent.kvmagent import logger
from zstacklib.utils import traceable_shell, linux, shell, plugin


class FileDownloader:
    URL_HTTP = 'http'
    URL_HTTPS = 'https'
    URL_FILE = 'file'
    URL_SFTP = 'sftp'
    URL_FTP = 'ftp'
    URL_NFS = 'nfs'

    def __init__(self, reporter, cmd):
        self.reporter = reporter
        self.cmd = cmd
        self.t_shell = traceable_shell.get_shell(cmd)
        self.supported_schemes = [
            self.URL_HTTP, self.URL_HTTPS,
            self.URL_FTP, self.URL_SFTP, self.URL_FILE
        ]
        self.path = os.path.dirname(self.cmd.installPath)
        self.file_name = os.path.basename(self.cmd.installPath)
        self.install_path = self.cmd.installPath
        self.timeout = self.cmd.timeout if self.cmd.timeout else 7200

    def percentage_callback(self, percent):
        self.reporter.progress_report(int(percent))

    def use_wget(self, url, name, workdir, timeout):
        return linux.wget(url, workdir=workdir, rename=name, timeout=timeout, interval=2,
                          callback=self.percentage_callback, callback_data=url)

    def download_via_http(self):
        try:
            self.cmd.url = linux.shellquote(self.cmd.url)
            ret = self.use_wget(self.cmd.url, self.file_name, self.path, self.timeout)
            if ret != 0:
                linux.rm_file_force(self.cmd.install_path)
                return False, 'http/https/ftp download failed, [wget -O %s %s] returns value %s' % (
                    self.file_name, self.cmd.url, ret)
            return True, None
        except linux.LinuxError as e:
            linux.rm_file_force(self.install_path)
            traceback.format_exc()
            return False, str(e)

    def download_via_sftp(self):
        ssh_pass_file = None
        port = (self.cmd.url.port, 22)[self.cmd.url.port is None]
        install_path = self.cmd.installPath

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
            with SftpDownloadDaemon(self.cmd, "DownloadImage"):
                sftp_cmd = "sftp -P %d -o BatchMode=no -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -b /dev/stdin %s@%s " \
                           "<<EOF\n%%s\nEOF\n" % (port, self.cmd.url.username, self.cmd.url.hostname)
                if self.cmd.url.password is not None:
                    ssh_pass_file = linux.write_to_temp_file(self.cmd.url.password)
                    sftp_cmd = 'sshpass -f %s %s' % (ssh_pass_file, sftp_cmd)

                total_size = int(shell.call(sftp_cmd % ("ls -l " + self.cmd.url.path)).splitlines()[1].split()[4])
                self.t_shell.call(sftp_cmd % ("reget %s %s" % (self.cmd.url.path, self.cmd.install_path)))
            return True, None
        except Exception:
            return False, "SFTP download failed"

    def download_via_file(self):
        src_path = self.cmd.url.lstrip('file:')
        src_path = os.path.normpath(src_path)
        if not os.path.isfile(src_path):
            raise Exception('cannot find the file[{src_path}]')

        logger.debug("src_path is: %s" % src_path)
        try:
            self.t_shell.call('yes | cp %s %s' % (src_path, linux.shellquote(self.install_path)))
            return True, None
        except shell.ShellError as e:
            linux.rm_file_force(self.install_path)
            return False, str(e)

    def download(self):
        if self.cmd.urlScheme not in self.supported_schemes:
            return False, 'unsupported url scheme[%s], SimpleSftpBackupStorage only supports %s' % (
                self.cmd.urlScheme, self.supported_schemes)

        if not os.path.exists(self.path):
            os.makedirs(self.path, 0777)

        if self.cmd.urlScheme in [self.URL_HTTP, self.URL_HTTPS, self.URL_FTP]:
            return self.download_via_http()
        elif self.cmd.urlScheme == self.URL_SFTP:
            return self.download_via_sftp()
        elif self.cmd.urlScheme == self.URL_FILE:
            return self.download_via_file()
