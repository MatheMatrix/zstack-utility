"""LVM lock management with lvmlockd and sanlock."""


import functools
import random
import threading
import weakref
from typing import Optional, Dict, List

from zstacklib.utils import bash, shell, linux, log
from zstacklib.storage.lvm.models import LvmLockType

logger = log.get_logger(__name__)

ENABLE_DUP_GLOBAL_CHECK = False


class RetryException(Exception):
    """Exception indicating operation should be retried."""
    pass


class LvmlockdLockType:
    """Lock type constants for lvmlockd."""
    NULL = 0
    SHARE = 1
    EXCLUSIVE = 2

    @staticmethod
    def from_abbr(abbr: str, raise_exception: bool = False) -> int:
        abbr = abbr.strip()
        if abbr == "sh":
            return LvmlockdLockType.SHARE
        elif abbr == "ex":
            return LvmlockdLockType.EXCLUSIVE
        elif abbr == "un":
            return LvmlockdLockType.NULL
        elif abbr == "":
            if raise_exception:
                raise RetryException("can not get locking type since it is active without lvmlock info")
            logger.warn("can not get correct lvm lock type! use null as a safe choice")
            return LvmlockdLockType.NULL
        else:
            raise Exception(f"unknown lock type from abbr: {abbr}")


@bash.in_bash
def get_lv_locking_type(path: str) -> int:
    """Get the current lock type for an LV."""
    from zstacklib.storage.lvm.lv import lv_uuid, lv_is_active
    from zstacklib.utils import lock
    
    @linux.retry(times=5, sleep_time=2)
    def _get_lv_locking_type(path: str) -> int:
        output = bash.bash_o(f"lvmlockctl -i | grep {lv_uuid(path)} | head -n1 | awk '{{print $3}}'")
        return LvmlockdLockType.from_abbr(output.strip(), raise_exception=True)

    locking_type = LvmlockdLockType.NULL
    active = None
    with lock.NamedLock(path.split("/")[-1]):
        try:
            active = lv_is_active(path)
            if not active:
                return locking_type
            locking_type = _get_lv_locking_type(path)
        except Exception:
            output = bash.bash_o(f"lvmlockctl -i | grep {lv_uuid(path)} | head -n1 | awk '{{print $3}}'")
            locking_type = LvmlockdLockType.from_abbr(output.strip(), raise_exception=False)
            if active and locking_type == LvmlockdLockType.NULL:
                locking_type = LvmlockdLockType.SHARE

    return locking_type


_internal_lock = threading.RLock()
_lv_locks: weakref.WeakValueDictionary = weakref.WeakValueDictionary()


