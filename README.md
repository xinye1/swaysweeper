# swaysweeper

The classic Windows Minesweeper — Windows 95–2000 `winmine`, rules, look and
colours and all. Inspired by [omasweeper](https://github.com/jankeesvw/omasweeper).

- Beginner, Intermediate, Expert and Custom; Marks (?), Color, Best Times.
- winmine's rules: the first-click mine moves to the top-left-most free square
  (never the last row or column); right *press* flags; chord with both buttons,
  the middle button or Shift+left, on the first button released.
- One deliberate deviation: the 95/98 one-click-win timer bug is fixed, as 2000 did.
- Extras that stay out of the way: vim/arrow keyboard play (`?` lists the keys),
  Zoom ×2 when it fits, and a game in progress survives closing — or a crash.

![A lost Intermediate game](screenshots/win95.png)

## Play

| Mouse | |
| --- | --- |
| Left click | open a square |
| Right click | flag, then `?`, then clear (on the press, as winmine) |
| Both buttons, middle, or Shift+left | open around a satisfied number |
| Smiley | new game |

| Keyboard | |
| --- | --- |
| Arrows or `h j k l` | move the cursor (the first press puts it in the middle) |
| Space or Enter | open — or, on a number, open around it |
| `f` | flag, then `?`, then clear |
| `c` | open around a number |
| F2 | new game |
| `?` | list the keys |
| Ctrl+Q | exit |

## Install

### Linux (sway)

    make install      # ~/.local/{bin,share}; a desktop entry with an absolute Exec=
    make test

Needs `gtk4`, `python-gobject`, `python-cairo`; `pipewire` (`pw-play`) for sound.

### Windows 10 and 11

A native build: one `.exe`, real Windows menus and dialogs, no installer.
Download `swaysweeper-windows-x86_64.exe` from the
[releases](https://github.com/xinye1/swaysweeper/releases) and run it. For this beta:

```powershell
$url = "https://github.com/xinye1/swaysweeper/releases/download/v0.1.0-beta.2/swaysweeper-windows-x86_64.exe"
Invoke-WebRequest $url -OutFile swaysweeper.exe
(Get-FileHash swaysweeper.exe -Algorithm SHA256).Hash   # compare with the .sha256 on the release
.\swaysweeper.exe
```

The exe isn't code-signed, so SmartScreen may warn on the first run: choose
**More info → Run anyway**, or run `Unblock-File .\swaysweeper.exe` once.
Minimising pauses the clock, as winmine did, and the window remembers where it was.

To build it yourself, install [MSYS2](https://www.msys2.org), open the
**UCRT64** shell and run:

```sh
pacman -S --needed mingw-w64-ucrt-x86_64-gcc make
make -C win CC=gcc LDFLAGS="-static -s"
```

## Screenshot

    tools/screenshots.py

renders `screenshots/win95.png` offscreen (no window opens).

## State

`$XDG_STATE_HOME/swaysweeper/` — settings, best times and the game in progress.
A file that will not parse is moved aside to `*.bad`; the game always starts.

On Windows: `%LOCALAPPDATA%\swaysweeper\` (`*.ini`), with the same rules.
