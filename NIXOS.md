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

## Install

```fish
cd /tmp && git clone --depth 1 --branch nixos-hyprland https://github.com/BasitAli/wisp.git
cd wisp && python3 wispd install
systemctl --user daemon-reload && systemctl --user restart wispd
```

Point your NixOS glue at `whisper-cpp-vulkan` separately; this branch does not vendor models.
