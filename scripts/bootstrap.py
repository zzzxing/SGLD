import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VENV = ROOT / ".venv"


def run(cmd: list[str], allow_fail: bool = False) -> int:
    print("$", " ".join(cmd))
    r = subprocess.run(cmd, cwd=ROOT)
    if r.returncode != 0 and not allow_fail:
        raise SystemExit(r.returncode)
    return r.returncode


def main() -> None:
    if not VENV.exists():
        run([sys.executable, "-m", "venv", str(VENV)])

    py = VENV / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    pip = [str(py), "-m", "pip"]

    run(pip + ["install", "--upgrade", "pip"], allow_fail=True)
    install_rc = run(pip + ["install", "-r", "requirements.txt"], allow_fail=True)

    if install_rc != 0:
        print("[WARN] 依赖安装失败。可设置镜像后重试：")
        print("       Windows: set PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple")
        print("       Linux:   export PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple")
        print("[WARN] 当前环境若无 sqlalchemy/fastapi，将无法初始化或启动服务。")
        return

    run([str(py), "scripts/init_db.py"], allow_fail=True)
    run([str(py), "scripts/seed_demo_data.py"], allow_fail=True)
    print("[OK] Bootstrap completed.")


if __name__ == "__main__":
    main()
