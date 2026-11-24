import subprocess
import sys

from tests.helpers import REPO_ROOT, add_ioc, opened
from tests.logutil import check, check_true


# ------------------------------------------------------- scripts/init_state_db.py


INIT_SCRIPT = REPO_ROOT / "scripts" / "init_state_db.py"


def run_init_script(*args):
    return subprocess.run(
        [sys.executable, "-I", str(INIT_SCRIPT), *args], capture_output=True, text=True
    )


def test_init_script_creates_the_database_and_creating_it_again_is_harmless(tmp_path):
    """建库脚本: 新路径建库(包括缺的目录);已有的库不改动,退出码仍是 0"""
    db = tmp_path / "new-dir" / "ioc-state.db"
    first = run_init_script(str(db))
    check("第一次的退出码", first.returncode, 0)
    check_true("库建出来了", db.is_file(), first.stderr)
    opened_db = opened(str(db))
    add_ioc(opened_db, "ioca")
    opened_db.close()
    second = run_init_script(str(db))
    check("第二次的退出码", second.returncode, 0)
    check_true("提示已存在", "already exists" in second.stdout, second.stdout)
    again = opened(str(db))
    check("已有的数据没有被动", again.list_iocs(), ["ioca"])
    again.close()


def test_init_script_reports_failures_and_bad_arguments(tmp_path):
    """建库脚本: 建不出来退出码 1 并写 stderr;参数多了退出码 2"""
    blocker = tmp_path / "a-file"
    blocker.write_text("x")
    bad = run_init_script(str(blocker / "ioc-state.db"))
    check("目录建不出来的退出码", bad.returncode, 1)
    check_true("错误写在 stderr", "failed to create" in bad.stderr, bad.stderr)
    usage = run_init_script("a", "b")
    check("参数多了的退出码", usage.returncode, 2)
    check_true("提示用法", "usage" in usage.stderr, usage.stderr)
