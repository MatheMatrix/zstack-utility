# -*- coding: utf-8 -*-

import pytest

from kvmagent.plugins import vm_plugin


class Volume(object):
    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)

    def __getattr__(self, name):
        return None

    def hasattr(self, name):
        return name in self.__dict__


def cbd_volume(**kwargs):
    values = {
        'deviceType': 'cbd',
        'useVirtio': True,
        'useVirtioSCSI': False,
        'multiQueues': '16',
        'ioThreads': 8,
        'volumeUuid': 'volume-uuid',
        'deviceId': 1,
    }
    values.update(kwargs)
    return Volume(**values)


class EmptyAddons(object):
    def __init__(self):
        self.attachedDataVolumes = []

    def __bool__(self):
        return False

    __nonzero__ = __bool__


def no_retry(*args, **kwargs):
    def decorator(func):
        return func
    return decorator


@pytest.mark.kvmagent
def test_is_virtio_blk_excludes_virtio_scsi():
    assert vm_plugin.is_virtio_blk(cbd_volume(useVirtio=True, useVirtioSCSI=False))
    assert not vm_plugin.is_virtio_blk(cbd_volume(useVirtio=True, useVirtioSCSI=True))
    assert not vm_plugin.is_virtio_blk(cbd_volume(useVirtio=False, useVirtioSCSI=False))


@pytest.mark.kvmagent
def test_iothread_vq_mapping_allocator_distributes_queues_to_larger_iothread_ids_first():
    volume = cbd_volume(ioThreads=7)

    allocator = vm_plugin.IothreadVqMappingAllocator.allocate(volume, set())

    assert allocator.iothread_ids == [101, 102, 103, 104, 105, 106, 107]
    assert allocator.queue_ids_by_iothread[101] == [0, 1]
    assert allocator.queue_ids_by_iothread[102] == [2, 3]
    assert allocator.queue_ids_by_iothread[103] == [4, 5]
    assert allocator.queue_ids_by_iothread[104] == [6, 7]
    assert allocator.queue_ids_by_iothread[105] == [8, 9]
    assert allocator.queue_ids_by_iothread[106] == [10, 11, 12]
    assert allocator.queue_ids_by_iothread[107] == [13, 14, 15]


@pytest.mark.kvmagent
def test_iothread_vq_mapping_allocator_uses_one_iothread_per_queue_when_count_matches_queue_count():
    volume = cbd_volume(multiQueues='8', ioThreads=8)

    allocator = vm_plugin.IothreadVqMappingAllocator.allocate(volume, set())

    assert allocator.iothread_ids == [101, 102, 103, 104, 105, 106, 107, 108]
    assert allocator.queue_ids_by_iothread[101] == [0]
    assert allocator.queue_ids_by_iothread[108] == [7]


@pytest.mark.kvmagent
def test_iothread_vq_mapping_allocator_avoids_existing_iothread_ids():
    volume = cbd_volume(multiQueues='4', ioThreads=4)

    allocator = vm_plugin.IothreadVqMappingAllocator.allocate(volume, set([101, 103]))

    assert allocator.iothread_ids == [102, 104, 105, 106]


@pytest.mark.kvmagent
def test_iothread_vq_mapping_allocator_reports_id_exhaustion():
    used_ids = set(range(vm_plugin.AUTOMATIC_IOTHREAD_ID_START, vm_plugin.AUTOMATIC_IOTHREAD_ID_LIMIT + 1))

    with pytest.raises(Exception) as exc:
        vm_plugin.IothreadVqMappingAllocator.allocate_iothread_ids(1, used_ids)

    assert 'no id available' in str(exc.value)


@pytest.mark.kvmagent
def test_prepare_scsi_controller_indexes_reuses_manual_iothread_controller():
    volume1 = cbd_volume(useVirtio=False, useVirtioSCSI=True, ioThreadId=101, deviceId=1)
    volume2 = cbd_volume(volumeUuid='volume-uuid-2', useVirtio=False, useVirtioSCSI=True, ioThreadId=101, deviceId=2)

    vm_plugin.IothreadVqMappingAllocator.prepare_scsi_controller_indexes([volume1, volume2])

    assert volume1.controllerIndex == 1
    assert volume2.controllerIndex == 1


@pytest.mark.kvmagent
def test_manual_iothread_pin_disables_automatic_iothread_vq_mapping():
    volume = cbd_volume(ioThreadId=3)

    assert vm_plugin.IothreadVqMappingAllocator.allocate(volume, set()) is None


@pytest.mark.kvmagent
def test_missing_iothreads_disables_automatic_iothread_vq_mapping():
    volume = cbd_volume()
    delattr(volume, 'ioThreads')

    assert vm_plugin.IothreadVqMappingAllocator.allocate(volume, set()) is None


@pytest.mark.kvmagent
def test_non_cbd_volume_can_use_dedicated_scsi_controller_without_automatic_mapping():
    volume = cbd_volume(deviceType='ceph', useVirtio=False, useVirtioSCSI=True, multiQueues='4')

    assert vm_plugin.IothreadVqMappingAllocator.needs_automatic_mapping(volume) is False
    assert vm_plugin.IothreadVqMappingAllocator.needs_dedicated_scsi_controller(volume) is True


