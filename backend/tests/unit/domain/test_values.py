import pytest

from workspace107.domain.errors import InvalidRelativePath
from workspace107.domain.values import relative_posix_path


@pytest.mark.parametrize(
    "value",
    ["/etc/passwd", "../secret", "a/../../b", "a\x00b", "a\\b", "", "."],
)
def test_rejects_unsafe_relative_path(value: str) -> None:
    with pytest.raises(InvalidRelativePath):
        relative_posix_path(value)


def test_normalizes_relative_path() -> None:
    assert str(relative_posix_path("code/./train.py")) == "code/train.py"


def test_preserves_unicode_relative_path() -> None:
    assert str(relative_posix_path("data/结果.json")) == "data/结果.json"
