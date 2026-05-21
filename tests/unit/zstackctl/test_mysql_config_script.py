import ast
import warnings
from pathlib import Path


def _mysql_db_config_script():
    ctl_py = Path(__file__).resolve().parents[3] / "zstackctl" / "zstackctl" / "ctl.py"
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", SyntaxWarning)
        module = ast.parse(ctl_py.read_text(encoding="utf-8"))

    for node in module.body:
        if not isinstance(node, ast.Assign):
            continue
        if any(isinstance(target, ast.Name) and target.id == "mysql_db_config_script" for target in node.targets):
            return ast.literal_eval(node.value)

    raise AssertionError("mysql_db_config_script not found")


def test_mysql_config_script_keeps_foreign_key_checks_enabled_on_alinux4():
    script = _mysql_db_config_script()

    assert "SET GLOBAL foreign_key_checks=0" not in script
    assert "foreign_key_checks=0 via init-file" not in script
    assert r"grep -E '^[[:space:]]*init-file[[:space:]]*=.*init_fk\.sql'" in script
    assert r"sed -i '\#^[[:space:]]*init-file[[:space:]]*=.*init_fk\.sql#d'" in script
    assert "rm -f /var/lib/zstack/init_fk.sql /var/lib/mysql/init_fk.sql" in script
