import os.path
import functools
import time

from zstacklib.utils import log
from zstacklib.utils import linux
from zstacklib.utils import thread
from zstacklib.utils import lock
from zstacklib.utils import jsonobject
from zstacklib.utils import report
from zstacklib.utils import http
from zstacklib.utils import sizeunit

import re
import random
from string import whitespace
from zstacklib.utils import bash
from zstacklib.utils.linux import ignoreerror

GLLK_BEGIN = 65
VGLK_BEGIN = 66
SMALL_ALIGN_SIZE = 1*1024**2
SECTOR_SIZE_512 = 512
SECTOR_SIZE_4K = 8*512
BIG_ALIGN_SIZE = 8*1024**2
sector_size_cache = {}
SANLOCK_BACKUP_PATH = "/etc/sanlock/backup/"

logger = log.get_logger(__name__)

def repair_metadata(vg_name, lease_struct):
    offset = int(lease_struct.offset)
    if offset == 0:
        host_id = lease_struct.host_id
        r, _, e = repair_delta_lease_if_corrupted(vg_name, host_id)
    else:
        resource_name = lease_struct.resource_name
        r, _, e = repair_paxos_lease(vg_name, resource_name, offset)

    if r != 0:
        return "failed to repair sanlock lease, err %s" % e
    return None


def request_mn_repair_metadata(vg_name, specify_host_by_id=False, **lease_struct):
    url = report.Report.url
    host_uuid = report.Report.serverUuid

    struct = {"primaryStorageUuid": vg_name,
              "hostUuid": host_uuid,
              "leaseStruct": lease_struct,
              "specifyHostById": specify_host_by_id}
    if not url or not host_uuid:
        logger.warn("Cannot find SEND_COMMAND_URL or HOST_UUID, unable send event to management node, detail: %s" % jsonobject.dumps(struct))
        return

    return http.json_dump_post(url, struct, {'commandpath': "/sharedblock/sanlock/metadata/repair"})


class SanlockHostStatus(object):
    def __init__(self, record):
        lines = record.strip().splitlines()
        hid, s, ts = lines[0].split()
        if s != 'timestamp':
            raise Exception('unexpected sanlock host status: ' + record)
        self.host_id = int(hid)
        self.timestamp = int(ts)

        for line in lines[1:]:
            try:
                k, v = line.strip().split('=', 2)
                if k == 'io_timeout': self.io_timeout = int(v)
                elif k == 'last_check': self.last_check = int(v)
                elif k == 'last_live': self.last_live = int(v)
                elif k == 'owner_name': self.owner_name = v
            except ValueError:
                logger.warn("unexpected sanlock status: %s" % line)

        if not all([self.io_timeout, self.last_check, self.last_live]):
            raise Exception('unexpected sanlock host status: ' + record)

    def get_timestamp(self):
        return self.timestamp

    def get_io_timeout(self):
        return self.io_timeout

    def get_last_check(self):
        return self.last_check

    def get_last_live(self):
        return self.last_live

    def get_owner_name(self):
        return self.owner_name


class SanlockHostStatusParser(object):
    def __init__(self, status):
        self.status = status

    def is_timed_out(self, hostId):
        r = self.get_record(hostId)
        if r is None:
            return None

        return r.get_timestamp() == 0 or r.get_last_check() - r.get_last_live() > 10 * r.get_io_timeout()

    def is_alive(self, hostId):
        r = self.get_record(hostId)
        if r is None:
            return None

        return r.get_timestamp() != 0 and r.get_last_check() - r.get_last_live() < 2 * r.get_io_timeout()

    def get_record(self, hostId):
        m = re.search(r"^%d\b" % hostId, self.status, re.M)
        if not m:
            return None

        substr = self.status[m.end():]
        m = re.search(r"^\d+\b", substr, re.M)
        remainder = substr if not m else substr[:m.start()]
        return SanlockHostStatus(str(hostId) + remainder)


