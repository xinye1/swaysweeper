# swaysweeper for Windows — design

*2026-10-11. Status: approved. Revised after an adversarial review (17 findings folded in);
Xinye took the recommendation on all five taste questions.*

A native Win32 version of swaysweeper: the same game as the Linux one, in C against the Win32 API
and GDI, shipped as one `.exe`. The Linux design
(`docs/specs/2026-10-09-swaysweeper-design.md`, with its colour/theme parts superseded) stays the
authority on **rules, geometry and look**. This document covers what's different on Windows and
how the two implementations are kept identical.

Sources: the reverse-engineered winmine at
[repnz/ReversingMinesweeper](https://github.com/repnz/ReversingMinesweeper), cited as `file.c:line`
under `Minesweeper/`, and Microsoft Learn for Win32.

## 0. Understanding

**Stated by Xinye**

- Make a Windows version and release it. The first release (`v0.1.0-beta.1`, Linux) is out.
- **Native Win32 rewrite**, chosen over bundling GTK with the Python code: a small exe with real
  Windows menus and dialogs, at the cost of a second codebase.
- Pre-release versioning: the Windows release is **`v0.1.0-beta.2`**.
- Classic colours only, as on Linux: Windows 95 with Color on, monochrome with Color off.

**Assumed**

- Windows 10 1703+ and 11, x86-64.
  - No ARM64 build, no installer, no code signing, so SmartScreen warns on first run, and the
    README says so.
  - "Dependency-free" means no DLLs beyond what Windows 10+ ships. The static UCRT64 build still
    uses the system UCRT.
- There's no Windows or Wine here, so the exe is built and exercised only on GitHub's Windows
  runner, as termtris is.
  - Everything that can be portable C is, so it builds and is tested on Linux with gcc.
  - The runner is 96 DPI with one monitor, so **DPI scaling, multi-monitor and Zoom fitting aren't
    verified by CI**. They wait for hands-on play.

**Success criteria**

- **Same rules, pixels, keys and session behaviour as Linux, proved rather than eyeballed.**
  - Scripted sessions are replayed through the C core and the Python implementation, then compared
    step by step and pixel by pixel (§5).
  - This runs against both the gcc/Linux build and the MinGW/Windows build of the core.
- **A static `swaysweeper.exe` that launches, plays, saves and resumes on a real Windows desktop**,
  exercised by an automated smoke test on the runner (§6).
- **Release `v0.1.0-beta.2` carries `swaysweeper-windows-x86_64.exe` and its `.sha256`**, built by
  a workflow from the tagged source.

## 1. Behaviour

Identical to Linux (Linux spec §1; §2 geometry; §5 resume semantics; §6 keyboard; §7 sounds),
except:

| | Linux | Windows |
|---|---|---|
| Menu bar | GTK popover menu | Native Win32 menu (`.rc`): the same items, check marks and radio dots |
| Dialogs | GTK windows, non-blocking | Native modal dialog templates (§3.6) |
| Minimise | n/a (sway has none) | **Pauses the timer and stops any sound**, as winmine does (§3.4) |
| Window position | sway places it | **Remembered** in `settings.ini` and kept on-screen (§3.3) |
| Scale | GTK logical pixels | Per-monitor DPI aware (§3.3) |
| State | `$XDG_STATE_HOME/swaysweeper/*.json` | `%LOCALAPPDATA%\swaysweeper\*.ini` (§3.5) |
| Sound | `pw-play`, WAV files cached | `PlaySoundW` from static in-memory WAV bytes |
| Second launch | GApplication presents the window | A named mutex: the second process brings the first window forward and exits (§3.8) |

The window:

- Title: `swaysweeper`.
- Styles: `WS_OVERLAPPED | WS_CAPTION | WS_SYSMENU | WS_MINIMIZEBOX`, which is caption, system
  menu, minimise box, no maximise and no sizing border, as in winmine (windowing.c:835).
- Class style 0, so double-clicks arrive as two presses (windowing.c:812).
- Client area: exactly the game area × scale.

Winmine does **not** pause on deactivation or while a menu is open (windowing.c:489-493, 524), so
neither does this.

## 2. Architecture

### 2.1 Python first: a GTK-free session layer

The Linux version keeps session logic inside GTK modules. That logic is exactly what `main.c` will
reimplement, so it moves into **`swaysweeper/session.py`** (no GTK), unchanged in behaviour, with
tests written first. It takes:

- the key → action map and cursor rules (view.py:107-133);
- motion hiding the cursor (view.py:91-93);
- the hit-testing of pointer events through `geometry.cell_at` / `on_face`;
- new game resetting the cursor and gesture mode (app.py:269-276);
- `app.act`'s consequences (app.py:206-302): status transitions, which sound plays (tick on
  READY→PLAYING, win, lose), best-time eligibility (`seconds < best`, standard levels only), and
  save-vs-delete of the game file;
