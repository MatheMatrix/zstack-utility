import os
import re

import simplejson

from zstacklib.utils import lvm_range


LVM_REPORT_TIMEOUT_SECONDS = 60
_LVM_IDENTIFIER_PATTERN = re.compile(r"^[A-Za-z0-9+_.-]+$")


class LvRangeTarget(object):
    def __init__(self, resource_uuid, absolute_install_path):
        self.resourceUuid = resource_uuid
        self.absoluteInstallPath = absolute_install_path


def _run_lvm_json_report(command):
    from zstacklib.utils import shell

    cmd = shell.ShellCmd(
        "timeout %s %s" % (LVM_REPORT_TIMEOUT_SECONDS, command))
    cmd(is_exception=False)
    if cmd.return_code != 0:
        raise Exception(
            "failed to query LVM range metadata, command[%s], error[%s]" %
            (command, cmd.stderr))
    try:
        return simplejson.loads(cmd.stdout)
    except Exception:
        raise Exception(
            "failed to parse LVM JSON report from command[%s], output[%s]" %
            (command, cmd.stdout))


def _get_vg_range_report(vg_uuid):
    from zstacklib.utils import linux

    return _run_lvm_json_report(
        "vgs --readonly --nolocking -t --units b --nosuffix "
        "--reportformat json -o %s %s" % (
            ",".join(lvm_range.VG_RANGE_REPORT_FIELDS),
            linux.shellquote(vg_uuid)))


def _get_lv_range_report(absolute_install_paths):
    from zstacklib.utils import linux

    quoted_paths = " ".join(
        [linux.shellquote(path) for path in absolute_install_paths])
    return _run_lvm_json_report(
        "lvs --readonly --nolocking -t --segments --units b --nosuffix "
        "--reportformat json -o vg_uuid,lv_uuid,lv_name,lv_size,segtype,"
        "seg_start_pe,seg_size_pe,seg_pe_ranges %s" % quoted_paths)


def _get_pv_range_report(vg_uuid):
    from zstacklib.utils import linux

    return _run_lvm_json_report(
        "pvs --readonly --nolocking -t --units b --nosuffix "
        "--reportformat json -o %s -S %s" % (
            ",".join(lvm_range.PV_RANGE_REPORT_FIELDS),
            linux.shellquote("vg_name=%s" % vg_uuid)))


def _get_pv_duplicate_audit_report():
    return _run_lvm_json_report(
        "pvs --readonly --nolocking -t --all --units b --nosuffix "
        "--reportformat json -o %s" % (
            ",".join(lvm_range.PV_DUPLICATE_AUDIT_FIELDS)))


def _candidate_paths(candidate):
    paths = []
    dev_name = getattr(candidate, "dev_name", None)
    if dev_name:
        paths.append("/dev/%s" % dev_name)
    multipath_path = getattr(candidate, "multipathPath", None)
    if multipath_path:
        paths.append("/dev/mapper/%s" % multipath_path)
    by_path = getattr(candidate, "path", None)
    if by_path:
        paths.append("/dev/disk/by-path/%s" % by_path)

    wwid = getattr(candidate, "wwid", None)
    if wwid:
        paths.extend([
            "/dev/disk/by-id/scsi-%s" % wwid,
            "/dev/disk/by-id/dm-uuid-mpath-%s" % wwid,
            "/dev/mapper/%s" % wwid
        ])

    paths.extend([
        os.path.realpath(path) for path in list(paths)
        if os.path.exists(path)
    ])
    return list(set(paths))


