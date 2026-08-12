import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
import json
import random
from types import SimpleNamespace
from typing import Any, Literal, Protocol

import httpx


class DeepSeekChatModel(Protocol):
    async def ainvoke(self, messages: list[tuple[str, str]]): ...


DeepSeekTransmissionState = Literal["not_transmitted", "sent", "indeterminate"]


@dataclass(frozen=True)
class DeepSeekCallEvidence:
    transmission_state: DeepSeekTransmissionState
    finish_reason: str | None = None
    model_id: str | None = None
    request_id: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None
    cache_hit_input_tokens: int | None = None
    cache_miss_input_tokens: int | None = None
    reasoning_output_tokens: int | None = None


@dataclass(frozen=True)
class DeepSeekJsonResponse:
    payload: dict
    evidence: DeepSeekCallEvidence


class DeepSeekStructuredOutputError(ValueError):
    def __init__(
        self,
        code: str,
        message: str,
        *,
        evidence: DeepSeekCallEvidence | None = None,
    ):
        super().__init__(message)
        self.code = code
        self.evidence = evidence


class DeepSeekProviderError(RuntimeError):
    def __init__(
        self,
        code: str,
        *,
        retryable: bool,
        evidence: DeepSeekCallEvidence | None = None,
    ):
        super().__init__("DeepSeek workflow is temporarily unavailable.")
        self.code = code
        self.retryable = retryable
        self.evidence = evidence or DeepSeekCallEvidence(
            transmission_state="indeterminate"
        )


class DeepSeekJsonClient:
    def __init__(
        self,
        chat_model: DeepSeekChatModel,
        *,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
        jitter: Callable[[], float] = random.random,
        requested_model_id: str | None = None,
        absolute_timeout: float = 300,
    ):
        self._chat_model = chat_model
        self._sleep = sleep
        self._jitter = jitter
        self._requested_model_id = requested_model_id
        self._absolute_timeout = absolute_timeout

    @property
    def requested_model_id(self) -> str:
        if not self._requested_model_id:
            raise RuntimeError("The Analysis provider model identity is unavailable.")
        return self._requested_model_id

    async def request_json(self, messages: list[tuple[str, str]]) -> dict:
        """Legacy bounded transport recovery used by Resume Creation."""
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

    async def request_json_once(
        self, messages: list[tuple[str, str]]
    ) -> DeepSeekJsonResponse:
        """Perform exactly one provider invocation for Analysis-owned recovery."""
        return await self._request_json_once(
            lambda: self._chat_model.ainvoke(messages)
        )

    def prepare_json_request(self, messages: list[tuple[str, str]]) -> bytes:
        """Render the complete body that the prepared Analysis path will send."""
        render = getattr(self._chat_model, "render_request", None)
        if not callable(render):
            raise RuntimeError(
                "The configured Analysis provider cannot render an exact request."
            )
        rendered = render(messages)
        if not isinstance(rendered, bytes) or not rendered:
            raise RuntimeError("The Analysis provider rendered an invalid request.")
        return rendered

    async def request_json_once_prepared(
        self, rendered_request: bytes
    ) -> DeepSeekJsonResponse:
        """Send exactly the bytes previously measured by spend authorization."""
        invoke = getattr(self._chat_model, "ainvoke_prepared", None)
        if not callable(invoke):
            raise RuntimeError(
                "The configured Analysis provider cannot send a prepared request."
            )
        return await self._request_json_once(lambda: invoke(rendered_request))

    async def _request_json_once(
        self, invoke: Callable[[], Awaitable[Any]]
    ) -> DeepSeekJsonResponse:
        try:
            response = await asyncio.wait_for(
                invoke(),
                timeout=self._absolute_timeout,
            )
        except Exception as error:
            retryable, code = _provider_error(error)
            if isinstance(error, TimeoutError) and not isinstance(
                error, httpx.TimeoutException
            ):
                retryable, code = True, "absolute_deadline_exceeded"
            raise DeepSeekProviderError(
                code,
                retryable=retryable,
                evidence=_error_evidence(error),
            ) from error

        evidence = _response_evidence(response)
        if evidence.finish_reason in {"length", "max_tokens"}:
            raise DeepSeekStructuredOutputError(
                "length_truncated",
                "DeepSeek stopped before completing JSON output.",
                evidence=evidence,
            )
        content = _message_text(response)
        if not content:
            raise DeepSeekStructuredOutputError(
                "empty_content",
                "DeepSeek returned empty JSON content.",
                evidence=evidence,
            )
        try:
            payload = json.loads(content)
        except json.JSONDecodeError as error:
            raise DeepSeekStructuredOutputError(
                "invalid_json",
                "DeepSeek returned invalid JSON.",
                evidence=evidence,
            ) from error
        if not isinstance(payload, dict):
            raise DeepSeekStructuredOutputError(
                "invalid_json_root",
                "DeepSeek JSON must be an object.",
                evidence=evidence,
            )
        return DeepSeekJsonResponse(payload=payload, evidence=evidence)


