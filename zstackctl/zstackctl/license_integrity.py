#!/usr/bin/env python
# encoding: utf-8

"""
License hardening: startup integrity checks for the ZStack management node.

This module is intentionally dependency-free (standard library only) so it can be
imported by ctl.py and exercised by unit tests without pulling in the heavy ctl.py
runtime dependencies.

Current scope: detection of dangerous JVM options that weaken or disable bytecode
verification or allow runtime code injection. Such options were used in the field to
load a tampered management-node JAR while keeping the product believing the license
was valid.

Signed-manifest and critical JAR / exploded-class hash verification are deliberately
not implemented here yet; they depend on the release trust-anchor design and are wired
in through verify_integrity() once that design lands. See the TODO in that function.
"""

import os
from collections import OrderedDict

# JVM honours these environment variables automatically, regardless of the options
# written into Tomcat's setenv.sh. A startup check that only inspects setenv.sh is
# therefore bypassable by exporting one of these, so they must be scanned too.
JVM_OPT_ENV_VARS = ('JAVA_TOOL_OPTIONS', '_JAVA_OPTIONS', 'JDK_JAVA_OPTIONS')

# zstack-ctl variables whose value ends up as JVM options and must be guarded when
# persisted through "zstack-ctl setenv".
GUARDED_OPT_KEYS = ('CATALINA_OPTS',) + JVM_OPT_ENV_VARS

_EXACT_BAD = {
    '-noverify': 'disables bytecode verification',
    '-Xverify:none': 'disables bytecode verification',
    '-XX:-UseSplitVerifier': 'disables the split bytecode verifier',
    '--patch-module': 'patches or replaces module classes at runtime',
}

_PREFIX_BAD = (
    ('-javaagent:', 'loads a Java agent that can rewrite bytecode at load time'),
    ('-agentlib:', 'loads a native agent'),
    ('-agentpath:', 'loads a native agent'),
    ('-Xbootclasspath', 'overrides the boot classpath'),
    ('--patch-module=', 'patches or replaces module classes at runtime'),
    ('-XX:-BytecodeVerification', 'disables bytecode verification'),
    ('-Djava.system.class.loader=', 'installs a custom system class loader'),
)


def _match(token):
    token = token.strip()
    if not token:
        return None
    if token in _EXACT_BAD:
        return _EXACT_BAD[token]
    for prefix, reason in _PREFIX_BAD:
        if token.startswith(prefix):
            return reason
    return None


def find_dangerous_jvm_args(opts):
    """Return a list of {'arg', 'reason'} for every dangerous option in opts.

    opts may be a whitespace-separated string or an iterable of tokens.
    """
    if opts is None:
        return []
    tokens = opts.split() if isinstance(opts, str) else list(opts)
    findings = []
    for token in tokens:
        reason = _match(token)
        if reason:
            findings.append({'arg': token, 'reason': reason})
    return findings


def check_setenv_assignment(key, value):
    """Return dangerous-arg findings for a "zstack-ctl setenv KEY=VALUE" assignment.

    Returns an empty list when KEY is not a JVM-option carrier, so callers can treat a
    non-empty result as "reject this assignment".
    """
    if key.strip() in GUARDED_OPT_KEYS:
        return find_dangerous_jvm_args(value)
    return []


def scan_jvm_arg_sources(sources, environ=None):
    """Scan multiple option sources plus the JVM option environment variables.

    sources: dict of {source_label: opts(str|iterable)}.
    Returns an OrderedDict of {source_label: findings} containing only the sources
    that actually have dangerous options.
    """
    environ = os.environ if environ is None else environ
    result = OrderedDict()
    for label, opts in sources.items():
        findings = find_dangerous_jvm_args(opts)
        if findings:
            result[label] = findings
    for var in JVM_OPT_ENV_VARS:
        findings = find_dangerous_jvm_args(environ.get(var))
        if findings:
            result['environment variable %s' % var] = findings
    return result


def format_jvm_scan_report(scan_result):
    lines = ['dangerous JVM options detected; refusing to proceed to protect license integrity:']
    for source, findings in scan_result.items():
        lines.append('  in %s:' % source)
        for finding in findings:
            lines.append('    %s -> %s' % (finding['arg'], finding['reason']))
    lines.append("remove these options from setenv.sh, the zstack-ctl ctl-env file, "
                 "and the environment, then retry.")
    return '\n'.join(lines)
