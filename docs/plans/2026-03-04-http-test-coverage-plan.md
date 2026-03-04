# HTTP Integration Test Coverage Improvement Plan

> **Owner**: ye.zou | **Created**: 2026-03-04 | **Target**: zstack-utility 5.5.12
> **Status**: ACTIVE — evolve loop in progress

## Goal

Bring HTTP integration test coverage from 14 endpoints → full agent coverage,
with async callback verification, on real kvmagent environments.

## Current State (Baseline)

- **Unit tests**: 155 passed, 9 skipped (fully mocked, 0.62s)
- **HTTP tests**: 14 passed (kvmagent only, reachability-only assertions)
- **Agents with 0 HTTP tests**: virtualrouter, appliancevm, cephbackup, cephprimary
- **Known bugs fixed**: taskUuid header (!6683), async empty body handling

## Phase 1: HTTP Smoke Coverage (Rounds 1-6)

**Goal**: Every agent endpoint has at least one reachability test.

### Round 1: Scan all kvmagent endpoints
- Grep all `@replyerror` / `@in_bash` decorated handlers in kvmagent/kvmagent/plugins/
- Build endpoint inventory (path, method, required params, sync vs async)
- Output: `tests/http/fixtures/endpoint_registry.py`

### Round 2: kvmagent smoke tests — host/vm/network plugins
- Add smoke tests for all remaining kvmagent host_plugin endpoints
- Add smoke tests for all remaining kvmagent vm_plugin endpoints
- Add smoke tests for all remaining kvmagent network_plugin endpoints
- Target: 30+ new test cases

### Round 3: kvmagent smoke tests — storage plugins
- localstorage_plugin (all endpoints)
- nfs_primarystorage_plugin (all endpoints)
- shareblock_plugin, smp_plugin
- Target: 20+ new test cases

### Round 4: kvmagent smoke tests — remaining plugins
- ha_plugin, prometheus_plugin, imagestore_plugin
- security_group_plugin, bmv2_gateway_agent
- Any remaining kvmagent plugins
- Target: 20+ new test cases

### Round 5: virtualrouter + appliancevm smoke tests
- Scan virtualrouter/virtualrouter/plugins/ for all endpoints
- Scan appliancevm/appliancevm/ for all endpoints
- Write smoke tests under tests/http/virtualrouter/ and tests/http/appliancevm/
- Target: 15+ new test cases

### Round 6: ceph agents smoke tests
- Scan cephbackupstorage/ for all endpoints
- Scan cephprimarystorage/ for all endpoints
- Write smoke tests under tests/http/ceph/
- Target: 15+ new test cases

### Phase 1 Exit Criteria
- [ ] All agents have HTTP smoke tests
- [ ] 100+ HTTP test cases total
- [ ] All pass on Jenkins CI nested VM environment
- [ ] Endpoint inventory document generated

## Phase 2: Async Callback Verification (Rounds 7-10)

**Goal**: Verify handler logic via callback responses, not just reachability.

### Round 7: Callback test infrastructure
- Create `tests/http/fixtures/callback_server.py` — lightweight HTTP server fixture
- Accepts callbacks from kvmagent, stores responses by taskUuid
- Fixture: `callback_server` (session-scoped), `wait_callback(taskUuid, timeout)`
- Update AgentClient.post() to optionally inject callbackUrl

### Round 8: kvmagent callback tests — read-only handlers
- /host/capacity → verify cpuNum, totalMemory are positive integers
- /host/fact → verify osDistribution, libvirtVersion are non-empty strings
- /host/ping → verify success=True
- /vm/checkstate with real VM UUIDs (query from libvirt)
- Target: 15+ callback-verified test cases

### Round 9: kvmagent callback tests — storage queries
- /localstorage/getphysicalcapacity → verify totalCapacity > 0
- /localstorage/checkbits → verify existing field accuracy
- /nfsprimarystorage/ping → verify NFS mount detection
- Target: 10+ callback-verified test cases

### Round 10: Other agent callback tests
- virtualrouter callback tests (dnsmasq, iptables queries)
- ceph callback tests (pool capacity, image listing)
- Target: 10+ callback-verified test cases

### Phase 2 Exit Criteria
- [ ] Callback server fixture works reliably
- [ ] 50+ callback-verified test cases
- [ ] Handler return values validated (not just status codes)
- [ ] CI integration tested

## Phase 3: Destructive Operations (Rounds 11-14)

**Goal**: Test state-changing handlers on disposable VMs.

### Round 11: Network destructive tests
- createBridge / deleteBridge
- configureNic (attach/detach)
- Security group rule apply/remove
- Guard: `--allow-destructive` flag, VM-only environment check

### Round 12: Storage destructive tests
- localstorage: create/delete volume, create/revert snapshot
- NFS: mount/umount operations
- Guard: test-specific temporary paths, cleanup fixtures

### Round 13: VM lifecycle tests
- attachVolume / detachVolume
- attachNic / detachNic
- VM state transitions (start/stop/pause/resume via libvirt)
- Guard: use test VM created by fixture, cleanup on teardown

### Round 14: Cross-plugin integration
- Create bridge → attach NIC → verify connectivity
- Create volume → attach to VM → verify block device
- Full cleanup verification

### Phase 3 Exit Criteria
- [ ] 40+ destructive test cases
- [ ] All guarded by --allow-destructive
- [ ] Cleanup fixtures verified (no leaked resources)
- [ ] CI runs on nested VM only

## Evolve Round Mapping

| Round | Phase | Focus | Est. New Tests |
|-------|-------|-------|---------------|
| 1 | P1 | Endpoint inventory scan | 0 (infra) |
| 2 | P1 | kvmagent host/vm/network smoke | 30+ |
| 3 | P1 | kvmagent storage smoke | 20+ |
| 4 | P1 | kvmagent remaining plugins smoke | 20+ |
| 5 | P1 | virtualrouter + appliancevm smoke | 15+ |
| 6 | P1 | ceph agents smoke | 15+ |
| 7 | P2 | Callback server infrastructure | 0 (infra) |
| 8 | P2 | kvmagent read-only callback tests | 15+ |
| 9 | P2 | kvmagent storage callback tests | 10+ |
| 10 | P2 | Other agent callback tests | 10+ |
| 11 | P3 | Network destructive tests | 10+ |
| 12 | P3 | Storage destructive tests | 10+ |
| 13 | P3 | VM lifecycle tests | 10+ |
| 14 | P3 | Cross-plugin integration | 10+ |

**Total target: 175+ new test cases across 14 rounds**

## Verification Strategy

Each round:
1. Run `pytest tests/unit/ -v` — must not regress (155+ passed)
2. Run `pytest tests/http/ -v --direct-host=<compute-ip>` — new tests pass
3. Commit with `zcommit test ZSTAC-67534 "round N: description"`
4. Push to branch, update MR

## Notes

- All HTTP tests require real agent environment (Jenkins nested VM or --direct-host)
- Unit tests run anywhere (fully mocked)
- Python 2/3 compat: test code is Py3 only, source code must stay Py2/3 compatible
- kvmagent async model: POST → 200 empty → callback with JSON result
