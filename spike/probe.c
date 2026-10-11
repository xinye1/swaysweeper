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
