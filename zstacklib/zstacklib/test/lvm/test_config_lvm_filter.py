import os
import re
import shutil
import tempfile
import unittest

try:
    import mock
except ImportError:
    from unittest import mock

from zstacklib.utils import lvm
from zstacklib.utils import bash
from zstacklib.utils import linux


DEFAULT_LVM_CONF_FRAGMENT = """\
# This is a default lvm.conf fragment.

# Configuration option devices/filter.
# Limit the block devices that are used by LVM commands.
# This is a list of regular expressions used to accept or reject block
# device path names. Each regex is delimited by a vertical bar '|'
# (or any character) and is preceded by 'a' to accept the path, or
# by 'r' to reject the path. The first regex in the list to match the
# path is used, producing the 'a' or 'r' result for the device.
# Example:
# filter = [ "a|.*|" ]

# Configuration option devices/global_filter.
# Limit the block devices that are used by LVM system components.
# Example:
# global_filter = [ "a|.*|" ]

devices {
    dir = "/dev"
    scan = [ "/dev" ]
}
"""

CONF_WITH_ACTIVE_FILTER = """\
# leading comment mentioning filter
devices {
    dir = "/dev"
    filter = [ "a|.*|", "r|/dev/cdrom|" ]
    global_filter = [ "a|.*|" ]
}
# trailing comment about filter and global_filter
"""


def _count_active_filter_lines(text, key):
    pat = re.compile(r'^\s*%s(?:\s|=)' % re.escape(key))
    n = 0
    for line in text.splitlines():
        stripped = line.lstrip()
        if stripped.startswith("#"):
            continue
        if pat.match(line):
            n += 1
    return n


