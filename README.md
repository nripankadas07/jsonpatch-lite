# jsonpatch-lite

A minimal, dependency-free implementation of [RFC 6902](https://www.rfc-editor.org/rfc/rfc6902)
JSON Patch and [RFC 6901](https://www.rfc-editor.org/rfc/rfc6901) JSON Pointer
for Python 3.10+. Pure functions, immutable inputs, descriptive errors.

## Install

```bash
pip install jsonpatch-lite
```

## Usage

```python
from jsonpatch_lite import apply_patch

document = {"name": "ada", "skills": ["math"]}

patch = [
    {"op": "add", "path": "/skills/-", "value": "logic"},
    {"op": "replace", "path": "/name", "value": "Ada Lovelace"},
    {"op": "test", "path": "/skills/0", "value": "math"},
]

new_doc = apply_patch(document, patch)
# {"name": "Ada Lovelace", "skills": ["math", "logic"]}

# The original document is never mutated:
assert document["name"] == "ada"
```

## API

### `apply_patch(document, patch) -> new_document`

Apply an iterable of RFC-6902 operation objects to ``document`` and return a
deep-copied result. Supported operations:

| op        | required fields           | behavior                                     |
|-----------|---------------------------|----------------------------------------------|
| `add`     | `path`, `value`           | Insert into object or array (`-` = append).  |
| `remove`  | `path`                    | Delete the referenced node.                  |
| `replace` | `path`, `value`           | Overwrite an existing node.                  |
| `move`    | `from`, `path`            | Remove `from` and add at `path`.             |
| `copy`    | `from`, `path`            | Deep-copy the value at `from` to `path`.     |
| `test`    | `path`, `value`           | Assert deep equality; raise on mismatch.     |

If any operation is malformed, references a missing path, or fails its `test`
assertion, `JsonPatchError` is raised and the original input is left unchanged.

### `JsonPatchError`

A `ValueError` subclass raised for every patch failure: invalid pointers,
out-of-range indices, type mismatches, missing required fields, unknown ops,
and failed tests.

## Pointer rules

JSON Pointers follow RFC 6901: the empty string targets the root document,
segments are slash-separated, `~1` decodes to `/`, and `~0` decodes to `~`.
Inside an `add` operation, the array token `-` refers to the position past
the last element (i.e. it appends).

## Non-goals

- **Diff generation.** This library applies patches; it does not produce them.
- **In-place mutation.** All operations work on a deep copy.
- **JSON I/O.** Inputs are native Python objects; bring your own `json.loads`.

## Running tests

```bash
pip install pytest pytest-cov
PYTHONPATH=src pytest --cov=jsonpatch_lite
```

## License

MIT — see `LICENSE`.
