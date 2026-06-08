# -*- coding: utf-8 -*-
import gzip
import io
import os
import shutil
import tempfile
import unittest


class TestDoArchiveGzip(unittest.TestCase):
    """Test log rotation gzip compression (Py2/Py3 compatible)."""

    def setUp(self):
        self.log_dir = tempfile.mkdtemp()
        self.log_file = os.path.join(self.log_dir, 'zstack.log')
        self.gz_file = self.log_file + '.gz'

    def tearDown(self):
        shutil.rmtree(self.log_dir)

    def _write_log(self, content):
        with io.open(self.log_file, 'w', encoding='utf-8') as f:
            f.write(content)

    def _read_original(self):
        with open(self.log_file, 'rb') as f:
            return f.read()

    def _do_archive(self, old_log):
        """Mirrors ZstackRotatingFileHandler.doArchive"""
        with open(old_log, 'rb') as log:
            with gzip.open(old_log + '.gz', 'wb') as comp_log:
                shutil.copyfileobj(log, comp_log)
        os.remove(old_log)

    def test_archive_basic(self):
        self._write_log(u'INFO test log line\n' * 100)
        original = self._read_original()

        self._do_archive(self.log_file)

        self.assertFalse(os.path.exists(self.log_file))
        self.assertTrue(os.path.exists(self.gz_file))
        with gzip.open(self.gz_file, 'rb') as f:
            self.assertEqual(f.read(), original)

    def test_archive_empty_file(self):
        self._write_log(u'')
        self._do_archive(self.log_file)

        self.assertTrue(os.path.exists(self.gz_file))
        with gzip.open(self.gz_file, 'rb') as f:
            self.assertEqual(f.read(), b'')

    def test_archive_large_file(self):
        self._write_log(u'2026-03-17 INFO [main] message\n' * 10000)
        original = self._read_original()

        self._do_archive(self.log_file)

        with gzip.open(self.gz_file, 'rb') as f:
            self.assertEqual(f.read(), original)
        self.assertLess(os.path.getsize(self.gz_file), len(original))

    def test_archive_unicode_content(self):
        self._write_log(u'2026-03-17 ERROR \u9519\u8bef\u4fe1\u606f \u30a8\u30e9\u30fc\n' * 10)
        original = self._read_original()

        self._do_archive(self.log_file)

        with gzip.open(self.gz_file, 'rb') as f:
            self.assertEqual(f.read(), original)


class TestGzipReadTextMode(unittest.TestCase):
    """Test gzip.open('rt') for reading compressed logs."""

    def setUp(self):
        self.log_dir = tempfile.mkdtemp()
        self.log_file = os.path.join(self.log_dir, 'zstack.log')
        self.gz_file = self.log_file + '.gz'
        with open(self.log_file, 'w') as f:
            for i in range(100):
                f.write('2026-03-17 INFO [main] message #%d\n' % i)
        with open(self.log_file, 'rb') as src:
            with gzip.open(self.gz_file, 'wb') as dst:
                shutil.copyfileobj(src, dst)

    def tearDown(self):
        shutil.rmtree(self.log_dir)

    def test_rt_returns_str(self):
        with gzip.open(self.gz_file, 'rt') as f:
            line = f.readline()
        self.assertIsInstance(line, str)
        self.assertIn('message #0', line)

    def test_rt_readlines(self):
        with gzip.open(self.gz_file, 'rt') as f:
            lines = f.readlines()
        self.assertEqual(len(lines), 100)
        self.assertIn('message #99', lines[-1])

    def test_rt_keyword_search(self):
        """Simulates timeline.build keyword filtering"""
        keyword = 'message #42'
        with gzip.open(self.gz_file, 'rt') as f:
            matched = [l for l in f if keyword in l]
        self.assertEqual(len(matched), 1)


if __name__ == '__main__':
    unittest.main()
