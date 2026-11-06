# nixos-hyprland branch

Generic Hyprland / NixOS-oriented fixes on top of upstream `v0.9.0`.
**No personal config, keys, prompts, or machine paths** — those stay in
the installer’s `~/.config/wisp/`.

## Changes vs v0.9.0

- **Hyprland 0.57**: focus/close via `hl.dsp.*` (legacy `focuswindow`/`closewindow` broken)
- **Launch focuses** a running window (class aliases for chrome/zed/…) before spawning
- **Focus/close** require a live `hyprctl clients` match (eval returns ok on miss)
- **Dictation**: `type` trigger; skip app low-conf chooser; restore PTT-time window before `wtype`
- **Local STT**: pass `stt.prompt` to `whisper-cli --prompt`
- **Close** honoured when Jev sets `route=launch` + `action=close`
- **`agent.answers=false`**: skip OpenRouter Q&A path (hands-only)
- **`agent.act=false`**: skip Maverick act / learn / shell→act loops
- **`agent.local_first`**: keyword router (`wisp/local_router.py`) before Jev —
  focus/open/close/type/keys; personal phrases in `~/.config/wisp/commands.toml`
  (never commit that file here)
- **`agent.jev=false`**: no OpenRouter at all; unmatched speech → dictation
  (`router: local_fallback`); enter trailer on type/`? press enter` works
- **`audio.pause_media`**: pause MPRIS players (playerctl) while PTT is held
- **Multi-step macros**: spoken `open … and type …`; `wait_window` after launch
  (hyprctl poll); `commands.toml` `[[command.step]]`; `read_kitty` /
  `agent.read_after_type` via `kitten @ get-text` (Kitty remote control)

## Install

```fish
cd /tmp && git clone --depth 1 --branch v0.9.0-nixos.3 https://github.com/BasitAli/wisp.git
cd wisp && python3 wispd install
systemctl --user daemon-reload && systemctl --user restart wispd
```

Point your NixOS glue at `whisper-cpp-vulkan` separately; this branch does not vendor models.

## Updating from upstream

When duketopceo/wisp ships a new release, **rebase this branch** — do not only
reinstall an old tag:

```fish
git fetch upstream --tags
git checkout nixos-hyprland
git rebase upstream/vX.Y.Z    # or upstream/master
git push --force-with-lease origin nixos-hyprland
git tag -a vX.Y.Z-nixos.1 -m "vX.Y.Z + nixos-hyprland fixes"
git push origin vX.Y.Z-nixos.1
```

Then `wispd install` from the new tag. Keep personal config out of this repo.
