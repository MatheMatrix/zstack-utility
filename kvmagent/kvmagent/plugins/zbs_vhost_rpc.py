import json
import socket

from zstacklib.utils import log

logger = log.get_logger(__name__)

DEFAULT_RPC_TIMEOUT = 60


class ZbsVhostRpcError(Exception):
    def __init__(self, method, code, message):
        self.code = code
        self.message = message
        super(ZbsVhostRpcError, self).__init__(
            "zbs vhost rpc[%s] failed: code=%s, message=%s" % (method, code, message))


class ZbsVhostRpc(object):
    def __init__(self, control_sock, timeout=DEFAULT_RPC_TIMEOUT):
        self.control_sock = control_sock
        self.timeout = timeout
        self._id = 0

    def _call(self, method, params=None):
        self._id += 1
        req = {"jsonrpc": "2.0", "id": self._id, "method": method}
        if params:
            req["params"] = params

        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        s.settimeout(self.timeout)
        try:
            s.connect(self.control_sock)
            s.sendall(json.dumps(req).encode())
            rsp = self._recv_json(s)
        finally:
            s.close()

        if "error" in rsp:
            err = rsp["error"]
            raise ZbsVhostRpcError(method, err.get("code"), err.get("message"))
        return rsp.get("result")

    def _recv_json(self, s):
        buf = b""
        while True:
            chunk = s.recv(65536)
            if not chunk:
                break
            buf += chunk
            try:
                return json.loads(buf.decode())
            except ValueError:
                continue
        raise ZbsVhostRpcError("recv", None, "incomplete json response: %s" % buf.decode("utf-8", "replace"))

    def bdev_zbs_create(self, zbs_file, name):
        return self._call("bdev_zbs_create", {"file": zbs_file, "name": name})

    def bdev_zbs_delete(self, name):
        return self._call("bdev_zbs_delete", {"name": name})

    def bdev_zbs_resize(self, name, new_size_mib):
        return self._call("bdev_zbs_resize", {"name": name, "new_size": new_size_mib})

    def bdev_get_bdevs(self, name=None):
        params = {"name": name} if name else None
        return self._call("bdev_get_bdevs", params)

    def get_bdev(self, name):
        try:
            bdevs = self.bdev_get_bdevs(name)
        except ZbsVhostRpcError as e:
            if e.code == -19:
                return None
            raise
        return bdevs[0] if bdevs else None

    def vhost_create_blk_controller(self, ctrlr, bdev):
        return self._call("vhost_create_blk_controller", {"ctrlr": ctrlr, "dev_name": bdev})

    def vhost_delete_controller(self, ctrlr):
        return self._call("vhost_delete_controller", {"ctrlr": ctrlr})

    def vhost_get_controllers(self, name=None):
        params = {"name": name} if name else None
        return self._call("vhost_get_controllers", params)

    def get_controller(self, ctrlr):
        try:
            ctrls = self.vhost_get_controllers(ctrlr)
        except ZbsVhostRpcError as e:
            if e.code in (-19, -32602, -32603):
                return None
            raise
        return ctrls[0] if ctrls else None