@pytest.mark.kvmagent
def test_iothread_vq_mapping_allocator_writes_individual_queues():
    volume = cbd_volume(ioThreads=7)
    allocator = vm_plugin.IothreadVqMappingAllocator.allocate(volume, set())
    driver = vm_plugin.etree.Element('driver')

    vm_plugin.IothreadVqMappingAllocator.apply(driver, allocator)

    iothreads = driver.findall('./iothreads/iothread')
    assert iothreads[-2].get('id') == '106'
    assert [q.get('id') for q in iothreads[-2].findall('queue')] == ['10', '11', '12']
    assert iothreads[-1].get('id') == '107'
    assert [q.get('id') for q in iothreads[-1].findall('queue')] == ['13', '14', '15']


@pytest.mark.kvmagent
def test_get_new_cbd_disk_keeps_existing_iothread_vq_mapping_for_migration():
    old_disk = vm_plugin.etree.fromstring('''
    <disk type="network" device="disk">
      <driver name="qemu" type="raw" cache="none" discard="unmap" queues="4">
        <iothreads>
          <iothread id="101"><queue id="0-1"/></iothread>
          <iothread id="102"><queue id="2-3"/></iothread>
        </iothreads>
      </driver>
      <source protocol="cbd" name="old"/>
      <target dev="vdb" bus="virtio"/>
    </disk>
    ''')
    volume = cbd_volume(
        installPath='cbd:new-volume',
        dev_letter='b',
        multiQueues=None,
        ioThreads=None,
        physicalBlockSize=None,
    )

    new_disk = vm_plugin.VmPlugin._get_new_disk(old_disk, volume)

    driver = new_disk.find('driver')
    assert driver.get('queues') == '4'
    iothreads = driver.findall('./iothreads/iothread')
    assert [i.get('id') for i in iothreads] == ['101', '102']
    assert [q.get('id') for q in iothreads[0].findall('queue')] == ['0', '1']
    assert [q.get('id') for q in iothreads[1].findall('queue')] == ['2', '3']


@pytest.mark.kvmagent
def test_get_new_cbd_scsi_disk_does_not_write_queues_on_disk_driver():
    old_disk = vm_plugin.etree.fromstring('''
    <disk type="network" device="disk">
      <driver name="qemu" type="raw" cache="none" discard="unmap"/>
      <source protocol="cbd" name="old"/>
      <target dev="sdb" bus="scsi"/>
    </disk>
    ''')
    volume = cbd_volume(
        installPath='cbd:new-volume',
        dev_letter='b',
        useVirtio=True,
        useVirtioSCSI=True,
        multiQueues='4',
        physicalBlockSize=None,
        wwn='123456789abcdef0',
    )

    new_disk = vm_plugin.VmPlugin._get_new_disk(old_disk, volume)

    driver = new_disk.find('driver')
    assert driver.get('queues') is None
    assert driver.find('iothreads') is None
    assert new_disk.find('target').get('bus') == 'scsi'


@pytest.mark.kvmagent
def test_add_scsi_controller_records_alias_before_attach(monkeypatch):
    class FakeDomain(object):
        def attachDeviceFlags(self, xml, flags):
            raise RuntimeError('attach failed')

    class FakeVm(object):
        domain = FakeDomain()

        def find_scsi_controller_by_iothread(self, io_thread_id):
            return "0"

    aliases = []
    monkeypatch.setattr(vm_plugin, 'get_vm_by_uuid', lambda uuid: FakeVm())
    monkeypatch.setattr(vm_plugin.VmPlugin, 'get_next_scsi_controller_index', staticmethod(lambda vm: 3))

    with pytest.raises(RuntimeError):
        vm_plugin.VmPlugin.add_scsi_controller_with_driver('vm-uuid', queues=4, created_aliases=aliases)

    assert aliases == ['scsi3']