- the face, pressed cells and cursor that a paint derives (view.py `_draw`).

Its interface is **events in, effects out**:

```
Session(settings, best, game)
  .press(button, px, py, shift, held)   .release(button, px, py, held)   .motion(px, py)
  .key(name)   .tick()   .new(game)
  -> [effects]: ("sound", name) ("best", level, seconds) ("save",) ("delete",)
                ("new_game",) ("show_keys",) ("unhandled",) ("redraw",)
  .paint_state() -> (face, pressed cells, cursor)
```

- Pointer coordinates are game-area pixels at ×1, so hit-testing is covered too. Off-board is
  just a coordinate outside the board.
- `("new_game",)` asks the host for a fresh random board. The host (or a parity script) supplies
  it with `.new(game)`.
- `app.py` and `view.py` become thin hosts over `Session`. The full existing suite must stay green.

**Key vocabulary** (canonical names, shared by both builds): `Left Right Up Down h j k l space
Return f c question`.

### 2.2 The C side

Everything lives under `win/`, in C11.

| File | Contents | Depends on |
|---|---|---|
| `win/core.h`, `win/core.c` | Board, game, gestures, geometry, **session** (§2.1), renderer into a 32-bit pixel buffer, WAV synthesis, state (de)serialisation, RNG. **No `windows.h`.** | C library, `-lm` |
| `win/sprites.h` | Generated sprite and colour tables. | — |
| `win/main.c` | Window, menu, message loop, input to `session`, timer, blit, dialogs, sound playback, files, DPI, single instance. | `core`, Win32 |
| `win/swaysweeper.rc` | Menu, accelerators, dialog templates, `VERSIONINFO`, icon, manifest. `#include "core.h"` for the version. | — |
| `win/swaysweeper.manifest` | Common Controls v6, PerMonitorV2 DPI awareness, `asInvoker`. | — |
| `win/swaysweeper.ico` | Generated (§2.3). | — |
| `win/replay.c` | Test driver: reads a script on stdin, drives `core`, prints effects, state and PPMs. | `core` |
| `win/test_core.c` | C unit tests for what replay doesn't cover. | `core` |
| `win/wintest.c` | Windows-only smoke test that drives the real exe (§6). | Win32 |
| `win/Makefile` | `make -C win` builds the exe; `make -C win test` builds and runs the portable tests with any `cc`. | — |
| `tools/gen_c_sprites.py` | Writes `win/sprites.h` and `win/swaysweeper.ico` from `sprites.py` and `colours.py`. | Python |

### 2.3 Single sources

**Art.** The sprites and both colour sets are defined once, in the Python package.
`win/sprites.h` and `win/swaysweeper.ico` are generated from them and committed, and a Python test
regenerates both in memory and fails if either differs. The icon images are:

- **16 px:** the 17 px face cropped to its centre 16.
- **20, 24 px:** the face on a transparent canvas.
- **32, 48 px:** the 16 and 24 px images doubled by nearest-neighbour.

**Version.**

- `win/core.h` defines `SWAYSWEEPER_VERSION` ("0.1.0-beta.2") and the numeric
  `SWAYSWEEPER_VERSION_NUM` (`0,1,0,2`) for `VERSIONINFO`.
- A Python test asserts that the string equals `swaysweeper.__version__`.
- The release workflow checks both against the tag.

## 3. Windows specifics

### 3.1 Rendering

`core` renders the game area at ×1 into a `uint32_t` buffer (`0x00RRGGBB`), the same way
`render.py` does.

- **Buffer:** allocated **once** at the largest game area (Custom 30×24: 504 × 451), so a
  difficulty change can't fail an allocation mid-game.
