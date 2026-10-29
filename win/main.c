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
        if (wp == SIZE_MAXIMIZED) {
            /* A fixed-size window, as winmine's: never maximised. A shortcut's
             * "Run: Maximized" or a restore from it lands here; put it back. */
            ShowWindowAsync(hwnd, SW_RESTORE);
            return 0;
        }
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
    ShowWindow(g_wnd, show == SW_SHOWMAXIMIZED ? SW_SHOWNORMAL : show);
    sync_timer();

    MSG msg;
    while (GetMessageW(&msg, NULL, 0, 0) > 0)
        if (!TranslateAcceleratorW(g_wnd, accel, &msg)) {
            TranslateMessage(&msg);
            DispatchMessageW(&msg);
        }
    return (int)msg.wParam;
}
