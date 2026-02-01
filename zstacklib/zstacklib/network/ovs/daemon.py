# Copyright (c) ZStack.io, Inc.

"""
Open vSwitch daemon management.

Provides the Ovs class for controlling ovsdb-server and ovs-vswitchd lifecycle.
"""

from __future__ import annotations

import logging
import os
import shutil
import time
import uuid

from zstacklib.utils import lock
from zstacklib.utils import shell

from .config import (
    CONF_DB, CONF_PATH, CTL_BIN, DB_CTL_FILE_PATH, DB_LOG_PATH, DB_PID_PATH,
    DB_SOCK, LOGROTATE_CONF, LOGROTATE_FILE, OVS_RUN_PATH,
    SWITCH_CTL_FILE_PATH, SWITCH_LOG_PATH, SWITCH_PID_PATH,
)
from .exceptions import OvsError, OvsDaemonError
from .utils import get_os_release_info, version_geq
from .venv import OvsVenv


logger = logging.getLogger(__name__)


class Ovs:
    """OVS daemon lifecycle manager.

    Controls ovsdb-server and ovs-vswitchd processes.
    Ensures OvsVenv is ready before starting daemons.

    Attributes:
        venv: OVS environment manager.
        ovs_schema: Path to OVS schema file.
    """

    def __init__(self):
        self.venv = OvsVenv()
        self.ovs_schema = self._get_ovs_schema()

    def _get_ovs_schema(self) -> str:
        """Get path to OVS schema file."""
        ovs_dir = '/usr/share/openvswitch/'
        path = os.path.join(ovs_dir, 'vswitchd', 'vswitch.ovsschema')
        if os.path.isfile(path):
            return path
        return os.path.join(ovs_dir, 'vswitch.ovsschema')

    def start(self) -> None:
        """Start both ovsdb-server and ovs-vswitchd.

        Raises:
            OvsError: If startup fails.
        """
        try:
            self.start_db()
            self.start_switch()
        except OvsError:
            self.stop()
            raise

    def stop(self) -> None:
        """Stop both daemons."""
        self.stop_db()
        self.stop_switch()

    def restart(self) -> None:
        """Restart both daemons."""
        self.stop()
        self.start()

    def is_ovs_proc_running(self, proc_name: str | None = None) -> bool:
        """Check if OVS processes are running.

        Args:
            proc_name: Specific process to check ('ovsdb-server' or 'ovs-vswitchd').
                      If None, checks both.

        Returns:
            True if specified process(es) are running.
        """
        proc_name_to_pids = {
            'ovsdb-server': self.pids[0],
            'ovs-vswitchd': self.pids[1],
        }

        if proc_name:
            pids = [proc_name_to_pids[proc_name]]
        else:
            pids = self.pids

        for pid in pids:
            if pid <= 0:
                return False
            if not self._process_exists(pid):
                return False

        return True

    def _create_ovs_db(self) -> None:
        """Create a new OVS database."""
        ret = shell.run(f'ovsdb-tool -v create {CONF_DB} {self.ovs_schema}')
        if ret != 0:
            raise OvsDaemonError('ovsdb-server', 'Create ovsdb file failed.')

    def _backup_ovs_db(self) -> None:
        """Backup existing OVS database."""
        get_db_ver_cmd = shell.ShellCmd(f'ovsdb-tool db-version {CONF_DB}')
        get_db_ver_cmd(False)
        version = get_db_ver_cmd.stdout if get_db_ver_cmd.return_code == 0 else 'old'

        get_db_cksum_cmd = shell.ShellCmd(f"ovsdb-tool db-cksum {CONF_DB} | awk '{{print $1}}'")
        get_db_cksum_cmd(False)
        cksum = get_db_cksum_cmd.stdout if get_db_cksum_cmd.return_code == 0 else 'unknown'

        backup = CONF_DB + '.backup' + version + '-' + cksum
        shutil.copy2(CONF_DB, backup)

    def _convert_ovs_db(self) -> None:
        """Convert OVS database to new schema version."""
        # Compact database first
        shell.run(f'ovsdb-tool compact {CONF_DB}')

        ret = shell.run(f'ovsdb-tool convert {CONF_DB} {self.ovs_schema}')
        if ret != 0:
            logger.warning('Schema conversion failed, using empty database instead')
            os.remove(CONF_DB)
            self._create_ovs_db()

    def upgrade_db(self) -> None:
        """Create or upgrade OVS database as needed."""
        if not os.path.isfile(CONF_DB):
            self._create_ovs_db()
            return

        s = shell.ShellCmd(
            f'ovsdb-tool needs-conversion {CONF_DB} {self.ovs_schema}',
            None, False
        )
        s(False)

        if s.return_code != 0:
            logger.warning(f'upgrade ovsdb failed: {s.stderr} {s.stdout}')
            return
        elif s.stdout.strip() != 'yes':
            logger.debug('current ovsdb do not need conversion.')
            return
        else:
            self._backup_ovs_db()
            self._convert_ovs_db()
            logger.debug('upgrade ovsdb success.')

    def _init_ovs_db_setting(self) -> None:
        """Initialize OVS database settings."""
        ret = shell.run(
            CTL_BIN + f'--no-wait -- init -- set Open_vSwitch . db-version={self.venv.version_info.ovsdb_ver}'
        )
        if ret != 0:
            raise OvsDaemonError('ovsdb-server', 'Init openvswitch database settings failed.')

        time.sleep(1)

        # Get OS release info
        os_release = get_os_release_info()
        system_type = os_release.get('ID', 'linux')
        system_version = os_release.get('VERSION_ID', 'unknown')

        cmd = (
            CTL_BIN +
            f'--no-wait set Open_vSwitch . ovs-version={self.venv.version_info.vswitch_ver}' +
            f' external-ids:system-id={uuid.uuid4()}' +
            f' external-ids:rundir={OVS_RUN_PATH}' +
            f' system-type={system_type}' +
            f' system-version={system_version}'
        )

        if shell.run(cmd) != 0:
            logger.warning('Set OS informations to ovsdb failed.')

    @lock.lock('startDB')
    def start_db(self) -> None:
        """Start ovsdb-server.

        Raises:
            OvsDaemonError: If startup fails.
        """
        if self.is_ovs_proc_running('ovsdb-server'):
            return

        self.stop_db()
        self.upgrade_db()

        cmd = (
            f'ovsdb-server {CONF_DB}' +
            ' -vconsole:emer -vsyslog:err -vfile:info' +
            f' --remote=punix:{DB_SOCK}' +
            ' --private-key=db:Open_vSwitch,SSL,private_key' +
            ' --certificate=db:Open_vSwitch,SSL,certificate' +
            ' --bootstrap-ca-cert=db:Open_vSwitch,SSL,ca_cert' +
            f' --no-chdir --log-file={DB_LOG_PATH} --pidfile={DB_PID_PATH} --unixctl={DB_CTL_FILE_PATH}' +
            ' --detach --monitor'
        )

        start_db_cmd = shell.ShellCmd(cmd)
        start_db_cmd(False)

        if start_db_cmd.return_code != 0:
            raise OvsDaemonError(
                'ovsdb-server',
                f'start ovsdb failed: {start_db_cmd.stderr} {start_db_cmd.stdout}'
            )

        self._init_ovs_db_setting()
        logger.debug(f'ovsdb start success. pid:[{self.pids[0]}]')

    def stop_db(self) -> None:
        """Stop ovsdb-server."""
        self._stop_ovs_process('ovsdb-server')

    def restart_db(self) -> None:
        """Restart ovsdb-server."""
        self.stop_db()
        self.start_db()

    def check_ovs_configuration(self, key: str, value: str) -> bool:
        """Check if an OVS configuration value is set.

        Args:
            key: Configuration key.
            value: Expected value.

        Returns:
            True if configuration matches.
        """
        try:
            ret = shell.call(
                CTL_BIN + f'get Open_vSwitch . other_config:{key}'
            ).strip('\n').strip('"')
            return ret == str(value)
        except shell.ShellError:
            return False

    def _get_dpdk_init_states(self) -> bool:
        """Check if DPDK is initialized."""
        if not self.venv.is_dpdk_support():
            return False
        if not self.is_ovs_proc_running('ovsdb-server'):
            return False
        if not self.check_ovs_configuration('dpdk-init', 'true'):
            return False
        return True

    @lock.lock('startSwitch')
    def start_switch(self) -> None:
        """Start ovs-vswitchd.

        Raises:
            OvsDaemonError: If startup fails.
        """
        if self.is_ovs_proc_running('ovs-vswitchd'):
            return

        self.stop_switch()

        if self._get_dpdk_init_states():
            self.venv.allocate_hugepage_mem()

        cmd = (
            f'ovs-vswitchd unix:{DB_SOCK}' +
            ' -vconsole:emer -vsyslog:err -vfile:info' +
            ' --mlockall --no-chdir' +
            f' --log-file={SWITCH_LOG_PATH} --pidfile={SWITCH_PID_PATH} --unixctl={SWITCH_CTL_FILE_PATH}' +
            ' --detach --monitor'
        )

        start_switch_cmd = shell.ShellCmd(cmd)
        start_switch_cmd(False)

        if start_switch_cmd.return_code != 0:
            raise OvsDaemonError(
                'ovs-vswitchd',
                f'start ovs-vswitch failed: {start_switch_cmd.stderr} {start_switch_cmd.stdout}'
            )

        self.set_ovs_logrotate()
        logger.debug(f'ovs-vswitch start success. pid:[{self.pids[1]}]')

    def stop_switch(self) -> None:
        """Stop ovs-vswitchd."""
        self._stop_ovs_process('ovs-vswitchd')

    def restart_switch(self) -> None:
        """Restart ovs-vswitchd."""
        self.stop_switch()
        self.start_switch()

    @property
    def pids(self) -> list[int]:
        """Get PIDs of OVS processes.

        Returns:
            List [ovsdb_pid, ovs_vswitchd_pid].
        """
        result = [-1, -1]
        try:
            ovsdb_pidf = os.path.join(OVS_RUN_PATH, 'ovsdb-server.pid')
            vswitch_pidf = os.path.join(OVS_RUN_PATH, 'ovs-vswitchd.pid')

            if os.path.exists(ovsdb_pidf):
                with open(ovsdb_pidf, 'r') as f:
                    result[0] = int(f.read().strip())

            if os.path.exists(vswitch_pidf):
                with open(vswitch_pidf, 'r') as f:
                    result[1] = int(f.read().strip())
        except OSError as err:
            logger.error(f'OSError: {err}')

        return result

    def _process_exists(self, pid: int) -> bool:
        """Check if a process exists."""
        return os.path.isdir(os.path.join('/proc', str(pid)))

    def _stop_process_in_schedule(self, proc_name: str, proc_info_dict: dict) -> None:
        """Stop a process using graceful/forced methods."""
        pid = proc_info_dict[proc_name]['pid']
        ver = proc_info_dict[proc_name]['ver']
        ctl = proc_info_dict[proc_name]['ctl']
        pid_path = os.path.join(OVS_RUN_PATH, f'{proc_name}.pid')

        graceful = 'EXIT 0.1 0.25 0.65 1'
        actions = 'TERM 0.1 0.25 0.65 1 1 1 1 KILL 1 1 1 2 10 15 30 FAIL'

        # Use ovs-appctl exit for versions >= 2.5.90
        if version_geq(ver, '2.5.90'):
            actions = graceful + ' ' + actions

        force_stop = False
        for action in actions.split():
            if not self._process_exists(pid):
                if force_stop:
                    return
                else:
                    # Check one more time
                    if not os.path.exists(pid_path) and not self._process_exists(pid):
                        return

            if action == 'EXIT':
                shell.run(f'ovs-appctl -T 1 -t {ctl} exit ')
            elif action == 'TERM':
                shell.run(f'kill {pid}')
                force_stop = True
            elif action == 'KILL':
                shell.run(f'kill -9 {pid}')
                force_stop = True
            elif action == 'FAIL':
                raise OvsError(f'Killing {proc_name} {pid} failed')
            else:
                time.sleep(float(action))

    def _stop_ovs_process(self, proc_name: str) -> None:
        """Stop ovsdb or vswitchd by ovs-appctl, or kill if needed."""
        proc_dict = {
            'ovsdb-server': {
                'pid': self.pids[0],
                'ver': self.venv.version_info.ovsdb_ver,
                'ctl': DB_CTL_FILE_PATH,
            },
            'ovs-vswitchd': {
                'pid': self.pids[1],
                'ver': self.venv.version_info.vswitch_ver,
                'ctl': SWITCH_CTL_FILE_PATH,
            },
        }

        pid = proc_dict[proc_name]['pid']
        ctl = proc_dict[proc_name]['ctl']

        if pid < 0:
            return

        try:
            pid_path = os.path.join(OVS_RUN_PATH, f'{proc_name}.pid')
            if not self._process_exists(pid):
                if os.path.exists(pid_path):
                    os.remove(pid_path)
                if os.path.exists(ctl):
                    os.remove(ctl)
                return
            else:
                self._stop_process_in_schedule(proc_name, proc_dict)
        except OSError as err:
            logger.error(f'OSError: {err}')
            raise OvsError(str(err))

    def set_ovs_logrotate(self) -> None:
        """Set up logrotate for OVS logs."""
        first_time_logrotate = not os.path.exists(LOGROTATE_FILE)

        with open(LOGROTATE_FILE, 'w') as f:
            f.write(LOGROTATE_CONF)

        if first_time_logrotate:
            ret = shell.run('logrotate --force /etc/logrotate.d/openvswitch-zstack')
            if ret != 0:
                raise OvsError('set logrotate for openvswitch failed.')

        logger.debug('set logrotate for openvswitch success.')
