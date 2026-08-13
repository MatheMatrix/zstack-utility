import os
import re


try:
    _long = long
except NameError:
    _long = int


_PE_RANGE_PATTERN = re.compile(r"^(.+):(\d+)(?:-(\d+))?$")

VG_RANGE_REPORT_FIELDS = (
    "vg_name", "vg_uuid", "vg_attr", "vg_extent_size", "vg_seqno",
    "pv_count", "vg_missing_pv_count")
PV_RANGE_REPORT_FIELDS = (
    "vg_uuid", "pv_uuid", "pv_name", "pv_size", "dev_size", "pe_start",
    "pv_pe_count", "pv_attr", "pv_missing", "pv_duplicate")


def _value(item, name, default=None):
    if isinstance(item, dict):
        return item.get(name, default)
    return getattr(item, name, default)


def _text(value):
    if value is None:
        return None
    return str(value).strip()


def _required_text(value, field):
    result = _text(value)
    if not result:
        raise ValueError("missing text field[%s]" % field)
    return result


def _report_rows(report, section):
    if not isinstance(report, dict):
        raise ValueError("invalid LVM report for section[%s]" % section)

    rows = []
    for part in report.get("report", []):
        rows.extend(part.get(section, []))
    return rows


def _number(value, field):
    if value is None:
        raise ValueError("missing numeric field[%s]" % field)
    try:
        return _long(str(value).strip())
    except (TypeError, ValueError):
        raise ValueError("invalid numeric field[%s:%s]" % (field, value))


def _error(code, message):
    raise ValueError("%s: %s" % (code, message))


def _flag_is_set(value):
    value = (_text(value) or "").lower()
    return value not in ("", "0", "false", "n", "no")


def _device_path(dev_name):
    dev_name = _required_text(dev_name, "block-device.dev_name")
    if dev_name.startswith("/dev/"):
        return dev_name
    return "/dev/%s" % dev_name


def _read_capacity(path, capacity_reader):
    try:
        capacity = _number(capacity_reader(path),
                           "block-device.path-capacity.size")
    except Exception as error:
        _error("LVM_RANGE_DEVICE_CAPACITY_MISSING",
               "cannot read capacity for path[%s]: %s" % (path, error))
    if capacity <= 0:
        _error("LVM_RANGE_DEVICE_CAPACITY_MISSING",
               "path[%s] has no positive capacity" % path)
    return capacity


def build_block_device_evidence(candidate, paths, realpath, list_slaves,
                                capacity_reader):
    try:
        wwid = _required_text(_value(candidate, "wwid"),
                              "block-device.wwid")
    except ValueError as error:
        _error("LVM_RANGE_WWID_MISSING", str(error))
    device_type = _text(_value(candidate, "type"))
    multipath_name = _text(_value(candidate, "multipathPath"))
    normalized_paths = set(_text(path) for path in paths if _text(path))

    if device_type == "mpath" or multipath_name:
        if not multipath_name:
            _error("LVM_RANGE_MULTIPATH_TOPOLOGY_INCOMPLETE",
                   "multipath device[%s] has no map name" % wwid)
        map_path = "/dev/mapper/%s" % multipath_name
        canonical_path = realpath(map_path)
        try:
            slaves = list(list_slaves(canonical_path) or [])
        except Exception as error:
            _error("LVM_RANGE_MULTIPATH_TOPOLOGY_INCOMPLETE",
                   "cannot enumerate slaves for map[%s]: %s" %
                   (map_path, error))
        slave_paths = sorted(set(_device_path(slave) for slave in slaves))
        if not slave_paths:
            _error("LVM_RANGE_MULTIPATH_TOPOLOGY_INCOMPLETE",
                   "multipath map[%s] has no slave devices" % map_path)

        capacity_paths = [map_path] + slave_paths
        path_capacities = [{"path": path,
                            "size": _read_capacity(path, capacity_reader)}
                           for path in capacity_paths]
        normalized_paths.update(capacity_paths)
        normalized_paths.add(canonical_path)
        topology = "mpath"
    elif device_type in ("disk", "lvm-pv"):
        disk_path = _device_path(_value(candidate, "dev_name"))
        canonical_path = realpath(disk_path)
        capacity_paths = [disk_path]
        path_capacities = [{
            "path": disk_path,
            "size": _read_capacity(disk_path, capacity_reader)
        }]
        normalized_paths.update([disk_path, canonical_path])
        topology = "disk"
    else:
        _error("LVM_RANGE_TOPOLOGY_UNSUPPORTED",
               "device[%s] has unsupported topology[%s]" %
               (wwid, device_type))

    return {
        "paths": sorted(normalized_paths),
        "canonicalPath": canonical_path,
        "wwid": wwid,
        "size": path_capacities[0]["size"],
        "topology": topology,
        "pathCapacities": path_capacities
    }


