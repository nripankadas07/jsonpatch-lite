"""Test suite for jsonpatch-lite."""
from __future__ import annotations

import pytest

from jsonpatch_lite import JsonPatchError, apply_patch


# ---------------------------------------------------------------------------
# add
# ---------------------------------------------------------------------------


def test_add_object_member_inserts_key():
    doc = {"a": 1}
    out = apply_patch(doc, [{"op": "add", "path": "/b", "value": 2}])
    assert out == {"a": 1, "b": 2}


def test_add_does_not_mutate_original_document():
    doc = {"a": 1}
    apply_patch(doc, [{"op": "add", "path": "/b", "value": 2}])
    assert doc == {"a": 1}


def test_add_to_array_inserts_at_index():
    out = apply_patch([1, 3], [{"op": "add", "path": "/1", "value": 2}])
    assert out == [1, 2, 3]


def test_add_to_array_with_dash_appends():
    out = apply_patch([1, 2], [{"op": "add", "path": "/-", "value": 3}])
    assert out == [1, 2, 3]


def test_add_replaces_root_when_path_is_empty():
    out = apply_patch({"a": 1}, [{"op": "add", "path": "", "value": [1, 2]}])
    assert out == [1, 2]


def test_add_with_escaped_pointer_token():
    doc = {}
    out = apply_patch(doc, [{"op": "add", "path": "/a~1b", "value": 1}])
    assert out == {"a/b": 1}


def test_add_with_tilde_escape():
    out = apply_patch({}, [{"op": "add", "path": "/a~0b", "value": 1}])
    assert out == {"a~b": 1}


def test_add_with_empty_string_key():
    out = apply_patch({}, [{"op": "add", "path": "/", "value": 1}])
    assert out == {"": 1}


# ---------------------------------------------------------------------------
# remove
# ---------------------------------------------------------------------------


def test_remove_object_member():
    out = apply_patch({"a": 1, "b": 2}, [{"op": "remove", "path": "/a"}])
    assert out == {"b": 2}


def test_remove_array_element():
    out = apply_patch([1, 2, 3], [{"op": "remove", "path": "/1"}])
    assert out == [1, 3]


def test_remove_missing_key_raises():
    with pytest.raises(JsonPatchError, match="path not found"):
        apply_patch({"a": 1}, [{"op": "remove", "path": "/missing"}])


def test_remove_root_raises():
    with pytest.raises(JsonPatchError, match="cannot remove root"):
        apply_patch({"a": 1}, [{"op": "remove", "path": ""}])


# ---------------------------------------------------------------------------
# replace
# ---------------------------------------------------------------------------


def test_replace_existing_key():
    out = apply_patch({"a": 1}, [{"op": "replace", "path": "/a", "value": 2}])
    assert out == {"a": 2}


def test_replace_root_returns_new_value():
    out = apply_patch({"a": 1}, [{"op": "replace", "path": "", "value": "hi"}])
    assert out == "hi"


def test_replace_missing_key_raises():
    with pytest.raises(JsonPatchError):
        apply_patch({"a": 1}, [{"op": "replace", "path": "/b", "value": 2}])


# ---------------------------------------------------------------------------
# move
# ---------------------------------------------------------------------------


def test_move_renames_key():
    out = apply_patch(
        {"a": 1}, [{"op": "move", "from": "/a", "path": "/b"}]
    )
    assert out == {"b": 1}


def test_move_into_own_child_raises():
    with pytest.raises(JsonPatchError, match="own children"):
        apply_patch(
            {"a": {"b": 1}}, [{"op": "move", "from": "/a", "path": "/a/c"}]
        )


def test_move_root_raises():
    with pytest.raises(JsonPatchError, match="cannot move root"):
        apply_patch({"a": 1}, [{"op": "move", "from": "", "path": "/b"}])


# ---------------------------------------------------------------------------
# copy
# ---------------------------------------------------------------------------


def test_copy_duplicates_value_independently():
    doc = {"a": [1, 2]}
    out = apply_patch(doc, [{"op": "copy", "from": "/a", "path": "/b"}])
    out["b"].append(3)
    assert out["a"] == [1, 2]
    assert out["b"] == [1, 2, 3]


def test_copy_to_root_returns_value():
    out = apply_patch({"a": 1}, [{"op": "copy", "from": "/a", "path": ""}])
    assert out == 1


