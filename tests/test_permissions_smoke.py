from pathlib import Path


def test_api_has_role_guard_helper_used():
    api_code = Path("app/routers/api.py").read_text(encoding="utf-8")
    assert "def _require_role" in api_code
    assert api_code.count("_require_role(request") >= 10


def test_web_has_role_guard_helper_used():
    web_code = Path("app/routers/web.py").read_text(encoding="utf-8")
    assert "def require_role_web" in web_code
    assert web_code.count("require_role_web(request") >= 10