def resolve_pv_block_devices(pv_names, candidates, realpath, list_slaves,
                             capacity_reader):
    result = []
    for pv_name in pv_names:
        pv_name = _required_text(pv_name, "pv_name")
        real_pv_name = realpath(pv_name)
        matches = []
        for candidate, paths in candidates:
            normalized_paths = set(
                _text(path) for path in paths if _text(path))
            real_paths = set(realpath(path) for path in normalized_paths)
            if pv_name in normalized_paths or real_pv_name in real_paths:
                matches.append((candidate, list(normalized_paths)))
        if not matches:
            _error("LVM_RANGE_PV_DEVICE_UNRESOLVED",
                   "cannot resolve block device for PV[%s]" % pv_name)
        if len(matches) != 1:
            _error("LVM_RANGE_PV_DEVICE_AMBIGUOUS",
                   "PV[%s] resolves to[%s] block-device candidates" %
                   (pv_name, len(matches)))

        candidate, paths = matches[0]
        paths.extend([pv_name, real_pv_name])
        result.append(build_block_device_evidence(
            candidate, paths, realpath, list_slaves, capacity_reader))

    target_wwids = set(device["wwid"] for device in result)
    candidate_count_by_wwid = {}
    for candidate, unused_paths in candidates:
        wwid = _text(_value(candidate, "wwid"))
        if wwid in target_wwids:
            candidate_count_by_wwid[wwid] = (
                candidate_count_by_wwid.get(wwid, 0) + 1)
    for wwid, count in candidate_count_by_wwid.items():
        if count > 1:
            _error("LVM_RANGE_WWID_AMBIGUOUS",
                   "target WWID[%s] occurs on[%s] block-device candidates" %
                   (wwid, count))
    return result


def _parse_pe_range(value):
    ranges = [item.strip() for item in str(value).split(",") if item.strip()]
    if len(ranges) != 1:
        raise ValueError("linear segment must contain exactly one PV range[%s]" % value)

    matched = _PE_RANGE_PATTERN.match(ranges[0])
    if not matched:
        raise ValueError("invalid seg_pe_ranges[%s]" % value)

    start = _number(matched.group(2), "pv extent start")
    end = _number(matched.group(3) or matched.group(2), "pv extent end")
    if end < start:
        raise ValueError("invalid descending PV range[%s]" % value)
    return matched.group(1).strip(), start, end - start + 1


def _device_paths(device):
    paths = list(_value(device, "paths", []) or [])
    path = _value(device, "path")
    if path:
        paths.append(path)
    multipath_path = _value(device, "multipathPath")
    if multipath_path:
        paths.append("/dev/mapper/%s" % multipath_path)
    dev_name = _value(device, "dev_name")
    if dev_name:
        paths.append("/dev/%s" % dev_name)

    normalized = set()
    for path in paths:
        path = _text(path)
        if not path:
            continue
        normalized.add(path)
        normalized.add(os.path.realpath(path))
    return normalized


def _find_block_device(pv_name, block_devices):
    pv_paths = set([pv_name, os.path.realpath(pv_name)])
    matches = [device for device in block_devices if pv_paths.intersection(_device_paths(device))]
    if not matches:
        raise ValueError("cannot resolve block device for PV[%s]" % pv_name)
    if len(matches) != 1:
        raise ValueError("ambiguous block-device mapping for PV[%s]" % pv_name)
    return matches[0]


def _target_lv(target):
    path = _value(target, "absoluteInstallPath") or _value(target, "installPath")
    path = _required_text(path, "absoluteInstallPath")
    parts = path.split("/")
    if len(parts) != 4 or parts[0] != "" or parts[1] != "dev" or not parts[2] or not parts[3]:
        raise ValueError("invalid absolute LV install path[%s]" % path)
    return path, parts[2], parts[3]


def _pv_rows_by_name(pv_report):
    result = {}
    for row in _report_rows(pv_report, "pv"):
        name = _required_text(row.get("pv_name"), "pv_name")
        if name in result:
            raise ValueError("PV report contains duplicate pv_name[%s]" % name)
        result[name] = row
    return result


