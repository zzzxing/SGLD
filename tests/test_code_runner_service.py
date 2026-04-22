from app.services.code_runner_service import run_python_code, validate_python_code


def test_validate_blocks_dangerous_import():
    ok, message = validate_python_code("import os\nprint('x')")
    assert not ok
    assert "危险导入" in message


def test_run_python_code_success():
    result = run_python_code("print('hello')", timeout_sec=2)
    assert result["status"] == "success"
    assert "hello" in result["stdout"]


def test_run_python_code_timeout():
    result = run_python_code("while True:\n    pass", timeout_sec=1)
    assert result["status"] == "timeout"
