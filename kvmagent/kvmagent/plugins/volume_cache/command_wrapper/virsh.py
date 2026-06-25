import re
try:
    from shlex import quote
except ImportError:
    from pipes import quote
from subprocess import Popen
import threading
from typing import IO, Callable, Generator, Optional

import pipes
from types import FunctionType

from zstacklib.utils import log, shell


class VirshCommandWrapper:
    """VirshCommandWrapper is a wrapper of virsh command"""

    @staticmethod
    def get_secret_value(secret_uuid):
        # type: (str) -> str
        cmd = shell.ShellCmd('virsh secret-get-value %s' % pipes.quote(secret_uuid))
        cmd(False)
        if cmd.return_code != 0:
            raise Exception('Failed to get secret value for secret %s: %s' % (secret_uuid, cmd.stderr))
        return cmd.stdout.strip()

    @staticmethod
    def block_cache_attach(domain, path, cache):
        # type: (str, str, str) -> None
        args = []
        args.append("block-cache-attach")
        args.extend(["--domain", pipes.quote(domain)])
        args.extend(["--path", pipes.quote(path)])
        args.extend(["--cache", pipes.quote(cache)])

        cmd = shell.ShellCmd('virsh %s' % ' '.join(args))
        cmd(False)
        if cmd.return_code != 0:
            raise Exception('Failed to attach block cache for volume %s of vm %s: %s' % (path, domain, cmd.stderr))

    @staticmethod
    def _parse_block_cache_detach_progress(stdout_stream, stderr_stream):
        # type: (IO[str], IO[str]) -> Generator[float, None, None]
        pattern = r'\[\s*(\d+)\s*%\]'
        compiled = re.compile(pattern)
        buf = ""
        yield 0.0

        while True:
            ch = stderr_stream.read(1)
            if not ch:
                # EOF, process finished
                if buf.strip():
                    try:
                        matched = compiled.search(buf)
                        if matched:
                            progress = matched.group(1)
                            yield float(progress)
                        else:
                            raise Exception(buf)
                    except (AttributeError, ValueError):
                        pass
                break
            if ch == '\r' or ch == '\n':
                line = buf.strip()
                buf = ""
                if not line:
                    continue
                try:
                    matched = compiled.search(line)
                    if matched:
                        progress = matched.group(1)
                        yield float(progress)
                    else:
                        buf += line
                        line = ""
                except (AttributeError, ValueError):
                    pass
            else:
                buf += ch

    @staticmethod
    def _block_cache_detach_progress_monitor(process, on_progress):
        # type: (Popen[str], Callable[[Optional[float], Optional[str]], None]) -> None
        assert process.stdout
        assert process.stderr
        progress = None
        try:
            for _progress in VirshCommandWrapper._parse_block_cache_detach_progress(process.stdout, process.stderr):
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
    def block_cache_detach(domain, path, timeout=None, delete=False, on_progress=None):
        # type: (str, str, int|None, bool, FunctionType|None) -> object
        args = []
        args.append("block-cache-detach")
        args.extend(["--domain", pipes.quote(domain)])
        args.extend(["--path", pipes.quote(path)])
        if timeout is not None:
            args.extend(["--timeout", str(timeout)])
        if delete:
            args.append("--delete")
        # sub process has been create while ShellCmd initialization
        cmd = shell.ShellCmd('virsh %s' % ' '.join(quote(arg) for arg in args))
        if on_progress:
            log.get_logger(__name__).debug(cmd.cmd)
            # cmd.process is created, so it's safe to start the progress monitor thread before calling cmd()
            callback_thread = threading.Thread(target=VirshCommandWrapper._block_cache_detach_progress_monitor, args=(cmd.process, on_progress))
            callback_thread.daemon = True
            callback_thread.start()
            callback_thread.join()
        else:
            cmd(True)
