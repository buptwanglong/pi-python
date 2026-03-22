# No `Any` Type

## Rule

**禁止使用 `typing.Any` 及任何等效的弱类型。**

This project enforces strict typing. The use of `Any` from the `typing` module is **not allowed** in any Python code.

## What Is Prohibited

- `from typing import Any`
- `typing.Any` as a type annotation
- `dict[str, Any]`, `list[Any]`, `Callable[..., Any]`, etc.
- Using `# type: ignore` to bypass type checks related to `Any`

## What To Use Instead

| Instead of | Use |
|---|---|
| `Any` | A concrete type (`str`, `int`, `bool`, etc.) |
| `dict[str, Any]` | A `TypedDict` or Pydantic `BaseModel` |
| `list[Any]` | `list[str]`, `list[int]`, or a generic `list[T]` |
| `Callable[..., Any]` | `Callable[[ParamType], ReturnType]` with explicit signatures |
| Unknown/mixed types | `Union[X, Y]`, `TypeVar`, generics, or `Protocol` |
| JSON-like data | A Pydantic model or `TypedDict` |
| Catch-all container | `object` (if truly any type is valid, prefer `object` over `Any`) |

## Exceptions

If there is a **genuinely unavoidable** case (e.g., wrapping a third-party library with no type stubs), document the reason with a comment:

```python
value: Any  # EXCEPTION: third-party lib `foo` returns untyped data — tracked in #123
```

Such exceptions must be rare and reviewed.
