import re
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
CTL_PY = REPO_ROOT / "zstackctl" / "zstackctl" / "ctl.py"
INSTALL_SH = REPO_ROOT / "installation" / "install.sh"


def _iam_service_source():
    ctl_py = CTL_PY.read_text(encoding="utf-8")
    match = re.search(
        r"^class IamService\(ExtraService\):.*?(?=^class MorphService\(ExtraService\):)",
        ctl_py,
        re.MULTILINE | re.DOTALL,
    )

    assert match is not None
    return match.group(0)


def test_iam_service_accepts_patch_release_from_supported_os_family():
    iam_service = _iam_service_source()

    assert "def is_supported_os" in iam_service
    assert 'startswith("%s." % supported_os)' in iam_service
    assert "if not self.is_supported_os(current_os):" in iam_service
    assert "if current_os not in self.SUPPORTED_OS:" not in iam_service


def test_region_manager_installs_java21_on_kylin_sp3_2403():
    install_sh = INSTALL_SH.read_text(encoding="utf-8")
    match = re.search(r'^REGION_MANAGER_OS="([^"]+)"', install_sh, re.MULTILINE)

    assert match is not None
    assert "ky10sp3.2403" in match.group(1).split()
