# swaysweeper — design

*2026-10-09. Status: revised after an adversarial review; awaiting Xinye's review of this document.*

> **Superseded in part (2026-10-10):** theme-awareness was removed. The game draws only winmine's
> own colours — Windows 95 with Color on, monochrome with it off. There is no theme file, watcher,
> `--check-colors` or dotfiles template; the parts of §0 and §3–§4 about palettes no longer apply.

A faithful clone of the classic Windows Minesweeper (Windows 95–2000 `winmine`), drawn in the
colours of the active dotfiles palette and recoloured live when the palette switches.
Inspiration: [omasweeper](https://github.com/jankeesvw/omasweeper), a Minesweeper that draws itself
from the active Omarchy theme.

**Rules reference.** Where this document says "winmine does X" the source is the reverse-engineered
winmine in [repnz/ReversingMinesweeper](https://github.com/repnz/ReversingMinesweeper) (XP build,
which shares 2000's rules), cited as `file.c:line`. The one deliberate deviation is listed in §1.

## 0. Understanding

**Stated by Xinye**

- Faithful clone of the classic Windows game, theme-aware.
- Theme = the dotfiles palettes (`palettes.toml`, nord / gruvbox), live repaint on `theme <name>`.
- Python + GTK4 + Cairo, in its own repo (`~/repos/swaysweeper`), with the dotfiles repo providing
  one template that `theme` renders.
- Faithful rules plus small extras: keyboard play, zoom, resume of a game in progress.
- Name: **swaysweeper**.
- Review decisions: fix the 95/98 one-click timer bug; clamp the counter at −99; Zoom ×1/×2 only (superseded 2026-10-29: levels from 100% to 300%, see Zoom below).

**Assumed**

- Personal use; Linux / Wayland (sway) only.

**Success criteria**

1. A player who knows winmine finds no rule difference other than the one listed in §1.
2. Under nord or gruvbox it reads as *that* game in *those* colours — bevels, LEDs, the smiley —
   not a generic grid, and every number is legible (§3 contrast floors).
3. `theme <name>` recolours an open window without a restart, and nothing the theme does can crash
   the game, flash it back to Win95 colours, or lose a game in progress.

**Out of scope:** XP/Vista looks, online scores, hints or a solver, Omarchy themes (the slot table
in §3 leaves room for an adapter later), non-Linux platforms, a `menu.toml` row (Super+Space
already lists desktop entries and searches their keywords).

## 1. Rules (faithful)

| Difficulty | Width × height | Mines |
|---|---|---|
| Beginner | 9 × 9 | 10 |
| Intermediate | 16 × 16 | 40 |
| Expert | 30 × 16 | 99 |
| Custom | width 9–30, height 9–24 | 10 – min((w−1)(h−1), 999) |

Custom input outside those bounds is clamped, not rejected (`windowing.c:220–223`).

- **Placement and first click.** Mines are placed at game start from a seedable RNG. If the first
  reveal lands on a mine, that mine moves to the first mine-free square found scanning row-major
  over rows `0…h−2` and columns `0…w−2` — **the last row and last column are never scanned**
  (`game.c:551–553`). The clicked square is still a mine when the scan runs, so the mine never
  lands back on it. If the scan finds no free square (possible when mines = (w−1)(h−1)), the click
  does nothing: no reveal, and the game stays unstarted. Nothing else about the first click is
  guaranteed: it may land on a number.
- **Reveal.** A left release on a covered, unflagged square reveals it. A zero flood-fills: every
  neighbour of a revealed zero is revealed, recursively; `?` marks inside a flood are cleared and
  revealed, flags are not touched. `?` squares are revealable by a direct click, flags are not.
- **Marks.** Right **press** (not release) cycles covered → flag → `?` → covered when *Marks (?)*
  is on (default), covered ↔ flag when off. Turning Marks off leaves existing `?` on the board.
- **Chord.** A chord gesture is any of: right pressed while left is held; left pressed while right
  is held (the right press has already flagged, as above — winmine does the same); middle button;
  Shift + left (`windowing.c:495–548`). While it is held the 3×3 block under the pointer draws
  sunken. It fires on the **first** button released: on a revealed number whose adjacent flag
  count equals the number, every covered, unflagged neighbour is revealed; on anything else
  nothing happens.
- **Press preview.** While left is held (no chord), the square under the pointer draws sunken —
  a `?` square uses the pressed-`?` sprite — and dragging moves the preview. Release outside the
  board cancels. Flags never draw sunken.
- **Counter.** Mines − flags, displayed clamped to −99…999 (`-12`, minus in the first digit).
  *(winmine draws garbage below −99; clamping is Xinye's call.)*
- **Timer.** Starts at 1 on the first left or middle release **on the board** of a new game, even
  one that reveals nothing (a release on a flag), ticks once per second, stops at 999. It always
  stops on a win or loss. *(Deviation: Win95/98 left the timer running after a one-click win;
  2000 fixed it, and so do we.)* The time recorded for a win is the displayed value.
- **Loss.** Every mine revealed by the losing action — one for a click, possibly several for a
  chord (`game.c:505`) — is drawn on the `exploded` background; every flag on a non-mine shows the
  crossed-out mine; every other mine is revealed; flags on mines stay.
- **Win.** When every non-mine square is revealed, every remaining mine is auto-flagged and the
  counter reads `000`.
- **Smiley.** Normal; `o` mouth while left or middle is held anywhere in the game area (a right
  press does not change it); dead after a loss; sunglasses after a win; drawn pressed while it is
  itself held, cancelled by dragging off it. Releasing on it starts a new game at the same
  difficulty.
- **Best times.** One per standard difficulty, default `999 Anonymous`. A win **strictly faster**
  than the record asks for a name ("You have the fastest time for beginner level. Please type
  your name:"), then shows *Best Times*, as winmine does. *Best Times…* shows all three with a
  *Reset Scores* button. Custom games are never recorded.

## 2. Window and chrome

**Geometry** at zoom ×1, in logical pixels, from `drawing.c:337–383`. With `xRight = 16·W + 24` and
`yBottom = 16·H + 67` (the game area's size):

| Element | Rectangle (left, top → right, bottom) | Bevel |
|---|---|---|
| Outer frame | 0, 0 → xRight−1, yBottom−1 | 3 px, raised |
| Status panel | 9, 9 → xRight−10, 45 | 2 px, sunken |
| Mine counter | 16, 16 → 56, 39 | 1 px, sunken |
| Timer | xRight−57, 15 → +40, 39 | 1 px, sunken |
| Smiley | (xRight−24)/2 − 1, 15 → +25, 40 | 1 px |
| Board | 9, 52 → xRight−10, yBottom−10 | 3 px, sunken |
| Cells | origin 12, 55; 16 × 16 each | — |

LED digits are 13 × 23, drawn at x = 17 / 30 / 43 (counter) and xRight−56 / −43 / −30 (timer);
the face is 24 × 24 at x = (xRight−24)/2. `drawing.c` subtracts a further `WindowWidthInPixels` from
the timer's x — that is the Win32 non-client border width leaking into a client coordinate, and it
is dropped here, which makes the timer mirror the counter as it does on screen. These numbers live
as named constants in one place, and a test pins them for each standard difficulty.

**Window.**

- Application id **`io.github.xinye1.swaysweeper`** (`"swaysweeper"` alone fails
  `Gio.Application.id_is_valid`). GApplication single-instance: a second launch presents the
  existing window, so two processes never race on the state files.
- `set_resizable(False)` at game area × zoom. Verified on this machine: sway floats it, draws its
  own `pixel` border, GTK draws no titlebar, and it resizes when the board shrinks.
- The view still draws the game centred in whatever allocation it gets and paints the surround in
  the `backdrop` slot, so a forced tile looks deliberate.

**Crispness.** Cairo `ANTIALIAS_NONE`, every rectangle on whole device pixels. GTK already draws
in logical pixels, so on this scale-2 display ×1 is 32 device pixels per cell. At a fractional
output scale, coordinates are snapped to device pixels using `Gdk.Surface.get_scale()`.

**Menu bar** — `Gtk.PopoverMenuBar` from a `Gio.Menu`:

- **Game:** New (F2) · Beginner · Intermediate · Expert · Custom… · Marks (?) · Color · Sound ·
  Zoom ▸ · Best Times… · Exit
- **Help:** Keys… · About swaysweeper

Its colours come from the slots through a CSS provider whose selectors are scoped to a class on the
menu bar, so dialogs keep the system GTK theme. *Color* keeps winmine's meaning: unticked renders
the built-in monochrome set.

**Zoom** (amended 2026-10-29: ×1 was too small and ×2 too big) is a submenu: Zoom In (Ctrl+=),
Zoom Out (Ctrl+-), then the levels 100% (Ctrl+0), 125%, 150%, 175%, 200%, 250% and 300%
(`geometry.ZOOMS`). It lists the levels whose window fits the monitor's logical work area. The game
shows the chosen level, or the largest below it that fits; `settings.json` keeps the choice
(`"zoom": 1.25`), so it comes back on a monitor it fits. Cells stay nearest-neighbour: a quarter
step makes every cell a whole number of pixels (16 × 1.25 = 20), so every cell looks the same,
though a 1 px line inside one may come out a pixel thicker than its neighbour.

## 3. Rendering and theming

**Sprites as text.** Every glyph is pixel art written as a list of strings in `sprites.py`; each
character names a colour **slot**, `.` is transparent. Sprites: numbers 1–8, mine, flag, `?`,
pressed `?`, crossed mine, the five faces, LED digits 0–9 and minus (segments drawn as
`led_on` / `led_off`). Bevels, the cell grid and covered squares are rectangles from the same
slots. Painting is one Cairo rectangle per run of equal pixels; no bitmaps ship.

**Slots and the Win95 set.** Every slot has a Win95 value; that set is the built-in default.

| Slot | Used for | Win95 |
|---|---|---|
| `face` | chrome and covered squares | `#c0c0c0` |
| `light` | bevel highlight | `#ffffff` |
| `shadow` | bevel shadow | `#808080` |
| `grid` | lines between revealed squares | `#808080` |
| `revealed` | revealed squares | `#c0c0c0` |
| `backdrop` | surround when the allocation exceeds the game | `#008080` |
| `text` | menu bar text | `#000000` |
| `led_bg` / `led_on` / `led_off` | counter and timer | `#000000` / `#ff0000` / `#800000` |
| `mine` / `glint` | mine body / its highlight | `#000000` / `#ffffff` |
| `flag` / `ink` | flag cloth / flag pole, base and the `?` glyph | `#ff0000` / `#000000` |
| `exploded` | background of a mine that ended the game; the cross | `#ff0000` |
| `smiley` / `smiley_ink` | face / its features | `#ffff00` / `#000000` |
| `cursor` | keyboard cursor outline | `#ff00ff` |
| `num1` … `num8` | numbers | `#0000ff` `#008000` `#ff0000` `#000080` `#800000` `#008080` `#000000` `#808080` |

**Monochrome set** (built-in; *Color* off): black, white and greys only.

**Theme file.** `~/.config/swaysweeper/colors.gen.toml`, a flat table `slot = "#rrggbb"` (`#rgb`
also accepted).

- **First load:** a slot missing or invalid falls back to its Win95 value, one stderr line each.
- **Live reload:** a slot missing or invalid **keeps its current colour**. A missing file, or a
  parse error, keeps everything current.
- Unknown keys are reported, never silently used.

**Contrast floors** — checked against the theme file, not the built-in sets (Win95's own grey 8
would fail them):

| Pair | Floor |
|---|---|
| each `numN` vs `revealed` | 4.5 : 1 (the dotfiles text floor) |
| `light` vs `shadow` | 3 : 1 (the bevel is what makes it read as 3D) |
| `mine` vs `revealed`; `flag` vs `face`; `ink` vs `face`; `smiley_ink` vs `smiley`; `led_on` vs `led_bg` | 3 : 1 |
| `cursor` vs `revealed` and vs `face` | 3 : 1 |
| `cursor` vs every `numN` | must differ |

**`swaysweeper --check-colors FILE`** validates a theme file without opening a window. It exits
non-zero on an unknown, missing or invalid slot, or on any floor in the table above, and prints
each problem. It is what the dotfiles check (§4) runs; it exists because a misspelled slot would
otherwise silently fall back, the exact failure the dotfiles' CLAUDE.md warns about for GTK, tmux
and yazi.

**Live repaint.** A `Gio.FileMonitor` watches `~/.config/swaysweeper/`. `theme` rewrites the
file with `Path.write_text` (truncate, then write), and a read between the two sees an empty —
valid — TOML file. So the game re-parses only on `CHANGES_DONE_HINT` (close-after-write) for
`colors.gen.toml`, never on `CHANGED`. Verified on this machine: watching through the folded stow
symlink works; a directory missing at launch is picked up by GLib's polling a few seconds after it
appears; an **unfolded** package (the file a symlink into the repo) delivers no events, hence
"folded is required" in §4. A successful parse redraws everything and updates the menu-bar CSS.

**Never written by the game.** `~/.config/swaysweeper/` is a stow fold into the dotfiles repo; the
game only reads it.

## 4. Dotfiles side (separate PR in `~/repos/dotfiles`)

- New stow package `swaysweeper/.config/swaysweeper/colors.gen.toml.tmpl` mapping **every** slot
  to a role. Role choices are made by rendering under both palettes and must pass
  `--check-colors` under both. Measured starting mapping (every floor passes under both):
  `face=surface`, `light=dim`, `shadow=desktop`, `grid=sel`, **`revealed=desktop`** (darker than
  `bg`, which is what lets magenta and gruvbox's red clear 4.5:1), `backdrop=desktop`,
  `text=fg`, `led_bg=desktop`, `led_on=critical`, `led_off=bg`, `mine=fg`, `glint=bg`,
  `flag=critical_text`, `ink=fg`, `exploded=critical`, `smiley=warning`, `smiley_ink=desktop`,
  `cursor=fg_bright`; numbers 1 `ansi_bright_blue`, 2 `ansi_bright_green`, 3 `critical_text`,
  4 `ansi_bright_magenta`, 5 `warning`, 6 `ansi_bright_cyan`, 7 `fg`, 8 `dim`.
  The template comment explains each departure from winmine's colours.
- **New palette role `critical_text`** (Xinye, 2026-10-10): nord's only red measures 3.47:1 on
  `desktop`, under the 4.5:1 number floor, and no nord role is a lighter red. Following `dim`'s
  precedent — the shortest step that clears the floor, nothing more — `critical_text` is
  `critical` mixed toward `fg_bright` in 5% steps until it clears 4.5:1 on `desktop`: nord
  `#c87d86` (20%; 4.55:1 on `desktop`, 3.23:1 on `surface` for the flag), gruvbox `#fb4934`
  (= `critical`, which already clears it: 4.77:1 on `desktop`). Added to **both** palettes in `palettes.toml` with that comment;
  `theme` refuses to render if only one has it.
- README package table row; PLAYBOOK §5.2 entry — **folded, and folding is required**: live
  repaint sees no events through an unfolded package, and the game never writes there.
  `setup.sh` must not pre-create `~/.config/swaysweeper`.
- **A check that runs `swaysweeper --check-colors` against the template rendered under each
  palette.** The existing guards don't cover it: `check_hex.py` skips `*.tmpl`, and
  `check_consumers.sh` is a hand-written list. The check reports `skip` (not a pass) when
  swaysweeper is not installed. Where it lives — `check_consumers.sh` or `theme_test.sh` — is
  settled in that PR's plan by reading both.
- `stow -n -v swaysweeper` before `stow swaysweeper`; `tests/theme_test.sh` after.

## 5. State

`$XDG_STATE_HOME/swaysweeper/` (default `~/.local/state/swaysweeper/`):

- `settings.json` — difficulty, custom dimensions, Marks, Color, Sound, Zoom.
- `best.json` — best time and name per standard difficulty.
- `game.json` — a game in progress.

All writes are atomic (temp file in the same directory, `fsync`, `rename`). An unreadable or
invalid file — including one from an incompatible version — is renamed `<name>.bad` and defaults
are used; the game always starts.

**Resume.** `game.json` is rewritten after **every** board change and every timer tick that changes
the displayed second (it is a few kilobytes), so logout, sway exiting or SIGTERM lose at most a
second — not only a clean close. On launch, a game in the *playing* state is restored with the
timer **paused**; it resumes on the first board input, so time spent away is never counted. When a
game ends, or a new one starts, `game.json` is deleted.

## 6. Input

**Mouse:** as §1.

**Keyboard** (extra; invisible until used): the first direction key places a cursor in the board's
centre, later ones move it. Arrows / `h j k l` move; Space or Enter reveals (or chords on a revealed
number); `f` flags / cycles marks; `c` chords; `F2` new game; `?` Keys help; Ctrl+Q exits. The
cursor is a 1-logical-pixel outline in the `cursor` slot. Mouse motion over the board hides it.
Keyboard actions follow the same rules as the mouse, including the timer start.

## 7. Sound (off by default, as in winmine)

Three square-wave sounds — tick, win, lose — generated with the stdlib `wave` module into
`$XDG_CACHE_HOME/swaysweeper/` on first use and played by `pw-play` (GTK has no media backend
installed here). Fire-and-forget: `subprocess.Popen` with stdin/stdout/stderr on `DEVNULL`, never a
pipe. If `pw-play` is absent the *Sound* item is disabled; a failed play is silent and never blocks
the UI.

## 8. Code structure

```
swaysweeper/            package
  board.py              pure game logic; no GTK
  game.py               session: state, timer value, difficulty, (de)serialise
  geometry.py           §2 constants and layout maths; no GTK
  sprites.py            text pixel art + paint(cr, sprite, x, y, scale, colours)
  theme.py              slots, Win95 + mono sets, parser, contrast check, file watcher
  store.py              atomic JSON state, .bad on corruption
  sound.py              wav generation + pw-play
  view.py               DrawingArea: input, face state, cursor, painting
  app.py                Gtk.Application, menu, dialogs, timer tick, --check-colors
bin/swaysweeper         launcher, #!/usr/bin/python3 (the mise shim's python lacks gi)
data/io.github.xinye1.swaysweeper.desktop.in
tests/                  unittest
Makefile                test, install, uninstall
```

**Data flow:** input → `view` → `game` / `board` → redraw + `store.save`. Timer tick → `game` →
timer redraw (+ save on a new second). File monitor → `theme` → full redraw.

`board`, `game`, `geometry`, `theme` (minus the watcher) and `store` import nothing from GTK, so
all rule, layout and colour logic is testable without a display.

## 9. Error handling

| Failure | Behaviour |
|---|---|
| Theme file missing / malformed / half-written | Keep current colours; next close-after-write retries |
| Theme slot missing or invalid | First load: Win95 value + stderr line. Reload: keep current |
| State file corrupt or wrong version | Renamed `.bad`; defaults; game starts |
| `pw-play` missing or fails | Sound item disabled / silent; never blocks the UI |
| Session ends without a clean close | `game.json` is at most one second old |

## 10. Testing

`/usr/bin/python3 -m unittest`; no display needed.

- **board:** seeded layouts; first-click relocation — scan order, last row/column excluded, the
  clicked square never chosen, no-free-square click ignored, a mined top-left first click;
  flood-fill at edges and corners, clearing `?` but not flags; chord on satisfied / unsatisfied
  numbers; a chord revealing two mines marks both exploded; wrong-flag marking on loss; auto-flag
  on win; counter clamped at −99.
- **game:** timer starts at 1 on the first board release, including one on a flag; caps at 999;
  stops on a one-click win; serialise / restore round trip; restored timer paused until input.
- **geometry:** the §2 rectangles for each standard difficulty; Zoom ×2 offered only when it fits.
- **theme:** first load vs reload fallback rules; empty file on reload keeps colours; `#rgb` /
  `#rrggbb` accepted, others rejected; unknown key reported; each contrast floor fails a file
  built to violate it and passes the Win95-free fixture.
- **store:** round trip; corrupt and wrong-version files moved to `.bad`; atomic write leaves no
  partial file.
- **sprites:** every sprite rectangular, expected size, only known slot characters.
- **render smoke:** a lost Expert board painted to a Cairo `ImageSurface` under each colour set;
  the exploded cell's pixel equals `exploded`, a revealed number's pixel equals its `numN`.
- **Mutation check:** key assertions are shown to go red against a deliberately broken copy — the
  relocation scan bounds, the chord flag count, the timer cap, the reload keep-current rule.

**Manual, before calling it done:** play each difficulty with mouse and keyboard, including every
chord gesture; `theme nord` then `theme gruvbox` with a game open (no Win95 flash); close mid-game
and relaunch; `kill` the process mid-game and relaunch; launch from fuzzel.

## 11. Install

`make install`:

- the package to `~/.local/share/swaysweeper/`, the launcher to `~/.local/bin/swaysweeper`;
- the desktop entry to `~/.local/share/applications/io.github.xinye1.swaysweeper.desktop`, with
  **`Exec=` an absolute path** (`$HOME` expanded at install): the sway session's `PATH` has no
  `~/.local/bin`, so a bare `swaysweeper` never resolves from fuzzel or Super+Space.
  `Categories=Game;LogicGame;`, `Keywords=minesweeper;mines;game;`.

`make uninstall` reverses it. Dependencies (already installed): `gtk4`, `python-gobject`,
`python-cairo`; `pipewire` for sound.
