"""Tests for cratekeeper.tidal.auth session path and session loading."""

from __future__ import annotations

from pathlib import Path

import pytest


def test_session_path_respects_xdg(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    """_session_path() should use XDG_CONFIG_HOME when set."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "custom-config"))
    from cratekeeper.tidal.auth import _session_path

    result = _session_path()
    assert result == tmp_path / "custom-config" / "cratekeeper" / "tidal-session.json"


def test_session_path_default(monkeypatch: pytest.MonkeyPatch):
    """_session_path() should fall back to ~/.config when XDG_CONFIG_HOME is unset."""
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
    from cratekeeper.tidal.auth import _session_path

    result = _session_path()
    assert result == Path.home() / ".config" / "cratekeeper" / "tidal-session.json"


def test_get_tidal_session_missing_file(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    """get_tidal_session() should raise FileNotFoundError when no session file exists."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "no-session"))
    from cratekeeper.tidal.auth import get_tidal_session

    with pytest.raises(FileNotFoundError, match="crate tidal-auth"):
        get_tidal_session()
