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

/* `show` as a shortcut's "Run:" setting passes it; 0 for the default. */
static HANDLE launch_as(DWORD *pid, WORD show)
{
    STARTUPINFOW si;
    PROCESS_INFORMATION pi;
    memset(&si, 0, sizeof si);
    si.cb = sizeof si;
    if (show) {
        si.dwFlags = STARTF_USESHOWWINDOW;
        si.wShowWindow = show;
    }
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

static HANDLE launch(DWORD *pid)
{
    return launch_as(pid, 0);
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
    check(at(&s, 83, 22) == 0xFFFF00, "the smiley is yellow");
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

    /* A shortcut set to "Run: Maximized" still gets the fixed-size window, and a
     * minimise and restore brings it back unmaximised (else the clock froze). */
    app = launch_as(&pid, SW_SHOWMAXIMIZED);
    w = app ? wait_window(pid) : NULL;
    check(w != NULL, "launches with Run: Maximized");
    if (w) {
        GetClientRect(w, &r);
        check(!IsZoomed(w) && r.right == 168 * scale && r.bottom == 211 * scale,
              "Run: Maximized still shows the Beginner area");
        PostMessageW(w, WM_SYSCOMMAND, SC_MINIMIZE, 0);
        Sleep(500);
        ShowWindow(w, SW_RESTORE);
        Sleep(500);
        GetClientRect(w, &r);
        check(!IsIconic(w) && !IsZoomed(w) && r.right == 168 * scale,
              "a restore after Run: Maximized comes back unmaximised");
        close_app(w, app);
    }

    printf("%d failure(s)\n", failures);
    return failures != 0;
}