def pv_names_for_device_resolution(pv_report):
    names = []
    for row in _report_rows(pv_report, "pv"):
        if _flag_is_set(row.get("pv_missing")):
            continue
        names.append(_required_text(row.get("pv_name"), "pv_name"))
    return names


def _validate_vg(vg, pv_rows):
    try:
        vg_name = _required_text(vg.get("vg_name"), "vg_name")
        vg_uuid = _required_text(vg.get("vg_uuid"), "vg_uuid")
        vg_attr = _required_text(vg.get("vg_attr"), "vg_attr")
        missing_pv_count = _number(
            vg.get("vg_missing_pv_count"), "vg_missing_pv_count")
        expected_pv_count = _number(vg.get("pv_count"), "pv_count")
    except ValueError as error:
        _error("LVM_RANGE_VG_METADATA_INVALID", str(error))
    if len(vg_attr) < 4 or vg_attr[3] == "p":
        _error("LVM_RANGE_VG_PARTIAL",
               "VG[%s] is partial, attributes[%s]" % (vg_name, vg_attr))

    if missing_pv_count != 0:
        _error("LVM_RANGE_VG_PARTIAL",
               "VG[%s] has missing PV count[%s]" %
               (vg_name, missing_pv_count))

    if expected_pv_count <= 0 or expected_pv_count != len(pv_rows):
        _error("LVM_RANGE_PV_COUNT_MISMATCH",
               "VG[%s] expects[%s] PV rows but report contains[%s]" %
               (vg_name, expected_pv_count, len(pv_rows)))
    return vg_uuid


def _validate_pvs(pv_rows, expected_vg_uuid, extent_size):
    pvids = set()
    for pv_name, pv in pv_rows.items():
        if _required_text(pv.get("vg_uuid"), "pv.vg_uuid") != expected_vg_uuid:
            _error("LVM_RANGE_PV_VG_MISMATCH",
                   "PV[%s] belongs to unexpected VG UUID[%s]" %
                   (pv_name, pv.get("vg_uuid")))

        pvid = _text(pv.get("pv_uuid"))
        if not pvid:
            _error("LVM_RANGE_PVID_MISSING",
                   "PV[%s] has no PVID" % pv_name)
        if pvid in pvids:
            _error("LVM_RANGE_PVID_DUPLICATE",
                   "PVID[%s] occurs more than once in the target VG" % pvid)
        pvids.add(pvid)

        if _flag_is_set(pv.get("pv_missing")):
            _error("LVM_RANGE_PV_MISSING",
                   "PV[%s] is reported missing" % pv_name)
        if _flag_is_set(pv.get("pv_duplicate")):
            _error("LVM_RANGE_PV_DUPLICATE",
                   "PV[%s] is an unchosen duplicate" % pv_name)

        try:
            pe_start = _number(pv.get("pe_start"), "pe_start")
            pv_size = _number(pv.get("pv_size"), "pv_size")
            dev_size = _number(pv.get("dev_size"), "dev_size")
            pe_count = _number(pv.get("pv_pe_count"), "pv_pe_count")
        except ValueError as error:
            _error("LVM_RANGE_PV_METADATA_INVALID",
                   "PV[%s]: %s" % (pv_name, error))
        data_size = pe_count * extent_size
        if (pe_start < 0 or pv_size <= 0 or dev_size <= 0 or pe_count <= 0
                or data_size > pv_size or pv_size > dev_size
                or pe_start + data_size > dev_size):
            _error("LVM_RANGE_PV_BOUNDARY",
                   "PV[%s] has invalid data-area boundary: pe_start[%s], "
                   "pv_size[%s], dev_size[%s], pe_count[%s], extent_size[%s]" %
                   (pv_name, pe_start, pv_size, dev_size, pe_count,
                   extent_size))


def validate_lvm_metadata(vg_report, pv_report):
    vg_rows = _report_rows(vg_report, "vg")
    if len(vg_rows) != 1:
        _error("LVM_RANGE_VG_METADATA_INVALID",
               "expected exactly one VG report row, got[%s]" % len(vg_rows))
    vg = vg_rows[0]
    extent_size = _number(vg.get("vg_extent_size"), "vg_extent_size")
    if extent_size <= 0:
        _error("LVM_RANGE_VG_METADATA_INVALID",
               "VG extent size must be positive")
    try:
        pv_rows = _pv_rows_by_name(pv_report)
    except ValueError as error:
        _error("LVM_RANGE_PV_METADATA_INVALID", str(error))
    vg_uuid = _validate_vg(vg, pv_rows)
    _validate_pvs(pv_rows, vg_uuid, extent_size)
    return vg, pv_rows, vg_uuid, extent_size