class SanlockClientStatus(object):
    def __init__(self, status_lines):
        self.lockspace = status_lines[0].split()[1]
        self.is_adding = ':0 ADD' in status_lines[0]

        for line in status_lines[1:]:
            try:
                k, v = line.strip().split('=', 2)
                if k == 'renewal_last_result': self.renewal_last_result = int(v)
                elif k == 'renewal_last_attempt': self.renewal_last_attempt = int(v)
                elif k == 'renewal_last_success': self.renewal_last_success = int(v)
                elif k == 'io_timeout': self.io_timeout = int(v)
                elif k == 'space_dead': self.space_dead = int(v)
            except ValueError:
                logger.warn("unexpected sanlock client status: %s" % line)

    def get_lockspace(self):
        return self.lockspace

    def get_renewal_last_result(self):
        return self.renewal_last_result

    def get_renewal_last_attempt(self):
        return self.renewal_last_attempt

    def get_renewal_last_success(self):
        return self.renewal_last_success

    def get_io_timeout(self):
        return self.io_timeout

    def is_space_dead(self):
        return bool(self.space_dead)


class SanlockClientStatusParser(object):
    def __init__(self):
        self.status = self._init()
        self.lockspace_records = None  # type: list[SanlockClientStatus]

    def get_lockspace_records(self):
        if self.lockspace_records is None:
            self.lockspace_records = self._do_get_lockspace_records()
        return self.lockspace_records

    def get_lockspace_record(self, needle):
        for r in self.get_lockspace_records():
            if needle in r.get_lockspace():
                return r
        return None

    def _init(self):
        @linux.retry(3, 1)
        def _get():
            return bash.bash_errorout("timeout 10 sanlock client status -D")
        try:
            return _get()
        except:
            return ""

    def _do_get_lockspace_records(self):
        records = []
        current_lines = []

        for line in self.status.splitlines():
            if len(line) == 0:
                continue

            if line[0] in whitespace and len(current_lines) > 0:
                current_lines.append(line)
                continue

            # found new records - check whether to complete last record.
            if len(current_lines) > 0:
                records.append(SanlockClientStatus(current_lines))
                current_lines = []

            if line.startswith("s "):
                current_lines.append(line)

        if len(current_lines) > 0:
            records.append(SanlockClientStatus(current_lines))

        return records

    def get_config(self, config_key):
        for line in self.status.splitlines():
            if config_key in line:
                return line.strip().split("=")[-1]


@bash.in_bash
def direct_init_resource(resource):
    cmd = "sanlock direct init -r %s" % resource
    return bash.bash_r(cmd)

@bash.in_bash
def direct_init_host(vg_name, host_id, opts=""):
    return bash.bash_roe("sanlock direct init_host -s lvm_%s:%s:/dev/mapper/%s-lvmlock:0 %s" %
                       (vg_name, host_id, vg_name, opts))


def check_stuck_vglk_and_gllk():
    # 1. clear the vglk/gllk held by the dead host
    # 2. check stuck vglk/gllk
    locks = get_vglks() + get_gllks()
    logger.debug("start checking all vgs[%s] to see if the VGLK/GLLK on disk is normal" % map(lambda v: v.vg_name, locks))

    abnormal_lcks = filter(lambda v: v.abnormal_held(), locks)
    if len(abnormal_lcks) == 0:
        logger.debug("no abnormal vglk or gllk found")
        return

    logger.debug("found possible dirty vglk/gllk on disk: %s" % map(lambda v: v.vg_name, abnormal_lcks))
    results = {}
    def check_stuck_lock():
        @thread.AsyncThread
        def check(lck):
            results.update({lck.vg_name: lck.stuck()})
        for lck in abnormal_lcks:
            check(lck)

    def wait(_):
        return len(results) == len(abnormal_lcks)

    check_stuck_lock()
    linux.wait_callback_success(wait, timeout=60, interval=3)
    for lck in filter(lambda v: results.get(v.vg_name) is True, abnormal_lcks):
        lck.refresh()
        if not lck.abnormal_held():
            continue

        if lck.host_id not in lck.owners:
            live_min_host_id = get_hosts_state(lck.lockspace_name).get_live_min_hostid()
            if int(lck.host_id) != live_min_host_id:
                logger.debug("find dirty %s on vg %s, init it directly by host[hostId:%s] with min hostId" % (lck.resource_name, lck.vg_name, live_min_host_id))
                continue

        logger.debug("find dirty %s on vg %s, init it directly" % (lck.resource_name, lck.vg_name))
        direct_init_resource("{}:{}:/dev/mapper/{}-lvmlock:{}".format(lck.lockspace_name, lck.resource_name, lck.vg_name, lck.offset))


