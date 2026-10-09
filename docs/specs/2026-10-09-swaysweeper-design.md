# swaysweeper — design

*2026-10-09. Status: approved in conversation, awaiting review of this document.*

A faithful clone of the classic Windows Minesweeper (Windows 95/98/2000 `winmine`), drawn in the
colours of the active dotfiles palette and recoloured live when the palette switches.
Inspiration: [omasweeper](https://github.com/jankeesvw/omasweeper), a Minesweeper that draws itself
from the active Omarchy theme.

## 0. Understanding

**Stated by Xinye**

- Faithful clone of the classic Windows game, theme-aware.
- Theme = the dotfiles palettes (`palettes.toml`, nord / gruvbox), live repaint on `theme <name>`.
- Python + GTK4 + Cairo, in its own repo (`~/repos/swaysweeper`), with the dotfiles repo providing
  one template that `theme` renders.
- Faithful rules plus small extras: keyboard play, integer zoom, resume of a game in progress.
- Name: **swaysweeper**.

**Assumed**

- Reference version is Windows 95–2000 winmine: its layout, menu and quirks, not XP or Vista.
- Personal use; Linux / Wayland (sway) only.

**Success criteria**

1. A player who knows winmine finds no rule difference.
2. Under nord or gruvbox it reads as *that* game in *those* colours: bevels, LEDs, the smiley,
   not a generic grid.
3. `theme <name>` recolours an open window without a restart, and nothing the theme does can crash
   the game or lose a game in progress.

**Out of scope:** XP/Vista looks, online scores, hints or a solver, Omarchy themes (the slot table
in §3 leaves room for an adapter later), non-Linux platforms.

## 1. Rules (faithful)

| Difficulty | Width × height | Mines |
|---|---|---|
| Beginner | 9 × 9 | 10 |
| Intermediate | 16 × 16 | 40 |
| Expert | 30 × 16 | 99 |
| Custom | width 9–30, height 9–24 | 10 – (w−1)(h−1) |

Custom input outside those bounds is clamped, as winmine did, not rejected.

- **First click.** Mines are placed at game start, before the first click, from a seedable RNG.
  If the first reveal lands on a mine, that mine moves to the first mine-free square scanning
  row-major from the top-left, as winmine does. Nothing else about the first click is guaranteed:
  it may land on a number.
- **Reveal.** Left-click on a covered, unflagged square reveals it. A zero flood-fills: every
  neighbour of a revealed zero is revealed, recursively. Flags and `?` inside a flood are cleared
  and revealed; `?` squares are revealable by a direct click, flags are not.
- **Marks.** Right-click cycles covered → flag → `?` → covered when *Marks (?)* is on (default), and
  covered ↔ flag when off. Turning Marks off leaves existing `?` on the board.
- **Chord.** Both buttons released together, or a middle-button release, on a revealed number
  whose adjacent flag count equals the number reveals every covered, unflagged neighbour. A chord
  that reveals a mine loses. A chord on an unsatisfied number does nothing.
- **Press preview.** While the left button is held, the square under the pointer draws sunken;
  dragging moves the preview; with a chord gesture held the 3×3 block draws sunken. Release
  outside the board cancels. Flags never draw sunken.
- **Counter.** Mines − flags, so it can go negative (`-12`, the minus in the first digit); it
  clamps to the range −99…999 for display.
- **Timer.** Starts at 1 on the first reveal, ticks once per second, stops at 999. The time
  recorded for a win is the displayed value.
- **Loss.** The mine that was revealed is drawn on the `exploded` background; every flag on a
  non-mine shows the crossed-out mine; every other mine is revealed; flags on mines stay.
- **Win.** When every non-mine square is revealed, every remaining mine is auto-flagged and the
  counter reads `000`.
- **Smiley.** Normal; `o` mouth while any board button is held during play; dead after a loss;
  sunglasses after a win; drawn pressed while it is itself held. Clicking it starts a new game at
  the same difficulty.
- **Best times.** One per standard difficulty, default `999 Anonymous`. A win that beats it asks
  for a name ("You have the fastest time for beginner level. Please type your name:"). *Best
  Times…* shows all three with a *Reset Scores* button. Custom games are never recorded.

## 2. Window and chrome

Geometry at scale 1, in pixels, matching winmine:

- Cell 16 × 16. LED digit 13 × 23. Smiley button 26 × 26 (24 × 24 face in a 1 px border).
- Outer frame raised 3 px; margins 12 px left / right, 8 px between panel and board, 12 px bottom
  — the exact margins are confirmed against a reference screenshot during implementation and
  live as named constants in one place.
- Status panel sunken 2 px, 37 px tall: counter (3 digits, sunken 1 px) left, smiley centred,
  timer right.
- Board sunken 3 px.

The window is `set_resizable(False)` at board size × scale; sway floats a toplevel whose minimum
and maximum sizes match. **Verify this in implementation**; if sway tiles it anyway, the dotfiles
PR adds `for_window [app_id="swaysweeper"] floating enable`. Either way the view draws the game
centred in whatever allocation it gets and paints the surround in the `backdrop` slot, so a
tiled window still looks deliberate.

**Menu bar** (`Gtk.PopoverMenuBar` from a `Gio.Menu`, styled from the slots by a CSS provider so
it matches the chrome; dialogs keep the system GTK theme):

- **Game:** New (F2) · Beginner · Intermediate · Expert · Custom… · Marks (?) · Color · Sound ·
  Zoom ×1 / ×2 / ×3 · Best Times… · Exit
- **Help:** Keys… · About swaysweeper

*Color* keeps its original meaning: unticked renders the built-in monochrome slot set. *Zoom* is
an integer scale (default: the monitor's scale factor, rounded), rendered with nearest-neighbour
so the pixel art stays crisp.

## 3. Rendering and theming

**Sprites as text.** Every glyph is pixel art written as a list of strings in `sprites.py`; each
character names a colour **slot**, `.` is transparent. Sprites: numbers 1–8, mine, flag, `?`,
crossed mine, the five faces, LED digits 0–9 and minus (segments drawn as `led_on` / `led_off`).
Bevels, cell grid and covered squares are drawn as rectangles from the same slots. Painting is one
Cairo rectangle per run of equal pixels at `scale`; no bitmaps ship.

**Slots**

| Group | Slots |
|---|---|
| Chrome | `face`, `light`, `shadow`, `grid`, `revealed`, `backdrop`, `text` |
| LED | `led_bg`, `led_on`, `led_off` |
| Pieces | `mine`, `flag`, `exploded`, `cursor` |
| Numbers | `num1` … `num8` |

**Colour sets**

- **Win95** (built-in default): `face #c0c0c0`, `light #ffffff`, `shadow #808080`, `revealed`
  `#c0c0c0`, `led_bg #000000`, `led_on #ff0000`, `led_off #800000`, `exploded #ff0000`, numbers
  1 blue `#0000ff`, 2 green `#008000`, 3 red `#ff0000`, 4 navy `#000080`, 5 maroon `#800000`,
  6 teal `#008080`, 7 black `#000000`, 8 grey `#808080`.
- **Monochrome** (built-in; used when *Color* is off): black, white and greys only.
- **Theme** (from file, below), used when present and *Color* is on.

**Theme file.** `~/.config/swaysweeper/colors.gen.toml`, a flat table of `slot = "#rrggbb"`.
Accepted values are `#rgb` and `#rrggbb`; anything else is ignored for that slot. A slot
missing or invalid in the file falls back to its Win95 value and is reported once on stderr.

**Live repaint.** A `Gio.FileMonitor` watches the file's directory. `theme` overwrites the file in
place, so a change event is followed by a 150 ms debounce, then a re-parse. A parse failure or a
missing file **keeps the current colours** and waits for the next event — never a crash, never a
mid-game fall back to Win95 because of a half-written file. A successful parse triggers a full
redraw and a menu-bar CSS update.

**Never written by the game.** `~/.config/swaysweeper/` may be a stow fold into the dotfiles repo;
the game only reads it.

## 4. Dotfiles side (separate PR in `~/repos/dotfiles`)

- New stow package `swaysweeper/.config/swaysweeper/colors.gen.toml.tmpl`, mapping slots to roles,
  e.g. `face = "{{surface}}"`, `light = "{{muted}}"`, `shadow = "{{desktop}}"`,
  `revealed = "{{bg}}"`, `grid = "{{sel}}"`, `backdrop = "{{desktop}}"`, `text = "{{fg}}"`,
  `led_bg = "{{desktop}}"`, `led_on = "{{critical}}"`, `led_off = "{{surface}}"`, `exploded = "{{critical}}"`,
  `cursor = "{{accent}}"`.
- Numbers from the ANSI ramp: 1 `ansi_normal_blue`, 2 `ansi_normal_green`, 3 `ansi_normal_red`,
  4 `ansi_normal_magenta`, 5 `ansi_normal_yellow`, 6 `ansi_normal_cyan`, 7 `fg`, 8 `dim`. The
  template comment explains the departure: winmine's navy, maroon and black vanish on a dark
  background. The exact role choices are judged by rendering under both palettes, not chosen
  on paper.
- README package table row; PLAYBOOK §5.2 entry — **folded**, safe because the game never writes
  into `~/.config/swaysweeper/`.
- Confirm (do not assume) that `tests/theme_test.sh`'s hex guard and `check_consumers.sh` pick the
  new template up; `stow -n -v swaysweeper` before `stow swaysweeper`.
- Optionally a row in `menu.toml` (Super+Space palette), with `tests/menu_test.py` run after.

## 5. State

`$XDG_STATE_HOME/swaysweeper/` (default `~/.local/state/swaysweeper/`):

- `settings.json` — difficulty, custom dimensions, Marks, Color, Sound, Zoom.
- `best.json` — best time and name per standard difficulty.
- `game.json` — a game in progress.

All writes are atomic (temp file in the same directory, `fsync`, `rename`). An unreadable or
invalid file is renamed `<name>.bad` and defaults are used; the game always starts.

**Resume.** On close, a game in the *playing* state is saved (board, marks, elapsed seconds,
difficulty). On launch it is restored with the timer **paused**; the clock resumes on the first
board input, so time spent away is never counted. Won, lost and not-yet-started games are not
saved; a restored game is deleted from disk once it ends.

## 6. Input

**Mouse:** as §1.

**Keyboard** (extra; invisible until used): the first direction key places a cursor in the board's
centre, later ones move it. Arrows / `h j k l` move; Space or Enter reveals (or chords on a revealed
number); `f` flags / cycles marks; `c` chords; `F2` new game; `?` keys help; Ctrl+Q exits. The
cursor draws as a 1-pixel-scaled outline in the `cursor` slot. Any mouse motion over the board
hides it.

## 7. Sound (off by default, as in winmine)

Three square-wave sounds — tick, win, lose — generated with the stdlib `wave` module into
`$XDG_CACHE_HOME/swaysweeper/` on first use and played by `pw-play` (GTK has no media backend
installed here). Played fire-and-forget: `subprocess.Popen` with stdin/stdout/stderr on
`DEVNULL`, never a pipe. If `pw-play` is absent, the *Sound* item is disabled.

## 8. Code structure

```
swaysweeper/            package
  board.py              pure game logic; no GTK
  game.py               session: state, timer value, difficulty, (de)serialise
  sprites.py            text pixel art + paint(cr, sprite, x, y, scale, colours)
  theme.py              slots, Win95 + mono sets, parser, file watcher
  store.py              atomic JSON state, .bad on corruption
  sound.py              wav generation + pw-play
  view.py               DrawingArea: layout, input, face state, cursor
  app.py                Gtk.Application, menu, dialogs, timer tick
bin/swaysweeper         launcher, #!/usr/bin/python3 (the mise shim's python lacks gi)
data/swaysweeper.desktop
tests/                  unittest
Makefile                test, install, uninstall
```

**Data flow:** input → `view` → `game` / `board` → redraw. Timer tick → `game` → redraw of the
timer region. File monitor → `theme` → full redraw. Window close → `store.save`.

`board` and `game` import nothing from GTK, so all rule logic is testable without a display.

## 9. Error handling

| Failure | Behaviour |
|---|---|
| Theme file missing / malformed / half-written | Keep current colours; next event retries |
| Theme slot missing or invalid | Win95 value for that slot; one stderr line |
| State file corrupt | Renamed `.bad`; defaults; game starts |
| `pw-play` missing or fails | Sound item disabled / silent; never blocks the UI |
| Saved game from an incompatible version | Treated as corrupt (`.bad`) |

## 10. Testing

`python3 -m unittest` under `/usr/bin/python3`; no display needed.

- **board:** seeded layouts; first-click relocation and its scan order; flood-fill at edges and
  corners, clearing marks; chord on satisfied / unsatisfied numbers; chord onto a mine loses;
  wrong-flag marking on loss; auto-flag on win; negative counter; Custom clamping.
- **game:** timer start at 1 on first reveal, cap at 999; serialise / restore round trip; restored
  game timer paused until input.
- **theme:** missing file; partial file per-slot fallback; malformed TOML keeps the previous set;
  `#rgb` / `#rrggbb` accepted, others rejected.
- **store:** round trip; corrupt file moved to `.bad`; atomic write leaves no partial file.
- **sprites:** every sprite rectangular, expected size, only known slot characters.
- **render smoke:** a lost Expert board painted to a Cairo `ImageSurface` under each colour set;
  the exploded cell's pixel equals the `exploded` colour, a revealed number's pixel equals its
  `numN` colour.
- **Mutation check:** key assertions are shown to go red against a deliberately broken copy (the
  first-click rule, the chord flag count, the timer cap) — a suite that cannot fail proves nothing.

Manual check before calling it done: play each difficulty; `theme nord` then `theme gruvbox` with a
game open; close mid-game and relaunch.

## 11. Install

`make install`: `bin/swaysweeper` to `~/.local/bin/`, the package to
`~/.local/share/swaysweeper/`, the desktop entry to `~/.local/share/applications/`
(`Categories=Game;LogicGame;`, `Keywords=minesweeper;mines;game;`). `make uninstall` reverses it.
Dependencies (already installed): `gtk4`, `python-gobject`, `python-cairo`; `pipewire` for sound.
