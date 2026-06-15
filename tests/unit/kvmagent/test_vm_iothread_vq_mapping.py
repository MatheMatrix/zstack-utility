# -*- coding: utf-8 -*-

import pytest

from zstacklib.utils import plugin


class FakeTaskDaemon(object):
    def __init__(self, *args, **kwargs):
        pass


plugin.TaskDaemon = FakeTaskDaemon

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


class FakeLibvirtError(Exception):
    pass


DOMAIN_XML_WITH_USED_IOTHREAD = '''
<domain>
  <iothreadids>
    <iothread id="101"/>
  </iothreadids>
  <devices>
    <disk type="network" device="disk">
      <driver name="qemu" type="raw" cache="none" discard="unmap" queues="4"/>
      <source protocol="cbd" name="old"/>
      <target dev="vdb" bus="virtio"/>
    </disk>
  </devices>
</domain>
'''


def cbd_migration_volume(**kwargs):
    values = {
        'installPath': 'cbd:new-volume',
        'dev_letter': 'b',
        'multiQueues': '4',
        'ioThreads': 2,
        'physicalBlockSize': None,
    }
    values.update(kwargs)
    return cbd_volume(**values)


class FakeDomainXmlVm(object):
    domain_xml = DOMAIN_XML_WITH_USED_IOTHREAD

    def _get_target_disk_by_path(self, path):
        return None, 'vdb'


def write_temp_file_to(monkeypatch, path):
    def write_temp_file(content):
        path.write_text(content)
        return str(path)

    monkeypatch.setattr(vm_plugin.linux, 'write_to_temp_file', write_temp_file)


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


def migration_domain_with_virtio_disks(count=1, queues='4'):
    driver_queues = '' if queues is None else ' queues="%s"' % queues
    disks = ''.join([
        '''
        <disk type="network" device="disk">
          <driver name="qemu" type="raw" cache="none" discard="unmap"%s/>
          <source protocol="cbd" name="old-%s"/>
          <target dev="vd%s" bus="virtio"/>
        </disk>
        ''' % (driver_queues, index, chr(ord('a') + index))
        for index in range(count)
    ])
    return vm_plugin.etree.fromstring('<domain><devices>%s</devices></domain>' % disks)


@pytest.mark.kvmagent
def test_migration_cbd_disk_allocates_iothread_vq_mapping_from_driver_queues():
    root = migration_domain_with_virtio_disks()
    disk = root.find('./devices/disk')
    volume = cbd_volume(multiQueues='16', ioThreads=2)

    vm_plugin.VmPlugin._apply_migration_iothread_vq_mapping(root, disk, volume)

    driver = disk.find('driver')
    assert driver.get('queues') == '4'
    iothreads = driver.findall('./iothreads/iothread')
    assert [i.get('id') for i in iothreads] == ['101', '102']
    assert [q.get('id') for q in iothreads[0].findall('queue')] == ['0', '1']
    assert [q.get('id') for q in iothreads[1].findall('queue')] == ['2', '3']
    assert root.find('iothreads').text == '2'
    assert [i.get('id') for i in root.findall('./iothreadids/iothread')] == ['101', '102']


@pytest.mark.kvmagent
def test_migration_cbd_disk_without_driver_queues_does_not_allocate_iothread_vq_mapping():
    root = migration_domain_with_virtio_disks(queues=None)
    disk = root.find('./devices/disk')
    volume = cbd_volume(multiQueues='16', ioThreads=2)

    vm_plugin.VmPlugin._apply_migration_iothread_vq_mapping(root, disk, volume)

    assert disk.find('./driver/iothreads') is None
    assert root.find('iothreads') is None
    assert root.find('iothreadids') is None


@pytest.mark.kvmagent
def test_migration_cbd_disks_allocate_distinct_iothread_ids():
    root = migration_domain_with_virtio_disks(count=2)
    volume = cbd_volume(multiQueues='16', ioThreads=2)

    for disk in root.findall('./devices/disk'):
        vm_plugin.VmPlugin._apply_migration_iothread_vq_mapping(root, disk, volume)

    disk_iothread_ids = [
        [i.get('id') for i in disk.findall('./driver/iothreads/iothread')]
        for disk in root.findall('./devices/disk')
    ]
    assert disk_iothread_ids == [['101', '102'], ['103', '104']]
    assert root.find('iothreads').text == '4'
    assert [i.get('id') for i in root.findall('./iothreadids/iothread')] == ['101', '102', '103', '104']


@pytest.mark.kvmagent
def test_build_domain_new_xml_allocates_cbd_iothreads_from_domain_root():
    vm = vm_plugin.Vm()
    vm.get_migratable_xml = lambda: DOMAIN_XML_WITH_USED_IOTHREAD
    vm._get_target_disk_by_path = lambda path: (None, 'vdb')

    disks, dest_xml = vm._build_domain_new_xml({'old': cbd_migration_volume()})

    assert disks == ['vdb']
    root = vm_plugin.etree.fromstring(dest_xml)
    iothreads = root.findall('./devices/disk/driver/iothreads/iothread')
    assert [i.get('id') for i in iothreads] == ['102', '103']


