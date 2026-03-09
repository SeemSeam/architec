from __future__ import annotations

from typing import Any


_INFRA_QUERY_TERMS = (
    "gateway",
    "proxy",
    "provider",
    "model",
    "api",
    "transport",
    "protocol",
    "session sync",
    "session",
    "llm call",
    "backend llm",
    "网关",
    "模型",
    "接口",
    "协议",
    "会话同步",
)

_TEST_QUERY_TERMS = (
    "test",
    "tests",
    "pytest",
    "unit test",
    "integration test",
    "用例",
    "测试",
)


def query_targets_infra(text: str) -> bool:
    query = str(text or "").lower()
    return any(term in query for term in _INFRA_QUERY_TERMS)


def query_targets_tests(text: str) -> bool:
    query = str(text or "").lower()
    return any(term in query for term in _TEST_QUERY_TERMS)


def is_infra_component(component: str, descriptor: dict[str, Any] | None = None) -> bool:
    comp = str(component or "").lower()
    if "gateway" in comp:
        return True
    descriptor = descriptor if isinstance(descriptor, dict) else {}
    layer_role = str(descriptor.get("layer_role", "") or "").strip().lower()
    if layer_role == "interface_adapter":
        return True
    summary = str(descriptor.get("responsibility_summary", "") or "").lower()
    return any(
        term in summary
        for term in ("provider", "transport", "protocol", "gateway", "session sync", "api")
    )