@pytest.mark.kvmagent
def test_attach_data_volume_failure_cleans_created_mapping(monkeypatch):
    class FakeDomain(object):
        def attachDeviceFlags(self, xml, flags):
            raise RuntimeError('disk attach failed')

    class FakeCurrentVm(object):
        def _get_target_disk(self, volume, is_exception=False):
            return None, None

    vm = vm_plugin.Vm()
    vm.uuid = 'vm-uuid'
    vm.domain = FakeDomain()
    attached_disk_xml = []
    volume = cbd_volume(
        useVirtio=True,
        useVirtioSCSI=True,
        installPath='cbd:test-volume',
        wwn='123456789abcdef0',
        physicalBlockSize=None,
    )
    created_iothreads = []
    deleted_iothreads = []
    detached_aliases = []

    def fake_attach_device(xml, flags):
        attached_disk_xml.append(xml)
        raise RuntimeError('disk attach failed')

    def fake_add_controller(vm_uuid, io_thread_id=None, queues=None, mapping_allocator=None, created_aliases=None):
        created_aliases.append('scsi5')
        return 5

    vm.domain.attachDeviceFlags = fake_attach_device
    monkeypatch.setattr(vm_plugin.linux, 'retry', no_retry)
    monkeypatch.setattr(vm_plugin.linux, 'wait_callback_success', lambda callback, *args: callback(None))
    monkeypatch.setattr(vm_plugin, 'file_volume_check', lambda v: v)
    monkeypatch.setattr(vm_plugin, 'get_vm_by_uuid', lambda uuid: FakeCurrentVm())
    monkeypatch.setattr(vm_plugin.Vm, 'set_device_address', staticmethod(lambda *args: None))
    monkeypatch.setattr(vm_plugin.VmPlugin, 'get_iothread_info', staticmethod(lambda uuid: []))
    monkeypatch.setattr(vm_plugin.VmPlugin, 'add_io_thread',
                        staticmethod(lambda uuid, iothread_id: created_iothreads.append(iothread_id) or None))
    monkeypatch.setattr(vm_plugin.VmPlugin, 'del_io_thread',
                        staticmethod(lambda uuid, iothread_id: deleted_iothreads.append(iothread_id) or None))
    monkeypatch.setattr(vm_plugin.VmPlugin, 'add_scsi_controller_with_driver', staticmethod(fake_add_controller))
    monkeypatch.setattr(vm, 'detach_controller_by_alias',
                        lambda vm_uuid, alias: detached_aliases.append(alias) or None)

    with pytest.raises(RuntimeError):
        vm._attach_data_volume(volume, EmptyAddons())

    assert created_iothreads == [101, 102, 103, 104, 105, 106, 107, 108]
    assert deleted_iothreads == created_iothreads
    assert detached_aliases == ['scsi5']
    disk = vm_plugin.etree.fromstring(attached_disk_xml[0])
    assert disk.find('driver').get('queues') is None
    assert disk.find('driver').find('iothreads') is None
    assert disk.find('target').get('bus') == 'scsi'


@pytest.mark.kvmagent
def test_detach_data_volume_keeps_referenced_iothread(monkeypatch):
    class FakeDomain(object):
        def detachDeviceFlags(self, xml, flags):
            return None

    class FakeTargetDisk(object):
        def dump(self):
            return '''
            <disk type="network" device="disk">
              <driver name="qemu" type="raw">
                <iothreads>
                  <iothread id="101"><queue id="0"/></iothread>
                  <iothread id="102"><queue id="1"/></iothread>
                </iothreads>
              </driver>
              <target dev="sdb" bus="scsi"/>
              <address type="drive" controller="1"/>
            </disk>
            '''

    class FakeVm(object):
        def __init__(self, domain_xml):
            self.domain_xml = domain_xml

        def _get_target_disk(self, volume, is_exception=False):
            return None, None

    controller_xml = '''
    <domain>
      <devices>
        <controller type="scsi" model="virtio-scsi" index="1">
          <driver queues="16">
            <iothreads>
              <iothread id="101"><queue id="0"/></iothread>
              <iothread id="102"><queue id="1"/></iothread>
            </iothreads>
          </driver>
          <alias name="scsi1"/>
        </controller>
      </devices>
    </domain>
    '''
    referenced_xml = '''
    <domain>
      <devices>
        <disk type="network" device="disk">
          <driver name="qemu" type="raw">
            <iothreads>
              <iothread id="101"><queue id="0"/></iothread>
            </iothreads>
          </driver>
        </disk>
      </devices>
    </domain>
    '''
    current_vms = [
        FakeVm('<domain><devices/></domain>'),
        FakeVm(controller_xml),
        FakeVm(referenced_xml),
    ]
    vm = vm_plugin.Vm()
    vm.uuid = 'vm-uuid'
    vm.domain = FakeDomain()
    vm.domain_xml = controller_xml
    volume = cbd_volume(
        useVirtio=False,
        useVirtioSCSI=True,
        installPath='cbd:test-volume',
        volumeUuid='volume-uuid',
    )
    detached_aliases = []
    deleted_iothreads = []

    def fake_get_vm_by_uuid(uuid):
        return current_vms.pop(0) if current_vms else FakeVm(referenced_xml)

    monkeypatch.setattr(vm_plugin.linux, 'retry', no_retry)
    monkeypatch.setattr(vm_plugin.linux, 'wait_callback_success', lambda callback, *args: callback(None))
    monkeypatch.setattr(vm_plugin, 'get_vm_by_uuid', fake_get_vm_by_uuid)
    monkeypatch.setattr(vm_plugin, 'is_libvirt_support_blockdev', lambda version: True)
    monkeypatch.setattr(vm_plugin.VmPlugin, 'del_io_thread',
                        staticmethod(lambda uuid, iothread_id: deleted_iothreads.append(iothread_id) or None))
    monkeypatch.setattr(vm, '_get_target_disk', lambda v: (FakeTargetDisk(), 'sdb'))
    monkeypatch.setattr(vm, 'detach_controller_by_alias',
                        lambda vm_uuid, alias: detached_aliases.append(alias) or None)

    vm._detach_data_volume(volume)

    assert detached_aliases == ['scsi1']
    assert deleted_iothreads == [102]