class DeltaLease(object):
    def __init__(self, lines=None):
        self.sector_size = None
        self.owner_id = None
        self.owner_generation = None
        self.lver = None
        self.space_name = None
        self.resource_name = None
        self.timestamp = None
        self.checksum = None
        self.io_timeout = None
        self.align_size = None
        if lines:
            self._update(lines)

    def _update(self, lines):
        ''' lines example:
read_leader done 0
magic 0x12212010
version 0x30004
flags 0x10
sector_size 512
num_hosts 0
max_hosts 1
owner_id 55
owner_generation 1
lver 0
space_name lvm_8071334fc528468fa75352c0d48773e1
resource_name 8071334f-8e17af6a-172-26-50-245
timestamp 3728429
checksum 0x325ac994
io_timeout 20
extra1 0
extra2 0
extra3 0
        '''
        for line in lines.strip().split("\n"):
            fields = line.strip().split()
            if len(fields) < 2:
                continue

            key, value = fields[0], fields[1]
            if key == "sector_size":
                self.sector_size = int(value)
            elif key == "owner_id":
                self.owner_id = int(value)
            elif key == "owner_generation":
                self.owner_generation = int(value)
            elif key == "lver":
                self.lver = int(value)
            elif key == "space_name":
                self.space_name = value
            elif key == "resource_name":
                self.resource_name = value
            elif key == "timestamp":
                self.timestamp = int(value)
            elif key == "checksum":
                self.checksum = value
            elif key == "io_timeout":
                self.io_timeout = int(value)


class PaxosLease(object):
    def __init__(self, lines=None, host_id=None, align_size=SMALL_ALIGN_SIZE):
        self.host_id = host_id
        self.sector_size = None
        self.align_size = align_size
        self.offset = None
        self.lockspace_name = None
        self.resource_name = None
        self.owners = []
        self.shared = None
        if lines:
            self._update(lines)

    def _update(self, lines):
        ''' lines example:
79691776 lvm_8071334fc528468fa75352c0d48773e1           tZ7r5r-64u5-MatG-hHSc-vJUj-u6nw-TV92Yi 0000000000 0084 0004 10
                                                                                                              0055 0001 SH
        '''
        self.owners = []
        self.shared = None
        for line in lines.strip().splitlines():
            line = line.strip()
            if ' lvm_' in line:
                self.offset, self.lockspace_name, self.resource_name, self.timestamp, own, self.gen = line.split()[:6]
                if len(line.split()) == 7:
                    self.lver = line.split()[6]
                self.vg_name = self.lockspace_name.strip("lvm_")
                if self.timestamp.strip("0") != '':
                    self.owners.append(str(int(own)))
            elif ' SH' in line:
                self.shared = True
                self.owners.append(str(int(line.split()[0])))

    @property
    def lock_type(self):
        if self.shared:
            return 'sh'
        elif len(self.owners) == 1:
            return 'ex'
        else:
            return 'un'

    def refresh(self):
        r, o, e = direct_dump_resource("/dev/mapper/%s-lvmlock" % self.vg_name, self.offset, size=self.align_size)
        self._update(o)

    def in_use(self):
        return bash.bash_r("sanlock client status | grep %s:%s | grep -v 'ADD' " % (self.lockspace_name, self.resource_name)) == 0

    # the current host holds the resource lock, but the process holding the lock cannot be found or held by a dead host
    def abnormal_held(self):
        if self.lock_type == 'un':
            return False
        # held by us
        if self.host_id in self.owners:
            return not self.in_use()
        # held by dead host with ex mode
        if self.lock_type != 'ex':
            return False
        host_state = get_hosts_state(self.lockspace_name)
        if host_state is not None and host_state.is_host_dead(self.owners[0]):
            return True

        return False

    def stuck(self):
        if not self.abnormal_held():
            return False

        ori_lver = self.lver
        ori_lock_type = self.lock_type
        ori_time = linux.get_current_timestamp()
        # the purpose of retrying is to repeatedly confirm that the lock on the resource has generated dirty data
        # because the results of 'sanlock client status' and 'sanlock direct dump' may not necessarily be at the same time
        @linux.retry(12, sleep_time=random.uniform(3, 4))
        def _stuck():
            self.refresh()
            if not self.abnormal_held() or self.lock_type != ori_lock_type:
                return
            elif self.lock_type == 'ex' and self.lver == ori_lver:
                raise RetryException("resource %s held by us, lock type: ex" % self.resource_name)
            elif self.lock_type == 'sh':
                raise RetryException("resource %s held by us, lock type: sh" % self.resource_name)

        try:
            _stuck()
        except RetryException as e:
            logger.warn(str(e) + (" over %s seconds" % (linux.get_current_timestamp() - ori_time)))
            return True
        except Exception as e:
            raise e

        return False


