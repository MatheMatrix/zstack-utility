import shell

def _call_with_timeout(cmd, timeout=10):
    return shell.call("timeout %s %s" % (timeout, cmd))

def list(all=False, timeout=10):
    cmd = "virsh list"
    if all:
        cmd += " --all"

    return _call_with_timeout(cmd, timeout)

def vm_in_used_bridge_names(vm_uuid, timeout=10):
    cmd = "virsh domiflist %s | grep bridge | awk '{print $3}'" % vm_uuid
    return _call_with_timeout(cmd, timeout)

def find_vm_xml_source_contains(vm_uuid, key_in_vm_disk_source, timeout=10):
    cmd = "virsh dumpxml %s | grep '<source' | head -1 | grep %s" % (vm_uuid, key_in_vm_disk_source)
    return _call_with_timeout(cmd, timeout)
    