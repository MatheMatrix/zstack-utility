import functools
import os
import yaml

# Dual-mode support:
#   CI/VM mode (default): reads /root/.zguest/envconfig.yaml (zguest-injected by ztest)
#   Local mode (ZTEST_LOCAL_MODE=1): uses safe defaults so unit tests run without a VM
_LOCAL_MODE = os.environ.get('ZTEST_LOCAL_MODE') == '1'

if _LOCAL_MODE:
    envFile = os.path.expanduser("~/.zstack-test/env.yaml")
else:
    envFile = "/root/.zguest/envconfig.yaml"

# Try to import real modules; fall back to no-ops for local mode
try:
    from zstacklib.utils import log, jsonobject
    logger = log.get_logger(__name__)
except Exception:
    import logging
    logger = logging.getLogger(__name__)
    jsonobject = None


def init_env():
    if not os.path.exists(envFile):
        return {}
    with open(envFile, "r") as f:
        try:
            env = yaml.load(f.read(), Loader=yaml.FullLoader)
        except Exception:
            env = yaml.load(f.read())
    return env if env else {}


class EnvVariable(object):
    def __init__(self, name, variable_type, default=None, required=False):
        self.name = name
        self.type = variable_type
        self.default = default
        self.required = required
        self._env = None

    @property
    def env(self):
        if self._env is None:
            self._env = init_env()
        return self._env

    def set(self, value):
        self.env[self.name] = value
        with open(envFile, "w") as f:
            f.write(yaml.dump(self.env))

    def value(self):
        v = self.env.get(self.name, None)
        try:
            if v is not None:
                return self.type(v)
            elif v is None and self.required:
                if not _LOCAL_MODE:
                    raise ValueError('the required environment variable[%s] is not defined' % self.name)
                # In local mode, return a safe default instead of crashing
                return self.type(self.default) if self.default is not None else self._safe_default()
            else:
                return self.type(self.default) if self.default is not None else self._safe_default()
        except TypeError as ex:
            if not _LOCAL_MODE:
                raise Exception('environment[%s] is defined as type[%s] but get %s. %s' %
                                (self.name, self.type, type(v), str(ex)))
            return self._safe_default()

    def _safe_default(self):
        """Return a type-appropriate safe default for local mode."""
        if self.type == str:
            return ''
        elif self.type == bool:
            return False
        elif self.type in (int, float):
            return 0
        return None


def env_var(name, the_type, default=None, required=True):
    # type: (str, typing.Type, typing.Any, bool) -> EnvVariable
    return EnvVariable(name=name, variable_type=the_type, default=default, required=required)


# Lazy-evaluated module-level variables via descriptor pattern.
# In VM-internal mode, these read from envconfig.yaml as before.
# In local mode, they return safe defaults without crashing.
class _LazyEnvVar(object):
    """Descriptor that lazily evaluates an EnvVariable on first access."""
    def __init__(self, name, the_type, default=None, required=True):
        self._env_var = env_var(name, the_type, default=default, required=required)
        self._value = None
        self._resolved = False

    def __set_name__(self, owner, name):
        self._attr = name

    def resolve(self):
        if not self._resolved:
            self._value = self._env_var.value()
            self._resolved = True
        return self._value


class _EnvVars(object):
    """Container for lazy environment variables, accessed as module-level names."""
    _vars = {}

    @classmethod
    def register(cls, name, the_type, default=None, required=True):
        lazy = _LazyEnvVar(name, the_type, default=default, required=required)
        cls._vars[name] = lazy
        return lazy

    @classmethod
    def get(cls, name):
        lazy = cls._vars.get(name)
        if lazy is None:
            raise AttributeError("No env var registered: %s" % name)
        return lazy.resolve()


# Register all environment variables (lazy - not evaluated at import time)
_env_vars_registry = {
    'VM_IMAGE_PATH': ('caseImagePath', str),
    'DEFAULT_ETH_INTERFACE_NAME': ('defaultEthName', str),
    'TEST_ROOT': ('testRoot', str),
    'VOLUME_DIR': ('volumePath', str),
    'SNAPSHOT_DIR': ('snapShotPath', str),
    'CASE_PATH': ('casePath', str),
    'ZSTACK_UTILITY_SOURCE_DIR': ('projectSourceDir', str),
    'DRY_RUN': ('dryRun', bool, False, False),
    'TEST_FOR_OUTPUT_DIR': ('outPutDir', str, '/root/ztest-test-for', False),
    'SSH_PRIVATE_KEY': ('privateKey', str),
    'COVERAGE': ('coverage', bool, False, False),
}

