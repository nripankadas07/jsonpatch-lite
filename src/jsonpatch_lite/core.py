"""Core JSON Patch (RFC 6902) implementation."""
from __future__ import annotations

from copy import deepcopy
from typing import Any, Iterable, Mapping, MutableMapping, MutableSequence


class JsonPatchError(ValueError):
    """Raised on any invalid patch document, pointer, or operation result."""


JsonValue = Any
Pointer = list[str]


_VALID_OPS = frozenset({"add", "remove", "replace", "move", "copy", "test"})


def _parse_pointer(pointer: str) -> Pointer:
    """Parse an RFC 6901 JSON Pointer string into a list of unescaped tokens."""
    if not isinstance(pointer, str):
        raise JsonPatchError(f"pointer must be str, got {type(pointer).__name__}")
    if pointer == "":
        return []
    if not pointer.startswith("/"):
        raise JsonPatchError(f"pointer must be empty or start with '/': {pointer!r}")
    return [seg.replace("~1", "/").replace("~0", "~") for seg in pointer[1:].split("/")]


def _array_index(token: str, length: int, *, allow_dash: bool) -> int:
    """Validate and convert a pointer token used as an array index."""
    if allow_dash and token == "-":
        return length
    if not token.lstrip("-").isdigit() or (len(token) > 1 and token.startswith("0")):
        raise JsonPatchError(f"invalid array index {token!r}")
    index = int(token)
    if index < 0 or index >= length:
        raise JsonPatchError(f"array index {token!r} out of range")
    return index


def _get_value(document: JsonValue, tokens: Pointer) -> JsonValue:
    """Resolve a pointer to its referenced value, raising on missing paths."""
    current = document
    for token in tokens:
        if isinstance(current, Mapping):
            if token not in current:
                raise JsonPatchError(f"path not found: key {token!r}")
            current = current[token]
        elif isinstance(current, list):
            current = current[_array_index(token, len(current), allow_dash=False)]
        else:
            raise JsonPatchError(f"cannot traverse into {type(current).__name__}")
    return current


def _navigate_parent(document: JsonValue, tokens: Pointer) -> tuple[JsonValue, str]:
    """Return (parent_container, last_token) so callers can mutate the parent."""
    if not tokens:
        raise JsonPatchError("cannot navigate parent of root pointer")
    return _get_value(document, tokens[:-1]), tokens[-1]


def _add_into(parent: JsonValue, token: str, value: JsonValue) -> None:
    """Insert/replace a value inside a parent container per RFC 6902 'add'."""
    if isinstance(parent, MutableMapping):
        parent[token] = value
        return
    if isinstance(parent, MutableSequence):
        index = _array_index(token, len(parent) + 1, allow_dash=True)
        parent.insert(index, value)
        return
    raise JsonPatchError(f"cannot add into {type(parent).__name__}")


def _remove_from(parent: JsonValue, token: str) -> JsonValue:
    """Remove and return the value identified by token from its parent."""
    if isinstance(parent, MutableMapping):
        if token not in parent:
            raise JsonPatchError(f"path not found: key {token!r}")
        return parent.pop(token)
    if isinstance(parent, MutableSequence):
        return parent.pop(_array_index(token, len(parent), allow_dash=False))
    raise JsonPatchError(f"cannot remove from {type(parent).__name__}")


def _require(op: Mapping[str, Any], field: str) -> Any:
    if field not in op:
        raise JsonPatchError(f"operation missing required field {field!r}: {op}")
    return op[field]


def _op_add(doc: JsonValue, op: Mapping[str, Any]) -> JsonValue:
    tokens = _parse_pointer(_require(op, "path"))
    value = deepcopy(_require(op, "value"))
    if not tokens:
        return value
    parent, token = _navigate_parent(doc, tokens)
    _add_into(parent, token, value)
    return doc


def _op_remove(doc: JsonValue, op: Mapping[str, Any]) -> JsonValue:
    tokens = _parse_pointer(_require(op, "path"))
    if not tokens:
        raise JsonPatchError("cannot remove root document")
    parent, token = _navigate_parent(doc, tokens)
    _remove_from(parent, token)
    return doc


def _op_replace(doc: JsonValue, op: Mapping[str, Any]) -> JsonValue:
    tokens = _parse_pointer(_require(op, "path"))
    value = deepcopy(_require(op, "value"))
    if not tokens:
        return value
    parent, token = _navigate_parent(doc, tokens)
    _remove_from(parent, token)
    _add_into(parent, token, value)
    return doc


def _op_move(doc: JsonValue, op: Mapping[str, Any]) -> JsonValue:
    from_tokens = _parse_pointer(_require(op, "from"))
    path_tokens = _parse_pointer(_require(op, "path"))
    if from_tokens and path_tokens[: len(from_tokens)] == from_tokens and len(path_tokens) > len(from_tokens):
        raise JsonPatchError("cannot move a value into one of its own children")
    if not from_tokens:
        raise JsonPatchError("cannot move root document")
    parent, token = _navigate_parent(doc, from_tokens)
    value = _remove_from(parent, token)
    if not path_tokens:
        return value
    new_parent, new_token = _navigate_parent(doc, path_tokens)
    _add_into(new_parent, new_token, value)
    return doc


def _op_copy(doc: JsonValue, op: Mapping[str, Any]) -> JsonValue:
    from_tokens = _parse_pointer(_require(op, "from"))
    path_tokens = _parse_pointer(_require(op, "path"))
    value = deepcopy(_get_value(doc, from_tokens))
    if not path_tokens:
        return value
    parent, token = _navigate_parent(doc, path_tokens)
    _add_into(parent, token, value)
    return doc


def _op_test(doc: JsonValue, op: Mapping[str, Any]) -> JsonValue:
    tokens = _parse_pointer(_require(op, "path"))
    expected = _require(op, "value")
    actual = _get_value(doc, tokens)
    if actual != expected:
        raise JsonPatchError(f"test failed at {op['path']!r}: {actual!r} != {expected!r}")
    return doc


_DISPATCH = {
    "add": _op_add,
    "remove": _op_remove,
    "replace": _op_replace,
    "move": _op_move,
    "copy": _op_copy,
    "test": _op_test,
}


def apply_patch(document: JsonValue, patch: Iterable[Mapping[str, Any]]) -> JsonValue:
    """Apply an RFC 6902 JSON Patch to a document and return the new value.

    The input ``document`` is never mutated; a deep copy is made up front.
    Operations are applied in order; if any operation fails, ``JsonPatchError``
    is raised and the partially-modified copy is discarded.
    """
    if not isinstance(patch, Iterable) or isinstance(patch, (str, bytes, Mapping)):
        raise JsonPatchError("patch must be an iterable of operation objects")
    working = deepcopy(document)
    for index, op in enumerate(patch):
        if not isinstance(op, Mapping):
            raise JsonPatchError(f"operation {index} is not an object: {op!r}")
        op_name = op.get("op")
        if op_name not in _VALID_OPS:
            raise JsonPatchError(f"operation {index} has invalid op: {op_name!r}")
        working = _DISPATCH[op_name](working, op)
    return working
