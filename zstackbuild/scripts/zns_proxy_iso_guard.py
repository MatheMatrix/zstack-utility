#!/usr/bin/env python
import argparse
import hashlib
import json
import os


def sha256sum(path):
    digest = hashlib.sha256()
    with open(path, "rb") as stream:
        while True:
            chunk = stream.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def fail(message):
    raise SystemExit("zns-proxy ISO package guard failed: %s" % message)


def main():
    parser = argparse.ArgumentParser(description="Validate zns-proxy ISO package content")
    parser.add_argument("--ansible-dir", required=True)
    args = parser.parse_args()

    znsproxy_dir = os.path.join(args.ansible_dir, "znsproxy")
    package_path = os.path.join(znsproxy_dir, "zns-proxy.bin")
    manifest_path = os.path.join(znsproxy_dir, "zns-proxy-manifest.json")

    if not os.path.isfile(package_path):
        fail("missing znsproxy/zns-proxy.bin")
    if not os.path.isfile(manifest_path):
        fail("missing znsproxy/zns-proxy-manifest.json")

    with open(manifest_path) as stream:
        manifest = json.load(stream)

    expected = {
        "packageName": "zns-proxy.bin",
        "path": "zns-proxy.bin",
    }
    for key, value in expected.items():
        if manifest.get(key) != value:
            fail("manifest %s must be %s, got %s" % (key, value, manifest.get(key)))

    if manifest.get("sha256") != sha256sum(package_path):
        fail("manifest sha256 does not match znsproxy/zns-proxy.bin")

    if "znsagentansible" in os.listdir(args.ansible_dir):
        fail("znsagentansible must not be packaged in Cloud ISO")

    forbidden = []
    for root, _, files in os.walk(args.ansible_dir):
        for name in files:
            if name.startswith("zns-agent") and name.endswith(".bin"):
                forbidden.append(os.path.join(root, name))
    if forbidden:
        fail("zns-agent binary must not be packaged: %s" % ", ".join(forbidden))


if __name__ == "__main__":
    main()
