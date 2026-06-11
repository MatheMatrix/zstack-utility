#!/usr/bin/env python
# encoding: utf-8

"""
License hardening: signed release manifest.

The manifest pins the SHA-256 of the critical files a tampered deployment would have
to modify (the mevoco JAR, the license CA, the exploded webapps/zstack/WEB-INF classes
and the Spring/serviceConfig XML that wire the license enforcement interceptor). At
build time the manifest is produced and signed with the release private key; at runtime
it is verified.

Authoritative verification (detached-signature check with a compile-time pinned public
key fingerprint) is performed by the native helper "zstack-integrity-verifier", not by
this module: a plain-Python signature check could be patched out by anyone holding root,
and the public key on disk could simply be replaced. This module covers the parts that
do not require the trust anchor:

  * build-time manifest construction and serialization, and
  * a file-hash-only fallback used when the native helper is absent (which must be
    reported as a degraded, not-fully-verified, result).

The signature itself is created at build time (see write_signature, which shells out to
openssl in the release/signing environment only) and verified by the native helper.
"""

import argparse
import glob as globmod
import hashlib
import json
import os
import subprocess

SCHEMA_VERSION = 1

# Critical files a license bypass would have to touch, relative to the install root
# (default /usr/local/zstack). Globs are expanded at manifest-generation time. This list
# deliberately covers the exploded webapp classes/JARs, the license CA, and the
# Spring/serviceConfig XML that wire the license enforcement interceptor (an attacker can
# disable enforcement by deleting that XML registration without touching any JAR).
DEFAULT_CRITICAL_GLOBS = [
    'apache-tomcat/webapps/zstack/WEB-INF/lib/mevoco*.jar',
    'apache-tomcat/webapps/zstack/WEB-INF/classes/license/ca.pem',
    'apache-tomcat/webapps/zstack/WEB-INF/classes/springConfigXml/license.xml',
    'apache-tomcat/webapps/zstack/WEB-INF/classes/springConfigXml/licenseServer.xml',
    'apache-tomcat/webapps/zstack/WEB-INF/classes/serviceConfig/license.xml',
    'zstack-integrity/zstack-integrity-verifier',
]

# Detached signature lives next to the manifest.
SIGNATURE_SUFFIX = '.sig'

_DIGEST_CHUNK = 1024 * 1024


def sha256_of_file(path):
    digest = hashlib.sha256()
    with open(path, 'rb') as fd:
        for chunk in iter(lambda: fd.read(_DIGEST_CHUNK), b''):
            digest.update(chunk)
    return digest.hexdigest()


def collect_files(root, rel_paths):
    """Build the file entry list for rel_paths under root.

    Missing paths are returned with sha256 None so the manifest records that the file
    was expected; the generator decides whether a missing critical file is fatal.
    """
    entries = []
    for rel in rel_paths:
        abs_path = os.path.join(root, rel)
        if os.path.isfile(abs_path):
            entries.append({
                'path': rel,
                'size': os.path.getsize(abs_path),
                'sha256': sha256_of_file(abs_path),
            })
        else:
            entries.append({'path': rel, 'size': None, 'sha256': None})
    return entries


def expand_globs(root, globs):
    """Resolve glob patterns (relative to root) to a sorted, de-duplicated list of
    relative file paths.
    """
    found = set()
    for pattern in globs:
        for abs_path in globmod.glob(os.path.join(root, pattern)):
            if os.path.isfile(abs_path):
                found.add(os.path.relpath(abs_path, root))
    return sorted(found)


def build_manifest(meta, files):
    """meta: dict with product/version/release/arch/build_time/git_commit/key_id.
    files: list from collect_files().
    """
    manifest = {
        'schema_version': SCHEMA_VERSION,
        'sig_algo': 'RSA-SHA256',
    }
    manifest.update(meta)
    manifest['files'] = files
    return manifest


def serialize_manifest(manifest):
    """Deterministic bytes. The detached signature is computed over exactly these bytes,
    and the native helper verifies the signature against the on-disk file bytes, so the
    serialization here and the file written by write_manifest must be identical.
    """
    return (json.dumps(manifest, sort_keys=True, separators=(',', ':'), ensure_ascii=True)
            + '\n').encode('utf-8')


def write_manifest(manifest, manifest_path):
    data = serialize_manifest(manifest)
    with open(manifest_path, 'wb') as fd:
        fd.write(data)
    return data


def write_signature(manifest_path, private_key_path):
    """Sign the manifest file bytes with the release private key. Intended for the
    controlled build/signing environment only (the private key never ships).
    """
    signature_path = manifest_path + SIGNATURE_SUFFIX
    subprocess.check_call([
        'openssl', 'dgst', '-sha256', '-sign', private_key_path,
        '-out', signature_path, manifest_path,
    ])
    return signature_path


def verify_file_hashes(root, manifest):
    """Fallback hash-only verification (no signature trust).

    Returns a list of {'path', 'reason'} for every critical file that is missing or whose
    content does not match the manifest. An empty list means every recorded file matched.
    """
    failures = []
    for entry in manifest.get('files', []):
        rel = entry.get('path')
        expected = entry.get('sha256')
        if expected is None:
            continue
        abs_path = os.path.join(root, rel)
        if not os.path.isfile(abs_path):
            failures.append({'path': rel, 'reason': 'missing'})
            continue
        if sha256_of_file(abs_path) != expected:
            failures.append({'path': rel, 'reason': 'sha256 mismatch'})
    return failures


