import os
import re
import shutil


BLACK_PATHS = frozenset(["", "/", "*", "/root", "/var", "/bin", "/lib", "/sys"])
PROTECTED_TOP_DIRS = frozenset([
    '/bin', '/boot', '/dev', '/etc', '/home', '/lib', '/lib64', '/media',
    '/mnt', '/opt', '/proc', '/root', '/run', '/sbin', '/srv', '/sys',
    '/tmp', '/usr', '/var',
])
PROTECTED_FILE_NAMES = frozenset([
    'shadow', 'passwd', 'sudoers', 'fstab', 'crypttab',
    'authorized_keys', 'id_rsa', 'id_ed25519',
])
PROTECTED_DEPTH1_DIRS = frozenset(['/etc', '/usr', '/var', '/lib', '/lib64'])
SHELL_UNSAFE_RE = re.compile(r'[;|&$`\'"\\(){}\[\]<>!#~\n\r\x00*?]')


def contains_path_traversal(path):
    normalized = path.replace('\\', '/')
    return any(part == '..' for part in normalized.split('/'))


def validate_install_path(install_path, param_name="installPath"):
    if not install_path:
        return None, "%s cannot be empty" % param_name
    if not isinstance(install_path, str):
        return None, "%s must be a string, got %s" % (
            param_name, type(install_path).__name__)
    if not os.path.isabs(install_path):
        return None, "%s must be an absolute path" % param_name
    if contains_path_traversal(install_path):
        return None, "%s %s contains illegal traversal sequence" % (
            param_name, install_path)

    install_path = os.path.normpath(install_path)
    match = SHELL_UNSAFE_RE.search(install_path)
    if match:
        return None, "%s contains unsafe shell character: %r" % (
            param_name, match.group())
    if install_path in BLACK_PATHS or install_path in PROTECTED_TOP_DIRS:
        return None, "%s %s is a protected path" % (param_name, install_path)
    return install_path, None


def _is_path_dangerous(path):
    if not path:
        return True, "path is empty"

    path = os.path.normpath(path)
    if path in BLACK_PATHS or path in PROTECTED_TOP_DIRS:
        return True, "%s is a protected system path" % path

    parts = path.rstrip('/').split('/')
    if len(parts) == 3 and ('/' + parts[1]) in PROTECTED_DEPTH1_DIRS:
        return True, "%s is a protected system directory" % path

    basename = os.path.basename(path)
    if basename in PROTECTED_FILE_NAMES and (
            path.startswith('/etc/') or '/.ssh/' in path):
        return True, "%s is a protected sensitive file" % path

    return False, None


def safe_delete_paths(paths, max_batch=1000):
    if len(paths) > max_batch:
        raise ValueError(
            "too many paths to delete in one batch (max: %d, got: %d)"
            % (max_batch, len(paths)))

    failed = []
    for path in paths:
        normalized, error = validate_install_path(path, "filePath")
        if error:
            failed.append(error)
            continue

        dangerous, reason = _is_path_dangerous(normalized)
        if dangerous:
            failed.append(reason)
            continue

        if not os.path.exists(normalized) and not os.path.islink(normalized):
            continue

        try:
            if os.path.islink(normalized):
                os.unlink(normalized)
                continue

            real_path = os.path.realpath(normalized)
            dangerous, reason = _is_path_dangerous(real_path)
            if dangerous:
                failed.append("%s resolves to dangerous path %s: %s"
                              % (normalized, real_path, reason))
                continue
            if real_path != normalized:
                failed.append(
                    "%s contains a symbolic-link path component and resolves to %s"
                    % (normalized, real_path))
                continue

            if os.path.isdir(normalized):
                shutil.rmtree(normalized)
            else:
                os.remove(normalized)
        except Exception as error:
            failed.append("%s: %s" % (normalized, str(error)))

    return failed
