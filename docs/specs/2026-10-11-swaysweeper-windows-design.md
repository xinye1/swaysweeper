# swaysweeper for Windows — design

*2026-10-11. Status: draft, for adversarial review.*

A native Win32 version of swaysweeper: the same game as the Linux one, in C against the Win32 API
and GDI, shipped as one `.exe`. The Linux design
(`docs/specs/2026-10-09-swaysweeper-design.md`, its colour/theme parts superseded) stays the
authority on **rules, geometry and look**. This document covers what is different on Windows and
how the two implementations are kept identical.

## 0. Understanding

**Stated by Xinye**

- Make a Windows version and release it. The first release (`v0.1.0-beta.1`, Linux) is out.
- **Native Win32 rewrite**, chosen over bundling GTK with the Python code. A small exe with real
  Windows menus and dialogs, at the cost of a second codebase.
- Pre-release versioning: the Windows release is **`v0.1.0-beta.2`**.
- Classic colours only, as on Linux: Windows 95 with Color on, monochrome with it off.

**Assumed**

- Windows 10 1703+ and 11, x86-64. No ARM64 build, no installer, no code signing, so SmartScreen
  warns on first run and the README says so.
- There's no Windows or Wine here, so the exe is compiled and exercised only on GitHub's Windows
  runner, as termtris is. Everything that can be portable C is, so it compiles and is tested on
  Linux with the system `gcc`.

**Success criteria**

- The same rules, pixels and keys as the Linux build, *proved* rather than eyeballed: the C core
  replays scripted games and renders boards that a Python test compares, step by step and pixel by
  pixel, against the Python implementation (§5).
- A static, dependency-free `swaysweeper.exe` that launches, plays, saves and resumes on a real
  Windows desktop, exercised by an automated smoke test on the runner (§6).
- Release `v0.1.0-beta.2` carries `swaysweeper-windows-x86_64.exe` and its `.sha256`, built by a
  workflow from the tagged source.

## 1. Behaviour

Identical to Linux (Linux spec §1, §2 geometry, §5 resume semantics, §6 keyboard, §7 sounds),
except:

| | Linux | Windows |
|---|---|---|
| Menu bar | GTK popover menu | Native Win32 menu (`.rc`), the same items, check marks and radio dots |
| Dialogs | GTK windows | Native dialog templates: Custom Field, Congratulations (name entry), Fastest Mine Sweepers (with Reset Scores), Keys, About |
| Minimise | n/a (sway has none) | **Pauses the timer**, as winmine did on minimise; it resumes on restore |
| Scale | GTK logical pixels | Per-monitor DPI aware (§3.3) |
| State | `$XDG_STATE_HOME/swaysweeper/*.json` | `%LOCALAPPDATA%\swaysweeper\*.ini` (§3.5) |
| Sound | `pw-play`, WAV files cached | `PlaySoundW` from WAV bytes in memory; no files |
| Second launch | GApplication presents the window | A named mutex; the second process brings the first window forward and exits |

The window title is `swaysweeper`. The window has a caption, system menu and minimise box, but no
maximise box and no sizing border, like winmine. Its client area is exactly the game area × scale.

## 2. Architecture

Everything lives under `win/` in this repo. The C is C11.