class _LazyDeepSeekChatModel:
    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        max_tokens: int,
        timeout: float | httpx.Timeout,
        reasoning_effort: Literal["high", "max"] | None,
        thinking: Literal["enabled"] | None,
    ):
        self._api_key = api_key
        self._model = model
        self._max_tokens = max_tokens
        self._timeout = timeout
        self._reasoning_effort = reasoning_effort
        self._thinking = thinking
        self._chat = None
        self.endpoint = "https://api.deepseek.com/v1/chat/completions"

    def _configured_chat(self):
        if self._chat is None:
            from langchain_deepseek import ChatDeepSeek

            options = {
                "api_key": self._api_key,
                "model": self._model,
                "max_tokens": self._max_tokens,
                "timeout": self._timeout,
                "max_retries": 0,
            }
            if self._thinking is None:
                options["temperature"] = 0
            if self._reasoning_effort is not None:
                options["reasoning_effort"] = self._reasoning_effort
            if self._thinking is not None:
                options["streaming"] = False
                options["extra_body"] = {"thinking": {"type": self._thinking}}
            self._chat = ChatDeepSeek(
                **options,
            ).bind(
                response_format={"type": "json_object"},
            )
        return self._chat

    async def ainvoke(self, messages: list[tuple[str, str]]):
        return await self._configured_chat().ainvoke(messages)

    def render_request(self, messages: list[tuple[str, str]]) -> bytes:
        if self._thinking is None or self._reasoning_effort is None:
            raise RuntimeError(
                "Prepared requests are reserved for thinking-enabled Analysis."
            )
        roles = {"human": "user", "ai": "assistant", "system": "system"}
        payload = {
            "model": self._model,
            "messages": [
                {"role": roles.get(role, role), "content": content}
                for role, content in messages
            ],
            "max_tokens": self._max_tokens,
            "response_format": {"type": "json_object"},
            "stream": False,
            "reasoning_effort": self._reasoning_effort,
            "thinking": {"type": self._thinking},
        }
        return json.dumps(
            payload,
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")

    async def ainvoke_prepared(self, rendered_request: bytes):
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.post(
                self.endpoint,
                content=rendered_request,
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                },
            )
        response.raise_for_status()
        document = response.json()
        choices = document.get("choices") if isinstance(document, dict) else None
        choice = choices[0] if isinstance(choices, list) and choices else {}
        message = choice.get("message") if isinstance(choice, dict) else {}
        usage = document.get("usage") if isinstance(document, dict) else {}
        if not isinstance(message, dict):
            message = {}
        if not isinstance(usage, dict):
            usage = {}
        request_id = (
            response.headers.get("x-request-id")
            or response.headers.get("x-ds-request-id")
            or (document.get("id") if isinstance(document, dict) else None)
        )
        return SimpleNamespace(
            content=message.get("content") or "",
            id=request_id,
            response_metadata={
                "finish_reason": choice.get("finish_reason")
                if isinstance(choice, dict)
                else None,
                "model_name": (
                    document.get("model") if isinstance(document, dict) else None
                ),
                "request_id": request_id,
                "token_usage": usage,
            },
            usage_metadata={
                "input_tokens": usage.get("prompt_tokens"),
                "output_tokens": usage.get("completion_tokens"),
                "total_tokens": usage.get("total_tokens"),
                "output_token_details": usage.get("completion_tokens_details")
                or {},
            },
        )