- **Blit:** `main.c` draws it with `StretchDIBits` at the integer scale.
- **Paint:** `WM_PAINT` and **`WM_PRINTCLIENT`** both perform the blit, so `PrintWindow` captures
  work.
- **No cell cache:** the area is small enough to re-render on every paint.

### 3.2 Input

**Mouse**

- `WM_{L,M,R}BUTTON{DOWN,UP}` and `WM_MOUSEMOVE` go to `session`, with coordinates from
  `GET_X_LPARAM`/`GET_Y_LPARAM` (never `LOWORD`; captured coordinates go negative) divided by the
  scale. XBUTTON messages are ignored.
- The held set comes from the message's `MK_*` flags.
  - Win32 down messages include the pressed button and up messages exclude it, the reverse of
    GTK's mask.
  - `Gestures.press`/`release` add and discard the button themselves (gestures.py:28-31, 54-57),
    so both conventions give the same result.
- **Release order:** `session.release`, then apply its effects, then `ReleaseCapture`.
  - `SetCapture` is taken on the first press.
  - `ReleaseCapture` itself sends `WM_CAPTURECHANGED`, so that message is ignored while a
    self-release flag is set.
  - Any other `WM_CAPTURECHANGED` resets the gesture state.
- **Activation click:** it plays. Unlike winmine, which drops the first press after a
  click-activation (windowing.c:495-538, 586-589), `WM_MOUSEACTIVATE` is left to `DefWindowProc`
  (`MA_ACTIVATE`), so the click that brings the window forward also acts, as on Linux.
- **Spurious motion:** a `WM_MOUSEMOVE` at an unchanged position is ignored. Windows synthesises
  these after dialogs close and on resize, and they'd wrongly hide the keyboard cursor.

**Keyboard**

- Arrows come from `WM_KEYDOWN`.
- `h j k l f c ?` and Space come from `WM_CHAR`.
- Enter comes from `WM_CHAR '\r'` only, which also covers numpad Enter.
- Both handlers ignore the key while `GetKeyState(VK_CONTROL) < 0`, matching Linux's
  Ctrl/Alt filter. Otherwise Ctrl+M (`'\r'`) would open a cell.
- Alt combinations (`WM_SYSCHAR`/`WM_SYSKEYDOWN`) go to `DefWindowProc`.
- `F2` (New) and Ctrl+Q (Exit) are accelerators, translated before `TranslateMessage`.

**Modal dialogs are never opened from inside an input handler.**

- A win that sets a best time saves the time first, then `PostMessage(WM_APP_WON)`.
- That handler opens Congratulations, after the gesture has finished and capture is released.
- After naming, the Fastest Mine Sweepers dialog is shown, as on Linux (app.py:257-260) and in
  winmine (game.c:324-325).
- The `?` key's Keys dialog is posted the same way.

### 3.3 Scale, Zoom and position

The process is PerMonitorV2 DPI-aware (manifest), so Windows never bitmap-stretches it.

**Scale**

- `base = max(1, (dpi + 48) / 96)` in integer arithmetic, i.e. rounded: 125 % gives ×1, 150 %
  and 175 % give ×2. Zoom ×2 covers anyone who finds ×1 small.
- `want = base × (zoom ? 2 : 1)`.
- `scale` = the largest integer ≤ `want` whose window fits the monitor's work area, minimum 1.

**Fitting** measures the outer window, from `AdjustWindowRectExForDpi` plus
`GetSystemMetricsForDpi`.

- Zoom ×2 is enabled only while `base × 2` fits.
- When it stops fitting (e.g. a laptop undocked), the item greys out and the game shows at
  `base`, **for this session only**: `settings.ini` keeps `zoom=2` and the greyed item keeps its
  check. ×2 comes back by itself once it fits again; the scale is recomputed on `WM_DPICHANGED`,
  `WM_DISPLAYCHANGE` and `WM_SETTINGCHANGE` (`SPI_SETWORKAREA`).

**`WM_GETDPISCALEDSIZE`** returns the exact size for the new DPI.

- `WM_DPICHANGED` then uses only the suggested rectangle's top-left, so a drag across monitors
  can't oscillate.

**Menu wrap guard**

