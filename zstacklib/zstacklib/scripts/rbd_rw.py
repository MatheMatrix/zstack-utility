import base64
import ctypes
import traceback

from zstacklib.utils.linux import get_config_path_from_fs_id

ctypes.CDLL('/lib64/librados.so', ctypes.RTLD_GLOBAL)
import sys
sys.path.insert(0, "/home/xclient/bin/python2/")
import rados
import rbd
import time
import json

external_conf = {}
external_conf['do_lunmap'] = 'false'

cluster = None
ioctx = dict()
images = dict()


class HeartbeatIOResult(object):
    def __init__(self, success, execute_time, reason=None, data=None):
        self.data = data
        self.execute_time = execute_time
        self.success = success
        self.reason = reason

    # json
    def __str__(self):
        try:
            return json.dumps(self.__dict__).replace('\n', '\\n')
        except Exception as e:
            self.data = base64.b64encode(self.data)
            return json.dumps(self.__dict__).replace('\n', '\\n')

def get_cluster(conf_pth):
    global cluster
    if not cluster:
        temp_cluster = rados.Rados(conffile=conf_pth, conf=external_conf)
        temp_cluster.connect()
        if temp_cluster.state == 'connected':
            cluster = temp_cluster
        else:
            raise Exception("failed to connect cluster, please check your configuration.")
    return cluster


def get_ioctx(pool_name, conf_path):
    global ioctx
    if pool_name not in ioctx:
        ioctx[pool_name] = get_cluster(conf_path).open_ioctx(pool_name)
    return ioctx[pool_name]


def get_image(pool_name, image_name, fs_id):
    conf_path = get_config_path_from_fs_id(fs_id)
    global images
    key = pool_name + '/' + image_name
    if key not in images:
        images[key] = rbd.Image(get_ioctx(pool_name, conf_path), image_name)
    return images[key]


def read_rbd_image(pool_name, image_name, fs_id, offset=0, size=sys.maxsize, stream=None):
    if stream is None and size > 1024 * 1024:
        raise Exception("size is too large to return value, please specify a stream to write the content to.")

    image = get_image(pool_name, image_name, fs_id)
    # Read image size
    image_size = image.size()
    total_size = min(size, image_size - offset)
    read_size = 0

    # Read and output the image content
    chunk_size = 4 * 1024 * 1024  # 4MB
    while read_size < total_size:
        chunk = min(chunk_size, total_size - read_size)
        data = _do_read_image(image, offset + read_size, chunk)
        if stream:
            stream.write(data)
        else:
            return data
        read_size += chunk


def write_rbd_image(pool_name, image_name, fs_id, offset=0, content=None):
    image = get_image(pool_name, image_name, fs_id)
    _do_write_image(image, offset, content)


def _do_read_image(image, offset, size):
    data_ptr = ctypes.create_string_buffer(size)
    def oncomplete(_, data):
        data_ptr.raw = data
    completion = image.aio_read(offset, size, oncomplete)
    for i in xrange(100):
        if completion.is_complete():
            break
        time.sleep(0.05)
    if not completion.is_complete():
        raise Exception("read image timeout after 5 seconds")
    completion.wait_for_complete_and_cb()
    if completion.get_return_value() != size:
        raise Exception("read image not completed, size: {} return code: {}".format(size, completion.get_return_value()))
    return data_ptr.raw


def _do_write_image(image, offset, content):
    completion = image.aio_write(content, offset, lambda _: None)
    for i in xrange(100):
        if completion.is_complete():
            break
        time.sleep(0.05)
    if not completion.is_complete():
        raise Exception("write image timeout after 5 seconds")
    completion.wait_for_complete_and_cb()
    if completion.get_return_value() != len(content):
        raise Exception("write image not completed, content length: {} return code: {}".format(
            len(content), completion.get_return_value()))


