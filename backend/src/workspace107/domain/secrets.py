"""环境变量表达式、Variable 与 Secret 解析。

Run Configuration 使用与 GitHub Actions 类似的表达式引用 Workspace 的
Variable 和 Secret::

    env:
      LOG_LEVEL: ${{ vars.LOG_LEVEL }}
      BATCH_SIZE: "32"
      HF_TOKEN: ${{ secrets.HF_TOKEN }}

创建 Run 时：

    字面值和 Variable -> 解析后固定到 Run Snapshot
    Secret            -> Run Snapshot 只保存引用表达式，执行时由平台注入

对应 GR-012：Run Snapshot、日志和 API 响应都不得出现 Secret 明文。
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .enums import EnvValueKind
from .errors import ValidationFailed

_EXPRESSION = re.compile(r"^\$\{\{\s*(vars|secrets)\.([A-Za-z_][A-Za-z0-9_]*)\s*\}\}$")
_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

REDACTED = "***"


@dataclass(frozen=True, slots=True)
class EnvValue:
    """Run Configuration 中一个环境变量的取值。

    ``kind`` 为 ``literal`` 时 ``value`` 是字面量；
    为 ``variable`` / ``secret`` 时 ``value`` 是被引用的名称。
    """

    kind: EnvValueKind
    value: str

    @property
    def expression(self) -> str:
        """还原为可展示、可复制的原始表达式。"""
        if self.kind is EnvValueKind.LITERAL:
            return self.value
        namespace = "vars" if self.kind is EnvValueKind.VARIABLE else "secrets"
        return f"${{{{ {namespace}.{self.value} }}}}"


def parse_env_value(raw: str) -> EnvValue:
    """把原始字符串解析为 :class:`EnvValue`。"""
    match = _EXPRESSION.match(raw.strip())
    if match is None:
        return EnvValue(EnvValueKind.LITERAL, raw)
    namespace, name = match.group(1), match.group(2)
    kind = EnvValueKind.VARIABLE if namespace == "vars" else EnvValueKind.SECRET
    return EnvValue(kind, name)


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
    """创建 Run 时解析出的环境变量配置。

    ``literals`` 已经是最终值，可以安全写入 Run Snapshot；
    ``secret_refs`` 只保存引用关系，执行时才由平台注入实际值。
    """

    literals: dict[str, str]
    secret_refs: dict[str, str]

    def snapshot_payload(self) -> dict[str, dict[str, str]]:
        return {
            "literals": dict(self.literals),
            "secret_refs": dict(self.secret_refs),
        }


def resolve_env(
    env: dict[str, EnvValue],
    *,
    variables: dict[str, str],
    available_secrets: set[str],
) -> tuple[ResolvedEnv, list[str]]:
    """把环境变量配置解析为可固定进 Run Snapshot 的形式。

    返回解析结果和问题列表。引用了不存在的 Variable 或 Secret 时，
    对应条目不会进入结果，并在问题列表中给出说明（GR-007：引用在使用时重新校验）。
    """
    literals: dict[str, str] = {}
    secret_refs: dict[str, str] = {}
    problems: list[str] = []

    for name, value in env.items():
        match value.kind:
            case EnvValueKind.LITERAL:
                literals[name] = value.value
            case EnvValueKind.VARIABLE:
                if value.value not in variables:
                    problems.append(
                        f"环境变量 {name} 引用的 Workspace Variable {value.value} 不存在"
                    )
                    continue
                literals[name] = variables[value.value]
            case EnvValueKind.SECRET:
                if value.value not in available_secrets:
                    problems.append(f"环境变量 {name} 引用的 Workspace Secret {value.value} 不存在")
                    continue
                secret_refs[name] = value.value

    return ResolvedEnv(literals=literals, secret_refs=secret_refs), problems


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
