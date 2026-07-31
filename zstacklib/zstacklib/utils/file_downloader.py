import os
import re
import subprocess
import threading
from urllib import parse as urlparse
from enum import Enum

from zstacklib.utils import traceable_shell, linux, shell, plugin, log
from zstacklib.utils.bash import bash_roe

logger = log.get_logger(__name__)


class UrlScheme(Enum):
    HTTP = 'http'
    HTTPS = 'https'
    FILE = 'file'
    SFTP = 'sftp'
    FTP = 'ftp'
    NFS = 'nfs'


class DownloadStrategy(object):

    def __init__(self, downloader):
        self.downloader = downloader

    def download(self):
        raise NotImplementedError()


class HttpDownloadStrategy(DownloadStrategy):

    def download(self):
        temporary_path = self.downloader.temporary_path

        try:
            cmd = self.downloader.cmd
            ret = self.downloader.use_wget(
                linux.shellquote(cmd.url),
                self.downloader.temporary_file_name,
                self.downloader.path,
                self.downloader.timeout,
                self.downloader.cancellation_pending
            )
            if ret != 0:
                linux.rm_file_force(temporary_path)
                return False, 'http/https/ftp download failed, [wget -O %s %s] returns value %s' % (
                    self.downloader.file_name, self.downloader._redact_url(cmd.url), ret)
            return True, None
        except linux.LinuxError as e:
            linux.rm_file_force(temporary_path)
            error = self.downloader._redact_error(e)
            logger.warning("HTTP download failed: %s" % error)
            return False, error


class SftpDownloadStrategy(DownloadStrategy):

    def download(self):
        ssh_pass_file = None
        url = urlparse.urlparse(self.downloader.cmd.url)
        port = url.port or 22
        temporary_path = self.downloader.temporary_path

        if not url.hostname or not re.match(r'^[A-Za-z0-9.-]+$', url.hostname):
            return False, "SFTP hostname is invalid"
        if not url.username or not re.match(r'^[A-Za-z0-9._-]+$', url.username):
            return False, "SFTP username is invalid"

        remote_path = urlparse.unquote(url.path)
        if not remote_path.startswith('/') or linux.contains_path_traversal(remote_path):
            return False, "SFTP path must be an absolute path without traversal"
        if '\x00' in remote_path or '\n' in remote_path or '\r' in remote_path:
            return False, "SFTP path contains illegal characters"

        def quote_batch_path(path):
            return '"%s"' % path.replace('\\', '\\\\').replace('"', '\\"')

        try:
            args = [
                'sftp', '-P', str(port), '-o', 'BatchMode=no',
                '-o', 'StrictHostKeyChecking=no',
                '-o', 'UserKnownHostsFile=/dev/null',
                '-b', '-', '%s@%s' % (url.username, url.hostname),
            ]
            if url.password is not None:
                ssh_pass_file = linux.write_to_temp_file(urlparse.unquote(url.password))
                os.chmod(ssh_pass_file, 0o600)
                args = ['sshpass', '-f', ssh_pass_file] + args

            process = subprocess.Popen(
                args, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                stderr=subprocess.PIPE, universal_newlines=True)
            self.downloader.set_active_process(process)
            batch = "reget %s %s\n" % (
                quote_batch_path(remote_path), quote_batch_path(temporary_path))
            _, error = process.communicate(batch, timeout=self.downloader.timeout)
            if process.returncode != 0:
                raise Exception(error.strip() or "sftp exited with code %s" % process.returncode)
            return True, None
        except subprocess.TimeoutExpired:
            process = self.downloader.get_active_process()
            if process and process.poll() is None:
                process.kill()
            linux.rm_file_force(temporary_path)
            return False, "SFTP download timed out after %s seconds" % self.downloader.timeout
        except Exception as e:
            linux.rm_file_force(temporary_path)
            return False, "SFTP download failed: %s" % str(e)
        finally:
            self.downloader.set_active_process(None)
            if ssh_pass_file:
                linux.rm_file_force(ssh_pass_file)


