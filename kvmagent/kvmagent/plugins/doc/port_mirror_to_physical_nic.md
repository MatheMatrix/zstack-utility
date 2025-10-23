# 端口镜像到物理网卡（KVM Agent Port Mirror）

本文档描述 kvmagent 的端口镜像实现，用于将源端口的流量镜像到目标物理网卡，支持同宿主机与跨宿主机（通过 GRE-TAP）两种模式。基于源码 `kvmagent/kvmagent/plugins/port_mirror_plugin.py`。

## 概览

- 同宿主机镜像：直接在源设备上通过 `tc` 配置镜像到目标设备，并调整目标设备的桥接关系。
- 跨宿主机镜像：在源宿主机创建 GRE-TAP 设备镜像输出，在目标宿主机创建对应 GRE-TAP 设备接收并重定向到目标物理网卡。
- 方向支持：`Egress`、`Ingress`、`Bidirection`（双向）。
- 设备命名：
  - 源端 GRE 设备：`send<mName>`
  - 目的端 GRE 设备：`recv<mName>`

## HTTP 接口

KVM Agent 注册了以下异步 URI：

- `POST /portmirror/apply/source`：源端应用镜像（同宿主机或跨宿主机的源端）
- `POST /portmirror/release/source`：源端释放镜像
- `POST /portmirror/apply/dest`：目的端应用镜像（仅跨宿主机目的端）
- `POST /portmirror/release/dest`：目的端释放镜像

所有接口的请求体均为 JSON，响应为：
```json
{"success": true, "error": null}
```
如失败：`{"success": false, "error": "message"}`

## 数据模型

请求体字段（统一结构）：
```json
{
  "tunnel": {
    "dev": "br_eth1",
    "localIp": "192.168.100.185",
    "remoteIp": "192.168.100.186",
    "gw": "192.168.100.1",
    "prefix": 24,
    "key": 12345,
    "uuid": "l3Uuid:xxxx-yyyy"
  },
  "mirror": {
    "type": "Egress|Ingress|Bidirection",
    "snic": "源设备名，如 vnic47.0",
    "dnic": "目的设备名，如 eth1",
    "bridge": "目的设备所在桥，如 br_eth1",
    "mName": "会话名称，用于拼接 send/recv 设备"
  },
  "isLocal": true | false
}
```

说明：
- `isLocal=true`：同宿主机镜像，两端都在同一 KVM 主机。
- `isLocal=false`：跨宿主机镜像，需要在源与目的主机分别调用 source/dest 接口。
- `tunnel.key` 可选，用于 GRE-TAP 的 key。
- `tunnel.uuid` 会写入 GRE 设备的 ifalias，用于清理判断。

## 工作流程

### 同宿主机（isLocal=true）
- Apply（源端调用 `/portmirror/apply/source`）：
  1. 在 `mirror.snic` 上配置 `tc qdisc` 与 `tc filter`，将流量镜像到 `mirror.dnic`（按 `type` 决定方向）。
  2. 将 `mirror.dnic` 从其原桥 `mirror.bridge` 中移除，同时创建/加入监控桥 `br_monitor`：
     - 若 `br_monitor` 不存在则创建并 `up`
     - 目标设备（如 `mirror.dnic`）脱离原桥，镜像接收设备加入 `br_monitor`（同宿主机场景不创建 GRE 设备）
- Release（源端调用 `/portmirror/release/source`）：
  1. 移除源端 `tc` 配置（删除 ingress/root prio qdisc）。
  2. 将 `mirror.dnic` 重新加入其原桥 `mirror.bridge`。

### 跨宿主机（isLocal=false）
- Apply Source（源端调用 `/portmirror/apply/source`）：
  1. 计算 GRE 设备名：`send<mName>`。
  2. 若存在与本次 `tunnel.uuid` 不匹配的同名设备，删除之（基于 ifalias）。
  3. 创建并 `up` GRE-TAP 设备（`gretap`），设置 ifalias 为 `tunnel.uuid`。
  4. 在源设备 `mirror.snic` 上配置 `tc`，镜像流量到 `send<mName>`（按 `type`）。
- Apply Dest（目的端调用 `/portmirror/apply/dest`）：
  1. 计算 GRE 设备名：`recv<mName>`。
  2. 清理不匹配的同名设备后，创建并 `up` `recv<mName>`。
  3. 将 `recv<mName>` 加入监控桥 `br_monitor`；同时把 `mirror.dnic` 从 `mirror.bridge` 中移除。
  4. 在 `recv<mName>` 上配置 `tc`，将其接收的数据重定向（mirred）到物理网卡 `mirror.dnic`（`Egress`）。
- Release Source（源端调用 `/portmirror/release/source`）：
  1. 清除源设备 `mirror.snic` 上的 `tc` 镜像配置（针对 `send<mName>`）。
  2. 删除源端 GRE 设备 `send<mName>`；若不再存在该会话相关的设备别名，删除本地隧道 IP。
- Release Dest（目的端调用 `/portmirror/release/dest`）：
  1. 清除 `recv<mName>` 上对 `mirror.dnic` 的重定向配置。
  2. 将 `mirror.dnic` 重新加入 `mirror.bridge`。
  3. 删除目的端 GRE 设备 `recv<mName>`。

## 关键实现要点

- `tc` 配置：
  - Ingress（入方向）：
    - `tc qdisc add dev <dev> ingress`
    - `tc filter add dev <dev> parent ffff: ... action mirred egress mirror dev <mirror_dev>`
  - Egress（出方向）：
    - `tc qdisc add dev <dev> handle 1: root prio`
    - `tc filter add dev <dev> parent 1: ... action mirred egress mirror dev <mirror_dev>`
  - 若已存在则 `replace`。
  - 清理时删除 ingress 与 root prio qdisc。
