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

    make install      # ~/.local/{bin,share}; a desktop entry with an absolute Exec=
    make test

Needs `gtk4`, `python-gobject`, `python-cairo`; `pipewire` (`pw-play`) for sound.

## Screenshot

    tools/screenshots.py

renders `screenshots/win95.png` offscreen (no window opens).

## State

`$XDG_STATE_HOME/swaysweeper/` — settings, best times and the game in progress.
A file that will not parse is moved aside to `*.bad`; the game always starts.
