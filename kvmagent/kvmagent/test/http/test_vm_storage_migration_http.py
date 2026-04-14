# -*- coding: utf-8 -*-
"""Remote-only storage migration test that validates block-job observability."""
import hashlib
import json
import time
import urllib.request
from datetime import datetime

import pytest


pytestmark = [
    pytest.mark.remote_xfail(
        reason='requires real MN + kvmagent + migratable VM'),
]


def _mn_json_request(base_url, path, session_uuid, body=None, method='GET'):
    url = '%s%s' % (base_url.rstrip('/'), path)
    data = None if body is None else json.dumps(body).encode('utf-8')
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header('Content-Type', 'application/json')
    if session_uuid:
        req.add_header('Authorization', 'OAuth %s' % session_uuid)
    with urllib.request.urlopen(req, timeout=30) as rsp:
        payload = rsp.read().decode('utf-8')
    return json.loads(payload) if payload.strip() else {}


def _mn_login(base_url, account, password):
    hashed = hashlib.sha512(password.encode('utf-8')).hexdigest()
    rsp = _mn_json_request(
        base_url,
        '/v1/accounts/login',
        None,
        body={'logInByAccount': {'accountName': account, 'password': hashed}},
        method='PUT',
    )
    return rsp['inventory']['uuid']


def _get_required_option(request, name):
    value = request.config.getoption(name)
    if value:
        return value
    pytest.skip('missing required option: --%s' % name.replace('_', '-'))


def _parse_progress_details(log_text):
    samples = []
    for line in log_text.splitlines():
        marker = 'detail: '
        if marker not in line:
            continue
        try:
            left, detail = line.split(marker, 1)
            timestamp = left.split(' ')[1].rstrip(',')
            payload = json.loads(detail)
        except Exception:
            continue

        if payload.get('stage') != 'migrating':
            continue
        if 'processed' not in payload or 'speed' not in payload:
            continue
        samples.append((timestamp, payload))
    return samples


def _append_qmp_samples(samples, qmp_text, fallback_timestamp):
    try:
        qmp_obj = json.loads(qmp_text.strip())
    except Exception:
        return samples

    jobs = qmp_obj.get('return') or []
    if not jobs:
        return samples

    job = jobs[0]
    samples.append({
        'timestamp': fallback_timestamp,
        'device': job.get('device'),
        'offset': job.get('offset', 0),
        'len': job.get('len', 0),
        'speed': job.get('speed'),
        'status': job.get('status'),
    })
    return samples


@pytest.fixture(autouse=True)
def _require_remote(http_client):
    if not http_client.is_remote:
        pytest.skip('requires remote kvmagent')


@pytest.fixture(scope='module')
def storage_migration_case(request, http_client):
    mn_url = _get_required_option(request, 'mn_url')
    mn_password = _get_required_option(request, 'mn_password')
    vm_uuid = _get_required_option(request, 'storage_migrate_vm_uuid')
    dst_ps_uuid = _get_required_option(request, 'storage_migrate_dst_ps_uuid')
    dst_host_uuid = _get_required_option(request, 'storage_migrate_dst_host_uuid')

    session_uuid = _mn_login(
        mn_url,
        request.config.getoption('mn_account'),
        mn_password,
    )

    vm_rsp = _mn_json_request(mn_url, '/v1/vm-instances/%s' % vm_uuid, session_uuid)
    inventories = vm_rsp.get('inventories') or []
    if not inventories:
        pytest.skip('vm not found on MN: %s' % vm_uuid)

    vm_inv = inventories[0]
    if vm_inv.get('state') != 'Running':
        pytest.skip('vm is not running: %s' % vm_inv.get('state'))

    current_host_uuid = vm_inv.get('hostUuid')
    host_rsp = _mn_json_request(mn_url, '/v1/hosts/%s' % current_host_uuid, session_uuid)
    src_host_inv = (host_rsp.get('inventories') or [None])[0]
    if src_host_inv is None:
        pytest.skip('current host not found on MN: %s' % current_host_uuid)

    direct_host = request.config.getoption('direct_host')
    if direct_host and direct_host != src_host_inv.get('managementIp'):
        pytest.skip('direct-host %s is not current source host %s' % (direct_host, src_host_inv.get('managementIp')))

    return {
        'mn_url': mn_url,
        'session_uuid': session_uuid,
        'vm_uuid': vm_uuid,
        'dst_ps_uuid': dst_ps_uuid,
        'dst_host_uuid': dst_host_uuid,
        'bandwidth': request.config.getoption('storage_migrate_bandwidth'),
        'timeout': request.config.getoption('storage_migrate_timeout'),
        'poll_interval': request.config.getoption('storage_migrate_poll_interval'),
        'src_host_ip': src_host_inv.get('managementIp'),
    }


