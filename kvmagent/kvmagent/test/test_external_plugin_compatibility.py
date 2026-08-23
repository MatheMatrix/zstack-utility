# -*- coding: utf-8 -*-
from __future__ import absolute_import

import unittest

from kvmagent.external_plugin_manifest import ExternalPluginManifest, ManifestError
from kvmagent.external_plugin_runtime import CompatibilityError, validate_compatibility


class ExternalPluginCompatibilityTest(unittest.TestCase):
    def setUp(self):
        self.compatibility = dict((name, ">=1.0,<10.0") for name in (
            "python", "kvmAgent", "zstacklib", "qemu", "libvirt"))
        self.compatibility.update({
            "os": ["centos7", "kylin10", "helix8.4r"],
            "architectures": ["x86_64", "aarch64"],
        })
        self.versions = dict((name, "5.1.0") for name in (
            "python", "kvmAgent", "zstacklib", "qemu", "libvirt"))
        self.versions.update({"os": "centos7", "architectures": "x86_64"})

    def _manifest_document(self):
        return {
            "schemaVersion": "1",
            "identity": {
                "pluginId": "zrm-kvm-plugin",
                "version": "2.0.0",
                "contentSha256": "0" * 64,
            },
            "loading": {
                "entryModule": "zrm_kvm_plugin.plugin",
                "entryClass": "ZrmPlugin",
                "pluginApi": 1,
            },
            "compatibility": dict(self.compatibility),
            "interfaces": {"zrmApiVersion": 1, "errorCodeVersion": 1},
            "capabilities": {"replication": {"full": {"supported": True}}},
            "security": {"dynamicDependencies": False},
        }

    def test_all_declared_runtime_dimensions_are_required(self):
        self.versions["libvirt"] = None

        with self.assertRaises(CompatibilityError) as raised:
            validate_compatibility(self.compatibility, self.versions)

        self.assertEqual("PLUGIN_RUNTIME_VERSION_UNAVAILABLE",
                         raised.exception.code)
        self.assertEqual("libvirt", raised.exception.dependency)

    def test_semantic_version_outside_range_is_incompatible(self):
        self.versions["qemu"] = "10.0.0"

        with self.assertRaises(CompatibilityError) as raised:
            validate_compatibility(self.compatibility, self.versions)

        self.assertEqual("PLUGIN_RUNTIME_INCOMPATIBLE", raised.exception.code)
        self.assertEqual("qemu", raised.exception.dependency)

    def test_actual_zrm_manifest_compatibility_dimensions_are_accepted(self):
        manifest = ExternalPluginManifest(self._manifest_document(), "manifest.yaml")

        self.assertEqual(
            {"python", "kvmAgent", "zstacklib", "qemu", "libvirt",
             "os", "architectures"},
            set(manifest.compatibility))
        self.assertTrue(validate_compatibility(manifest.compatibility,
                                               self.versions))

    def test_manifest_requires_exact_compatibility_dimension_keys(self):
        for missing in self.compatibility:
            document = self._manifest_document()
            document["compatibility"].pop(missing)
            with self.assertRaises(ManifestError) as raised:
                ExternalPluginManifest(document, "manifest.yaml")
            self.assertEqual("PLUGIN_COMPATIBILITY_INVALID",
                             raised.exception.code)

        document = self._manifest_document()
        document["compatibility"]["kernel"] = ">=3.10"
        with self.assertRaises(ManifestError) as raised:
            ExternalPluginManifest(document, "manifest.yaml")
        self.assertEqual("PLUGIN_COMPATIBILITY_INVALID", raised.exception.code)

    def test_manifest_rejects_malformed_blank_or_duplicate_dimensions(self):
        invalid_values = (
            ("python", "latest"),
            ("qemu", ""),
            ("os", []),
            ("os", ["centos7", "centos7"]),
            ("os", ["centos7", ""]),
            ("architectures", "x86_64"),
            ("architectures", ["x86_64", "x86_64"]),
            ("architectures", ["x86 64"]),
        )
        for dimension, value in invalid_values:
            document = self._manifest_document()
            document["compatibility"][dimension] = value
            with self.assertRaises(ManifestError) as raised:
                ExternalPluginManifest(document, "manifest.yaml")
            self.assertEqual("PLUGIN_COMPATIBILITY_INVALID",
                             raised.exception.code)

    def test_os_and_architecture_membership_are_hard_gates(self):
        for dimension, actual in (("os", "ubuntu24.04"),
                                  ("architectures", "ppc64le")):
            versions = dict(self.versions)
            versions[dimension] = actual
            with self.assertRaises(CompatibilityError) as raised:
                validate_compatibility(self.compatibility, versions)
            self.assertEqual("PLUGIN_RUNTIME_INCOMPATIBLE",
                             raised.exception.code)
            self.assertEqual(dimension, raised.exception.dependency)
            self.assertEqual(actual, raised.exception.actual)

    def test_full_manifest_digest_is_stable_across_mapping_order(self):
        document = self._manifest_document()
        reordered = dict(reversed(list(document.items())))
        reordered["identity"] = dict(reversed(list(
            document["identity"].items())))
        reordered["compatibility"] = dict(reversed(list(
            document["compatibility"].items())))

        first = ExternalPluginManifest(document, "first.yaml")
        second = ExternalPluginManifest(reordered, "second.yaml")

        self.assertEqual(first.manifest_digest, second.manifest_digest)


if __name__ == "__main__":
    unittest.main()