| File | Contents | Depends on |
|---|---|---|
| `win/core.h`, `win/core.c` | Board, game, gestures, geometry, renderer into a 32-bit pixel buffer, sound synthesis (WAV bytes), state (de)serialisation, xorshift RNG. **No `windows.h`.** | C library |
| `win/sprites.h` | Generated sprite and colour tables. | — |
| `win/main.c` | Window, menu, message loop, input → gestures, timer, blit, dialogs, sound playback, files, DPI, single instance. | `core`, Win32 |
| `win/swaysweeper.rc` | Menu, accelerators, dialog templates, version info, icon, manifest. | — |
| `win/swaysweeper.manifest` | Common Controls v6, PerMonitorV2 DPI awareness, `asInvoker`. | — |
| `win/swaysweeper.ico` | Generated from the smiley sprite at 16, 32 and 48 px. | — |
| `win/replay.c` | Test driver: reads a script on stdin, drives `core`, prints state or a PPM. | `core` |
| `win/test_core.c` | C unit tests for what the replay doesn't cover (serialisation, clamping, WAV header). | `core` |
| `win/wintest.c` | Windows-only smoke test that drives the real exe (§6). | Win32 |
| `win/Makefile` | `make -C win` builds the exe; `make -C win test` builds and runs the portable tests with any `cc`. | — |
| `tools/gen_c_sprites.py` | Writes `win/sprites.h` and `win/swaysweeper.ico` from `swaysweeper/sprites.py` and `colours.py`. | Python |

**Single source of the art.** The sprites and both colour sets are defined once, in the Python
package; `win/sprites.h` is generated from them and committed. A Python test regenerates it in
memory and fails if the committed file differs, so the two builds can never drift in look.

**One Linux-side refactor.** The key → action mapping lives in `view.py` (GTK), so the parity
test can't drive it. It moves, unchanged in behaviour, to a GTK-free `swaysweeper/keys.py`
(`key(name, cursor, board) → (cursor, action)`), which `view.py` calls. Its existing behaviour gets
tests first.

**Single source of the version.** `win/core.h` defines `SWAYSWEEPER_VERSION`. A Python test asserts
it equals `swaysweeper.__version__`. The release workflow checks both against the tag.

## 3. Windows specifics

### 3.1 Rendering

`core` renders the whole game area at ×1 into a `uint32_t` buffer (`0x00RRGGBB`), the same way
`render.py` does: fill, bevels, LEDs, face, cells, pressed preview, keyboard cursor. `main.c` keeps
a DIB of that size and draws it with `StretchDIBits` at an integer scale, `COLORONCOLOR`, so it
stays crisp. The whole game area is re-rendered on every `WM_PAINT`. At ≤ 504 × 323 pixels that's
cheap, so there's no cell cache.

### 3.2 Input

- **Mouse:** `WM_{L,M,R}BUTTON{DOWN,UP}` and `WM_MOUSEMOVE` are mapped to `core` gestures. The
  message's `MK_*` flags supply the held-button set, the same way the GTK mask does on Linux.
  `SetCapture` on the first press and `ReleaseCapture` when no button is held. `WM_CAPTURECHANGED`
  (e.g. a dialog opening mid-gesture) resets the gesture state. Shift comes from `MK_SHIFT`.
  Double-click messages aren't requested (no `CS_DBLCLKS`), so a fast second click is a press.
- **Keyboard:** arrows via `WM_KEYDOWN`; `h j k l`, `f`, `c`, `?`, Space and Enter via `WM_CHAR`.
  `F2` (New) and Ctrl+Q (Exit) are accelerators. `Alt` opens the menu as usual.
- Mouse motion over the board hides the keyboard cursor, as on Linux.

### 3.3 Scale and Zoom

The process is PerMonitorV2 DPI-aware, so Windows never bitmap-stretches the window.

- **Base scale:** `max(1, round(dpi / 96))`.
- **Effective scale:** `base × (Zoom ×2 ? 2 : 1)`.
- **Fitting:** Zoom ×2 is enabled only while the window at `base × 2`, including its non-client
  frame (`AdjustWindowRectExForDpi`), fits the monitor's work area. Otherwise it is greyed out, and
  switched off if it was on. The ×1 window also gets the "fits" check: if even `base` doesn't fit
  (Expert on a small screen at 200 %), the scale steps down to the largest integer that fits,
  minimum 1.
- **Changes:** `WM_DPICHANGED` recomputes all of this and resizes.

### 3.4 Timer and pause

`SetTimer` at 1000 ms while the game is ticking, as on Linux.

