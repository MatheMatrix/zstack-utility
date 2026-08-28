import os
import shlex


GPU_TOOL_PATHS = (
    "/usr/local/sbin/npu-smi",
    "/opt/hyhal/bin/hy-smi",
)

# TODO: Move deployment metadata into the zstacklib GPU registry before adding a third vendor CLI.
def build_gpu_tool_link_command(virtualenv_path, source_path):
    source = shlex.quote(source_path)
    target = shlex.quote(os.path.join(
        virtualenv_path, "bin", os.path.basename(source_path)))
    return "if [ -x {0} ]; then ln -sf {0} {1}; fi".format(source, target)
