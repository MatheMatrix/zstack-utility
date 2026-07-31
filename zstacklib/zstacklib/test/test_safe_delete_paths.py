import os
import tempfile
import unittest

from zstacklib.utils import path_guard


class TestSafeDeletePaths(unittest.TestCase):
    def test_rejects_symbolic_link_parent(self):
        with tempfile.TemporaryDirectory() as directory:
            target_dir = os.path.join(directory, 'target')
            os.mkdir(target_dir)
            target_file = os.path.join(target_dir, 'package.tar')
            with open(target_file, 'w') as stream:
                stream.write('data')

            link_dir = os.path.join(directory, 'link')
            os.symlink(target_dir, link_dir)
            requested_path = os.path.join(link_dir, 'package.tar')

            failed = path_guard.safe_delete_paths([requested_path])

            self.assertEqual(1, len(failed))
            self.assertIn('symbolic-link path component', failed[0])
            self.assertTrue(os.path.exists(target_file))

    def test_unlinks_symbolic_link_without_deleting_target(self):
        with tempfile.TemporaryDirectory() as directory:
            target_file = os.path.join(directory, 'target')
            with open(target_file, 'w') as stream:
                stream.write('data')

            link_path = os.path.join(directory, 'link')
            os.symlink(target_file, link_path)

            self.assertEqual([], path_guard.safe_delete_paths([link_path]))
            self.assertFalse(os.path.lexists(link_path))
            self.assertTrue(os.path.exists(target_file))


if __name__ == '__main__':
    unittest.main()
