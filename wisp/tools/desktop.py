"""Desktop tools: app launch/focus/close and Hyprland workspace ops."""
import json
import re
import shutil
import subprocess
from pathlib import Path

from .. import config
from ..pipeline import hypr_env

# binary basename -> Hyprland class candidates (first match wins)
_CLASS_ALIASES = {
    "google-chrome-stable": ("google-chrome",),
    "google-chrome": ("google-chrome",),
    "chromium": ("chromium", "Chromium"),
    "zeditor": ("dev.zed.Zed", "zed"),
    "code": ("Code", "code"),
    "cursor": ("cursor", "Cursor"),
    "spotify": ("spotify", "Spotify"),
    "slack": ("slack", "Slack"),
    "firefox": ("firefox", "Firefox"),
    "missioncenter": ("io.missioncenter.MissionCenter", "missioncenter"),
}


def _resolve_apps(cfg: dict, harness: dict | None) -> dict:
    apps = dict(cfg.get("apps", {}))
    if harness:
        apps.update({n: a["launch"] for n, a in harness.get("apps", {}).items()
                     if a.get("launch")})
    return apps


def _exec_detached(binname: str) -> None:
    from .. import platform
    platform._try(platform.launch_exec_cmds(binname))


def _class_candidates(app: str, binname: str) -> list[str]:
    base = Path(binname.split()[0]).name
    out: list[str] = []
    for c in (app, base, *(_CLASS_ALIASES.get(base, ()))):
        if c and c not in out:
            out.append(c)
    return out


def _match_running_class(candidates: list[str]) -> str | None:
    """Return the live Hyprland class for the first matching candidate."""
    wins = clients()
    for cand in candidates:
        rx = re.compile(f"^{cand}$", re.I)
        for w in wins:
            cls = w.get("class") or ""
            if rx.match(cls):
                return cls
    return None


def class_for_app(app: str, cfg: dict, harness: dict | None = None) -> str | None:
    """Resolve a Jev app slot / name to a running window class, if any."""
    apps = _resolve_apps(cfg, harness)
    binname = apps.get(app, app)
    if not binname or " msg " in f" {binname} ":
        return None
    return _match_running_class(_class_candidates(app, binname))


def launch(app: str, cfg: dict, harness: dict | None = None) -> str:
    apps = _resolve_apps(cfg, harness)
    binname = apps.get(app)
    if not binname:
        return f"SKIP (unknown app {app!r})"
    binary = binname.split()[0]
    if not (shutil.which(binary)
            or (config.HOME / ".local" / "bin" / binary).exists()):
        # terminal: fall back to the desktop's configured default
        # (xdg-terminal-exec) — e.g. ghostty isn't packaged on Asahi
        if app == "terminal" and shutil.which("xdg-terminal-exec"):
            binname = binary = "xdg-terminal-exec"
        else:
            return f"SKIP ({app} -> {binary!r} not installed)"
    # "open X" → focus if already running (skip new-tab / IPC toggles)
    if app != "browser_new_tab" and " msg " not in f" {binname} ":
        cls = _match_running_class(_class_candidates(app, binname))
        if cls:
            out = focus(cls)
            if out.startswith("FOCUSED"):
                return f"FOCUSED {app} ({cls})"
    _exec_detached(binname)
    return f"LAUNCHED {app} -> {binname}"


_FOCUS_PREFIX = re.compile(
    r"^\s*(please\s+)?(?:focus|switch to|bring(?:\s+up)?|go to|show)\s+"
    r"(?:the\s+|my\s+)?",
    re.I)
_FOCUS_NOISE = re.compile(
    r"\b(window|tab|in chrome|chrome|browser|please)\b", re.I)


def focus_needle(text: str) -> str:
    """'Focus OpenRouter' / 'switch to gmail' → needle for title match."""
    if not text:
        return ""
    q = _FOCUS_PREFIX.sub("", text).strip().rstrip(".!?")
    q = _FOCUS_NOISE.sub(" ", q)
    return re.sub(r"\s+", " ", q).strip()