def load_manifest(manifest_path):
    with open(manifest_path, 'rb') as fd:
        return json.loads(fd.read().decode('utf-8'))


# Verification status values returned by verify_release_integrity().
STATUS_VERIFIED = 'verified'
STATUS_TAMPERED = 'tampered'
STATUS_SIGNATURE_INVALID = 'signature_invalid'
STATUS_MISSING_MANIFEST = 'missing_manifest'
STATUS_ERROR = 'error'

# Verification modes, in decreasing order of trust.
MODE_NATIVE = 'native'              # authoritative: pinned-fingerprint + signature + hashes
MODE_HASH_ONLY = 'hash_only'        # degraded: file hashes only, signature/anchor unchecked


def _verify_with_helper(helper_path, manifest_path, pubkey_path, root):
    proc = subprocess.Popen([helper_path, '--manifest', manifest_path,
                             '--pubkey', pubkey_path, '--root', root],
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    out, err = proc.communicate()
    out = out.decode('utf-8', 'replace').strip()
    try:
        parsed = json.loads(out)
    except ValueError:
        return {'status': STATUS_ERROR, 'mode': MODE_NATIVE, 'pubkey_anchored': False,
                'failures': [{'path': '', 'reason': (err.decode('utf-8', 'replace').strip()
                                                     or 'integrity verifier produced no parsable output')}]}
    parsed['mode'] = MODE_NATIVE
    return parsed


def verify_release_integrity(install_root, manifest_path, pubkey_path, helper_path):
    """Verify the release manifest, preferring the trust-anchored native helper.

    Returns a dict with 'status', 'mode', 'pubkey_anchored' and 'failures'. A missing
    manifest yields STATUS_MISSING_MANIFEST (callers decide whether that is fatal during
    rollout). When the native helper is unavailable, falls back to a hash-only check and
    reports MODE_HASH_ONLY so callers can treat the result as not fully anchored.
    """
    if not os.path.isfile(manifest_path):
        return {'status': STATUS_MISSING_MANIFEST, 'mode': None,
                'pubkey_anchored': False, 'failures': []}

    if helper_path and os.path.isfile(helper_path) and os.access(helper_path, os.X_OK) \
            and pubkey_path and os.path.isfile(pubkey_path):
        return _verify_with_helper(helper_path, manifest_path, pubkey_path, install_root)

    manifest = load_manifest(manifest_path)
    failures = verify_file_hashes(install_root, manifest)
    return {
        'status': STATUS_TAMPERED if failures else STATUS_VERIFIED,
        'mode': MODE_HASH_ONLY,
        'pubkey_anchored': False,
        'failures': failures,
    }


def format_integrity_report(result):
    status = result.get('status')
    if status == STATUS_MISSING_MANIFEST:
        return 'release manifest not found; skipping manifest integrity verification'
    if status == STATUS_VERIFIED:
        if result.get('mode') == MODE_HASH_ONLY:
            return ('release manifest file hashes verified, but the native integrity '
                    'verifier was unavailable so the signature and public-key anchor were '
                    'not checked (degraded verification)')
        return 'release manifest verified'
    lines = ['release integrity verification failed (%s):' % status]
    for failure in result.get('failures', []):
        path = failure.get('path') or '(manifest)'
        lines.append('  %s -> %s' % (path, failure.get('reason')))
    return '\n'.join(lines)


def generate(root, out_path, meta, globs=None, private_key_path=None):
    """Build (and optionally sign) a release manifest for the tree at root. Intended for
    the build/signing environment.
    """
    rel_paths = expand_globs(root, globs or DEFAULT_CRITICAL_GLOBS)
    manifest = build_manifest(meta, collect_files(root, rel_paths))
    write_manifest(manifest, out_path)
    if private_key_path:
        write_signature(out_path, private_key_path)
    return rel_paths


def main():
    parser = argparse.ArgumentParser(description='generate a signed ZStack release integrity manifest')
    parser.add_argument('--root', required=True, help='install root to scan')
    parser.add_argument('--out', required=True, help='output manifest path')
    parser.add_argument('--key', help='release private key (PEM); when given, a detached signature is written')
    parser.add_argument('--glob', action='append', dest='globs',
                        help='override critical-file glob (repeatable); defaults to the built-in list')
    parser.add_argument('--product', default='ZStack')
    parser.add_argument('--version', required=True)
    parser.add_argument('--release', default='')
    parser.add_argument('--arch', default='')
    parser.add_argument('--build-time', default='', dest='build_time')
    parser.add_argument('--git-commit', default='', dest='git_commit')
    parser.add_argument('--key-id', default='', dest='key_id')
    args = parser.parse_args()

    meta = {
        'product': args.product, 'version': args.version, 'release': args.release,
        'arch': args.arch, 'build_time': args.build_time, 'git_commit': args.git_commit,
        'key_id': args.key_id,
    }
    rel_paths = generate(args.root, args.out, meta, args.globs, args.key)
    print('manifest written to %s covering %d files%s' % (
        args.out, len(rel_paths), ' (signed)' if args.key else ' (UNSIGNED)'))


if __name__ == '__main__':
    main()
