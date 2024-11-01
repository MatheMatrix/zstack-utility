import unittest
from kvmagent.plugins import ha_plugin
from mock import patch
import time

class DummyFencer(ha_plugin.StorageFencer):
    def __init__(self, name, max_failures, interval, timeout, strategy):
        super(DummyFencer, self).__init__(name, max_failures, interval, timeout, strategy)

        self.checkResult = True
        self.checkError = False
        self.failedCheckCalled = False
        self.handleFencerFailureCalled = False
        self.counter = 0

    def handle_fencer_failure(self):
        self.handleFencerFailureCalled = True
        super(DummyFencer, self).handle_fencer_failure()

    def retry_to_recover_storage(self):
        """
        retry to recover storage connection
        """
        pass

    def do_check(self):
        if self.checkError:
            raise Exception("on purpose failure")

        return self.checkResult

    def is_failed(self):
        self.failedCheckCalled = True
        self.counter += 1
        print("loop counter: %s" % self.counter)
        return super(DummyFencer, self).is_failed()

    def reset(self):
        self.checkResult = True
        self.checkError = False
        self.failedCheckCalled = False
        self.handleFencerFailureCalled = False


class TestAbstractFencer(unittest.TestCase):
    def setUp(self):
        self.fencer_manager = ha_plugin.fencer_manager
        self.fencer = DummyFencer('fencer1', 1, 1, 1, 'Force')

    def stop_fencer_after_n_loop(self, n):
        self.fencer.failedCheckCalled = False
        self.fencer_manager.start_fencer('fencer1')
        while(True):
            print("case counter: %s" % self.fencer.counter)
            if (self.fencer_manager.get_fencer('fencer1').counter >= n):
                self.fencer_manager.stop_fencer('fencer1')
                break

            time.sleep(0.1)

    def stop_fencer_after_one_loop(self):
        self.stop_fencer_after_n_loop(1)

    def test_fencer_lifecyle(self):
        self.fencer_manager.register_fencer(self.fencer)
        self.assertEqual(self.fencer_manager.fencers['fencer1'], self.fencer)

        # test fencer no failures
        self.fencer.checkResult = True
        self.stop_fencer_after_one_loop()
        self.assertFalse(self.fencer.is_failed())
        self.assertFalse(self.fencer.handleFencerFailureCalled)

        # test fencer with check failure
        self.fencer.checkResult = False
        self.stop_fencer_after_one_loop()
        self.assertFalse(self.fencer.is_failed())
        self.assertFalse(self.fencer.handleFencerFailureCalled)

        # test fencer with check exception
        self.fencer.checkResult = True
        self.fencer.checkError = True
        self.stop_fencer_after_one_loop()
        self.assertTrue(self.fencer.is_failed())
        self.assertFalse(self.fencer.handleFencerFailureCalled)

    def shell_failure_mock(self, is_exception=True, logcmd=True):
        self.return_code = 1
        self.stdout = None
        self.stderr = "on purpose failure"

        return self.stdout

    def test_handle_fencer_failure(self):
        self.assertRaises(Exception, self.fencer.handle_fencer_failure)

        # confirm failure will not break the loop
        self.fencer.checkResult = False
        self.stop_fencer_after_n_loop(3)