- **Minimise:** `SC_MINIMIZE` pauses, killing the timer and keeping the seconds. The board is
  drawn as normal underneath, since nothing is visible anyway.
- **Restore:** `SC_RESTORE` resumes, if the game was ticking before.
- **Resume after relaunch:** a game resumed from disk starts paused until the first board input,
  exactly as on Linux.

### 3.5 State

`%LOCALAPPDATA%\swaysweeper\` holds `settings.ini`, `best.ini` and `game.ini`: UTF-8 `key=value`
lines, written by `core` and parsed by `core`.

- **Location:** `LOCALAPPDATA` is read from the environment, falling back to
  `SHGetKnownFolderPath(FOLDERID_LocalAppData)`, so tests can redirect it.
- **Atomic writes:** a temp file in the same directory, `FlushFileBuffers`, then
  `MoveFileExW(MOVEFILE_REPLACE_EXISTING | MOVEFILE_WRITE_THROUGH)`.
- **Bad files:** an unreadable or invalid file is renamed `<name>.ini.bad`, and the defaults are
  used. The game always starts.
- **Validation:** loading validates exactly what `store.py` and `Game.from_dict` validate: known
  keys, ranges, board size against difficulty, mines in bounds, marks rows, state, and exploded ⊆
  mines.
- **Names:** best-time names are at most 32 characters (code points), converted UTF-16 ⇄ UTF-8 at
  the dialog boundary.

The file format is Windows-only; the two builds never share state.

### 3.6 Dialogs

All dialogs are modal and use the dialog font (`MS Shell Dlg 2`).

- **Custom Field:** Height, Width and Mines edit boxes (numbers only), OK and Cancel. Values are
  clamped by `clamp_custom`, never rejected.
- **Congratulations:** "You have the fastest time for <level> level. Please type your name:". The
  edit box is prefilled `Anonymous`, all selected, 32-character limit. Closing it any way records
  the typed name, or `Anonymous` if empty, as on Linux. The time is saved *before* the dialog
  opens.
- **Fastest Mine Sweepers:** three rows of seconds and name, with Reset Scores and OK.
- **Keys:** the same text as Linux's Keys dialog.
- **About:** name, version, "The classic Windows Minesweeper.", the omasweeper credit and MIT.

### 3.7 Sound

`core` synthesises the three WAVs (tick, win, lose) byte-for-byte as `sound.write_wav` does. A
test compares the bytes against the Python output. `main.c` plays them with `PlaySoundW(...,
SND_MEMORY | SND_ASYNC | SND_NODEFAULT)`. Sound is off by default; a failed play is silent.

### 3.8 Single instance

`CreateMutexW(L"Local\\io.github.xinye1.swaysweeper")`. If it already exists, the second process
finds the first window by class name, restores it if minimised, calls `SetForegroundWindow`, and
exits. Two processes never race on the state files.

### 3.9 RNG

A xorshift64* generator seeded from `QueryPerformanceCounter` ^ the process id. Mines are placed by
a partial Fisher–Yates shuffle over the W×H cells. The C and Python builds needn't share
sequences: the parity tests feed explicit mine lists.

## 4. Build

- **Toolchain:** MinGW-w64 GCC. That's MSYS2 UCRT64 on the runner, or `x86_64-w64-mingw32-gcc` if
  installed locally (it isn't, today).
- **Flags:** `-std=c11 -O2 -Wall -Wextra -pedantic -Werror -municode -mwindows`, plus `-static -s`
  for the release build.
- **Linking:** links `user32 gdi32 winmm comctl32 shell32 ole32 uuid` only.
- **Size:** the exe is expected to be well under 1 MB.
- **Portable targets:** `make -C win test` builds `replay` and `test_core` with plain `cc` and the
  same warning flags, so they run here and on both runners.

## 5. Parity testing (the core of the confidence)

`tests/test_win_parity.py`, run by `make test`, compiles `win/replay` with the system `cc` (the
test is skipped if there is none). It then runs one set of scripts through both implementations
and compares the results.

- **Script language:** one command per line.
  - `new <w> <h> <difficulty> <x,y;x,y;…>` — explicit mines.
  - `reveal x y` · `chord x y` · `mark x y <marks:0|1>` · `tick`.
  - `press <button> <cx> <cy> <face:0|1> <shift:0|1> <held>` · `release …` · `motion …` — gestures.
  - `key <name>` — keyboard actions.
  - `dump` — state.
  - `render <face> <pressed-cells> <cursor>` — a PPM of the game area.
- **Compared outputs:**
  - **State:** marks rows, board state, exploded set, revealed count, counter, seconds,
    timer_running and paused, gesture mode and face, keyboard cursor, plus each action list a
    gesture returns.
  - **Pixels:** every `render` is a PPM compared byte-for-byte with the Python renderer's
    (`render.draw` to a Cairo `RGB24` surface, converted to PPM).
  - **Serialisation:** a round trip of the C state format, plus validation rejects for the same
    malformed inputs as `test_store.py` and `test_game.py`.
  - **WAV:** the bytes of each synthesised sound.
- **Scripts:** the existing Python test boards (walled, relocation, chord-with-wrong-flags,
  one-click win, −99 clamp, Custom clamps), plus a seeded random walk. That walk is a few hundred
  games with random moves and gestures, generated in Python, replayed by both, and compared after
  every step.

## 6. Windows smoke test (CI)

`win/wintest.c` runs on the Windows runner against the built exe, with `LOCALAPPDATA` redirected to
a temp directory. It:

1. Launches `swaysweeper.exe` and waits for its window (`FindWindowW` by class), then checks that
   the client size is the Beginner game area × the base scale.
2. Captures the client with `PrintWindow` and checks the smiley's yellow and a covered cell's
   bevel.
3. Posts `WM_LBUTTONDOWN`/`UP` on a cell, captures again, and checks the cell is now revealed
   (sunken grid line) and the timer reads 001.
4. Posts `WM_RBUTTONDOWN` on another covered cell and checks the flag's red.
5. Sends `WM_CLOSE`, waits for exit, and checks `game.ini` exists. It relaunches and checks the
   same cells are restored, closes again, and checks a second launch while one is running exits
   within 5 s with the first still alive.
6. Writes every capture as a BMP artifact for human inspection.

## 7. CI and release

The repo has no CI today. It gets termtris's pattern.

- **`ci.yml`:** gated to PR opened-as-ready / ready_for_review, plus `workflow_dispatch`, never on
  every push. A **linux** job runs `make test`, which includes the parity tests with gcc. A
  **windows** job (MSYS2 UCRT64) runs `make -C win test`, then `make -C win`, then
  `wintest.exe swaysweeper.exe`, and uploads the captures.
- **`release.yml`:** runs on `release: published`. It checks that the tag is `v` + `__version__`
  and also `v` + `SWAYSWEEPER_VERSION`, builds the static stripped exe, and uploads
  `swaysweeper-windows-x86_64.exe` with `.sha256` via `gh release upload`.
- **The release:** bump both versions to `0.1.0-beta.2`, merge, then publish `v0.1.0-beta.2` as a
  pre-release. The notes name the SmartScreen warning and the checksum.

## 8. Error handling

- No path ends in a crash dialog.
- A failed state write is ignored: the game goes on, as on Linux.
- A failed `PlaySoundW` is silent.
- A failed DIB allocation at startup shows a `MessageBoxW` and exits non-zero.
- Every Win32 call whose failure matters is checked.

## 9. Out of scope

- ARM64, 32-bit, installer, MSI or winget, and code signing.
- Sharing state with the Linux build.
- High-contrast themes and screen readers. The game area is a bitmap, as winmine's was.
