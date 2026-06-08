from __future__ import annotations

import os
import tarfile
import tempfile
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

import pytest

REMOTE_BASE_DIR = "/tmp/zstack-test"
REMOTE_REPO_NAME = "zstack-utility"


def pytest_addoption(parser):
    parser.addoption(
        "--vm-deploy",
        action="store_true",
        default=False,
        help="Enable VM deployment runner for system tests.",
    )
    parser.addoption(
        "--target",
        action="store",
        default=None,
        help="Target VM address in IP[:port] format (used with --vm-deploy).",
    )


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _build_ssh_host(target: str) -> str:
    if "@" in target:
        return target
    return f"root@{target}"


def _discover_packages(repo_root: Path) -> List[Path]:
    packages = []
    for child in sorted(repo_root.iterdir()):
        if not child.is_dir():
            continue
        if (child / "setup.py").exists() or (child / "setup.cfg").exists():
            packages.append(child)
    return packages


def _tar_filter(tarinfo: tarfile.TarInfo) -> Optional[tarfile.TarInfo]:
    name = tarinfo.name
    excluded_parts = (
        "/.git/",
        "/.pytest_cache/",
        "/__pycache__/",
        "/.venv/",
    )
    for part in excluded_parts:
        if part in name or name.endswith(part.strip("/")):
            return None
    return tarinfo


def _create_repo_tar(repo_root: Path) -> str:
    temp_file = tempfile.NamedTemporaryFile(suffix=".tar.gz", delete=False)
    temp_file.close()
    with tarfile.open(temp_file.name, "w:gz") as tar:
        tar.add(repo_root, arcname=REMOTE_REPO_NAME, filter=_tar_filter)
    return temp_file.name


@pytest.fixture(scope="session")
def vm_connection(request):
    vm_deploy_enabled = request.config.getoption("--vm-deploy", default=False)
    if not vm_deploy_enabled:
        return None

    target = request.config.getoption("--target", default=None)
    if not target:
        raise ValueError("--target is required when --vm-deploy is enabled")

    ssh_host = request.config.getoption("--ssh-host", default=None)
    if not ssh_host:
        request.config.option.ssh_host = _build_ssh_host(target)

    os.environ.setdefault("ZSTACK_VM_TARGET", target)
    return request.getfixturevalue("ssh_client")


@pytest.fixture(scope="session")
def vm_run(vm_connection, ssh_run) -> Optional[Callable[[str], Tuple[int, str, str]]]:
    if vm_connection is None:
        return None
    return ssh_run


@pytest.fixture(scope="session")
def vm_sync(vm_connection, scp_file, vm_run):
    if vm_connection is None:
        return None

    repo_root = _repo_root()
    tar_path = _create_repo_tar(repo_root)
    remote_tar = f"{REMOTE_BASE_DIR}/{REMOTE_REPO_NAME}.tar.gz"
    remote_repo_root = f"{REMOTE_BASE_DIR}/{REMOTE_REPO_NAME}"
    packages = _discover_packages(repo_root)

    try:
        vm_run(f"mkdir -p {REMOTE_BASE_DIR}")
        scp_file(tar_path, remote_tar)
        vm_run(f"tar -xzf {remote_tar} -C {REMOTE_BASE_DIR}")

        install_results = []
        for package in packages:
            remote_pkg = f"{remote_repo_root}/{package.name}"
            exit_code, stdout, stderr = vm_run(
                f"cd {remote_pkg} && pip install -e ."
            )
            install_results.append((str(package), exit_code, stdout, stderr))
            if exit_code != 0:
                raise RuntimeError(
                    f"pip install failed for {package.name}: {stderr.strip()}"
                )

        return {
            "repo_root": str(repo_root),
            "remote_repo_root": remote_repo_root,
            "packages": install_results,
        }
    finally:
        if os.path.exists(tar_path):
            os.unlink(tar_path)


@pytest.fixture(scope="session")
def vm_deploy(vm_connection, vm_run, vm_sync):
    if vm_connection is None:
        return None

    _ = vm_sync
    script_path = (
        f"{REMOTE_BASE_DIR}/{REMOTE_REPO_NAME}/kvmagent/kvmagent/test/"
        "unittest_tools/install_kvm.sh"
    )
    return vm_run(f"bash {script_path}")
