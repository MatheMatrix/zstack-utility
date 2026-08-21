import importlib.util
import os
import pathlib
import subprocess


def _load_gpu_tools():
    path = pathlib.Path(__file__).parents[3] / "kvmagent/ansible/gpu_tools.py"
    spec = importlib.util.spec_from_file_location("kvm_ansible_gpu_tools", str(path))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_gpu_tool_paths_cover_supported_out_of_path_vendor_commands():
    gpu_tools = _load_gpu_tools()

    assert gpu_tools.GPU_TOOL_PATHS == (
        "/usr/local/sbin/npu-smi",
        "/opt/hyhal/bin/hy-smi",
    )


def test_npu_smi_link_command_exposes_executable_in_kvm_virtualenv(tmp_path):
    gpu_tools = _load_gpu_tools()
    source = tmp_path / "usr/local/sbin/npu-smi"
    virtualenv = tmp_path / "virtualenv/kvm"
    source.parent.mkdir(parents=True)
    (virtualenv / "bin").mkdir(parents=True)
    source.write_text("#!/bin/sh\n")
    source.chmod(0o755)

    command = gpu_tools.build_gpu_tool_link_command(
        str(virtualenv), str(source))

    subprocess.check_call(command, shell=True)
    subprocess.check_call(command, shell=True)

    target = virtualenv / "bin/npu-smi"
    assert target.is_symlink()
    assert os.path.realpath(str(target)) == str(source)


def test_npu_smi_link_command_skips_missing_executable(tmp_path):
    gpu_tools = _load_gpu_tools()
    source = tmp_path / "usr/local/sbin/npu-smi"
    virtualenv = tmp_path / "virtualenv/kvm"
    (virtualenv / "bin").mkdir(parents=True)

    command = gpu_tools.build_gpu_tool_link_command(
        str(virtualenv), str(source))

    subprocess.check_call(command, shell=True)

    assert not (virtualenv / "bin/npu-smi").exists()


def test_npu_smi_link_command_skips_non_executable_source(tmp_path):
    gpu_tools = _load_gpu_tools()
    source = tmp_path / "usr/local/sbin/npu-smi"
    virtualenv = tmp_path / "virtualenv/kvm"
    source.parent.mkdir(parents=True)
    (virtualenv / "bin").mkdir(parents=True)
    source.write_text("#!/bin/sh\n")
    source.chmod(0o644)

    command = gpu_tools.build_gpu_tool_link_command(
        str(virtualenv), str(source))

    subprocess.check_call(command, shell=True)

    assert not (virtualenv / "bin/npu-smi").exists()


def test_gpu_tool_link_command_exposes_hy_smi_in_kvm_virtualenv(tmp_path):
    gpu_tools = _load_gpu_tools()
    source = tmp_path / "opt/hyhal/bin/hy-smi"
    virtualenv = tmp_path / "virtualenv/kvm"
    source.parent.mkdir(parents=True)
    (virtualenv / "bin").mkdir(parents=True)
    source.write_text("#!/bin/sh\n")
    source.chmod(0o755)

    command = gpu_tools.build_gpu_tool_link_command(
        str(virtualenv), str(source))

    subprocess.check_call(command, shell=True)
    subprocess.check_call(command, shell=True)

    target = virtualenv / "bin/hy-smi"
    assert target.is_symlink()
    assert os.path.realpath(str(target)) == str(source)