@pytest.mark.kvmagent
def test_vm_plugin_build_domain_new_xml_allocates_cbd_iothreads_from_domain_root(monkeypatch, tmp_path):
    plugin = object.__new__(vm_plugin.VmPlugin)
    domain_xml_path = tmp_path / 'domain.xml'
    write_temp_file_to(monkeypatch, domain_xml_path)

    disks, fpath = plugin._build_domain_new_xml(FakeDomainXmlVm(), {'old': cbd_migration_volume()})

    assert disks == ['vdb']
    root = vm_plugin.etree.parse(fpath).getroot()
    iothreads = root.findall('./devices/disk/driver/iothreads/iothread')
    assert [i.get('id') for i in iothreads] == ['102', '103']


@pytest.mark.kvmagent
def test_vm_plugin_build_dest_disk_xml_allocates_cbd_iothreads_from_domain_root(monkeypatch, tmp_path):
    plugin = object.__new__(vm_plugin.VmPlugin)
    disk_xml_path = tmp_path / 'disk.xml'
    write_temp_file_to(monkeypatch, disk_xml_path)

    dev, fpath = plugin._build_dest_disk_xml(FakeDomainXmlVm(), 'old', cbd_migration_volume())

    assert dev == 'vdb'
    disk = vm_plugin.etree.parse(fpath).getroot()
    iothreads = disk.findall('./driver/iothreads/iothread')
    assert [i.get('id') for i in iothreads] == ['102', '103']


@pytest.mark.kvmagent
def test_retrieve_diskele_allocates_cbd_iothreads_from_domain_root():
    class FakeNbdDisk(object):
        class Source(object):
            name_ = 'old'

        source = Source()

        def dump(self):
            return '''
            <disk type="network" device="disk">
              <driver name="qemu" type="raw" cache="none" discard="unmap" queues="4"/>
              <source protocol="cbd" name="old"/>
              <target dev="vdb" bus="virtio"/>
            </disk>
            '''

    class FakeDomainXmlObject(object):
        def dump(self):
            return DOMAIN_XML_WITH_USED_IOTHREAD

    task = object.__new__(vm_plugin.VmVolumesRecoveryTask)
    task.volumes = [cbd_migration_volume(installPath='cbd:new-volume?old')]
    task.domain_xmlobject = FakeDomainXmlObject()

    disk = task.retrieve_diskele(FakeNbdDisk())

    iothreads = disk.findall('./driver/iothreads/iothread')
    assert [i.get('id') for i in iothreads] == ['102', '103']


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
def test_migration_cbd_scsi_controller_allocates_iothread_vq_mapping_from_controller_queues():
    root = vm_plugin.etree.fromstring('''
    <domain>
      <devices>
        <controller type="scsi" model="virtio-scsi" index="1">
          <driver queues="4"/>
          <alias name="scsi1"/>
        </controller>
        <disk type="network" device="disk">
          <driver name="qemu" type="raw" cache="none" discard="unmap"/>
          <source protocol="cbd" name="old"/>
          <target dev="sdb" bus="scsi"/>
          <address type="drive" controller="1"/>
        </disk>
      </devices>
    </domain>
    ''')
    old_disk = root.find('./devices/disk')
    volume = cbd_volume(
        installPath='cbd:new-volume',
        dev_letter='b',
        useVirtio=True,
        useVirtioSCSI=False,
        multiQueues='16',
        ioThreads=2,
        physicalBlockSize=None,
        wwn='123456789abcdef0',
    )

    new_disk = vm_plugin.VmPlugin._get_new_disk(old_disk, volume)
    vm_plugin.VmPlugin._apply_migration_iothread_vq_mapping(root, new_disk, volume)

    disk_driver = new_disk.find('driver')
    controller_driver = root.find('./devices/controller/driver')
    iothreads = controller_driver.findall('./iothreads/iothread')
    assert disk_driver.get('queues') is None
    assert disk_driver.find('iothreads') is None
    assert controller_driver.get('queues') == '4'
    assert [i.get('id') for i in iothreads] == ['101', '102']
    assert [q.get('id') for q in iothreads[0].findall('queue')] == ['0', '1']
    assert [q.get('id') for q in iothreads[1].findall('queue')] == ['2', '3']
    assert root.find('iothreads').text == '2'
    assert [i.get('id') for i in root.findall('./iothreadids/iothread')] == ['101', '102']


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
    monkeypatch.setattr(vm_plugin.libvirt, 'libvirtError', FakeLibvirtError)
    monkeypatch.setattr(vm_plugin.Vm, 'set_device_address', staticmethod(lambda *args: None))
    monkeypatch.setattr(vm_plugin.VmPlugin, 'get_iothread_info', staticmethod(lambda uuid: []))
    monkeypatch.setattr(vm_plugin.VmPlugin, 'add_io_thread',
                        staticmethod(lambda uuid, iothread_id: created_iothreads.append(iothread_id) or None))
    monkeypatch.setattr(vm_plugin.VmPlugin, 'del_io_thread',
                        staticmethod(lambda uuid, iothread_id: deleted_iothreads.append(iothread_id) or None))
    monkeypatch.setattr(vm_plugin.VmPlugin, 'add_scsi_controller_with_driver', staticmethod(fake_add_controller))
    monkeypatch.setattr(vm, 'detach_controller_by_alias',
                        lambda vm_uuid, alias: detached_aliases.append(alias) or None,
                        raising=False)

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
                        lambda vm_uuid, alias: detached_aliases.append(alias) or None,
                        raising=False)

    vm._detach_data_volume(volume)

    assert detached_aliases == ['scsi1']
    assert deleted_iothreads == [102]
