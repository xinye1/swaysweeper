/* See core.h. Each section names the Python module it ports; keep them in
 * step, and tests/test_win_parity.py will say when they aren't. */
#include "core.h"
#include "sprites.h"
#include <math.h>
#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
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