def _get_block_device_capacity(path):
    from zstacklib.utils import linux
    from zstacklib.utils import shell

    cmd = shell.ShellCmd(
        "blockdev --getsize64 %s" % linux.shellquote(path))
    cmd(is_exception=False)
    if cmd.return_code != 0:
        raise Exception(
            "LVM_RANGE_DEVICE_CAPACITY_MISSING: cannot read capacity for "
            "device[%s], error[%s]" % (path, cmd.stderr))
    try:
        capacity = long(cmd.stdout.strip())
    except (TypeError, ValueError):
        raise Exception(
            "LVM_RANGE_DEVICE_CAPACITY_MISSING: invalid capacity[%s] for "
            "device[%s]" % (cmd.stdout, path))
    if capacity <= 0:
        raise Exception(
            "LVM_RANGE_DEVICE_CAPACITY_MISSING: device[%s] has no positive "
            "capacity" % path)
    return capacity


def _list_block_device_slaves(canonical_path):
    device_name = os.path.basename(canonical_path)
    slave_path = "/sys/class/block/%s/slaves" % device_name
    try:
        return os.listdir(slave_path)
    except OSError as error:
        raise Exception(
            "LVM_RANGE_MULTIPATH_TOPOLOGY_INCOMPLETE: cannot enumerate "
            "slaves for device[%s]: %s" % (canonical_path, error))


def _get_lv_range_block_devices(pv_report):
    from zstacklib.utils import lvm

    pv_names = lvm_range.pv_names_for_device_resolution(pv_report)
    candidates = [(candidate, _candidate_paths(candidate))
                  for candidate in lvm.get_block_devices()]
    return lvm_range.resolve_pv_block_devices(
        pv_names, candidates, os.path.realpath, _list_block_device_slaves,
        _get_block_device_capacity)


def get_lv_range_descriptors(vg_uuid, targets):
    from zstacklib.utils import log

    if not targets:
        raise Exception("at least one LV range descriptor target is required")

    absolute_install_paths = []
    normalized_targets = []
    for target in targets:
        absolute_path = getattr(target, "absoluteInstallPath", None)
        if not absolute_path:
            raise Exception(
                "target[%s] does not contain an absolute LV install path" %
                getattr(target, "resourceUuid", None))
        absolute_install_paths.append(absolute_path)
        normalized_targets.append({
            "resourceUuid": getattr(target, "resourceUuid", None),
            "absoluteInstallPath": absolute_path
        })

    return lvm_range.collect_consistent_lv_range_descriptors(
        vg_uuid, absolute_install_paths, normalized_targets,
        _get_vg_range_report, _get_lv_range_report, _get_pv_range_report,
        _get_pv_duplicate_audit_report, _get_lv_range_block_devices,
        lvm_range.build_lv_range_descriptors,
        log.get_logger(__name__).warning)


def _value(item, name, default=None):
    if isinstance(item, dict):
        return item.get(name, default)
    return getattr(item, name, default)


def _validate_lvm_identifier(value, name):
    if (not value or value in (".", "..")
            or _LVM_IDENTIFIER_PATTERN.match(value) is None):
        raise ValueError("invalid SharedBlock %s[%s]" % (name, value))
    return value


def absolute_install_path(vg_uuid, install_path, identity):
    _validate_lvm_identifier(vg_uuid, "VG name")
    prefix = "sharedblock://%s/" % vg_uuid
    if not install_path or not install_path.startswith(prefix):
        raise ValueError(
            "snapshot[%s] install path[%s] does not belong to SharedBlock VG[%s]" %
            (identity, install_path, vg_uuid))
    lv_name = install_path[len(prefix):]
    try:
        _validate_lvm_identifier(lv_name, "LV name")
    except ValueError:
        raise ValueError(
            "snapshot[%s] has invalid SharedBlock LV install path[%s]" %
            (identity, install_path))
    return "/dev/%s/%s" % (vg_uuid, lv_name)


def _validate_chain_paths(vg_uuid, chain):
    _validate_lvm_identifier(vg_uuid, "VG name")
    if not chain:
        raise ValueError("qcow2 backing chain is empty")
    if any(not path for path in chain):
        raise ValueError("qcow2 backing chain contains an empty path")
    if len(set(chain)) != len(chain):
        raise ValueError(
            "qcow2 backing chain contains a cycle or duplicate path")
    prefix = "/dev/%s/" % vg_uuid
    for path in chain:
        if not path or not path.startswith(prefix):
            raise ValueError(
                "backing path[%s] does not belong to SharedBlock VG[%s]" %
                (path, vg_uuid))
        lv_name = path[len(prefix):]
        try:
            _validate_lvm_identifier(lv_name, "LV name")
        except ValueError:
            raise ValueError("invalid SharedBlock backing LV path[%s]" % path)


