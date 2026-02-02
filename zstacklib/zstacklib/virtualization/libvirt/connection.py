from __future__ import annotations

import threading
from typing import Any, Callable

from .exceptions import LibvirtError, LibvirtConnectionError, LibvirtNotAvailableError
from .models import LibvirtConfig, HostInfo


_connection_lock = threading.Lock()
_cached_connection: Any = None


def _get_libvirt():
    try:
        import libvirt
        return libvirt
    except ImportError:
        raise LibvirtNotAvailableError()


class LibvirtConnection:
    _instance: "LibvirtConnection | None" = None
    _lock = threading.Lock()
    
    def __init__(self, config: LibvirtConfig | None = None):
        self.config = config or LibvirtConfig()
        self._conn: Any = None
        self._conn_lock = threading.Lock()
    
    @classmethod
    def get_instance(cls, config: LibvirtConfig | None = None) -> "LibvirtConnection":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls(config)
        return cls._instance
    
    @classmethod
    def reset_instance(cls) -> None:
        with cls._lock:
            if cls._instance is not None:
                cls._instance.close()
                cls._instance = None
    
    def connect(self) -> Any:
        with self._conn_lock:
            if self._conn is not None:
                try:
                    self._conn.getVersion()
                    return self._conn
                except Exception:
                    self._conn = None
            
            libvirt = _get_libvirt()
            
            try:
                if self.config.readonly:
                    self._conn = libvirt.openReadOnly(self.config.uri)
                else:
                    self._conn = libvirt.open(self.config.uri)
                
                if self._conn is None:
                    raise LibvirtConnectionError(self.config.uri, "Connection returned None")
                    
                return self._conn
            except libvirt.libvirtError as e:
                raise LibvirtConnectionError(self.config.uri, str(e))
    
    def close(self) -> None:
        with self._conn_lock:
            if self._conn is not None:
                try:
                    self._conn.close()
                except Exception:
                    pass
                self._conn = None
    
    @property
    def connection(self) -> Any:
        return self.connect()
    
    def is_connected(self) -> bool:
        with self._conn_lock:
            if self._conn is None:
                return False
            try:
                self._conn.getVersion()
                return True
            except Exception:
                return False
    
    def get_host_info(self) -> HostInfo:
        conn = self.connect()
        info = conn.getInfo()
        
        return HostInfo(
            hostname=conn.getHostname(),
            max_vcpus=conn.getMaxVcpus(None),
            memory_kb=info[1] * 1024,
            cpus=info[2],
            mhz=info[3],
            numa_nodes=info[4],
            cpu_sockets=info[5],
            cpu_cores=info[6],
            cpu_threads=info[7],
            cpu_model=info[0],
            libvirt_version=str(conn.getLibVersion()),
        )


def get_connection(config: LibvirtConfig | None = None) -> LibvirtConnection:
    return LibvirtConnection.get_instance(config)


def with_connection(config: LibvirtConfig | None = None):
    def decorator(func: Callable) -> Callable:
        def wrapper(*args, **kwargs):
            conn = get_connection(config)
            return func(conn.connection, *args, **kwargs)
        wrapper.__name__ = func.__name__
        return wrapper
    return decorator