'''
s lvm_8e97627ab5ea4b0e8cb9f42c8345d728:7:/dev/mapper/8e97627ab5ea4b0e8cb9f42c8345d728-lvmlock:0 
h 7 gen 3 timestamp 3654034 LIVE
h 52 gen 2 timestamp 1815547 DEAD
h 58 gen 3 timestamp 1104848 DEAD
h 67 gen 5 timestamp 1824156 DEAD
h 100 gen 4 timestamp 1207551 LIVE
s lvm_675a67fb03b54acf9daac0a7ae966b74:70:/dev/mapper/675a67fb03b54acf9daac0a7ae966b74-lvmlock:0 
h 70 gen 2 timestamp 3654038 LIVE
h 100 gen 1 timestamp 1207549 LIVE
'''
class HostsState(object):
    def __init__(self, lines, lockspace_name):
        self.lockspace_name = lockspace_name
        self.hosts = {}
        self.host_timestamp = {}
        self._update(lines)

    def _update(self, lines):
        self.hosts = {}
        find_lockspace = False
        for line in lines.strip().splitlines():
            if line.strip().startswith('s %s' % self.lockspace_name):
                find_lockspace = True
            elif line.strip().startswith('h ') and find_lockspace:
                host_id = line.split()[1]
                host_state = line.split()[-1]
                timestamp = line.split()[-2]
                self.hosts.update({host_id: host_state})
                self.host_timestamp.update({host_id: timestamp})
            elif find_lockspace and line.strip().startswith('s lvm_'):
                break
        logger.debug("get hosts state[%s] on lockspace %s" % (self.hosts, self.lockspace_name))

    def is_host_live(self, host_id):
        return self.hosts.get(str(host_id)) == "LIVE"

    def is_host_dead(self, host_id):
        return self.hosts.get(str(host_id)) == "DEAD"

    def get_timestamp(self, host_id):
        return self.host_timestamp.get(str(host_id))
    
    def get_live_min_hostid(self):
        ids = [int(id) for id in self.hosts.keys() if self.is_host_live(id)]
        if len(ids) == 0:
            return None
        return min(ids)


def get_hosts_state(lockspace_name):
    r, o, e = bash.bash_roe("sanlock client gets -h 1")
    if r == 0 and lockspace_name in o:
        return HostsState(o, lockspace_name)


@bash.in_bash
def direct_dump(path, offset, length):
    return bash.bash_roe("sanlock direct dump %s:%s:%s" % (path, offset, length))


@bash.in_bash
def direct_dump_resource(path, offset, size=SMALL_ALIGN_SIZE):
    return bash.bash_roe("sanlock direct dump %s:%s:%s" % (path, offset, size))

@bash.in_bash
def read_delta_lease(vg_uuid, host_id, sector_size=None):
    if not sector_size:
        sector_size = get_sector_size(vg_uuid)

    align_size_MB = sizeunit.Byte.toMegaByte(sector_size_to_align_size(sector_size))
    return bash.bash_roe("sanlock direct read_leader -s lvm_%s:%s:/dev/mapper/%s-lvmlock:0 -Z %s -A %sM" % (vg_uuid, host_id, vg_uuid, sector_size, align_size_MB))

@bash.in_bash
def read_paxos_lease(vg_uuid, resource_name, offset):
    return bash.bash_roe("sanlock direct read_leader -r lvm_%s:%s:/dev/mapper/%s-lvmlock:%s" % (vg_uuid, resource_name, vg_uuid, offset))

def get_vglks():
    result = []
    for lockspace in get_lockspaces():
        path = lockspace.split(":")[2]
        host_id = lockspace.split(":")[1]
        vg_uuid = lockspace.split(":")[0].replace("lvm_", "", 1)
        align_size = sector_size_to_align_size(get_sector_size(vg_uuid))
        r, o, e = direct_dump_resource(path, VGLK_BEGIN * align_size)
        if ' VGLK ' in o:
            result.append(PaxosLease(o, host_id, align_size))
    return result


