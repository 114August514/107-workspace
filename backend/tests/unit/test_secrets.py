"""环境变量表达式、Variable 与 Secret 解析。"""

from __future__ import annotations

import pytest

from workspace107.domain.enums import EnvValueKind
from workspace107.domain.errors import ValidationFailed
from workspace107.domain.secrets import (
    REDACTED,
    parse_env_map,
    parse_env_value,
    redact,
    resolve_env,
)


@pytest.mark.parametrize(
    ("raw", "kind", "value"),
    [
        ("32", EnvValueKind.LITERAL, "32"),
        ("${{ vars.LOG_LEVEL }}", EnvValueKind.VARIABLE, "LOG_LEVEL"),
        ("${{vars.LOG_LEVEL}}", EnvValueKind.VARIABLE, "LOG_LEVEL"),
        ("${{ secrets.HF_TOKEN }}", EnvValueKind.SECRET, "HF_TOKEN"),
    ],
)
def test_解析环境变量表达式(raw: str, kind: EnvValueKind, value: str) -> None:
    parsed = parse_env_value(raw)
    assert parsed.kind is kind
    assert parsed.value == value


def test_表达式可以还原为原始写法() -> None:
    assert parse_env_value("${{ secrets.HF_TOKEN }}").expression == "${{ secrets.HF_TOKEN }}"
    assert parse_env_value("${{ vars.EPOCHS }}").expression == "${{ vars.EPOCHS }}"
    assert parse_env_value("32").expression == "32"


def test_不合法的环境变量名被拒绝() -> None:
    with pytest.raises(ValidationFailed):
        parse_env_map({"3INVALID": "1"})


def test_解析后_variable_变成字面值_secret_只留引用() -> None:
    env = parse_env_map(
        {
            "BATCH_SIZE": "32",
            "LOG_LEVEL": "${{ vars.LOG_LEVEL }}",
            "TOKEN": "${{ secrets.HF_TOKEN }}",
        }
    )
    resolved, problems = resolve_env(
        env,
        variables={"LOG_LEVEL": "INFO"},
        available_secrets={"HF_TOKEN"},
    )

    assert problems == []
    assert resolved.literals == {"BATCH_SIZE": "32", "LOG_LEVEL": "INFO"}
    # GR-304：Secret 只保存引用关系，值不出现在解析结果里。
    assert resolved.secret_refs == {"TOKEN": "HF_TOKEN"}
    assert "TOKEN" not in resolved.literals


def test_引用不存在的_variable_或_secret_会给出问题而不是静默通过() -> None:
    env = parse_env_map({"A": "${{ vars.MISSING }}", "B": "${{ secrets.MISSING }}"})
    resolved, problems = resolve_env(env, variables={}, available_secrets=set())

    assert len(problems) == 2
    assert "MISSING" in problems[0]
    assert resolved.literals == {}
    assert resolved.secret_refs == {}


def test_redact_抹掉已知的_secret_明文() -> None:
    text = "token=abc123 用完了\n再打印一次 abc123"
    assert redact(text, ["abc123"]) == f"token={REDACTED} 用完了\n再打印一次 {REDACTED}"


def test_redact_先替换长值_避免短值把长值切碎() -> None:
    # "abc" 是 "abc123" 的前缀。先替换短值会让长值永远匹配不上。
    assert redact("abc123", ["abc", "abc123"]) == REDACTED


def test_redact_忽略空值() -> None:
    assert redact("原文", ["", None or ""]) == "原文"
