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
