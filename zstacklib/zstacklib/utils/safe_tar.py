import os
import subprocess
import tarfile


class UnsafeArchiveError(Exception):
    pass


def inspect_archive(archive_path, max_entries=100000):
    total_size = 0
    entry_count = 0
    with tarfile.open(archive_path, mode='r:*') as archive:
        for member in archive:
            entry_count += 1
            if entry_count > max_entries:
                raise UnsafeArchiveError("archive contains too many entries")
            name = member.name.replace('\\', '/')
            parts = name.split('/')
            if not name or name.startswith('/') or '..' in parts:
                raise UnsafeArchiveError(
                    "path escape detected in archive entry: %s" % member.name)
            if member.issym() or member.islnk():
                raise UnsafeArchiveError(
                    "links are not allowed in archive: %s" % member.name)
            if not member.isfile() and not member.isdir():
                raise UnsafeArchiveError(
                    "unsupported archive entry type: %s" % member.name)
            if member.isfile():
                total_size += member.size
    return total_size


def extract_archive(archive_path, target_path, timeout=1200):
    inspect_archive(archive_path)
    subprocess.check_call([
        'tar', '--no-same-owner', '--no-same-permissions',
        '-xf', archive_path, '-C', target_path,
    ], timeout=timeout)

    real_target = os.path.realpath(target_path)
    file_sizes = {}
    for root, dirs, files in os.walk(target_path):
        for name in dirs + files:
            path = os.path.join(root, name)
            if os.path.commonpath([real_target, os.path.realpath(path)]) != real_target:
                raise UnsafeArchiveError(
                    "path escape detected after extraction: %s" % path)
        for name in files:
            path = os.path.join(root, name)
            file_sizes[path] = os.path.getsize(path)
    return file_sizes