def install_path_from_absolute(vg_uuid, absolute_path):
    _validate_lvm_identifier(vg_uuid, "VG name")
    prefix = "/dev/%s/" % vg_uuid
    if not absolute_path.startswith(prefix):
        raise ValueError(
            "absolute LV path[%s] does not belong to SharedBlock VG[%s]" %
            (absolute_path, vg_uuid))
    lv_name = absolute_path[len(prefix):]
    _validate_lvm_identifier(lv_name, "LV name")
    return "sharedblock://%s/%s" % (vg_uuid, lv_name)


def build_source_plan(vg_uuid, target, chain):
    snapshot_uuid = _value(target, "volumeSnapshotUuid")
    if not snapshot_uuid or not snapshot_uuid.strip():
        raise ValueError("volumeSnapshotUuid must be non-empty")
    snapshot_path = absolute_install_path(
        vg_uuid, _value(target, "volumeSnapshotInstallPath"), snapshot_uuid)

    paths = list(chain or [])
    _validate_chain_paths(vg_uuid, paths)
    if paths[0] != snapshot_path:
        raise ValueError(
            "volume snapshot path[%s] is not the backing chain head[%s]" %
            (snapshot_path, paths[0]))

    range_targets = []
    for index, path in enumerate(paths):
        range_targets.append(LvRangeTarget(
            "%s:%s" % (snapshot_uuid, index), path))

    return {
        "vgUuid": vg_uuid,
        "paths": paths,
        "rangeTargets": range_targets
    }


def build_source_layout(target, plan, range_result, formats, lv_sizes,
                        virtual_size):
    expected_ids = [item.resourceUuid for item in plan["rangeTargets"]]
    ranges_by_id = {}
    for descriptor in range_result.get("descriptors", []):
        resource_uuid = descriptor.get("resourceUuid")
        if resource_uuid in ranges_by_id:
            raise ValueError("duplicate range descriptor[%s]" % resource_uuid)
        ranges_by_id[resource_uuid] = descriptor.get("ranges")
    if set(ranges_by_id.keys()) != set(expected_ids):
        raise ValueError(
            "mismatched range descriptors, expected[%s], actual[%s]" %
            (expected_ids, list(ranges_by_id.keys())))

    layers = []
    layer_count = len(plan["paths"])
    for index, path in enumerate(plan["paths"]):
        identity = expected_ids[index]
        layers.append({
            "layerIndex": index,
            "parentLayerIndex":
                index + 1 if index + 1 < layer_count else None,
            "sourceInstallPath":
                install_path_from_absolute(
                    plan["vgUuid"], path),
            "format": formats[path],
            "lvSizeBytes": lv_sizes[path],
            "ranges": ranges_by_id[identity]
        })

    return {
        "volumeSnapshotUuid": _value(target, "volumeSnapshotUuid"),
        "volumeUuid": _value(target, "volumeUuid"),
        "virtualSizeBytes": virtual_size,
        "layers": layers
    }


def merge_luns(lun_groups):
    result = []
    by_wwid = {}
    for luns in lun_groups:
        for lun in luns:
            wwid = _value(lun, "wwid")
            capacity = _value(lun, "capacityBytes")
            if not wwid or capacity is None:
                raise ValueError("invalid LUN descriptor")
            existing = by_wwid.get(wwid)
            if existing is not None:
                if _value(existing, "capacityBytes") != capacity:
                    raise ValueError(
                        "conflicting capacities for LUN[%s]" % wwid)
                continue
            by_wwid[wwid] = lun
            result.append(lun)
    return result
