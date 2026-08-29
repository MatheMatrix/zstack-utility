import sys
import types
import unittest


class OptionalList(list):
    pass


class NotNoneList(list):
    pass


class APIGetSharedBlockVolumeSnapshotLanFreeLayoutMsg(object):
    def __init__(self):
        self.snapshotUuids = NotNoneList()


class Session(object):
    pass


apibinding = types.ModuleType('apibinding')
apibinding.__path__ = []
inventory = types.ModuleType('apibinding.inventory')
inventory.OptionalList = OptionalList
inventory.NotNoneList = NotNoneList
inventory.APIGetSharedBlockVolumeSnapshotLanFreeLayoutMsg = \
    APIGetSharedBlockVolumeSnapshotLanFreeLayoutMsg
inventory.Session = Session
inventory.api_names = ['APIGetSharedBlockVolumeSnapshotLanFreeLayoutMsg']
inventory.queryMessageInventoryMap = {}
inventory.INITIAL_SYSTEM_ADMIN_NAME = 'admin'
inventory.INITIAL_SYSTEM_ADMIN_PASSWORD = 'password'
api = types.ModuleType('apibinding.api')
api_actions = types.ModuleType('apibinding.api_actions')
apibinding.inventory = inventory
apibinding.api = api
apibinding.api_actions = api_actions
sys.modules['apibinding'] = apibinding
sys.modules['apibinding.inventory'] = inventory
sys.modules['apibinding.api'] = api
sys.modules['apibinding.api_actions'] = api_actions
from zstackcli.cli import Cli


class CapturedMessage(Exception):
    def __init__(self, message):
        self.message = message


class CapturingApi(object):
    def async_call_wait_for_complete(self, message, apievent=None, fail_soon=True):
        raise CapturedMessage(message)


class TestLanFreeCli(unittest.TestCase):
    def test_snapshot_uuids_are_parsed_as_ordered_string_list(self):
        cli = Cli.__new__(Cli)
        cli.session_uuid = 'test-session'
        cli.cli_cmd = []
        cli.api = CapturingApi()
        cli.msg_creator = {}
        cli.write_more = lambda *args, **kwargs: None

        with self.assertRaises(CapturedMessage) as context:
            cli.do_command([
                'GetSharedBlockVolumeSnapshotLanFreeLayout',
                'snapshotUuids=snapshot-1,snapshot-2',
            ])

        self.assertEqual(
            ['snapshot-1', 'snapshot-2'],
            context.exception.message.snapshotUuids)

    def test_duplicate_snapshot_uuids_are_left_for_server_validation(self):
        cli = Cli.__new__(Cli)
        cli.session_uuid = 'test-session'
        cli.cli_cmd = []
        cli.api = CapturingApi()
        cli.msg_creator = {}
        cli.write_more = lambda *args, **kwargs: None

        with self.assertRaises(CapturedMessage) as context:
            cli.do_command([
                'GetSharedBlockVolumeSnapshotLanFreeLayout',
                'snapshotUuids=snapshot-1,snapshot-1',
            ])

        self.assertEqual(
            ['snapshot-1', 'snapshot-1'],
            context.exception.message.snapshotUuids)


if __name__ == '__main__':
    unittest.main()