def get_vglk(vg_uuid):
    lockspace = get_lockspace(vg_uuid)
    if lockspace is None:
        return None

    path = lockspace.split(":")[2]
    host_id = lockspace.split(":")[1]
    vg_uuid = lockspace.split(":")[0].replace("lvm_", "", 1)
    align_size = sector_size_to_align_size(get_sector_size(vg_uuid))
    r, o, e = direct_dump_resource(path, VGLK_BEGIN * align_size)
    if ' VGLK ' in o:
        return PaxosLease(o, host_id, align_size)
    return None


def get_gllks():
    result = []
    for lockspace in get_lockspaces():
        path = lockspace.split(":")[2]
        host_id = lockspace.split(":")[1]
        vg_uuid = lockspace.split(":")[0].replace("lvm_", "", 1)
        align_size = sector_size_to_align_size(get_sector_size(vg_uuid))
        r, o, e = direct_dump_resource(path, GLLK_BEGIN * align_size)
        if ' GLLK ' in o:
            result.append(PaxosLease(o, host_id, align_size))
    return result


def get_lockspaces():
    result = []
    r, o, e = bash.bash_roe("sanlock client gets")
    if r != 0 or o.strip() == '':
        return result
    return [line.split()[1].strip() for line in o.strip().splitlines() if 's lvm_' in line]


def get_lockspace(vg_uuid):
    r, o, e = bash.bash_roe("sanlock client gets | grep %s" % vg_uuid)
    if r == 0:
        return o.split()[1].strip()
    return None

@bash.in_bash
def repair_delta_lease_if_corrupted(vg_uuid, host_id):
    r, o, e = read_delta_lease(vg_uuid, host_id)
    if r == 0:
        return r, o, e

    back_delta_lease = read_lockspace_metadata_from_backup(vg_uuid, host_id)
    ext_opts = ""
    if back_delta_lease:
        ext_opts += " -g %s " % back_delta_lease[0].owner_generation

    return direct_init_host(vg_uuid, host_id, ext_opts)


@bash.in_bash
def repair_paxos_lease(vg_name, resource_name, offset):
    return bash.bash_roe("sanlock direct init -r lvm_%s:%s:/dev/mapper/%s-lvmlock:%s" % (vg_name, resource_name, vg_name, offset))


@lock.lock("sanlock_backup")
def backup_lockspace_metadata(vg_uuid, host_id):
    if not os.path.exists(SANLOCK_BACKUP_PATH):
        os.mkdir(SANLOCK_BACKUP_PATH)

    bk_file = os.path.join(SANLOCK_BACKUP_PATH, "%s.lockspace" % vg_uuid)
    r, o, e = read_delta_lease(vg_uuid, host_id)
    if r != 0:
        return
    context = {}
    meta_backup = linux.read_file(bk_file)
    if meta_backup:
        try:
            context = jsonobject.loads(meta_backup).__dict__
        except:
            logger.debug("read sanlock backup invalid: {}, overwrite it.".format(meta_backup))
    context.update({str(host_id): DeltaLease(o)})
    linux.write_file(bk_file, jsonobject.dumps(context), create_if_not_exist=True)


def read_lockspace_metadata_from_backup(vg_uuid, host_id=None):
    # type: (str, str) -> list[DeltaLease]
    bk_file = os.path.join(SANLOCK_BACKUP_PATH, "%s.lockspace" % vg_uuid)
    meta_backup = linux.read_file(bk_file)
    if not meta_backup:
        return []
    try:
        meta_backup = jsonobject.loads(meta_backup)
    except:
        logger.debug("read sanlock backup invalid: {}, skip it.".format(meta_backup))
        return []

    if not host_id:
        return meta_backup.__dict__.values()
    elif str(host_id) in meta_backup.__dict__:
        return [meta_backup[str(host_id)]]
    return []


def test_direct_read(path):
    return bash.bash_r("dd if=%s of=/dev/null bs=1M count=1 iflag=direct" % path)


