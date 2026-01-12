# ZStack Utility Codebase Guide

## Architecture Overview
ZStack is an open-source IaaS platform. This repository contains Python-based agents that run on hosts to manage virtualization, storage, networking, and monitoring. Agents communicate with the management node via HTTP APIs using JSON serialization.

Key components:
- **kvmagent**: Manages KVM VMs, collects Prometheus metrics, handles storage/backup operations
- **virtualrouter**: Network routing and firewall management
- **Storage agents**: cephbackupstorage, sftpbackupstorage, etc. for different storage backends
- **Console proxy**: VM console access
- **Bare metal agents**: PXE server, instance agent for bare metal provisioning

## Communication Patterns
- Agents inherit from `plugin.Plugin` or `kvmagent.KvmAgent`
- Commands received via HTTP POST, responses via `http.json_dump_post`
- Use `zstacklib.utils.jsonobject` for structured data
- Alarms sent to management node with unique IDs to avoid duplicates

## Key Patterns
- **Logging**: `logger = log.get_logger(__name__)` from `zstacklib.utils.log`
- **Bash execution**: `bash_ro()`, `bash_o()` for shell commands with error handling
- **Async operations**: `@thread.AsyncThread` decorator
- **GPU management**: Track devices in sets like `gpu_devices['NVIDIA']`
- **Metrics collection**: Use Prometheus client for gauges, handle collection throttling

## Development Workflows
- **Build packages**: `python setup.py sdist` in each component directory
- **Run tests**: `tox -e py36` (supports py27, py35, py36, py37)
- **Install agents**: Ansible playbooks in `ansible/` subdirs handle deployment
- **Debugging**: Check `/var/log/zstack/` for logs, use `dump_stack_and_objects` for deep inspection

## Examples
- Metric collection: Define `GaugeMetricFamily` in collect functions, return list of metrics
- Alarm sending: `send_alarm_to_mn('cpu', cpu_id, cpuName=cpu_id, status=status)`
- Plugin registration: Classes inherit from `KvmAgent`, methods exposed via HTTP

Focus on host-level operations, error resilience, and integration with management node APIs.