def _match_by_title(needle: str) -> dict | None:
    """Best client whose title contains needle (case-insensitive)."""
    if not needle or len(needle) < 2:
        return None
    n = needle.casefold()
    hits = []
    for w in clients():
        title = w.get("title") or ""
        if n in title.casefold() and w.get("address"):
            hits.append(w)
    if not hits:
        return None
    # Prefer shorter titles (tighter match) then stable address order
    hits.sort(key=lambda w: (len(w.get("title") or ""), w.get("address")))
    return hits[0]


def focus_by_title(needle: str) -> str:
    from .. import platform
    w = _match_by_title(needle)
    if not w:
        return f"SKIP (no window title matching {needle!r})"
    addr = w.get("address", "")
    if not platform._try(platform.focus_address_cmds(addr)):
        return f"SKIP (focus failed for {needle!r})"
    # Confirm active address — hyprctl lies on miss
    live = platform.active_window()
    if live.get("address") != addr:
        return f"SKIP (focus missed {needle!r})"
    return f"FOCUSED title:{needle!r} ({w.get('class')}: {(w.get('title') or '')[:60]})"


def focus(classname: str) -> str:
    from .. import platform
    # Require a live window — hyprctl returns ok even on miss
    # (warns "window not found"), so trust clients[] not exit code.
    # Prefer address when several clients share a class (Chrome tabs/windows).
    target = _match_running_class([classname]) if classname else None
    if not target:
        return f"SKIP (no window matching class {classname!r})"
    wins = [c for c in clients() if (c.get("class") or "") == target]
    if len(wins) == 1 and wins[0].get("address"):
        if platform._try(platform.focus_address_cmds(wins[0]["address"])):
            return f"FOCUSED {target}"
        return f"SKIP (no window matching class {target!r})"
    # Ambiguous class — caller should use focus_by_title
    if len(wins) > 1:
        return (f"SKIP (ambiguous class {target!r}: {len(wins)} windows — "
                f"say a title word, e.g. focus gmail)")
    cmds = platform.focus_cmds(target)
    if not cmds:
        return (f"SKIP (focus unsupported — "
                f"{platform.missing_deps_hint()})")
    if platform._try(cmds):
        return f"FOCUSED {target}"
    return f"SKIP (no window matching class {target!r})"


def close(classname: str) -> str:
    import time
    from .. import platform
    # Always close by address. Bare hl.dsp.window.close() returns ok but
    # often no-ops; verify the address is gone before claiming CLOSED.
    if classname:
        target_cls = _match_running_class([classname]) or ""
        if not target_cls:
            return f"SKIP (no window matching class {classname!r})"
        addr = next((c.get("address", "") for c in clients()
                     if (c.get("class") or "") == target_cls), "")
        label = target_cls
    else:
        w = platform.active_window()
        addr = w.get("address", "") or ""
        label = w.get("class") or "active window"
    if not addr:
        return "SKIP (no active window to close)"
    platform._try(platform.close_address_cmds(addr))
    time.sleep(0.05)
    if any(c.get("address") == addr for c in clients()):
        time.sleep(0.1)
        if any(c.get("address") == addr for c in clients()):
            return f"SKIP (still open: {label} {addr})"
    return f"CLOSED {label}"


def workspace(n: str) -> str:
    from .. import platform
    try:
        num = int(str(n).strip())
    except ValueError:
        return f"SKIP (workspace {n!r} not a number)"
    cmds = platform.workspace_cmds(num)
    if not cmds:
        return (f"SKIP (workspace {num} unsupported — "
                f"{platform.missing_deps_hint()})")
    platform._try(cmds)
    return f"WORKSPACE {num}"


def clients() -> list:
    r = subprocess.run(["hyprctl", "clients", "-j"],
                       capture_output=True, text=True, env=hypr_env())
    try:
        return json.loads(r.stdout)
    except json.JSONDecodeError:
        return []