def create_deepseek_json_client(
    *,
    api_key: str,
    model: str,
    max_tokens: int = 3000,
    timeout: float | httpx.Timeout = 30,
    reasoning_effort: Literal["high", "max"] | None = None,
    thinking: Literal["enabled"] | None = None,
    absolute_timeout: float = 300,
) -> DeepSeekJsonClient:
    chat_model = _LazyDeepSeekChatModel(
        api_key=api_key,
        model=model,
        max_tokens=max_tokens,
        timeout=timeout,
        reasoning_effort=reasoning_effort,
        thinking=thinking,
    )
    return DeepSeekJsonClient(
        chat_model,
        requested_model_id=model,
        absolute_timeout=absolute_timeout,
    )


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


def _response_evidence(message: Any) -> DeepSeekCallEvidence:
    metadata = _mapping(getattr(message, "response_metadata", None))
    usage_metadata = _mapping(getattr(message, "usage_metadata", None))
    token_usage = _mapping(metadata.get("token_usage"))
    output_details = _mapping(
        usage_metadata.get("output_token_details")
        or token_usage.get("completion_tokens_details")
    )
    finish_reason = _safe_metadata_text(
        metadata.get("finish_reason") or metadata.get("stop_reason")
    )
    model_id = _safe_metadata_text(
        metadata.get("model_name")
        or metadata.get("model")
        or metadata.get("model_id")
    )
    request_id = _safe_metadata_text(
        metadata.get("request_id")
        or metadata.get("id")
        or getattr(message, "id", None)
    )
    return DeepSeekCallEvidence(
        transmission_state="sent",
        finish_reason=finish_reason,
        model_id=model_id,
        request_id=request_id,
        input_tokens=_safe_token_count(
            _first_defined(
                usage_metadata.get("input_tokens"),
                token_usage.get("prompt_tokens"),
            )
        ),
        output_tokens=_safe_token_count(
            _first_defined(
                usage_metadata.get("output_tokens"),
                token_usage.get("completion_tokens"),
            )
        ),
        total_tokens=_safe_token_count(
            _first_defined(
                usage_metadata.get("total_tokens"),
                token_usage.get("total_tokens"),
            )
        ),
        cache_hit_input_tokens=_safe_token_count(
            token_usage.get("prompt_cache_hit_tokens")
        ),
        cache_miss_input_tokens=_safe_token_count(
            token_usage.get("prompt_cache_miss_tokens")
        ),
        reasoning_output_tokens=_safe_token_count(
            _first_defined(
                output_details.get("reasoning"),
                output_details.get("reasoning_tokens"),
            )
        ),
    )


def _error_evidence(error: Exception) -> DeepSeekCallEvidence:
    if isinstance(error, (httpx.ConnectTimeout, httpx.ConnectError)):
        transmission_state: DeepSeekTransmissionState = "not_transmitted"
    else:
        response = getattr(error, "response", None)
        status_code = getattr(response, "status_code", None) or getattr(
            error, "status_code", None
        )
        transmission_state = "sent" if status_code is not None else "indeterminate"
    response = getattr(error, "response", None)
    headers = getattr(response, "headers", {}) if response is not None else {}
    request_id = None
    if hasattr(headers, "get"):
        request_id = headers.get("x-request-id") or headers.get("x-ds-request-id")
    return DeepSeekCallEvidence(
        transmission_state=transmission_state,
        request_id=_safe_metadata_text(request_id),
    )


def _mapping(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    model_dump = getattr(value, "model_dump", None)
    if callable(model_dump):
        dumped = model_dump()
        return dumped if isinstance(dumped, dict) else {}
    return {}


def _safe_token_count(value: Any) -> int | None:
    return value if type(value) is int and value >= 0 else None


def _first_defined(*values: Any) -> Any:
    return next((value for value in values if value is not None), None)


def _safe_metadata_text(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = " ".join(value.split()).strip()
    return normalized[:200] or None


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
    if status == 402:
        return False, "balance_insufficient"
    if isinstance(status, int) and 400 <= status < 500:
        return False, "invalid_request"
    return False, "provider_error"
