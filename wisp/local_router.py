"""Local-first voice command router — keyword/phrase match before Jev.

Personal phrases live in ~/.config/wisp/commands.toml (never in the repo).
Built-in patterns cover focus/open/close/type/enter/approve without a file.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from . import config

COMMANDS_FILE = config.CFG_DIR / "commands.toml"

# Enter cue at end of a type utterance. Whisper often inserts "? "/" . "
# before "press enter" — must not require a bare space-only prefix.
_ENTER_TRAIL = re.compile(
    r"(?:[.!?;,]+\s*|\s+)(?:and\s+)?(?:then\s+)?(?:press\s+|hit\s+)?"
    r"enter\s*[.!]?\s*$",
    re.I)
_FOCUS = re.compile(
    r"^\s*(?:please\s+)?(?:focus|switch\s+to|bring(?:\s+up)?|go\s+to|show)\s+"
    r"(?:the\s+|my\s+)?(.+?)\s*$", re.I)
_OPEN = re.compile(
    r"^\s*(?:please\s+)?(?:open|launch|start|pull\s+up)\s+"
    r"(?:the\s+|my\s+|a\s+)?(.+?)\s*$", re.I)
_CLOSE_ACTIVE = re.compile(
    r"^\s*(?:please\s+)?(?:close|quit)"
    r"(?:\s+(?:the\s+)?(?:active\s+)?(?:app|window|one)?)?\s*[.!]?\s*$",
    re.I)
_CLOSE_APP = re.compile(
    r"^\s*(?:please\s+)?(?:close|quit)\s+(?:the\s+)?(.+?)\s*$", re.I)
_TYPE = re.compile(
    r"^\s*(?:please\s+)?(?:type|dictate|type\s+this|write\s+this\s+down)\s+"
    r"[:,.\s—-]*(.+?)\s*$", re.I)
_PRESS = re.compile(
    r"^\s*(?:please\s+)?(?:press|hit|send|do)\s+(?:the\s+)?(.+?)\s*$", re.I)
# Do NOT split on press/hit — "type foo? press enter" must stay one utterance.
_FIRST_CLAUSE = re.compile(
    r"[.!?]\s+(?:open|focus|launch|close|quit|type|switch|clear)\b",
    re.I)

# Spoken phrase → wtype spec (single key, chord, or comma-sequence)
_KEY_PHRASE = {
    "press enter": "Return",
    "hit enter": "Return",
    "enter": "Return",
    "return": "Return",
    "approve": "Return",
    "accept": "Return",
    "allow": "Return",
    "yes": "y",
    "deny": "n",
    "reject": "n",
    "no": "n",
    "escape": "Escape",
    "esc": "Escape",
    "press escape": "Escape",
    "hit escape": "Escape",
    "cancel": "Escape",
    "backspace": "BackSpace",
    "back space": "BackSpace",
    "press backspace": "BackSpace",
    "delete": "Delete",
    "press delete": "Delete",
    "tab": "Tab",
    "press tab": "Tab",
    "space": "space",
    "spacebar": "space",
    "control c": "ctrl+c",
    "ctrl c": "ctrl+c",
    "control see": "ctrl+c",  # STT often hears "see"
    "press control c": "ctrl+c",
    "press ctrl c": "ctrl+c",
    "send control c": "ctrl+c",
    "interrupt": "ctrl+c",
    "copy": "ctrl+c",
    "paste": "ctrl+v",
    "cut": "ctrl+x",
    "undo": "ctrl+z",
    "redo": "ctrl+Shift+z",
    "select all": "ctrl+a",
    "clear": "ctrl+a,BackSpace",
    "clear text": "ctrl+a,BackSpace",
    "clear the text": "ctrl+a,BackSpace",
    "clear field": "ctrl+a,BackSpace",
    "wipe": "ctrl+a,BackSpace",
    "wipe text": "ctrl+a,BackSpace",
    "delete all": "ctrl+a,BackSpace",
    "delete everything": "ctrl+a,BackSpace",
    "select all and delete": "ctrl+a,BackSpace",
    "select all and backspace": "ctrl+a,BackSpace",
    "clear line": "ctrl+u",  # terminal-style
    "delete word": "ctrl+BackSpace",
    "backspace word": "ctrl+BackSpace",
}

_MOD_WORDS = {
    "control": "ctrl", "ctrl": "ctrl",
    "alt": "alt", "option": "alt",
    "shift": "shift",
    "super": "win", "meta": "win", "cmd": "win", "command": "win",
    "win": "win", "windows": "win",
}

_KEY_WORDS = {
    "enter": "Return", "return": "Return",
    "escape": "Escape", "esc": "Escape",
    "backspace": "BackSpace", "back space": "BackSpace",
    "delete": "Delete", "del": "Delete",
    "tab": "Tab",
    "space": "space", "spacebar": "space",
    "up": "Up", "down": "Down", "left": "Left", "right": "Right",
    "home": "Home", "end": "End",
    "page up": "Prior", "page down": "Next",
    "see": "c",  # "control see" → ctrl+c
}

_APP_ALIASES = {
    "browser": "browser", "chrome": "browser", "google chrome": "browser",
    "firefox": "firefox",
    "terminal": "terminal", "kitty": "terminal", "shell": "terminal",
    "files": "files", "file manager": "files", "strata": "files",
    "editor": "vscode", "vscode": "vscode", "zed": "vscode",
    "zeditor": "vscode", "code": "code", "cursor": "cursor",
    "slack": "slack", "spotify": "music", "music": "music",
    "whatsapp": "whatsapp", "zapfast": "whatsapp",
    "settings": "settings", "monitor": "monitor",
}


@dataclass(frozen=True)
class LocalCmd:
    action: str
    arg: str = ""
    press_enter: bool = False
    require_class: str = ""


def _fold(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (s or "").casefold())


def _first_clause(text: str) -> str:
    return _FIRST_CLAUSE.split(text, maxsplit=1)[0].strip()


def _take_enter_trailer(text: str) -> tuple[str, bool]:
    """Strip a trailing enter cue; return (remainder, pressed)."""
    m = _ENTER_TRAIL.search(text or "")
    if not m:
        return text, False
    return (text[: m.start()].rstrip(), True)


def _strip_noise_title(s: str) -> str:
    # Don't strip bare chrome/browser — "open chrome" would become empty.
    s = re.sub(r"\b(window|tab|please|in chrome)\b", " ", s, flags=re.I)
    return re.sub(r"\s+", " ", s).strip().rstrip(".!?")


def load_registry() -> list[dict]:
    path = COMMANDS_FILE
    if not path.is_file():
        return []
    try:
        import tomllib
    except ImportError:
        try:
            import tomli as tomllib  # type: ignore
        except ImportError:
            return []
    try:
        data = tomllib.loads(path.read_text())
    except Exception:
        return []
    cmds = data.get("command") or data.get("commands") or []
    return cmds if isinstance(cmds, list) else []


def match_registry(text: str) -> LocalCmd | None:
    folded = _fold(_first_clause(text))
    if not folded:
        return None
    best: tuple[int, LocalCmd] | None = None
    for entry in load_registry():
        phrases = entry.get("phrases") or []
        action = (entry.get("action") or "").strip()
        if not action or not phrases:
            continue
        for phrase in phrases:
            pf = _fold(phrase)
            if not pf:
                continue
            if folded != pf and not folded.startswith(pf) and pf not in folded:
                continue
            cand = LocalCmd(
                action=action,
                arg=str(entry.get("arg") or ""),
                press_enter=bool(entry.get("press_enter")),
                require_class=str(entry.get("require_class") or ""),
            )
            score = len(pf)
            if best is None or score > best[0]:
                best = (score, cand)
    return best[1] if best else None


def parse_key_spec(spoken: str) -> str | None:
    """Turn 'control c' / 'escape' / 'ctrl+shift+z' into a wtype spec."""
    s = re.sub(r"\s+", " ", (spoken or "").casefold()).strip().rstrip(".!")
    if not s:
        return None
    if s in _KEY_PHRASE:
        return _KEY_PHRASE[s]
    # Already a machine spec (from commands.toml)
    if re.fullmatch(r"[A-Za-z0-9+_,\-]+", spoken.strip()) and \
            any(c in spoken for c in "+,"):
        return spoken.strip()
    # mods + key: "control c", "ctrl+shift+z", "alt f4"
    tokens = re.split(r"[\s+]+", s)
    mods: list[str] = []
    i = 0
    while i < len(tokens) and tokens[i] in _MOD_WORDS:
        mods.append(_MOD_WORDS[tokens[i]])
        i += 1
    if not mods or i >= len(tokens):
        # bare key word / F-key
        if s in _KEY_WORDS:
            return _KEY_WORDS[s]
        if len(tokens) == 1:
            fm = re.fullmatch(r"f(\d{1,2})", tokens[0], re.I)
            if fm:
                return f"F{fm.group(1)}"
            return _KEY_WORDS.get(tokens[0])
        return None
    rest = " ".join(tokens[i:])
    key = _KEY_WORDS.get(rest) or _KEY_WORDS.get(tokens[i])
    if key is None:
        fm = re.fullmatch(r"f(\d{1,2})", tokens[i], re.I)
        if fm:
            key = f"F{fm.group(1)}"
    if key is None and len(tokens[i]) == 1:
        key = tokens[i]
    if key is None and len(rest) == 1:
        key = rest
    if not key:
        return None
    # Canonical chord casing for named keys
    if len(key) > 1:
        key = key[0].upper() + key[1:] if key.islower() else key
        # keep wtype names: BackSpace, Escape, …
        for canon in ("BackSpace", "Escape", "Return", "Delete", "Tab",
                      "Prior", "Next", "Home", "End", "Up", "Down",
                      "Left", "Right"):
            if key.casefold() == canon.casefold():
                key = canon
                break
    # shift in mods → Shift for readability in logs; wtype wants lowercase -M
    return "+".join(mods + [key])


def match_keys(raw: str) -> LocalCmd | None:
    phrase = re.sub(r"\s+", " ", raw.casefold()).strip().rstrip(".!")
    # longest phrase first so "clear text" beats "clear"
    for spoken, spec in sorted(_KEY_PHRASE.items(), key=lambda kv: -len(kv[0])):
        if phrase == spoken or phrase == f"press {spoken}" \
                or phrase == f"hit {spoken}" or phrase == f"send {spoken}":
            return LocalCmd(action="keys", arg=spec)
    m = _PRESS.match(raw)
    if m:
        spec = parse_key_spec(m.group(1))
        if spec:
            return LocalCmd(action="keys", arg=spec)
    # bare chord without "press": "ctrl c", "alt f4"
    spec = parse_key_spec(phrase)
    if spec and ("+" in spec or spec in (
            "Escape", "BackSpace", "Delete", "Tab", "Return", "space")
            or re.fullmatch(r"F\d{1,2}", spec)):
        return LocalCmd(action="keys", arg=spec)
    return None


def match_builtin(text: str) -> LocalCmd | None:
    # Strip enter trailer on the FULL transcript first so
    # "type whatscene? press enter" keeps press_enter (first-clause
    # used to cut at "? press" and drop the cue).
    stripped, enter_cue = _take_enter_trailer((text or "").strip())
    raw = _first_clause(stripped).strip()
    if not raw:
        return None

    # Type (+ optional enter) before bare key matching — otherwise
    # leftover "press enter" after a bad split becomes keys-only.
    m = _TYPE.match(raw)
    if m:
        body = m.group(1).strip()
        if _ENTER_TRAIL.search(body):
            enter_cue = True
            body = _ENTER_TRAIL.sub("", body).strip()
        if body:
            return LocalCmd(action="type", arg=body, press_enter=enter_cue)

    keys = match_keys(raw)
    if keys is not None:
        return keys
    # Whole utterance was just "press enter" (no type prefix)
    if enter_cue and not stripped.strip():
        return LocalCmd(action="keys", arg="Return")
    keys = match_keys((text or "").strip())
    if keys is not None:
        return keys

    if _CLOSE_ACTIVE.match(raw):
        return LocalCmd(action="close_active")

    m = _FOCUS.match(raw)
    if m:
        needle = _strip_noise_title(m.group(1))
        if needle:
            return LocalCmd(action="focus_title", arg=needle)

    m = _OPEN.match(raw)
    if m:
        name = _strip_noise_title(m.group(1))
        if not name:
            return None
        slot = _APP_ALIASES.get(name.casefold())
        if slot:
            return LocalCmd(action="launch", arg=slot)
        return LocalCmd(action="focus_title", arg=name)

    m = _CLOSE_APP.match(raw)
    if m:
        name = _strip_noise_title(m.group(1))
        if name and name.casefold() not in ("active", "app", "window"):
            slot = _APP_ALIASES.get(name.casefold(), name)
            return LocalCmd(action="close_app", arg=slot)

    return None


def match(text: str) -> LocalCmd | None:
    return match_registry(text) or match_builtin(text)


def fallback_dictation(text: str) -> LocalCmd | None:
    """When Jev is off: type the whole transcript (enter trailer honored)."""
    stripped, enter = _take_enter_trailer((text or "").strip())
    body = stripped.strip()
    if not body and enter:
        return LocalCmd(action="keys", arg="Return")
    if not body or "[BLANK" in body.upper():
        return None
    return LocalCmd(action="type", arg=body, press_enter=enter)


def _class_ok(require_class: str) -> bool:
    if not require_class:
        return True
    from . import platform
    live = (platform.active_window().get("class") or "").casefold()
    want = require_class.casefold()
    return live == want or want in live


def _press_one(spec: str, env: dict) -> bool:
    """One chord or key via wtype. spec: Return | y | ctrl+c | ctrl+Shift+z."""
    import subprocess
    spec = (spec or "").strip()
    if not spec:
        return False
    cmd = ["wtype"]
    if "+" in spec and not spec.startswith("+"):
        parts = spec.split("+")
        mods, key = parts[:-1], parts[-1]
        for m in mods:
            cmd.extend(["-M", m.lower()])
        if len(key) == 1:
            cmd.extend(["--", key])
        else:
            cmd.extend(["-k", key])
        for m in reversed(mods):
            cmd.extend(["-m", m.lower()])
    elif len(spec) == 1:
        cmd.extend(["--", spec])
    else:
        cmd.extend(["-k", spec])
    r = subprocess.run(cmd, capture_output=True, env=env)
    return r.returncode == 0


def press_keys(spec: str) -> str:
    """spec: 'Return' | 'ctrl+c' | 'ctrl+a,BackSpace' (comma = sequence)."""
    import shutil
    import subprocess
    import time
    from . import platform
    from .pipeline import hypr_env, type_target_address

    addr = type_target_address()
    if addr:
        platform._try(platform.focus_address_cmds(addr))
        time.sleep(0.12)
    if not shutil.which("wtype"):
        return "SKIP (wtype not installed)"
    spec = (spec or "").strip()
    if not spec:
        return "SKIP (empty keys)"
    env = hypr_env()
    steps = [s.strip() for s in spec.split(",") if s.strip()]
    ok = True
    for i, step in enumerate(steps):
        if not _press_one(step, env):
            ok = False
            break
        if i + 1 < len(steps):
            time.sleep(0.05)
    return f"KEYS {spec}" if ok else "SKIP (wtype failed)"


def run(cmd: LocalCmd, cfg: dict, harness: dict | None = None) -> str:
    from .tools import desktop, system

    if cmd.require_class and not _class_ok(cmd.require_class):
        return (f"SKIP (require_class={cmd.require_class!r}, "
                f"focused elsewhere)")

    if cmd.action == "focus_title":
        return desktop.focus_by_title(cmd.arg)
    if cmd.action == "launch":
        return desktop.launch(cmd.arg, cfg, harness)
    if cmd.action == "close_active":
        return desktop.close("")
    if cmd.action == "close_app":
        cls = desktop.class_for_app(cmd.arg, cfg, harness)
        if not cls:
            titled = desktop.focus_by_title(cmd.arg)
            if titled.startswith("FOCUSED"):
                return desktop.close("")
            return f"SKIP (no window for {cmd.arg!r})"
        return desktop.close(cls)
    if cmd.action == "type":
        out = system.type_text(cmd.arg)
        if cmd.press_enter and out.startswith("TYPED"):
            return f"{out}; {press_keys('Return')}"
        return out
    if cmd.action == "keys":
        return press_keys(cmd.arg)
    return f"SKIP (unknown local action {cmd.action!r})"


def vocab_tokens() -> list[str]:
    out: list[str] = []
    for entry in load_registry():
        for p in entry.get("phrases") or []:
            out.extend(str(p).split())
        if entry.get("arg"):
            out.append(str(entry["arg"]))
    seen: set[str] = set()
    uniq: list[str] = []
    for t in out:
        k = t.casefold()
        if k not in seen and len(t) > 1:
            seen.add(k)
            uniq.append(t)
    return uniq
