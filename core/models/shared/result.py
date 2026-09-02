from __future__ import annotations

from collections.abc import Callable
from typing import Any, Generic, TypeVar, cast

T = TypeVar("T")
U = TypeVar("U")


class Result(Generic[T]):
    """Generic result container for success/failure flows."""

    __slots__ = ("_error", "_is_success", "_value")

    def __init__(
        self,
        value: T | None = None,
        error: BaseException | None = None,
        *,
        is_success: bool | None = None,
    ) -> None:
        if is_success is None:
            is_success = error is None

        if is_success and error is not None:
            raise ValueError("A successful Result cannot contain an error.")

        if not is_success and error is None:
            raise ValueError("A failed Result must contain an error.")

        self._value = value
        self._error = error
        self._is_success = is_success

    @classmethod
    def ok(cls, value: T) -> Success[T]:
        """Create a successful Result."""
        return Success(value)

    @classmethod
    def fail(cls, error: BaseException | str) -> Failure:
        """Create a failed Result."""
        return Failure(error)

    @property
    def is_success(self) -> bool:
        return self._is_success

    @property
    def is_failure(self) -> bool:
        return not self._is_success

    @property
    def value(self) -> T | None:
        return self._value

    @property
    def error(self) -> BaseException | None:
        return self._error

    def map(self, fn: Callable[[T], U]) -> Result[U]:
        """Apply a transformation to a successful result."""
        if self.is_failure:
            return Failure(self._error or RuntimeError("Unknown error"))

        return Success(fn(cast(T, self._value)))

    def bind(self, fn: Callable[[T], Result[U]]) -> Result[U]:
        """Chain a function returning a Result."""
        if self.is_failure:
            return Failure(self._error or RuntimeError("Unknown error"))

        return fn(cast(T, self._value))

    def unwrap(self) -> T:
        """Return the successful value or raise the stored error."""
        if self.is_failure:
            assert self._error is not None
            raise self._error

        return cast(T, self._value)

    def unwrap_or(self, default: T) -> T:
        """Return the value if successful, otherwise the provided default."""
        if self.is_failure:
            return default

        return cast(T, self._value)

    def unwrap_error(self) -> BaseException:
        """Return the stored error or raise if the result is successful."""
        if self.is_success:
            raise ValueError("Successful Result has no error.")

        assert self._error is not None
        return self._error

    def __bool__(self) -> bool:
        return self.is_success

    def __repr__(self) -> str:
        if self.is_success:
            return f"Success({self._value!r})"

        return f"Failure({self._error!r})"


class Success(Result[T]):
    """Successful Result wrapper."""

    def __init__(self, value: T) -> None:
        super().__init__(value=value, is_success=True)


class Failure(Result[Any]):
    """Failed Result wrapper."""

    def __init__(self, error: BaseException | str) -> None:
        if isinstance(error, str):
            error = RuntimeError(error)

        super().__init__(error=error, is_success=False)
