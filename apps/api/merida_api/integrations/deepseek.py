import asyncio
from collections.abc import Awaitable, Callable
import json
import random
from typing import Protocol

import httpx


class DeepSeekChatModel(Protocol):
    async def ainvoke(self, messages: list[tuple[str, str]]): ...


class DeepSeekStructuredOutputError(ValueError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


class DeepSeekProviderError(RuntimeError):
    def __init__(self, code: str, *, retryable: bool):
        super().__init__("DeepSeek Application Analysis is temporarily unavailable.")
        self.code = code
        self.retryable = retryable


class DeepSeekJsonClient:
    def __init__(
        self,
        chat_model: DeepSeekChatModel,
        *,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
        jitter: Callable[[], float] = random.random,
    ):
        self._chat_model = chat_model
        self._sleep = sleep
        self._jitter = jitter

    async def request_json(self, messages: list[tuple[str, str]]) -> dict:
        for attempt in range(3):
            try:
                response = await self._chat_model.ainvoke(messages)
                break
            except Exception as error:
                retryable, code = _provider_error(error)
                if not retryable or attempt == 2:
                    raise DeepSeekProviderError(
                        code, retryable=retryable
                    ) from error
                await self._sleep((0.25 * (2**attempt)) + (self._jitter() * 0.1))
        content = _message_text(response)
        if not content:
            raise DeepSeekStructuredOutputError(
                "empty_content", "DeepSeek returned empty JSON content."
            )
        try:
            payload = json.loads(content)
        except json.JSONDecodeError as error:
            raise DeepSeekStructuredOutputError(
                "invalid_json", "DeepSeek returned invalid JSON."
            ) from error
        if not isinstance(payload, dict):
            raise DeepSeekStructuredOutputError(
                "invalid_json_root", "DeepSeek JSON must be an object."
            )
        return payload


class _LazyDeepSeekChatModel:
    def __init__(self, *, api_key: str, model: str):
        self._api_key = api_key
        self._model = model
        self._chat = None

    def _configured_chat(self):
        if self._chat is None:
            from langchain_deepseek import ChatDeepSeek

            self._chat = ChatDeepSeek(
                api_key=self._api_key,
                model=self._model,
                temperature=0,
                max_tokens=3000,
                timeout=30,
                max_retries=0,
            ).bind(
                response_format={"type": "json_object"},
                thinking={"type": "disabled"},
            )
        return self._chat

    async def ainvoke(self, messages: list[tuple[str, str]]):
        return await self._configured_chat().ainvoke(messages)


def create_deepseek_json_client(*, api_key: str, model: str) -> DeepSeekJsonClient:
    return DeepSeekJsonClient(_LazyDeepSeekChatModel(api_key=api_key, model=model))


def _message_text(message) -> str:
    content = getattr(message, "content", "")
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        return "".join(
            str(item.get("text") or "")
            for item in content
            if isinstance(item, dict)
        ).strip()
    return ""


def _provider_error(error: Exception) -> tuple[bool, str]:
    if isinstance(error, (httpx.TimeoutException, httpx.NetworkError)):
        return True, "transport_unavailable"
    status = getattr(error, "status_code", None)
    if status is None:
        response = getattr(error, "response", None)
        status = getattr(response, "status_code", None)
    if status == 429:
        return True, "rate_limited"
    if isinstance(status, int) and status >= 500:
        return True, "provider_unavailable"
    if status in {401, 403}:
        return False, "authentication_failed"
    if isinstance(status, int) and 400 <= status < 500:
        return False, "invalid_request"
    return False, "provider_error"
