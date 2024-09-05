import zstack as zs
import veritas as v

"""单个虚拟机的备份流程"""

def vm_backup(cmd):
    connection_handle = zs.init_access(cmd.ip, cmd.user, cmd.password)
    backup_metadata = zs.vm_backup_begin(connection_handle, cmd.vm_uuid, cmd.last_saved_point_timestamp)
    for volume_backup_data in backup_metadata.volume_backup_metadata:
        source_disk_handle = zs.disk_open(connection_handle, volume_backup_data.path)

        # 灾备厂商的备份磁盘准备接口
        target_disk_handle = v.create_disk(volume_backup_data.virtual_size)
        # 灾备厂商保存备份任务信息
        v.backup_metadata_save(backup_metadata.uuid, volume_backup_data.uuid, volume_backup_data.bitmaps, backup_metadata.bitmap_timestamp)

        for map in zs.bitmap_deserialize(volume_backup_data.bitmaps):
            read_buffer = zs.disk_read(source_disk_handle, map.start_sector, map.num_sectors)
            v.disk_write(target_disk_handle, map.start_sector, map.num_sectors, read_buffer)
        zs.disk_close(source_disk_handle)

    zs.volume_backup_end(connection_handle, backup_metadata.uuid)
    zs.exit_access(connection_handle)


"""单个云盘的备份流程"""


def volume_backup(cmd):
    connection_handle = zs.init_access(cmd.ip, cmd.user, cmd.password)
    backup_metadata = zs.volume_backup_begin(connection_handle, cmd.volume_uuid, cmd.last_saved_point_timestamp)
    source_disk_handle = zs.disk_open(connection_handle, backup_metadata.path)

    # 灾备厂商的备份磁盘准备接口
    target_disk_handle = v.create_disk(backup_metadata.virtual_size)
    # 灾备厂商保存备份任务信息
    v.backup_metadata_save(backup_metadata.uuid, backup_metadata.bitmaps, backup_metadata.last_saved_point_timestamp)

    for map in zs.bitmap_deserialize(backup_metadata.bitmaps):
        read_buffer = zs.disk_read(source_disk_handle, map.start_sector, map.num_sectors)
        v.disk_write(target_disk_handle, map.start_sector, map.num_sectors, read_buffer)

    zs.volume_backup_end(connection_handle, backup_metadata.uuid)
    zs.disk_close(source_disk_handle)
    zs.exit_access(connection_handle)


"""单个云盘恢复流程"""


def volume_recovery(cmd):
    connection_handle = zs.init_access(cmd.ip, cmd.user, cmd.password)
    # 备份厂商构建备份恢复任务的元数据信息
    recovery_metadata = v.get_recovery_metadata(cmd.backup_uuid)

    path = zs.prepare_recovery(connection_handle, recovery_metadata)
    target_disk_handle = zs.disk_open(connection_handle, path)

    # 灾备厂商的备份数据获取接口
    backup_bitmaps, source_disk_handle = v.backup_metadata_load(cmd.backup_uuid)
    backup_bitmap = zs.bitmap_merge(backup_bitmaps)

    for map in zs.bitmap_deserialize(backup_bitmap):
        read_buffer = v.disk_read(source_disk_handle, map.start_sector, map.num_sectors)
        zs.disk_write(target_disk_handle, map.start_sector, map.num_sectors, read_buffer)

    # 调用zstack 相关API 进行备份恢复
    zs.recovery(cmd.backup_uuid, target_disk_handle)

    zs.disk_close(target_disk_handle)
    zs.exit_access(connection_handle)


def init_access(ip, user, password):
    """ 初始化与 ZStack 管理节点的连接， 在进程初始化过程中调用。 """

    # Params:
    #   ip: ZStack 管理节点的 IP 地址
    #   user: ZStack 管理节点的用户名
    #   password: ZStack 管理节点的密码

    # Return:
    #   connection_handle: 与 ZStack 管理节点的连接句柄
    return


def exit_access(connection_handle):
    """ 释放与 ZStack 管理节点的连接，在进程退出时调用 """

    # Params:
    #   connection_handle: 与 ZStack 管理节点的连接句柄

    # Return: 无
    return


def disk_open(connection_handle, path):
    """ 打开指定的虚拟机磁盘，打开磁盘才能进行读写等操作 """

    # Params:
    #   connection_handle: 与 ZStack 管理节点的连接句柄
    #   path: 磁盘路径

    # Return::
    #   disk_handle: 打开磁盘返回的句柄
    return


def disk_close(disk_handle):
    """ 关闭打开的虚拟磁盘连接 """

    # Params:
    #   disk_handle: 先前打开磁盘返回的句柄

    # Return: 无
    return


