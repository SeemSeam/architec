from __future__ import annotations

import asyncio
import hashlib
import json

from .config import load_provider_state, write_provider_state
from .runtime import (
    normalize_model_request,
    prefers_anthropic_messages,
    prefers_litellm,
    prefers_openai_chat,
    prefers_openai_responses,
    resolve_temperature,
)
from .spec import CallResult, RuntimeSpec, TaskRequest, Validator
from .transport import (
    anthropic_messages_completion,
    litellm_completion,
    openai_chat_completion,
    openai_responses_completion,
)


class LLMService:
    def __init__(self, runtime: RuntimeSpec):
        self.runtime = runtime
        self._semaphore = asyncio.Semaphore(max(1, int(runtime.max_concurrent)))
        self._sleep = asyncio.sleep
        self._provider_preferences = load_provider_state()
        self._config_provider_key = self._config_provider_preference_key()
        self._preferred_provider_key = self._provider_preferences.get(self._config_provider_key, "")

    def _provider_dict(self, provider_spec=None) -> dict[str, object]:
        provider = provider_spec or self.runtime.provider
        return {
            "provider_type": provider.provider_type,
            "api_style": provider.api_style,
            "base_url": provider.base_url,
            "api_key": provider.api_key,
            "headers": dict(provider.headers),
            "model_map": dict(provider.model_map),
        }

    def _provider_dicts(self) -> list[dict[str, object]]:
        providers = [self._provider_dict(provider) for provider in self.runtime.providers]
        preferred_key = str(self._preferred_provider_key or "").strip()
        if not preferred_key:
            return providers
        preferred: list[dict[str, object]] = []
        others: list[dict[str, object]] = []
        for provider in providers:
            if self._provider_key(provider) == preferred_key and not preferred:
                preferred.append(provider)
                continue
            others.append(provider)
        return preferred + others

    def _provider_key(self, provider: dict[str, object]) -> str:
        payload = json.dumps(provider, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def _config_provider_preference_key(self) -> str:
        providers = [self._provider_dict(provider) for provider in self.runtime.providers]
        payload = json.dumps(providers, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def _remember_provider_success(self, provider: dict[str, object]) -> None:
        provider_key = self._provider_key(provider)
        if provider_key == self._preferred_provider_key:
            return
        self._preferred_provider_key = provider_key
        updated_preferences = dict(self._provider_preferences)
        updated_preferences[self._config_provider_key] = provider_key
        try:
            write_provider_state(updated_preferences)
        except Exception:
            self._provider_preferences = updated_preferences
            return
        self._provider_preferences = updated_preferences

    def _validate_provider(self, provider: dict[str, object]) -> None:
        base_url = str(provider.get("base_url", "") or "").strip()
        if not base_url:
            raise RuntimeError("LLM base_url is not configured.")

    def _timeout_error(
        self,
        *,
        request: TaskRequest,
        provider: dict[str, object],
        normalized_model: str,
        timeout_sec: float,
        request_deadline: float,
    ) -> RuntimeError:
        requested_model = self._requested_model_text(request) or normalized_model
        base_url = str(provider.get("base_url", "") or "").strip()
        max_concurrent = max(1, int(self.runtime.max_concurrent))
        message = (
            f"LLM request timed out for task '{request.task}' after {request_deadline:.1f}s "
            f"(model='{requested_model}', timeout={timeout_sec:.1f}s, "
            f"max_concurrent={max_concurrent}, base_url='{base_url}'). "
            "Consider increasing settings.timeout or lowering settings.max_concurrent."
        )
        return RuntimeError(message)

    def _resolved_request(
        self,
        request: TaskRequest,
        provider: dict[str, object],
    ) -> tuple[str, str, float, int]:
        task = self.runtime.task(request.task)
        requested_tier = str(request.tier or task.tier or "").strip().lower()
        requested_model = self._requested_model_text(request)
        if not requested_model:
            raise RuntimeError(f"No model configured for task '{request.task}'.")

        normalized_model, inferred_reasoning_effort = normalize_model_request(provider, requested_model)
        temperature = resolve_temperature(
            normalized_model,
            task.temperature if request.temperature is None else float(request.temperature),
        )
        reasoning_effort = str(
            request.reasoning_effort
            or task.reasoning_effort
            or self.runtime.reasoning_effort_for_tier(requested_tier)
            or inferred_reasoning_effort
            or ""
        ).strip().lower()
        max_tokens = int(request.max_tokens or task.max_tokens or 4000)
        return normalized_model, reasoning_effort, temperature, max_tokens

    def _requested_model_text(self, request: TaskRequest) -> str:
        task = self.runtime.task(request.task)
        requested_tier = str(request.tier or task.tier or "").strip().lower()
        return str(
            request.model
            or task.model
            or self.runtime.model_for_tier(requested_tier)
            or self.runtime.fallback_model
            or ""
        ).strip()

    async def _complete_once(
        self,
        *,
        provider: dict[str, object],
        model: str,
        messages: list[dict[str, str]],
        timeout: float,
        temperature: float,
        max_tokens: int,
        reasoning_effort: str = "",
    ) -> str:
        if prefers_openai_responses(provider):
            return await openai_responses_completion(
                provider=provider,
                model=model,
                messages=messages,
                max_tokens=max_tokens,
                timeout=timeout,
                temperature=temperature,
                reasoning_effort=reasoning_effort,
            )
        if prefers_openai_chat(provider):
            return await openai_chat_completion(
                provider=provider,
                model=model,
                messages=messages,
                max_tokens=max_tokens,
                timeout=timeout,
                temperature=temperature,
                reasoning_effort=reasoning_effort,
            )
        if prefers_anthropic_messages(provider, model):
            return await anthropic_messages_completion(
                provider=provider,
                model=model,
                messages=messages,
                max_tokens=max_tokens,
                timeout=timeout,
                temperature=temperature,
            )
        if prefers_litellm(provider):
            return await litellm_completion(
                provider=provider,
                model=model,
                messages=messages,
                max_tokens=max_tokens,
                timeout=timeout,
                temperature=temperature,
            )
        return await openai_responses_completion(
            provider=provider,
            model=model,
            messages=messages,
            max_tokens=max_tokens,
            timeout=timeout,
            temperature=temperature,
            reasoning_effort=reasoning_effort,
        )

    def _provider_label(self, provider: dict[str, object], index: int) -> str:
        provider_type = str(provider.get("provider_type", "") or "").strip() or "unknown"
        base_url = str(provider.get("base_url", "") or "").strip() or "<missing>"
        return f"provider #{index} ({provider_type}, {base_url})"

    def _all_providers_failed_error(
        self,
        request: TaskRequest,
        failures: list[str],
    ) -> RuntimeError:
        message = (
            f"LLM request failed for task '{request.task}' across all configured providers:\n"
            + "\n".join(failures)
        )
        return RuntimeError(message)

    async def generate(self, request: TaskRequest) -> CallResult:
        providers = self._provider_dicts()
        if not providers:
            raise RuntimeError("No LLM providers are configured.")
        timeout_sec = float(self.runtime.timeout)
        request_deadline = max(timeout_sec + 5.0, timeout_sec * 1.25)
        transport_retries = max(1, int(self.runtime.transport_retries))
        failures: list[str] = []
        last_error: Exception | None = None

        async with self._semaphore:
            for provider_index, provider in enumerate(providers, start=1):
                try:
                    self._validate_provider(provider)
                    normalized_model, reasoning_effort, temperature, max_tokens = self._resolved_request(
                        request,
                        provider,
                    )
                except Exception as exc:
                    last_error = exc
                    failures.append(f"- {self._provider_label(provider, provider_index)}: {exc}")
                    continue

                for attempt in range(transport_retries):
                    try:
                        text = await asyncio.wait_for(
                            self._complete_once(
                                provider=provider,
                                model=normalized_model,
                                messages=request.messages,
                                timeout=timeout_sec,
                                temperature=temperature,
                                max_tokens=max_tokens,
                                reasoning_effort=reasoning_effort,
                            ),
                            timeout=request_deadline,
                        )
                        if text.strip():
                            self._remember_provider_success(provider)
                            return CallResult(
                                task=request.task,
                                text=text,
                                requested_model=self._requested_model_text(request),
                                normalized_model=normalized_model,
                                reasoning_effort=reasoning_effort,
                                temperature=temperature,
                                max_tokens=max_tokens,
                            )
                        raise RuntimeError(
                            "LLM response text was empty. Check provider api_style/response format."
                        )
                    except asyncio.TimeoutError as exc:
                        last_error = self._timeout_error(
                            request=request,
                            provider=provider,
                            normalized_model=normalized_model,
                            timeout_sec=timeout_sec,
                            request_deadline=request_deadline,
                        )
                    except Exception as exc:
                        last_error = exc

                    if attempt >= transport_retries - 1:
                        failures.append(
                            f"- {self._provider_label(provider, provider_index)}: {last_error}"
                        )
                        break
                    await self._sleep(2 ** attempt + 1)

        if last_error is not None:
            raise self._all_providers_failed_error(request, failures) from last_error
        raise self._all_providers_failed_error(request, failures)

    async def generate_text(self, request: TaskRequest) -> str:
        result = await self.generate(request)
        return result.text

    async def generate_text_with_retry(
        self,
        request: TaskRequest,
        validator: Validator | None = None,
    ) -> tuple[str, list[str]]:
        text = ""
        errors: list[str] = []
        messages = list(request.messages)

        for attempt in range(max(0, int(self.runtime.retry_max)) + 1):
            try:
                text = await self.generate_text(
                    TaskRequest(
                            task=request.task,
                            messages=messages,
                            model=request.model,
                            tier=request.tier,
                            temperature=request.temperature,
                            reasoning_effort=request.reasoning_effort,
                            max_tokens=request.max_tokens,
                        )
                )
            except Exception as exc:
                if attempt >= int(self.runtime.retry_max):
                    raise
                errors = [str(exc)]
                await self._sleep(2 ** attempt + 1)
                continue

            if validator is None:
                return text, []

            errors = validator(text)
            if not errors:
                return text, []

            retry_msg = (
                "Your previous output had the following issues:\n"
                + "\n".join(f"- {error}" for error in errors)
                + "\n\nPlease regenerate the full JSON only."
            )
            if attempt < int(self.runtime.retry_max):
                messages = messages + [
                    {"role": "assistant", "content": text},
                    {"role": "user", "content": retry_msg},
                ]

        return text, errors

    async def run_many(self, requests: list[TaskRequest]) -> list[CallResult]:
        tasks = [asyncio.create_task(self.generate(request)) for request in requests]
        return list(await asyncio.gather(*tasks))

    async def run_many_with_retry(
        self,
        requests: list[TaskRequest],
        validators: list[Validator | None] | None = None,
    ) -> list[tuple[str, list[str]]]:
        validator_items = validators or [None] * len(requests)
        if len(validator_items) != len(requests):
            raise ValueError("validators length must match requests length")
        tasks = [
            asyncio.create_task(self.generate_text_with_retry(request, validator))
            for request, validator in zip(requests, validator_items)
        ]
        return list(await asyncio.gather(*tasks))


__all__ = ["LLMService"]
