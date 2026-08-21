"""Environment Variable expressions and exact scoped Secret references.

Run Configuration expressions resolve User, User Group, and Project scopes::

    env:
      LOG_LEVEL: ${{ vars.LOG_LEVEL }}
      HF_TOKEN: ${{ secrets.HF_TOKEN }}
      USER_TOKEN: ${{ user.secrets.USER_TOKEN }}

The application resolver fixes Variable values into Run Snapshot and stores only
scope-qualified SecretReference keys. Secret plaintext is never serialized into
Snapshot, API responses, or logs.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .config_scope import SecretReference
from .enums import EnvValueKind
from .errors import ValidationFailed

_EXPRESSION = re.compile(
    r"^\$\{\{\s*((?:user\.)?(?:vars|secrets))\.([A-Za-z_][A-Za-z0-9_]*)\s*\}\}$"
)
_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

REDACTED = "***"


@dataclass(frozen=True, slots=True)
class EnvValue:
    """Run Configuration value, retaining explicit initiated-user scope."""

    kind: EnvValueKind
    value: str
    user_scope: bool = False

    @property
    def expression(self) -> str:
        """还原为可展示、可复制的原始表达式。"""
        if self.kind is EnvValueKind.LITERAL:
            return self.value
        namespace = "vars" if self.kind is EnvValueKind.VARIABLE else "secrets"
        prefix = "user." if self.user_scope else ""
        return f"${{{{ {prefix}{namespace}.{self.value} }}}}"


def parse_env_value(raw: str) -> EnvValue:
    """Parse literal, standard, and explicit initiated-user references."""
    match = _EXPRESSION.match(raw.strip())
    if match is None:
        return EnvValue(EnvValueKind.LITERAL, raw)
    namespace, name = match.group(1), match.group(2)
    user_scope = namespace.startswith("user.")
    kind = EnvValueKind.VARIABLE if namespace.endswith("vars") else EnvValueKind.SECRET
    return EnvValue(kind, name, user_scope=user_scope)


def parse_env_map(raw: dict[str, str]) -> dict[str, EnvValue]:
    """解析整张环境变量表，并校验变量名合法。"""
    parsed: dict[str, EnvValue] = {}
    for name, value in raw.items():
        if not _NAME.match(name):
            raise ValidationFailed(f"环境变量名 {name!r} 不合法，应匹配 [A-Za-z_][A-Za-z0-9_]*")
        parsed[name] = parse_env_value(value)
    return parsed


@dataclass(frozen=True, slots=True)
class ResolvedEnv:
    """创建 Run 时解析出的环境变量配置，Secret 仅保存 exact reference。"""

    literals: dict[str, str]
    secret_refs: dict[str, SecretReference]

    def snapshot_payload(self) -> dict[str, dict[str, str]]:
        return {
            "literals": dict(self.literals),
            "secret_refs": {name: ref.as_key() for name, ref in self.secret_refs.items()},
        }


def redact(text: str, secret_values: list[str]) -> str:
    """把已知的 Secret 明文从文本中抹掉。

    日志和错误信息写入存储之前都要经过这里。用户程序自己把 Token 打印到
    stdout 时，这是最后一道防线。
    """
    if not text:
        return text
    result = text
    # 先替换长的值，避免短值是长值子串时把长值切碎后漏掉。
    for value in sorted((v for v in secret_values if v), key=len, reverse=True):
        result = result.replace(value, REDACTED)
    return result
