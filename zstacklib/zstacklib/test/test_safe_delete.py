import errno
import os
import shutil
import sys
import tempfile
import unittest

# linux.py has heavy dependencies (simplejson, etc.) that may not be installed
# in all test environments. Extract only the functions we need by reading and
# exec'ing the relevant portion.
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_LINUX_PY = os.path.join(_THIS_DIR, '..', 'utils', 'linux.py')

# Build a minimal namespace with required builtins
_ns = {'os': os, 're': __import__('re'), 'shutil': shutil, '__builtins__': __builtins__}

# Read linux.py source and extract lines from "black_dpath_list" to
# end of "safe_delete_paths" function.
with open(_LINUX_PY) as _f:
    _src = _f.read()

# Find start: "black_dpath_list = "
_start = _src.index('\nblack_dpath_list = ')
# Find end: after "def safe_delete_paths" ... "return failed"
# We need everything from black_dpath_list through safe_delete_paths
_end_marker = '\ndef rm_file_checked('
_end = _src.index(_end_marker, _start)

_fragment = _src[_start:_end]

# Provide stubs for dependencies used in the fragment
import logging as _logging
_ns['logger'] = _logging.getLogger('test_safe_delete')
_ns['_string_types'] = (str,) if sys.version_info[0] >= 3 else (str, getattr(__builtins__, 'unicode', str))


# We also need rm_dir_force and rm_file_force
def _rm_dir_force(path):
    shutil.rmtree(path)

def _rm_file_force(path):
    try:
        os.remove(path)
    except OSError as e:
        if e.errno == errno.ENOENT:
            return
        raise

_ns['rm_dir_force'] = _rm_dir_force
_ns['rm_file_force'] = _rm_file_force

exec(compile(_fragment, _LINUX_PY, 'exec'), _ns)

is_path_dangerous = _ns['is_path_dangerous']
safe_delete_paths = _ns['safe_delete_paths']
contains_path_traversal = _ns['contains_path_traversal']


class TestIsPathDangerous(unittest.TestCase):

    def test_empty_path(self):
        dangerous, reason = is_path_dangerous("")
        self.assertTrue(dangerous)
        self.assertIn("empty", reason)

    def test_black_dpath_list(self):
        for p in ["", "/", "*", "/root", "/var", "/bin", "/lib", "/sys"]:
            dangerous, _ = is_path_dangerous(p)
            self.assertTrue(dangerous, "%s should be in black_dpath_list" % p)

    def test_protected_top_dirs(self):
        for p in ["/bin", "/boot", "/dev", "/etc", "/home", "/lib", "/lib64",
                  "/media", "/mnt", "/opt", "/proc", "/root", "/run", "/sbin",
                  "/snap", "/srv", "/sys", "/tmp", "/usr", "/var"]:
            dangerous, _ = is_path_dangerous(p)
            self.assertTrue(dangerous, "%s should be a protected top-level dir" % p)

    def test_depth1_child_protected(self):
        for p in ["/etc/nginx", "/usr/local", "/var/log", "/lib/modules",
                  "/lib64/ld", "/home/user", "/home/tmp"]:
            dangerous, reason = is_path_dangerous(p)
            self.assertTrue(dangerous, "%s should be depth-1 protected" % p)
            self.assertIn("depth-1", reason)

    def test_depth2_child_allowed(self):
        for p in ["/etc/nginx/conf.d", "/usr/local/bin", "/var/log/zstack",
                  "/home/tmp/zmigrate"]:
            dangerous, _ = is_path_dangerous(p)
            self.assertFalse(dangerous, "%s should be allowed (depth >= 2)" % p)

    def test_sensitive_filenames_under_etc(self):
        for name in ["shadow", "passwd", "sudoers", "fstab", "crypttab"]:
            p = "/etc/" + name
            dangerous, _ = is_path_dangerous(p)
            self.assertTrue(dangerous, "%s should be blocked" % p)

    def test_sensitive_filenames_under_ssh(self):
        for name in ["authorized_keys", "id_rsa", "id_ed25519"]:
            p = "/home/user/.ssh/" + name
            dangerous, _ = is_path_dangerous(p)
            self.assertTrue(dangerous, "%s should be blocked" % p)

    def test_sensitive_filenames_outside_sensitive_dir(self):
        dangerous, _ = is_path_dangerous("/home/tmp/shadow")
        self.assertFalse(dangerous)
        dangerous, _ = is_path_dangerous("/opt/backup/passwd")
        self.assertFalse(dangerous)

    def test_ssh_directory_blocked(self):
        for p in ["/home/user/.ssh", "/root/.ssh", "/home/deploy/.ssh"]:
            dangerous, reason = is_path_dangerous(p)
            self.assertTrue(dangerous, "%s should be blocked (.ssh dir)" % p)
            self.assertIn(".ssh", reason)

    def test_safe_paths(self):
        for p in ["/home/tmp/zmigrate/ZMigrate2.tar.gz",
                  "/home/tmp/zmigrate/unzip_path_2424652908",
                  "/opt/data/images/test.qcow2",
                  "/vms_image/some_file.img"]:
            dangerous, reason = is_path_dangerous(p)
            self.assertFalse(dangerous, "%s should be safe, got: %s" % (p, reason))

    def test_trailing_slash(self):
        dangerous, _ = is_path_dangerous("/etc/")
        self.assertTrue(dangerous)