def disk_read(disk_handle, start_sector, num_sectors):
    """ 先前通过备份任务获取的有效数据变化块，记录在bitmap中，依据bitmap记录的起始、偏移从磁盘中读取数据 """

    # Params:
    #   disk_handle: 先前打开磁盘返回的句柄
    #   start_sector: 读取的起始偏移地址
    #   num_sectors: 要读取的扇区数量

    # Return:
    #   read_buffer: 读取数据存放的缓冲区
    return


def disk_write(disk_handle, start_sector, num_sectors, write_buffer):
    """ 将备份数据，依据bitmap中记录的数据块的起始、偏移，写入到虚拟机磁盘中 """

    # Params:
    #   disk_handle: 打开磁盘返回的句柄
    #   start_sector: 读取的起始偏移地址
    #   num_sectors: 要读取的扇区数量
    #   write_buffer: 读取数据存放的缓冲区

    # Return: 无
    return


def bitmap_serialize(bitmap_matedata_map):
    """ 将位图对象序列化为bitmap元数据Map """

    # Params:
    #   bitmap_matedata_map: bitmap元数据信息Map

    # Return:
    #   bitmap: 位图对象
    return


def bitmap_deserialize(bitmap):
    # 将bitmap元数据Map反序列化为位图对象

    # Params:
    #   bitmap: 位图对象

    # Return:
    #   bitmap_matedata_map: bitmap元数据信息Map
    return


def bitmap_merge(*bitmaps):
    # 合并多个位图对象

    # Params:
    #  *bitmaps: 多个位图对象

    # Return:
    #   bitmap: 合并一个全量bitmap
    return


def volume_backup_begin(connection_handle, volume_uuid, bitmap_timestamp):
    """ 开始云盘备份任务 """

    # Params:
    #   connection_handle: 与 ZStack 管理节点的连接句柄
    #   volume_uuid: 云盘的唯一标识符
    #   last_saved_point_timestamp: 位图列表时间戳，用于比较是否可与上次的增量备份是连续的
    #                不填，则进行全量备份
    #                若填写bitmap_timestamp，当虚机不存在bitmap（重启或异常情况），增量备份bitmap时间戳与上次不符等情况下会自动做全量备份

    # Return:
    #   backup_metadata: 备份任务详情，包含备份任务的唯一标识符、源磁盘路径、备份模式和位图列表等
    #                   uuid: 备份任务的唯一标识符
    #                   path: 源磁盘路径
    #                   virtual_size: 源磁盘路径
    #                   mode: 真实备份模式，“full/incremental”
    #                   bitmap: 位图列表
    #                   bitmap_timestamp: 最新的位图列表时间戳
    return


def volume_backup_end(connection_handle, backup_uuid):
    """ 结束备份任务：停止备份任务，删除云平台侧快照数据 """

    # Params:
    #   connection_handle: 与 ZStack 管理节点的连接句柄
    #   backup_uuid: 备份任务的唯一标识符

    # Return: 无
    return


def vm_backup_begin(connection_handle, vm_uuid, bitmap_timestamp):
    """ 开始云盘备份任务 """

    # Params:
    #   connection_handle: 与 ZStack 管理节点的连接句柄
    #   volume_uuid: 云盘的唯一标识符
    #   last_saved_point_timestamp: 位图列表时间戳，用于比较是否可与上次的增量备份是连续的
    #                不填，则进行全量备份
    #                若填写bitmap_timestamp，当虚机不存在bitmap（重启或异常情况），增量备份bitmap时间戳与上次不符等情况下会自动做全量备份

    # Return:
    #   backup_metadata: 备份任务详情，包含备份任务的唯一标识符、源磁盘路径、备份模式和位图列表等
    #                   uuid: 备份任务的唯一标识符
    #                   bitmap_timestamp: 最新的位图列表时间戳
    #                   volume_backup_metadata: List类型，云盘的备份元数据信息
    #                                   uuid: 云盘uuid
    #                                   path: 源磁盘路径
    #                                   virtual_size: 源磁盘路径
    #                                   mode: 真实备份模式，“full/incremental”
    #                                   bitmap: 位图列表
    return


def vm_backup_end(connection_handle, backup_uuid):
    """ 结束备份任务：停止备份任务，删除云平台侧快照数据 """

    # Params:
    #   connection_handle: 与 ZStack 管理节点的连接句柄
    #   backup_uuid: 备份任务的唯一标识符

    # Return: 无
    return


def prepare_recovery(connection_handle, recovery_metadata):
    """ 准备云盘恢复，将恢复任务需要的磁盘信息，恢复模式，虚拟机启动选项传给ZStack，做执行恢复任务的准备工作 """

    # Params:
    #   connection_handle: 与 ZStack 管理节点的连接句柄
    #   recovery_metadata: 恢复任务的元数据信息
    #                   mode： 新建/覆盖磁盘恢复
    #                   volume_uuid: 磁盘的唯一标识符
    #                   volume_size: 磁盘容量
    #                   uuid： 恢复任务的唯一标识符

    # Return:
    #   path: 恢复任务创建的目标磁盘路径
    return