# ---------------------------------------------------------------------------
# test
# ---------------------------------------------------------------------------


def test_test_op_passes_when_value_matches():
    out = apply_patch({"a": 1}, [{"op": "test", "path": "/a", "value": 1}])
    assert out == {"a": 1}


def test_test_op_fails_when_value_differs():
    with pytest.raises(JsonPatchError, match="test failed"):
        apply_patch({"a": 1}, [{"op": "test", "path": "/a", "value": 2}])


def test_test_op_supports_nested_pointer():
    doc = {"a": {"b": [1, 2, 3]}}
    out = apply_patch(doc, [{"op": "test", "path": "/a/b/2", "value": 3}])
    assert out == doc


# ---------------------------------------------------------------------------
# Pointer parsing & validation
# ---------------------------------------------------------------------------


def test_invalid_pointer_without_leading_slash_raises():
    with pytest.raises(JsonPatchError, match="must be empty or start with"):
        apply_patch({}, [{"op": "add", "path": "foo", "value": 1}])


def test_pointer_must_be_string():
    with pytest.raises(JsonPatchError):
        apply_patch({}, [{"op": "add", "path": 123, "value": 1}])


def test_array_index_out_of_range_raises():
    with pytest.raises(JsonPatchError, match="out of range"):
        apply_patch([1, 2], [{"op": "remove", "path": "/5"}])


def test_array_index_with_leading_zero_raises():
    with pytest.raises(JsonPatchError, match="invalid array index"):
        apply_patch([1, 2], [{"op": "remove", "path": "/01"}])


# ---------------------------------------------------------------------------
# Patch document validation
# ---------------------------------------------------------------------------


def test_patch_must_be_iterable_not_dict():
    with pytest.raises(JsonPatchError, match="iterable"):
        apply_patch({}, {"op": "add", "path": "/a", "value": 1})  # type: ignore[arg-type]


def test_patch_operation_must_be_object():
    with pytest.raises(JsonPatchError, match="not an object"):
        apply_patch({}, ["nope"])  # type: ignore[list-item]


def test_invalid_op_name_raises():
    with pytest.raises(JsonPatchError, match="invalid op"):
        apply_patch({}, [{"op": "frobnicate", "path": "/a", "value": 1}])


def test_missing_required_field_raises():
    with pytest.raises(JsonPatchError, match="missing required field"):
        apply_patch({}, [{"op": "add", "path": "/a"}])


# ---------------------------------------------------------------------------
# Multiple sequential ops
# ---------------------------------------------------------------------------


def test_multiple_operations_applied_in_order():
    patch = [
        {"op": "add", "path": "/a", "value": 1},
        {"op": "add", "path": "/b", "value": 2},
        {"op": "replace", "path": "/a", "value": 10},
        {"op": "remove", "path": "/b"},
    ]
    assert apply_patch({}, patch) == {"a": 10}


def test_get_value_through_missing_intermediate_key_raises():
    with pytest.raises(JsonPatchError, match="path not found"):
        apply_patch({"a": {}}, [{"op": "test", "path": "/a/b/c", "value": 1}])


def test_get_value_traverse_into_scalar_raises():
    with pytest.raises(JsonPatchError, match="cannot traverse"):
        apply_patch({"a": 5}, [{"op": "test", "path": "/a/b", "value": 1}])


def test_add_into_scalar_parent_raises():
    with pytest.raises(JsonPatchError, match="cannot add into"):
        apply_patch({"a": 5}, [{"op": "add", "path": "/a/b", "value": 1}])


def test_move_root_to_self_via_copy_returns_new_root():
    out = apply_patch([1, 2], [{"op": "copy", "from": "", "path": ""}])
    assert out == [1, 2]


def test_move_value_to_root_returns_value():
    out = apply_patch({"a": [1, 2]}, [{"op": "move", "from": "/a", "path": ""}])
    assert out == [1, 2]


def test_failed_operation_does_not_affect_input():
    doc = {"a": 1}
    with pytest.raises(JsonPatchError):
        apply_patch(
            doc,
            [
                {"op": "add", "path": "/b", "value": 2},
                {"op": "test", "path": "/a", "value": 999},
            ],
        )
    assert doc == {"a": 1}
