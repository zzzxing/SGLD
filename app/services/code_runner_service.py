import re
import subprocess
import tempfile
from pathlib import Path

DANGEROUS_IMPORTS = {
    "os",
    "sys",
    "subprocess",
    "socket",
    "shutil",
    "pathlib",
    "ctypes",
    "multiprocessing",
}


class CodeRunResult(dict):
    pass


def validate_python_code(source_code: str) -> tuple[bool, str]:
    if "__import__" in source_code or "open(" in source_code:
        return False, "代码包含受限调用（__import__/open）"

    import_hits = re.findall(r"^\s*(?:from|import)\s+([a-zA-Z0-9_\.]+)", source_code, flags=re.MULTILINE)
    for hit in import_hits:
        root = hit.split(".")[0]
        if root in DANGEROUS_IMPORTS:
            return False, f"检测到危险导入：{root}"
    return True, "ok"


def run_python_code(source_code: str, timeout_sec: int = 3) -> CodeRunResult:
    valid, message = validate_python_code(source_code)
    if not valid:
        return CodeRunResult(status="blocked", stdout="", stderr=message, runtime_ms=0)

    with tempfile.TemporaryDirectory(prefix="sgld_run_") as temp_dir:
        path = Path(temp_dir) / "main.py"
        path.write_text(source_code, encoding="utf-8")

        try:
            proc = subprocess.run(
                ["python", "-I", "-B", str(path)],
                cwd=temp_dir,
                capture_output=True,
                text=True,
                timeout=timeout_sec,
            )
            stdout = proc.stdout[:4000]
            stderr = proc.stderr[:4000]
            status = "success" if proc.returncode == 0 else "error"
            return CodeRunResult(status=status, stdout=stdout, stderr=stderr, runtime_ms=0)
        except subprocess.TimeoutExpired:
            return CodeRunResult(status="timeout", stdout="", stderr="代码运行超时", runtime_ms=timeout_sec * 1000)
