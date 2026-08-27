import os
import unittest


class SftpBackupStorageDeploymentTest(unittest.TestCase):
    def test_reinstalls_agents_after_virtualenv_recreation(self):
        script_path = os.path.join(
            os.path.dirname(__file__), "..", "ansible", "sftpbackupstorage.py"
        )
        with open(script_path) as script:
            source = script.read()

        self.assertIn(
            'if not py_version or zstacklib_copy_result != "changed:False":', source
        )
        self.assertIn(
            'if not py_version or sftp_copy_result != "changed:False":', source
        )
        self.assertEqual(
            1, source.count("sftp_copy_result = copy(copy_arg, host_post_info)")
        )


if __name__ == "__main__":
    unittest.main()