def vg_seqno(vg_report):
    rows = _report_rows(vg_report, "vg")
    if len(rows) != 1:
        _error("LVM_RANGE_VG_METADATA_INVALID",
               "cannot get a unique VG sequence number")
    try:
        return _number(rows[0].get("vg_seqno"), "vg_seqno")
    except ValueError as error:
        _error("LVM_RANGE_VG_METADATA_INVALID", str(error))


def collect_consistent_lv_range_descriptors(
        vg_uuid, absolute_install_paths, targets, vg_collector, lv_collector,
        pv_collector, device_collector, builder, retry_observer=None):
    retry_observer = retry_observer or (lambda unused_message: None)
    for attempt in range(3):
        vg_report_before = vg_collector(vg_uuid)
        lv_report = lv_collector(absolute_install_paths)
        pv_report = pv_collector(vg_uuid)
        vg_report_metadata_after = vg_collector(vg_uuid)
        before_seqno = vg_seqno(vg_report_before)
        metadata_after_seqno = vg_seqno(vg_report_metadata_after)
        if before_seqno != metadata_after_seqno:
            retry_observer(
                "VG[%s] metadata changed from seqno[%s] to [%s] while "
                "collecting LVM reports, retry[%s/3]" %
                (vg_uuid, before_seqno, metadata_after_seqno, attempt + 1))
            continue

        validate_lvm_metadata(vg_report_metadata_after, pv_report)
        block_devices = device_collector(pv_report)
        vg_report_device_after = vg_collector(vg_uuid)
        device_after_seqno = vg_seqno(vg_report_device_after)
        if metadata_after_seqno != device_after_seqno:
            retry_observer(
                "VG[%s] metadata changed from seqno[%s] to [%s] while "
                "collecting block devices, retry[%s/3]" %
                (vg_uuid, metadata_after_seqno, device_after_seqno,
                 attempt + 1))
            continue

        return builder(vg_report_device_after, lv_report, pv_report,
                       block_devices, targets)

    _error("LVM_RANGE_METADATA_CHANGED",
           "VG[%s] metadata changed while collecting LV range descriptors" %
           vg_uuid)


def _validate_block_device(pv_name, pv, device):
    topology = _required_text(
        _value(device, "topology"), "block-device.topology")
    if topology not in ("disk", "mpath"):
        _error("LVM_RANGE_TOPOLOGY_UNSUPPORTED",
               "PV[%s] resolves to unsupported topology[%s]" %
               (pv_name, topology))

    try:
        wwid = _required_text(_value(device, "wwid"),
                              "block-device.wwid")
    except ValueError as error:
        _error("LVM_RANGE_WWID_MISSING",
               "PV[%s]: %s" % (pv_name, error))
    path_capacities = list(_value(device, "pathCapacities", []) or [])
    if not path_capacities:
        _error("LVM_RANGE_DEVICE_CAPACITY_MISSING",
               "no capacity evidence exists for PV[%s]" % pv_name)
    capacity_values = []
    for path_capacity in path_capacities:
        path = _required_text(_value(path_capacity, "path"),
                              "block-device.path-capacity.path")
        path_size = _number(_value(path_capacity, "size"),
                            "block-device.path-capacity.size")
        if path_size <= 0:
            _error("LVM_RANGE_DEVICE_CAPACITY_MISSING",
                   "path[%s] for PV[%s] has no positive capacity" %
                   (path, pv_name))
        capacity_values.append(path_size)
    if topology == "mpath" and (len(capacity_values) < 2
                                or len(set(capacity_values)) != 1):
        _error("LVM_RANGE_MULTIPATH_CAPACITY_MISMATCH",
               "multipath PV[%s] has inconsistent map/slave capacities[%s]" %
               (pv_name, capacity_values))

    capacity = _number(_value(device, "size"), "block device size")
    if capacity <= 0:
        _error("LVM_RANGE_DEVICE_CAPACITY_MISSING",
               "block device capacity must be positive for PV[%s]" % pv_name)
    pv_device_size = _number(pv.get("dev_size"), "pv.dev_size")
    if capacity != pv_device_size or capacity not in capacity_values:
        _error("LVM_RANGE_DEVICE_CAPACITY_MISMATCH",
               "LVM device size[%s] and canonical device capacity[%s] "
               "differ for PV[%s]" % (pv_device_size, capacity, pv_name))

    canonical_path = _required_text(_value(device, "canonicalPath"),
                                    "block-device.canonicalPath")
    return {
        "device": device,
        "wwid": wwid,
        "capacity": capacity,
        "identity": (_required_text(pv.get("pv_uuid"), "pv_uuid"),
                     canonical_path)
    }


