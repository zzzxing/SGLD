import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VENV = ROOT / ".venv"


def run(cmd: list[str], allow_fail: bool = False) -> int:
    print("$", " ".join(cmd))
    result = subprocess.run(cmd, cwd=ROOT)
    if result.returncode != 0 and not allow_fail:
        raise SystemExit(result.returncode)
    return result.returncode


def get_venv_python() -> Path:
    return VENV / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def create_venv() -> Path:
    print("[INFO] 创建虚拟环境 .venv")
    run([sys.executable, "-m", "venv", str(VENV)])
    py = get_venv_python()
    if not py.exists():
        print("[ERROR] 虚拟环境创建失败：未找到 python 可执行文件")
        raise SystemExit(1)
    return py


def ensure_pip_available(py: Path) -> None:
    pip_check = run([str(py), "-m", "pip", "--version"], allow_fail=True)
    if pip_check == 0:
        return

    print("[WARN] 检测到虚拟环境 pip 不可用，尝试执行 ensurepip --upgrade 修复")
    ensurepip_rc = run([str(py), "-m", "ensurepip", "--upgrade"], allow_fail=True)
    if ensurepip_rc != 0:
        print("[ERROR] ensurepip 执行失败，尝试重建 .venv")
        if VENV.exists():
            shutil.rmtree(VENV)
        py = create_venv()
        ensurepip_rc = run([str(py), "-m", "ensurepip", "--upgrade"], allow_fail=True)
        if ensurepip_rc != 0:
            print("[ERROR] 仍无法修复 pip。请确认 Python 安装包含 ensurepip。")
            print("        建议重装 Python 3.11 并勾选“Add python.exe to PATH”。")
            raise SystemExit(ensurepip_rc)

    pip_check_after = run([str(py), "-m", "pip", "--version"], allow_fail=True)
    if pip_check_after != 0:
        print("[ERROR] pip 仍不可用，请删除 .venv 后重试：")
        print("        Windows: rmdir /s /q .venv")
        print("        Linux:   rm -rf .venv")
        raise SystemExit(pip_check_after)


def main() -> None:
    py = get_venv_python()
    if not py.exists():
        py = create_venv()

    ensure_pip_available(py)

    run([str(py), "-m", "pip", "install", "--upgrade", "pip"])

    install_rc = run([str(py), "-m", "pip", "install", "-r", "requirements.txt"], allow_fail=True)
    if install_rc != 0:
        print("[ERROR] 依赖安装失败。可设置镜像后重试：")
        print("        Windows: set PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple")
        print("        Linux:   export PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple")
        print("[ERROR] 未完成依赖安装，已停止。")
        raise SystemExit(install_rc)

    run([str(py), "scripts/init_db.py"])
    run([str(py), "scripts/seed_demo_data.py"])
    print("[OK] Bootstrap completed.")


if __name__ == "__main__":
    main()