def get_sector_size(vg_uuid):
    if vg_uuid in sector_size_cache:
        return sector_size_cache.get(vg_uuid)

    for delta_lease in read_lockspace_metadata_from_backup(vg_uuid):
        if delta_lease.sector_size in (SECTOR_SIZE_512, SECTOR_SIZE_4K):
            sector_size_cache.update({vg_uuid:delta_lease.sector_size})
            logger.debug("retrieve sanlock backup metadata locally, %s.", delta_lease.__dict__)
            return delta_lease.sector_size

    sector_size = int(linux.get_dev_sector_size("/dev/mapper/{}-lvmlock".format(vg_uuid)))
    if sector_size in (SECTOR_SIZE_512, SECTOR_SIZE_4K):
        sector_size_cache.update({vg_uuid:sector_size})
        return sector_size

    raise Exception("sector size[{}] is invalid".format(sector_size))


def sector_size_to_align_size(sector_size):
    if sector_size == SECTOR_SIZE_512:
        return SMALL_ALIGN_SIZE
    elif sector_size == SECTOR_SIZE_4K:
        return BIG_ALIGN_SIZE
    raise Exception("invalid sector size %s" % sector_size)


class RetryException(Exception):
    pass

def calc_id_renewal_fail_seconds(io_timeout):
    return 8 * int(io_timeout)


def calc_host_dead_seconds(io_timeout):
    return 8 * int(io_timeout) + get_watchdog_fire_timeout()

@bash.in_bash
def get_watchdog_fire_timeout():
    r, o = bash.bash_ro("sanlock client status -D | grep watchdog_fire_timeout")
    if r == 0:
        return int(o.strip().split("=")[1])
    return 60


@ignoreerror
def handle_lease_corrupted_for_adding_lockspace(vg_name, host_id):
    sector_size = get_sector_size(vg_name)

    # init the hostId=1 on its corresponding host
    r, _, _ = read_delta_lease(vg_name, 1, sector_size=sector_size)
    if r != 0:
        lease = DeltaLease()
        lease.sector_size = sector_size
        lease.align_size = sector_size_to_align_size(lease.sector_size)
        lease.lockspace_name = "lvm_" + vg_name
        lease.host_id = 1
        lease.offset = 0
        request_mn_repair_metadata(vg_name, specify_host_by_id=True, **lease.__dict__)

    # init host id lease directly
    if int(host_id) != 1:
        repair_delta_lease_if_corrupted(vg_name, host_id)

    # directly init gllk without using lvmlockctl, as there is no lockspace available
    repair_paxos_lease(vg_name, "_GLLK_disabled", GLLK_BEGIN * sector_size_to_align_size(sector_size))

@bash.in_bash
def handle_paxos_lease_corrupted(error_msg):
    vg_name = None
    lockspace_name = None
    resource_name = None
    for line in error_msg.strip().splitlines():
        line = line.strip()
        match = re.search(r'VG (\S+) lock (skipped|failed): sanlock lease needs repair', line)
        if match:
            vg_name = match.group(1)
            lockspace_name = "lvm_" + vg_name
            resource_name = "VGLK"
            break
        match = re.search(r'LV (\S+)/(\S+) lock failed: sanlock lease needs repair', line)
        if match:
            vg_name = match.group(1)
            lockspace_name = "lvm_" + vg_name
            resource_name = match.group(2)
            break
        match = re.search(r'(Global lock failed|Skipping global lock): sanlock lease needs repair', line)
        if match:
            resource_name = "GLLK"
            break

    if not resource_name:
        return None

    if resource_name == "VGLK":
        # send repair metadata request to mn
        lease = PaxosLease()
        lease.lockspace_name = lockspace_name
        lease.resource_name = resource_name
        lease.sector_size = get_sector_size(vg_name)
        lease.align_size = sector_size_to_align_size(lease.sector_size)
        lease.offset = VGLK_BEGIN * lease.align_size
        return request_mn_repair_metadata(vg_name, **lease.__dict__)

    from zstacklib.utils import lvm
    # LVLK/GLLK lease init directly
    if resource_name == "GLLK":
        lvm.fix_global_lock()
    else:
        attr = lvm.get_lv_attr(os.path.join("/dev/", vg_name, resource_name), "lv_uuid", "lock_args")
        offset = int(attr.get("lv_lockargs").split(":")[-1])
        resource_name = attr.get("lv_uuid")
        bash.bash_errorout("sanlock direct init -r lvm_%s:%s:/dev/mapper/%s-lvmlock:%s" % (vg_name, resource_name,
                                                                                           vg_name, offset))
    return None