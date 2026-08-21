"""纯领域层的环境变量表达式、Variable 与 Secret 解析。"""

from __future__ import annotations

import pytest

from workspace107.domain.enums import EnvValueKind
from workspace107.domain.errors import ValidationFailed
from workspace107.domain.secrets import REDACTED, parse_env_map, parse_env_value, redact


@pytest.mark.parametrize(
    ("raw", "kind", "value"),
    [
        ("32", EnvValueKind.LITERAL, "32"),
        ("${{ vars.LOG_LEVEL }}", EnvValueKind.VARIABLE, "LOG_LEVEL"),
        ("${{vars.LOG_LEVEL}}", EnvValueKind.VARIABLE, "LOG_LEVEL"),
        ("${{ secrets.HF_TOKEN }}", EnvValueKind.SECRET, "HF_TOKEN"),
        ("${{ user.vars.LOG_LEVEL }}", EnvValueKind.VARIABLE, "LOG_LEVEL"),
        ("${{ user.secrets.HF_TOKEN }}", EnvValueKind.SECRET, "HF_TOKEN"),
    ],
)
def test_parses_environment_value_expression(raw: str, kind: EnvValueKind, value: str) -> None:
    parsed = parse_env_value(raw)
    assert parsed.kind is kind
    assert parsed.value == value


def test_expression_round_trips_to_original_form() -> None:
    assert parse_env_value("${{ secrets.HF_TOKEN }}").expression == "${{ secrets.HF_TOKEN }}"
    assert parse_env_value("${{ vars.EPOCHS }}").expression == "${{ vars.EPOCHS }}"
    assert parse_env_value("${{ user.vars.EPOCHS }}").expression == "${{ user.vars.EPOCHS }}"
    assert (
        parse_env_value("${{ user.secrets.HF_TOKEN }}").expression == "${{ user.secrets.HF_TOKEN }}"
    )
    assert parse_env_value("32").expression == "32"


def test_invalid_environment_variable_name_is_rejected() -> None:
    with pytest.raises(ValidationFailed):
        parse_env_map({"3INVALID": "1"})


def test_redact_removes_known_secret_values() -> None:
    text = "token=abc123 用完了\n再打印一次 abc123"
    assert redact(text, ["abc123"]) == f"token={REDACTED} 用完了\n再打印一次 {REDACTED}"


def test_redact_replaces_long_values_before_prefixes() -> None:
    # "abc" 是 "abc123" 的前缀。先替换短值会让长值永远匹配不上。
    assert redact("abc123", ["abc", "abc123"]) == REDACTED


def test_redact_ignores_empty_values() -> None:
    assert redact("原文", ["", None or ""]) == "原文"
