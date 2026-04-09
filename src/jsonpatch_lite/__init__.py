"""jsonpatch-lite — Minimal RFC-6902 JSON Patch implementation.

Public API:
    apply_patch(document, patch)  -> new document (deep-copied)
    JsonPatchError                -> exception type for all patch failures
"""
from .core import JsonPatchError, apply_patch

__all__ = ["JsonPatchError", "apply_patch"]
__version__ = "0.1.0"