def _validate_block_devices(pv_rows, block_devices):
    result = {}
    by_wwid = {}
    for pv_name, pv in pv_rows.items():
        device = _find_block_device(pv_name, block_devices)
        validated = _validate_block_device(pv_name, pv, device)
        existing = by_wwid.get(validated["wwid"])
        if existing is not None:
            if existing["capacity"] != validated["capacity"]:
                _error("LVM_RANGE_WWID_CAPACITY_MISMATCH",
                       "WWID[%s] has conflicting capacities[%s,%s]" %
                       (validated["wwid"], existing["capacity"],
                        validated["capacity"]))
            if existing["identity"] != validated["identity"]:
                _error("LVM_RANGE_WWID_AMBIGUOUS",
                       "WWID[%s] resolves to distinct PV/device identities" %
                       validated["wwid"])
        else:
            by_wwid[validated["wwid"]] = validated
        result[pv_name] = validated
    return result


def _lv_rows_by_name(lv_report):
    result = {}
    for row in _report_rows(lv_report, "seg"):
        name = _required_text(row.get("lv_name"), "lv_name")
        result.setdefault(name, []).append(row)
    return result


def _build_range(row, pv_rows, validated_devices, extent_size, lv_size,
                 expected_vg_uuid):
    lv_name = _required_text(row.get("lv_name"), "lv_name")
    segtype = _required_text(row.get("segtype"), "segtype")
    if segtype != "linear":
        _error("LVM_RANGE_SEGMENT_TYPE_UNSUPPORTED",
               "segment type[%s] for LV[%s] is unsupported" %
               (segtype, lv_name))
    if _required_text(row.get("vg_uuid"), "vg_uuid") != expected_vg_uuid:
        raise ValueError("LV[%s] belongs to unexpected VG UUID[%s]" %
                         (lv_name, row.get("vg_uuid")))

    pv_name, pv_extent_start, pv_extent_count = _parse_pe_range(row.get("seg_pe_ranges", ""))
    extent_count = _number(row.get("seg_size_pe"), "seg_size_pe")
    if extent_count <= 0:
        raise ValueError("segment extent count must be positive for LV[%s]" % lv_name)
    if pv_extent_count != extent_count:
        raise ValueError("segment extent count[%s] does not match PV range count[%s] for LV[%s]" %
                         (extent_count, pv_extent_count, lv_name))

    pv = pv_rows.get(pv_name)
    if pv is None:
        raise ValueError("cannot find PV metadata for device[%s]" % pv_name)
    if _required_text(pv.get("vg_uuid"), "pv.vg_uuid") != expected_vg_uuid:
        raise ValueError("PV[%s] belongs to unexpected VG UUID[%s]" % (pv_name, pv.get("vg_uuid")))
    validated_device = validated_devices[pv_name]
    wwid = validated_device["wwid"]

    seg_start_pe = _number(row.get("seg_start_pe"), "seg_start_pe")
    if seg_start_pe < 0:
        raise ValueError("negative segment start for LV[%s]" % lv_name)
    lv_offset = seg_start_pe * extent_size
    if lv_offset >= lv_size:
        raise ValueError("segment starts beyond LV size for LV[%s]" % lv_name)
    length = min(extent_count * extent_size, lv_size - lv_offset)

    pv_data_offset = _number(pv.get("pe_start"), "pe_start")
    if pv_data_offset < 0:
        raise ValueError("negative PV data offset for PV[%s]" % pv_name)
    lun_offset = pv_data_offset + pv_extent_start * extent_size
    if length <= 0 or lun_offset < 0:
        raise ValueError("invalid physical range for LV[%s]" % lv_name)

    capacity = validated_device["capacity"]
    pv_pe_count = _number(pv.get("pv_pe_count"), "pv_pe_count")
    if pv_extent_start + extent_count > pv_pe_count:
        _error("LVM_RANGE_PV_EXTENT_OVERFLOW",
               "segment range[%s:%s] exceeds PV[%s] extent count[%s]" %
               (pv_extent_start, pv_extent_start + extent_count - 1,
                pv_name, pv_pe_count))
    if lun_offset + length > capacity:
        raise ValueError("physical range exceeds block device capacity for PV[%s]" % pv_name)

    return ({
        "wwid": wwid,
        "lvOffsetBytes": lv_offset,
        "lunOffsetBytes": lun_offset,
        "lengthBytes": length
    }, {
        "wwid": wwid,
        "capacityBytes": capacity
    })


