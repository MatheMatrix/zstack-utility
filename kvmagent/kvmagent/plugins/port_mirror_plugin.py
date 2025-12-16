'''

@author: zhanyong.miao
'''
import copy
from kvmagent import kvmagent
from zstacklib.utils import jsonobject
from zstacklib.utils import http
from zstacklib.utils import log
from zstacklib.utils import lock
from zstacklib.utils import shell
from zstacklib.utils import linux
from zstacklib.utils import iproute
from zstacklib.utils.bash import *
import os
import traceback
import netaddr

KVM_APPLY_MIRROR_SESSION_SOURCE = "/portmirror/apply/source"
KVM_RELEASE_MIRROR_SESSION_SOURCE = "/portmirror/release/source"
KVM_APPLY_MIRROR_SESSION_DEST = "/portmirror/apply/dest"
KVM_RELEASE_MIRROR_SESSION_DEST = "/portmirror/release/dest"

MIRROR_DEVICE_PREFIX = "ifb"

logger = log.get_logger(__name__)

class Tunnel:
    def __init__(self):
        self.dev = None
        self.uuid = None
        self.localIp = None
        self.remoteIp = None
        self.prefix = None
        self.gw = None
        self.key = None

class Mirror:
    def __init__(self):
        self.type = None
        self.snic = None
        self.dnic = None
        self.bridge = None
        self.mName = None
        self.dstEndPointType = "VmNic"  # "VmNic" or "UpLinkPort"
        self.sourceVlanId = 0  # source nic belong to this vlan
        self.interfaceName = None
        self.vlanId = 0

class ApplyMirrorSessionOnKVMCmd(kvmagent.AgentCommand):
    def __init__(self):
        super(ApplyMirrorSessionOnKVMCmd, self).__init__()
        self.tunnel = None
        self.mirror = None
        self.isLocal = None

class ApplyMirrorSessionOnKVMResponse(kvmagent.AgentResponse):
    def __init__(self):
        super(ApplyMirrorSessionOnKVMResponse, self).__init__()

class ReleaseMirrorSessionOnKVMCmd(kvmagent.AgentCommand):
    def __init__(self):
        super(ReleaseMirrorSessionOnKVMCmd, self).__init__()
        self.tunnel = None
        self.mirror = None
        self.isLocal = None

class ReleaseMirrorSessionOnKVMResponse(kvmagent.AgentResponse):
    def __init__(self):
        super(ReleaseMirrorSessionOnKVMResponse, self).__init__()