def listen_pipe():
    while True:
        operation = raw_input()
        if not operation:
            break

        ### operation: read rbd:pool/image 0 100
        ### operation: write rbd:pool/image 0 content
        splits = operation.split(None, 4)
        if len(splits) < 4:
            sys.stdout.write("Invalid operation: {}\n".format(operation))
            sys.stdout.flush()
            continue

        op = splits[0]
        path = splits[1]
        path = path.replace('rbd:', '')
        pool_name = path.split('/')[0]
        image_name = path.split('/')[1]
        start_time = time.time()
        result = None
        try:
            if op == 'readhb':
                fs_id = int(splits[2])
                offset = int(splits[3])
                size = int(splits[4])
                content = read_rbd_image(pool_name, image_name, fs_id, offset, size, stream=None)
                hbcontent = content.split('EOF')[0]
                result = HeartbeatIOResult(True, (time.time() - start_time) * 1000, data=hbcontent)
            elif op == 'writehb':
                fs_id = int(splits[2])
                offset = int(splits[3])
                content = splits[4]
                write_rbd_image(pool_name, image_name, fs_id, offset, content)
                result = HeartbeatIOResult(True, (time.time() - start_time) * 1000)
            else:
                raise Exception("Invalid operation: {}".format(op))
        except Exception as e:
            trace = traceback.format_exc()
            result = HeartbeatIOResult(False, (time.time() - start_time) * 1000, reason=str(e) + "; trace: " + trace)

        sys.stdout.write(str(result) + '\n')
        sys.stdout.flush()

def exit(sig, stack):
    global cluster
    global ioctx
    global images
    _log("Received signal {}, exiting".format(sig))
    for image in images.values():
        image.close()
    for ctx in ioctx.values():
        ctx.close()
    if cluster is not None:
        cluster.shutdown()
    sys.exit(0)


def dump_thread(sig, stack):
    _log("Received signal {}, dumping thread".format(sig))
    import threading
    import traceback
    id2name = dict([(th.ident, th.name) for th in threading.enumerate()])
    for threadId, stack in sys._current_frames().items():
        _log("# ThreadID: %s(%d)" % (id2name.get(threadId, ""), threadId))
        traceback.print_stack(f=stack)

    _log("")

def listen_signal():
    import signal
    signal.signal(signal.SIGTERM, exit)
    signal.signal(signal.SIGINT, exit)
    signal.signal(signal.SIGUSR2, dump_thread)

def _log(content):
    sys.stderr.write(content + "\n")
    sys.stderr.flush()

listen_signal()
if __name__ == '__main__':
    if len(sys.argv) == 1:
        listen_pipe()
        sys.exit(0)

    if len(sys.argv) != 5 and len(sys.argv) != 3:
        print >> sys.stderr, "Usage: {} <operation> <pool_name>/<image_name> [offset] [size/content]".format(sys.argv[0])
        print >> sys.stderr, "system arguments: {}".format(sys.argv)
        print >> sys.stderr, "args length: {}".format(len(sys.argv))
        sys.exit(1)

    op = sys.argv[1]
    path = sys.argv[2]
    path = path.replace('rbd:', '')
    pool_name = path.split('/')[0]
    image_name = path.split('/')[1]
    if op == 'read':
        if len(sys.argv) == 6:
            fs_id = int(sys.argv[3])
            offset = int(sys.argv[4])
            size = int(sys.argv[5])
            read_rbd_image(pool_name, image_name, fs_id, offset, size, stream=sys.stdout)
        else:
            fs_id = int(sys.argv[3])
            read_rbd_image(pool_name, image_name, fs_id)
    elif op == 'write':
        if len(sys.argv) == 6:
            fs_id = int(sys.argv[3])
            offset = int(sys.argv[4])
            content = sys.argv[5]
            write_rbd_image(pool_name, image_name, fs_id, offset, content)
    else:
        print >> sys.stderr, "Unknown operation: {}".format(op)
        sys.exit(1)
