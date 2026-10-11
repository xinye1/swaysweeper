# swaysweeper for Windows Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A native Win32 `swaysweeper.exe` that plays exactly like the Linux build, proved by replaying the same scripts through both, released as `v0.1.0-beta.2` with the exe and its checksum.

**Architecture:** First, the session logic that lives inside the GTK modules moves into a GTK-free `swaysweeper/session.py` (events in, effects out), and the GTK app becomes a thin host over it. `win/core.c` then ports board, game, gestures, geometry, session, renderer, sounds and INI state to portable C11 with no `windows.h`. A test driver, `win/replay.c`, and its Python twin, `tests/replay.py`, run one script each and must print the same lines and write the same PPM/WAV bytes. `win/main.c` is the Win32 shell around the core: window, menu, dialogs, timer, DPI, files and single instance. `win/wintest.c` drives the real exe on GitHub's Windows runner.

**Tech Stack:** C11 (gcc 16 on Linux; MinGW-w64 GCC from MSYS2 UCRT64 on the runner; zig 0.17 via `uvx` as a local compile-only check for the Win32 sources), Win32 API + GDI + winmm, `windres`; Python 3.14 (`/usr/bin/python3`) with pycairo for the reference side; GitHub Actions.

**Spec:** `docs/specs/2026-10-11-swaysweeper-windows-design.md` (approved 2026-10-11). The Linux spec `docs/specs/2026-10-09-swaysweeper-design.md` stays the authority on rules, geometry and look. Rules reference: [repnz/ReversingMinesweeper](https://github.com/repnz/ReversingMinesweeper).

## Global Constraints

- Work on branch `feat/windows` in `~/repos/swaysweeper` (it already holds the spec commits). Push with the SSH remote that's configured; never force-push.
- Python tests run with **`/usr/bin/python3`** (`make test`); the mise `python3` on PATH lacks `gi`.
- `swaysweeper/session.py`, `board.py`, `game.py`, `gestures.py`, `geometry.py`, `store.py`, `sound.py`, `colours.py`, `sprites.py` **must not import `gi`**.
- `win/core.c`, `win/core.h`, `win/replay.c`, `win/test_core.c` **must not include `windows.h`** (replay.c may include `io.h`/`fcntl.h` under `#ifdef _WIN32` only).
- C flags everywhere: `-std=c11 -O2 -Wall -Wextra -pedantic -Werror`. No `-ffast-math`. Win32 sources add `-DUNICODE -D_UNICODE -D_WIN32_WINNT=0x0A00 -DWINVER=0x0A00 -municode`.
- Exe links `-lwinmm -lcomctl32 -lshell32 -lole32 -luuid` (+ `-mwindows`); release adds `-static -s`.
- Window class and the `wintest` lookup: `swaysweeper`. Mutex: `Local\io.github.xinye1.swaysweeper`.
- State: `%LOCALAPPDATA%\swaysweeper\{settings,best,game}.ini`, `LOCALAPPDATA` read from the environment first. Bad file → `<name>.ini.bad`, defaults used.
- Generated files (`win/sprites.h`, `win/swaysweeper.ico`) are only ever written by `tools/gen_c_sprites.py`, never by hand.
- Version: `win/core.h` `SWAYSWEEPER_VERSION` always equals `swaysweeper.__version__`; both become `0.1.0-beta.2` only in Task 9. `SWAYSWEEPER_VERSION_NUM` is `major,minor,patch,beta`.
- CI is gated (`pull_request` types `opened, reopened, ready_for_review`, plus `workflow_dispatch`). During development only, `ci.yml` also runs on `push` to `feat/windows`; that trigger is deleted in Task 10 before the PR leaves draft.
- Commit after every task with a conventional message ending in:
  ```
  Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
  Claude-Session: https://claude.ai/code/session_014cXNm1YtXA8z8QgkySFjrB
  ```

## Review Focus

The inputs the spec implies that no rule-level parity script reaches on its own, most likely to bite first. Each has a test in its owning task.

1. **Minimised mid-game, then brought back by launching the exe again**: the timer must not count while minimised and must count again after the restore. *(Task 8: wintest "the timer stops while minimised", "the timer runs again after the restore".)*
2. **A press on the board, a drag off the window, a release out there**: nothing opens, the timer doesn't start, and the gesture is cleared. *(Task 2: `test_release_off_the_board_does_nothing`; Task 4: parity `test_drag_off_and_release`.)*
3. **A `settings.ini` hand-edited in Notepad** (UTF-8 BOM, CRLF line ends): it must load, not be moved aside. *(Task 6: `test_settings_tolerate_bom_and_crlf` in `test_core.c`.)*
4. **A corrupt `game.ini`**: the game still starts, on a fresh board, and the bad file is kept as `game.ini.bad`. *(Task 8: wintest "starts despite a corrupt game.ini", "the corrupt game.ini is moved aside".)*
5. **The largest Custom field (30×24, 667 mines) and the −99 counter clamp**: the buffer, the renderer and the LED text hold at the extremes. *(Task 4: parity `test_largest_custom_board`, `test_counter_clamps_at_minus_99`; Task 5: their pixel twins.)*

## Files

| File | Task | Responsibility |
|---|---|---|
| `swaysweeper/session.py` | 2 | Events in, effects out; the key text (`KEYS`). No GTK. |
| `swaysweeper/app.py`, `view.py`, `dialogs.py` | 2 | Thin GTK hosts over `Session`. |
| `swaysweeper/sprites.py` | 3 | Adds the public 17×17 `SMILEY` for the icon. |
| `tools/gen_c_sprites.py` | 3 | Writes `win/sprites.h` and `win/swaysweeper.ico`. |
| `win/sprites.h`, `win/swaysweeper.ico` | 3 | Generated, committed. |
| `win/core.h`, `win/core.c` | 4–6 | Portable core: rules, session, renderer, WAV, INI, RNG. |
| `win/replay.c`, `tests/replay.py` | 4–6 | Parity drivers, C and Python. |
| `win/test_core.c` | 4, 6 | C unit tests for what replay doesn't reach (INI, RNG, clamps). |
| `win/Makefile` | 4, 7, 8 | `test`, the exe, `wintest.exe`, `zigcheck`. |
| `tests/test_win_parity.py`, `tests/test_win_files.py` | 3–6 | Parity scripts; generated-file and version checks. |
| `win/resource.h`, `win/swaysweeper.rc`, `win/swaysweeper.manifest` | 7 | Menu, accelerators, dialogs, version, icon, manifest. |
| `win/main.c` | 7 | The Win32 shell. |
| `win/wintest.c` | 8 | Desktop smoke test on the runner. |
| `.github/workflows/ci.yml`, `release.yml` | 8, 9 | Gated CI; release asset upload. |
| `README.md`, `.gitignore`, `swaysweeper/__init__.py` | 9 | Windows section, build outputs, version bump. |

**Execution notes**

- Windows builds and runs happen only on GitHub's `windows-latest`. Locally, `make -C win zigcheck` compile-checks every Win32 source (and the `.rc`) with zig's mingw target; run it before every push that touches `win/`.
- Pushing to `feat/windows` triggers the spike workflow (Task 1) or `ci.yml` (Task 8 on). Watch runs with `gh run watch <id> --exit-status`; read failures with `gh run view <id> --log-failed`; captures with `gh run download <id> -n captures -D <scratch dir>`.

---
### Task 1: Spike — can the Windows runner paint, capture, click and run the Python side?

Throwaway. It answers four questions before anything depends on them, and leaves only a ledger entry behind:

1. Does `PrintWindow(…, PW_CLIENTONLY)` on the runner return what our `WM_PRINTCLIENT` paints?
2. Do posted `WM_LBUTTONDOWN`/`UP` reach the window, and does a repaint show in the next capture?
3. Does a posted `SC_MINIMIZE` minimise it?
4. Inside the MSYS2 shell with `path-type: inherit`, is setup-python's `python` first on PATH, does `pip install pycairo` work, and which of `cc`/`gcc` exist?

**Files:**
- Create (then delete in Step 6): `spike/app.c`, `spike/probe.c`, `.github/workflows/spike.yml`

**Interfaces:**
- Consumes: nothing.
- Produces: a ledger entry `Task 1: spike — capture <yes|no via PW_CLIENTONLY|yes via PW_RENDERFULLCONTENT>, click <yes|no>, minimise <yes|no>, python <path>, pycairo <version|fail>, cc <path|none>, gcc <path>, dpi <n>`. Task 8 reads it: if capture works only with `PW_RENDERFULLCONTENT` (value 2), `wintest.c`'s `shoot()` passes that flag instead; if no capture works at all, record `Ruling: wintest falls back to game.ini checks only` and drop the pixel checks in Task 8. If `pycairo` fails, record a ruling to run the parity test on Linux only and drop that step from the Windows job.

- [ ] **Step 1: Write the spike window**

`spike/app.c`:

```c
/* Spike: a fixed-size window that paints red via StretchDIBits, blue after a click. */
#include <windows.h>
#include <stdint.h>

static uint32_t px[168 * 211];

static void fill(uint32_t c)
{
    for (int i = 0; i < 168 * 211; i++)
        px[i] = c;
}

static void blit(HDC dc)
{
    BITMAPINFO bi;
    ZeroMemory(&bi, sizeof bi);
    bi.bmiHeader.biSize = sizeof bi.bmiHeader;
    bi.bmiHeader.biWidth = 168;
    bi.bmiHeader.biHeight = -211;
    bi.bmiHeader.biPlanes = 1;
    bi.bmiHeader.biBitCount = 32;
    bi.bmiHeader.biCompression = BI_RGB;
    StretchDIBits(dc, 0, 0, 168, 211, 0, 0, 168, 211, px, &bi, DIB_RGB_COLORS, SRCCOPY);
}

static LRESULT CALLBACK proc(HWND w, UINT m, WPARAM wp, LPARAM lp)
{
    switch (m) {
    case WM_PAINT: {
        PAINTSTRUCT ps;
        HDC dc = BeginPaint(w, &ps);
        blit(dc);
        EndPaint(w, &ps);
        return 0;
    }
    case WM_PRINTCLIENT:
        blit((HDC)wp);
        return 0;
    case WM_LBUTTONUP:
        fill(0x0000FF);
        InvalidateRect(w, NULL, FALSE);
        return 0;
    case WM_DESTROY:
        PostQuitMessage(0);
        return 0;
    }
    return DefWindowProcW(w, m, wp, lp);
}

int WINAPI wWinMain(HINSTANCE inst, HINSTANCE prev, PWSTR cmd, int show)
{
    (void)prev;
    (void)cmd;
    fill(0xFF0000);
    WNDCLASSW wc;
    ZeroMemory(&wc, sizeof wc);
    wc.lpfnWndProc = proc;
    wc.hInstance = inst;
    wc.lpszClassName = L"spike";
    RegisterClassW(&wc);
    DWORD style = WS_OVERLAPPED | WS_CAPTION | WS_SYSMENU | WS_MINIMIZEBOX;
    RECT r = {0, 0, 168, 211};
    AdjustWindowRect(&r, style, FALSE);
    HWND w = CreateWindowW(L"spike", L"spike", style, 100, 100, r.right - r.left,
                           r.bottom - r.top, NULL, NULL, inst, NULL);
    ShowWindow(w, show);
    MSG msg;
    while (GetMessageW(&msg, NULL, 0, 0) > 0) {
        TranslateMessage(&msg);
        DispatchMessageW(&msg);
    }
    return 0;
}
```

- [ ] **Step 2: Write the probe**

`spike/probe.c`:

```c
/* Spike: launch app.exe, capture it two ways, click it, minimise it. */
#include <windows.h>
#include <stdint.h>
#include <stdio.h>

static uint32_t grab(HWND w, UINT flags)
{
    RECT r;
    GetClientRect(w, &r);
    BITMAPINFO bi;
    ZeroMemory(&bi, sizeof bi);
    bi.bmiHeader.biSize = sizeof bi.bmiHeader;
    bi.bmiHeader.biWidth = r.right;
    bi.bmiHeader.biHeight = -r.bottom;
    bi.bmiHeader.biPlanes = 1;
    bi.bmiHeader.biBitCount = 32;
    bi.bmiHeader.biCompression = BI_RGB;
    HDC screen = GetDC(NULL), mem = CreateCompatibleDC(screen);
    void *bits = NULL;
    HBITMAP bmp = CreateDIBSection(mem, &bi, DIB_RGB_COLORS, &bits, NULL, 0);
    HGDIOBJ old = SelectObject(mem, bmp);
    BOOL ok = PrintWindow(w, mem, flags);
    GdiFlush();
    uint32_t value = ok && bits ? ((uint32_t *)bits)[10 * r.right + 10] & 0xFFFFFF : 0xDEAD;
    SelectObject(mem, old);
    DeleteObject(bmp);
    DeleteDC(mem);
    ReleaseDC(NULL, screen);
    printf("# PrintWindow(flags=%u) ok=%d client=%ldx%ld pixel(10,10)=%06X\n", flags, ok, r.right,
           r.bottom, value);
    return value;
}

int main(void)
{
    STARTUPINFOW si;
    PROCESS_INFORMATION pi;
    ZeroMemory(&si, sizeof si);
    ZeroMemory(&pi, sizeof pi);
    si.cb = sizeof si;
    wchar_t cmd[] = L"app.exe";
    if (!CreateProcessW(NULL, cmd, NULL, NULL, FALSE, 0, NULL, NULL, &si, &pi)) {
        printf("FAIL launch %lu\n", GetLastError());
        return 1;
    }
    HWND w = NULL;
    for (int i = 0; i < 100 && !w; i++) {
        Sleep(100);
        w = FindWindowW(L"spike", NULL);
    }
    printf("# window %p dpi %u visible %d\n", (void *)w, w ? GetDpiForWindow(w) : 0,
           w ? IsWindowVisible(w) : 0);
    if (!w)
        return 1;
    Sleep(500);
    uint32_t a = grab(w, 1), b = grab(w, 2);
    printf("%s - capture red (client-only %06X, full-content %06X)\n",
           a == 0xFF0000 || b == 0xFF0000 ? "ok" : "FAIL", a, b);
    PostMessageW(w, WM_LBUTTONDOWN, MK_LBUTTON, MAKELPARAM(20, 20));
    PostMessageW(w, WM_LBUTTONUP, 0, MAKELPARAM(20, 20));
    Sleep(500);
    a = grab(w, 1);
    b = grab(w, 2);
    printf("%s - click repaints blue (%06X, %06X)\n",
           a == 0x0000FF || b == 0x0000FF ? "ok" : "FAIL", a, b);
    PostMessageW(w, WM_SYSCOMMAND, SC_MINIMIZE, 0);
    Sleep(500);
    printf("%s - minimised\n", IsIconic(w) ? "ok" : "FAIL");
    PostMessageW(w, WM_CLOSE, 0, 0);
    printf("%s - closed\n", WaitForSingleObject(pi.hProcess, 5000) == WAIT_OBJECT_0 ? "ok" : "FAIL");
    return 0;
}
```

- [ ] **Step 3: Compile-check both locally with zig**

Run:
```bash
cd ~/repos/swaysweeper/spike
Z="uvx --from ziglang python -m ziglang cc -target x86_64-windows-gnu -std=c11 -Wall -Wextra -pedantic -Werror -DUNICODE -D_UNICODE -D_WIN32_WINNT=0x0A00"
$Z -municode -o /tmp/claude-1000/zapp.exe app.c && $Z -o /tmp/claude-1000/zprobe.exe probe.c -lgdi32 -luser32 && echo COMPILED
```
Expected: `COMPILED`, no warnings.

- [ ] **Step 4: Write the spike workflow**

`.github/workflows/spike.yml`:

```yaml
name: Spike
# Throwaway (plan Task 1): deleted once its answers are in the ledger.
on:
  push:
    branches: [feat/windows]
    paths: [spike/**, .github/workflows/spike.yml]
permissions:
  contents: read
jobs:
  windows:
    runs-on: windows-latest
    defaults:
      run:
        shell: msys2 {0}
    steps:
      - uses: actions/checkout@v5
        with:
          persist-credentials: false
      - uses: actions/setup-python@v6
        with:
          python-version: "3.13"
      - uses: msys2/setup-msys2@v2
        with:
          msystem: UCRT64
          update: false
          path-type: inherit
          install: mingw-w64-ucrt-x86_64-gcc make
      - name: Python and compilers as the parity test will see them
        run: |
          which python; python --version
          python -m pip install pycairo
          python -c "import cairo, shutil; print('pycairo', cairo.version, 'cc', shutil.which('cc'), 'gcc', shutil.which('gcc'))"
      - name: Desktop capture, click, minimise
        run: |
          cd spike
          gcc -std=c11 -O2 -Wall -Wextra -pedantic -Werror -DUNICODE -D_UNICODE -D_WIN32_WINNT=0x0A00 -municode -mwindows -o app.exe app.c
          gcc -std=c11 -O2 -Wall -Wextra -pedantic -Werror -DUNICODE -D_UNICODE -D_WIN32_WINNT=0x0A00 -o probe.exe probe.c -lgdi32
          ./probe.exe
```

- [ ] **Step 5: Push and read the run**

Run:
```bash
cd ~/repos/swaysweeper
git add spike .github/workflows/spike.yml
git commit -m "chore(spike): probe the Windows runner's desktop (throwaway)" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_014cXNm1YtXA8z8QgkySFjrB"
git push
sleep 5; RUN=$(gh run list --branch feat/windows --workflow spike.yml --limit 1 --json databaseId -q '.[0].databaseId')
gh run watch "$RUN" --exit-status; gh run view "$RUN" --log | grep -E 'ok -|FAIL|# |pycairo|python|Python' | head -40
```
Expected: four `ok -` lines (capture, click, minimise, closed), a `pycairo` line with a version and compiler paths. Any `FAIL` is an answer, not an error: record it.

- [ ] **Step 6: Record the answers and remove the spike**

Write the ledger entry described under **Produces** (the workspace ledger from superpowers:executing-plans), then:

```bash
cd ~/repos/swaysweeper
git rm -r -q spike .github/workflows/spike.yml
git commit -m "chore(spike): remove the runner probe; answers are in the plan ledger" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_014cXNm1YtXA8z8QgkySFjrB"
git push
```
Expected: the push triggers nothing (no workflow matches).

---
### Task 2: `session.py` — the GTK-free session layer, and the GTK app on top of it

Spec §2.1. Behaviour doesn't change; it moves. `view.py`'s key/cursor/motion rules and `app.py`'s `act`/`_status_changed`/`_won`/tick consequences become `Session`, which returns effects; `app.py` applies them.

**Files:**
- Create: `swaysweeper/session.py`, `tests/test_session.py`
- Modify: `swaysweeper/app.py` (`__init__`, play and timer sections), `swaysweeper/view.py` (whole file), `swaysweeper/dialogs.py:8-22` (`KEYS` moves out)

**Interfaces:**
- Consumes: `Game`, `Board`, `Gestures`, `geometry.layout/cell_at/on_face`, unchanged.
- Produces (Tasks 4–6 port it; `tests/replay.py` drives it):
  - `Session(game, settings, best)`: `settings` is the host's dict (reads `"marks"`, `"sound"`), `best` the host's `{level: [seconds, name]}`, both shared, not copied. `game` may be `None` until the first `new()`.
  - `.press(button, px, py, shift=False, held=None) -> list`, `.release(button, px, py, held=None) -> list`, `.motion(px, py) -> list`, `.key(name) -> list`, `.tick() -> list`, `.new(game) -> list`, `.paint_state() -> (face, pressed frozenset, cursor or None)`.
  - Attributes read by hosts and the replay: `.game`, `.gestures` (its `.mode`), `.cursor`.
  - Effects: `("save",)`, `("delete",)`, `("sound", "tick"|"win"|"lose")`, `("best", level, seconds)`, `("new_game",)`, `("show_keys",)`, `("unhandled",)`, `("redraw",)`.
  - `session.KEYS`: the Keys dialog text (moved from `dialogs.py`).
  - `App.session`, `App.apply(effects, sync=True)`; `App.game` and `App.best` become properties over the session.

- [ ] **Step 1: Write the failing tests**

`tests/test_session.py`:

```python
import unittest

from swaysweeper import geometry as G
from swaysweeper.board import FLAG, QUESTION, REVEALED, Board
from swaysweeper.game import Game
from swaysweeper.session import KEYS, Session


def centre(x, y):
    """Game-area pixel in the middle of board square (x, y)."""
    return G.BOARD_X + G.CELL * x + 8, G.BOARD_Y + G.CELL * y + 8


def walled():
    # A wall of mines down x = 4 (and one at 8,8): opening (0, 0) floods
    # x = 0..3 and stops; (3, 4) is a 3.
    return Game("beginner", Board(9, 9, [(4, y) for y in range(9)] + [(8, 8)]))


def one_click_win():
    return Game("beginner", Board(9, 9, [(8, 8)]))


def session(game=None, sound=False, marks=True):
    settings = {"marks": marks, "sound": sound, "color": True}
    best = {level: [999, "Anonymous"] for level in ("beginner", "intermediate", "expert")}
    return Session(game or walled(), settings, best)


def click(s, x, y, button=1):
    px, py = centre(x, y)
    return s.press(button, px, py, held=frozenset()) + s.release(button, px, py, held={button})


class Pointer(unittest.TestCase):
    def test_left_click_opens_and_saves(self):
        s = session()
        self.assertEqual(click(s, 0, 0), [("redraw",), ("save",), ("redraw",)])
        self.assertEqual(s.game.board.marks[0][0], REVEALED)

    def test_first_open_ticks_when_sound_is_on(self):
        s = session(sound=True)
        px, py = centre(0, 0)
        s.press(1, px, py, held=frozenset())
        self.assertEqual(s.release(1, px, py, held={1}),
                         [("save",), ("sound", "tick"), ("redraw",)])

    def test_right_press_marks_without_starting_the_game(self):
        s = session()
        self.assertEqual(s.press(3, *centre(2, 2), held=frozenset()), [("delete",), ("redraw",)])
        self.assertEqual(s.game.board.marks[2][2], FLAG)

    def test_marks_setting_is_read_live(self):
        s = session()
        s.press(3, *centre(2, 2), held=frozenset())
        s.release(3, *centre(2, 2), held={3})
        s.settings["marks"] = False
        s.press(3, *centre(2, 2), held=frozenset())
        self.assertNotEqual(s.game.board.marks[2][2], QUESTION)

    def test_release_off_the_board_does_nothing(self):
        s = session()
        s.press(1, *centre(0, 0), held=frozenset())
        s.motion(-20, -20)
        self.assertEqual(s.release(1, -20, -20, held={1}), [("redraw",)])
        self.assertEqual(s.game.status, "ready")
        self.assertIsNone(s.gestures.mode)

    def test_face_click_asks_for_a_new_game(self):
        s = session()
        fx, fy = G.layout(9, 9).face_x + 12, G.FACE_Y + 12
        s.press(1, fx, fy, held=frozenset())
        self.assertEqual(s.paint_state()[0], "pressed")
        self.assertEqual(s.release(1, fx, fy, held={1}), [("new_game",), ("redraw",)])

    def test_holding_left_shows_wow_and_the_pressed_square(self):
        s = session()
        s.press(1, *centre(3, 3), held=frozenset())
        self.assertEqual(s.paint_state(), ("wow", frozenset({(3, 3)}), None))


class Motion(unittest.TestCase):
    def test_motion_over_a_square_hides_the_cursor(self):
        s = session()
        s.key("Left")
        self.assertEqual(s.motion(*centre(1, 1)), [("redraw",)])
        self.assertIsNone(s.cursor)

    def test_idle_motion_needs_no_redraw(self):
        self.assertEqual(session().motion(*centre(1, 1)), [])

    def test_motion_off_the_board_keeps_the_cursor(self):
        s = session()
        s.key("Left")
        self.assertEqual(s.motion(1, 1), [])
        self.assertEqual(s.cursor, (4, 4))


class Keys(unittest.TestCase):
    def test_first_arrow_places_the_cursor_in_the_middle(self):
        s = session()
        self.assertEqual(s.key("Right"), [("redraw",)])
        self.assertEqual(s.cursor, (4, 4))

    def test_arrows_and_hjkl_move_and_stop_at_the_edge(self):
        s = session()
        s.key("Up")
        for name in ("h", "h", "h", "h", "h", "k"):
            s.key(name)
        self.assertEqual(s.cursor, (0, 3))
        for name in ("l", "j", "Down"):
            s.key(name)
        self.assertEqual(s.cursor, (1, 5))

    def test_question_shows_the_keys(self):
        self.assertEqual(session().key("question"), [("show_keys",)])

    def test_open_keys_need_a_cursor(self):
        self.assertEqual(session().key("space"), [("unhandled",)])

    def test_space_opens_a_square(self):
        s = session()
        s.key("Left")
        s.key("h")                                    # (3, 4)
        self.assertEqual(s.key("space"), [("save",), ("redraw",)])
        self.assertEqual(s.game.board.marks[4][3], REVEALED)

    def test_return_on_an_open_number_chords(self):
        s = session()
        s.key("Left")
        s.key("h")
        s.key("space")
        for y in (3, 4, 5):
            s.game.mark(4, y, True)
        s.key("Return")
        self.assertEqual(s.game.board.marks[4][0], REVEALED)

    def test_f_marks_and_c_on_a_flag_still_starts_the_timer(self):
        s = session()
        s.key("Left")
        s.key("h")
        s.key("f")
        self.assertEqual(s.game.board.marks[4][3], FLAG)
        self.assertEqual(s.key("c"), [("save",), ("redraw",)])
        self.assertEqual(s.game.status, "playing")

    def test_unknown_key_with_a_cursor_is_unhandled(self):
        s = session()
        s.key("Left")
        self.assertEqual(s.key("x"), [("unhandled",)])

    def test_keys_text_names_the_bindings(self):
        for binding in ("F2", "Ctrl+Q", "h j k l"):
            self.assertIn(binding, KEYS)


class Outcomes(unittest.TestCase):
    def test_a_win_records_a_best_time_as_anonymous(self):
        s = session(one_click_win(), sound=True)
        px, py = centre(0, 0)
        s.press(1, px, py, held=frozenset())
        self.assertEqual(s.release(1, px, py, held={1}),
                         [("delete",), ("sound", "win"), ("best", "beginner", 1), ("redraw",)])
        self.assertEqual(s.best["beginner"], [1, "Anonymous"])

    def test_a_slower_win_is_not_a_best_time(self):
        s = session(one_click_win())
        s.best["beginner"] = [1, "Ada"]
        self.assertNotIn(("best", "beginner", 1), click(s, 0, 0))
        self.assertEqual(s.best["beginner"], [1, "Ada"])

    def test_custom_wins_never_count(self):
        s = session(Game("custom", Board(9, 9, [(8, 8)])))
        self.assertEqual([e for e in click(s, 0, 0) if e[0] == "best"], [])

    def test_a_loss_plays_lose(self):
        s = session(sound=True)
        click(s, 0, 0)
        px, py = centre(4, 0)
        s.press(1, px, py, held=frozenset())
        self.assertEqual(s.release(1, px, py, held={1}),
                         [("delete",), ("sound", "lose"), ("redraw",)])


class Timer(unittest.TestCase):
    def test_tick_saves_and_redraws_while_running(self):
        s = session()
        click(s, 0, 0)
        self.assertEqual(s.tick(), [("save",), ("redraw",)])
        self.assertEqual(s.game.seconds, 2)

    def test_tick_plays_when_sound_is_on(self):
        s = session(sound=True)
        click(s, 0, 0)
        self.assertEqual(s.tick(), [("save",), ("sound", "tick"), ("redraw",)])

    def test_no_tick_before_the_first_click(self):
        self.assertEqual(session().tick(), [])

    def test_the_timer_stops_at_999(self):
        s = session()
        click(s, 0, 0)
        s.game.seconds = 999
        self.assertEqual(s.tick(), [])


class NewGame(unittest.TestCase):
    def test_new_resets_cursor_and_gesture(self):
        s = session()
        s.key("Left")
        s.press(1, *centre(0, 0), held=frozenset())
        fresh = walled()
        self.assertEqual(s.new(fresh), [("delete",), ("redraw",)])
        self.assertIs(s.game, fresh)
        self.assertIsNone(s.cursor)
        self.assertIsNone(s.gestures.mode)

    def test_a_session_can_start_without_a_game(self):
        s = Session(None, {"marks": True, "sound": False}, {})
        s.new(walled())
        self.assertEqual(s.game.difficulty, "beginner")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run them to verify they fail**

Run: `cd ~/repos/swaysweeper && /usr/bin/python3 -m unittest tests.test_session -v 2>&1 | tail -3`
Expected: `ModuleNotFoundError: No module named 'swaysweeper.session'`.

- [ ] **Step 3: Write `swaysweeper/session.py`**

Move `KEYS` here verbatim from `dialogs.py:8-22`:

```python
"""One game window's play, minus the toolkit: events in, effects out. No GTK.

app.py and view.py host it on Linux; win/core.c ports it for Windows, and
tests/test_win_parity.py replays the same scripts through both.

Pointer coordinates are game-area pixels at zoom 1. Key names are
`Left Right Up Down h j k l space Return f c question`; anything else is
unhandled. Effects come back in the order a host applies them:

  ("save",) | ("delete",)   write the game file, or remove it (not PLAYING)
  ("sound", name)           tick, win or lose; only with Sound on
  ("best", level, seconds)  a new best time, already recorded as Anonymous
  ("new_game",)             build a fresh Game and pass it to new()
  ("show_keys",)            open the Keys dialog
  ("unhandled",)            a key this session doesn't use
  ("redraw",)               repaint
"""

from . import geometry as G
from .board import LOST, PLAYING, READY, REVEALED, WON
from .game import DIFFICULTIES
from .gestures import Gestures

KEYS = """Mouse
  Left click             open a square
  Right click            flag, then ?, then clear
  Both buttons, middle,  open around a satisfied number
  or Shift+left
  Smiley                 new game

Keyboard
  Arrows or h j k l      move the cursor
  Space or Enter         open (around a number: chord)
  f                      flag, then ?, then clear
  c                      open around a number
  F2                     new game
  ?                      this list
  Ctrl+Q                 exit"""

MOVES = {"Left": (-1, 0), "h": (-1, 0), "Right": (1, 0), "l": (1, 0),
         "Up": (0, -1), "k": (0, -1), "Down": (0, 1), "j": (0, 1)}


class Session:
    def __init__(self, game, settings, best):
        """`settings` and `best` are the host's dicts, shared, not copied."""
        self.game = game
        self.settings = settings
        self.best = best
        self.gestures = Gestures()
        self.cursor = None

    # --- events --------------------------------------------------------------

    def press(self, button, px, py, shift=False, held=None):
        cell, face = self._hit(px, py)
        return self._run(self.gestures.press(button, cell, face, shift=shift,
                                             active=not self.game.board.over, held=held))

    def release(self, button, px, py, held=None):
        cell, face = self._hit(px, py)
        return self._run(self.gestures.release(button, cell, face, held=held))

    def motion(self, px, py):
        cell, face = self._hit(px, py)
        self.gestures.motion(cell, face)
        had_cursor = self.cursor is not None
        if cell is not None:
            self.cursor = None
        if self.gestures.mode or (had_cursor and self.cursor is None):
            return [("redraw",)]
        return []

    def key(self, name):
        b = self.game.board
        if name in MOVES:
            if self.cursor is None:
                self.cursor = (b.width // 2, b.height // 2)
            else:
                dx, dy = MOVES[name]
                x, y = self.cursor
                self.cursor = (min(max(x + dx, 0), b.width - 1),
                               min(max(y + dy, 0), b.height - 1))
            return [("redraw",)]
        if name == "question":
            return [("show_keys",)]
        if self.cursor is None:
            return [("unhandled",)]
        x, y = self.cursor
        if name in ("space", "Return"):
            kind = "chord" if b.marks[y][x] == REVEALED else "reveal"
        elif name == "f":
            kind = "mark"
        elif name == "c":
            kind = "chord"
        else:
            return [("unhandled",)]
        return self._run([(kind, x, y)])

    def tick(self):
        if not self.game.tick():
            return []
        return [("save",)] + self._sound("tick") + [("redraw",)]

    def new(self, game):
        self.game = game
        self.cursor = None
        self.gestures.mode = None
        return [("delete",), ("redraw",)]

    def paint_state(self):
        b = self.game.board
        return (self.gestures.face(self.game.status),
                self.gestures.preview(b.width, b.height), self.cursor)

    # --- internals -----------------------------------------------------------

    def _hit(self, px, py):
        b = self.game.board
        lay = G.layout(b.width, b.height)
        return G.cell_at(lay, px, py), G.on_face(lay, px, py)

    def _run(self, actions):
        effects = []
        for action in actions:
            effects += self._act(action)
        return effects + [("redraw",)]

    def _sound(self, name):
        return [("sound", name)] if self.settings["sound"] else []

    def _act(self, action):
        if action[0] == "new":
            return [("new_game",)]
        kind, x, y = action
        game = self.game
        before = game.status
        if kind == "mark":
            game.mark(x, y, self.settings["marks"])
        else:
            game.release(x, y, chord=kind == "chord")
        after = game.status
        effects = [("save",) if after == PLAYING else ("delete",)]
        if before == after:
            return effects
        if before == READY and after == PLAYING:
            effects += self._sound("tick")
        elif after == WON:
            effects += self._sound("win")
        elif after == LOST:
            effects += self._sound("lose")
        if after == WON:
            level, seconds = game.difficulty, game.seconds
            if level in DIFFICULTIES and seconds < self.best[level][0]:
                self.best[level] = [seconds, "Anonymous"]
                effects.append(("best", level, seconds))
        return effects
```

- [ ] **Step 4: Run the session tests**

Run: `/usr/bin/python3 -m unittest tests.test_session -v 2>&1 | tail -3`
Expected: `OK` (29 tests).

- [ ] **Step 5: Make `dialogs.py` import the text**

Replace `dialogs.py:8-22` (the `KEYS = """…"""` block) with nothing, and change the imports to:

```python
from . import __version__
from .game import DIFFICULTIES, clamp_custom
from .session import KEYS
```

- [ ] **Step 6: Rewrite `view.py` as a thin host**

Replace the whole file with:

```python
"""The board widget: paints the session, turns raw input into session events."""

import cairo
import gi

gi.require_version("Gdk", "4.0")
gi.require_version("Graphene", "1.0")
gi.require_version("Gtk", "4.0")
from gi.repository import Gdk, Graphene, Gtk  # noqa: E402

from . import geometry as G  # noqa: E402
from . import render  # noqa: E402
from .colours import rgb  # noqa: E402

_MASKS = ((Gdk.ModifierType.BUTTON1_MASK, 1), (Gdk.ModifierType.BUTTON2_MASK, 2),
          (Gdk.ModifierType.BUTTON3_MASK, 3))
_INPUT = (Gdk.EventType.BUTTON_PRESS, Gdk.EventType.BUTTON_RELEASE,
          Gdk.EventType.MOTION_NOTIFY)
_KEY_NAMES = {"KP_Enter": "Return"}


class BoardView(Gtk.DrawingArea):
    def __init__(self, app):
        super().__init__()
        self.app = app
        self.cache = render.CellCache()
        self.set_focusable(True)
        self.set_draw_func(self._draw)
        # Legacy, not GestureClick: a click gesture ignores a second button
        # pressed while the first is held, and that IS the chord.
        legacy = Gtk.EventControllerLegacy()
        legacy.connect("event", self._event)
        self.add_controller(legacy)

    # --- geometry ------------------------------------------------------------

    def _layout(self):
        b = self.app.game.board
        return G.layout(b.width, b.height)

    def _origin(self):
        lay, z = self._layout(), self.app.zoom
        ox = max(0, (self.get_width() - lay.width * z) // 2)
        oy = max(0, (self.get_height() - lay.height * z) // 2)
        return ox, oy, z, lay

    def resize(self):
        lay, z = self._layout(), self.app.zoom
        self.set_content_width(lay.width * z)
        self.set_content_height(lay.height * z)
        self.queue_draw()

    def _surface_to_widget(self, sx, sy):
        native = self.get_native()
        nx, ny = native.get_surface_transform()
        ok, p = native.compute_point(self, Graphene.Point().init(sx - nx, sy - ny))
        return (p.x, p.y) if ok else (-1.0, -1.0)

    def _game_point(self, sx, sy):
        wx, wy = self._surface_to_widget(sx, sy)
        ox, oy, z, _lay = self._origin()
        return (wx - ox) / z, (wy - oy) / z

    # --- input ---------------------------------------------------------------

    def _event(self, controller, _event):
        # PyGObject hands this signal's GdkEvent over as None; the controller
        # still has it.
        event = controller.get_current_event()
        if event is None:
            return False
        kind = event.get_event_type()
        if kind not in _INPUT:
            return False
        ok, sx, sy = event.get_position()
        if not ok:
            return False
        px, py = self._game_point(sx, sy)
        session = self.app.session
        if kind == Gdk.EventType.MOTION_NOTIFY:
            self.app.apply(session.motion(px, py))
            return False
        button = event.get_button()
        state = event.get_modifier_state()
        held = frozenset(b for mask, b in _MASKS if state & mask)
        if kind == Gdk.EventType.BUTTON_PRESS:
            self.grab_focus()
            effects = session.press(button, px, py,
                                    shift=bool(state & Gdk.ModifierType.SHIFT_MASK), held=held)
        else:
            effects = session.release(button, px, py, held=held)
        self.app.apply(effects)
        return True

    def key(self, keyval, state):
        if state & (Gdk.ModifierType.CONTROL_MASK | Gdk.ModifierType.ALT_MASK):
            return False
        name = Gdk.keyval_name(keyval)
        effects = self.app.session.key(_KEY_NAMES.get(name, name))
        self.app.apply(effects)
        return ("unhandled",) not in effects

    # --- paint ---------------------------------------------------------------

    def _draw(self, _area, cr, _width, _height):
        ox, oy, z, _lay = self._origin()
        colours = self.app.colours
        cr.set_antialias(cairo.ANTIALIAS_NONE)
        cr.set_source_rgb(*rgb(colours["backdrop"]))
        cr.paint()
        cr.translate(ox, oy)
        cr.scale(z, z)
        face, pressed, cursor = self.app.session.paint_state()
        render.draw(cr, self.app.game, colours, pressed=pressed, face=face,
                    cursor=cursor, cache=self.cache)
```

- [ ] **Step 7: Make `app.py` apply effects**

(a) Imports: add `from .session import Session` after the `.game` import, and drop `LOST, READY, WON` from the `.board` import (keep `PLAYING`).

(b) Replace `__init__`'s body from `self.best = …` through `self.game = self._fresh()` (app.py:26-37) with:

```python
        best = self.store.load("best", store.best_from) or store.default_best()
        self.sound = Sound(Path(GLib.get_user_cache_dir()) / "swaysweeper")
        saved = self.store.load("game", Game.from_dict)
        if saved is not None and saved.status == PLAYING:
            game = saved
            self.settings["difficulty"] = saved.difficulty
            if saved.difficulty == "custom":
                b = saved.board
                self.settings["custom"] = [b.width, b.height, b.mine_count]
        else:
            self.store.delete("game")
            game = self._fresh()
        self.session = Session(game, self.settings, best)
```

(c) Add to the `derived` section:

```python
    @property
    def game(self):
        return self.session.game

    @property
    def best(self):
        return self.session.best

    @best.setter
    def best(self, value):
        self.session.best = value
```

(d) Replace `act`, `_status_changed`, `_won` and `new_game` (app.py:208-263) with:

```python
    def apply(self, effects, sync=True):
        for effect in effects:
            kind = effect[0]
            if kind == "save":
                self._save("game", self.game.to_dict())
            elif kind == "delete":
                self.store.delete("game")
            elif kind == "sound":
                self.sound.play(effect[1])
            elif kind == "best":
                self._best_time(effect[1])
            elif kind == "new_game":
                self.new_game()
            elif kind == "show_keys":
                self.activate_action("keys", None)
            elif kind == "redraw" and self.view is not None:
                self.view.queue_draw()
        if sync:
            self._sync_timer()

    def _best_time(self, level):
        # Already recorded as Anonymous by the session, so closing the window
        # mid-dialog can never lose the time; the dialog only names it.
        self._save("best", self.best)

        def named(name):
            self.best[level][1] = name
            self._save("best", self.best)
            self._show_best()

        dialogs.fastest_time(self.window, level, named)

    def new_game(self):
        self.apply(self.session.new(self._fresh()))
        self._apply_size()
```

(e) Replace `_tick` (app.py:275-285) with:

```python
    def _tick(self):
        self.apply(self.session.tick(), sync=False)
        if not self.game.ticking:
            self._timer = 0
            return GLib.SOURCE_REMOVE
        return GLib.SOURCE_CONTINUE
```

(f) Delete `_save_game` (app.py:295-299); nothing calls it now.

- [ ] **Step 8: Run the whole suite and a live smoke**

Run:
```bash
cd ~/repos/swaysweeper && make test 2>&1 | tail -3
grep -n "_save_game\|reset_cursor\|view.gestures\|view.cursor\|\.act(" swaysweeper/*.py
timeout 4 /usr/bin/python3 -m swaysweeper; echo "exit $?"
```
Expected: `OK`; the grep prints nothing; `exit 124` (the window ran for 4 s without a traceback). If there is no `__main__`, use `timeout 4 bin/swaysweeper`.

- [ ] **Step 9: Commit**

```bash
git add swaysweeper/session.py swaysweeper/app.py swaysweeper/view.py swaysweeper/dialogs.py tests/test_session.py
git commit -m "refactor: move session logic into GTK-free session.py" -m "Events in, effects out, so win/core.c can port it and the parity tests
can replay one script through both. Behaviour is unchanged.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_014cXNm1YtXA8z8QgkySFjrB"
```

---
### Task 3: Generated art — `win/sprites.h` and `win/swaysweeper.ico`

Spec §2.3. The sprites, both colour sets and the Keys text are defined once in Python; the C build gets generated copies, and a test fails when a copy is stale.

**Files:**
- Modify: `swaysweeper/sprites.py:228-251` (factor out the 17×17 face; add `SMILEY`)
- Create: `tools/gen_c_sprites.py`, `tests/test_win_files.py`, `win/sprites.h` (generated), `win/swaysweeper.ico` (generated)

**Interfaces:**
- Consumes: `colours.SLOTS/WIN95/MONO`, `sprites.LEGEND/CELLS/FACES/LED`, `session.KEYS`.
- Produces (core.c includes `sprites.h`; Tasks 5 and 7 use these names):
  - `enum { SLOT_FACE, SLOT_LIGHT, …, SLOT_NUM8, SLOT_COUNT }` in `colours.SLOTS` order.
  - `static const uint32_t PALETTE_WIN95[SLOT_COUNT]`, `PALETTE_MONO[SLOT_COUNT]` (`0x00RRGGBB`).
  - `static const unsigned char LEGEND[128]`: art char → slot + 1, 0 = transparent.
  - `typedef struct { int w, h; const char *px; } Sprite;` and `static const Sprite SPRITES[SPR_COUNT]` with `enum { SPR_OPEN1 … SPR_OPEN8, SPR_MINE, SPR_FLAG, SPR_QUESTION, SPR_CROSS, SPR_FACE_NORMAL, SPR_FACE_WOW, SPR_FACE_DEAD, SPR_FACE_COOL, SPR_FACE_PRESSED, SPR_LED_0 … SPR_LED_9, SPR_LED_MINUS, SPR_COUNT }`.
  - `static const char KEYS_TEXT[]`.
  - `win/swaysweeper.ico`: 16, 20, 24, 32, 48 px, 32-bit BMP entries.
  - `sprites.SMILEY`: the 17×17 normal face, list of 17 strings.

- [ ] **Step 1: Write the failing tests**

`tests/test_win_files.py`:

```python
"""Files the Windows build takes from the Python package stay in step with it."""

import importlib.util
import struct
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REGENERATE = "stale: run /usr/bin/python3 tools/gen_c_sprites.py"


def generator():
    spec = importlib.util.spec_from_file_location("gen_c_sprites",
                                                  ROOT / "tools" / "gen_c_sprites.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class Generated(unittest.TestCase):
    def test_sprites_header_is_current(self):
        self.assertEqual((ROOT / "win" / "sprites.h").read_text(), generator().header_text(),
                         REGENERATE)

    def test_icon_is_current(self):
        self.assertEqual((ROOT / "win" / "swaysweeper.ico").read_bytes(), generator().ico_bytes(),
                         REGENERATE)

    def test_icon_has_the_five_sizes(self):
        data = generator().ico_bytes()
        _reserved, kind, count = struct.unpack_from("<HHH", data)
        self.assertEqual((kind, count), (1, 5))
        self.assertEqual([data[6 + 16 * i] for i in range(count)], [16, 20, 24, 32, 48])

    def test_icon_corners_are_transparent_and_the_face_is_yellow(self):
        images = generator().icon_images()
        for image in images:
            self.assertEqual(image[0][0][3], 0)
        big = images[-1]                       # 48 px: the 24 px canvas doubled
        self.assertEqual(big[24][24], (0xff, 0xff, 0x00, 255))


if __name__ == "__main__":
    unittest.main()
```

The 48 px check: the 24 px canvas puts the 17 px face at offset 3, so pixel (12, 12) of the 24 px image is face pixel (9, 9), inside the yellow (row 9 of the circle is `"SYYYYYYYYYYYYYYYS"`, no feature on row 9 of `normal`); doubled, that's (24, 24).

- [ ] **Step 2: Run them to verify they fail**

Run: `cd ~/repos/swaysweeper && /usr/bin/python3 -m unittest tests.test_win_files 2>&1 | tail -3`
Expected: errors with `FileNotFoundError` for `tools/gen_c_sprites.py`.

- [ ] **Step 3: Expose the bare face in `sprites.py`**

Replace `_face` (sprites.py:228-247) and the two `FACES` lines after it with:

```python
def _smiley(features):
    face = _stamp(_blank(17, 17), _CIRCLE, 0, 0)
    for row, art in features:
        _stamp(face, [art], 0, row)
    return _rows(face)


def _face(features, pressed):
    grid = [["f"] * 24 for _ in range(24)]
    if pressed:
        for i in range(24):
            grid[0][i] = grid[i][0] = "D"
    else:
        for i in range(2):                       # 2 px raised, diagonal corners
            for x in range(0, 24 - i):
                grid[i][x] = "L"
            for y in range(0, 24 - i):
                grid[y][i] = "L"
            for x in range(i + 1, 24):
                grid[23 - i][x] = "D"
            for y in range(i + 1, 24):
                grid[y][23 - i] = "D"
    off = 4 if pressed else 3
    return _rows(_stamp(grid, _smiley(features), off, off))


FACES = {name: _face(f, pressed=False) for name, f in _FEATURES.items()}
FACES["pressed"] = _face(_FEATURES["normal"], pressed=True)
SMILEY = _smiley(_FEATURES["normal"])     # the face alone, 17x17: the Windows icon
```

Run: `/usr/bin/python3 -m unittest tests.test_sprites tests.test_render 2>&1 | tail -1`
Expected: `OK` (the faces are unchanged).

- [ ] **Step 4: Write the generator**

`tools/gen_c_sprites.py`:

```python
#!/usr/bin/python3
"""Write win/sprites.h and win/swaysweeper.ico from the Python package.

The art, both colour sets and the Keys text live once, in swaysweeper/;
the Windows build gets generated copies, and tests/test_win_files.py fails
when a copy is stale. Run after changing sprites.py, colours.py or KEYS:

    /usr/bin/python3 tools/gen_c_sprites.py
"""

import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from swaysweeper import colours, sprites  # noqa: E402
from swaysweeper.session import KEYS  # noqa: E402

HEADER = ROOT / "win" / "sprites.h"
ICON = ROOT / "win" / "swaysweeper.ico"

# core.c indexes SPRITES by these names: FACE_* follows FaceName in core.h,
# and LED_0..LED_9 must stay consecutive.
SPRITE_ORDER = (
    [(f"OPEN{n}", sprites.CELLS[f"open{n}"]) for n in range(1, 9)]
    + [("MINE", sprites.CELLS["mine"]), ("FLAG", sprites.CELLS["flag"]),
       ("QUESTION", sprites.CELLS["question"]), ("CROSS", sprites.CELLS["cross"])]
    + [(f"FACE_{name.upper()}", sprites.FACES[name])
       for name in ("normal", "wow", "dead", "cool", "pressed")]
    + [(f"LED_{d}", sprites.LED[d]) for d in "0123456789"]
    + [("LED_MINUS", sprites.LED["-"])]
)


def _c_string(text):
    return '"' + text.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n") + '"'


def header_text():
    lines = [
        "/* Generated by tools/gen_c_sprites.py from swaysweeper/sprites.py,",
        " * colours.py and session.py. Do not edit: change those and regenerate. */",
        "#ifndef SWAYSWEEPER_SPRITES_H",
        "#define SWAYSWEEPER_SPRITES_H",
        "",
        "#include <stdint.h>",
        "",
        "enum {",
        *[f"    SLOT_{name.upper()}," for name in colours.SLOTS],
        "    SLOT_COUNT",
        "};",
    ]
    for set_name, palette in (("WIN95", colours.WIN95), ("MONO", colours.MONO)):
        lines += ["", f"static const uint32_t PALETTE_{set_name}[SLOT_COUNT] = {{"]
        lines += [f"    0x00{palette[name][1:].upper()}, /* {name} */" for name in colours.SLOTS]
        lines += ["};"]
    lines += ["", "/* Art character -> colour slot + 1; 0 is transparent. */",
              "static const unsigned char LEGEND[128] = {"]
    lines += [f"    ['{ch}'] = SLOT_{slot.upper()} + 1," for ch, slot in sprites.LEGEND.items()]
    lines += ["};", "", "typedef struct {", "    int w, h;", "    const char *px;", "} Sprite;",
              "", "enum {"]
    lines += [f"    SPR_{name}," for name, _art in SPRITE_ORDER]
    lines += ["    SPR_COUNT", "};", "", "static const Sprite SPRITES[SPR_COUNT] = {"]
    for name, art in SPRITE_ORDER:
        lines.append(f"    {{{len(art[0])}, {len(art)}, /* {name} */")
        lines += [f"     {_c_string(row)}" for row in art[:-1]]
        lines.append(f"     {_c_string(art[-1])}}},")
    lines += ["};", "", "static const char KEYS_TEXT[] ="]
    key_lines = KEYS.split("\n")
    lines += [f"    {_c_string(line + chr(10))}" for line in key_lines[:-1]]
    lines += [f"    {_c_string(key_lines[-1])};", "", "#endif", ""]
    return "\n".join(lines)


# --- icon --------------------------------------------------------------------

_CLEAR = (0, 0, 0, 0)


def _rgba(art):
    grid = []
    for row in art:
        out = []
        for ch in row:
            if ch == ".":
                out.append(_CLEAR)
            else:
                c = colours.WIN95[sprites.LEGEND[ch]]
                out.append((int(c[1:3], 16), int(c[3:5], 16), int(c[5:7], 16), 255))
        grid.append(out)
    return grid


def _canvas(grid, size):
    oy, ox = (size - len(grid)) // 2, (size - len(grid[0])) // 2
    canvas = [[_CLEAR] * size for _ in range(size)]
    for y, row in enumerate(grid):
        for x, px in enumerate(row):
            canvas[oy + y][ox + x] = px
    return canvas


def _double(grid):
    return [[px for px in row for _ in (0, 1)] for row in grid for _ in (0, 1)]


def icon_images():
    """16, 20, 24, 32, 48 px, each a list of rows of (r, g, b, a)."""
    face = _rgba(sprites.SMILEY)                      # 17 x 17
    small = [row[:16] for row in face[:16]]           # 16: drop the last row and column
    mid = _canvas(face, 24)
    return [small, _canvas(face, 20), mid, _double(small), _double(mid)]


def _bmp(grid):
    size = len(grid)
    xor = b"".join(bytes((b, g, r, a)) for row in reversed(grid) for r, g, b, a in row)
    stride = (size + 31) // 32 * 4
    mask = bytearray()
    for row in reversed(grid):
        bits = bytearray(stride)
        for x, px in enumerate(row):
            if px[3] == 0:
                bits[x // 8] |= 0x80 >> (x % 8)
        mask += bits
    header = struct.pack("<IiiHHIIiiII", 40, size, size * 2, 1, 32, 0,
                         len(xor) + len(mask), 0, 0, 0, 0)
    return header + xor + bytes(mask)


def ico_bytes():
    images = icon_images()
    blobs = [_bmp(grid) for grid in images]
    out = struct.pack("<HHH", 0, 1, len(blobs))
    offset = 6 + 16 * len(blobs)
    for grid, blob in zip(images, blobs):
        size = len(grid)
        out += struct.pack("<BBBBHHII", size, size, 0, 0, 1, 32, len(blob), offset)
        offset += len(blob)
    return out + b"".join(blobs)


def main():
    HEADER.parent.mkdir(exist_ok=True)
    HEADER.write_text(header_text())
    ICON.write_bytes(ico_bytes())
    print(f"wrote {HEADER.relative_to(ROOT)} and {ICON.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 5: Generate, then check the header compiles and every table is reachable**

Run:
```bash
cd ~/repos/swaysweeper && /usr/bin/python3 tools/gen_c_sprites.py
cat > /tmp/claude-1000/spr.c <<'C'
#include <stdio.h>
#include "sprites.h"
int main(void)
{
    printf("%d %d %u %u %c\n", SPRITES[SPR_LED_MINUS].w, LEGEND['M'],
           (unsigned)PALETTE_WIN95[SLOT_NUM8], (unsigned)PALETTE_MONO[SLOT_FACE], KEYS_TEXT[0]);
    return 0;
}
C
cc -std=c11 -Wall -Wextra -pedantic -Werror -I win -o /tmp/claude-1000/spr /tmp/claude-1000/spr.c && /tmp/claude-1000/spr
```
Expected: `wrote win/sprites.h and win/swaysweeper.ico`, then `13 11 8421504 12632256 M` (LED width 13; `M` is `SLOT_MINE` = 10, plus 1; `#808080`; `#c0c0c0`; "Mouse").

- [ ] **Step 6: Run the tests**

Run: `/usr/bin/python3 -m unittest tests.test_win_files -v 2>&1 | tail -3`
Expected: `OK` (4 tests).

- [ ] **Step 7: Commit**

```bash
git add swaysweeper/sprites.py tools/gen_c_sprites.py tests/test_win_files.py win/sprites.h win/swaysweeper.ico
git commit -m "feat(win): generate sprites.h and the icon from the Python art" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_014cXNm1YtXA8z8QgkySFjrB"
```

---
### Task 4: The C core — rules and session — with replay parity

Spec §2.2, §5. `win/core.c` ports `board.py`, `game.py`, `gestures.py`, `geometry.py` and `session.py`. `win/replay.c` and `tests/replay.py` read the same script; `tests/test_win_parity.py` compares every printed line. Rendering, WAV and INI come in Tasks 5–6.

**Files:**
- Create: `win/core.h`, `win/core.c`, `win/replay.c`, `win/test_core.c`, `win/Makefile`, `tests/replay.py`, `tests/test_win_parity.py`
- Modify: `tests/test_win_files.py` (version test), `.gitignore`

**Interfaces:**
- Consumes: `session.Session` and its effect tuples (Task 2).
- Produces (Tasks 5–8 rely on these exact names):
  - Types: `Mark {COVERED, FLAG, QUESTION, REVEALED}`, `State {READY, PLAYING, WON, LOST}`, `Level {BEGINNER, INTERMEDIATE, EXPERT, CUSTOM}`, `Board`, `Game {level, board, seconds, timer_running, paused}`, `Settings {level, custom[3], marks, color, sound, zoom, has_pos, x, y}`, `Best {seconds, name[129]}`, `Layout`, `Rect`, `Style`, `CellFace` (`CF_OPEN0..CF_OPEN8, CF_COVERED, CF_FLAG, CF_QUESTION, CF_QUESTION_PRESSED, CF_MINE, CF_EXPLODED, CF_WRONG_FLAG`), `Mode`, `FaceName {FACE_NORMAL, FACE_WOW, FACE_DEAD, FACE_COOL, FACE_PRESSED}`, `Gestures {held, mode, has_cell, cx, cy, on_face}`, `EffectKind`, `SoundName {SND_TICK, SND_WIN, SND_LOSE}`, `Effect {kind, arg, seconds}`, `Effects {n, e[8]}`, `Session {game, settings, best, gestures, has_cursor, cursor_x, cursor_y}`.
  - Constants: `MAX_W 30`, `MAX_H 24`, `CELL 16`, `BOARD_X 12`, `BOARD_Y 55`, `FACE_SIZE 24`, `FACE_Y 16`, `DIGIT_Y 16`, `AREA_MAX_W 504`, `AREA_MAX_H 451`, `TIMER_MAX 999`, `NAME_MAX_BYTES 128`, `BUTTON_BIT(b)`, `LEFT/MIDDLE/RIGHT`.
  - Functions: `layout_of`, `cell_at`, `on_face`, `level_name`, `level_from_name`, `state_name`, `clamp_custom`, `clamp_counter`, `level_dims`, `board_init`, `board_over`, `board_count`, `board_counter`, `board_cell_face`, `board_toggle_mark`, `board_reveal`, `board_chord`, `game_init`, `game_status`, `game_ticking`, `game_release`, `game_mark`, `game_tick`, `game_counter`, `gestures_pressed`, `gestures_face`, `session_init`, `session_press`, `session_release`, `session_motion`, `session_key`, `session_tick`, `session_new`, `sound_name`.
  - Callers zero an `Effects` (`Effects fx = {0};`) and session functions append to it.
  - `held` is a bitmask of `BUTTON_BIT(button)`; both Win32 conventions (pressed button in or out) give the same result, as in `gestures.py`.
  - Replay protocol: `replay <outdir>` reads commands on stdin (see the header comment of `win/replay.c`), prints `fx …` per event and a 4-line `dump`; `tests/replay.Replay(outdir).run(line) -> [lines]` does the same in Python.

- [ ] **Step 1: Write the Python twin of the replay**

`tests/replay.py`:

```python
"""The Python side of the parity tests: win/replay.c's twin, over session.py.

Both read the same script and must print the same lines and write the same
files. The commands are documented at the top of win/replay.c.
"""

from pathlib import Path

from swaysweeper.board import Board
from swaysweeper.game import Game
from swaysweeper.session import Session

LEVELS = ("beginner", "intermediate", "expert")
_MARK_CHAR = {"covered": ".", "flag": "F", "question": "?", "revealed": "#"}


def _points(cells):
    return ";".join(f"{x},{y}" for x, y in sorted(cells)) or "-"


def _held(text):
    return frozenset() if text == "-" else frozenset(int(b) for b in text.split(","))


def format_effects(effects):
    words = ["fx"]
    for effect in effects:
        if effect[0] == "sound":
            words.append(f"sound:{effect[1]}")
        elif effect[0] == "best":
            words.append(f"best:{effect[1]}:{effect[2]}")
        else:
            words.append(effect[0])
    return " ".join(words)


class Replay:
    def __init__(self, outdir):
        self.outdir = Path(outdir)
        self.settings = {"marks": True, "color": True, "sound": False}
        self.best = {level: [999, "Anonymous"] for level in LEVELS}
        self.session = Session(None, self.settings, self.best)

    def run(self, line):
        """One script line in, the lines it prints out."""
        words = line.split()
        if not words:
            return []
        cmd, args = words[0], words[1:]
        s = self.session
        if cmd == "new":
            w, h, level, spec = int(args[0]), int(args[1]), args[2], args[3]
            mines = [] if spec == "-" else [tuple(int(v) for v in p.split(","))
                                           for p in spec.split(";")]
            return [format_effects(s.new(Game(level, Board(w, h, mines))))]
        if cmd == "press":
            return [format_effects(s.press(int(args[0]), int(args[1]), int(args[2]),
                                           shift=args[3] == "1", held=_held(args[4])))]
        if cmd == "release":
            return [format_effects(s.release(int(args[0]), int(args[1]), int(args[2]),
                                             held=_held(args[3])))]
        if cmd == "motion":
            return [format_effects(s.motion(int(args[0]), int(args[1])))]
        if cmd == "key":
            return [format_effects(s.key(args[0]))]
        if cmd == "tick":
            return [format_effects(s.tick())]
        if cmd == "settings":
            for pair in args:
                key, value = pair.split("=")
                self.settings[key] = value == "1"
            return []
        if cmd == "dump":
            return self._dump()
        raise ValueError(f"unknown command {cmd!r}")

    def _dump(self):
        s, g = self.session, self.session.game
        b = g.board
        face, pressed, cursor = s.paint_state()
        cur = "-" if cursor is None else f"{cursor[0]},{cursor[1]}"
        best = ",".join(str(self.best[level][0]) for level in LEVELS)
        return [
            f"dump status={g.status} state={b.state} revealed={b.revealed_count} "
            f"counter={g.counter()} seconds={g.seconds} running={int(g.timer_running)} "
            f"paused={int(g.paused)} mode={s.gestures.mode or 'none'} face={face} "
            f"cursor={cur} best={best}",
            "marks=" + "/".join("".join(_MARK_CHAR[m] for m in row) for row in b.marks),
            "exploded=" + _points(b.exploded),
            "pressed=" + _points(pressed),
        ]
```

- [ ] **Step 2: Write the failing parity tests**

`tests/test_win_parity.py`:

```python
"""win/core.c against the Python implementation, script by script (spec §5).

Builds win/replay with the system C compiler ($CC, else cc, else gcc), or
uses $SWAYSWEEPER_REPLAY as the Windows CI job does; runs each script
through it and through tests/replay.py; compares every printed line and
every written file. Skipped when there's no C compiler.
"""

import os
import random
import shlex
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from swaysweeper import geometry as G
from swaysweeper.game import DIFFICULTIES
from tests.replay import Replay

ROOT = Path(__file__).resolve().parent.parent
_exe = None
_tmp = None


def setUpModule():
    global _exe, _tmp
    prebuilt = os.environ.get("SWAYSWEEPER_REPLAY")
    if prebuilt:
        _exe = str(Path(prebuilt).resolve())
        return
    cc = shlex.split(os.environ["CC"]) if os.environ.get("CC") else \
        [shutil.which("cc") or shutil.which("gcc")]
    if cc[0] is None:
        raise unittest.SkipTest("no C compiler")
    _tmp = tempfile.TemporaryDirectory()
    _exe = os.path.join(_tmp.name, "replay")
    subprocess.run([*cc, "-std=c11", "-O2", "-Wall", "-Wextra", "-pedantic", "-Werror",
                    "-o", _exe, str(ROOT / "win" / "replay.c"), str(ROOT / "win" / "core.c"),
                    "-lm"], check=True)


def tearDownModule():
    if _tmp is not None:
        _tmp.cleanup()


# --- script helpers ------------------------------------------------------------

def centre(x, y):
    return G.BOARD_X + G.CELL * x + 8, G.BOARD_Y + G.CELL * y + 8


def click(x, y, button=1):
    px, py = centre(x, y)
    return [f"press {button} {px} {py} 0 -", f"release {button} {px} {py} {button}"]


def mines(cells):
    return ";".join(f"{x},{y}" for x, y in cells) or "-"


WALLED = "new 9 9 beginner " + mines([(4, y) for y in range(9)] + [(8, 8)])
FACE = (G.layout(9, 9).face_x + 12, G.FACE_Y + 12)


def random_board(rng):
    level = rng.choice(["beginner", "intermediate", "expert", "custom"])
    if level == "custom":
        w, h = rng.randint(9, 30), rng.randint(9, 24)
        m = rng.randint(10, min((w - 1) * (h - 1), 999))
    else:
        w, h, m = DIFFICULTIES[level]
    cells = [(x, y) for y in range(h) for x in range(w)]
    return f"new {w} {h} {level} " + mines(rng.sample(cells, m))


KEY_NAMES = ["Left", "Right", "Up", "Down", "h", "j", "k", "l", "space", "Return",
             "f", "c", "question", "x"]


def random_walk(seed, sessions, steps, render_every=0):
    """A script of random input, with a `new` answering every new_game effect.

    Generated against the Python session (so it can see those effects);
    render lines are emitted but not run here.
    """
    rng = random.Random(seed)
    script, held = [], set()
    with tempfile.TemporaryDirectory() as tmp:
        sim = Replay(tmp)

        def emit(line):
            script.append(line)
            return [] if line.startswith(("render", "wav")) else sim.run(line)

        for n in range(sessions):
            emit(random_board(rng))
            for step in range(steps):
                b = sim.session.game.board
                gw, gh = G.game_size(b.width, b.height)
                roll = rng.random()
                if roll < 0.1:
                    px, py = G.layout(b.width, b.height).face_x + 12, G.FACE_Y + 12
                elif roll < 0.8:
                    px, py = centre(rng.randrange(b.width), rng.randrange(b.height))
                    px, py = px + rng.randint(-8, 7), py + rng.randint(-8, 7)
                else:
                    px, py = rng.randint(-10, gw + 10), rng.randint(-10, gh + 10)
                held_text = ",".join(map(str, sorted(held))) or "-"
                roll, out = rng.random(), []
                if roll < 0.3:
                    free = [b for b in (1, 1, 1, 2, 3, 3) if b not in held]
                    if free:
                        button = rng.choice(free)
                        out = emit(f"press {button} {px} {py} {int(rng.random() < 0.1)} "
                                   f"{held_text}")
                        held.add(button)
                    else:
                        out = emit(f"motion {px} {py}")
                elif roll < 0.55:
                    if held:                        # held_text includes it, as GTK's mask does
                        button = rng.choice(sorted(held))
                        out = emit(f"release {button} {px} {py} {held_text}")
                        held.discard(button)
                    else:
                        out = emit(f"motion {px} {py}")
                elif roll < 0.7:
                    out = emit(f"motion {px} {py}")
                elif roll < 0.85:
                    out = emit(f"key {rng.choice(KEY_NAMES)}")
                elif roll < 0.95:
                    out = emit("tick")
                else:
                    if rng.random() < 0.3:
                        held.clear()                # a release delivered elsewhere
                    emit(f"settings marks={rng.randint(0, 1)} color={rng.randint(0, 1)} "
                         f"sound={rng.randint(0, 1)}")
                if out and "new_game" in out[0].split():
                    emit(random_board(rng))
                emit("dump")
                if render_every and step % render_every == render_every - 1:
                    emit(f"render walk-{seed}-{n}-{step}.ppm")
    return script


# --- the comparison ------------------------------------------------------------

class Parity(unittest.TestCase):
    maxDiff = None

    def check(self, script):
        with tempfile.TemporaryDirectory() as tmp:
            py_dir, c_dir = Path(tmp, "py"), Path(tmp, "c")
            py_dir.mkdir()
            c_dir.mkdir()
            replay = Replay(py_dir)
            expected = [out for line in script for out in replay.run(line)]
            got = subprocess.run([_exe, str(c_dir)], input="\n".join(script) + "\n",
                                 capture_output=True, text=True, check=True).stdout.splitlines()
            for i, (want, have) in enumerate(zip(expected, got)):
                if want != have:
                    self.fail(f"output line {i} differs\n  python: {want}\n  c:      {have}")
            self.assertEqual(len(got), len(expected), "C printed a different number of lines")
            for path in sorted(py_dir.iterdir()):
                other = c_dir / path.name
                self.assertTrue(other.exists(), f"C wrote no {path.name}")
                a, b = path.read_bytes(), other.read_bytes()
                if a != b:
                    at = next((i for i, (x, y) in enumerate(zip(a, b)) if x != y), min(len(a), len(b)))
                    self.fail(f"{path.name} differs at byte {at} (sizes {len(a)}, {len(b)})")
        return expected


class Rules(Parity):
    def test_walled_board(self):
        self.check([WALLED, *click(0, 0), "dump", "tick", "tick", "dump",
                    *click(5, 4, 3), *click(5, 4, 3), *click(3, 4, 3), "dump",
                    *click(4, 0), "dump", "tick", "dump"])

    def test_first_click_on_a_mine_relocates_it(self):
        self.check(["new 9 9 beginner " + mines([(0, 0), (8, 8)] + [(x, 8) for x in range(8)]),
                    *click(0, 0), "dump"])

    def test_chord_with_a_wrong_flag_loses(self):
        cells = [(1, 1), (8, 8), (6, 0), (7, 0), (8, 0), (6, 1), (7, 1), (8, 1), (6, 2), (7, 2)]
        px, py = centre(0, 0)
        self.check(["settings sound=1", "new 9 9 beginner " + mines(cells), *click(0, 0),
                    *click(0, 1, 3), f"press 2 {px} {py} 0 -", f"release 2 {px} {py} 2", "dump"])

    def test_one_click_win_sets_a_best_time(self):
        self.check(["settings sound=1", "new 9 9 beginner 8,8", *click(0, 0), "dump",
                    "new 9 9 beginner 8,8", "tick", *click(0, 0), "dump"])

    def test_both_buttons_chord_and_right_after_left_does_not_mark(self):
        px, py = centre(3, 4)
        self.check([WALLED, *click(3, 4), *click(4, 3, 3), *click(4, 4, 3), *click(4, 5, 3),
                    f"press 1 {px} {py} 0 -", f"press 3 {px} {py} 0 1", "dump",
                    f"release 3 {px} {py} 1,3", f"release 1 {px} {py} 1", "dump"])

    def test_drag_off_and_release(self):
        px, py = centre(0, 0)
        self.check([WALLED, f"press 1 {px} {py} 0 -", "motion -20 -20", "dump",
                    "release 1 -20 -20 1", "dump"])

    def test_face_asks_for_a_new_game(self):
        fx, fy = FACE
        self.check([WALLED, *click(0, 0), f"press 1 {fx} {fy} 0 -", "dump", "motion 0 0",
                    "dump", f"motion {fx} {fy}", f"release 1 {fx} {fy} 1", WALLED, "dump"])

    def test_keys(self):
        self.check([WALLED, "key space", "key Up", *["key h"] * 5, "key k", "dump",
                    "key l", "key l", "key l", "key j", "key space", "key f", "key c", "key x",
                    "key question", "key Return", "dump", *click(0, 0), "dump"])

    def test_marks_off_skips_the_question(self):
        self.check([WALLED, "settings marks=0", *click(2, 2, 3), *click(2, 2, 3), "dump",
                    "settings marks=1", *click(2, 2, 3), *click(2, 2, 3), "dump"])

    def test_counter_clamps_at_minus_99(self):
        top = [(x, y) for y in range(4) for x in range(30)][:99]
        flags = [line for y in range(5, 12) for x in range(30) for line in click(x, y, 3)]
        self.check(["new 30 16 expert " + mines(top), *flags, "dump"])

    def test_largest_custom_board(self):
        cells = [(x, y) for y in range(24) for x in range(30)]
        self.check(["new 30 24 custom " + mines(cells[53:]), *click(0, 0), "dump",
                    "key Down", "key Down", "dump"])

    def test_timer_stops_at_999(self):
        self.check([WALLED, *click(0, 0), *["tick"] * 1000, "dump"])


class RandomWalk(Parity):
    def test_random_walk(self):
        self.check(random_walk(seed=1, sessions=60, steps=50))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 3: Add the C version test**

Append to `tests/test_win_files.py`, inside `class Generated` (and add `import re` and `from swaysweeper import __version__` at the top):

```python
    def test_c_version_matches_python(self):
        text = (ROOT / "win" / "core.h").read_text()
        self.assertIn(f'#define SWAYSWEEPER_VERSION "{__version__}"', text)
        major, minor, patch, beta = re.fullmatch(r"(\d+)\.(\d+)\.(\d+)-beta\.(\d+)",
                                                 __version__).groups()
        self.assertIn(f"#define SWAYSWEEPER_VERSION_NUM {major},{minor},{patch},{beta}", text)
```

- [ ] **Step 4: Run them to verify they fail**

Run: `cd ~/repos/swaysweeper && /usr/bin/python3 -m unittest tests.test_win_parity tests.test_win_files 2>&1 | tail -4`
Expected: an error from `setUpModule` (the compiler can't find `win/replay.c`) and `test_c_version_matches_python` failing with `FileNotFoundError` for `win/core.h`.

- [ ] **Step 5: Write `win/core.h`**

```c
/* swaysweeper's portable core: rules, session, renderer, sounds and state
 * files, ported from swaysweeper/{board,game,gestures,geometry,session,
 * render,sound,store}.py. No windows.h, so it builds and is tested on Linux
 * too; tests/test_win_parity.py holds it to the Python output step by step.
 * swaysweeper.rc includes this for the version, hence the RC_INVOKED guard.
 */
#ifndef SWAYSWEEPER_CORE_H
#define SWAYSWEEPER_CORE_H

#define SWAYSWEEPER_VERSION "0.1.0-beta.1"
#define SWAYSWEEPER_VERSION_NUM 0,1,0,1

#ifndef RC_INVOKED

#include <stddef.h>
#include <stdint.h>

enum { MAX_W = 30, MAX_H = 24 };
enum { CELL = 16, FACE_SIZE = 24, BOARD_X = 12, BOARD_Y = 55, DIGIT_Y = 16, FACE_Y = 16 };
enum { AREA_MAX_W = CELL * MAX_W + 24, AREA_MAX_H = CELL * MAX_H + 67 };
enum { TIMER_MAX = 999, NAME_MAX_BYTES = 128 };     /* 32 code points of UTF-8 */
enum { LEFT = 1, MIDDLE = 2, RIGHT = 3 };
#define BUTTON_BIT(b) (1u << (b))

typedef enum { COVERED, FLAG, QUESTION, REVEALED } Mark;
typedef enum { READY, PLAYING, WON, LOST } State;
typedef enum { BEGINNER, INTERMEDIATE, EXPERT, CUSTOM } Level;

typedef struct {
    int width, height, mine_count, revealed_count;
    State state;
    unsigned char mine[MAX_H][MAX_W], mark[MAX_H][MAX_W], exploded[MAX_H][MAX_W];
} Board;

typedef struct {
    Level level;
    Board board;
    int seconds, timer_running, paused;
} Game;

typedef struct {
    Level level;
    int custom[3];                  /* width, height, mines */
    int marks, color, sound, zoom;  /* zoom is 1 or 2 */
    int has_pos, x, y;              /* window position (Windows only) */
} Settings;

typedef struct {
    int seconds;
    char name[NAME_MAX_BYTES + 1];  /* UTF-8 */
} Best;

/* --- geometry.py ------------------------------------------------------------ */

typedef enum { RAISED, SUNKEN, FLAT } Style;
typedef struct { int left, top, right, bottom, bevel; Style style; } Rect;  /* inclusive */
typedef struct {
    int width, height;
    Rect frame, panel, counter, timer, smiley, board;
    int counter_x[3], timer_x[3], face_x;
} Layout;

void layout_of(int w, int h, Layout *out);
int cell_at(const Layout *lay, int x, int y, int *cx, int *cy);
int on_face(const Layout *lay, int x, int y);

/* --- game.py: levels -------------------------------------------------------- */

const char *level_name(Level level);
int level_from_name(const char *name, Level *out);
const char *state_name(State state);
void clamp_custom(int w, int h, int m, int out[3]);
int clamp_counter(int n);
void level_dims(Level level, const int custom[3], int out[3]);

/* --- board.py --------------------------------------------------------------- */

typedef enum {
    CF_OPEN0, CF_OPEN1, CF_OPEN2, CF_OPEN3, CF_OPEN4, CF_OPEN5, CF_OPEN6, CF_OPEN7, CF_OPEN8,
    CF_COVERED, CF_FLAG, CF_QUESTION, CF_QUESTION_PRESSED, CF_MINE, CF_EXPLODED, CF_WRONG_FLAG
} CellFace;

/* `mines` may repeat a square (it counts once); -1 if a size or square is out of range. */
int board_init(Board *b, int w, int h, const int (*mines)[2], int n);
int board_over(const Board *b);
int board_count(const Board *b, int x, int y);
int board_counter(const Board *b);
CellFace board_cell_face(const Board *b, int x, int y);
int board_toggle_mark(Board *b, int x, int y, int marks_enabled);
int board_reveal(Board *b, int x, int y);
int board_chord(Board *b, int x, int y);

/* --- game.py ---------------------------------------------------------------- */

void game_init(Game *g, Level level, const Board *b);
State game_status(const Game *g);
int game_ticking(const Game *g);
int game_release(Game *g, int x, int y, int chord);
int game_mark(Game *g, int x, int y, int marks_enabled);
int game_tick(Game *g);
int game_counter(const Game *g);

/* --- gestures.py ------------------------------------------------------------ */

typedef enum { MODE_NONE, MODE_SINGLE, MODE_CHORD, MODE_FACE } Mode;
typedef enum { FACE_NORMAL, FACE_WOW, FACE_DEAD, FACE_COOL, FACE_PRESSED } FaceName;
typedef struct {
    unsigned held;                  /* BUTTON_BIT()s */
    Mode mode;
    int has_cell, cx, cy, on_face;
} Gestures;

int gestures_pressed(const Gestures *g, int x, int y);   /* in preview()? */
FaceName gestures_face(const Gestures *g, State status);

/* --- session.py ------------------------------------------------------------- */

typedef enum {
    FX_SAVE, FX_DELETE, FX_SOUND, FX_BEST, FX_NEW_GAME, FX_SHOW_KEYS, FX_UNHANDLED, FX_REDRAW
} EffectKind;
typedef enum { SND_TICK, SND_WIN, SND_LOSE } SoundName;
typedef struct { EffectKind kind; int arg, seconds; } Effect;  /* arg: SoundName or Level */
enum { MAX_EFFECTS = 8 };
typedef struct { int n; Effect e[MAX_EFFECTS]; } Effects;

typedef struct {
    Game game;
    const Settings *settings;       /* the host's; marks and sound are read live */
    Best *best;                     /* the host's [3], indexed by Level */
    Gestures gestures;
    int has_cursor, cursor_x, cursor_y;
} Session;

/* Pointer coordinates are game-area pixels at x1. Each call appends to `fx`,
 * which the caller zeroes. */
void session_init(Session *s, const Settings *settings, Best *best);
void session_press(Session *s, int button, int px, int py, int shift, unsigned held, Effects *fx);
void session_release(Session *s, int button, int px, int py, unsigned held, Effects *fx);
void session_motion(Session *s, int px, int py, Effects *fx);
void session_key(Session *s, const char *name, Effects *fx);
void session_tick(Session *s, Effects *fx);
void session_new(Session *s, const Game *game, Effects *fx);
const char *sound_name(SoundName name);

#endif /* RC_INVOKED */
#endif
```

- [ ] **Step 6: Write `win/core.c`**

```c
/* See core.h. Each section names the Python module it ports; keep them in
 * step, and tests/test_win_parity.py will say when they aren't. */
#include "core.h"

#include <string.h>

static int clampi(int v, int lo, int hi)
{
    return v < lo ? lo : v > hi ? hi : v;
}

/* --- geometry.py ------------------------------------------------------------ */

static Rect rect(int left, int top, int right, int bottom, int bevel, Style style)
{
    Rect r = {left, top, right, bottom, bevel, style};
    return r;
}

void layout_of(int w, int h, Layout *out)
{
    int xr = CELL * w + 24, yb = CELL * h + 67;
    int face_x = (xr - FACE_SIZE) / 2;
    out->width = xr;
    out->height = yb;
    out->frame = rect(0, 0, xr - 1, yb - 1, 3, RAISED);
    out->panel = rect(9, 9, xr - 10, 45, 2, SUNKEN);
    out->counter = rect(16, 15, 56, 39, 1, SUNKEN);
    out->timer = rect(xr - 57, 15, xr - 17, 39, 1, SUNKEN);
    out->smiley = rect(face_x - 1, 15, face_x + FACE_SIZE, 40, 1, FLAT);
    out->board = rect(9, 52, xr - 10, yb - 10, 3, SUNKEN);
    out->counter_x[0] = 17;
    out->counter_x[1] = 30;
    out->counter_x[2] = 43;
    out->timer_x[0] = xr - 56;
    out->timer_x[1] = xr - 43;
    out->timer_x[2] = xr - 30;
    out->face_x = face_x;
}

int cell_at(const Layout *lay, int x, int y, int *cx, int *cy)
{
    int w = (lay->width - 24) / CELL, h = (lay->height - 67) / CELL;
    if (x < BOARD_X || y < BOARD_Y)
        return 0;
    *cx = (x - BOARD_X) / CELL;
    *cy = (y - BOARD_Y) / CELL;
    return *cx < w && *cy < h;
}

int on_face(const Layout *lay, int x, int y)
{
    return lay->face_x <= x && x < lay->face_x + FACE_SIZE && FACE_Y <= y && y < FACE_Y + FACE_SIZE;
}

/* --- game.py: levels -------------------------------------------------------- */

static const char *const LEVEL_NAMES[] = {"beginner", "intermediate", "expert", "custom"};
static const char *const STATE_NAMES[] = {"ready", "playing", "won", "lost"};
static const int PRESETS[3][3] = {{9, 9, 10}, {16, 16, 40}, {30, 16, 99}};

const char *level_name(Level level)
{
    return LEVEL_NAMES[level];
}

int level_from_name(const char *name, Level *out)
{
    for (int i = 0; i < 4; i++)
        if (strcmp(name, LEVEL_NAMES[i]) == 0) {
            *out = (Level)i;
            return 1;
        }
    return 0;
}

const char *state_name(State state)
{
    return STATE_NAMES[state];
}

/* winmine's Custom limits (windowing.c:220-223): clamp, never reject. */
void clamp_custom(int w, int h, int m, int out[3])
{
    out[1] = clampi(h, 9, 24);
    out[0] = clampi(w, 9, 30);
    int most = (out[0] - 1) * (out[1] - 1);
    out[2] = clampi(m, 10, most < 999 ? most : 999);
}

int clamp_counter(int n)
{
    return clampi(n, -99, 999);
}

void level_dims(Level level, const int custom[3], int out[3])
{
    if (level == CUSTOM)
        clamp_custom(custom[0], custom[1], custom[2], out);
    else
        memcpy(out, PRESETS[level], sizeof PRESETS[level]);
}

/* --- board.py --------------------------------------------------------------- */

static int in_bounds(const Board *b, int x, int y)
{
    return x >= 0 && x < b->width && y >= 0 && y < b->height;
}

int board_init(Board *b, int w, int h, const int (*mines)[2], int n)
{
    memset(b, 0, sizeof *b);
    if (w < 1 || w > MAX_W || h < 1 || h > MAX_H)
        return -1;
    b->width = w;
    b->height = h;
    b->state = READY;
    for (int i = 0; i < n; i++) {
        int x = mines[i][0], y = mines[i][1];
        if (!in_bounds(b, x, y))
            return -1;
        if (!b->mine[y][x]) {
            b->mine[y][x] = 1;
            b->mine_count++;
        }
    }
    return 0;
}

int board_over(const Board *b)
{
    return b->state == WON || b->state == LOST;
}

int board_count(const Board *b, int x, int y)
{
    int n = 0;
    for (int dy = -1; dy <= 1; dy++)
        for (int dx = -1; dx <= 1; dx++)
            if ((dx || dy) && in_bounds(b, x + dx, y + dy) && b->mine[y + dy][x + dx])
                n++;
    return n;
}

static int flags_around(const Board *b, int x, int y)
{
    int n = 0;
    for (int dy = -1; dy <= 1; dy++)
        for (int dx = -1; dx <= 1; dx++)
            if ((dx || dy) && in_bounds(b, x + dx, y + dy) && b->mark[y + dy][x + dx] == FLAG)
                n++;
    return n;
}

/* Mines minus flags, unclamped: the display clamps (game_counter). */
int board_counter(const Board *b)
{
    int flags = 0;
    for (int y = 0; y < b->height; y++)
        for (int x = 0; x < b->width; x++)
            flags += b->mark[y][x] == FLAG;
    return b->mine_count - flags;
}

/* The sprite for one square, including winmine's end-of-game reveal. */
CellFace board_cell_face(const Board *b, int x, int y)
{
    int mark = b->mark[y][x], mine = b->mine[y][x];
    if (b->state == LOST) {
        if (b->exploded[y][x])
            return CF_EXPLODED;
        if (mark == FLAG && !mine)
            return CF_WRONG_FLAG;
        if (mine && mark != FLAG)
            return CF_MINE;
    }
    if (mark == REVEALED)
        return (CellFace)(CF_OPEN0 + board_count(b, x, y));
    if (mark == FLAG)
        return CF_FLAG;
    if (mark == QUESTION)
        return CF_QUESTION;
    return CF_COVERED;
}

/* Right press: covered -> flag -> ? -> covered (? only with Marks on). */
int board_toggle_mark(Board *b, int x, int y, int marks_enabled)
{
    if (board_over(b) || !in_bounds(b, x, y) || b->mark[y][x] == REVEALED)
        return 0;
    int mark = b->mark[y][x];
    if (mark == COVERED)
        b->mark[y][x] = FLAG;
    else if (mark == FLAG)
        b->mark[y][x] = marks_enabled ? QUESTION : COVERED;
    else
        b->mark[y][x] = COVERED;
    return 1;
}

/* game.c:551-553 loops `row < Height`, `col < Width` from 1 (1-based): the
 * last row and column are never scanned. The clicked square is still a mine
 * here, so it can never be chosen. */
static int relocate(Board *b, int x, int y)
{
    for (int ry = 0; ry < b->height - 1; ry++)
        for (int rx = 0; rx < b->width - 1; rx++)
            if (!b->mine[ry][rx]) {
                b->mine[y][x] = 0;
                b->mine[ry][rx] = 1;
                return 1;
            }
    return 0;
}

static void flood(Board *b, int x, int y)
{
    /* Each square is revealed once and pushes at most 8 neighbours. */
    static unsigned char stack[8 * MAX_W * MAX_H + 1][2];
    int top = 0;
    stack[top][0] = (unsigned char)x;
    stack[top][1] = (unsigned char)y;
    top++;
    while (top > 0) {
        top--;
        int cx = stack[top][0], cy = stack[top][1];
        if (b->mark[cy][cx] == FLAG || b->mark[cy][cx] == REVEALED)
            continue;
        b->mark[cy][cx] = REVEALED;
        b->revealed_count++;
        if (board_count(b, cx, cy) != 0)
            continue;
        for (int dy = -1; dy <= 1; dy++)
            for (int dx = -1; dx <= 1; dx++)
                if ((dx || dy) && in_bounds(b, cx + dx, cy + dy)) {
                    stack[top][0] = (unsigned char)(cx + dx);
                    stack[top][1] = (unsigned char)(cy + dy);
                    top++;
                }
    }
}

static void lose(Board *b, const int (*hit)[2], int n)
{
    b->state = LOST;
    memset(b->exploded, 0, sizeof b->exploded);
    for (int i = 0; i < n; i++)
        b->exploded[hit[i][1]][hit[i][0]] = 1;
}

static void check_win(Board *b)
{
    if (b->revealed_count != b->width * b->height - b->mine_count)
        return;
    b->state = WON;
    for (int y = 0; y < b->height; y++)
        for (int x = 0; x < b->width; x++)
            if (b->mine[y][x])
                b->mark[y][x] = FLAG;
}

/* Left release. Returns whether anything changed. */
int board_reveal(Board *b, int x, int y)
{
    if (board_over(b) || !in_bounds(b, x, y))
        return 0;
    if (b->mark[y][x] == FLAG || b->mark[y][x] == REVEALED)
        return 0;
    if (b->mine[y][x]) {
        if (b->revealed_count == 0) {          /* game.c: NumberOfRevealedBlocks == 0 */
            if (!relocate(b, x, y))
                return 0;
        } else {
            const int hit[1][2] = {{x, y}};
            lose(b, hit, 1);
            return 1;
        }
    }
    b->state = PLAYING;
    flood(b, x, y);
    check_win(b);
    return 1;
}

/* Open every covered, unflagged neighbour of a satisfied number. */
int board_chord(Board *b, int x, int y)
{
    if (board_over(b) || !in_bounds(b, x, y) || b->mark[y][x] != REVEALED)
        return 0;
    int n = board_count(b, x, y);
    if (n == 0 || flags_around(b, x, y) != n)
        return 0;
    int hit[8][2], nhit = 0;
    for (int dy = -1; dy <= 1; dy++)
        for (int dx = -1; dx <= 1; dx++) {
            int nx = x + dx, ny = y + dy;
            if (!(dx || dy) || !in_bounds(b, nx, ny))
                continue;
            if (b->mark[ny][nx] == FLAG || b->mark[ny][nx] == REVEALED)
                continue;
            if (b->mine[ny][nx]) {                 /* game.c:505: each one exploded */
                hit[nhit][0] = nx;
                hit[nhit][1] = ny;
                nhit++;
            } else {
                flood(b, nx, ny);
            }
        }
    if (nhit)
        lose(b, (const int (*)[2])hit, nhit);
    else
        check_win(b);
    return 1;
}

/* --- game.py ---------------------------------------------------------------- */

void game_init(Game *g, Level level, const Board *b)
{
    memset(g, 0, sizeof *g);
    g->level = level;
    g->board = *b;
}

State game_status(const Game *g)
{
    State s = g->board.state;
    if (s == WON || s == LOST)
        return s;
    return g->timer_running || s == PLAYING ? PLAYING : READY;
}

int game_ticking(const Game *g)
{
    return g->timer_running && !g->paused && g->seconds < TIMER_MAX;
}

/* A left/middle release (or a keyboard open) on board square (x, y). The
 * timer starts here, on the first release on the board, even one that
 * reveals nothing (a flag): game.c HandleBlockClick. */
int game_release(Game *g, int x, int y, int chord)
{
    Board *b = &g->board;
    if (board_over(b) || !in_bounds(b, x, y))
        return 0;
    g->paused = 0;
    if (b->revealed_count == 0 && g->seconds == 0) {
        g->seconds = 1;
        g->timer_running = 1;
    }
    if (chord)
        board_chord(b, x, y);
    else
        board_reveal(b, x, y);
    if (board_over(b))
        g->timer_running = 0;
    return 1;
}

int game_mark(Game *g, int x, int y, int marks_enabled)
{
    if (board_over(&g->board))
        return 0;
    g->paused = 0;
    return board_toggle_mark(&g->board, x, y, marks_enabled);
}

int game_tick(Game *g)
{
    if (!game_ticking(g))
        return 0;
    g->seconds++;
    return 1;
}

int game_counter(const Game *g)
{
    return clamp_counter(board_counter(&g->board));
}

/* --- gestures.py: winmine's mouse model (windowing.c:495-548) ---------------- */

typedef enum { ACT_NONE, ACT_NEW, ACT_REVEAL, ACT_CHORD, ACT_MARK } ActKind;
typedef struct { ActKind kind; int x, y; } Action;

static void gestures_at(Gestures *g, int has_cell, int cx, int cy, int face)
{
    g->has_cell = has_cell;
    g->cx = cx;
    g->cy = cy;
    g->on_face = face;
}

static Action gestures_press(Gestures *g, int button, int has_cell, int cx, int cy, int face,
                             int shift, int active, unsigned held)
{
    Action a = {ACT_NONE, cx, cy};
    g->held = held | BUTTON_BIT(button);
    gestures_at(g, has_cell, cx, cy, face);
    if (g->mode == MODE_FACE)
        return a;
    if (button == LEFT && face && g->mode == MODE_NONE && g->held == BUTTON_BIT(LEFT)) {
        g->mode = MODE_FACE;
        return a;
    }
    if (!active)
        return a;
    if (button == RIGHT) {
        if (g->mode == MODE_SINGLE)
            g->mode = MODE_CHORD;
        else if (g->mode == MODE_NONE && !(g->held & BUTTON_BIT(LEFT)) && has_cell)
            a.kind = ACT_MARK;
        return a;
    }
    if (button == MIDDLE || (button == LEFT && (shift || (g->held & BUTTON_BIT(RIGHT)))))
        g->mode = MODE_CHORD;
    else if (button == LEFT)
        g->mode = MODE_SINGLE;
    return a;
}

static Action gestures_release(Gestures *g, int button, int has_cell, int cx, int cy, int face,
                               unsigned held)
{
    Action a = {ACT_NONE, cx, cy};
    g->held = held & ~BUTTON_BIT(button);
    gestures_at(g, has_cell, cx, cy, face);
    Mode mode = g->mode;
    if (mode == MODE_FACE) {
        if (button != LEFT)
            return a;
        g->mode = MODE_NONE;
        if (face)
            a.kind = ACT_NEW;
        return a;
    }
    g->mode = MODE_NONE;
    if ((mode == MODE_SINGLE || mode == MODE_CHORD) && has_cell)
        a.kind = mode == MODE_CHORD ? ACT_CHORD : ACT_REVEAL;
    return a;
}

int gestures_pressed(const Gestures *g, int x, int y)
{
    if (!g->has_cell)
        return 0;
    if (g->mode == MODE_SINGLE)
        return x == g->cx && y == g->cy;
    if (g->mode == MODE_CHORD)
        return x >= g->cx - 1 && x <= g->cx + 1 && y >= g->cy - 1 && y <= g->cy + 1;
    return 0;
}

FaceName gestures_face(const Gestures *g, State status)
{
    if (g->mode == MODE_FACE && g->on_face)
        return FACE_PRESSED;
    if (status == LOST)
        return FACE_DEAD;
    if (status == WON)
        return FACE_COOL;
    if (g->mode == MODE_SINGLE || g->mode == MODE_CHORD)
        return FACE_WOW;
    return FACE_NORMAL;
}

/* --- session.py ------------------------------------------------------------- */

static const char *const SOUND_NAMES[] = {"tick", "win", "lose"};

const char *sound_name(SoundName name)
{
    return SOUND_NAMES[name];
}

void session_init(Session *s, const Settings *settings, Best *best)
{
    memset(s, 0, sizeof *s);
    s->settings = settings;
    s->best = best;
}

static void push(Effects *fx, EffectKind kind, int arg, int seconds)
{
    if (fx->n == MAX_EFFECTS)
        return;
    fx->e[fx->n].kind = kind;
    fx->e[fx->n].arg = arg;
    fx->e[fx->n].seconds = seconds;
    fx->n++;
}

static void sound(const Session *s, SoundName name, Effects *fx)
{
    if (s->settings->sound)
        push(fx, FX_SOUND, name, 0);
}

static void act(Session *s, Action a, Effects *fx)
{
    if (a.kind == ACT_NONE)
        return;
    if (a.kind == ACT_NEW) {
        push(fx, FX_NEW_GAME, 0, 0);
        return;
    }
    Game *g = &s->game;
    State before = game_status(g);
    if (a.kind == ACT_MARK)
        game_mark(g, a.x, a.y, s->settings->marks);
    else
        game_release(g, a.x, a.y, a.kind == ACT_CHORD);
    State after = game_status(g);
    push(fx, after == PLAYING ? FX_SAVE : FX_DELETE, 0, 0);
    if (before == after)
        return;
    if (before == READY && after == PLAYING)
        sound(s, SND_TICK, fx);
    else if (after == WON)
        sound(s, SND_WIN, fx);
    else if (after == LOST)
        sound(s, SND_LOSE, fx);
    if (after == WON && g->level != CUSTOM && g->seconds < s->best[g->level].seconds) {
        s->best[g->level].seconds = g->seconds;
        strcpy(s->best[g->level].name, "Anonymous");
        push(fx, FX_BEST, g->level, g->seconds);
    }
}

static void hit(const Session *s, int px, int py, int *has_cell, int *cx, int *cy, int *face)
{
    Layout lay;
    layout_of(s->game.board.width, s->game.board.height, &lay);
    *cx = *cy = 0;
    *has_cell = cell_at(&lay, px, py, cx, cy);
    *face = on_face(&lay, px, py);
}

void session_press(Session *s, int button, int px, int py, int shift, unsigned held, Effects *fx)
{
    int has_cell, cx, cy, face;
    hit(s, px, py, &has_cell, &cx, &cy, &face);
    act(s, gestures_press(&s->gestures, button, has_cell, cx, cy, face, shift,
                          !board_over(&s->game.board), held), fx);
    push(fx, FX_REDRAW, 0, 0);
}

void session_release(Session *s, int button, int px, int py, unsigned held, Effects *fx)
{
    int has_cell, cx, cy, face;
    hit(s, px, py, &has_cell, &cx, &cy, &face);
    act(s, gestures_release(&s->gestures, button, has_cell, cx, cy, face, held), fx);
    push(fx, FX_REDRAW, 0, 0);
}

void session_motion(Session *s, int px, int py, Effects *fx)
{
    int has_cell, cx, cy, face;
    hit(s, px, py, &has_cell, &cx, &cy, &face);
    gestures_at(&s->gestures, has_cell, cx, cy, face);
    int had_cursor = s->has_cursor;
    if (has_cell)
        s->has_cursor = 0;
    if (s->gestures.mode != MODE_NONE || (had_cursor && !s->has_cursor))
        push(fx, FX_REDRAW, 0, 0);
}

static const struct { const char *name; int dx, dy; } MOVES[] = {
    {"Left", -1, 0}, {"h", -1, 0}, {"Right", 1, 0}, {"l", 1, 0},
    {"Up", 0, -1},   {"k", 0, -1}, {"Down", 0, 1},  {"j", 0, 1},
};

void session_key(Session *s, const char *name, Effects *fx)
{
    const Board *b = &s->game.board;
    for (size_t i = 0; i < sizeof MOVES / sizeof MOVES[0]; i++) {
        if (strcmp(name, MOVES[i].name) != 0)
            continue;
        if (!s->has_cursor) {
            s->has_cursor = 1;
            s->cursor_x = b->width / 2;
            s->cursor_y = b->height / 2;
        } else {
            s->cursor_x = clampi(s->cursor_x + MOVES[i].dx, 0, b->width - 1);
            s->cursor_y = clampi(s->cursor_y + MOVES[i].dy, 0, b->height - 1);
        }
        push(fx, FX_REDRAW, 0, 0);
        return;
    }
    if (strcmp(name, "question") == 0) {
        push(fx, FX_SHOW_KEYS, 0, 0);
        return;
    }
    if (!s->has_cursor) {
        push(fx, FX_UNHANDLED, 0, 0);
        return;
    }
    Action a = {ACT_NONE, s->cursor_x, s->cursor_y};
    if (strcmp(name, "space") == 0 || strcmp(name, "Return") == 0)
        a.kind = b->mark[a.y][a.x] == REVEALED ? ACT_CHORD : ACT_REVEAL;
    else if (strcmp(name, "f") == 0)
        a.kind = ACT_MARK;
    else if (strcmp(name, "c") == 0)
        a.kind = ACT_CHORD;
    else {
        push(fx, FX_UNHANDLED, 0, 0);
        return;
    }
    act(s, a, fx);
    push(fx, FX_REDRAW, 0, 0);
}

void session_tick(Session *s, Effects *fx)
{
    if (!game_tick(&s->game))
        return;
    push(fx, FX_SAVE, 0, 0);
    sound(s, SND_TICK, fx);
    push(fx, FX_REDRAW, 0, 0);
}

void session_new(Session *s, const Game *game, Effects *fx)
{
    s->game = *game;
    s->has_cursor = 0;
    s->gestures.mode = MODE_NONE;
    push(fx, FX_DELETE, 0, 0);
    push(fx, FX_REDRAW, 0, 0);
}
```

- [ ] **Step 7: Write `win/replay.c`**

```c
/* Parity driver: reads a script on stdin, drives core, prints what happened.
 * tests/replay.py is its Python twin; tests/test_win_parity.py runs both on
 * one script and compares them line by line and file by file.
 *
 * Usage: replay <output-dir>        Commands, one per line:
 *   new <w> <h> <level> <x,y;...|->   a board with these mines (answers new_game)
 *   press <button> <px> <py> <shift> <held>    held: e.g. 1,3 or -
 *   release <button> <px> <py> <held>
 *   motion <px> <py>        key <name>        tick
 *   settings marks=<0|1> color=<0|1> sound=<0|1>
 *   dump                    the session's state, four lines
 *   render <file>           the game area as a PPM in <output-dir>
 *   wav <tick|win|lose> <file>
 * Events print "fx" and their effects. CRLF input is fine.
 */
#include "core.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#ifdef _WIN32
#include <fcntl.h>
#include <io.h>
#endif

static Settings settings;
static Best best[3];
static Session session;

static char *arg(void)
{
    char *t = strtok(NULL, " ");
    if (!t) {
        fprintf(stderr, "replay: missing argument\n");
        exit(1);
    }
    return t;
}

static int iarg(void)
{
    return atoi(arg());
}

static unsigned held_arg(void)
{
    unsigned held = 0;
    for (const char *p = arg(); *p; p++)
        if (*p >= '1' && *p <= '9')
            held |= BUTTON_BIT(*p - '0');
    return held;
}

static void print_fx(const Effects *fx)
{
    fputs("fx", stdout);
    for (int i = 0; i < fx->n; i++) {
        const Effect *e = &fx->e[i];
        switch (e->kind) {
        case FX_SAVE: fputs(" save", stdout); break;
        case FX_DELETE: fputs(" delete", stdout); break;
        case FX_SOUND: printf(" sound:%s", sound_name((SoundName)e->arg)); break;
        case FX_BEST: printf(" best:%s:%d", level_name((Level)e->arg), e->seconds); break;
        case FX_NEW_GAME: fputs(" new_game", stdout); break;
        case FX_SHOW_KEYS: fputs(" show_keys", stdout); break;
        case FX_UNHANDLED: fputs(" unhandled", stdout); break;
        case FX_REDRAW: fputs(" redraw", stdout); break;
        }
    }
    putchar('\n');
}

static void cmd_new(void)
{
    static int mines[MAX_W * MAX_H][2];
    int w = iarg(), h = iarg(), n = 0;
    Level level;
    if (!level_from_name(arg(), &level)) {
        fprintf(stderr, "replay: unknown level\n");
        exit(1);
    }
    char *spec = arg();
    if (strcmp(spec, "-") != 0)
        for (char *p = spec; *p && n < MAX_W * MAX_H; n++) {
            mines[n][0] = (int)strtol(p, &p, 10);
            mines[n][1] = (int)strtol(p + 1, &p, 10);
            if (*p == ';')
                p++;
        }
    Board b;
    if (board_init(&b, w, h, (const int (*)[2])mines, n) != 0) {
        fprintf(stderr, "replay: bad board\n");
        exit(1);
    }
    Game g;
    game_init(&g, level, &b);
    Effects fx = {0};
    session_new(&session, &g, &fx);
    print_fx(&fx);
}

static void points(const unsigned char cells[MAX_H][MAX_W], int pressed)
{
    const Board *b = &session.game.board;
    int any = 0;
    for (int x = 0; x < b->width; x++)            /* Python's sorted((x, y)) order */
        for (int y = 0; y < b->height; y++) {
            int on = pressed ? gestures_pressed(&session.gestures, x, y) : cells[y][x];
            if (on) {
                printf("%s%d,%d", any ? ";" : "", x, y);
                any = 1;
            }
        }
    if (!any)
        putchar('-');
    putchar('\n');
}

static void cmd_dump(void)
{
    static const char *const MODES[] = {"none", "single", "chord", "face"};
    static const char *const FACES[] = {"normal", "wow", "dead", "cool", "pressed"};
    const Game *g = &session.game;
    const Board *b = &g->board;
    State status = game_status(g);
    printf("dump status=%s state=%s revealed=%d counter=%d seconds=%d running=%d paused=%d "
           "mode=%s face=%s cursor=",
           state_name(status), state_name(b->state), b->revealed_count, game_counter(g),
           g->seconds, g->timer_running != 0, g->paused != 0, MODES[session.gestures.mode],
           FACES[gestures_face(&session.gestures, status)]);
    if (session.has_cursor)
        printf("%d,%d", session.cursor_x, session.cursor_y);
    else
        putchar('-');
    printf(" best=%d,%d,%d\nmarks=", best[0].seconds, best[1].seconds, best[2].seconds);
    for (int y = 0; y < b->height; y++) {
        if (y)
            putchar('/');
        for (int x = 0; x < b->width; x++)
            putchar(".F?#"[b->mark[y][x]]);
    }
    fputs("\nexploded=", stdout);
    points(b->exploded, 0);
    fputs("pressed=", stdout);
    points(b->exploded, 1);
}

static void cmd_settings(void)
{
    for (char *t = strtok(NULL, " "); t; t = strtok(NULL, " ")) {
        int on = strchr(t, '=') && strchr(t, '=')[1] == '1';
        if (strncmp(t, "marks=", 6) == 0)
            settings.marks = on;
        else if (strncmp(t, "color=", 6) == 0)
            settings.color = on;
        else if (strncmp(t, "sound=", 6) == 0)
            settings.sound = on;
    }
}

int main(int argc, char **argv)
{
#ifdef _WIN32
    _setmode(_fileno(stdout), _O_BINARY);
#endif
    if (argc != 2) {
        fprintf(stderr, "usage: replay <output-dir>\n");
        return 2;
    }
    (void)argv;                 /* the output directory: render and wav (Tasks 5-6) */
    settings.level = BEGINNER;
    settings.custom[0] = 9;
    settings.custom[1] = 9;
    settings.custom[2] = 10;
    settings.marks = settings.color = settings.zoom = 1;
    for (int i = 0; i < 3; i++) {
        best[i].seconds = 999;
        strcpy(best[i].name, "Anonymous");
    }
    session_init(&session, &settings, best);

    static char line[1 << 16];
    while (fgets(line, sizeof line, stdin)) {
        line[strcspn(line, "\r\n")] = 0;
        char *cmd = strtok(line, " ");
        Effects fx = {0};
        if (!cmd)
            continue;
        if (strcmp(cmd, "new") == 0) {
            cmd_new();
            continue;
        }
        if (strcmp(cmd, "press") == 0) {
            int button = iarg(), px = iarg(), py = iarg(), shift = iarg();
            session_press(&session, button, px, py, shift, held_arg(), &fx);
        } else if (strcmp(cmd, "release") == 0) {
            int button = iarg(), px = iarg(), py = iarg();
            session_release(&session, button, px, py, held_arg(), &fx);
        } else if (strcmp(cmd, "motion") == 0) {
            int px = iarg(), py = iarg();
            session_motion(&session, px, py, &fx);
        } else if (strcmp(cmd, "key") == 0) {
            session_key(&session, arg(), &fx);
        } else if (strcmp(cmd, "tick") == 0) {
            session_tick(&session, &fx);
        } else {
            if (strcmp(cmd, "settings") == 0)
                cmd_settings();
            else if (strcmp(cmd, "dump") == 0)
                cmd_dump();
            else {
                fprintf(stderr, "replay: unknown command %s\n", cmd);
                return 1;
            }
            continue;
        }
        print_fx(&fx);
    }
    return 0;
}
```

The `int button = iarg(), px = iarg(), …` declarations evaluate left to right (each declarator is a full expression with a sequence point), so the arguments are read in order.

- [ ] **Step 8: Write `win/test_core.c` and `win/Makefile`**

`win/test_core.c`:

```c
/* C unit tests for what the parity scripts don't reach. `make -C win test`. */
#include "core.h"

#include <stdio.h>
#include <string.h>

static int failures;

#define CHECK(cond)                                                          \
    do {                                                                     \
        if (!(cond)) {                                                       \
            printf("FAIL %s:%d: %s\n", __FILE__, __LINE__, #cond);           \
            failures++;                                                      \
        }                                                                    \
    } while (0)

static void test_clamp_custom(void)
{
    int c[3];
    clamp_custom(0, 0, 0, c);
    CHECK(c[0] == 9 && c[1] == 9 && c[2] == 10);
    clamp_custom(99, 99, 99999, c);
    CHECK(c[0] == 30 && c[1] == 24 && c[2] == 667);
    clamp_custom(9, 9, 100, c);
    CHECK(c[2] == 64);
}

static void test_layout_of_beginner(void)
{
    Layout lay;
    layout_of(9, 9, &lay);
    CHECK(lay.width == 168 && lay.height == 211 && lay.face_x == 72);
    layout_of(MAX_W, MAX_H, &lay);
    CHECK(lay.width == AREA_MAX_W && lay.height == AREA_MAX_H);
}

static void test_board_rejects_out_of_range(void)
{
    Board b;
    const int off[1][2] = {{9, 0}};
    CHECK(board_init(&b, 9, 9, off, 1) == -1);
    CHECK(board_init(&b, 31, 9, NULL, 0) == -1);
    const int twice[2][2] = {{1, 1}, {1, 1}};
    CHECK(board_init(&b, 9, 9, twice, 2) == 0 && b.mine_count == 1);
}

int main(void)
{
    test_clamp_custom();
    test_layout_of_beginner();
    test_board_rejects_out_of_range();
    if (!failures)
        printf("ok\n");
    return failures != 0;
}
```

`win/Makefile`:

```make
# make -C win            the Windows exe (MinGW-w64; MSYS2 UCRT64 on CI)
# make -C win test       the portable core's own tests, with any C compiler
# make -C win zigcheck   compile-check every Windows source on Linux with zig

CFLAGS  ?= -std=c11 -O2 -Wall -Wextra -pedantic -Werror
WINDEFS := -DUNICODE -D_UNICODE -D_WIN32_WINNT=0x0A00 -DWINVER=0x0A00
WINLIBS := -lwinmm -lcomctl32 -lshell32 -lole32 -luuid
WINDRES ?= windres
ZIG     ?= uvx --from ziglang python -m ziglang
ZIGCC   := $(ZIG) cc -target x86_64-windows-gnu

.PHONY: all test zigcheck clean

all: swaysweeper.exe

test: replay test_core
	./test_core

replay: replay.c core.c core.h sprites.h
	$(CC) $(CFLAGS) -o $@ replay.c core.c -lm

test_core: test_core.c core.c core.h sprites.h
	$(CC) $(CFLAGS) -o $@ test_core.c core.c -lm

clean:
	rm -f replay replay.exe test_core test_core.exe swaysweeper.exe swaysweeper.res.o \
	      wintest.exe zig-*.exe zig-*.pdb
```

(The exe, `wintest.exe` and `zigcheck` rules come in Tasks 7 and 8.)

Append to `.gitignore`:

```
win/replay
win/test_core
win/*.exe
win/*.o
win/*.pdb
win/captures/
```

- [ ] **Step 9: Run everything**

Run:
```bash
cd ~/repos/swaysweeper && make -C win test && /usr/bin/python3 -m unittest tests.test_win_parity tests.test_win_files -v 2>&1 | tail -4 && make test 2>&1 | tail -2
```
Expected: `ok` from `test_core`; the parity and file tests `OK` (13 parity, 5 file tests); the full suite `OK`. A parity failure prints the first differing line with both sides: find which side disagrees with `swaysweeper/*.py` (the Python is the reference) and fix the C, not the script.

- [ ] **Step 10: Commit**

```bash
git add win/core.h win/core.c win/replay.c win/test_core.c win/Makefile tests/replay.py \
        tests/test_win_parity.py tests/test_win_files.py .gitignore
git commit -m "feat(win): portable C core for rules and session, with replay parity" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_014cXNm1YtXA8z8QgkySFjrB"
```

---
### Task 5: The renderer, pixel for pixel with Cairo

Spec §3.1, §5 "Pixels". `render_session` paints the game area at ×1 into a `uint32_t` buffer (`0x00RRGGBB`) exactly as `render.draw` paints a Cairo `RGB24` surface. Parity compares PPMs byte for byte, in both colour sets.

**Files:**
- Modify: `win/core.h` (append declarations), `win/core.c` (include `sprites.h`; append the renderer), `win/replay.c` (`render`), `tests/replay.py` (`render`), `tests/test_win_parity.py` (pixel tests)

**Interfaces:**
- Consumes: `sprites.h` tables (Task 3); `Session`, `layout_of`, `board_cell_face`, `gestures_pressed`, `gestures_face`, `game_counter` (Task 4).
- Produces: `void render_session(const Session *s, uint32_t *pixels, int stride);` (writes `layout.width × layout.height` pixels, `stride` pixels per row; palette from `s->settings->color`), and `const char *core_keys_text(void);` (Task 7's Keys dialog).

- [ ] **Step 1: Write the failing pixel tests**

In `tests/replay.py`, add the imports `import cairo` and `from swaysweeper import colours, render` and `from swaysweeper import geometry as G`; in `Replay.__init__` add `self.cache = render.CellCache()`; in `run`, before the `raise`, add:

```python
        if cmd == "render":
            self._render(args[0])
            return []
```

and add the method:

```python
    def _render(self, name):
        g = self.session.game
        lay = G.layout(g.board.width, g.board.height)
        surf = cairo.ImageSurface(cairo.FORMAT_RGB24, lay.width, lay.height)
        face, pressed, cursor = self.session.paint_state()
        palette = colours.WIN95 if self.settings["color"] else colours.MONO
        render.draw(cairo.Context(surf), g, palette, pressed=pressed, face=face, cursor=cursor,
                    cache=self.cache)
        surf.flush()
        if surf.get_stride() != 4 * lay.width:
            raise ValueError("unexpected Cairo stride")
        data = bytes(surf.get_data())      # little-endian RGB24: B, G, R, unused
        rgb = bytearray(lay.width * lay.height * 3)
        rgb[0::3], rgb[1::3], rgb[2::3] = data[2::4], data[1::4], data[0::4]
        (self.outdir / name).write_bytes(f"P6\n{lay.width} {lay.height}\n255\n".encode()
                                         + bytes(rgb))
```

Append to `tests/test_win_parity.py`:

```python
class Pixels(Parity):
    def test_a_game_in_both_colour_sets(self):
        px, py = centre(3, 3)
        self.check([WALLED, "render a.ppm", *click(0, 0), "render b.ppm",
                    f"press 1 {px} {py} 0 -", "render c.ppm", f"release 1 {px} {py} 1",
                    "key Left", "render d.ppm", *click(5, 4, 3), *click(6, 4, 3), *click(6, 4, 3),
                    "render e.ppm", "settings color=0", "render f.ppm", "settings color=1",
                    *click(4, 0), "render g.ppm", "settings color=0", "render h.ppm"])

    def test_every_cell_face(self):
        cells = [(1, 1), (8, 8), (6, 0), (7, 0), (8, 0), (6, 1), (7, 1), (8, 1), (6, 2), (7, 2)]
        qx, qy = centre(3, 5)
        cx, cy = centre(0, 0)
        self.check(["new 9 9 beginner " + mines(cells), *click(0, 0), *click(3, 5, 3),
                    *click(3, 5, 3), f"press 1 {qx} {qy} 0 -", "render pressed-question.ppm",
                    "release 1 -20 -20 1", *click(0, 1, 3),
                    f"press 2 {cx} {cy} 0 -", "render chord-held.ppm",
                    f"release 2 {cx} {cy} 2", "render lost.ppm"])

    def test_a_win_and_the_pressed_face(self):
        fx, fy = FACE
        self.check(["new 9 9 beginner 8,8", *click(0, 0), "render won.ppm",
                    f"press 1 {fx} {fy} 0 -", "render face-pressed.ppm"])

    def test_largest_board(self):
        cells = [(x, y) for y in range(24) for x in range(30)]
        self.check(["new 30 24 custom " + mines(cells[53:]), *click(0, 0), "render big.ppm",
                    *["tick"] * 120, "render big-120.ppm"])

    def test_negative_counter(self):
        top = [(x, y) for y in range(4) for x in range(30)][:99]
        flags = [line for y in range(5, 12) for x in range(30) for line in click(x, y, 3)]
        self.check(["new 30 16 expert " + mines(top), "render c99.ppm", *flags[:2 * 104],
                    "render c-5.ppm", *flags[2 * 104:], "render c-99.ppm"])

    def test_random_walk_pixels(self):
        self.check(random_walk(seed=2, sessions=30, steps=30, render_every=10))
```

`test_negative_counter` places 104 flags against 99 mines (`-05`), then all 210 (−111, shown `-99`).

- [ ] **Step 2: Run them to verify they fail**

Run: `cd ~/repos/swaysweeper && /usr/bin/python3 -m unittest tests.test_win_parity.Pixels 2>&1 | tail -3`
Expected: failures with `replay: unknown command render`.

- [ ] **Step 3: Declare the renderer**

Append to `win/core.h`, just before `#endif /* RC_INVOKED */`:

```c
/* --- render.py -------------------------------------------------------------- */

/* The game area at x1 as 0x00RRGGBB, `stride` pixels per row, in Color on
 * (Windows 95) or Color off (monochrome) per s->settings->color. */
void render_session(const Session *s, uint32_t *pixels, int stride);
const char *core_keys_text(void);   /* the Keys dialog text, from session.KEYS */
```

- [ ] **Step 4: Write the renderer**

In `win/core.c`, add `#include "sprites.h"` and `#include <stdio.h>` after `#include "core.h"`, and append:

```c
/* --- render.py -------------------------------------------------------------- */

const char *core_keys_text(void)
{
    return KEYS_TEXT;
}

typedef struct {
    uint32_t *px;
    int stride, w, h;
    const uint32_t *palette;
} Canvas;

/* Cairo's rectangle + fill with antialiasing off, clipped to the canvas. */
static void fill(Canvas *c, int slot, int x, int y, int w, int h)
{
    if (w < 0) {
        x += w;
        w = -w;
    }
    if (h < 0) {
        y += h;
        h = -h;
    }
    int x0 = x < 0 ? 0 : x, y0 = y < 0 ? 0 : y;
    int x1 = x + w > c->w ? c->w : x + w, y1 = y + h > c->h ? c->h : y + h;
    for (int yy = y0; yy < y1; yy++)
        for (int xx = x0; xx < x1; xx++)
            c->px[yy * c->stride + xx] = c->palette[slot];
}

static const int BEVEL[3][2] = {
    {SLOT_LIGHT, SLOT_SHADOW}, {SLOT_SHADOW, SLOT_LIGHT}, {SLOT_SHADOW, SLOT_SHADOW},
};

/* `r.bevel` px lines inside r; the top-left colour wins the corners above
 * the diagonal, as Windows draws it. */
static void bevel(Canvas *c, Rect r)
{
    int first = BEVEL[r.style][0], second = BEVEL[r.style][1];
    for (int i = 0; i < r.bevel; i++) {
        fill(c, first, r.left, r.top + i, r.right - i - r.left + 1, 1);
        fill(c, first, r.left + i, r.top, 1, r.bottom - i - r.top + 1);
    }
    for (int i = 0; i < r.bevel; i++) {
        fill(c, second, r.left + i + 1, r.bottom - i, r.right - r.left - i, 1);
        fill(c, second, r.right - i, r.top + i + 1, 1, r.bottom - r.top - i);
    }
}

static void paint(Canvas *c, int sprite, int x, int y)
{
    const Sprite *s = &SPRITES[sprite];
    for (int dy = 0; dy < s->h; dy++)
        for (int dx = 0; dx < s->w; dx++) {
            int slot = LEGEND[(unsigned char)s->px[dy * s->w + dx] & 0x7f];
            if (slot)
                fill(c, slot - 1, x + dx, y + dy, 1, 1);
        }
}

static void draw_cell(Canvas *c, CellFace f, int x, int y)
{
    if (f == CF_COVERED || f == CF_FLAG || f == CF_QUESTION) {
        fill(c, SLOT_FACE, x, y, 16, 16);
        bevel(c, rect(x, y, x + 15, y + 15, 2, RAISED));
        if (f == CF_FLAG)
            paint(c, SPR_FLAG, x, y);
        else if (f == CF_QUESTION)
            paint(c, SPR_QUESTION, x, y);
        return;
    }
    fill(c, f == CF_EXPLODED ? SLOT_EXPLODED : SLOT_REVEALED, x, y, 16, 16);
    fill(c, SLOT_GRID, x, y, 16, 1);
    fill(c, SLOT_GRID, x, y, 1, 16);
    if (f == CF_MINE || f == CF_EXPLODED || f == CF_WRONG_FLAG)
        paint(c, SPR_MINE, x, y);
    else if (f == CF_QUESTION_PRESSED)
        paint(c, SPR_QUESTION, x, y);
    else if (f >= CF_OPEN1 && f <= CF_OPEN8)
        paint(c, SPR_OPEN1 + (f - CF_OPEN1), x, y);
    if (f == CF_WRONG_FLAG)
        paint(c, SPR_CROSS, x, y);
}

static void digits(Canvas *c, const int xs[3], const char *text)
{
    for (int i = 0; i < 3 && text[i]; i++)
        paint(c, text[i] == '-' ? SPR_LED_MINUS : SPR_LED_0 + (text[i] - '0'), xs[i], DIGIT_Y);
}

void render_session(const Session *s, uint32_t *pixels, int stride)
{
    const Game *g = &s->game;
    const Board *b = &g->board;
    Layout lay;
    layout_of(b->width, b->height, &lay);
    Canvas c = {pixels, stride, lay.width, lay.height,
                s->settings->color ? PALETTE_WIN95 : PALETTE_MONO};
    fill(&c, SLOT_FACE, 0, 0, lay.width, lay.height);
    const Rect frames[] = {lay.frame, lay.panel, lay.counter, lay.timer, lay.smiley, lay.board};
    for (size_t i = 0; i < sizeof frames / sizeof frames[0]; i++)
        bevel(&c, frames[i]);

    char text[16];
    int n = game_counter(g);
    if (n < 0)
        snprintf(text, sizeof text, "-%02d", -n);
    else
        snprintf(text, sizeof text, "%03d", n);
    digits(&c, lay.counter_x, text);
    snprintf(text, sizeof text, "%03d", g->seconds);
    digits(&c, lay.timer_x, text);
    State status = game_status(g);
    paint(&c, SPR_FACE_NORMAL + gestures_face(&s->gestures, status), lay.face_x, FACE_Y);

    for (int y = 0; y < b->height; y++)
        for (int x = 0; x < b->width; x++) {
            CellFace f = board_cell_face(b, x, y);
            if (gestures_pressed(&s->gestures, x, y)) {
                if (f == CF_COVERED)
                    f = CF_OPEN0;
                else if (f == CF_QUESTION)
                    f = CF_QUESTION_PRESSED;
            }
            draw_cell(&c, f, BOARD_X + CELL * x, BOARD_Y + CELL * y);
        }

    if (s->has_cursor) {
        int x = BOARD_X + CELL * s->cursor_x, y = BOARD_Y + CELL * s->cursor_y;
        fill(&c, SLOT_CURSOR, x, y, 16, 1);
        fill(&c, SLOT_CURSOR, x, y + 15, 16, 1);
        fill(&c, SLOT_CURSOR, x, y, 1, 16);
        fill(&c, SLOT_CURSOR, x + 15, y, 1, 16);
    }
}
```

- [ ] **Step 5: Teach `replay.c` to render**

Add above `main`:

```c
static const char *outdir;

static FILE *open_out(const char *name)
{
    char path[4096];
    snprintf(path, sizeof path, "%s/%s", outdir, name);
    FILE *f = fopen(path, "wb");
    if (!f) {
        perror(path);
        exit(1);
    }
    return f;
}

static void cmd_render(const char *name)
{
    static uint32_t px[AREA_MAX_W * AREA_MAX_H];
    Layout lay;
    layout_of(session.game.board.width, session.game.board.height, &lay);
    render_session(&session, px, lay.width);
    FILE *f = open_out(name);
    fprintf(f, "P6\n%d %d\n255\n", lay.width, lay.height);
    for (int i = 0; i < lay.width * lay.height; i++) {
        unsigned char rgb[3] = {(unsigned char)(px[i] >> 16), (unsigned char)(px[i] >> 8),
                                (unsigned char)px[i]};
        fwrite(rgb, 1, 3, f);
    }
    fclose(f);
}
```

In `main`, replace the `(void)argv;` line with `outdir = argv[1];`, and add to the non-event chain (next to `dump`):

```c
            else if (strcmp(cmd, "render") == 0)
                cmd_render(arg());
```

- [ ] **Step 6: Run the pixel tests, then everything**

Run:
```bash
cd ~/repos/swaysweeper && /usr/bin/python3 -m unittest tests.test_win_parity -v 2>&1 | tail -4 && make -C win test && make test 2>&1 | tail -2
```
Expected: `OK` (19 parity tests), `ok`, full suite `OK`. A PPM mismatch names the file and byte: byte `b` past the header (`len("P6\n<w> <h>\n255\n")`) is pixel `(b - header) // 3`, at `x = p % w`, `y = p // w`; compare that spot with `render.py`.

- [ ] **Step 7: Commit**

```bash
git add win/core.h win/core.c win/replay.c tests/replay.py tests/test_win_parity.py
git commit -m "feat(win): render the game area, byte-identical to the Cairo renderer" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_014cXNm1YtXA8z8QgkySFjrB"
```

---
### Task 6: Sounds, state files and the RNG

Spec §3.5, §3.7, §3.9. WAVs byte-identical to `sound.write_wav` (checked by parity); INI parse/format with `store.py`'s rules (checked by `test_core.c`, including the §3.5 reject list); xorshift64* seeded through splitmix64, mines by partial Fisher–Yates.

**Files:**
- Modify: `win/core.h`, `win/core.c`, `win/replay.c` (`wav`), `tests/replay.py` (`wav`), `tests/test_win_parity.py`, `win/test_core.c`

**Interfaces:**
- Consumes: Task 4's types.
- Produces (Task 7 calls all of these):
  - `enum { WAV_MAX = 20000, INI_MAX = 16384 };`
  - `size_t wav_build(SoundName name, unsigned char *out, size_t cap);` → bytes written, 0 if `cap` is too small.
  - `void settings_default(Settings *s);` `int settings_parse(const char *text, Settings *out);` `size_t settings_format(const Settings *s, char *buf, size_t cap);`
  - `void best_default(Best best[3]);` `int best_parse(const char *text, Best out[3]);` `size_t best_format(const Best best[3], char *buf, size_t cap);`
  - `int game_parse(const char *text, Game *out);` (sets `paused = 1`) `size_t game_format(const Game *g, char *buf, size_t cap);`
  - Parsers start from defaults and return 0, or −1 for a file to move aside. Formatters return the length, or 0 if `cap` is too small.
  - `uint64_t rng_seed(uint64_t entropy);` `uint64_t rng_next(uint64_t *state);` `void game_new(Game *g, Level level, const int custom[3], uint64_t *rng);`
  - INI keys — settings: `difficulty custom(w,h,m) marks color sound zoom x y`; best: `beginner intermediate expert` = `seconds,name`; game: `version difficulty seconds timer_running width height state mines exploded marks`, points as `x,y;x,y` (empty for none), marks rows joined by `/`.

- [ ] **Step 1: Write the failing WAV parity test**

In `tests/replay.py`, add `from swaysweeper.sound import TONES, write_wav` and, in `run` before the `raise`:

```python
        if cmd == "wav":
            write_wav(self.outdir / args[1], TONES[args[0]])
            return []
```

Append to `tests/test_win_parity.py`:

```python
class Sounds(Parity):
    def test_wav_bytes(self):
        self.check(["wav tick tick.wav", "wav win win.wav", "wav lose lose.wav"])
```

- [ ] **Step 2: Write the failing C tests**

Add to `win/test_core.c`, above `main` (and call each from `main`):

```c
static const char WALLED_GAME[] =
    "version=1\ndifficulty=beginner\nseconds=5\ntimer_running=1\nwidth=9\nheight=9\n"
    "state=playing\nmines=4,0;4,1;4,2;4,3;4,4;4,5;4,6;4,7;4,8;8,8\nexploded=\n"
    "marks=#...F..../........./........./........./........./........./........./"
    "........./.........\n";

static int replace_line(const char *text, const char *key, const char *line, char *out)
{
    /* Copies text with the line starting "key=" replaced by `line` (or dropped if NULL). */
    size_t k = strlen(key);
    out[0] = 0;
    int found = 0;
    for (const char *p = text; *p;) {
        const char *end = strchr(p, '\n');
        size_t n = end ? (size_t)(end - p + 1) : strlen(p);
        if (strncmp(p, key, k) == 0 && p[k] == '=') {
            found = 1;
            if (line) {
                strcat(out, line);
                strcat(out, "\n");
            }
        } else {
            strncat(out, p, n);
        }
        p += n;
    }
    return found;
}

static void test_settings_round_trip(void)
{
    Settings s, t;
    settings_default(&s);
    CHECK(s.level == BEGINNER && s.marks && s.color && !s.sound && s.zoom == 1 && !s.has_pos);
    s.level = CUSTOM;
    s.custom[0] = 30;
    s.custom[1] = 24;
    s.custom[2] = 667;
    s.sound = 1;
    s.zoom = 2;
    s.has_pos = 1;
    s.x = -1200;
    s.y = 40;
    char buf[INI_MAX];
    CHECK(settings_format(&s, buf, sizeof buf) > 0);
    CHECK(settings_parse(buf, &t) == 0);
    CHECK(t.level == CUSTOM && t.custom[0] == 30 && t.custom[1] == 24 && t.custom[2] == 667);
    CHECK(t.marks == 1 && t.color == 1 && t.sound == 1 && t.zoom == 2);
    CHECK(t.has_pos && t.x == -1200 && t.y == 40);
    CHECK(settings_format(&s, buf, 8) == 0);
}

static void test_settings_tolerate_bom_and_crlf(void)
{
    Settings s;
    CHECK(settings_parse("\xEF\xBB\xBF" "difficulty=expert\r\nsound=1\r\n\r\nzoom=2\r\n", &s) == 0);
    CHECK(s.level == EXPERT && s.sound == 1 && s.zoom == 2 && s.marks == 1);
}

static void test_settings_rules(void)
{
    Settings s;
    CHECK(settings_parse("custom=99,99,9999\nfuture=thing\n", &s) == 0);
    CHECK(s.custom[0] == 30 && s.custom[1] == 24 && s.custom[2] == 667);
    CHECK(settings_parse("x=5\n", &s) == 0 && !s.has_pos);
    CHECK(settings_parse("difficulty=hard\n", &s) == -1);
    CHECK(settings_parse("zoom=3\n", &s) == -1);
    CHECK(settings_parse("marks=yes\n", &s) == -1);
    CHECK(settings_parse("custom=9,9\n", &s) == -1);
    CHECK(settings_parse("sound\n", &s) == -1);
}

static void test_best_round_trip_and_names(void)
{
    Best b[3], c[3];
    best_default(b);
    CHECK(b[EXPERT].seconds == 999 && strcmp(b[EXPERT].name, "Anonymous") == 0);
    b[BEGINNER].seconds = 7;
    strcpy(b[BEGINNER].name, "Zo\xC3\xAB, the = best");
    char buf[INI_MAX];
    CHECK(best_format(b, buf, sizeof buf) > 0);
    CHECK(best_parse(buf, c) == 0);
    CHECK(c[BEGINNER].seconds == 7 && strcmp(c[BEGINNER].name, "Zo\xC3\xAB, the = best") == 0);

    char long_name[200] = "beginner=3,";
    for (int i = 0; i < 40; i++)
        strcat(long_name, "\xC3\xA9");                  /* 40 x e-acute */
    CHECK(best_parse(long_name, c) == 0 && strlen(c[BEGINNER].name) == 64);   /* 32 kept */
    CHECK(best_parse("beginner=0,x\n", c) == -1);
    CHECK(best_parse("beginner=1000,x\n", c) == -1);
    CHECK(best_parse("beginner=12\n", c) == -1);
    CHECK(best_parse("custom=5,x\nsomething=else\n", c) == 0 && c[BEGINNER].seconds == 999);
}

static void test_game_round_trip(void)
{
    Game g, h;
    CHECK(game_parse(WALLED_GAME, &g) == 0);
    CHECK(g.level == BEGINNER && g.seconds == 5 && g.timer_running && g.paused);
    CHECK(g.board.mine_count == 10 && g.board.revealed_count == 1);
    CHECK(g.board.mark[0][0] == REVEALED && g.board.mark[0][4] == FLAG);
    CHECK(game_status(&g) == PLAYING);
    game_release(&g, 3, 4, 0);
    game_release(&g, 4, 1, 0);                         /* lose: exploded (4,1) */
    char buf[INI_MAX];
    CHECK(game_format(&g, buf, sizeof buf) > 0);
    CHECK(game_parse(buf, &h) == 0);
    CHECK(h.board.state == LOST && h.board.exploded[1][4] && h.board.mark[4][3] == REVEALED);
    CHECK(memcmp(h.board.mine, g.board.mine, sizeof g.board.mine) == 0);
    CHECK(game_format(&g, buf, 16) == 0);
}

static void test_game_rejects(void)
{
    static const struct { const char *key, *line; } BAD[] = {
        {"seconds", "seconds"},                  /* missing '=' */
        {"seconds", "seconds=five"},             /* not an integer */
        {"seconds", "seconds=1000"},             /* out of range */
        {"marks", "marks=#...F.../........./........./........./........./........./"
                  "........./........./........."},          /* a short row */
        {"marks", "marks=#...X..../........./........./........./........./........./"
                  "........./........./........."},          /* unknown mark */
        {"state", "state=paused"},               /* unknown state */
        {"exploded", "exploded=0,0"},            /* exploded off a mine */
        {"version", "version=2"},                /* wrong version */
        {"mines", "mines=4,0;4,1;4,2;4,3;4,4;4,5;4,6;4,7;4,8"},     /* 9 mines on Beginner */
        {"mines", "mines=4,0;4,0;4,2;4,3;4,4;4,5;4,6;4,7;4,8;8,8"}, /* a repeated mine */
        {"mines", "mines=4,0;4,1;4,2;4,3;4,4;4,5;4,6;4,7;4,8;9,8"}, /* off the board */
        {"width", NULL},                         /* a missing key */
    };
    char text[INI_MAX];
    Game g;
    for (size_t i = 0; i < sizeof BAD / sizeof BAD[0]; i++) {
        CHECK(replace_line(WALLED_GAME, BAD[i].key, BAD[i].line, text));
        if (game_parse(text, &g) != -1) {
            printf("FAIL accepted a bad game.ini: %s\n", BAD[i].line ? BAD[i].line : "no width");
            failures++;
        }
    }
    CHECK(game_parse("\xEF\xBB\xBF" "garbage", &g) == -1);
}

static void test_rng_boards(void)
{
    uint64_t rng = rng_seed(0);
    CHECK(rng != 0);
    const int custom[3] = {30, 24, 667};
    for (int level = BEGINNER; level <= CUSTOM; level++) {
        Game g;
        game_new(&g, (Level)level, custom, &rng);
        int dims[3];
        level_dims((Level)level, custom, dims);
        CHECK(g.board.width == dims[0] && g.board.height == dims[1]);
        CHECK(g.board.mine_count == dims[2]);
        CHECK(g.level == (Level)level && game_status(&g) == READY);
    }
    uint64_t a = rng_seed(1), b = rng_seed(2);
    Game ga, gb;
    game_new(&ga, EXPERT, custom, &a);
    game_new(&gb, EXPERT, custom, &b);
    CHECK(memcmp(ga.board.mine, gb.board.mine, sizeof ga.board.mine) != 0);
}
```

Main becomes:

```c
int main(void)
{
    test_clamp_custom();
    test_layout_of_beginner();
    test_board_rejects_out_of_range();
    test_settings_round_trip();
    test_settings_tolerate_bom_and_crlf();
    test_settings_rules();
    test_best_round_trip_and_names();
    test_game_round_trip();
    test_game_rejects();
    test_rng_boards();
    if (!failures)
        printf("ok\n");
    return failures != 0;
}
```

- [ ] **Step 3: Run them to verify they fail**

Run: `cd ~/repos/swaysweeper && make -C win test 2>&1 | tail -3; /usr/bin/python3 -m unittest tests.test_win_parity.Sounds 2>&1 | tail -2`
Expected: compile errors for the undeclared `INI_MAX`, `settings_default`, …; the parity test fails with `replay: unknown command wav`.

- [ ] **Step 4: Declare them**

Append to `win/core.h`, before `#endif /* RC_INVOKED */`:

```c
/* --- sound.py: the three sounds as WAV files, byte for byte ----------------- */

enum { WAV_MAX = 20000, INI_MAX = 16384 };
size_t wav_build(SoundName name, unsigned char *out, size_t cap);

/* --- store.py's rules, in Windows' INI files (spec §3.5) --------------------- */
/* Parsers start from the defaults and return 0, or -1 for a file to move
 * aside. Formatters return the length written, or 0 if `cap` is too small. */

void settings_default(Settings *s);
int settings_parse(const char *text, Settings *out);
size_t settings_format(const Settings *s, char *buf, size_t cap);
void best_default(Best best[3]);
int best_parse(const char *text, Best out[3]);
size_t best_format(const Best best[3], char *buf, size_t cap);
int game_parse(const char *text, Game *out);    /* a resumed game starts paused */
size_t game_format(const Game *g, char *buf, size_t cap);

/* --- RNG: xorshift64*, seeded through splitmix64 ----------------------------- */

uint64_t rng_seed(uint64_t entropy);
uint64_t rng_next(uint64_t *state);
void game_new(Game *g, Level level, const int custom[3], uint64_t *rng);
```

- [ ] **Step 5: Implement them**

In `win/core.c`, add `#include <math.h>`, `#include <stdarg.h>` and `#include <stdlib.h>` to the includes, and append:

```c
/* --- sound.py --------------------------------------------------------------- */

typedef struct { double hz, seconds; } Note;
static const Note TICK_NOTES[] = {{1200, 0.02}};
static const Note WIN_NOTES[] = {{523, 0.08}, {659, 0.08}, {784, 0.16}};
static const Note LOSE_NOTES[] = {{196, 0.12}, {147, 0.25}};
static const struct { const Note *notes; int n; } TONES[] = {
    {TICK_NOTES, 1}, {WIN_NOTES, 3}, {LOSE_NOTES, 2},
};
enum { RATE = 22050 };

static void put16(unsigned char *p, unsigned v)
{
    p[0] = (unsigned char)(v & 0xff);
    p[1] = (unsigned char)((v >> 8) & 0xff);
}

static void put32(unsigned char *p, unsigned long v)
{
    put16(p, (unsigned)(v & 0xffff));
    put16(p + 2, (unsigned)((v >> 16) & 0xffff));
}

/* write_wav's square wave with the same double arithmetic: a sample is high
 * iff fmod(i, period) < period / 2. Then Python's wave module's 44-byte header. */
size_t wav_build(SoundName name, unsigned char *out, size_t cap)
{
    const int amplitude = (int)(0.2 * 32767);
    const Note *notes = TONES[name].notes;
    size_t samples = 0;
    for (int i = 0; i < TONES[name].n; i++)
        samples += (size_t)(int)(RATE * notes[i].seconds);
    size_t data = samples * 2, total = 44 + data;
    if (total > cap)
        return 0;
    memcpy(out, "RIFF", 4);
    put32(out + 4, (unsigned long)(36 + data));
    memcpy(out + 8, "WAVEfmt ", 8);
    put32(out + 16, 16);
    put16(out + 20, 1);                 /* PCM */
    put16(out + 22, 1);                 /* mono */
    put32(out + 24, RATE);
    put32(out + 28, RATE * 2);
    put16(out + 32, 2);
    put16(out + 34, 16);
    memcpy(out + 36, "data", 4);
    put32(out + 40, (unsigned long)data);
    unsigned char *p = out + 44;
    for (int k = 0; k < TONES[name].n; k++) {
        double period = (double)RATE / notes[k].hz;
        int count = (int)(RATE * notes[k].seconds);
        for (int i = 0; i < count; i++, p += 2) {
            int v = fmod((double)i, period) < period / 2 ? amplitude : -amplitude;
            put16(p, (unsigned)v & 0xffff);
        }
    }
    return total;
}

/* --- store.py's rules, in INI ------------------------------------------------ */

typedef int (*IniLine)(char *key, char *value, void *ctx);

/* Calls fn per `key=value` line: split on the first '=', a UTF-8 BOM and CRLF
 * tolerated, blank lines skipped. -1 on a line with no '=' or a refused value. */
static int ini_each(const char *text, IniLine fn, void *ctx)
{
    size_t len = strlen(text);
    char *copy = malloc(len + 1);
    if (!copy)
        return -1;
    memcpy(copy, text, len + 1);
    char *p = copy;
    if ((unsigned char)p[0] == 0xEF && (unsigned char)p[1] == 0xBB && (unsigned char)p[2] == 0xBF)
        p += 3;
    int rc = 0;
    while (*p && rc == 0) {
        char *end = strchr(p, '\n');
        char *next = end ? end + 1 : p + strlen(p);
        if (end)
            *end = 0;
        size_t n = strlen(p);
        if (n && p[n - 1] == '\r')
            p[n - 1] = 0;
        if (*p) {
            char *eq = strchr(p, '=');
            if (!eq)
                rc = -1;
            else {
                *eq = 0;
                rc = fn(p, eq + 1, ctx);
            }
        }
        p = next;
    }
    free(copy);
    return rc;
}

/* A whole decimal integer, optionally negative; nothing else. */
static int parse_int(const char *s, int *out)
{
    const char *p = s;
    int neg = *p == '-';
    p += neg;
    if (!*p)
        return 0;
    long v = 0;
    for (; *p; p++) {
        if (*p < '0' || *p > '9')
            return 0;
        v = v * 10 + (*p - '0');
        if (v > 1000000)
            return 0;
    }
    *out = (int)(neg ? -v : v);
    return 1;
}

static int parse_flag(const char *s, int *out)
{
    if (strcmp(s, "0") != 0 && strcmp(s, "1") != 0)
        return -1;
    *out = s[0] == '1';
    return 0;
}

/* Exactly n comma-separated integers. */
static int parse_ints(char *s, int *out, int n)
{
    for (int i = 0; i < n; i++) {
        char *comma = strchr(s, ',');
        if ((comma != NULL) != (i < n - 1))
            return 0;
        if (comma)
            *comma = 0;
        if (!parse_int(s, &out[i]))
            return 0;
        s = comma ? comma + 1 : s;
    }
    return 1;
}

typedef struct { char *buf; size_t cap, len; int ok; } Out;

static void outf(Out *o, const char *fmt, ...);

void settings_default(Settings *s)
{
    memset(s, 0, sizeof *s);
    s->level = BEGINNER;
    s->custom[0] = 9;
    s->custom[1] = 9;
    s->custom[2] = 10;
    s->marks = s->color = 1;
    s->zoom = 1;
}

typedef struct { Settings s; int seen_x, seen_y; } SettingsIni;

static int settings_line(char *key, char *value, void *ctx)
{
    SettingsIni *si = ctx;
    Settings *s = &si->s;
    int v[3];
    if (strcmp(key, "difficulty") == 0)
        return level_from_name(value, &s->level) ? 0 : -1;
    if (strcmp(key, "custom") == 0) {
        if (!parse_ints(value, v, 3))
            return -1;
        clamp_custom(v[0], v[1], v[2], s->custom);
        return 0;
    }
    if (strcmp(key, "marks") == 0)
        return parse_flag(value, &s->marks);
    if (strcmp(key, "color") == 0)
        return parse_flag(value, &s->color);
    if (strcmp(key, "sound") == 0)
        return parse_flag(value, &s->sound);
    if (strcmp(key, "zoom") == 0) {
        if (!parse_int(value, &v[0]) || (v[0] != 1 && v[0] != 2))
            return -1;
        s->zoom = v[0];
        return 0;
    }
    if (strcmp(key, "x") == 0 || strcmp(key, "y") == 0) {
        if (!parse_int(value, &v[0]))
            return -1;
        if (key[0] == 'x') {
            s->x = v[0];
            si->seen_x = 1;
        } else {
            s->y = v[0];
            si->seen_y = 1;
        }
        return 0;
    }
    return 0;                                   /* unknown keys are ignored */
}

int settings_parse(const char *text, Settings *out)
{
    SettingsIni si;
    memset(&si, 0, sizeof si);
    settings_default(&si.s);
    if (ini_each(text, settings_line, &si) != 0)
        return -1;
    si.s.has_pos = si.seen_x && si.seen_y;
    *out = si.s;
    return 0;
}

size_t settings_format(const Settings *s, char *buf, size_t cap)
{
    Out o = {buf, cap, 0, 1};
    outf(&o, "difficulty=%s\ncustom=%d,%d,%d\nmarks=%d\ncolor=%d\nsound=%d\nzoom=%d\n",
         level_name(s->level), s->custom[0], s->custom[1], s->custom[2], s->marks != 0,
         s->color != 0, s->sound != 0, s->zoom);
    if (s->has_pos)
        outf(&o, "x=%d\ny=%d\n", s->x, s->y);
    return o.ok ? o.len : 0;
}

void best_default(Best best[3])
{
    for (int i = 0; i < 3; i++) {
        best[i].seconds = 999;
        strcpy(best[i].name, "Anonymous");
    }
}

/* At most 32 code points and NAME_MAX_BYTES bytes, cut between characters. */
static void copy_name(char *dst, const char *src)
{
    size_t i = 0;
    for (int points = 0; src[i] && points < 32; points++) {
        unsigned char c = (unsigned char)src[i];
        size_t len = c >= 0xF0 ? 4 : c >= 0xE0 ? 3 : c >= 0xC0 ? 2 : 1;
        size_t k = 1;
        while (k < len && src[i + k])
            k++;
        if (k < len || i + len > NAME_MAX_BYTES)
            break;
        i += len;
    }
    memcpy(dst, src, i);
    dst[i] = 0;
}

static int best_line(char *key, char *value, void *ctx)
{
    Best *best = ctx;
    Level level;
    if (!level_from_name(key, &level) || level == CUSTOM)
        return 0;                               /* unknown keys are ignored */
    char *comma = strchr(value, ',');
    int seconds;
    if (!comma)
        return -1;
    *comma = 0;
    if (!parse_int(value, &seconds) || seconds < 1 || seconds > 999)
        return -1;
    best[level].seconds = seconds;
    copy_name(best[level].name, comma + 1);
    return 0;
}

int best_parse(const char *text, Best out[3])
{
    Best b[3];
    best_default(b);
    if (ini_each(text, best_line, b) != 0)
        return -1;
    memcpy(out, b, sizeof b);
    return 0;
}

size_t best_format(const Best best[3], char *buf, size_t cap)
{
    Out o = {buf, cap, 0, 1};
    for (int i = 0; i < 3; i++)
        outf(&o, "%s=%d,%s\n", level_name((Level)i), best[i].seconds, best[i].name);
    return o.ok ? o.len : 0;
}

enum { POINTS_MAX = 8 * MAX_W * MAX_H };   /* "29,23;" is 6 chars; room to spare */

typedef struct {
    unsigned seen;
    int version, seconds, running, width, height;
    Level level;
    State state;
    char mines[POINTS_MAX], exploded[POINTS_MAX], marks[(MAX_W + 1) * MAX_H + 1];
} GameIni;

enum {
    SEEN_VERSION = 1, SEEN_LEVEL = 2, SEEN_SECONDS = 4, SEEN_RUNNING = 8, SEEN_WIDTH = 16,
    SEEN_HEIGHT = 32, SEEN_STATE = 64, SEEN_MINES = 128, SEEN_EXPLODED = 256, SEEN_MARKS = 512,
    SEEN_ALL = 1023
};

static int copy_value(char *dst, size_t cap, const char *value)
{
    size_t n = strlen(value);
    if (n >= cap)
        return -1;
    memcpy(dst, value, n + 1);
    return 0;
}

static int game_line(char *key, char *value, void *ctx)
{
    GameIni *g = ctx;
    static const struct { const char *key; unsigned bit; } FIELDS[] = {
        {"version", SEEN_VERSION}, {"difficulty", SEEN_LEVEL}, {"seconds", SEEN_SECONDS},
        {"timer_running", SEEN_RUNNING}, {"width", SEEN_WIDTH}, {"height", SEEN_HEIGHT},
        {"state", SEEN_STATE}, {"mines", SEEN_MINES}, {"exploded", SEEN_EXPLODED},
        {"marks", SEEN_MARKS},
    };
    unsigned bit = 0;
    for (size_t i = 0; i < sizeof FIELDS / sizeof FIELDS[0]; i++)
        if (strcmp(key, FIELDS[i].key) == 0)
            bit = FIELDS[i].bit;
    g->seen |= bit;
    switch (bit) {
    case SEEN_VERSION: return parse_int(value, &g->version) ? 0 : -1;
    case SEEN_LEVEL: return level_from_name(value, &g->level) ? 0 : -1;
    case SEEN_SECONDS: return parse_int(value, &g->seconds) ? 0 : -1;
    case SEEN_RUNNING: return parse_flag(value, &g->running);
    case SEEN_WIDTH: return parse_int(value, &g->width) ? 0 : -1;
    case SEEN_HEIGHT: return parse_int(value, &g->height) ? 0 : -1;
    case SEEN_STATE:
        for (int s = READY; s <= LOST; s++)
            if (strcmp(value, STATE_NAMES[s]) == 0) {
                g->state = (State)s;
                return 0;
            }
        return -1;
    case SEEN_MINES: return copy_value(g->mines, sizeof g->mines, value);
    case SEEN_EXPLODED: return copy_value(g->exploded, sizeof g->exploded, value);
    case SEEN_MARKS: return copy_value(g->marks, sizeof g->marks, value);
    }
    return 0;                                   /* unknown keys are ignored */
}

/* "x,y;x,y" (empty for none) into out; the count, or -1. */
static int parse_points(char *s, int (*out)[2])
{
    int n = 0;
    while (*s) {
        char *semi = strchr(s, ';');
        if (semi)
            *semi = 0;
        if (n == MAX_W * MAX_H || !parse_ints(s, out[n], 2))
            return -1;
        n++;
        if (!semi)
            break;
        s = semi + 1;
        if (!*s)
            return -1;                          /* a trailing ';' */
    }
    return n;
}

int game_parse(const char *text, Game *out)
{
    static GameIni gi;
    static int points[MAX_W * MAX_H][2];
    memset(&gi, 0, sizeof gi);
    if (ini_each(text, game_line, &gi) != 0 || gi.seen != SEEN_ALL)
        return -1;
    if (gi.version != 1 || gi.seconds < 0 || gi.seconds > TIMER_MAX)
        return -1;

    Board b;
    int n = parse_points(gi.mines, points);
    if (n < 0 || board_init(&b, gi.width, gi.height, (const int (*)[2])points, n) != 0
        || b.mine_count != n)
        return -1;                              /* off the board, or repeated */

    char *row = gi.marks;
    for (int y = 0; y < b.height; y++) {
        char *slash = strchr(row, '/');
        if ((slash != NULL) != (y < b.height - 1))
            return -1;
        if (slash)
            *slash = 0;
        if ((int)strlen(row) != b.width)
            return -1;
        for (int x = 0; x < b.width; x++) {
            const char *m = strchr(".F?#", row[x]);
            if (!m || !row[x])
                return -1;
            b.mark[y][x] = (unsigned char)(m - ".F?#");
            b.revealed_count += b.mark[y][x] == REVEALED;
        }
        row = slash ? slash + 1 : row;
    }
    b.state = gi.state;

    n = parse_points(gi.exploded, points);
    if (n < 0)
        return -1;
    for (int i = 0; i < n; i++) {
        int x = points[i][0], y = points[i][1];
        if (x < 0 || x >= b.width || y < 0 || y >= b.height || !b.mine[y][x])
            return -1;                          /* exploded must be a mine */
        b.exploded[y][x] = 1;
    }

    int dims[3] = {b.width, b.height, b.mine_count}, want[3];
    if (gi.level == CUSTOM)
        clamp_custom(dims[0], dims[1], dims[2], want);
    else
        memcpy(want, PRESETS[gi.level], sizeof want);
    if (memcmp(dims, want, sizeof dims) != 0)
        return -1;

    game_init(out, gi.level, &b);
    out->seconds = gi.seconds;
    out->timer_running = gi.running;
    out->paused = 1;                            /* spec §5: resumes on first input */
    return 0;
}

static void out_points(Out *o, const unsigned char cells[MAX_H][MAX_W], const Board *b)
{
    int any = 0;
    for (int x = 0; x < b->width; x++)
        for (int y = 0; y < b->height; y++)
            if (cells[y][x]) {
                outf(o, "%s%d,%d", any ? ";" : "", x, y);
                any = 1;
            }
}

size_t game_format(const Game *g, char *buf, size_t cap)
{
    const Board *b = &g->board;
    Out o = {buf, cap, 0, 1};
    outf(&o, "version=1\ndifficulty=%s\nseconds=%d\ntimer_running=%d\nwidth=%d\nheight=%d\n"
             "state=%s\nmines=", level_name(g->level), g->seconds, g->timer_running != 0,
         b->width, b->height, state_name(b->state));
    out_points(&o, b->mine, b);
    outf(&o, "\nexploded=");
    out_points(&o, b->exploded, b);
    outf(&o, "\nmarks=");
    for (int y = 0; y < b->height; y++) {
        if (y)
            outf(&o, "/");
        for (int x = 0; x < b->width; x++)
            outf(&o, "%c", ".F?#"[b->mark[y][x]]);
    }
    outf(&o, "\n");
    return o.ok ? o.len : 0;
}

static void outf(Out *o, const char *fmt, ...)
{
    if (!o->ok)
        return;
    va_list ap;
    va_start(ap, fmt);
    int n = vsnprintf(o->buf + o->len, o->cap - o->len, fmt, ap);
    va_end(ap);
    if (n < 0 || (size_t)n >= o->cap - o->len)
        o->ok = 0;
    else
        o->len += (size_t)n;
}

/* --- RNG ---------------------------------------------------------------------- */

uint64_t rng_seed(uint64_t x)
{
    x += 0x9E3779B97F4A7C15ull;                 /* splitmix64 */
    x = (x ^ (x >> 30)) * 0xBF58476D1CE4E5B9ull;
    x = (x ^ (x >> 27)) * 0x94D049BB133111EBull;
    x ^= x >> 31;
    return x ? x : 0x9E3779B97F4A7C15ull;
}

uint64_t rng_next(uint64_t *state)
{
    uint64_t x = *state;                        /* xorshift64* */
    x ^= x >> 12;
    x ^= x << 25;
    x ^= x >> 27;
    *state = x;
    return x * 0x2545F4914F6CDD1Dull;
}

void game_new(Game *g, Level level, const int custom[3], uint64_t *rng)
{
    static int order[MAX_W * MAX_H], mines[MAX_W * MAX_H][2];
    int d[3];
    level_dims(level, custom, d);
    int cells = d[0] * d[1];
    for (int i = 0; i < cells; i++)
        order[i] = i;
    for (int i = 0; i < d[2]; i++) {           /* partial Fisher-Yates */
        int j = i + (int)(rng_next(rng) % (uint64_t)(cells - i));
        int t = order[i];
        order[i] = order[j];
        order[j] = t;
        mines[i][0] = order[i] % d[0];
        mines[i][1] = order[i] / d[0];
    }
    Board b;
    board_init(&b, d[0], d[1], (const int (*)[2])mines, d[2]);
    game_init(g, level, &b);
}
```

- [ ] **Step 6: Teach `replay.c` the `wav` command**

Add above `main`:

```c
static void cmd_wav(void)
{
    static unsigned char buf[WAV_MAX];
    const char *name = arg();
    SoundName which = strcmp(name, "win") == 0 ? SND_WIN : strcmp(name, "lose") == 0 ? SND_LOSE
                                                                                    : SND_TICK;
    size_t n = wav_build(which, buf, sizeof buf);
    FILE *f = open_out(arg());
    fwrite(buf, 1, n, f);
    fclose(f);
}
```

and next to `render` in `main`'s non-event chain:

```c
            else if (strcmp(cmd, "wav") == 0)
                cmd_wav();
```

- [ ] **Step 7: Run everything**

Run:
```bash
cd ~/repos/swaysweeper && make -C win test && /usr/bin/python3 -m unittest tests.test_win_parity -v 2>&1 | tail -3 && make test 2>&1 | tail -2
```
Expected: `ok` (no `FAIL` lines), `OK` (20 parity tests), full suite `OK`. If a WAV differs, the failure names the byte: header bytes are 0–43; sample `k` is bytes `44 + 2k`.

- [ ] **Step 8: Commit**

```bash
git add win/core.h win/core.c win/replay.c win/test_core.c tests/replay.py tests/test_win_parity.py
git commit -m "feat(win): WAV synthesis, INI state and the RNG in the core" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_014cXNm1YtXA8z8QgkySFjrB"
```

---
### Task 7: The Win32 shell — `main.c`, resources, manifest

Spec §1, §3.2–§3.8, §4, §8. Everything that touches Windows lives here; every game decision is a call into the core. It can't run locally: verify with `make -C win zigcheck` (compile-only, `-Werror`), then on the runner in Task 8.

**Files:**
- Create: `win/resource.h`, `win/swaysweeper.rc`, `win/swaysweeper.manifest`, `win/main.c`
- Modify: `win/Makefile` (exe and `zigcheck` rules)

**Interfaces:**
- Consumes: everything in `core.h` (Tasks 4–6); `win/swaysweeper.ico` (Task 3).
- Produces: `swaysweeper.exe` with window class `swaysweeper`, mutex `Local\io.github.xinye1.swaysweeper`, state in `%LOCALAPPDATA%\swaysweeper\*.ini`, `WM_PRINTCLIENT` painting the client area — `wintest.c` (Task 8) depends on all four.

- [ ] **Step 1: Write `win/resource.h`**

```c
/* Resource ids, shared by swaysweeper.rc and main.c. */
#ifndef SWAYSWEEPER_RESOURCE_H
#define SWAYSWEEPER_RESOURCE_H

#define IDI_APP 1               /* lowest id: Explorer's icon for the exe */
#define IDM_MENU 100
#define IDA_ACCEL 101

#define IDD_CUSTOM 200
#define IDD_NAME 201
#define IDD_BEST 202
#define IDD_KEYS 203
#define IDD_ABOUT 204

#define IDC_HEIGHT 300
#define IDC_WIDTH 301
#define IDC_MINES 302
#define IDC_PROMPT 303
#define IDC_NAME 304
#define IDC_SECS0 310           /* IDC_SECS0 + Level */
#define IDC_SECS1 311
#define IDC_SECS2 312
#define IDC_NAME0 320           /* IDC_NAME0 + Level */
#define IDC_NAME1 321
#define IDC_NAME2 322
#define IDC_RESET 330
#define IDC_KEYS_TEXT 331
#define IDC_ABOUT_TEXT 332

#define ID_NEW 1000
#define ID_BEGINNER 1001        /* ID_BEGINNER + Level, through ID_CUSTOM */
#define ID_INTERMEDIATE 1002
#define ID_EXPERT 1003
#define ID_CUSTOM 1004
#define ID_MARKS 1005
#define ID_COLOR 1006
#define ID_SOUND 1007
#define ID_ZOOM 1008
#define ID_BEST 1009
#define ID_EXIT 1010
#define ID_KEYS 1011
#define ID_ABOUT 1012

#endif
```

- [ ] **Step 2: Write `win/swaysweeper.manifest`**

```xml
<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<assembly xmlns="urn:schemas-microsoft-com:asm.v1" manifestVersion="1.0">
  <dependency>
    <dependentAssembly>
      <assemblyIdentity type="win32" name="Microsoft.Windows.Common-Controls" version="6.0.0.0"
                        processorArchitecture="*" publicKeyToken="6595b64144ccf1df" language="*"/>
    </dependentAssembly>
  </dependency>
  <application xmlns="urn:schemas-microsoft-com:asm.v3">
    <windowsSettings>
      <dpiAware xmlns="http://schemas.microsoft.com/SMI/2005/WindowsSettings">true/pm</dpiAware>
      <dpiAwareness xmlns="http://schemas.microsoft.com/SMI/2016/WindowsSettings">PerMonitorV2</dpiAwareness>
    </windowsSettings>
  </application>
  <trustInfo xmlns="urn:schemas-microsoft-com:asm.v3">
    <security>
      <requestedPrivileges>
        <requestedExecutionLevel level="asInvoker" uiAccess="false"/>
      </requestedPrivileges>
    </security>
  </trustInfo>
  <compatibility xmlns="urn:schemas-microsoft-com:compatibility.v1">
    <application>
      <supportedOS Id="{8e0f7a12-bfb3-4fe8-b9a5-48fd50a15a9a}"/>
    </application>
  </compatibility>
</assembly>
```

- [ ] **Step 3: Write `win/swaysweeper.rc`**

Saved as UTF-8 (it has `…` and `×`):

```rc
#pragma code_page(65001)
#include <windows.h>
#include "core.h"
#include "resource.h"

IDI_APP ICON "swaysweeper.ico"
CREATEPROCESS_MANIFEST_RESOURCE_ID RT_MANIFEST "swaysweeper.manifest"

IDM_MENU MENU
BEGIN
    POPUP "&Game"
    BEGIN
        MENUITEM "&New\tF2", ID_NEW
        MENUITEM SEPARATOR
        MENUITEM "&Beginner", ID_BEGINNER
        MENUITEM "&Intermediate", ID_INTERMEDIATE
        MENUITEM "&Expert", ID_EXPERT
        MENUITEM "&Custom…", ID_CUSTOM
        MENUITEM SEPARATOR
        MENUITEM "&Marks (?)", ID_MARKS
        MENUITEM "Co&lor", ID_COLOR
        MENUITEM "&Sound", ID_SOUND
        MENUITEM "&Zoom ×2", ID_ZOOM
        MENUITEM SEPARATOR
        MENUITEM "Best &Times…", ID_BEST
        MENUITEM SEPARATOR
        MENUITEM "E&xit\tCtrl+Q", ID_EXIT
    END
    POPUP "&Help"
    BEGIN
        MENUITEM "&Keys…\t?", ID_KEYS
        MENUITEM "&About swaysweeper", ID_ABOUT
    END
END

IDA_ACCEL ACCELERATORS
BEGIN
    VK_F2, ID_NEW, VIRTKEY
    "Q", ID_EXIT, VIRTKEY, CONTROL
END

IDD_CUSTOM DIALOGEX 0, 0, 132, 72
STYLE DS_SHELLFONT | DS_MODALFRAME | DS_CENTER | WS_POPUP | WS_CAPTION | WS_SYSMENU
CAPTION "Custom Field"
FONT 8, "MS Shell Dlg 2", 0, 0, 0x1
BEGIN
    LTEXT "&Height:", -1, 8, 10, 36, 8
    EDITTEXT IDC_HEIGHT, 46, 8, 32, 12, ES_NUMBER
    LTEXT "&Width:", -1, 8, 28, 36, 8
    EDITTEXT IDC_WIDTH, 46, 26, 32, 12, ES_NUMBER
    LTEXT "&Mines:", -1, 8, 46, 36, 8
    EDITTEXT IDC_MINES, 46, 44, 32, 12, ES_NUMBER
    DEFPUSHBUTTON "OK", IDOK, 88, 8, 36, 14
    PUSHBUTTON "Cancel", IDCANCEL, 88, 26, 36, 14
END

IDD_NAME DIALOGEX 0, 0, 140, 78
STYLE DS_SHELLFONT | DS_MODALFRAME | DS_CENTER | WS_POPUP | WS_CAPTION | WS_SYSMENU
CAPTION "Congratulations"
FONT 8, "MS Shell Dlg 2", 0, 0, 0x1
BEGIN
    CTEXT "", IDC_PROMPT, 8, 8, 124, 26
    EDITTEXT IDC_NAME, 20, 38, 100, 12, ES_AUTOHSCROLL
    DEFPUSHBUTTON "OK", IDOK, 52, 58, 36, 14
END

IDD_BEST DIALOGEX 0, 0, 176, 82
STYLE DS_SHELLFONT | DS_MODALFRAME | DS_CENTER | WS_POPUP | WS_CAPTION | WS_SYSMENU
CAPTION "Fastest Mine Sweepers"
FONT 8, "MS Shell Dlg 2", 0, 0, 0x1
BEGIN
    LTEXT "Beginner:", -1, 8, 10, 48, 8
    RTEXT "", IDC_SECS0, 56, 10, 44, 8
    LTEXT "", IDC_NAME0, 106, 10, 64, 8
    LTEXT "Intermediate:", -1, 8, 24, 48, 8
    RTEXT "", IDC_SECS1, 56, 24, 44, 8
    LTEXT "", IDC_NAME1, 106, 24, 64, 8
    LTEXT "Expert:", -1, 8, 38, 48, 8
    RTEXT "", IDC_SECS2, 56, 38, 44, 8
    LTEXT "", IDC_NAME2, 106, 38, 64, 8
    PUSHBUTTON "&Reset Scores", IDC_RESET, 8, 60, 60, 14
    DEFPUSHBUTTON "OK", IDOK, 132, 60, 36, 14
END

IDD_KEYS DIALOGEX 0, 0, 290, 196
STYLE DS_SHELLFONT | DS_MODALFRAME | DS_CENTER | WS_POPUP | WS_CAPTION | WS_SYSMENU
CAPTION "swaysweeper keys"
FONT 8, "MS Shell Dlg 2", 0, 0, 0x1
BEGIN
    LTEXT "", IDC_KEYS_TEXT, 8, 8, 274, 160
    DEFPUSHBUTTON "OK", IDOK, 246, 174, 36, 14
END

IDD_ABOUT DIALOGEX 0, 0, 180, 112
STYLE DS_SHELLFONT | DS_MODALFRAME | DS_CENTER | WS_POPUP | WS_CAPTION | WS_SYSMENU
CAPTION "About swaysweeper"
FONT 8, "MS Shell Dlg 2", 0, 0, 0x1
BEGIN
    ICON IDI_APP, -1, 8, 8, 20, 20
    LTEXT "", IDC_ABOUT_TEXT, 36, 8, 136, 74
    DEFPUSHBUTTON "OK", IDOK, 136, 90, 36, 14
END

VS_VERSION_INFO VERSIONINFO
FILEVERSION SWAYSWEEPER_VERSION_NUM
PRODUCTVERSION SWAYSWEEPER_VERSION_NUM
FILEOS VOS_NT_WINDOWS32
FILETYPE VFT_APP
BEGIN
    BLOCK "StringFileInfo"
    BEGIN
        BLOCK "040904b0"
        BEGIN
            VALUE "CompanyName", "xinye1"
            VALUE "FileDescription", "swaysweeper"
            VALUE "FileVersion", SWAYSWEEPER_VERSION
            VALUE "InternalName", "swaysweeper"
            VALUE "LegalCopyright", "MIT License"
            VALUE "OriginalFilename", "swaysweeper.exe"
            VALUE "ProductName", "swaysweeper"
            VALUE "ProductVersion", SWAYSWEEPER_VERSION
        END
    END
    BLOCK "VarFileInfo"
    BEGIN
        VALUE "Translation", 0x409, 1200
    END
END
```

- [ ] **Step 4: Write `win/main.c`**

```c
/* swaysweeper for Windows: window, menu, dialogs, timer, sound, files, DPI
 * and single instance around win/core.c, which holds the game itself.
 * Spec: docs/specs/2026-10-11-swaysweeper-windows-design.md. */
#include <windows.h>
#include <windowsx.h>
#include <commctrl.h>
#include <mmsystem.h>
#include <shlobj.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <wchar.h>
#include <wctype.h>

#include "core.h"
#include "resource.h"

#ifndef WM_GETDPISCALEDSIZE
#define WM_GETDPISCALEDSIZE 0x02E4
#endif

#define CLASS_NAME L"swaysweeper"
#define MUTEX_NAME L"Local\\io.github.xinye1.swaysweeper"
#define STYLE (WS_OVERLAPPED | WS_CAPTION | WS_SYSMENU | WS_MINIMIZEBOX)  /* windowing.c:835 */
enum { WM_APP_WON = WM_APP + 1, WM_APP_KEYS, TIMER_ID = 1, PATH_MAX_W = 2 * MAX_PATH };

static HWND g_wnd;
static Settings g_settings;
static Best g_best[3];
static Session g_session;
static uint64_t g_rng;
static uint32_t *g_pixels;
static wchar_t g_dir[MAX_PATH];
static int g_have_dir;
static unsigned char g_wav[3][WAV_MAX];
static int g_scale = 1, g_zoom_fits = 1;
static int g_minimised, g_timer_on, g_captured, g_releasing;
static int g_last_x = -100000, g_last_y = -100000;

static void apply(const Effects *fx);
static void apply_size(void);

/* --- state files (spec §3.5) ------------------------------------------------- */

static int init_state_dir(void)
{
    wchar_t base[MAX_PATH];
    DWORD n = GetEnvironmentVariableW(L"LOCALAPPDATA", base, MAX_PATH);
    if (n == 0 || n >= MAX_PATH) {
        PWSTR known = NULL;
        if (FAILED(SHGetKnownFolderPath(&FOLDERID_LocalAppData, 0, NULL, &known)))
            return 0;
        int fits = wcslen(known) < MAX_PATH;
        if (fits)
            wcscpy(base, known);
        CoTaskMemFree(known);
        if (!fits)
            return 0;
    }
    if (wcslen(base) + 16 >= MAX_PATH)
        return 0;
    wcscpy(g_dir, base);
    wcscat(g_dir, L"\\swaysweeper");
    CreateDirectoryW(g_dir, NULL);
    return 1;
}

static void state_path(const wchar_t *name, const wchar_t *suffix, wchar_t *out)
{
    wcscpy(out, g_dir);
    wcscat(out, L"\\");
    wcscat(out, name);
    wcscat(out, suffix);
}

/* The file's text, NUL-terminated, or NULL; *missing tells "not there" apart
 * from "unreadable", which gets moved aside. */
static char *read_text(const wchar_t *path, int *missing)
{
    *missing = 0;
    HANDLE f = CreateFileW(path, GENERIC_READ, FILE_SHARE_READ, NULL, OPEN_EXISTING,
                           FILE_ATTRIBUTE_NORMAL, NULL);
    if (f == INVALID_HANDLE_VALUE) {
        DWORD e = GetLastError();
        *missing = e == ERROR_FILE_NOT_FOUND || e == ERROR_PATH_NOT_FOUND;
        return NULL;
    }
    char *buf = malloc(INI_MAX + 1);
    DWORD got = 0;
    BOOL ok = buf && ReadFile(f, buf, INI_MAX, &got, NULL);
    CloseHandle(f);
    if (!ok || memchr(buf, 0, got)) {
        free(buf);
        return NULL;
    }
    buf[got] = 0;
    return buf;
}

static void quarantine(const wchar_t *name)
{
    wchar_t from[PATH_MAX_W], to[PATH_MAX_W];
    state_path(name, L".ini", from);
    state_path(name, L".ini.bad", to);
    MoveFileExW(from, to, MOVEFILE_REPLACE_EXISTING);
}

static int load(const wchar_t *name, int (*parse)(const char *, void *), void *out)
{
    if (!g_have_dir)
        return 0;
    wchar_t path[PATH_MAX_W];
    state_path(name, L".ini", path);
    int missing;
    char *text = read_text(path, &missing);
    if (!text) {
        if (!missing)
            quarantine(name);
        return 0;
    }
    int ok = parse(text, out) == 0;
    free(text);
    if (!ok)
        quarantine(name);
    return ok;
}

static int parse_settings(const char *text, void *out) { return settings_parse(text, out); }
static int parse_best(const char *text, void *out) { return best_parse(text, out); }
static int parse_game(const char *text, void *out) { return game_parse(text, out); }

/* Temp file in the same directory, flushed, then moved over the old one.
 * A failed write is ignored and the game goes on (spec §8). */
static void save_text(const wchar_t *name, const char *text, size_t len)
{
    if (!g_have_dir || !len)
        return;
    wchar_t path[PATH_MAX_W], tmp[PATH_MAX_W];
    state_path(name, L".ini", path);
    state_path(name, L".ini.tmp", tmp);
    HANDLE f = CreateFileW(tmp, GENERIC_WRITE, 0, NULL, CREATE_ALWAYS, FILE_ATTRIBUTE_NORMAL, NULL);
    if (f == INVALID_HANDLE_VALUE)
        return;
    DWORD put = 0;
    BOOL ok = WriteFile(f, text, (DWORD)len, &put, NULL) && put == len && FlushFileBuffers(f);
    CloseHandle(f);
    if (!ok || !MoveFileExW(tmp, path, MOVEFILE_REPLACE_EXISTING | MOVEFILE_WRITE_THROUGH))
        DeleteFileW(tmp);
}

static void save_settings(void)
{
    static char buf[INI_MAX];
    save_text(L"settings", buf, settings_format(&g_settings, buf, sizeof buf));
}

static void save_best(void)
{
    static char buf[INI_MAX];
    save_text(L"best", buf, best_format(g_best, buf, sizeof buf));
}

static void save_game(void)
{
    static char buf[INI_MAX];
    save_text(L"game", buf, game_format(&g_session.game, buf, sizeof buf));
}

static void delete_game(void)
{
    wchar_t path[PATH_MAX_W];
    if (!g_have_dir)
        return;
    state_path(L"game", L".ini", path);
    DeleteFileW(path);
}

/* --- scale, size and position (spec §3.3) ------------------------------------ */

static void area_size(int *w, int *h)
{
    Layout lay;
    layout_of(g_session.game.board.width, g_session.game.board.height, &lay);
    *w = lay.width;
    *h = lay.height;
}

static void outer_size(int scale, UINT dpi, int *w, int *h)
{
    int aw, ah;
    area_size(&aw, &ah);
    RECT r = {0, 0, aw * scale, ah * scale};
    AdjustWindowRectExForDpi(&r, STYLE, TRUE, 0, dpi);
    *w = r.right - r.left;
    *h = r.bottom - r.top;
}

static int fits(int scale, UINT dpi, const RECT *work)
{
    int w, h;
    outer_size(scale, dpi, &w, &h);
    return w <= work->right - work->left && h <= work->bottom - work->top;
}

static int base_scale(UINT dpi)
{
    int base = (int)(dpi + 48) / 96;             /* rounded: 125 % -> 1, 150-175 % -> 2 */
    return base < 1 ? 1 : base;
}

/* Zoom x2 doubles the base while that fits the work area; otherwise the game
 * shows at base for now and settings.ini keeps zoom=2 for when it fits again. */
static int wanted_scale(UINT dpi)
{
    int base = base_scale(dpi);
    return g_settings.zoom == 2 && g_zoom_fits ? base * 2 : base;
}

static void update_menu(void)
{
    HMENU m = GetMenu(g_wnd);
    CheckMenuRadioItem(m, ID_BEGINNER, ID_CUSTOM, ID_BEGINNER + (UINT)g_settings.level,
                       MF_BYCOMMAND);
    CheckMenuItem(m, ID_MARKS, MF_BYCOMMAND | (g_settings.marks ? MF_CHECKED : MF_UNCHECKED));
    CheckMenuItem(m, ID_COLOR, MF_BYCOMMAND | (g_settings.color ? MF_CHECKED : MF_UNCHECKED));
    CheckMenuItem(m, ID_SOUND, MF_BYCOMMAND | (g_settings.sound ? MF_CHECKED : MF_UNCHECKED));
    CheckMenuItem(m, ID_ZOOM, MF_BYCOMMAND | (g_settings.zoom == 2 ? MF_CHECKED : MF_UNCHECKED));
    EnableMenuItem(m, ID_ZOOM, MF_BYCOMMAND | (g_zoom_fits ? MF_ENABLED : MF_GRAYED));
}

static void apply_size(void)
{
    if (IsIconic(g_wnd))
        return;                                 /* redone on restore */
    UINT dpi = GetDpiForWindow(g_wnd);
    RECT wr;
    GetWindowRect(g_wnd, &wr);
    MONITORINFO mi;
    mi.cbSize = sizeof mi;
    GetMonitorInfoW(MonitorFromRect(&wr, MONITOR_DEFAULTTONEAREST), &mi);
    const RECT *work = &mi.rcWork;

    g_zoom_fits = fits(base_scale(dpi) * 2, dpi, work);
    g_scale = wanted_scale(dpi);
    while (g_scale > 1 && !fits(g_scale, dpi, work))
        g_scale--;

    int w, h, x = wr.left, y = wr.top;           /* the top-left stays put... */
    outer_size(g_scale, dpi, &w, &h);
    if (x + w > work->right)                    /* ...unless that leaves the work area */
        x = work->right - w;
    if (y + h > work->bottom)
        y = work->bottom - h;
    if (x < work->left)
        x = work->left;
    if (y < work->top)
        y = work->top;
    SetWindowPos(g_wnd, NULL, x, y, w, h, SWP_NOZORDER | SWP_NOACTIVATE);

    /* AdjustWindowRectEx* assumes a one-row menu; grow once if it wrapped
     * (cf. windowing.c:383-394). */
    int aw, ah;
    area_size(&aw, &ah);
    RECT cr;
    GetClientRect(g_wnd, &cr);
    if (cr.bottom != ah * g_scale)
        SetWindowPos(g_wnd, NULL, 0, 0, w, h + ah * g_scale - cr.bottom,
                     SWP_NOZORDER | SWP_NOACTIVATE | SWP_NOMOVE);
    update_menu();
    InvalidateRect(g_wnd, NULL, FALSE);
}

/* --- paint (spec §3.1) ------------------------------------------------------- */

static void blit(HDC dc)
{
    int w, h;
    area_size(&w, &h);
    render_session(&g_session, g_pixels, w);
    BITMAPINFO bi;
    memset(&bi, 0, sizeof bi);
    bi.bmiHeader.biSize = sizeof bi.bmiHeader;
    bi.bmiHeader.biWidth = w;
    bi.bmiHeader.biHeight = -h;                  /* top-down */
    bi.bmiHeader.biPlanes = 1;
    bi.bmiHeader.biBitCount = 32;
    bi.bmiHeader.biCompression = BI_RGB;
    SetStretchBltMode(dc, COLORONCOLOR);
    StretchDIBits(dc, 0, 0, w * g_scale, h * g_scale, 0, 0, w, h, g_pixels, &bi, DIB_RGB_COLORS,
                  SRCCOPY);
}

/* --- timer, sound, effects --------------------------------------------------- */

static void sync_timer(void)
{
    int want = game_ticking(&g_session.game) && !g_minimised;
    if (want && !g_timer_on)
        g_timer_on = SetTimer(g_wnd, TIMER_ID, 1000, NULL) != 0;
    else if (!want && g_timer_on) {
        KillTimer(g_wnd, TIMER_ID);
        g_timer_on = 0;
    }
}

static void new_game(void)
{
    Game game;
    game_new(&game, g_settings.level, g_settings.custom, &g_rng);
    Effects fx = {0};
    session_new(&g_session, &game, &fx);
    apply(&fx);
    apply_size();
}

/* Modal dialogs are never opened from here: input handlers call this, so a
 * best time or the Keys dialog is posted and opened after the gesture ends. */
static void apply(const Effects *fx)
{
    for (int i = 0; i < fx->n; i++) {
        const Effect *e = &fx->e[i];
        switch (e->kind) {
        case FX_SAVE: save_game(); break;
        case FX_DELETE: delete_game(); break;
        case FX_SOUND:
            PlaySoundW((LPCWSTR)(const void *)g_wav[e->arg], NULL,
                       SND_MEMORY | SND_ASYNC | SND_NODEFAULT);
            break;
        case FX_BEST:
            save_best();
            PostMessageW(g_wnd, WM_APP_WON, (WPARAM)e->arg, 0);
            break;
        case FX_NEW_GAME: new_game(); break;
        case FX_SHOW_KEYS: PostMessageW(g_wnd, WM_APP_KEYS, 0, 0); break;
        case FX_UNHANDLED: break;
        case FX_REDRAW: InvalidateRect(g_wnd, NULL, FALSE); break;
        }
    }
    sync_timer();
}

/* --- input (spec §3.2) ------------------------------------------------------- */

/* Client pixels to game-area pixels, rounding toward minus infinity so a
 * captured pointer left of or above the window stays off the board. */
static int to_game(int v)
{
    return v >= 0 ? v / g_scale : -((-v + g_scale - 1) / g_scale);
}

static unsigned held_from(WPARAM wp)
{
    return (wp & MK_LBUTTON ? BUTTON_BIT(LEFT) : 0u) | (wp & MK_MBUTTON ? BUTTON_BIT(MIDDLE) : 0u)
           | (wp & MK_RBUTTON ? BUTTON_BIT(RIGHT) : 0u);
}

static void mouse_down(int button, WPARAM wp, LPARAM lp)
{
    if (!g_captured) {
        SetCapture(g_wnd);
        g_captured = 1;
    }
    Effects fx = {0};
    session_press(&g_session, button, to_game(GET_X_LPARAM(lp)), to_game(GET_Y_LPARAM(lp)),
                  (wp & MK_SHIFT) != 0, held_from(wp), &fx);
    apply(&fx);
}

static void mouse_up(int button, WPARAM wp, LPARAM lp)
{
    Effects fx = {0};
    session_release(&g_session, button, to_game(GET_X_LPARAM(lp)), to_game(GET_Y_LPARAM(lp)),
                    held_from(wp), &fx);
    apply(&fx);
    if (g_captured && !(wp & (MK_LBUTTON | MK_MBUTTON | MK_RBUTTON))) {
        g_releasing = 1;                        /* ReleaseCapture sends WM_CAPTURECHANGED */
        ReleaseCapture();
        g_releasing = 0;
        g_captured = 0;
    }
}

static void mouse_move(LPARAM lp)
{
    int x = GET_X_LPARAM(lp), y = GET_Y_LPARAM(lp);
    if (x == g_last_x && y == g_last_y)
        return;                                 /* synthesised after dialogs and resizes */
    g_last_x = x;
    g_last_y = y;
    Effects fx = {0};
    session_motion(&g_session, to_game(x), to_game(y), &fx);
    apply(&fx);
}

static void lost_capture(void)
{
    g_captured = 0;
    g_session.gestures.mode = MODE_NONE;
    g_session.gestures.held = 0;
    InvalidateRect(g_wnd, NULL, FALSE);
}

static void key(const char *name)
{
    Effects fx = {0};
    session_key(&g_session, name, &fx);
    apply(&fx);
}

static int key_down(WPARAM vk)
{
    const char *name = vk == VK_LEFT ? "Left" : vk == VK_RIGHT ? "Right" : vk == VK_UP ? "Up"
                     : vk == VK_DOWN ? "Down" : NULL;
    if (!name || GetKeyState(VK_CONTROL) < 0)
        return 0;
    key(name);
    return 1;
}

static void key_char(WPARAM ch)
{
    static const struct { WCHAR ch; const char *name; } CHARS[] = {
        {L'h', "h"}, {L'j', "j"}, {L'k', "k"}, {L'l', "l"}, {L'f', "f"}, {L'c', "c"},
        {L' ', "space"}, {L'\r', "Return"}, {L'?', "question"},
    };
    if (GetKeyState(VK_CONTROL) < 0)            /* Ctrl+M is '\r' too */
        return;
    for (size_t i = 0; i < sizeof CHARS / sizeof CHARS[0]; i++)
        if (ch == CHARS[i].ch) {
            key(CHARS[i].name);
            return;
        }
}

/* --- dialogs (spec §3.6) ----------------------------------------------------- */

static void set_utf8(HWND dlg, int id, const char *text)
{
    wchar_t w[1024];
    if (!MultiByteToWideChar(CP_UTF8, 0, text, -1, w, 1024))
        w[0] = 0;
    SetDlgItemTextW(dlg, id, w);
}

static INT_PTR end_on_ok_or_cancel(HWND dlg, WPARAM wp)
{
    if (LOWORD(wp) == IDOK || LOWORD(wp) == IDCANCEL) {
        EndDialog(dlg, LOWORD(wp));
        return TRUE;
    }
    return FALSE;
}

static INT_PTR CALLBACK custom_proc(HWND dlg, UINT msg, WPARAM wp, LPARAM lp)
{
    int *custom = (int *)GetWindowLongPtrW(dlg, DWLP_USER);
    if (msg == WM_INITDIALOG) {
        SetWindowLongPtrW(dlg, DWLP_USER, lp);
        custom = (int *)lp;
        SetDlgItemInt(dlg, IDC_HEIGHT, (UINT)custom[1], FALSE);
        SetDlgItemInt(dlg, IDC_WIDTH, (UINT)custom[0], FALSE);
        SetDlgItemInt(dlg, IDC_MINES, (UINT)custom[2], FALSE);
        return TRUE;
    }
    if (msg == WM_COMMAND && LOWORD(wp) == IDOK) {
        /* winmine's GetDlgIntOfRange (windowing.c:219-223): clamp, never refuse.
         * Pasted non-digits get past ES_NUMBER and read as 0. */
        static const int IDS[3] = {IDC_WIDTH, IDC_HEIGHT, IDC_MINES};
        int v[3];
        for (int i = 0; i < 3; i++) {
            BOOL ok;
            UINT n = GetDlgItemInt(dlg, IDS[i], &ok, FALSE);
            v[i] = !ok ? 0 : n > 9999 ? 9999 : (int)n;
        }
        clamp_custom(v[0], v[1], v[2], custom);
        EndDialog(dlg, IDOK);
        return TRUE;
    }
    return msg == WM_COMMAND ? end_on_ok_or_cancel(dlg, wp) : FALSE;
}

/* Closing it any way at all records the name typed, as on Linux. */
static INT_PTR CALLBACK name_proc(HWND dlg, UINT msg, WPARAM wp, LPARAM lp)
{
    if (msg == WM_INITDIALOG) {
        SetWindowLongPtrW(dlg, DWLP_USER, lp);
        char prompt[128];
        snprintf(prompt, sizeof prompt, "You have the fastest time\nfor %s level.\n"
                 "Please type your name:", level_name((Level)lp));
        set_utf8(dlg, IDC_PROMPT, prompt);
        SendDlgItemMessageW(dlg, IDC_NAME, EM_SETLIMITTEXT, 32, 0);
        SetDlgItemTextW(dlg, IDC_NAME, L"Anonymous");
        SendDlgItemMessageW(dlg, IDC_NAME, EM_SETSEL, 0, -1);
        SetFocus(GetDlgItem(dlg, IDC_NAME));
        return FALSE;                           /* focus already set */
    }
    if (msg == WM_COMMAND && (LOWORD(wp) == IDOK || LOWORD(wp) == IDCANCEL)) {
        Level level = (Level)GetWindowLongPtrW(dlg, DWLP_USER);
        wchar_t typed[64];
        GetDlgItemTextW(dlg, IDC_NAME, typed, 64);
        wchar_t *start = typed;
        while (*start && iswspace(*start))
            start++;
        size_t n = wcslen(start);
        while (n && iswspace(start[n - 1]))
            start[--n] = 0;
        char name[NAME_MAX_BYTES + 1];
        if (!n || !WideCharToMultiByte(CP_UTF8, 0, start, -1, name, sizeof name, NULL, NULL))
            strcpy(name, "Anonymous");
        strcpy(g_best[level].name, name);
        save_best();
        EndDialog(dlg, IDOK);
        return TRUE;
    }
    return FALSE;
}

static void fill_best(HWND dlg)
{
    for (int i = 0; i < 3; i++) {
        char secs[32];
        snprintf(secs, sizeof secs, "%d seconds", g_best[i].seconds);
        set_utf8(dlg, IDC_SECS0 + i, secs);
        set_utf8(dlg, IDC_NAME0 + i, g_best[i].name);
    }
}

static INT_PTR CALLBACK best_proc(HWND dlg, UINT msg, WPARAM wp, LPARAM lp)
{
    (void)lp;
    if (msg == WM_INITDIALOG) {
        fill_best(dlg);
        return TRUE;
    }
    if (msg == WM_COMMAND && LOWORD(wp) == IDC_RESET) {
        best_default(g_best);
        save_best();
        fill_best(dlg);
        return TRUE;
    }
    return msg == WM_COMMAND ? end_on_ok_or_cancel(dlg, wp) : FALSE;
}

static INT_PTR CALLBACK keys_proc(HWND dlg, UINT msg, WPARAM wp, LPARAM lp)
{
    (void)lp;
    if (msg == WM_INITDIALOG) {
        /* The dialog's own font, DPI-scaled, in a fixed pitch: the text is a table. */
        LOGFONTW lf;
        HFONT dialog_font = (HFONT)SendMessageW(dlg, WM_GETFONT, 0, 0);
        if (GetObjectW(dialog_font, sizeof lf, &lf)) {
            wcscpy(lf.lfFaceName, L"Courier New");
            lf.lfPitchAndFamily = FIXED_PITCH | FF_MODERN;
            HFONT mono = CreateFontIndirectW(&lf);
            SetWindowLongPtrW(dlg, DWLP_USER, (LONG_PTR)mono);
            SendDlgItemMessageW(dlg, IDC_KEYS_TEXT, WM_SETFONT, (WPARAM)mono, FALSE);
        }
        set_utf8(dlg, IDC_KEYS_TEXT, core_keys_text());
        return TRUE;
    }
    if (msg == WM_DESTROY) {
        HFONT mono = (HFONT)GetWindowLongPtrW(dlg, DWLP_USER);
        if (mono)
            DeleteObject(mono);
        return FALSE;
    }
    return msg == WM_COMMAND ? end_on_ok_or_cancel(dlg, wp) : FALSE;
}

static INT_PTR CALLBACK about_proc(HWND dlg, UINT msg, WPARAM wp, LPARAM lp)
{
    (void)lp;
    if (msg == WM_INITDIALOG) {
        set_utf8(dlg, IDC_ABOUT_TEXT, "swaysweeper " SWAYSWEEPER_VERSION "\n\n"
                 "The classic Windows Minesweeper.\n\n"
                 "Inspired by omasweeper\n(github.com/jankeesvw/omasweeper).\n\nMIT License");
        return TRUE;
    }
    return msg == WM_COMMAND ? end_on_ok_or_cancel(dlg, wp) : FALSE;
}

static INT_PTR dialog(int id, DLGPROC proc, LPARAM param)
{
    return DialogBoxParamW(GetModuleHandleW(NULL), MAKEINTRESOURCEW(id), g_wnd, proc, param);
}

/* --- menu -------------------------------------------------------------------- */

static void set_level(Level level, const int custom[3])
{
    g_settings.level = level;
    if (custom)
        memcpy(g_settings.custom, custom, sizeof g_settings.custom);
    save_settings();
    new_game();
}

static void command(int id)
{
    switch (id) {
    case ID_NEW: new_game(); break;
    case ID_BEGINNER:
    case ID_INTERMEDIATE:
    case ID_EXPERT: set_level((Level)(id - ID_BEGINNER), NULL); break;
    case ID_CUSTOM: {
        int custom[3];
        memcpy(custom, g_settings.custom, sizeof custom);
        if (dialog(IDD_CUSTOM, custom_proc, (LPARAM)custom) == IDOK)
            set_level(CUSTOM, custom);
        break;
    }
    case ID_MARKS: g_settings.marks = !g_settings.marks; save_settings(); update_menu(); break;
    case ID_COLOR:
        g_settings.color = !g_settings.color;
        save_settings();
        update_menu();
        InvalidateRect(g_wnd, NULL, FALSE);
        break;
    case ID_SOUND: g_settings.sound = !g_settings.sound; save_settings(); update_menu(); break;
    case ID_ZOOM: g_settings.zoom = g_settings.zoom == 2 ? 1 : 2; save_settings(); apply_size(); break;
    case ID_BEST: dialog(IDD_BEST, best_proc, 0); break;
    case ID_EXIT: DestroyWindow(g_wnd); break;
    case ID_KEYS: dialog(IDD_KEYS, keys_proc, 0); break;
    case ID_ABOUT: dialog(IDD_ABOUT, about_proc, 0); break;
    }
}

/* --- the window -------------------------------------------------------------- */

static LRESULT CALLBACK wndproc(HWND hwnd, UINT msg, WPARAM wp, LPARAM lp)
{
    switch (msg) {
    case WM_PAINT: {
        PAINTSTRUCT ps;
        HDC dc = BeginPaint(hwnd, &ps);
        blit(dc);
        EndPaint(hwnd, &ps);
        return 0;
    }
    case WM_PRINTCLIENT: blit((HDC)wp); return 0;     /* PrintWindow, wintest's captures */
    case WM_ERASEBKGND: return 1;
    case WM_LBUTTONDOWN: mouse_down(LEFT, wp, lp); return 0;
    case WM_MBUTTONDOWN: mouse_down(MIDDLE, wp, lp); return 0;
    case WM_RBUTTONDOWN: mouse_down(RIGHT, wp, lp); return 0;
    case WM_LBUTTONUP: mouse_up(LEFT, wp, lp); return 0;
    case WM_MBUTTONUP: mouse_up(MIDDLE, wp, lp); return 0;
    case WM_RBUTTONUP: mouse_up(RIGHT, wp, lp); return 0;
    case WM_MOUSEMOVE: mouse_move(lp); return 0;
    case WM_CAPTURECHANGED:
        if (!g_releasing)
            lost_capture();
        return 0;
    case WM_KEYDOWN:
        if (key_down(wp))
            return 0;
        break;
    case WM_CHAR: key_char(wp); return 0;
    case WM_TIMER:
        if (wp == TIMER_ID) {
            Effects fx = {0};
            session_tick(&g_session, &fx);
            apply(&fx);
        }
        return 0;
    case WM_COMMAND: command(LOWORD(wp)); return 0;
    case WM_APP_WON:
        dialog(IDD_NAME, name_proc, (LPARAM)wp);
        dialog(IDD_BEST, best_proc, 0);
        return 0;
    case WM_APP_KEYS: command(ID_KEYS); return 0;
    case WM_SIZE:                               /* spec §3.4: not WM_SYSCOMMAND */
        if (wp == SIZE_MINIMIZED) {
            g_minimised = 1;
            PlaySoundW(NULL, NULL, 0);          /* winmine's FreeSound, game.c:467 */
            sync_timer();
        } else if (wp == SIZE_RESTORED && g_minimised) {
            g_minimised = 0;
            sync_timer();
            apply_size();
        }
        return 0;
    case WM_WINDOWPOSCHANGED: {
        const WINDOWPOS *pos = (const WINDOWPOS *)lp;
        if (!IsIconic(hwnd) && !(pos->flags & SWP_NOMOVE)) {
            g_settings.has_pos = 1;             /* windowing.c:591-596 */
            g_settings.x = pos->x;
            g_settings.y = pos->y;
        }
        break;                                  /* DefWindowProc sends WM_SIZE and WM_MOVE */
    }
    case WM_GETDPISCALEDSIZE: {
        int w, h;
        outer_size(wanted_scale((UINT)wp), (UINT)wp, &w, &h);
        ((SIZE *)lp)->cx = w;
        ((SIZE *)lp)->cy = h;
        return TRUE;
    }
    case WM_DPICHANGED: {
        const RECT *r = (const RECT *)lp;       /* only its top-left: no oscillation */
        SetWindowPos(hwnd, NULL, r->left, r->top, 0, 0,
                     SWP_NOZORDER | SWP_NOACTIVATE | SWP_NOSIZE);
        apply_size();
        return 0;
    }
    case WM_DISPLAYCHANGE: apply_size(); break;
    case WM_SETTINGCHANGE:
        if (wp == SPI_SETWORKAREA)
            apply_size();
        break;
    case WM_DESTROY:
        KillTimer(hwnd, TIMER_ID);
        PlaySoundW(NULL, NULL, 0);
        save_settings();                        /* the position */
        PostQuitMessage(0);
        return 0;
    }
    return DefWindowProcW(hwnd, msg, wp, lp);
}

/* A second launch brings the first window forward and exits (spec §3.8). */
static void forward_to_first(void)
{
    HWND w = NULL;
    for (int i = 0; i < 20 && !(w = FindWindowW(CLASS_NAME, NULL)); i++)
        Sleep(100);                             /* the first may not have a window yet */
    if (!w)
        return;
    if (IsIconic(w))
        ShowWindowAsync(w, SW_RESTORE);
    SetForegroundWindow(w);
}

int WINAPI wWinMain(HINSTANCE inst, HINSTANCE prev, PWSTR cmdline, int show)
{
    (void)prev;
    (void)cmdline;
    HANDLE mutex = CreateMutexW(NULL, FALSE, MUTEX_NAME);   /* before any state is read */
    if (mutex && GetLastError() == ERROR_ALREADY_EXISTS) {
        forward_to_first();
        return 0;
    }

    INITCOMMONCONTROLSEX icc = {sizeof icc, ICC_STANDARD_CLASSES};
    InitCommonControlsEx(&icc);
    g_pixels = malloc(sizeof *g_pixels * AREA_MAX_W * AREA_MAX_H);   /* once, at the largest */
    if (!g_pixels) {
        MessageBoxW(NULL, L"Not enough memory to start.", L"swaysweeper", MB_ICONERROR);
        return 1;
    }

    g_have_dir = init_state_dir();
    if (!load(L"settings", parse_settings, &g_settings))
        settings_default(&g_settings);
    if (!load(L"best", parse_best, g_best))
        best_default(g_best);

    LARGE_INTEGER now;
    QueryPerformanceCounter(&now);
    g_rng = rng_seed((uint64_t)now.QuadPart ^ ((uint64_t)GetCurrentProcessId() << 32));
    for (int i = 0; i < 3; i++)
        wav_build((SoundName)i, g_wav[i], WAV_MAX);

    session_init(&g_session, &g_settings, g_best);
    Game game;
    if (load(L"game", parse_game, &game) && game_status(&game) == PLAYING) {
        g_settings.level = game.level;
        if (game.level == CUSTOM) {
            g_settings.custom[0] = game.board.width;
            g_settings.custom[1] = game.board.height;
            g_settings.custom[2] = game.board.mine_count;
        }
    } else {
        delete_game();
        game_new(&game, g_settings.level, g_settings.custom, &g_rng);
    }
    g_session.game = game;                      /* not session_new: that deletes game.ini */

    WNDCLASSEXW wc;
    memset(&wc, 0, sizeof wc);
    wc.cbSize = sizeof wc;
    wc.style = 0;                               /* no CS_DBLCLKS: windowing.c:812 */
    wc.lpfnWndProc = wndproc;
    wc.hInstance = inst;
    wc.hIcon = LoadIconW(inst, MAKEINTRESOURCEW(IDI_APP));
    wc.hIconSm = (HICON)LoadImageW(inst, MAKEINTRESOURCEW(IDI_APP), IMAGE_ICON,
                                   GetSystemMetrics(SM_CXSMICON), GetSystemMetrics(SM_CYSMICON), 0);
    wc.hCursor = LoadCursorW(NULL, IDC_ARROW);
    wc.lpszClassName = CLASS_NAME;
    if (!RegisterClassExW(&wc))
        return 1;

    int x = g_settings.has_pos ? g_settings.x : CW_USEDEFAULT;
    int y = g_settings.has_pos ? g_settings.y : CW_USEDEFAULT;
    g_wnd = CreateWindowExW(0, CLASS_NAME, L"swaysweeper", STYLE, x, y, 200, 200, NULL,
                            LoadMenuW(inst, MAKEINTRESOURCEW(IDM_MENU)), inst, NULL);
    if (!g_wnd)
        return 1;
    HACCEL accel = LoadAcceleratorsW(inst, MAKEINTRESOURCEW(IDA_ACCEL));
    apply_size();                               /* scale, then clamp onto a monitor */
    ShowWindow(g_wnd, show);
    sync_timer();

    MSG msg;
    while (GetMessageW(&msg, NULL, 0, 0) > 0)
        if (!TranslateAcceleratorW(g_wnd, accel, &msg)) {
            TranslateMessage(&msg);
            DispatchMessageW(&msg);
        }
    return (int)msg.wParam;
}
```

- [ ] **Step 5: Add the exe and `zigcheck` rules to `win/Makefile`**

Insert after the `test_core` rule:

```make
swaysweeper.exe: main.c core.c core.h sprites.h resource.h swaysweeper.res.o
	$(CC) $(CFLAGS) $(WINDEFS) -municode -mwindows -o $@ main.c core.c swaysweeper.res.o \
	      $(WINLIBS) $(LDFLAGS)

swaysweeper.res.o: swaysweeper.rc swaysweeper.manifest swaysweeper.ico core.h resource.h
	$(WINDRES) -O coff -o $@ swaysweeper.rc

# Compile-only check on Linux: zig ships the mingw-w64 headers and an .rc compiler.
zigcheck:
	$(ZIGCC) $(CFLAGS) $(WINDEFS) -municode -o zig-swaysweeper.exe \
	    main.c core.c swaysweeper.rc $(WINLIBS)
	$(ZIGCC) $(CFLAGS) -o zig-replay.exe replay.c core.c
	rm -f zig-*.exe zig-*.pdb
	@echo zigcheck: ok
```

- [ ] **Step 6: Compile-check**

Run: `cd ~/repos/swaysweeper && make -C win zigcheck 2>&1 | tail -15`
Expected: `zigcheck: ok` and no warnings. zig's clang is stricter than gcc in places; fix the source, never relax the flags. If clang rejects something that only matters to gcc's headers (e.g. `#pragma code_page` in the `.rc`), record a `Ruling:` and adjust the minimum needed.

Also confirm the core still passes on Linux: `make -C win test && /usr/bin/python3 -m unittest tests.test_win_parity 2>&1 | tail -1` → `ok`, `OK`.

- [ ] **Step 7: Commit**

```bash
git add win/resource.h win/swaysweeper.rc win/swaysweeper.manifest win/main.c win/Makefile
git commit -m "feat(win): the Win32 shell — window, menu, dialogs, timer, DPI, state" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_014cXNm1YtXA8z8QgkySFjrB"
```

---
### Task 8: The desktop smoke test and CI, green on the Windows runner

Spec §6, §7. `wintest.exe` drives the real exe from a known saved game; `ci.yml` runs the Linux suite (with parity on gcc) and the Windows job (portable tests, parity against MinGW's core, the static exe, its DLL list, wintest, captures). This is the first time `main.c` runs: expect to iterate.

**Files:**
- Create: `win/wintest.c`, `.github/workflows/ci.yml`
- Modify: `win/Makefile` (`wintest.exe` rule; `zigcheck` also builds wintest)

**Interfaces:**
- Consumes: the exe's contract from Task 7 (class `swaysweeper`, `LOCALAPPDATA`, the INI formats from Task 6, `WM_PRINTCLIENT`); Task 1's ledger entry (which `PrintWindow` flag works; whether pycairo installs).
- Produces: a green `ci.yml` run on `feat/windows`; `wintest` prints `ok - …`/`FAIL - …` lines and exits with the failure count; captures as `win/captures/*.bmp` (artifact `captures`).

- [ ] **Step 1: Write `win/wintest.c`**

The spec's "timer advanced by 0 to 2" check reads the saved seconds from `game.ini` rather than the LED pixels, and is folded into the minimise/restore checks (stronger: it proves the pause and the resume). Pixel coordinates are game-area pixels at ×1, from `geometry.py` and `sprites.py` (cell (x, y) starts at `(12 + 16x, 55 + 16y)`):

| Check | Point | Colour | Why |
|---|---|---|---|
| smiley | (83, 19) | `FFFF00` | face at x 72; circle row 3, col 8, offset 3 |
| covered (1,1) | (28, 71), (43, 86) | `FFFFFF`, `808080` | raised bevel corners |
| open (0,0) | (13, 56), (12, 55) | `C0C0C0`, `808080` | no bevel; grid line |
| flag (4,0) | (82, 58) | `FF0000` | flag art row 3, col 6 |
| the 3 at (3,4) | (64, 122), (61, 120) | `FF0000`, `C0C0C0` | digit 3 row 0 col 1, stamped at (3,3) |
| flag (6,4) | (114, 122) | `FF0000` | as above |

```c
/* The Windows smoke test (spec §6): drives the real swaysweeper.exe on the
 * runner's desktop from a known saved game, and checks what it paints and
 * saves. Usage: wintest <path\to\swaysweeper.exe>. Writes captures\*.bmp. */
#include <windows.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <wchar.h>

#define PRINT_FLAGS PW_CLIENTONLY       /* Task 1's answer; PW_RENDERFULLCONTENT (2) if not */

static int failures;
static wchar_t g_state[MAX_PATH];
static const wchar_t *g_exe;

/* Beginner, in progress: a wall of mines down x = 4 and one at (8,8); (0,0)
 * open, the mine at (4,0) flagged, 5 seconds in. Every target is known. */
static const char SETTINGS_INI[] =
    "difficulty=beginner\ncustom=9,9,10\nmarks=1\ncolor=1\nsound=0\nzoom=1\nx=100\ny=100\n";
static const char GAME_INI[] =
    "version=1\ndifficulty=beginner\nseconds=5\ntimer_running=1\nwidth=9\nheight=9\n"
    "state=playing\nmines=4,0;4,1;4,2;4,3;4,4;4,5;4,6;4,7;4,8;8,8\nexploded=\n"
    "marks=#...F..../........./........./........./........./........./........./"
    "........./.........\n";

static void check(int ok, const char *what)
{
    printf("%s - %s\n", ok ? "ok" : "FAIL", what);
    fflush(stdout);
    failures += !ok;
}

static void state_file(const wchar_t *name, wchar_t *out)
{
    wcscpy(out, g_state);
    wcscat(out, L"\\");
    wcscat(out, name);
}

static void write_state(const wchar_t *name, const char *text)
{
    wchar_t path[MAX_PATH * 2];
    state_file(name, path);
    HANDLE f = CreateFileW(path, GENERIC_WRITE, 0, NULL, CREATE_ALWAYS, FILE_ATTRIBUTE_NORMAL, NULL);
    DWORD put;
    if (f != INVALID_HANDLE_VALUE) {
        WriteFile(f, text, (DWORD)strlen(text), &put, NULL);
        CloseHandle(f);
    }
}

static int read_state(const wchar_t *name, char *buf, DWORD cap)
{
    wchar_t path[MAX_PATH * 2];
    state_file(name, path);
    HANDLE f = CreateFileW(path, GENERIC_READ, FILE_SHARE_READ | FILE_SHARE_DELETE, NULL,
                           OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, NULL);
    DWORD got = 0;
    buf[0] = 0;
    if (f == INVALID_HANDLE_VALUE)
        return 0;
    ReadFile(f, buf, cap - 1, &got, NULL);
    CloseHandle(f);
    buf[got] = 0;
    return 1;
}

static int state_exists(const wchar_t *name)
{
    wchar_t path[MAX_PATH * 2];
    state_file(name, path);
    return GetFileAttributesW(path) != INVALID_FILE_ATTRIBUTES;
}

static int ini_int(const char *text, const char *key)
{
    size_t k = strlen(key);
    for (const char *p = text; p && *p;) {
        if (strncmp(p, key, k) == 0 && p[k] == '=')
            return atoi(p + k + 1);
        p = strchr(p, '\n');
        p = p ? p + 1 : NULL;
    }
    return -1;
}

static char mark_at(const char *text, int x, int y)
{
    const char *p = strstr(text, "\nmarks=");
    if (!p)
        return 0;
    p += 7;
    for (int row = 0; row < y && p; row++) {
        p = strchr(p, '/');
        p = p ? p + 1 : NULL;
    }
    return p ? p[x] : 0;
}

static HANDLE launch(DWORD *pid)
{
    STARTUPINFOW si;
    PROCESS_INFORMATION pi;
    memset(&si, 0, sizeof si);
    si.cb = sizeof si;
    wchar_t cmd[MAX_PATH + 3];
    wcscpy(cmd, L"\"");
    wcscat(cmd, g_exe);
    wcscat(cmd, L"\"");
    if (!CreateProcessW(NULL, cmd, NULL, NULL, FALSE, 0, NULL, NULL, &si, &pi))
        return NULL;
    CloseHandle(pi.hThread);
    *pid = pi.dwProcessId;
    return pi.hProcess;
}

typedef struct { DWORD pid; HWND found; } Find;

static BOOL CALLBACK find_window(HWND w, LPARAM lp)
{
    Find *f = (Find *)lp;
    DWORD pid = 0;
    wchar_t cls[32];
    GetWindowThreadProcessId(w, &pid);
    if (pid == f->pid && GetClassNameW(w, cls, 32) && wcscmp(cls, L"swaysweeper") == 0) {
        f->found = w;
        return FALSE;
    }
    return TRUE;
}

static HWND wait_window(DWORD pid)
{
    for (int i = 0; i < 100; i++) {
        Find f = {pid, NULL};
        EnumWindows(find_window, (LPARAM)&f);
        if (f.found && IsWindowVisible(f.found))
            return f.found;
        Sleep(100);
    }
    return NULL;
}

typedef struct {
    int w, h, scale;
    uint32_t *px;
    HBITMAP bmp;
} Shot;

static void save_bmp(const Shot *s, const char *name)
{
    char path[128];
    snprintf(path, sizeof path, "captures\\%s.bmp", name);
    FILE *f = fopen(path, "wb");
    if (!f)
        return;
    BITMAPFILEHEADER fh;
    BITMAPINFOHEADER ih;
    memset(&fh, 0, sizeof fh);
    memset(&ih, 0, sizeof ih);
    DWORD bytes = (DWORD)s->w * (DWORD)s->h * 4;
    fh.bfType = 0x4D42;
    fh.bfOffBits = sizeof fh + sizeof ih;
    fh.bfSize = fh.bfOffBits + bytes;
    ih.biSize = sizeof ih;
    ih.biWidth = s->w;
    ih.biHeight = -s->h;
    ih.biPlanes = 1;
    ih.biBitCount = 32;
    ih.biCompression = BI_RGB;
    fwrite(&fh, sizeof fh, 1, f);
    fwrite(&ih, sizeof ih, 1, f);
    fwrite(s->px, 1, bytes, f);
    fclose(f);
}

/* Waits for posted input and the repaint it causes, then PrintWindow. */
static int shoot(HWND w, int scale, Shot *s, const char *name)
{
    Sleep(500);
    RECT r;
    GetClientRect(w, &r);
    s->w = r.right;
    s->h = r.bottom;
    s->scale = scale;
    BITMAPINFO bi;
    memset(&bi, 0, sizeof bi);
    bi.bmiHeader.biSize = sizeof bi.bmiHeader;
    bi.bmiHeader.biWidth = s->w;
    bi.bmiHeader.biHeight = -s->h;
    bi.bmiHeader.biPlanes = 1;
    bi.bmiHeader.biBitCount = 32;
    bi.bmiHeader.biCompression = BI_RGB;
    HDC screen = GetDC(NULL), mem = CreateCompatibleDC(screen);
    void *bits = NULL;
    s->bmp = CreateDIBSection(mem, &bi, DIB_RGB_COLORS, &bits, NULL, 0);
    HGDIOBJ old = SelectObject(mem, s->bmp);
    BOOL ok = PrintWindow(w, mem, PRINT_FLAGS);
    GdiFlush();
    SelectObject(mem, old);
    DeleteDC(mem);
    ReleaseDC(NULL, screen);
    s->px = bits;
    if (bits)
        save_bmp(s, name);
    return ok && bits;
}

static uint32_t at(const Shot *s, int x, int y)
{
    return s->px[(y * s->scale) * s->w + x * s->scale] & 0xFFFFFF;
}

static void done(Shot *s)
{
    DeleteObject(s->bmp);
}

static void click(HWND w, int scale, int cx, int cy, int right)
{
    int x = (12 + 16 * cx + 8) * scale, y = (55 + 16 * cy + 8) * scale;
    POINT p = {x, y};
    ClientToScreen(w, &p);
    SetCursorPos(p.x, p.y);                     /* so real motion lands on the same square */
    LPARAM where = MAKELPARAM(x, y);
    PostMessageW(w, right ? WM_RBUTTONDOWN : WM_LBUTTONDOWN, right ? MK_RBUTTON : MK_LBUTTON, where);
    PostMessageW(w, right ? WM_RBUTTONUP : WM_LBUTTONUP, 0, where);
}

static int close_app(HWND w, HANDLE app)
{
    PostMessageW(w, WM_CLOSE, 0, 0);
    int ok = WaitForSingleObject(app, 5000) == WAIT_OBJECT_0;
    if (!ok)
        TerminateProcess(app, 1);
    CloseHandle(app);
    return ok;
}

static void check_board_after_clicks(const Shot *s)
{
    check(at(s, 64, 122) == 0xFF0000 && at(s, 61, 120) == 0xC0C0C0, "(3,4) shows an open 3");
    check(at(s, 114, 122) == 0xFF0000, "(6,4) shows a flag");
    check(at(s, 82, 58) == 0xFF0000, "(4,0) still shows its flag");
}

int wmain(int argc, wchar_t **argv)
{
    if (argc != 2) {
        fprintf(stderr, "usage: wintest <swaysweeper.exe>\n");
        return 2;
    }
    g_exe = argv[1];
    CreateDirectoryW(L"captures", NULL);

    wchar_t root[MAX_PATH];
    GetTempPathW(MAX_PATH - 40, root);
    wcscat(root, L"swaysweeper-wintest");
    CreateDirectoryW(root, NULL);
    SetEnvironmentVariableW(L"LOCALAPPDATA", root);         /* inherited by the exe */
    wcscpy(g_state, root);
    wcscat(g_state, L"\\swaysweeper");
    CreateDirectoryW(g_state, NULL);
    write_state(L"settings.ini", SETTINGS_INI);
    write_state(L"game.ini", GAME_INI);

    char ini[16384];
    Shot s;
    DWORD pid;

    /* 1. It starts on the saved game, at the Beginner size. */
    HANDLE app = launch(&pid);
    check(app != NULL, "launches");
    HWND w = app ? wait_window(pid) : NULL;
    check(w != NULL, "shows its window");
    if (!w)
        return 1;
    RECT r;
    GetClientRect(w, &r);
    int scale = r.right / 168 > 0 ? r.right / 168 : 1;
    printf("# client %ldx%ld, scale %d, dpi %u\n", r.right, r.bottom, scale, GetDpiForWindow(w));
    check(r.right == 168 * scale && r.bottom == 211 * scale, "client area is the Beginner area");

    /* 2. It paints the resumed game. */
    check(shoot(w, scale, &s, "01-resumed"), "PrintWindow captures the client area");
    check(at(&s, 83, 19) == 0xFFFF00, "the smiley is yellow");
    check(at(&s, 28, 71) == 0xFFFFFF && at(&s, 43, 86) == 0x808080, "a covered square is raised");
    check(at(&s, 13, 56) == 0xC0C0C0 && at(&s, 12, 55) == 0x808080, "the saved open square is open");
    check(at(&s, 82, 58) == 0xFF0000, "the saved flag is back");
    done(&s);

    /* 3-4. A left click opens a 3; a right click flags. */
    click(w, scale, 3, 4, 0);
    click(w, scale, 6, 4, 1);
    check(shoot(w, scale, &s, "02-clicked"), "captures after the clicks");
    check_board_after_clicks(&s);
    done(&s);

    /* Review Focus 1: minimised, the clock stops; restored, it runs. */
    PostMessageW(w, WM_SYSCOMMAND, SC_MINIMIZE, 0);
    Sleep(1500);
    check(IsIconic(w), "minimises");
    read_state(L"game.ini", ini, sizeof ini);
    int a = ini_int(ini, "seconds");
    Sleep(2500);
    read_state(L"game.ini", ini, sizeof ini);
    int b = ini_int(ini, "seconds");
    printf("# seconds while minimised: %d then %d\n", a, b);
    check(a >= 5 && a == b, "the timer stops while minimised");

    /* 6. A second launch exits and restores the first. */
    DWORD pid2;
    HANDLE second = launch(&pid2);
    check(second && WaitForSingleObject(second, 5000) == WAIT_OBJECT_0, "a second launch exits");
    if (second)
        CloseHandle(second);
    check(WaitForSingleObject(app, 0) == WAIT_TIMEOUT, "the first is still running");
    Sleep(500);
    check(!IsIconic(w), "the second launch restored the first");
    Sleep(2500);
    read_state(L"game.ini", ini, sizeof ini);
    int c = ini_int(ini, "seconds");
    printf("# seconds after the restore: %d\n", c);
    check(c > b, "the timer runs again after the restore");

    /* 5. It closes and keeps the unfinished game. */
    check(close_app(w, app), "closes on WM_CLOSE");
    check(read_state(L"game.ini", ini, sizeof ini), "game.ini is kept for an unfinished game");
    check(mark_at(ini, 3, 4) == '#' && mark_at(ini, 6, 4) == 'F', "game.ini holds the new marks");
    int d = ini_int(ini, "seconds");
    check(d >= c && d <= c + 3, "game.ini holds the time");

    /* ...and comes back the same. */
    app = launch(&pid);
    w = app ? wait_window(pid) : NULL;
    check(w != NULL, "relaunches");
    if (w) {
        check(shoot(w, scale, &s, "03-relaunched"), "captures the relaunched game");
        check_board_after_clicks(&s);
        done(&s);
        close_app(w, app);
    }

    /* Review Focus 4: a corrupt game.ini is moved aside; a fresh game starts. */
    write_state(L"game.ini", "this is not a game\n");
    app = launch(&pid);
    w = app ? wait_window(pid) : NULL;
    check(w != NULL, "starts despite a corrupt game.ini");
    check(state_exists(L"game.ini.bad"), "the corrupt game.ini is moved aside");
    if (w) {
        check(shoot(w, scale, &s, "04-fresh"), "captures the fresh game");
        check(at(&s, 61, 120) == 0xFFFFFF, "(3,4) is covered on the fresh board");
        done(&s);
        close_app(w, app);
    }

    printf("%d failure(s)\n", failures);
    return failures != 0;
}
```

- [ ] **Step 2: Add the `wintest.exe` rule and extend `zigcheck`**

In `win/Makefile`, after the `swaysweeper.res.o` rule:

```make
wintest.exe: wintest.c
	$(CC) $(CFLAGS) $(WINDEFS) -municode -o $@ wintest.c -lgdi32 -luser32 $(LDFLAGS)
```

and in `zigcheck`, before the `rm -f` line:

```make
	$(ZIGCC) $(CFLAGS) $(WINDEFS) -municode -o zig-wintest.exe wintest.c -lgdi32 -luser32
```

Run: `cd ~/repos/swaysweeper && make -C win zigcheck 2>&1 | tail -5`
Expected: `zigcheck: ok`, no warnings.

- [ ] **Step 3: Write `.github/workflows/ci.yml`**

```yaml
name: CI

# Runs once per PR when it is ready to merge (opened as ready, or a draft
# marked ready), not on every push. Re-run by hand with workflow_dispatch.
on:
  pull_request:
    types: [opened, reopened, ready_for_review]
  workflow_dispatch:
  push:
    branches: [feat/windows]   # TEMPORARY, development only: removed before the PR is marked ready

permissions:
  contents: read

jobs:
  linux:
    if: github.event_name != 'pull_request' || !github.event.pull_request.draft
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v5
        with:
          persist-credentials: false
      - name: Install GTK and PyGObject
        run: sudo apt-get update && sudo apt-get install -y python3-gi python3-cairo gir1.2-gtk-4.0
      - name: Python tests, including C parity with gcc
        run: make test PY=/usr/bin/python3
      - name: Portable C tests
        run: make -C win test

  windows:
    if: github.event_name != 'pull_request' || !github.event.pull_request.draft
    runs-on: windows-latest
    defaults:
      run:
        shell: msys2 {0}
    steps:
      - uses: actions/checkout@v5
        with:
          persist-credentials: false
      - uses: actions/setup-python@v6
        with:
          python-version: "3.13"
      - uses: msys2/setup-msys2@v2
        with:
          msystem: UCRT64
          update: false
          path-type: inherit
          install: mingw-w64-ucrt-x86_64-gcc make
      - name: Portable C tests
        run: make -C win test CC=gcc
      - name: Parity of the MinGW-built core with the Python implementation
        run: |
          python -m pip install pycairo
          SWAYSWEEPER_REPLAY=win/replay.exe python -m unittest tests.test_win_parity -v
      - name: Build the static exe
        run: make -C win swaysweeper.exe CC=gcc LDFLAGS="-static -s"
      - name: Only system DLLs
        run: |
          objdump -p win/swaysweeper.exe | grep 'DLL Name' | tee dlls.txt
          ! grep -viE 'DLL Name: (KERNEL32|USER32|GDI32|WINMM|COMCTL32|SHELL32|ole32|api-ms-win-crt-[a-z0-9-]+)\.dll' dlls.txt
      - name: Smoke test on the desktop
        run: |
          make -C win wintest.exe CC=gcc LDFLAGS=-static
          cd win && ./wintest.exe ./swaysweeper.exe
      - uses: actions/upload-artifact@v4
        if: always()
        with:
          name: captures
          path: win/captures/
          if-no-files-found: ignore
```

Apply Task 1's ledger rulings here: if pycairo didn't install, delete the parity step and record it; if `PW_CLIENTONLY` failed but `PW_RENDERFULLCONTENT` worked, change `PRINT_FLAGS` in `wintest.c`.

- [ ] **Step 4: Commit, push, and watch**

```bash
cd ~/repos/swaysweeper
git add win/wintest.c win/Makefile .github/workflows/ci.yml
git commit -m "ci: gated CI with a Windows job — parity, static exe, desktop smoke test" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_014cXNm1YtXA8z8QgkySFjrB"
git push
sleep 5; RUN=$(gh run list --branch feat/windows --workflow ci.yml --limit 1 --json databaseId -q '.[0].databaseId')
gh run watch "$RUN" --exit-status
```
Expected: both jobs green; the wintest log shows every line `ok - …` and `0 failure(s)`.

- [ ] **Step 5: Iterate until green**

On a red run: `gh run view "$RUN" --log-failed | tail -80`, and for wintest failures `gh run download "$RUN" -n captures -D /tmp/claude-1000/captures-$RUN` and look at the BMPs (Read tool renders images). Use superpowers:systematic-debugging: find the cause, write or adjust a test that pins it where one can run (Linux core tests, parity, or a wintest check), fix, `make -C win zigcheck`, commit (`fix(win): …`), push, watch. A wrong expected pixel in wintest is fixed only after confirming against `sprites.py`/`geometry.py` which side is wrong. Ledger each fix as a `Ruling:` if it changes anything the spec says.

Known likely trouble, with the first thing to try:
- Linux job: the runner's Python lacks something `make test` needs → check which test fails; the GTK tests need only the apt packages above.
- `objdump` lists a DLL outside the allow-list (e.g. `libwinpthread-1.dll`) → the link isn't static: confirm `LDFLAGS="-static -s"` reached the link line.
- wintest can't find the window → print `GetLastError()` after `CreateProcessW`; check the class name.
- Captures are black → switch `PRINT_FLAGS` to `2` (`PW_RENDERFULLCONTENT`) and record the ruling.

- [ ] **Step 6: Ledger the green run**

When green, note the run id in the ledger with the wintest summary (`0 failure(s)`, client size, DPI).

---
### Task 9: Release workflow, version bump, README

Spec §2.3 "Version", §7. `release.yml` builds the static exe from the tagged source and attaches it with its checksum; both version strings become `0.1.0-beta.2`.

**Files:**
- Create: `.github/workflows/release.yml`
- Modify: `swaysweeper/__init__.py:3`, `win/core.h` (two `#define`s), `README.md` (Install section)

**Interfaces:**
- Consumes: the `swaysweeper.exe` Makefile target (Task 7); the version test (Task 4).
- Produces: on `release: published`, assets `swaysweeper-windows-x86_64.exe` and `swaysweeper-windows-x86_64.exe.sha256` on that release.

- [ ] **Step 1: Bump the Python version and watch the guard catch it**

Set `swaysweeper/__init__.py` to `__version__ = "0.1.0-beta.2"`.

Run: `cd ~/repos/swaysweeper && /usr/bin/python3 -m unittest tests.test_win_files 2>&1 | tail -3`
Expected: `test_c_version_matches_python` FAILS (core.h still says beta.1).

- [ ] **Step 2: Bump the C version**

In `win/core.h`:

```c
#define SWAYSWEEPER_VERSION "0.1.0-beta.2"
#define SWAYSWEEPER_VERSION_NUM 0,1,0,2
```

Run: `/usr/bin/python3 -m unittest tests.test_win_files 2>&1 | tail -1 && make test 2>&1 | tail -1`
Expected: `OK`, `OK`.

- [ ] **Step 3: Write `.github/workflows/release.yml`**

```yaml
name: Release

# Builds the Windows exe for a published GitHub release and attaches it.
on:
  release:
    types: [published]

permissions:
  contents: write

env:
  TAG: ${{ github.event.release.tag_name }}

jobs:
  windows:
    runs-on: windows-latest
    steps:
      - uses: actions/checkout@v5
        with:
          persist-credentials: false # the upload step passes its token itself
      - name: Check both versions match the tag
        shell: bash
        run: |
          py=$(sed -n 's/^__version__ = "\(.*\)"$/\1/p' swaysweeper/__init__.py)
          c=$(sed -n 's/^#define SWAYSWEEPER_VERSION "\(.*\)"$/\1/p' win/core.h)
          if [ "v$py" != "$TAG" ] || [ "v$c" != "$TAG" ]; then
            echo "__init__.py says $py and core.h says $c, but the release tag is $TAG"
            exit 1
          fi
      - uses: msys2/setup-msys2@v2
        with:
          msystem: UCRT64
          update: false
          install: mingw-w64-ucrt-x86_64-gcc make
      - name: Test and build (static, stripped)
        shell: msys2 {0}
        run: |
          make -C win test CC=gcc
          make -C win swaysweeper.exe CC=gcc LDFLAGS="-static -s"
      - name: Upload to the release
        shell: bash
        env:
          GH_TOKEN: ${{ github.token }}
        run: |
          asset=swaysweeper-windows-x86_64.exe
          cp win/swaysweeper.exe "$asset"
          sha256sum "$asset" > "$asset.sha256"
          gh release upload "$TAG" "$asset" "$asset.sha256" --clobber
```

- [ ] **Step 4: Add the Windows section to the README**

Replace the `## Install` section of `README.md` with:

````markdown
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
````

and add to the `## State` section:

```markdown
On Windows: `%LOCALAPPDATA%\swaysweeper\` (`*.ini`), with the same rules.
```

- [ ] **Step 5: Commit and push (CI runs on the push)**

```bash
cd ~/repos/swaysweeper
git add .github/workflows/release.yml swaysweeper/__init__.py win/core.h README.md
git commit -m "chore: version 0.1.0-beta.2; release workflow and Windows README" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_014cXNm1YtXA8z8QgkySFjrB"
git push
sleep 5; RUN=$(gh run list --branch feat/windows --workflow ci.yml --limit 1 --json databaseId -q '.[0].databaseId')
gh run watch "$RUN" --exit-status
```
Expected: green.

---

### Task 10: Ship — review, merge, publish `v0.1.0-beta.2`

Use the `ship` skill's flow (memory: the CodeRabbit CLI via `~/.claude/skills/ship/scripts/cr_review.sh`; the app review at the PR head is the fallback gate when the CLI is rate-limited). The repo's CI is pre-merge-gated, so: draft PR → review → fix → mark ready (the one gated CI run) → merge → release.

**Files:**
- Modify: `.github/workflows/ci.yml` (drop the temporary `push` trigger)

**Interfaces:**
- Consumes: Tasks 1–9 on `feat/windows`.
- Produces: `feat/windows` merged to `main`; pre-release `v0.1.0-beta.2` carrying `swaysweeper-windows-x86_64.exe` and its `.sha256`; the local install updated.

- [ ] **Step 1: Remove the development trigger**

Delete these two lines from `.github/workflows/ci.yml`:

```yaml
  push:
    branches: [feat/windows]   # TEMPORARY, development only: removed before the PR is marked ready
```

Run: `grep -n "push:\|TEMPORARY" .github/workflows/ci.yml`
Expected: nothing.

```bash
git add .github/workflows/ci.yml
git commit -m "ci: drop the development push trigger" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_014cXNm1YtXA8z8QgkySFjrB"
git push
```

- [ ] **Step 2: Final whole-branch review (executing-plans' fresh reviewer)**

Per superpowers:executing-plans "Final Review", on the branch range `git merge-base origin/main HEAD..HEAD`, with this plan's Review Focus list. Fix Critical/Important findings TDD-style (Linux tests, parity, or a wintest check), each a commit; push.

- [ ] **Step 3: Open the draft PR**

```bash
gh pr create --draft --base main --title "Windows: a native Win32 build" --body "$(cat <<'EOF'
## Summary
- `swaysweeper/session.py`: the session logic moves out of the GTK modules (events in, effects out); the GTK app is a thin host over it. Behaviour unchanged.
- `win/`: a portable C11 core (rules, session, renderer, WAV, INI state, RNG) and a Win32 shell (`main.c`, menu, dialogs, DPI, single instance) building one static `swaysweeper.exe`.
- Parity: `tests/test_win_parity.py` replays the same scripts through the C core and the Python code and compares every line, PPM and WAV byte, on gcc/Linux and MinGW/Windows.
- `wintest.c` drives the real exe on the Windows runner: paint, clicks, minimise pause, single instance, save/resume, a corrupt file.
- Gated CI (Linux + Windows) and a release workflow that attaches the exe and its sha256. Version 0.1.0-beta.2.

Spec: `docs/specs/2026-10-11-swaysweeper-windows-design.md`. Plan: `docs/plans/2026-10-11-swaysweeper-windows.md`.

## Test plan
- [x] `make test` (Python suite + C parity with gcc)
- [x] `make -C win test`, `make -C win zigcheck`
- [ ] CI: Linux and Windows jobs green on the ready PR
- [ ] Hands-on: DPI 125/150/175 %, a second monitor, Zoom ×2, dialogs and the feel (not verifiable on the runner)

🤖 Generated with [Claude Code](https://claude.com/claude-code)

https://claude.ai/code/session_014cXNm1YtXA8z8QgkySFjrB
EOF
)"
```

- [ ] **Step 4: CodeRabbit review, posted to the PR**

```bash
cd ~/repos/swaysweeper && git fetch origin main
bash ~/.claude/skills/ship/scripts/cr_review.sh /tmp/claude-1000/cr-win.txt --base origin/main --committed; echo "exit $?"
```
Run it in the background and read the file when it finishes. Exit 0 with a `Review complete` trailer is the gate; exit 3 (rate-limited for 3 h) → use the app review at the PR head (it reviews once the PR is ready; see memory `coderabbit-app-review-as-gate`). Verify each finding against the diff; fix real ones (each with a test where one can run), push, re-review. Post the final review: `sed 's/[\x1b\x07]//g' /tmp/claude-1000/cr-win.txt > /tmp/claude-1000/cr-win.md && gh pr comment <PR> --body-file /tmp/claude-1000/cr-win.md`.

- [ ] **Step 5: Mark ready (the one gated CI run) and merge**

```bash
gh pr ready <PR>
gh pr checks <PR> --watch
gh pr merge <PR> --merge --delete-branch
git checkout main && git pull --ff-only
```
Expected: both checks pass; the merge commit on `main`.

- [ ] **Step 6: Publish the pre-release and verify its assets**

```bash
SHA=$(git rev-parse HEAD)            # full SHA: a short one gets HTTP 422
gh release create v0.1.0-beta.2 --prerelease --target "$SHA" --title "swaysweeper 0.1.0-beta.2" --notes "$(cat <<'EOF'
The first Windows build: a native Win32 exe for Windows 10 and 11 (x86-64), with the same rules, look, keys and best times as the Linux game.

- Download `swaysweeper-windows-x86_64.exe`; check it against `swaysweeper-windows-x86_64.exe.sha256` (`Get-FileHash` in PowerShell).
- It isn't code-signed: SmartScreen may warn on the first run (More info → Run anyway).
- Minimising pauses the clock, as winmine did. State lives in `%LOCALAPPDATA%\swaysweeper`.
- Not yet tried by hand: display scaling other than 100 %, multiple monitors, Zoom ×2, and the overall feel. Reports welcome.

Linux: unchanged from 0.1.0-beta.1 apart from an internal refactor (`session.py`).
EOF
)"
sleep 10; RUN=$(gh run list --workflow release.yml --limit 1 --json databaseId -q '.[0].databaseId')
gh run watch "$RUN" --exit-status
gh release view v0.1.0-beta.2 --json assets -q '.assets[].name'
cd /tmp/claude-1000 && rm -rf rel && mkdir rel && cd rel && gh release download v0.1.0-beta.2 -R xinye1/swaysweeper && sha256sum -c swaysweeper-windows-x86_64.exe.sha256 && file swaysweeper-windows-x86_64.exe && ls -l
```
Expected: the release run green; assets `swaysweeper-windows-x86_64.exe` and `.sha256`; `sha256sum -c` says `OK`; `file` says `PE32+ executable (GUI) x86-64`; size well under 1 MB.

- [ ] **Step 7: Local install and memory**

```bash
cd ~/repos/swaysweeper && make install && make test 2>&1 | tail -1
```
Expected: `OK`. Update memory `swaysweeper-shipping.md`: replace the HANDOVER section with the outcome (PR number, release URL, the rulings from the ledger, and that hands-on Windows play — DPI, multi-monitor, Zoom, dialogs — is still owed), and refresh its `MEMORY.md` line.