_lazy_vars = {}
for _var_name, _spec in _env_vars_registry.items():
    if len(_spec) == 2:
        _lazy_vars[_var_name] = _EnvVars.register(_spec[0], _spec[1])
    elif len(_spec) == 4:
        _lazy_vars[_var_name] = _EnvVars.register(_spec[0], _spec[1], default=_spec[2], required=_spec[3])


# Module-level attribute access: import env; env.VM_IMAGE_PATH
# Uses __getattr__ (Python 3.7+) for lazy resolution
def __getattr__(name):
    if name in _lazy_vars:
        return _lazy_vars[name].resolve()
    raise AttributeError("module %r has no attribute %r" % (__name__, name))


# For backwards compatibility in CI/VM mode, also expose as real attributes
# so `from env import VM_IMAGE_PATH` works inside the VM
if not _LOCAL_MODE:
    VM_IMAGE_PATH = env_var('caseImagePath', str).value()
    DEFAULT_ETH_INTERFACE_NAME = env_var('defaultEthName', str).value()
    TEST_ROOT = env_var('testRoot', str).value()
    VOLUME_DIR = env_var('volumePath', str).value()
    SNAPSHOT_DIR = env_var('snapShotPath', str).value()
    CASE_PATH = env_var('casePath', str).value()
    ZSTACK_UTILITY_SOURCE_DIR = env_var('projectSourceDir', str).value()
    DRY_RUN = env_var('dryRun', bool, default=False, required=False).value()
    TEST_FOR_OUTPUT_DIR = env_var('outPutDir', str, default='/root/ztest-test-for', required=False).value()
    SSH_PRIVATE_KEY = env_var('privateKey', str).value()
    COVERAGE = env_var('coverage', bool, default=False, required=False).value()


def log_env_variables():
    try:
        if jsonobject is not None:
            logger.debug('environment variables: %s' % jsonobject.dumps(os.environ))
        else:
            logger.debug('environment variables: %s' % dict(os.environ))
    except Exception:
        pass


if not _LOCAL_MODE:
    log_env_variables()


def get_test_environment_metadata():
    env = init_env()
    return dict2obj(env.get("self", {}))


def get_private_key():
    env = init_env()
    return env.get("privateKey", "")


def get_vm_metadata(vm_name):
    env = init_env()
    return dict2obj(env.get(vm_name, {}))


class Dict(dict):
    __setattr__ = dict.__setitem__
    __getattr__ = dict.__getitem__


def dict2obj(dictObj):
    if not isinstance(dictObj, dict):
        return dictObj
    d = Dict()
    for k, v in dictObj.items():
        d[k] = dict2obj(v)
    return d


def _write_test_for_info(handlers, case_info):
    cc = case_info.split('::')
    case_name = cc[0]
    func_name = '::'.join(cc[1:])

    if handlers is not None and not isinstance(handlers, list) and not isinstance(handlers, str):
        raise ValueError('handlers of %s must be a non-empty list or a non-empty string' % func_name)

    if not handlers:
        # empty means just skip test for dry-run
        logger.warn('%s has empty handler' % case_info)
        return

    output_dir = os.path.abspath(__getattr__('TEST_FOR_OUTPUT_DIR'))
    if not os.path.isdir(output_dir):
        os.makedirs(output_dir)

    file_path = os.path.join(output_dir, '%s.json' % os.path.basename(case_name).split('.')[0])

    if os.path.isfile(file_path):
        with open(file_path, 'r') as fd:
            data = jsonobject.loads(fd.read())
    else:
        data = jsonobject.from_dict({})

    data.case_path = case_name
    if data.test_for is None:
        data.test_for = []

    data.test_for.append({
        'func': func_name,
        'handlers': handlers if isinstance(handlers, list) else [handlers]
    })

    with open(file_path, 'w+') as fd:
        fd.write(jsonobject.dumps(data))
        logger.debug('write test_for into to: %s' % file_path)


def test_for(handlers):
    def wrap(f):
        @functools.wraps(f)
        def inner(*args, **kwargs):
            dry_run = __getattr__('DRY_RUN') if _LOCAL_MODE else DRY_RUN
            if dry_run:
                _write_test_for_info(handlers, os.environ.get('PYTEST_CURRENT_TEST'))
            else:
                return f(*args, **kwargs)

        return inner

    return wrap