- GRE-TAP（`gretap`）：
  - `ip link add <send|recv> type gretap local <localIp> remote <remoteIp> ttl 255 key <key>`
  - `ip link set <send|recv> up`
  - `ip link set <send|recv> alias <tunnel.uuid>`
- 监控桥：
  - 创建 `br_monitor`（若不存在）：`ip link add br_monitor type bridge && ip link set br_monitor up`
  - 将接收端设备（目的或 `recv<mName>`）加入 `br_monitor`。
  - 将物理网卡 `mirror.dnic` 从原桥 `mirror.bridge` 中移除/恢复：`brctl delif <bridge> <dnic>` / `ip link set <dnic> master <bridge>`

## 幂等与清理

- 在创建 `send|recv` 设备前会检查 ifalias（`/sys/class/net/<dev>/ifalias`），若别名不包含本次会话 `tunnel.uuid`，删除同名设备以避免残留。
- 释放时若宿主机上不再存在本次会话的设备别名（通过 `ip link show | egrep -i '<l3Uuid or send|recv>'` 检查），将删除本地主隧道地址（`localIp/prefix`）。

## 锁与并发

- 释放接口加锁：`@lock.lock('port_mirror')`，避免并发清理冲突。
- 源/目的应用接口使用 `@kvmagent.replyerror` 处理异常并返回错误消息。

## 错误与限制

- 当 `isLocal=true` 调用目的端接口（`/portmirror/apply/dest` 或 `/portmirror/release/dest`）会返回错误：同宿主机场景不需要目的端独立调用。
- 依赖组件/能力：
  - Linux `tc`、`iproute2`、`bridge-utils (brctl)`、GRE-TAP（内核支持）
  - 需要有足够权限执行网络与流量控制命令
- 注意在生产环境中评估将物理网卡移出其原桥对业务的影响。

## 示例

同宿主机应用镜像（源端）：
```bash
curl -s -X POST http://<kvm-agent>:<port>/portmirror/apply/source -d '{
  "tunnel": {
    "dev": "br_eth1",
    "localIp": "192.168.100.185",
    "remoteIp": "192.168.100.185",
    "gw": "192.168.100.1",
    "prefix": 24,
    "key": 1,
    "uuid": "l3Uuid:local-session-001"
  },
  "mirror": {
    "type": "Egress",
    "snic": "vnic47.0",
    "dnic": "eth1",
    "bridge": "br_eth1",
    "mName": "pm-001"
  },
  "isLocal": true
}'
```

跨宿主机应用镜像（源端与目的端各调用一次）：

源端：
```bash
curl -s -X POST http://<src-kvm-agent>:<port>/portmirror/apply/source -d '{
  "tunnel": {
    "dev": "br_eth1",
    "localIp": "10.0.0.11",
    "remoteIp": "10.0.0.12",
    "gw": "10.0.0.1",
    "prefix": 24,
    "key": 100,
    "uuid": "l3Uuid:pm-cross-100"
  },
  "mirror": {
    "type": "Bidirection",
    "snic": "vnic25.0",
    "dnic": "eth1",
    "bridge": "br_eth1",
    "mName": "pm-100"
  },
  "isLocal": false
}'
```

目的端：
```bash
curl -s -X POST http://<dest-kvm-agent>:<port>/portmirror/apply/dest -d '{
  "tunnel": {
    "dev": "br_eth1",
    "localIp": "10.0.0.12",
    "remoteIp": "10.0.0.11",
    "gw": "10.0.0.1",
    "prefix": 24,
    "key": 100,
    "uuid": "l3Uuid:pm-cross-100"
  },
  "mirror": {
    "type": "Egress",
    "snic": "vnic25.0",
    "dnic": "eth1",
    "bridge": "br_eth1",
    "mName": "pm-100"
  },
  "isLocal": false
}'
```

释放流程类似，对应调用 `/portmirror/release/source` 与 `/portmirror/release/dest`。

## 故障排查

- 查看 `tc` 配置：
  - `tc qdisc show dev <dev>`
  - `tc filter list dev <dev> parent ffff:`（ingress）
  - `tc filter list dev <dev> parent 1:`（root prio）
- 查看 GRE 设备与别名：
  - `ip -d link show <send|recv><mName>`
  - `cat /sys/class/net/<send|recv><mName>/ifalias`
- 桥接关系：
  - `bridge link`
  - `brctl show`
- 日志：
  - KVM Agent 日志中有应用/释放成功与调试信息（`PortMirrorPlugin`）。


## 镜像到物理机接口
前述功能可以把流量镜像到虚拟机vnic, 本次改进将流量镜像到物理机网卡，或者物理机网卡的vlan子接口

### 如何判断镜像目的
参数mirror新增3个参数: 
- `dstEndPointType`: 取值 "VmNic", "UpLinkPort", VmNic表示旧逻辑不变，"UpLinkPort" 新逻辑
- `interfaceName`: 物理机网卡的命令
  - 在dstEndPointType为 'UpLinkPort' 有意义
- `vlanId `: vlan子接口的vlan id, 0 表示不使用vlan子接口
  -在dstEndPointType为 'UpLinkPort' 有意义

### 实现流程
#### 同宿主机（isLocal=true）
- Apply（源端调用 `/portmirror/apply/source`）：
  1. 在 `mirror.snic` 上配置 `tc qdisc` 与 `tc filter`，将流量镜像到 上行口`interfaceName.vlanId`

- Release（源端调用 `/portmirror/release/source`）：
  1. 移除源端 `tc` 配置（删除 ingress/root prio qdisc）
