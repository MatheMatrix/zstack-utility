import unittest
import time
from zstacklib.utils.traceable_shell import TraceableShell
from zstacklib.utils import shell

class TestTraceableShell(unittest.TestCase):

    def setUp(self):
        self.shell = TraceableShell(id="test_id", deadline=0)

    def test_call_success(self):
        result = self.shell.call("echo 'Hello, World!'")
        self.assertIn("Hello, World!", result)

    def test_call_failure(self):
        with self.assertRaises(shell.ShellError):
            self.shell.call("exit 1")

    def test_run_success(self):
        return_code = self.shell.run("echo 'Hello, World!'")
        self.assertEqual(return_code, 0)

    def test_run_failure(self):
        return_code = self.shell.run("exit 1")
        self.assertNotEqual(return_code, 0)

    def test_check_run_success(self):
        return_code = self.shell.check_run("echo 'Hello, World!'")
        self.assertEqual(return_code, 0)

    def test_check_run_failure(self):
        with self.assertRaises(shell.ShellError):
            self.shell.check_run("exit 1")

    def test_bash_progress_1(self):
        r, o, e = self.shell.bash_progress_1("echo 'Hello, World!'", lambda x: x == 0)
        self.assertIn("Hello, World!", o)

    def test_bash_roe(self):
        r, o, e = self.shell.bash_roe("echo 'Hello, World!'")
        self.assertIn("Hello, World!", o)

    def test_bash_errorout(self):
        o = self.shell.bash_errorout("echo 'Hello, World!'")
        self.assertIn("Hello, World!", o)


    def test_timeout_error(self):
        self.shell = TraceableShell(id="test_id", deadline=int(time.time()) + 2)
        self.shell.call("sleep 1")
        time.sleep(1)
        with self.assertRaises(Exception) as e:
            self.shell.call("true")
        self.assertIn("deadline", str(e.exception))
        # exceed deadline, so the command should not be executed
        self.assertNotIn("true", str(e.exception))

    def test_timeout_error2(self):
        self.shell = TraceableShell(id="test_id", deadline=int(time.time()) + 3)
        self.shell.call("sleep 1")
        with self.assertRaises(shell.ShellError) as e:
            self.shell.call("sleep 2")
        self.assertIn("execution timeout", str(e.exception))
        self.assertIn("sleep", str(e.exception))
        # error message should only contain original command
        self.assertNotIn("echo", str(e.exception))

    def test_timeout_error3(self):
        self.shell = TraceableShell(id="test_id", deadline=int(time.time()) + 3)
        self.shell.check_run("sleep 1")
        with self.assertRaises(shell.ShellError) as e:
            self.shell.check_run("sleep 2")
        self.assertIn("execution timeout", str(e.exception))
        self.assertIn("sleep", str(e.exception))


    def tearDown(self):
        pass

if __name__ == "__main__":
    unittest.main()