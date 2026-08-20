import os
import shlex


def build_npu_smi_link_command(virtualenv_path, source_path="/usr/local/sbin/npu-smi"):
    source = shlex.quote(source_path)
    target = shlex.quote(os.path.join(virtualenv_path, "bin", "npu-smi"))
    return "if [ -x {0} ]; then ln -sf {0} {1}; fi".format(source, target)
