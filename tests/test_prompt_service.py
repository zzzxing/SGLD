from app.services.prompt_service import get_prompt


def test_prompt_exists():
    assert "苏格拉底" in get_prompt("student_system")
