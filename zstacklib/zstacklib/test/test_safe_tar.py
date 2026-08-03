import io
import os
import tarfile
import tempfile
import unittest

from zstacklib.utils.safe_tar import UnsafeArchiveError, extract_archive, inspect_archive


class TestSafeTar(unittest.TestCase):
    def create_archive(self, members):
        stream = tempfile.NamedTemporaryFile(suffix='.tar.gz', delete=False)
        stream.close()
        with tarfile.open(stream.name, 'w:gz') as archive:
            for member, content in members:
                archive.addfile(member, io.BytesIO(content) if content is not None else None)
        self.addCleanup(lambda: os.path.exists(stream.name) and os.unlink(stream.name))
        return stream.name

    def test_inspect_and_extract_regular_archive(self):
        directory = tarfile.TarInfo('package')
        directory.type = tarfile.DIRTYPE
        directory.mode = 0o755
        file_info = tarfile.TarInfo('package/image.qcow2')
        file_info.size = 4
        file_info.mode = 0o644
        archive_path = self.create_archive([(directory, None), (file_info, b'data')])

        self.assertEqual(4, inspect_archive(archive_path))
        with tempfile.TemporaryDirectory() as target:
            sizes = extract_archive(archive_path, target)
            self.assertEqual(
                {os.path.join(target, 'package', 'image.qcow2'): 4},
                sizes)

    def test_rejects_parent_path_escape(self):
        file_info = tarfile.TarInfo('../escape')
        file_info.size = 1
        archive_path = self.create_archive([(file_info, b'x')])

        with self.assertRaises(UnsafeArchiveError):
            inspect_archive(archive_path)

    def test_rejects_absolute_path(self):
        file_info = tarfile.TarInfo('/etc/escape')
        file_info.size = 1
        archive_path = self.create_archive([(file_info, b'x')])

        with self.assertRaises(UnsafeArchiveError):
            inspect_archive(archive_path)

    def test_rejects_symbolic_link(self):
        link = tarfile.TarInfo('package/link')
        link.type = tarfile.SYMTYPE
        link.linkname = '/etc/passwd'
        archive_path = self.create_archive([(link, None)])

        with self.assertRaises(UnsafeArchiveError):
            inspect_archive(archive_path)

    def test_rejects_archive_over_entry_limit(self):
        members = []
        for index in range(3):
            file_info = tarfile.TarInfo('package/file-%s' % index)
            file_info.size = 1
            members.append((file_info, b'x'))
        archive_path = self.create_archive(members)

        with self.assertRaises(UnsafeArchiveError):
            inspect_archive(archive_path, max_entries=2)


if __name__ == '__main__':
    unittest.main()
