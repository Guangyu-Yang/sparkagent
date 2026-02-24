"""Tests for the CodeAct sandbox."""

import pytest

from sparkagent.agent.codeact.sandbox import (
    IMPORT_ALLOWLIST,
    IMPORT_BLOCKLIST,
    _guarded_import,
    build_safe_builtins,
)


class TestGuardedImport:
    def test_allowed_module(self):
        mod = _guarded_import("json")
        assert hasattr(mod, "dumps")

    def test_allowed_submodule(self):
        mod = _guarded_import("urllib.parse")
        assert hasattr(mod, "urlparse")

    def test_blocked_module_os(self):
        with pytest.raises(ImportError, match="not allowed"):
            _guarded_import("os")

    def test_blocked_module_subprocess(self):
        with pytest.raises(ImportError, match="not allowed"):
            _guarded_import("subprocess")

    def test_blocked_module_sys(self):
        with pytest.raises(ImportError, match="not allowed"):
            _guarded_import("sys")

    def test_blocked_submodule_os_path(self):
        with pytest.raises(ImportError, match="not allowed"):
            _guarded_import("os.path")

    def test_unlisted_module_rejected(self):
        with pytest.raises(ImportError, match="not allowed"):
            _guarded_import("requests")

    def test_allowlist_and_blocklist_disjoint(self):
        overlap = IMPORT_ALLOWLIST & IMPORT_BLOCKLIST
        assert not overlap, f"Overlap: {overlap}"


class TestBuildSafeBuiltins:
    def test_print_available(self):
        safe = build_safe_builtins()
        assert "print" in safe

    def test_len_available(self):
        safe = build_safe_builtins()
        assert safe["len"] is len

    def test_open_blocked(self):
        safe = build_safe_builtins()
        assert "open" not in safe

    def test_eval_blocked(self):
        safe = build_safe_builtins()
        assert "eval" not in safe

    def test_exec_blocked(self):
        safe = build_safe_builtins()
        # __import__ should be the guarded version
        assert safe.get("exec") is None
        # but __import__ should be our hook
        assert safe["__import__"] is _guarded_import

    def test_exception_classes_available(self):
        safe = build_safe_builtins()
        assert safe["ValueError"] is ValueError
        assert safe["TypeError"] is TypeError

    def test_guarded_import_is_injected(self):
        safe = build_safe_builtins()
        assert safe["__import__"] is _guarded_import