class FileDownloadStrategy(DownloadStrategy):

    def download(self):
        url = self.downloader.cmd.url
        if url.startswith('file://'):
            src_path = url[len('file://'):]
        elif url.startswith('file:'):
            src_path = url[len('file:'):]
        else:
            src_path = url
        if linux.contains_path_traversal(src_path):
            return False, 'file url contains illegal path traversal: %s' % src_path
        src_path = os.path.normpath(src_path)
        if not os.path.isabs(src_path):
            return False, 'file url must use absolute path: %s' % src_path
        if not os.path.isfile(src_path):
            return False, 'cannot find the file[%s]' % src_path

        logger.debug("src_path is: %s" % src_path)
        try:
            self.downloader.t_shell.call(
                'yes | cp %s %s' % (
                    linux.shellquote(src_path),
                    linux.shellquote(self.downloader.temporary_path)))
            return True, None
        except shell.ShellError as e:
            linux.rm_file_force(self.downloader.temporary_path)
            return False, str(e)


class FileDownloader:
    MIN_SAFE_CAPACITY = 1024 * 1024 * 1024

    @staticmethod
    def _redact_url(url):
        parsed = urlparse.urlparse(url)
        if parsed.username is None and parsed.password is None:
            return url
        host = parsed.hostname or ""
        if parsed.port:
            host = "%s:%s" % (host, parsed.port)
        netloc = "%s:***@%s" % (parsed.username or "", host)
        return urlparse.urlunparse((
            parsed.scheme, netloc, parsed.path,
            parsed.params, parsed.query, parsed.fragment
        ))

    def _redact_error(self, error):
        return str(error).replace(self.cmd.url, self._redact_url(self.cmd.url))

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
        api_id = plugin.get_api_id(self.cmd) or "anonymous"
        safe_api_id = re.sub(r'[^A-Za-z0-9_.-]', '_', api_id)
        self.temporary_file_name = "%s.downloading.%s" % (self.file_name, safe_api_id)
        self.temporary_path = os.path.join(self.path, self.temporary_file_name)
        self.timeout = self.cmd.timeout if self.cmd.timeout else 7200
        self.state_lock = threading.RLock()
        self.download_cancelled = False
        self.download_committed = False
        self.active_process = None

        try:
            self.urlScheme = UrlScheme(self.cmd.urlScheme)
        except ValueError:
            self.urlScheme = None

    def use_wget(self, url, name, workdir, timeout, cancellation_checker=None):
        if cancellation_checker is None:
            cancellation_checker = self.cancellation_pending

        return linux.wget(url, workdir=workdir, rename=name, timeout=timeout, interval=2,
                          callback=self.reporter.progress_report, callback_data="report",
                          cmd_wrapper=self.t_shell.wrap_cmd,
                          cancellation_checker=cancellation_checker)

    def cancellation_pending(self):
        with self.state_lock:
            if self.download_cancelled:
                return True
        return plugin.TaskManager.cancellation_pending(plugin.get_api_id(self.cmd))

    def set_active_process(self, process):
        with self.state_lock:
            self.active_process = process

    def get_active_process(self):
        with self.state_lock:
            return self.active_process

    def cancel(self):
        process = None
        with self.state_lock:
            if self.download_committed:
                return
            self.download_cancelled = True
            process = self.active_process
        if process and process.poll() is None:
            process.terminate()
        linux.rm_file_force(self.temporary_path)

    def get_url_file_size(self, url):
        parsed = urlparse.urlparse(url)
        if parsed.scheme not in ('http', 'https', 'ftp'):
            logger.debug("get_url_file_size: unsupported scheme %s, skipping" % parsed.scheme)
            return False, 0

        try:
            output = shell.call(
                "curl -sSL --head --connect-timeout 10 --max-time 30 %s" % linux.shellquote(url),
                logcmd=False)
        except Exception as e:
            logger.debug("curl HEAD request failed for %s: %s" % (
                self._redact_url(url), self._redact_error(e)))
            return False, 0

        content_length = None
        for line in output.split('\n'):
            line_lower = line.strip().lower()
            if 'content-length:' in line_lower:
                parts = line.split(':', 1)
                if len(parts) >= 2:
                    try:
                        content_length = int(parts[1].strip())
                    except ValueError:
                        pass
        if content_length is not None:
            return True, content_length
        return False, 0

    def get_local_file_size(self, local_file_path):
        parsed = urlparse.urlparse(local_file_path)
        if parsed.scheme == 'file':
            path = parsed.path
        else:
            path = local_file_path

        if not os.path.isabs(path):
            logger.debug("get_local_file_size: ignoring non-absolute path %s" % path)
            return 0

        try:
            return os.path.getsize(path)
        except OSError:
            return 0

    def get_url_file_size_by_wget(self, url):
        parsed = urlparse.urlparse(url)
        if parsed.scheme not in ('http', 'https', 'ftp'):
            return False, 0
        try:
            _, _, stderr = bash_roe("wget --spider --timeout=10 --tries=1 %s" % linux.shellquote(url))
            output = stderr if stderr else ''
            for line in output.split('\n'):
                line_lower = line.strip().lower()
                if 'length:' in line_lower:
                    parts = line.split()
                    for i, part in enumerate(parts):
                        if part.lower() == 'length:' and i + 1 < len(parts):
                            try:
                                return True, int(parts[i + 1])
                            except ValueError:
                                pass
        except Exception as e:
            logger.debug("wget --spider failed for %s: %s" % (
                self._redact_url(url), self._redact_error(e)))
        return False, 0

    def check_capacity(self):
        if self.urlScheme == UrlScheme.FILE:
            file_size = self.get_local_file_size(self.cmd.url)
            is_support_file_size = file_size > 0
        else:
            is_support_file_size, file_size = self.get_url_file_size(self.cmd.url)
            if not is_support_file_size:
                is_support_file_size, file_size = self.get_url_file_size_by_wget(self.cmd.url)

        if is_support_file_size:
            try:
                _, availableCapacity = linux.get_disk_capacity_by_df(os.path.dirname(self.install_path))
            except Exception:
                ancestor = os.path.dirname(self.install_path)
                while ancestor and ancestor != '/' and not os.path.exists(ancestor):
                    ancestor = os.path.dirname(ancestor)
                if not ancestor or not os.path.exists(ancestor):
                    logger.warning("cannot determine capacity for %s, skipping check", self.install_path)
                    return True, None
                _, availableCapacity = linux.get_disk_capacity_by_df(ancestor)
            required = int(file_size * 1.1)
            if availableCapacity < required:
                return False, 'disk capacity[%s] is not enough to download file[%s] of size[%s] (with 10%% margin)' % (
                    availableCapacity, self._redact_url(self.cmd.url), file_size)
        else:
            logger.warning("unable to determine file size for %s (Content-Length header missing or local file not found), "
                        "skipping capacity check", self._redact_url(self.cmd.url))
            try:
                ancestor = os.path.dirname(self.install_path)
                while ancestor and ancestor != '/' and not os.path.exists(ancestor):
                    ancestor = os.path.dirname(ancestor)
                if ancestor and os.path.exists(ancestor):
                    _, availableCapacity = linux.get_disk_capacity_by_df(ancestor)
                    if availableCapacity < self.MIN_SAFE_CAPACITY:
                        return False, ('disk available capacity [%s] is below minimum safe threshold [%s]'
                                       % (availableCapacity, self.MIN_SAFE_CAPACITY))
            except Exception:
                logger.debug("failed to check minimum capacity for %s" % self.install_path)

        return True, None

    def download(self):
        api_id = plugin.get_api_id(self.cmd)
        if plugin.TaskManager.cancellation_pending(api_id):
            return False, 'download canceled before start'

        if self.urlScheme is None or self.urlScheme not in self.STRATEGY_MAP:
            supported = [scheme.value for scheme in self.STRATEGY_MAP.keys()]
            return False, 'unsupported url scheme[%s], only supports %s' % (self.cmd.urlScheme, supported)

        success, err = self.check_capacity()
        if not success:
            return False, err

        if not os.path.exists(self.path):
            os.makedirs(self.path, 0o755)

        linux.rm_file_force(self.temporary_path)

        downloader = self

        class FileDownloadDaemon(plugin.TaskDaemon):
            def _cancel(self):
                downloader.cancel()

        daemon = FileDownloadDaemon(self.cmd, "DownloadFile")
        if not daemon.start():
            return False, 'download canceled before start'

        try:
            strategy_class = self.STRATEGY_MAP[self.urlScheme]
            strategy = strategy_class(self)
            success, error = strategy.download()
            if not success:
                return success, error
            with self.state_lock:
                if self.cancellation_pending():
                    return False, 'download canceled before completion'
                try:
                    os.replace(self.temporary_path, self.install_path)
                except OSError as e:
                    return False, 'failed to commit downloaded file: %s' % str(e)
                self.download_committed = True
            return True, None
        finally:
            daemon.close()
            if not self.download_committed:
                linux.rm_file_force(self.temporary_path)
