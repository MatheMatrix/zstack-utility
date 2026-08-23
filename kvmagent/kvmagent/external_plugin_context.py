# -*- coding: utf-8 -*-
from __future__ import absolute_import

from kvmagent.external_plugin_route_guard import guard_mutation


class ExternalPluginContext(object):
    def __init__(self, registry, record, http_server):
        self._registry = registry
        self._record = record
        self._http_server = http_server
        self._pending_routes = []
        self._active = False

    def metadata(self):
        return self._record.manifest.metadata()

    def set_capabilities(self, capabilities):
        self._record.capabilities = capabilities

    def _guard(self, handler, mutable):
        if not mutable:
            return handler

        return guard_mutation(
            handler,
            lambda: self._registry.can_mutate(self._record.plugin_id),
            lambda: self._record.compatibility_state)

    def _publish(self, kind, path, handler):
        try:
            getattr(self._http_server, "register_%s_uri" % kind)(path, handler)
        except Exception:
            unregister = getattr(self._http_server, "unregister_uri", None)
            if unregister is not None:
                unregister(path)
            raise
        self._record.add_route(path)

    def _register_uri(self, kind, path, handler, mutable):
        with self._record.lifecycle_lock:
            if (self._registry.is_stop_requested() or
                    self._record.context is not self):
                raise RuntimeError("external plugin route registration was cancelled")
            path = self._registry.claim_route(self._record.plugin_id, path)
            guarded = self._guard(handler, mutable)
            try:
                if self._active:
                    self._publish(kind, path, guarded)
                else:
                    self._pending_routes.append((kind, path, guarded))
            except Exception:
                self._registry.release_route(self._record.plugin_id, path)
                raise

    def register_sync_uri(self, path, handler, mutable=True):
        self._register_uri("sync", path, handler, mutable)

    def register_async_uri(self, path, handler, mutable=True):
        self._register_uri("async", path, handler, mutable)

    def activate(self):
        with self._record.lifecycle_lock:
            if (self._registry.is_stop_requested() or
                    self._record.context is not self):
                raise RuntimeError("external plugin activation was cancelled")
            pending = list(self._pending_routes)
            self._record.state = "STARTED"
            try:
                register_batch = getattr(
                    self._http_server, "register_uri_batch", None)
                if register_batch is not None:
                    register_batch(pending)
                    for unused_kind, path, unused_handler in pending:
                        self._record.add_route(path)
                else:
                    for kind, path, handler in pending:
                        self._publish(kind, path, handler)
                self._pending_routes = []
                self._active = True
            except Exception:
                self._record.state = "LOADED"
                raise

    def rollback(self):
        for unused_kind, path, unused_handler in self._pending_routes:
            self._registry.release_route(self._record.plugin_id, path)
        self._pending_routes = []
        self._active = False
