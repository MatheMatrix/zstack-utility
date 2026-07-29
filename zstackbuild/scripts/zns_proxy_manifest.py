#!/usr/bin/env python
import argparse
import datetime
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


def main():
    parser = argparse.ArgumentParser(description="Generate zns-proxy package manifest")
    parser.add_argument("--package", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--arch", required=True)
    parser.add_argument("--path", required=True)
    args = parser.parse_args()

    if not os.path.isfile(args.package):
        raise SystemExit("zns-proxy package not found: %s" % args.package)

    manifest = {
        "packageName": os.path.basename(args.package),
        "version": args.version,
        "arch": [item.strip() for item in args.arch.split(",") if item.strip()],
        "sha256": sha256sum(args.package),
        "path": args.path,
        "buildTime": datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
    }

    output_dir = os.path.dirname(args.output)
    if output_dir and not os.path.isdir(output_dir):
        os.makedirs(output_dir)

    with open(args.output, "w") as stream:
        json.dump(manifest, stream, indent=2, sort_keys=True)
        stream.write("\n")


if __name__ == "__main__":
    main()
