/* See core.h. Each section names the Python module it ports; keep them in
 * step, and tests/test_win_parity.py will say when they aren't. */
#include "core.h"
#include "sprites.h"
#include <stdio.h>

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