- `AdjustWindowRectEx*` assumes a one-row menu.
- After each `SetWindowPos`, `GetClientRect` is checked and the height corrected once if the menu
  wrapped (cf. windowing.c:383-394).

**Position**

- Kept from `WM_WINDOWPOSCHANGED` (windowing.c:591-596), persisted as `x`/`y` in `settings.ini`.
- On a resize, the top-left stays put. On a resize or a load, the window is then clamped into the
  work area of `MonitorFromRect(…, MONITOR_DEFAULTTONEAREST)`, so a saved position on a monitor
  that's gone comes back on-screen (cf. windowing.c:400-428).

### 3.4 Timer and minimise

- `SetTimer` runs at 1000 ms while `game.ticking && !minimised`.
- **`minimised`** is a `main.c` flag driven by **`WM_SIZE`**:
  - `SIZE_MINIMIZED` sets it, kills the timer and stops sound (`PlaySoundW(NULL, …)`, as winmine's
    `FreeSound`, game.c:467).
  - `SIZE_RESTORED`, after being minimised, clears it.
- Not `WM_SYSCOMMAND`: a restore through `ShowWindow`, which the second-launch path uses, sends no
  `SC_RESTORE`.
- It's separate from `game.paused`:
  - restore doesn't clear a resume-from-disk pause, and input doesn't clear a minimise;
  - a game resumed from disk still starts paused until the first board input, exactly as on Linux.

### 3.5 State

`%LOCALAPPDATA%\swaysweeper\` holds `settings.ini`, `best.ini` and `game.ini`.

**Format**

- UTF-8 `key=value` lines.
- Split on the first `=`.
- A UTF-8 BOM and CRLF line ends are tolerated.
- Values are never escaped. Names can't contain a newline because the edit control is single-line.
- Written and parsed by `core`.

**Location**

- `LOCALAPPDATA` is read from the environment, falling back to
  `SHGetKnownFolderPath(FOLDERID_LocalAppData)`, so tests can redirect it.
- The mutex (§3.8) is taken **before** any state is loaded.

**Atomic writes**: a temp file in the same directory, `FlushFileBuffers`, then
`MoveFileExW(MOVEFILE_REPLACE_EXISTING | MOVEFILE_WRITE_THROUGH)`.

**Bad files**: an unreadable or invalid file is renamed `<name>.ini.bad` and defaults are used. The
game always starts.

**Validation**: the same rules `store.py` and `Game.from_dict` apply, worded as the code behaves.

- Unknown settings keys are ignored.
- Custom values are clamped (`clamp_custom`).
- Booleans are `0`/`1`. Zoom is `1`/`2`. Difficulty is a known level or `custom`.
- Best times are integers from 1 to 999. Names are truncated to 32 code points.
- Game: version 1; a known difficulty whose dimensions match (standard) or are already in range
  (custom); mines in bounds and unique; marks rows of the right size from `.F?#`; a known state;
  exploded ⊆ mines; seconds from 0 to 999.
- A position (`x`, `y`) is any integer pair; it's clamped on use (§3.3).
- The malformed-input list for tests is INI-specific: missing `=`, a non-integer, out of range, a
  wrong row length, an unknown mark char, an unknown state, exploded off a mine, and a wrong
  version.

**Names**: a typed name is stripped of surrounding whitespace, and an empty one becomes
`Anonymous` (dialogs.py:89). It's converted UTF-16 ⇄ UTF-8 at the dialog boundary.
`EM_SETLIMITTEXT(32)` counts UTF-16 units, which means ≤ 32 code points.

The file format is Windows-only; the two builds never share state.

### 3.6 Dialogs

Modal templates in `.rc`, in `DS_SHELLFONT` with `FONT 8, "MS Shell Dlg 2"` (Tahoma), true to
the period rather than Segoe UI.

