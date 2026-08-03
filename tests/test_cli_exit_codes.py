"""CLI 退出码测试 — 调用真实 main() 返回码"""
import sys, os, subprocess
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_pages_negative_exit_code():
    """--pages -1 必须返回退出码 2"""
    r = subprocess.run(
        [sys.executable, "-c",
         "from main import main; import sys; sys.argv=['main.py','--pages','-1']; sys.exit(main())"],
        capture_output=True, timeout=10
    )
    assert r.returncode == 2


def test_category_pages_negative_exit_code():
    """--category-pages -1 必须返回退出码 2"""
    r = subprocess.run(
        [sys.executable, "-c",
         "from main import main; import sys; sys.argv=['main.py','--category-pages','-1']; sys.exit(main())"],
        capture_output=True, timeout=10
    )
    assert r.returncode == 2


def test_debug_exit_code():
    r = subprocess.run(
        [sys.executable, "-c",
         "from main import main; import sys; sys.argv=['main.py','--debug']; sys.exit(main())"],
        capture_output=True, timeout=10
    )
    assert r.returncode == 0
