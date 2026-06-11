#!/usr/bin/env python
# encoding: utf-8

import os
import sys
import unittest

curr_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.dirname(os.path.dirname(curr_dir)))

from zstackctl import license_integrity as li

# The exact JVM options ctl.py StartCmd.prepare_setenv() writes by default. They must
# never be flagged, otherwise every management node would refuse to start.
DEFAULT_CATALINA_OPTS = [
    '-Djdk.tls.trustNameService=true',
    '-Djava.net.preferIPv4Stack=true',
    '-Dcom.sun.management.jmxremote=true',
    '-Djava.security.egd=file:/dev/./urandom',
    '-XX:-OmitStackTraceInFastThrow',
    '-XX:MaxMetaspaceSize=512m',
    '-XX:+HeapDumpOnOutOfMemoryError',
    '-XX:HeapDumpPath=/usr/local/zstack/apache-tomcat/logs/heap.hprof',
    '-XX:+UseAltSigs',
    '-Dlog4j2.formatMsgNoLookups=true',
    '-Xms512M',
    '-Xmx12288M',
]

DANGEROUS_ARGS = [
    '-noverify',
    '-Xverify:none',
    '-XX:-UseSplitVerifier',
    '-XX:-BytecodeVerificationLocal',
    '-XX:-BytecodeVerificationRemote',
    '-javaagent:/tmp/agent.jar',
    '-agentlib:foo',
    '-agentpath:/tmp/agent.so',
    '-Xbootclasspath/a:/tmp/evil',
    '-Xbootclasspath/p:/tmp/evil',
    '--patch-module',
    '--patch-module=java.base=/tmp/evil',
    '-Djava.system.class.loader=org.evil.Loader',
]


class LicenseIntegrityTest(unittest.TestCase):

    def test_each_dangerous_arg_detected(self):
        for arg in DANGEROUS_ARGS:
            findings = li.find_dangerous_jvm_args(arg)
            self.assertTrue(findings, 'expected %s to be flagged' % arg)
            self.assertEqual(findings[0]['arg'], arg)
            self.assertTrue(findings[0]['reason'])

    def test_default_opts_not_flagged(self):
        # both list and string form
        self.assertEqual(li.find_dangerous_jvm_args(DEFAULT_CATALINA_OPTS), [])
        self.assertEqual(li.find_dangerous_jvm_args(' '.join(DEFAULT_CATALINA_OPTS)), [])

    def test_safe_lookalikes_not_flagged(self):
        # -Xverify:all / :remote enable verification; only :none is dangerous.
        # -XX:-OmitStackTraceInFastThrow shares the "-XX:-" shape but is unrelated.
        for safe in ['-Xverify:all', '-Xverify:remote', '-XX:-OmitStackTraceInFastThrow',
                     '-Xmx8192M', '-XX:+UseG1GC', '-Dcom.sun.management.jmxremote.port=7091']:
            self.assertEqual(li.find_dangerous_jvm_args(safe), [], 'false positive on %s' % safe)

    def test_dangerous_mixed_with_safe_in_string(self):
        opts = '-Xmx8192M -javaagent:/tmp/a.jar -XX:+UseG1GC'
        findings = li.find_dangerous_jvm_args(opts)
        self.assertEqual([f['arg'] for f in findings], ['-javaagent:/tmp/a.jar'])

    def test_scan_detects_each_jvm_opt_env_var(self):
        # F3: JAVA_TOOL_OPTIONS / _JAVA_OPTIONS / JDK_JAVA_OPTIONS bypass setenv.sh.
        for var in li.JVM_OPT_ENV_VARS:
            result = li.scan_jvm_arg_sources(
                {'CATALINA_OPTS (setenv.sh)': ' '.join(DEFAULT_CATALINA_OPTS)},
                {var: '-noverify'})
            label = 'environment variable %s' % var
            self.assertIn(label, result)
            self.assertNotIn('CATALINA_OPTS (setenv.sh)', result)

    def test_scan_clean_when_nothing_dangerous(self):
        result = li.scan_jvm_arg_sources(
            {'CATALINA_OPTS (setenv.sh)': ' '.join(DEFAULT_CATALINA_OPTS)},
            {'PATH': '/usr/bin', 'JAVA_TOOL_OPTIONS': '-Dfoo=bar'})
        self.assertEqual(result, {})

    def test_start_node_path_rejects_dangerous_catalina_opts(self):
        # StartCmd calls scan_jvm_arg_sources on the assembled CATALINA_OPTS; a non-empty
        # result is what makes start_node (and restart_node, which reuses it) raise.
        opts = DEFAULT_CATALINA_OPTS + ['-XX:-UseSplitVerifier']
        result = li.scan_jvm_arg_sources({'CATALINA_OPTS (setenv.sh)': opts}, {})
        self.assertIn('CATALINA_OPTS (setenv.sh)', result)

    def test_setenv_guards_only_jvm_opt_keys(self):
        # guarded key + dangerous value -> rejected
        self.assertTrue(li.check_setenv_assignment('CATALINA_OPTS', '-Xmx8G -noverify'))
        for var in li.JVM_OPT_ENV_VARS:
            self.assertTrue(li.check_setenv_assignment(var, '-javaagent:/x.jar'))
        # guarded key + legit value -> allowed
        self.assertEqual(li.check_setenv_assignment('CATALINA_OPTS', '-Xmx8192M'), [])
        # non-guarded key -> never inspected, always allowed
        self.assertEqual(li.check_setenv_assignment('ZSTACK_HOME', '-noverify'), [])

    def test_report_lists_offending_arg(self):
        result = li.scan_jvm_arg_sources({'CATALINA_OPTS (setenv.sh)': '-noverify'}, {})
        report = li.format_jvm_scan_report(result)
        self.assertIn('-noverify', report)
        self.assertIn('CATALINA_OPTS (setenv.sh)', report)


if __name__ == '__main__':
    unittest.main()
