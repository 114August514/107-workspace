"""请求标识上下文与日志格式化。

这条线索的用途只有一个：用户报「用不了」的时候，能从他手里的 request_id
一路查到服务端日志。所以两件事必须成立——日志里带得上，值传得对。
"""

from __future__ import annotations

import json
import logging

from workspace107.observability import (
    MAX_REQUEST_ID_LENGTH,
    JsonFormatter,
    RequestIdFilter,
    TextFormatter,
    bind_request_id,
    current_request_id,
    new_request_id,
)


def _record(message: str = "测试", **extra: object) -> logging.LogRecord:
    record = logging.LogRecord(
        name="workspace107.test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg=message,
        args=(),
        exc_info=None,
    )
    for key, value in extra.items():
        setattr(record, key, value)
    RequestIdFilter().filter(record)
    return record


def test_binding_none_generates_request_id() -> None:
    bind_request_id(None)
    assert current_request_id().startswith("req_")


def test_upstream_request_id_is_reused() -> None:
    assert bind_request_id("req_from_gateway") == "req_from_gateway"
    assert current_request_id() == "req_from_gateway"


def test_empty_request_id_generates_new_value() -> None:
    generated = bind_request_id("   ")
    assert generated.startswith("req_")


def test_request_id_is_truncated() -> None:
    """它会进日志，不能让调用方塞任意长度的内容。"""
    bound = bind_request_id("x" * 500)
    assert len(bound) == MAX_REQUEST_ID_LENGTH


def test_generated_request_ids_are_unique() -> None:
    assert new_request_id() != new_request_id()


def test_json_log_includes_request_id_and_business_fields() -> None:
    bind_request_id("req_json")
    payload = json.loads(JsonFormatter().format(_record("提交 Run", run_id="run_1", status=201)))

    assert payload["request_id"] == "req_json"
    assert payload["message"] == "提交 Run"
    assert payload["level"] == "INFO"
    assert payload["run_id"] == "run_1"
    assert payload["status"] == 201


def test_json_log_omits_log_record_internal_fields() -> None:
    """只带业务信息，不要把 pathname、lineno 这些一起倒出来。"""
    bind_request_id("req_clean")
    payload = json.loads(JsonFormatter().format(_record()))

    for noise in ("pathname", "lineno", "levelno", "msg", "args"):
        assert noise not in payload


def test_text_log_prefixes_request_id() -> None:
    bind_request_id("req_text")
    line = TextFormatter().format(_record("出错了"))

    assert "[req_text]" in line
    assert "出错了" in line
