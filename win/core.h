/* swaysweeper's portable core: rules, session, renderer, sounds and state
 * files, ported from swaysweeper/{board,game,gestures,geometry,session,
 * render,sound,store}.py. No windows.h, so it builds and is tested on Linux
 * too; tests/test_win_parity.py holds it to the Python output step by step.
 * swaysweeper.rc includes this for the version, hence the RC_INVOKED guard.
 */
#ifndef SWAYSWEEPER_CORE_H
#define SWAYSWEEPER_CORE_H

#define SWAYSWEEPER_VERSION "0.1.0-beta.2"
#define SWAYSWEEPER_VERSION_NUM 0,1,0,2

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
    int marks, color, sound, zoom;  /* zoom in percent, one of ZOOMS */
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

/* --- render.py -------------------------------------------------------------- */

/* The game area at x1 as 0x00RRGGBB, `stride` pixels per row, in Color on
 * (Windows 95) or Color off (monochrome) per s->settings->color. */
void render_session(const Session *s, uint32_t *pixels, int stride);
const char *core_keys_text(void);   /* the Keys dialog text, from session.KEYS */

/* --- sound.py: the three sounds as WAV files, byte for byte ----------------- */

enum { WAV_MAX = 20000, INI_MAX = 16384 };
size_t wav_build(SoundName name, unsigned char *out, size_t cap);

/* --- store.py's rules, in Windows' INI files (spec §3.5) --------------------- */
/* Parsers start from the defaults and return 0, or -1 for a file to move
 * aside. Formatters return the length written, or 0 if `cap` is too small. */

/* Game > Zoom's levels in percent; swaysweeper/geometry.py's ZOOMS as factors. */
enum { N_ZOOMS = 7 };
extern const int ZOOMS[N_ZOOMS];
int zoom_index(int percent);                    /* -1 if not a level */

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

#endif /* RC_INVOKED */
#endif
