from shlex import quote

from zstacklib.utils import shell


def get_secret_value(secret_uuid):
    cmd = shell.ShellCmd("virsh secret-get-value %s" % quote(secret_uuid))
    cmd(False)
    if cmd.return_code != 0:
        raise Exception("Failed to get secret value for secret %s: %s" % (secret_uuid, cmd.stderr))
    return cmd.stdout.strip()


def block_cache_attach(domain, path, cache):
    args = [
        "block-cache-attach",
        "--domain", quote(domain),
        "--path", quote(path),
        "--cache", quote(cache),
    ]
    cmd = shell.ShellCmd("virsh %s" % " ".join(args))
    cmd(False)
    if cmd.return_code != 0:
        raise Exception("Failed to attach block cache for volume %s of vm %s: %s" % (path, domain, cmd.stderr))


def block_cache_detach(domain, path, timeout=None, delete=False, cmd_shell=None, progress_output=None):
    cmd_shell = cmd_shell or shell
    args = [
        "block-cache-detach",
        "--domain", quote(domain),
        "--path", quote(path),
    ]
    if timeout is not None:
        args.extend(["--timeout", str(timeout)])
    if delete:
        args.append("--delete")
    redirect = " 2> %s" % quote(progress_output) if progress_output else ""
    cmd_shell.call("virsh %s%s" % (" ".join(args), redirect))
