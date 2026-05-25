import re

from zstacklib.utils import shell

_ebtablesUseLock = None
_SAFE_NAME_RE = re.compile(r'^[A-Za-z0-9_.-]+$')
_SAFE_RULE_RE = re.compile(r'^[A-Za-z0-9_. -]+$')

def get_ebtables_cmd():

    def checkEbtablesLock():
        global _ebtablesUseLock
        if shell.run("ebtables --concurrent -L > /dev/null") == 0:
            _ebtablesUseLock = True
        else:
            _ebtablesUseLock = False

    if _ebtablesUseLock is None:
        checkEbtablesLock()

    if _ebtablesUseLock:
        return "ebtables --concurrent"
    return "ebtables"


def validate_name(name, kind='ebtables name'):
    if not name or _SAFE_NAME_RE.match(name) is None:
        raise Exception('invalid %s[%s]' % (kind, name))
    return name


def has_table_chain_rule(table, chain, rule):
    table = validate_name(table, 'ebtables table')
    chain = validate_name(chain, 'ebtables chain')
    if not rule or _SAFE_RULE_RE.match(rule) is None:
        raise Exception('invalid ebtables rule[%s]' % rule)
    return shell.run(get_ebtables_cmd() + " -t %s -L %s | grep -F -- '%s' > /dev/null" % (table, chain, rule)) == 0


def has_nat_prerouting_rule(rule):
    return has_table_chain_rule('nat', 'PREROUTING', rule)