class LvLockOperator:
    """Manages lock reference counting for logical volumes."""
    
    def __init__(self, abs_path: str):
        self.op_lock = threading.Lock()
        self.inited = False
        self.abs_path = abs_path
        self.exists_locks: List[int] = []

    def _init(self) -> None:
        exists_lock = get_lv_locking_type(self.abs_path)
        self.exists_locks = [] if exists_lock == LvmlockdLockType.NULL else [exists_lock]
        self.inited = True
        logger.debug(f"lv [path:{self.abs_path}] lock operator inited, existing lock: {exists_lock}")

    def lock(self, target_lock: int) -> None:
        from zstacklib.storage.lvm.lv import _active_lv
        
        with self.op_lock:
            if not self.inited:
                self._init()

            if all(l < target_lock for l in self.exists_locks):
                _active_lv(self.abs_path, target_lock == LvmlockdLockType.SHARE)
            self.exists_locks.append(target_lock)
            logger.debug(f"lv [path:{self.abs_path}] add lock {target_lock}, existing locks: {self.exists_locks}")

    def force_lock(self, target_lock: int) -> None:
        from zstacklib.storage.lvm.lv import _active_lv
        
        with self.op_lock:
            self.exists_locks = [exist_lock for exist_lock in self.exists_locks if exist_lock <= target_lock]
            _active_lv(self.abs_path, target_lock == LvmlockdLockType.SHARE)
            self.exists_locks.append(target_lock)
            logger.debug(f"lv [path:{self.abs_path}] force lock to {target_lock}, existing locks: {self.exists_locks}")

    def unlock(self, target_lock: int) -> None:
        from zstacklib.storage.lvm.lv import _active_lv, _deactive_lv
        
        with self.op_lock:
            try:
                self.exists_locks.remove(target_lock)
            except ValueError:
                pass

            after_lock_type = LvmlockdLockType.NULL if len(self.exists_locks) == 0 else max(self.exists_locks)
            if after_lock_type == LvmlockdLockType.NULL:
                _deactive_lv(self.abs_path, raise_exception=False)
            elif after_lock_type == LvmlockdLockType.SHARE:
                _active_lv(self.abs_path, True)

            logger.debug(
                f"lv [path:{self.abs_path}] remove lock {target_lock}, unlock to {after_lock_type}, existing locks: {self.exists_locks}"
            )

    def force_unlock(self, raise_exception: bool = True) -> None:
        from zstacklib.storage.lvm.lv import _deactive_lv
        
        with self.op_lock:
            self.exists_locks.clear()
            _deactive_lv(self.abs_path, raise_exception)
            logger.debug(f"lv [path:{self.abs_path}] force unlock to 0")

    @staticmethod
    def get_lock_cnt(abs_path: str) -> 'LvLockOperator':
        global _lv_locks, _internal_lock
        with _internal_lock:
            lock_cnt = _lv_locks.get(abs_path, LvLockOperator(abs_path))
            if abs_path not in _lv_locks:
                _lv_locks[abs_path] = lock_cnt
            return lock_cnt

    @staticmethod
    def get_lock_cnt_or_else_none(abs_path: str) -> Optional['LvLockOperator']:
        global _lv_locks, _internal_lock
        with _internal_lock:
            return _lv_locks.get(abs_path)


class OperateLv:
    """Context manager for LV lock acquisition."""
    
    def __init__(self, abs_path: str, shared: bool = False, delete_when_exception: bool = False):
        self.abs_path = abs_path
        self.lock_ref_cnt = LvLockOperator.get_lock_cnt(abs_path)
        self.target_lock = LvmlockdLockType.SHARE if shared else LvmlockdLockType.EXCLUSIVE
        self.delete_when_exception = delete_when_exception

    def __enter__(self) -> None:
        self.lock_ref_cnt.lock(self.target_lock)

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        from zstacklib.storage.lvm.lv import delete_lv
        
        if exc_val is not None and self.delete_when_exception:
            delete_lv(self.abs_path, False)
            return

        self.lock_ref_cnt.unlock(self.target_lock)


class RecursiveOperateLv:
    """Context manager for recursive LV lock acquisition (follows backing chain)."""
    
    def __init__(
        self,
        abs_path: str,
        shared: bool = False,
        skip_deactivate_tags: Optional[List[str]] = None,
        delete_when_exception: bool = False
    ):
        self.abs_path = abs_path
        self.shared = shared
        self.lock_ref_cnt = LvLockOperator.get_lock_cnt(abs_path)
        self.target_lock = LvmlockdLockType.SHARE if shared else LvmlockdLockType.EXCLUSIVE
        self.backing: Optional[RecursiveOperateLv] = None
        self.delete_when_exception = delete_when_exception
        self.skip_deactivate_tags = skip_deactivate_tags

    def __enter__(self) -> None:
        self.lock_ref_cnt.lock(self.target_lock)
        backing_file = linux.qcow2_get_backing_file(self.abs_path)
        if backing_file != "":
            self.backing = RecursiveOperateLv(
                backing_file, True, self.skip_deactivate_tags, False
            )

        if self.backing is not None:
            self.backing.__enter__()

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        from zstacklib.storage.lvm.lv import delete_lv, has_one_lv_tag_sub_string
        
        if self.backing is not None:
            self.backing.__exit__(exc_type, exc_val, exc_tb)

        if exc_val is not None \
                and self.delete_when_exception \
                and not has_one_lv_tag_sub_string(self.abs_path, self.skip_deactivate_tags):
            delete_lv(self.abs_path, False)
            return

        if has_one_lv_tag_sub_string(self.abs_path, self.skip_deactivate_tags):
            logger.debug(f"the volume {self.abs_path} has skip tag")

        self.lock_ref_cnt.unlock(self.target_lock)