def _validate_complete_ranges(lv_name, lv_size, ranges):
    expected_offset = 0
    for item in ranges:
        if item["lvOffsetBytes"] != expected_offset:
            raise ValueError("LV[%s] ranges contain a gap or overlap at offset[%s]" %
                             (lv_name, expected_offset))
        expected_offset += item["lengthBytes"]
    if expected_offset != lv_size:
        raise ValueError("LV[%s] ranges cover[%s] bytes but LV size is[%s]" %
                         (lv_name, expected_offset, lv_size))

    ranges_by_wwid = {}
    for item in ranges:
        ranges_by_wwid.setdefault(item["wwid"], []).append(item)
    for wwid, physical_ranges in ranges_by_wwid.items():
        physical_ranges = sorted(
            physical_ranges, key=lambda value: value["lunOffsetBytes"])
        previous_end = -1
        for item in physical_ranges:
            if item["lunOffsetBytes"] < previous_end:
                _error(
                    "LVM_RANGE_PHYSICAL_OVERLAP",
                    "LV[%s] has overlapping physical ranges on LUN[%s]" %
                    (lv_name, wwid))
            previous_end = item["lunOffsetBytes"] + item["lengthBytes"]


def build_lv_range_descriptors(vg_report, lv_report, pv_report, block_devices, targets):
    vg, pv_rows, vg_uuid, extent_size = validate_lvm_metadata(
        vg_report, pv_report)
    lv_rows = _lv_rows_by_name(lv_report)
    vg_name = _required_text(vg.get("vg_name"), "vg_name")
    validated_devices = _validate_block_devices(pv_rows, block_devices)
    descriptors = []
    luns = []
    lun_by_wwid = {}
    seen_resource_uuids = set()

    for target in targets:
        resource_uuid = _required_text(_value(target, "resourceUuid"), "resourceUuid")
        if resource_uuid in seen_resource_uuids:
            raise ValueError("duplicate descriptor target resource UUID[%s]" % resource_uuid)
        seen_resource_uuids.add(resource_uuid)

        absolute_path, target_vg_name, lv_name = _target_lv(target)
        if target_vg_name != vg_name:
            raise ValueError("target LV[%s] belongs to VG[%s], expected[%s]" %
                             (absolute_path, target_vg_name, vg_name))

        rows = lv_rows.get(lv_name, [])
        if not rows:
            raise ValueError("cannot find LV metadata for target[%s]" % absolute_path)

        lv_uuid = _required_text(rows[0].get("lv_uuid"), "lv_uuid")
        lv_size = _number(rows[0].get("lv_size"), "lv_size")
        if lv_size <= 0:
            raise ValueError("LV size must be positive for target[%s]" % absolute_path)
        for row in rows:
            if (_required_text(row.get("lv_uuid"), "lv_uuid") != lv_uuid
                    or _number(row.get("lv_size"), "lv_size") != lv_size):
                raise ValueError("inconsistent LV segment metadata for target[%s]" % absolute_path)

        resolved = [_build_range(row, pv_rows, validated_devices,
                                 extent_size, lv_size, vg_uuid)
                    for row in rows]
        ranges = [item[0] for item in resolved]
        ranges.sort(key=lambda value: value["lvOffsetBytes"])
        _validate_complete_ranges(lv_name, lv_size, ranges)

        for unused_range, lun in resolved:
            existing = lun_by_wwid.get(lun["wwid"])
            if existing is not None:
                if existing["capacityBytes"] != lun["capacityBytes"]:
                    raise ValueError("conflicting capacities for LUN[%s]" % lun["wwid"])
                continue
            lun_by_wwid[lun["wwid"]] = lun
            luns.append(lun)

        descriptors.append({
            "resourceUuid": resource_uuid,
            "ranges": ranges
        })

    return {
        "luns": luns,
        "descriptors": descriptors
    }
