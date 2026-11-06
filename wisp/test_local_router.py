"""Match-only unit checks for local_router (no Hyprland / wtype side effects)."""
from __future__ import annotations

from .local_router import (
    LocalCmd, inject_waits, match, match_builtin, plan_sequence_from_clauses,
    split_instructions, wait_class_for_slot,
)


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
    _eq(match_builtin("type whatscene? press enter"), "type", "whatscene", True)
    _eq(match_builtin("type hello. press enter"), "type", "hello", True)
    _eq(match_builtin("press enter"), "keys", "Return")
    _eq(match_builtin("approve"), "keys", "Return")
    _eq(match_builtin("deny"), "keys", "n")
    _eq(match_builtin("press escape"), "keys", "Escape")
    _eq(match_builtin("control c"), "keys", "ctrl+c")
    _eq(match_builtin("clear text"), "keys", "ctrl+a,BackSpace")
    _eq(match_builtin("read the screen"), "read_kitty")
    assert match_builtin("what is the weather") is None


def test_split_keeps_type_enter() -> None:
    parts = split_instructions(
        "open terminal and type cd into nixos-config and press enter")
    assert parts == [
        "open terminal",
        "type cd into nixos-config and press enter",
    ], parts
    # Must not split "type hello and press enter" alone
    assert split_instructions("type hello and press enter") == [
        "type hello and press enter",
    ]


def test_sequence_plan_injects_wait() -> None:
    seq = match("open terminal and type echo hi press enter")
    assert seq is not None
    assert seq.action == "sequence"
    actions = [s.action for s in seq.steps]
    assert actions[0] == "launch"
    assert "wait_window" in actions
    assert actions[-1] == "type"
    assert seq.steps[-1].press_enter is True
    assert wait_class_for_slot("terminal") == "kitty"


def test_inject_waits_no_double() -> None:
    cmds = [
        LocalCmd(action="launch", arg="terminal"),
        LocalCmd(action="wait_window", arg="kitty"),
        LocalCmd(action="type", arg="hi", press_enter=True),
    ]
    out = inject_waits(cmds)
    assert [c.action for c in out] == [
        "launch", "wait_window", "type",
    ]


def test_first_clause_stops_compound() -> None:
    _eq(match_builtin("focus jira. open chrome"), "focus_title", "jira")


def test_match_uses_registry_when_present() -> None:
    cmd = match("open jira")
    assert cmd is not None
    assert cmd.action in ("focus_title", "launch", "sequence")


def test_unmatched_mid_sequence_aborts() -> None:
    seq = plan_sequence_from_clauses([
        "open terminal", "do something weird xyz", "type hi",
    ])
    assert seq is not None
    assert seq.arg.startswith("ABORT") or (
        seq.action == "sequence" and "ABORT" in seq.arg)


if __name__ == "__main__":
    test_builtins()
    test_split_keeps_type_enter()
    test_sequence_plan_injects_wait()
    test_inject_waits_no_double()
    test_first_clause_stops_compound()
    test_match_uses_registry_when_present()
    test_unmatched_mid_sequence_aborts()
    print("ok")