def lv_operate(abs_path: str, shared: bool = False):
    """Decorator for functions that need LV lock during execution."""
    def wrap(f):
        @functools.wraps(f)
        def inner(*args, **kwargs):
            with OperateLv(abs_path, shared):
                retval = f(*args, **kwargs)
            return retval
        return inner
    return wrap


def qcow2_lv_recursive_operate(abs_path: str, shared: bool = False):
    """Decorator for functions that need recursive LV lock."""
    def wrap(f):
        @functools.wraps(f)
        def inner(*args, **kwargs):
            with RecursiveOperateLv(abs_path, shared):
                retval = f(*args, **kwargs)
            return retval
        return inner
    return wrap


@bash.in_bash
def check_stuck_vglk() -> None:
    """Check for and release stuck VGLK locks."""
    @linux.retry(3, 1)
    def is_stuck_vglk():
        r, o, e = bash.bash_roe("sanlock client status | grep ':VGLK:'")
        if r != 0:
            return
        else:
            raise RetryException("found sanlock vglk lock stuck")
    try:
        is_stuck_vglk()
    except Exception:
        r, o, e = bash.bash_roe("sanlock client status | grep ':VGLK:'")
        if r != 0:
            return
        if len(o.strip().splitlines()) == 0:
            return
        for stucked in o.strip().splitlines():
            if "ADD" in stucked or "REM" in stucked:
                continue
            cmd = "sanlock client release -%s" % stucked.replace(" p ", " -p ")
            r, o, e = bash.bash_roe(cmd)
            logger.warn(
                f"find stuck vglk and already released, detail: [return_code: {r}, stdout: {o}, stderr: {e}]"
            )


@bash.in_bash
def fix_global_lock() -> None:
    """Fix duplicate global lock issues."""
    if not ENABLE_DUP_GLOBAL_CHECK:
        return
    vg_names = bash.bash_o("lvmlockctl -i | awk '/lock_type=sanlock/{print $2}'").strip().splitlines()
    vg_names.sort()
    if len(vg_names) < 2:
        return
    for vg_name in vg_names[1:]:
        bash.bash_roe(f"lvmlockctl --gl-disable {vg_name}")
    bash.bash_roe(f"lvmlockctl --gl-enable {vg_names[0]}")


@bash.in_bash
def check_gl_lock() -> None:
    """Check and enable global lock if needed."""
    r, o = bash.bash_ro("lvmlockctl -i | grep 'LK GL' -B 5")
    if r == 0:
        return

    r, o = bash.bash_ro("lvmlockctl -i | grep 'lock_type=sanlock' | awk '{print $2}'")
    if r == 0:
        o = o.strip()
        if len(o.splitlines()) != 0:
            for i in o.splitlines():
                i = i.strip()
                if i == "":
                    continue
                bash.bash_roe(f"lvmlockctl --gl-enable {i}")
                return


@bash.in_bash
def drop_vg_lock(vg_uuid: str) -> None:
    """Drop lock for a volume group."""
    bash.bash_roe(f"lvmlockctl --gl-disable {vg_uuid}")
    bash.bash_roe(f"lvmlockctl --drop {vg_uuid}")


def get_lockspace(vg_uuid: str) -> str:
    """Get sanlock lockspace for a VG."""
    @linux.retry(times=3, sleep_time=1)
    def _do_get_lockspace(vg_uuid: str) -> str:
        o = bash.bash_o(f"sanlock client gets | awk '{{print $2}}' | grep {vg_uuid}").strip()
        if o == "":
            raise RetryException("lockspace not found")
        return o

    out = bash.bash_o(f"sanlock client gets | awk '{{print $2}}' | grep {vg_uuid}").strip()
    if out != "":
        return out
    try:
        logger.debug(f"retrying get lockspace for vg {vg_uuid}")
        out = _do_get_lockspace(vg_uuid)
    except Exception:
        out = bash.bash_o(f"sanlock client gets | awk '{{print $2}}' | grep {vg_uuid}").strip()

    return out
