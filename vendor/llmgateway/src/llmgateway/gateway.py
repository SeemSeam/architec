from __future__ import annotations

from .service import LLMService
from .spec import CallResult, JSONResult, RuntimeSpec, TaskRequest


class Gateway:
    def __init__(self, runtime: RuntimeSpec):
        self.runtime = runtime
        self.service = LLMService(runtime)

    async def run_task(self, task: str, messages: list[dict[str, str]]) -> str:
        return await self.service.generate_text(
            TaskRequest(task=task, messages=list(messages))
        )

    async def run_task_with_retry(
        self,
        task: str,
        messages: list[dict[str, str]],
        validator=None,
    ) -> tuple[str, list[str]]:
        return await self.service.generate_text_with_retry(
            TaskRequest(task=task, messages=list(messages)),
            validator=validator,
        )

    async def run_json_task(self, task: str, messages: list[dict[str, str]]) -> JSONResult:
        text = await self.run_task(task, messages)
        return JSONResult(task=task, text=text, data=_parse_json_text(text), errors=[])

    async def run_json_task_with_retry(
        self,
        task: str,
        messages: list[dict[str, str]],
        validator=None,
    ) -> JSONResult:
        text, errors = await self.run_task_with_retry(task, messages, validator=validator)
        return JSONResult(task=task, text=text, data=_parse_json_text(text), errors=list(errors))

    async def run_tasks(self, requests: list[TaskRequest]) -> list[CallResult]:
        return await self.service.run_many(requests)

    async def run_tasks_with_retry(
        self,
        requests: list[TaskRequest],
        validators: list[object] | None = None,
    ) -> list[tuple[str, list[str]]]:
        return await self.service.run_many_with_retry(requests, validators=validators)

    async def run_json_tasks_with_retry(
        self,
        requests: list[TaskRequest],
        validators: list[object] | None = None,
    ) -> list[JSONResult]:
        results = await self.run_tasks_with_retry(requests, validators=validators)
        return [
            JSONResult(
                task=request.task,
                text=text,
                data=_parse_json_text(text),
                errors=list(errors),
            )
            for request, (text, errors) in zip(requests, results)
        ]


def _parse_json_text(text: str) -> dict | list | None:
    from .json import try_parse_json

    data, _error = try_parse_json(text)
    return data


__all__ = ["Gateway"]