class PortMirrorPlugin(kvmagent.KvmAgent):
    '''
    classdocs
    '''

    def _create_gre_device(self, tunnel, rec_device_name):
        addr_list = iproute.query_addresses_by_ip(tunnel.localIp)
        if not addr_list:
            iproute.add_address(tunnel.localIp, tunnel.prefix, 4, tunnel.dev)
        device_exists = iproute.is_device_ifname_exists(rec_device_name)
        logger.debug("Is link device %s exists: %s" % (rec_device_name, device_exists))
        if not device_exists:
            iproute.add_link(rec_device_name, 'gretap', remote=tunnel.remoteIp, local=tunnel.localIp, ttl=255, key=tunnel.key)
            iproute.set_link_up(rec_device_name)
            iproute.set_link_attribute(rec_device_name, alias=tunnel.uuid)

    def _delete_gre_device(self, tunnel, rec_device_name):
        device_index = iproute.query_index_by_ifname(rec_device_name)
        if device_index:
            iproute.delete_link(device_index)

        splitStrings = tunnel.uuid.split("l3Uuid:")
        aliasTag = ""
        if len(splitStrings) == 2:
            aliasTag = splitStrings[1]
        else:
            aliasTag = "'send|recv'"
        shell_cmd = shell.ShellCmd("ip link show|egrep -i %s" % aliasTag)
        shell_cmd(False)
        if shell_cmd.return_code != 0:
            iproute.delete_address_no_error(tunnel.localIp, tunnel.prefix, 4, tunnel.dev)

    def _set_redirect_config(self, device_name, mirror_device_name, interface_name, source_vlan_id=0):
        self._set_mirror_src_config(device_name, mirror_device_name, "Egress", interface_name, source_vlan_id)
    def _clear_redirect_config(self, device_name, mirror_device_name):
        self._clear_mirror_src_config(device_name, mirror_device_name, "Egress")

    def _set_mirror_src_config(self, device_name, mirror_device_name, direction, interface_name, source_vlan_id=0):
        if not interface_name:
            raise ValueError("interface_name must be specified to set mirror source config")
        # 1. create ifb device for each physical nic
        transit_device_name = '%s-%s' % (MIRROR_DEVICE_PREFIX, interface_name)
        if not os.path.exists('/sys/class/net/%s' % transit_device_name):
            shell.call("ip link add %s type ifb && ip link set dev %s up" % (transit_device_name, transit_device_name))

        # 2. set default qdisc for ifb device
        ## tc qdisc show dev ifb-zsn0 | grep "htb 1: root"
        shell_cmd = shell.ShellCmd('tc qdisc show dev %s | grep "htb 1: root"' % transit_device_name)
        shell_cmd(False)
        if shell_cmd.return_code != 0:
            shell.call('tc qdisc add dev %s root handle 1: htb' % transit_device_name)
            shell.call('tc class add dev %s parent 1: classid 1:1 htb rate 10gbit' % transit_device_name)

        # 3. set priority and mark by source_vlan_id
        priority = 1
        if source_vlan_id != 0:
            priority = priority + source_vlan_id
        # tc filter show dev ifb-zsn0 prio 4096
        shell_cmd = shell.ShellCmd("tc filter show dev %s prio %s" % (transit_device_name, priority))
        shell_cmd(False)
        if shell_cmd.stdout.strip() == "":
            # tc filter add dev zs-mirror0 parent 1: protocol all prio 1001 handle 1001 fw action vlan push id 1001 action mirred egress mirror dev zsn0.1112
            if source_vlan_id == 0:
                shell.call("tc filter add dev %s parent 1: protocol all prio %s handle %s fw action mirred egress mirror dev %s"
                           % (transit_device_name, priority, priority, mirror_device_name))
            else:
                shell.call("tc filter add dev %s parent 1: protocol all prio %s handle %s fw action vlan push id %s action mirred egress mirror dev %s"
                           % (transit_device_name, priority, priority, source_vlan_id, mirror_device_name))

        if direction == "Egress" or direction == "Bidirection":
            shell_cmd = shell.ShellCmd("tc qdisc show dev %s |grep 'qdisc ingress'" % device_name)
            shell_cmd(False)
            if shell_cmd.return_code != 0:
                shell.call("tc qdisc add dev %s ingress" % device_name)
            shell_cmd = shell.ShellCmd(" tc filter list dev %s parent ffff: |grep '%s'" % (device_name, transit_device_name))
            shell_cmd(False)

            # tc filter add dev vnic35.1 parent ffff: protocol all prio 10 matchall action skbedit mark 1001 action mirred egress mirror dev zs-mirror0
            if shell_cmd.return_code != 0:
                shell.call('tc filter add dev %s parent ffff: protocol all prio 10 matchall action skbedit mark %s action mirred egress mirror dev %s'
                       % (device_name, priority, transit_device_name))
            else:
                shell.call('tc filter delete dev {device_name} parent ffff:; tc filter add dev {device_name} parent ffff: '
                           'protocol all prio 10 matchall action skbedit mark {priority} action mirred egress mirror dev {mirror_device}'
                           .format(device_name=device_name, priority=priority, mirror_device=transit_device_name))

        if direction == "Ingress" or direction == "Bidirection":
            shell_cmd = shell.ShellCmd("tc qdisc show dev %s |grep 'qdisc prio 1:'" % device_name)
            shell_cmd(False)
            if shell_cmd.return_code != 0:
                shell.call("tc qdisc add dev %s handle 1: root prio" % device_name)
            shell_cmd = shell.ShellCmd(" tc filter list dev %s parent 1: |grep '%s'" % (device_name, transit_device_name))
            shell_cmd(False)
            
            # tc filter add dev vnic35.1 parent 1: protocol all prio 10 matchall action skbedit mark 1001 action mirred egress mirror dev zs-mirror0
            if shell_cmd.return_code != 0:
                shell.call('tc filter add dev %s parent 1: protocol all prio 10 matchall action skbedit mark %s action mirred egress mirror dev %s'
                       % (device_name, priority, transit_device_name))
            else:
                shell.call('tc filter delete dev {device_name} parent 1:; tc filter add dev {device_name} parent 1: '
                           'protocol all prio 10 matchall action skbedit mark {priority} action mirred egress mirror dev {mirror_device}'
                           .format(device_name=device_name, priority=priority, mirror_device=transit_device_name))

    def _clear_mirror_src_config(self, device_name, mirror_device_name, direction):
        shell_cmd = shell.ShellCmd("tc qdisc show dev %s |grep 'qdisc ingress'" % device_name)
        shell_cmd(False)
        if shell_cmd.return_code == 0:
            shell.call("tc qdisc del dev %s ingress" % device_name)

        shell_cmd = shell.ShellCmd("tc qdisc show dev %s |grep 'qdisc prio 1:'" % device_name)
        shell_cmd(False)
        if shell_cmd.return_code == 0:
            shell.call("tc qdisc del dev %s root" % device_name)

    def _set_mirror_dst_config(self, bridge_name, device_name, mirror_device_name=None):
        if not iproute.is_device_ifname_exists('br_monitor'):
            iproute.add_link('br_monitor', 'bridge')
            iproute.set_link_up('br_monitor')
        if mirror_device_name and iproute.is_device_ifname_exists('br_monitor'):
            iproute.set_link_attribute(mirror_device_name, master='br_monitor')
        shell.call("brctl delif %s %s" % (bridge_name, device_name), False)

    def _clear_mirror_dst_config(self, bridge_name, device_name,mirror_device_name):
        iproute.set_link_attribute(device_name, master=bridge_name)
        '''
         ip link add br_monitor type bridge
        ip link set dev br_monitor up
        ip link set dev vnic25.0 master br_monitor
        ip link set dev rec_vnic25.0 master br_monitor
        '''
    def _apply_mirror_session_local(self, src_device_name, dst_device_name, direction, bridge_name, dstEndPointType, interface_name, source_vlan_id=0):
        self._set_mirror_src_config(src_device_name, dst_device_name, direction, interface_name, source_vlan_id)
        # 只有当镜像目标是虚拟机网卡时才需要桥接操作
        if dstEndPointType == "VmNic":
            self._set_mirror_dst_config(bridge_name, dst_device_name)

    def _release_mirror_session_local(self, src_device_name, dst_device_name, direction, bridge_name, dstEndPointType):
        self._clear_mirror_src_config(src_device_name, dst_device_name, direction)
        # 只有当镜像目标是虚拟机网卡时才需要桥接恢复操作
        if dstEndPointType == "VmNic":
            self._clear_mirror_dst_config(bridge_name, dst_device_name, dst_device_name)

    def _get_mirror_device_name(self, tunnel, mirror):
        return "send" + mirror.mName, "recv" + mirror.mName



    def _get_physical_target_device(self, mirror):
        """获取物理机目标设备名称"""
        if mirror.dstEndPointType == "UpLinkPort":
            # 镜像到物理机网卡
            if mirror.interfaceName:
                if mirror.vlanId == 0:
                    return mirror.interfaceName
                else:
                    return "{}.{}".format(mirror.interfaceName, mirror.vlanId)
            else:
                raise Exception("interfaceName must be specified when dstEndPointType is UpLinkPort")
        else:
            # 镜像到虚拟机网卡（原有逻辑）
            if mirror.dnic:
                return mirror.dnic
            else:
                raise Exception("dnic must be specified when dstEndPointType is VmNic")

    def _del_if(self, alias, mirror_name):
        alias_path = '/sys/class/net/%s/ifalias' % mirror_name
        if not os.path.exists(alias_path):
            return
        with open(alias_path, 'r') as fd:
            alias_str = fd.read()
        if alias not in alias_str:
            iproute.delete_link(mirror_name)

    @kvmagent.replyerror
    def apply_mirror_session(self, req):
        cmd = jsonobject.loads(req[http.REQUEST_BODY])
        rsp = ApplyMirrorSessionOnKVMResponse()

        '''
        check if the endpoints of session both are in this host
        if yes, just configure the mirror and skip the gre tunnel setup
       
        "tunnel":{"dev":"br_eth1","localIp":"192.168.100.185","remoteIp":"192.168.100.185",
                  "gw":"192.168.100.1","prefix":24,"id":1, ""uuid": srcHostUuid/dstHostUuid},
        "mirror":{"type":"Ingress","snic":"vnic47.0","dnic":"vnic47.1"},
        '''
        if cmd.isLocal:
            target_device = self._get_physical_target_device(cmd.mirror)
            self._apply_mirror_session_local(cmd.mirror.snic, target_device, cmd.mirror.type, cmd.mirror.bridge, cmd.mirror.dstEndPointType, cmd.mirror.interfaceName, cmd.mirror.sourceVlanId)
        else:
            src_name, dst_name = self._get_mirror_device_name(cmd.tunnel, cmd.mirror)
            self._del_if(cmd.tunnel.uuid, src_name)
            self._del_if(cmd.tunnel.uuid, dst_name)
            self._create_gre_device(cmd.tunnel, src_name)
            self._set_mirror_src_config(cmd.mirror.snic, src_name, cmd.mirror.type, cmd.mirror.interfaceName, cmd.mirror.sourceVlanId)
        logger.debug('successfully apply mirror device [%s] to device[%s]' % (cmd.mirror.snic, cmd.mirror.dnic))
        return jsonobject.dumps(rsp)

    @lock.lock('port_mirror')
    @kvmagent.replyerror
    def release_mirror_session(self, req):
        cmd = jsonobject.loads(req[http.REQUEST_BODY])
        rsp = ReleaseMirrorSessionOnKVMResponse()

        if cmd.isLocal:
            target_device = self._get_physical_target_device(cmd.mirror)
            self._release_mirror_session_local(cmd.mirror.snic, target_device, cmd.mirror.type, cmd.mirror.bridge, cmd.mirror.dstEndPointType)
        else:
            rec_name,_ = self._get_mirror_device_name(cmd.tunnel, cmd.mirror)
            self._clear_mirror_src_config(cmd.mirror.snic, rec_name, cmd.mirror.type)
            self._delete_gre_device(cmd.tunnel, rec_name)
            logger.debug('successfully release mirror device [%s] to device[%s]' % (cmd.mirror.snic, cmd.mirror.dnic))

        return jsonobject.dumps(rsp)

    @kvmagent.replyerror
    def apply_mirror_session_dest(self, req):
        cmd = jsonobject.loads(req[http.REQUEST_BODY])
        rsp = ApplyMirrorSessionOnKVMResponse()

        if cmd.mirror.dstEndPointType == "UpLinkPort":
            rsp.error = "not supported operation"
            return jsonobject.dumps(rsp)

        '''
        check if the endpoints of session both are in this host
        if yes, just configure the mirror and skip the gre tunnel setup
        '''

        if cmd.isLocal:
            rsp.error = 'unable to apply mirror device [%s] to device[%s] in same hypervisor' % (cmd.mirror.snic, cmd.mirror.dnic)
            rsp.success = False
        else:
            src_name, dst_name = self._get_mirror_device_name(cmd.tunnel, cmd.mirror)
            self._del_if(cmd.tunnel.uuid, src_name)
            self._del_if(cmd.tunnel.uuid, dst_name)
            self._create_gre_device(cmd.tunnel, dst_name)
            target_device = self._get_physical_target_device(cmd.mirror)
            self._set_mirror_dst_config(cmd.mirror.bridge, target_device, dst_name)
            self._set_redirect_config(dst_name, target_device, cmd.mirror.interfaceName, cmd.mirror.sourceVlanId)

        logger.debug('successfully apply mirror device [%s] to device[%s]' % (cmd.mirror.snic, cmd.mirror.dnic))

        return jsonobject.dumps(rsp)

    @lock.lock('port_mirror')
    @kvmagent.replyerror
    def release_mirror_session_dest(self, req):
        cmd = jsonobject.loads(req[http.REQUEST_BODY])
        rsp = ReleaseMirrorSessionOnKVMResponse()

        if cmd.mirror.dstEndPointType == "UpLinkPort":
            rsp.error = "not supported operation"
            return jsonobject.dumps(rsp)

        if cmd.isLocal:
            rsp.error = 'unable to release mirror device [%s] to device[%s] in same hypervisor' % (cmd.mirror.snic, cmd.mirror.dnic)
            rsp.success = False
        else:
            _,rec_name = self._get_mirror_device_name(cmd.tunnel, cmd.mirror)
            target_device = self._get_physical_target_device(cmd.mirror)
            self._clear_redirect_config(rec_name, target_device)
            self._clear_mirror_dst_config(cmd.mirror.bridge, target_device, rec_name)
            self._delete_gre_device(cmd.tunnel, rec_name)
            logger.debug('successfully release mirror device [%s] to device[%s]' % (cmd.mirror.snic, cmd.mirror.dnic))

        return jsonobject.dumps(rsp)

    def start(self):
        http_server = kvmagent.get_http_server()
        http_server.register_async_uri(KVM_APPLY_MIRROR_SESSION_SOURCE, self.apply_mirror_session)
        http_server.register_async_uri(KVM_RELEASE_MIRROR_SESSION_SOURCE, self.release_mirror_session)
        http_server.register_async_uri(KVM_APPLY_MIRROR_SESSION_DEST, self.apply_mirror_session_dest)
        http_server.register_async_uri(KVM_RELEASE_MIRROR_SESSION_DEST, self.release_mirror_session_dest)

    def stop(self):
        pass
