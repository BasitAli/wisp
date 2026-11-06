"""Match-only unit checks for local_router (no Hyprland / wtype side effects)."""
from __future__ import annotations

from .local_router import match, match_builtin


def _eq(got, action: str, arg: str = "", press_enter: bool = False) -> None:
    assert got is not None, f"expected {action!r}, got None"
    assert got.action == action, f"action {got.action!r} != {action!r}"
    assert got.arg == arg, f"arg {got.arg!r} != {arg!r}"
    assert got.press_enter == press_enter, (
        f"press_enter {got.press_enter} != {press_enter}")


def test_builtins() -> None:
    _eq(match_builtin("focus jira"), "focus_title", "jira")
    _eq(match_builtin("switch to outlook"), "focus_title", "outlook")
    _eq(match_builtin("open chrome"), "launch", "browser")
    _eq(match_builtin("open outlook"), "focus_title", "outlook")
    _eq(match_builtin("close"), "close_active")
    _eq(match_builtin("close the window"), "close_active")
    _eq(match_builtin("close spotify"), "close_app", "music")
    _eq(match_builtin("type hello world"), "type", "hello world")
    _eq(match_builtin("type hello and press enter"), "type", "hello", True)
    # Whisper often puts ?/. before the enter cue — must keep press_enter
    _eq(match_builtin("type whatscene? press enter"), "type", "whatscene", True)
    _eq(match_builtin("type hello. press enter"), "type", "hello", True)
    _eq(match_builtin("press enter"), "keys", "Return")
    _eq(match_builtin("approve"), "keys", "Return")
    _eq(match_builtin("deny"), "keys", "n")
    _eq(match_builtin("press escape"), "keys", "Escape")
    _eq(match_builtin("escape"), "keys", "Escape")
    _eq(match_builtin("backspace"), "keys", "BackSpace")
    _eq(match_builtin("control c"), "keys", "ctrl+c")
    _eq(match_builtin("press ctrl c"), "keys", "ctrl+c")
    _eq(match_builtin("clear text"), "keys", "ctrl+a,BackSpace")
    _eq(match_builtin("clear"), "keys", "ctrl+a,BackSpace")
    _eq(match_builtin("undo"), "keys", "ctrl+z")
    _eq(match_builtin("press tab"), "keys", "Tab")
    assert match_builtin("what is the weather") is None


def test_first_clause_stops_compound() -> None:
    _eq(match_builtin("focus jira. open chrome"), "focus_title", "jira")


def test_match_uses_registry_when_present() -> None:
    cmd = match("open jira")
    assert cmd is not None
    assert cmd.action in ("focus_title", "launch")


if __name__ == "__main__":
    test_builtins()
    test_first_clause_stops_compound()
    test_match_uses_registry_when_present()
    print("ok")