class TestConfigLvmFilter(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="lvmconf-")
        self._orig_lvm_path = lvm.LVM_CONFIG_PATH
        lvm.LVM_CONFIG_PATH = self.tmpdir

        self._orig_bash_o = bash.bash_o
        bash.bash_o = mock.Mock(return_value="")

    def tearDown(self):
        lvm.LVM_CONFIG_PATH = self._orig_lvm_path
        bash.bash_o = self._orig_bash_o
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _write(self, name, content):
        path = os.path.join(self.tmpdir, name)
        with open(path, "w") as f:
            f.write(content)
        return path

    def _read(self, name):
        with open(os.path.join(self.tmpdir, name)) as f:
            return f.read()

    def test_preserve_disks_does_not_touch_comments(self):
        self._write("lvm.conf", DEFAULT_LVM_CONF_FRAGMENT)
        self._write("lvmlocal.conf", DEFAULT_LVM_CONF_FRAGMENT)

        with mock.patch.object(linux, "sync_file"):
            lvm.config_lvm_filter(
                ["lvm.conf", "lvmlocal.conf"],
                preserve_disks={"/dev/sda", "/dev/nvme0n1"},
            )

        for name in ("lvm.conf", "lvmlocal.conf"):
            new = self._read(name)
            self.assertEqual(1, _count_active_filter_lines(new, "filter"),
                             "unexpected active filter lines in %s:\n%s" % (name, new))
            self.assertEqual(1, _count_active_filter_lines(new, "global_filter"))
            for marker in (
                "# Configuration option devices/filter.",
                "# Configuration option devices/global_filter.",
                "# Example:",
                '# filter = [ "a|.*|" ]',
                '# global_filter = [ "a|.*|" ]',
            ):
                self.assertIn(marker, new, "lost comment %r in %s" % (marker, name))
            self.assertIn('"a|^/dev/sda$|"', new)
            self.assertIn('"a|^/dev/nvme0n1$|"', new)
            self.assertIn('"r|.*|"', new)

    def test_replaces_existing_active_filter_only(self):
        self._write("lvm.conf", CONF_WITH_ACTIVE_FILTER)

        with mock.patch.object(linux, "sync_file"):
            lvm.config_lvm_filter(["lvm.conf"], preserve_disks={"/dev/sda"})

        new = self._read("lvm.conf")
        self.assertEqual(1, _count_active_filter_lines(new, "filter"))
        self.assertEqual(1, _count_active_filter_lines(new, "global_filter"))
        self.assertIn('"a|^/dev/sda$|"', new)
        self.assertIn("# leading comment mentioning filter", new)
        self.assertIn("# trailing comment about filter and global_filter", new)

    def test_default_branch_appends_filter_only(self):
        self._write("lvm.conf", DEFAULT_LVM_CONF_FRAGMENT)
        bash.bash_o = mock.Mock(return_value="vg1\nvg2\n")

        with mock.patch.object(linux, "sync_file"):
            lvm.config_lvm_filter(["lvm.conf"], no_drbd=True)

        new = self._read("lvm.conf")
        self.assertEqual(1, _count_active_filter_lines(new, "filter"))
        self.assertEqual(0, _count_active_filter_lines(new, "global_filter"))
        self.assertIn('"r|/dev/cdrom|"', new)
        self.assertIn('"r|/dev/mapper/vg1.*|"', new)
        self.assertIn('"r|/dev/mapper/vg2.*|"', new)
        self.assertIn('"r|/dev/drbd.*|"', new)
        self.assertIn("# Configuration option devices/filter.", new)

    def test_skip_missing_file(self):
        self._write("lvm.conf", DEFAULT_LVM_CONF_FRAGMENT)

        with mock.patch.object(linux, "sync_file"):
            lvm.config_lvm_filter(
                ["lvm.conf", "lvmlocal.conf"],
                preserve_disks={"/dev/sda"},
            )

        self.assertEqual(1, _count_active_filter_lines(self._read("lvm.conf"), "filter"))
        self.assertFalse(os.path.exists(os.path.join(self.tmpdir, "lvmlocal.conf")))

    def test_idempotent_on_second_run(self):
        self._write("lvm.conf", DEFAULT_LVM_CONF_FRAGMENT)

        with mock.patch.object(linux, "sync_file"):
            lvm.config_lvm_filter(["lvm.conf"], preserve_disks={"/dev/sda"})
            after_first = self._read("lvm.conf")
            lvm.config_lvm_filter(["lvm.conf"], preserve_disks={"/dev/sda"})
            after_second = self._read("lvm.conf")

        self.assertEqual(after_first, after_second)
        self.assertEqual(1, _count_active_filter_lines(after_second, "filter"))
        self.assertEqual(1, _count_active_filter_lines(after_second, "global_filter"))

    def test_dedup_existing_duplicate_filter_lines(self):
        corrupted = (
            DEFAULT_LVM_CONF_FRAGMENT
            + 'filter = [ "a|.*|" ]\n'
            + 'filter = [ "a|.*|" ]\n'
            + 'global_filter = [ "a|.*|" ]\n'
            + 'global_filter = [ "a|.*|" ]\n'
        )
        self._write("lvm.conf", corrupted)

        with mock.patch.object(linux, "sync_file"):
            lvm.config_lvm_filter(["lvm.conf"], preserve_disks={"/dev/sda"})

        new = self._read("lvm.conf")
        self.assertEqual(1, _count_active_filter_lines(new, "filter"))
        self.assertEqual(1, _count_active_filter_lines(new, "global_filter"))

    def test_multiline_filter_value_consumed(self):
        multi = (
            "# header\n"
            "filter = [\n"
            '    "a|.*|",\n'
            '    "r|/dev/cdrom|"\n'
            "]\n"
            'other = "x"\n'
            "global_filter = [\n"
            '    "a|.*|"\n'
            "]\n"
            'trailer = "y"\n'
        )
        self._write("lvm.conf", multi)

        with mock.patch.object(linux, "sync_file"):
            lvm.config_lvm_filter(["lvm.conf"], preserve_disks={"/dev/sda"})

        new = self._read("lvm.conf")
        self.assertEqual(1, _count_active_filter_lines(new, "filter"))
        self.assertEqual(1, _count_active_filter_lines(new, "global_filter"))
        self.assertNotIn('"r|/dev/cdrom|"', new)
        self.assertNotIn("    \"a|", new)
        self.assertIn('other = "x"\n', new)
        self.assertIn('trailer = "y"\n', new)
        self.assertEqual(new.count('['), new.count(']'),
                         "unbalanced brackets in:\n%s" % new)

    def test_near_name_keys_not_matched(self):
        near = (
            "filter_a = 1\n"
            "filterX = 2\n"
            "globalfilter = 3\n"
            'filter_types = "abc"\n'
        )
        self._write("lvm.conf", near)

        with mock.patch.object(linux, "sync_file"):
            lvm.config_lvm_filter(["lvm.conf"], preserve_disks={"/dev/sda"})

        new = self._read("lvm.conf")
        self.assertIn("filter_a = 1\n", new)
        self.assertIn("filterX = 2\n", new)
        self.assertIn("globalfilter = 3\n", new)
        self.assertIn('filter_types = "abc"\n', new)
        self.assertEqual(1, _count_active_filter_lines(new, "filter"))
        self.assertEqual(1, _count_active_filter_lines(new, "global_filter"))

    def test_lvmconfig_default_style_no_spaces(self):
        text = (
            "# expanded\n"
            'filter=["a|.*|"]\n'
            'global_filter=["a|.*|"]\n'
            "issue_discards=0\n"
        )
        self._write("lvm.conf", text)

        with mock.patch.object(linux, "sync_file"):
            lvm.config_lvm_filter(["lvm.conf"], preserve_disks={"/dev/sda"})

        new = self._read("lvm.conf")
        self.assertEqual(1, _count_active_filter_lines(new, "filter"))
        self.assertEqual(1, _count_active_filter_lines(new, "global_filter"))
        self.assertIn("issue_discards=0\n", new)
        self.assertIn('"a|^/dev/sda$|"', new)

    def test_real_centos_default_lvm_conf_fixture(self):
        fixture_path = os.path.join(os.path.dirname(__file__),
                                    "centos_default_lvm.conf")
        with open(fixture_path) as f:
            original = f.read()
        self._write("lvm.conf", original)

        preserve = {"/dev/sda", "/dev/nvme0n1", "/dev/nvme0n2",
                    "/dev/nvme0n3", "/dev/vda1"}
        with mock.patch.object(linux, "sync_file"):
            lvm.config_lvm_filter(["lvm.conf"], preserve_disks=preserve)

        new = self._read("lvm.conf")

        self.assertEqual(1, _count_active_filter_lines(new, "filter"),
                         "expected exactly one active filter line")
        self.assertEqual(1, _count_active_filter_lines(new, "global_filter"),
                         "expected exactly one active global_filter line")

        for disk in preserve:
            self.assertIn('"a|^%s$|"' % disk, new,
                          "missing accept entry for %s" % disk)
        self.assertIn('"r|.*|"', new)

        for raw in original.splitlines():
            if raw.lstrip().startswith("#") and ("filter" in raw or "global_filter" in raw):
                self.assertIn(raw, new,
                              "lost stock comment line: %r" % raw)

        for noisy in ("# Example:", "# filter = [", "# global_filter = ["):
            self.assertTrue(any(noisy in l and l.lstrip().startswith("#")
                                for l in new.splitlines()),
                            "fixture sanity: %r should still appear as comment" % noisy)

        self.assertEqual(new.count('['), new.count(']'),
                         "unbalanced brackets after filter rewrite")

        with mock.patch.object(linux, "sync_file"):
            lvm.config_lvm_filter(["lvm.conf"], preserve_disks=preserve)
        self.assertEqual(new, self._read("lvm.conf"),
                         "config_lvm_filter is not idempotent on real fixture")

    def test_no_trailing_newline(self):
        self._write("lvm.conf", "foo = 1")

        with mock.patch.object(linux, "sync_file"):
            lvm.config_lvm_filter(["lvm.conf"], preserve_disks={"/dev/sda"})

        new = self._read("lvm.conf")
        self.assertIn("foo = 1\n", new)
        self.assertNotIn("1filter", new)
        self.assertEqual(1, _count_active_filter_lines(new, "filter"))


if __name__ == "__main__":
    unittest.main()
