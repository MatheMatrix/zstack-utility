from __future__ import annotations

import libvirt

from zstacklib.virtualization.libvirt import get_connection

from .exceptions import VmNotFoundError, VmOperationError, VmXmlParseError
from .models import VmDisk, VmInfo, VmNic, VmState


def _parse_disks(xml: str) -> list[VmDisk]:
    try:
        import xml.etree.ElementTree as ET
        root = ET.fromstring(xml)
    except Exception as exc:
        raise VmXmlParseError(str(exc))

    disks: list[VmDisk] = []
    for disk in root.findall("./devices/disk"):
        device = disk.get("device", "")
        target = disk.find("target")
        source = disk.find("source")
        driver = disk.find("driver")
        readonly = disk.find("readonly") is not None
        boot = disk.find("boot")
        disks.append(
            VmDisk(
                device=device,
                source_path=(source.get("file") if source is not None else "")
                or (source.get("dev") if source is not None else "")
                or (source.get("name") if source is not None else "")
                or "",
                target_dev=target.get("dev") if target is not None else "",
                bus=target.get("bus") if target is not None else "virtio",
                driver_type=driver.get("type") if driver is not None else "qcow2",
                cache=driver.get("cache") if driver is not None else "none",
                readonly=readonly,
                boot_order=int(boot.get("order")) if boot is not None and boot.get("order") else None,
            )
        )
    return disks


def _parse_nics(xml: str) -> list[VmNic]:
    try:
        import xml.etree.ElementTree as ET
        root = ET.fromstring(xml)
    except Exception as exc:
        raise VmXmlParseError(str(exc))

    nics: list[VmNic] = []
    for iface in root.findall("./devices/interface"):
        mac = iface.find("mac")
        source = iface.find("source")
        model = iface.find("model")
        target = iface.find("target")
        vlan = iface.find("vlan")
        vlan_id = None
        if vlan is not None:
            tag = vlan.find("tag")
            if tag is not None and tag.get("id"):
                try:
                    vlan_id = int(tag.get("id"))
                except ValueError:
                    vlan_id = None
        nics.append(
            VmNic(
                mac_address=mac.get("address") if mac is not None else "",
                source_bridge=source.get("bridge") if source is not None else "",
                source_network=source.get("network") if source is not None else "",
                model=model.get("type") if model is not None else "virtio",
                target_dev=target.get("dev") if target is not None else "",
                vlan_id=vlan_id,
            )
        )
    return nics


def _domain_to_info(domain: libvirt.virDomain) -> VmInfo:
    try:
        state, _ = domain.state()
        info = domain.info()
        xml = domain.XMLDesc(0)
        autostart = bool(domain.autostart())
        persistent = bool(domain.isPersistent())
        pid = None
        try:
            pid = int(domain.ID()) if domain.ID() != -1 else None
        except libvirt.libvirtError:
            pid = None
        return VmInfo(
            uuid=domain.UUIDString(),
            name=domain.name(),
            state=VmState.from_libvirt(state),
            vcpus=info[3],
            memory_kb=info[2],
            max_memory_kb=info[1],
            cpu_time_ns=info[4],
            autostart=autostart,
            persistent=persistent,
            disks=_parse_disks(xml),
            nics=_parse_nics(xml),
            xml=xml,
            pid=pid,
        )
    except libvirt.libvirtError as exc:
        raise VmOperationError(domain.name(), "inspect", str(exc))


def _lookup_domain(conn: libvirt.virConnect, name_or_uuid: str) -> libvirt.virDomain:
    try:
        return conn.lookupByName(name_or_uuid)
    except libvirt.libvirtError:
        try:
            return conn.lookupByUUIDString(name_or_uuid)
        except libvirt.libvirtError:
            raise VmNotFoundError(name_or_uuid)


def get_vm_info(name_or_uuid: str) -> VmInfo:
    conn = get_connection()
    domain = _lookup_domain(conn, name_or_uuid)
    return _domain_to_info(domain)


def list_vms() -> list[VmInfo]:
    conn = get_connection()
    domains: list[libvirt.virDomain] = []
    try:
        domains.extend(conn.listAllDomains())
    except libvirt.libvirtError:
        for dom_id in conn.listDomainsID():
            domains.append(conn.lookupByID(dom_id))
        for name in conn.listDefinedDomains():
            domains.append(conn.lookupByName(name))
    return [_domain_to_info(domain) for domain in domains]


def start_vm(name_or_uuid: str) -> None:
    conn = get_connection()
    domain = _lookup_domain(conn, name_or_uuid)
    try:
        domain.create()
    except libvirt.libvirtError as exc:
        raise VmOperationError(name_or_uuid, "start", str(exc))


def stop_vm(name_or_uuid: str, force: bool = False) -> None:
    conn = get_connection()
    domain = _lookup_domain(conn, name_or_uuid)
    try:
        if force:
            domain.destroy()
        else:
            domain.shutdown()
    except libvirt.libvirtError as exc:
        raise VmOperationError(name_or_uuid, "stop", str(exc))


def reboot_vm(name_or_uuid: str) -> None:
    conn = get_connection()
    domain = _lookup_domain(conn, name_or_uuid)
    try:
        domain.reboot(0)
    except libvirt.libvirtError as exc:
        raise VmOperationError(name_or_uuid, "reboot", str(exc))


def destroy_vm(name_or_uuid: str) -> None:
    conn = get_connection()
    domain = _lookup_domain(conn, name_or_uuid)
    try:
        domain.destroy()
    except libvirt.libvirtError as exc:
        raise VmOperationError(name_or_uuid, "destroy", str(exc))


def define_vm(xml: str) -> VmInfo:
    conn = get_connection()
    try:
        domain = conn.defineXML(xml)
    except libvirt.libvirtError as exc:
        raise VmOperationError("unknown", "define", str(exc))
    return _domain_to_info(domain)


def undefine_vm(name_or_uuid: str) -> None:
    conn = get_connection()
    domain = _lookup_domain(conn, name_or_uuid)
    try:
        domain.undefine()
    except libvirt.libvirtError as exc:
        raise VmOperationError(name_or_uuid, "undefine", str(exc))