- **Custom Field:** Height, Width and Mines edit boxes, OK and Cancel. Values are read with
  `GetDlgItemInt`; a failure (e.g. pasted non-digits, which `ES_NUMBER` doesn't block) counts as
  0. All three are then clamped by `clamp_custom`, never rejected (winmine's `GetDlgIntOfRange`,
  windowing.c:219-223).
- **Congratulations:** "You have the fastest time for <level> level. Please type your name:".
  - The edit box is prefilled `Anonymous`, all selected, 32-character limit.
  - Closing it any way records the typed name, as on Linux.
  - Opened via `WM_APP_WON` (§3.2); then Fastest Mine Sweepers is shown.
- **Fastest Mine Sweepers:** three rows of seconds and name, with Reset Scores and OK.
- **Keys:** the same text as Linux's Keys dialog.
- **About:** the name, the version, "The classic Windows Minesweeper.", the omasweeper credit, and
  MIT.

### 3.7 Sound

`core` synthesises the three WAVs (tick, win, lose) **byte-for-byte as `sound.write_wav` does**:

- `period = 22050.0 / hz`;
- a sample is high iff `fmod(i, period) < period / 2`;
- `(int)(22050 * seconds)` samples per note;
- the same double literals, and the standard 44-byte RIFF header that Python's `wave` writes;
- no `-ffast-math`.

The reviewer verified that an `fmod` build matches Python sample for sample.

- **Buffers:** static, built once at startup, alive for the process lifetime. `PlaySoundW(...,
  SND_MEMORY | SND_ASYNC | SND_NODEFAULT)` needs them to outlive playback.
- **Default:** sound is off by default.
- **Failure:** a failed play is silent.

### 3.8 Single instance

`CreateMutexW(L"Local\\io.github.xinye1.swaysweeper")` is taken first, before any state is loaded.

If the mutex already exists, the second process:

1. retries `FindWindowW` by class for up to 2 s, in case the first has no window yet;
2. calls `ShowWindowAsync(SW_RESTORE)` if the window is minimised;
3. calls `SetForegroundWindow`, which is allowed because the shell was foreground when it launched
   us;
4. exits.

### 3.9 RNG

- **Generator:** xorshift64*.
- **Seed:** `QueryPerformanceCounter` ^ process id, mixed through splitmix64 and forced nonzero.
- **Placement:** mines by partial Fisher–Yates over the W×H cells.
- The builds needn't share sequences: parity scripts supply explicit mines.

## 4. Build

**Toolchain**

- MinGW-w64 GCC: MSYS2 UCRT64 on the runner, or `x86_64-w64-mingw32-gcc` if installed locally
  (it isn't, today).

**Exe build**

- Flags: `-std=c11 -O2 -Wall -Wextra -pedantic -Werror -municode -mwindows`.
- Release adds `-static -s`.
- Links `winmm comctl32 shell32 ole32 uuid`; `-mwindows` brings `user32` and `gdi32`.
- Expected well under 1 MB.

**Portable build**

- `make -C win test` builds `replay` and `test_core` with plain `cc`, the same warning flags and
  `-lm`, and runs them.
- On Windows, `replay` sets stdout to binary mode (`_setmode(_fileno(stdout), _O_BINARY)`), so PPMs
  aren't corrupted, and it accepts CRLF scripts.

## 5. Parity testing (the core of the confidence)

`tests/test_win_parity.py`, run by `make test`, compiles `win/replay` with the system `cc`. If
there's no `cc`, it's skipped. It runs one set of scripts through the C replay and through
`swaysweeper.session`, and compares their output.

**Script commands**, one per line:

- `new <w> <h> <difficulty> <x,y;…>` — explicit mines. It also answers a pending `new_game`
  effect.
- `press <button> <px> <py> <shift> <held>`, `release <button> <px> <py> <held>`, `motion <px> <py>`
  — game-area pixels; `held` is a set like `1,3` or `-`.
- `key <name>` — from the vocabulary in §2.1.
- `tick`.
- `settings marks=<0|1> color=<0|1> sound=<0|1>`.
- `dump` — state.
- `render` — a PPM of the game area, taking face, pressed cells and cursor from the session.

**Compared**

- **Effects:** every effect list.
- **State:** each `dump` — marks rows, board state, exploded set, revealed count, counter, seconds,
  timer_running, paused, gesture mode, face, cursor.
- **Pixels:** each `render`, as a PPM compared byte-for-byte with the Python renderer's.
  - The Python side is `render.draw` to a Cairo `RGB24` surface, converted to PPM with the top
    byte masked.
  - Both colour sets are compared, via `settings color=`.
- **Serialisation:** a C round trip, plus validation rejects for the §3.5 list (in `test_core.c`).
- **WAV:** the bytes of each sound, from `replay`'s `wav <name>` command.

**Scripts**

- The existing Python test boards: walled, relocation, chord with wrong flags, one-click win, the
  −99 clamp, Custom clamps.
- A seeded random walk: a few hundred sessions of random gestures, keys, ticks and settings
  changes, generated in Python, replayed by both builds, and compared after every step.

**Both compilers**

- The Linux CI job runs the parity test with gcc.
- The Windows job runs it too, with `actions/setup-python`, `pip install pycairo` (it has Windows
  wheels) and MSYS2's gcc as `cc`.
- So the shipped compiler's `core` (UCRT `fmod` and `printf`) is checked, not just gcc's.

## 6. Windows smoke test (CI)

`win/wintest.c` runs on the Windows runner against the built exe, with `LOCALAPPDATA` redirected
to a temp directory. Before the first launch, wintest writes a **known** `settings.ini` (Beginner)
and `game.ini`: a fixed walled board, in progress, so every target cell is known and no click can
win or cascade.

1. Launches the exe and waits for its window by class. Checks the client size is the Beginner area
   × 1 (the runner is 96 DPI).
2. Captures with `PrintWindow` (served by `WM_PRINTCLIENT`) and checks:
   - the smiley's yellow;
   - a covered cell's bevel;
   - the restored marks.
3. Posts `WM_LBUTTONDOWN` and `WM_LBUTTONUP` back to back on a known safe cell, after
   `SetCursorPos` to it.
   - Checks the cell is revealed (grid line) and shows its expected number.
   - Checks the timer has advanced from the saved seconds by 0 to 2. The resumed timer starts on
     this input, and a tick may race the capture.
4. Posts `WM_RBUTTONDOWN` and `WM_RBUTTONUP` on another known cell, and checks the flag's red.
5. Sends `WM_CLOSE` and waits for exit.
   - Checks `game.ini` holds the new marks.
   - Relaunches and checks the same pixels come back.
6. Single-instance check: launches a second instance and checks it exits within 5 s, with the
   first still alive.
7. Closes the app and writes every capture as a BMP artifact for human inspection.

**First plan task: a spike** that creates a window on the runner, captures it and checks pixels.
It settles whether the runner's desktop paints and captures at all before anything depends on it.
If capture is impossible there, §6 falls back to message-level checks plus `game.ini` contents, and
the spec is amended.

## 7. CI and release

The repo has no CI today. It gets termtris's pattern.

**`ci.yml`**

- Gated: runs on a PR opened as ready or marked `ready_for_review`, and on `workflow_dispatch`.
  Never on every push.
- **linux** job:
  - `apt install python3-gi python3-cairo gir1.2-gtk-4.0`, then `make test`, which includes the
    parity tests.
- **windows** job (MSYS2 UCRT64 plus setup-python):
  - `make -C win test`;
  - the parity test (§5);
  - `make -C win`;
  - `wintest.exe swaysweeper.exe`;
  - upload the captures.

**`release.yml`** runs on `release: published`:

1. Checks the tag is `v` + `__version__` and `v` + `SWAYSWEEPER_VERSION`.
2. Builds the static, stripped exe.
3. Uploads `swaysweeper-windows-x86_64.exe` and its `.sha256` with `gh release upload`.

**The release**

- Bump both versions to `0.1.0-beta.2` and merge.
- Publish `v0.1.0-beta.2` as a pre-release.
- The notes name the SmartScreen warning and the checksum, and say that DPI, multi-monitor and feel
  haven't been tried by hand yet.

## 8. Error handling

- No path ends in a crash dialog.
- A failed state write is ignored, and the game goes on, as on Linux.
- A failed `PlaySoundW` is silent.
- A failed DIB allocation at startup shows a `MessageBoxW` and exits non-zero.
- Every Win32 call whose failure matters is checked.

## 9. Out of scope

- ARM64, 32-bit, an installer, MSI or winget, and code signing.
- Sharing state with the Linux build.
- High-contrast themes and screen readers. The game area is a bitmap, as winmine's was.
- Winmine's XYZZY cheat and its F4/F5/F6 keys (windowing.c:11, 707-765).
