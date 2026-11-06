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


def focus(classname: str) -> str:
    from .. import platform
    # Require a live window — hyprctl returns ok even on miss
    # (warns "window not found"), so trust clients[] not exit code.
    target = _match_running_class([classname]) if classname else None
    if not target:
        return f"SKIP (no window matching class {classname!r})"
    cmds = platform.focus_cmds(target)
    if not cmds:
        return (f"SKIP (focus unsupported — "
                f"{platform.missing_deps_hint()})")
    if platform._try(cmds):
        return f"FOCUSED {target}"
    return f"SKIP (no window matching class {target!r})"


def close(classname: str) -> str:
    from .. import platform
    # Same as focus: require a live class when one was named — hyprctl
    # returns ok on miss. Empty classname = close the active window.
    target = ""
    if classname:
        target = _match_running_class([classname]) or ""
        if not target:
            return f"SKIP (no window matching class {classname!r})"
    if platform._try(platform.close_cmds(target)):
        return f"CLOSED {target or 'active window'}"
    return f"SKIP (nothing closed for {classname!r})"


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