class TestContainsPathTraversal(unittest.TestCase):

    def test_traversal_detected(self):
        self.assertTrue(contains_path_traversal("/home/../etc/shadow"))
        self.assertTrue(contains_path_traversal("../../etc"))

    def test_no_traversal(self):
        self.assertFalse(contains_path_traversal("/home/user/file"))
        self.assertFalse(contains_path_traversal("/tmp/safe"))


class TestSafeDeletePaths(unittest.TestCase):

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_regular_file(self):
        f = os.path.join(self.tmpdir, "file.txt")
        with open(f, "w") as fp:
            fp.write("hello")
        failed = safe_delete_paths([f])
        self.assertEqual(failed, [])
        self.assertFalse(os.path.exists(f))

    def test_directory_recursive(self):
        d = os.path.join(self.tmpdir, "sub", "nested")
        os.makedirs(d)
        with open(os.path.join(d, "f.txt"), "w") as fp:
            fp.write("x")
        target = os.path.join(self.tmpdir, "sub")
        failed = safe_delete_paths([target])
        self.assertEqual(failed, [])
        self.assertFalse(os.path.exists(target))

    def test_nonexistent_path(self):
        failed = safe_delete_paths([os.path.join(self.tmpdir, "gone")])
        self.assertEqual(failed, [])

    def test_blacklisted_path_rejected(self):
        for p in ["/", "/bin", "/etc", "/usr", "/var", "/home", "/root"]:
            failed = safe_delete_paths([p])
            self.assertTrue(len(failed) > 0, "%s should be rejected" % p)

    def test_path_traversal(self):
        failed = safe_delete_paths(["/home/user/../../../etc/shadow"])
        self.assertTrue(len(failed) > 0)
        self.assertIn("traversal", failed[0])

    def test_relative_path(self):
        failed = safe_delete_paths(["relative/path"])
        self.assertTrue(len(failed) > 0)
        self.assertIn("absolute", failed[0])

    def test_null_byte(self):
        failed = safe_delete_paths(["/tmp/bad\x00file"])
        self.assertTrue(len(failed) > 0)
        self.assertIn("null byte", failed[0])

    def test_max_batch(self):
        paths = ["/tmp/fakefile"] * 1001
        with self.assertRaises(ValueError):
            safe_delete_paths(paths)

    def test_symlink_safe_target(self):
        target = os.path.join(self.tmpdir, "real.txt")
        with open(target, "w") as fp:
            fp.write("real")
        link = os.path.join(self.tmpdir, "link.txt")
        os.symlink(target, link)

        failed = safe_delete_paths([link])
        self.assertEqual(failed, [])
        self.assertFalse(os.path.islink(link))
        self.assertTrue(os.path.exists(target))

    def test_symlink_dangerous_target(self):
        link = os.path.join(self.tmpdir, "bad_link")
        os.symlink("/etc", link)

        failed = safe_delete_paths([link])
        self.assertTrue(len(failed) > 0)
        self.assertIn("dangerous", failed[0])
        self.assertTrue(os.path.islink(link))

    def test_dangling_symlink_safe(self):
        link = os.path.join(self.tmpdir, "dangling")
        os.symlink(os.path.join(self.tmpdir, "no_such_file"), link)

        failed = safe_delete_paths([link])
        self.assertEqual(failed, [])
        self.assertFalse(os.path.islink(link))

    def test_dangling_symlink_relative_target_dangerous(self):
        nested = os.path.join(self.tmpdir, "a", "b")
        os.makedirs(nested)
        link = os.path.join(nested, "bad_link")
        rel_target = os.path.relpath("/etc", nested)
        os.symlink(rel_target, link)

        resolved = os.path.realpath(link)
        self.assertEqual(resolved, "/etc")

        failed = safe_delete_paths([link])
        self.assertTrue(len(failed) > 0, "should reject symlink resolving to /etc")
        self.assertIn("dangerous", failed[0])
        self.assertTrue(os.path.islink(link))

    def test_mixed_valid_and_invalid(self):
        good = os.path.join(self.tmpdir, "good.txt")
        with open(good, "w") as fp:
            fp.write("ok")

        failed = safe_delete_paths([good, "/etc", "relative"])
        self.assertEqual(len(failed), 2)
        self.assertFalse(os.path.exists(good))

    def test_depth1_protected_child(self):
        failed = safe_delete_paths(["/etc/nginx"])
        self.assertTrue(len(failed) > 0)

    def test_home_blocked(self):
        failed = safe_delete_paths(["/home"])
        self.assertTrue(len(failed) > 0)

    def test_home_user_blocked(self):
        failed = safe_delete_paths(["/home/user"])
        self.assertTrue(len(failed) > 0)

    def test_home_deep_allowed(self):
        d = os.path.join(self.tmpdir, "deep")
        os.makedirs(d)
        failed = safe_delete_paths([d])
        self.assertEqual(failed, [])

    def test_parent_symlink_bypass(self):
        link_dir = os.path.join(self.tmpdir, "linkdir")
        os.symlink("/etc", link_dir)
        target = os.path.join(link_dir, "shadow")

        failed = safe_delete_paths([target])
        self.assertTrue(len(failed) > 0)
        self.assertIn("dangerous", failed[0])

    def test_parent_symlink_safe_target(self):
        real_dir = os.path.join(self.tmpdir, "realdir")
        os.makedirs(real_dir)
        target_file = os.path.join(real_dir, "file.txt")
        with open(target_file, "w") as fp:
            fp.write("data")

        link_dir = os.path.join(self.tmpdir, "linkdir")
        os.symlink(real_dir, link_dir)

        through_link = os.path.join(link_dir, "file.txt")
        failed = safe_delete_paths([through_link])
        self.assertEqual(failed, [])
        self.assertFalse(os.path.exists(target_file))

    def test_empty_string(self):
        failed = safe_delete_paths([""])
        self.assertTrue(len(failed) > 0)

    def test_whitespace_trimmed(self):
        f = os.path.join(self.tmpdir, "ws.txt")
        with open(f, "w") as fp:
            fp.write("data")
        failed = safe_delete_paths(["  " + f + "  "])
        self.assertEqual(failed, [])
        self.assertFalse(os.path.exists(f))

    def test_non_string_rejected(self):
        failed = safe_delete_paths([123])
        self.assertTrue(len(failed) > 0)
        self.assertIn("not a string", failed[0])


if __name__ == "__main__":
    unittest.main()
