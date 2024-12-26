import mock

from kvmagent.plugins import ha_plugin
from zstacklib.utils import sanlock

unittest_filesystem_mount_point = ha_plugin.FileSystemMountPoint(
    "/tmp", "/tmp", True, "nfsv4")

def mock_vm_running_on_ps(vm_uuid_list):
    # mock return value of find_ps_running_vm
    ha_plugin.find_ps_running_vm = mock.Mock(return_value=vm_uuid_list)


def mock_sanlock_status():
    ret = '''
daemon eb65fc94-1b565dca-ha-1
    our_host_name=eb65fc94-1b565dca-ha-1
    use_watchdog=0
    high_priority=0
    mlock_level=1
    quiet_fail=1
    debug_renew=1
    debug_clients=0
    debug_cmds=0xfffffffffe06ffff
    renewal_history_size=180
    gid=179
    uid=179
    sh_retries=20
    max_sectors_kb_ignore=1
    max_sectors_kb_align=0
    max_sectors_kb_num=0
    max_worker_threads=8
    write_init_io_timeout=60
    use_aio=1
    io_timeout=10
    watchdog_fire_timeout=1
    kill_grace_seconds=40
    helper_pid=130169
    helper_kill_fd=4
    helper_full_count=0
    helper_last_status=427759
    monotime=427772
    version_str=3.8.5
    version_num=3.8.5
    version_hex=03080500
    smproto_hex=00000001
p -1 helper
    ci=0
    fd=5
    pid=-1
    flags=0
    restricted=0
    cmd_active=0
    cmd_last=0
    pid_dead=0
    kill_count=0
    kill_last=0
    suspend=0
    need_free=0
p -1 listener
    ci=1
    fd=7
    pid=-1
    flags=0
    restricted=0
    cmd_active=0
    cmd_last=0
    pid_dead=0
    kill_count=0
    kill_last=0
    suspend=0
    need_free=0
p 130189 lvmlockd
    ci=2
    fd=9
    pid=130189
    flags=0
    restricted=2
    cmd_active=0
    cmd_last=8
    pid_dead=0
    kill_count=0
    kill_last=0
    suspend=0
    need_free=0
p -1 status
    ci=3
    fd=10
    pid=-1
    flags=0
    restricted=0
    cmd_active=0
    cmd_last=5
    pid_dead=0
    kill_count=0
    kill_last=0
    suspend=0
    need_free=0
s lvm_eb65fc94660949e99f638c5160ff8ebb:82:/dev/mapper/eb65fc94660949e99f638c5160ff8ebb-lvmlock:0
    list=spaces
    space_id=1
    io_timeout=20
    sector_size=512
    align_size=1048576
    host_generation=1
    renew_fail=0
    space_dead=0
    killing_pids=0
    used_retries=0
    external_used=0
    used_by_orphans=1
    renewal_read_extend_sec=24
    set_max_sectors_kb=0
    corrupt_result=0
    acquire_last_result=1
    renewal_last_result=1
    acquire_last_attempt=4189
    acquire_last_success=4189
    renewal_last_attempt=427758
    renewal_last_success=427758
'''
    # mock return value of get_sanlock_status
    sanlock.get_sanlock_status = mock.Mock(
        return_value=sanlock.SanlockClientStatusParser(ret))
