from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.models import ModelProvider
from app.services.settings_service import get_settings_map


@dataclass
class LLMResponse:
    content: str
    provider: str
    model: str
    debug: str = ""


class LLMProvider:
    def chat(
        self,
        *,
        model: str,
        messages: list[dict],
        timeout: int = 30,
        base_url: str = "",
        api_key: str = "",
        temperature: float = 0.3,
        max_tokens: int = 512,
    ) -> LLMResponse:
        raise NotImplementedError


class MockProvider(LLMProvider):
    def chat(self, *, model: str, messages: list[dict], timeout: int = 30, base_url: str = "", api_key: str = "", temperature: float = 0.3, max_tokens: int = 512) -> LLMResponse:
        user_text = messages[-1].get("content", "") if messages else ""
        return LLMResponse(
            content=f"[Mock追问] 你提到了：{user_text[:80]}。请先回到当前知识点再回答一步。",
            provider="mock",
            model=model,
            debug=f"timeout={timeout},temperature={temperature},max_tokens={max_tokens}",
        )


class OpenAICompatibleProvider(LLMProvider):
    def chat(self, *, model: str, messages: list[dict], timeout: int = 30, base_url: str = "", api_key: str = "", temperature: float = 0.3, max_tokens: int = 512) -> LLMResponse:
        if not api_key:
            content = "[openai_compatible] 未配置有效 API Key，返回演示提示。"
        else:
            content = "[openai_compatible] 已读取配置；演示环境默认不发起外网请求。"
        return LLMResponse(
            content=content,
            provider="openai_compatible",
            model=model,
            debug=f"base_url={base_url},timeout={timeout},temperature={temperature},max_tokens={max_tokens}",
        )


class LLMRouterService:
    def __init__(self) -> None:
        self.providers: dict[str, LLMProvider] = {
            "mock": MockProvider(),
            "openai_compatible": OpenAICompatibleProvider(),
        }

    def choose_provider(self, db: Session) -> ModelProvider | None:
        default = (
            db.query(ModelProvider)
            .filter(ModelProvider.enabled.is_(True), ModelProvider.is_default.is_(True))
            .order_by(ModelProvider.id.asc())
            .first()
        )
        if default:
            return default
        return db.query(ModelProvider).filter(ModelProvider.enabled.is_(True)).order_by(ModelProvider.id.asc()).first()

    def chat_with_db(self, db: Session, messages: list[dict]) -> LLMResponse:
        settings = get_settings_map(db)
        selected = self.choose_provider(db)
        if not selected:
            return self.providers["mock"].chat(
                model="mock-chat",
                messages=messages,
                timeout=int(settings.get("default_timeout_sec", "30")),
                temperature=float(settings.get("default_temperature", "0.3")),
                max_tokens=int(settings.get("default_max_tokens", "512")),
            )

        handler = self.providers.get(selected.provider_name, self.providers["mock"])
        return handler.chat(
            model=selected.model_name,
            messages=messages,
            timeout=selected.timeout_sec,
            base_url=selected.base_url,
            api_key=selected.api_key,
            temperature=float(selected.temperature or settings.get("default_temperature", "0.3")),
            max_tokens=int(selected.max_tokens or settings.get("default_max_tokens", "512")),
        )