class TestVmStorageMigrationRemote:
    def test_storage_migration_exposes_block_job_progress(self, http_client, host_plugin, storage_migration_case):
        body = {
            'primaryStorageMigrateVm': {
                'dstPrimaryStorageUuid': storage_migration_case['dst_ps_uuid'],
                'dstHostUuid': storage_migration_case['dst_host_uuid'],
                'withSnapshots': False,
                'withDataVolumes': False,
            }
        }
        if storage_migration_case['bandwidth'] > 0:
            body['primaryStorageMigrateVm']['bandwidth'] = storage_migration_case['bandwidth']

        trigger_rsp = _mn_json_request(
            storage_migration_case['mn_url'],
            '/v1/vm-instances/%s/actions' % storage_migration_case['vm_uuid'],
            storage_migration_case['session_uuid'],
            body=body,
            method='PUT',
        )
        if 'error' in trigger_rsp:
            pytest.fail('storage migration trigger failed: %s' % trigger_rsp['error'])

        job_path = trigger_rsp['location'].replace(storage_migration_case['mn_url'], '')
        deadline = time.time() + storage_migration_case['timeout']
        saw_running_job = False
        saw_query_status = False
        log_line_rsp = http_client._ssh_run('wc -l /var/log/zstack/zstack-kvmagent.log | awk \'{print $1}\'')
        start_line = int(log_line_rsp[1].strip() or '1') if log_line_rsp[0] == 0 else 1
        progress_samples = []
        qmp_samples = []

        while time.time() < deadline:
            qmp_rc, qmp_stdout, qmp_stderr = http_client._ssh_run(
                "virsh qemu-monitor-command %s '{\"execute\": \"query-block-jobs\"}'" %
                storage_migration_case['vm_uuid']
            )
            if qmp_rc == 0 and qmp_stdout.strip():
                qmp_samples = _append_qmp_samples(
                    qmp_samples, qmp_stdout, datetime.now().strftime('%H:%M:%S.%f')
                )
                qmp_obj = json.loads(qmp_stdout.strip())
                jobs = qmp_obj.get('return') or []
                if jobs:
                    saw_running_job = True
                    job = jobs[0]
                    rsp = http_client.post_async('/vm/volume/queryblockjobstatus', {
                        'vmUuid': storage_migration_case['vm_uuid'],
                    }, timeout=20)
                    saw_query_status = True
                    assert rsp.success is True
                    assert rsp.status in ('running', 'ready', 'completed')
                    assert rsp.total == job['len']
                    assert rsp.offset == job['offset']
                    assert rsp.remain == job['len'] - job['offset']
                    assert 0 <= rsp.percent <= 100

            log_rc, log_stdout, _ = http_client._ssh_run(
                "tail -n +%d /var/log/zstack/zstack-kvmagent.log | grep -a \"commandpath': '/progress/report'\" | tail -n 100" % start_line
            )
            if log_rc == 0 and log_stdout.strip():
                progress_samples = _parse_progress_details(log_stdout)

            job_rsp = _mn_json_request(
                storage_migration_case['mn_url'],
                job_path,
                storage_migration_case['session_uuid'],
            )
            if job_rsp.get('error'):
                pytest.fail('storage migration job failed: %s' % job_rsp['error'])
            if job_rsp.get('inventory'):
                root_volume = (job_rsp['inventory'].get('allVolumes') or [{}])[0]
                assert root_volume.get('primaryStorageUuid') == storage_migration_case['dst_ps_uuid']
                assert saw_running_job or progress_samples, 'no migration evidence observed during storage migration'
                if saw_running_job:
                    assert saw_query_status, 'queryblockjobstatus was never sampled during running block job'

                increasing = []
                for previous, current in zip(progress_samples, progress_samples[1:]):
                    previous_ts = datetime.strptime(previous[0], '%H:%M:%S.%f')
                    current_ts = datetime.strptime(current[0], '%H:%M:%S.%f')
                    delta_t = (current_ts - previous_ts).total_seconds()
                    delta_processed = current[1]['processed'] - previous[1]['processed']
                    if delta_t <= 0 or delta_processed <= 0:
                        continue
                    expected = delta_processed / delta_t
                    actual = current[1]['speed']
                    increasing.append((expected, actual))

                assert increasing, 'no increasing processed samples found in agent progress logs'
                for expected, actual in increasing[:5]:
                    tolerance = max(expected * 0.3, 8 * 1024 * 1024)
                    assert abs(actual - expected) <= tolerance, (
                        'agent speed %s deviates from processed delta/time %s' % (actual, expected)
                    )

                qmp_increasing = []
                for previous, current in zip(qmp_samples, qmp_samples[1:]):
                    previous_ts = datetime.strptime(previous['timestamp'], '%H:%M:%S.%f')
                    current_ts = datetime.strptime(current['timestamp'], '%H:%M:%S.%f')
                    delta_t = (current_ts - previous_ts).total_seconds()
                    delta_offset = current['offset'] - previous['offset']
                    if delta_t <= 0 or delta_offset <= 0:
                        continue
                    qmp_increasing.append({
                        'expected': delta_offset / delta_t,
                        'reported': current.get('speed'),
                        'status': current.get('status'),
                    })

                assert qmp_samples, 'no qmp block-job samples collected'
                assert any(sample['status'] in ('running', 'ready') for sample in qmp_samples), \
                    'qmp never reported running/ready block job'

                if storage_migration_case['bandwidth'] > 0:
                    qos_bytes = storage_migration_case['bandwidth'] * 1024 * 1024
                    reported_qmp_speeds = [sample['reported'] for sample in qmp_samples if sample.get('reported') is not None]
                    assert reported_qmp_speeds, 'qmp never reported block-job speed'
                    for reported in reported_qmp_speeds[:5]:
                        assert abs(reported - qos_bytes) <= max(qos_bytes * 0.1, 4096), (
                            'qmp speed %s does not match qos %s' % (reported, qos_bytes)
                        )

                    progress_actuals = [actual for _, actual in increasing if actual > 0]
                    assert progress_actuals, 'agent progress speed never became positive'
                    assert any(actual > qos_bytes for actual in progress_actuals), (
                        'expected at least one agent speed sample above qos %s to prove mixed metric path' % qos_bytes
                    )
                return

            time.sleep(storage_migration_case['poll_interval'])

        pytest.fail('storage migration did not finish within %ss' % storage_migration_case['timeout'])
