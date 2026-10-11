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

int main(int argc, char **argv)
{
#ifdef _WIN32
    _setmode(_fileno(stdout), _O_BINARY);
#endif
    if (argc != 2) {
        fprintf(stderr, "usage: replay <output-dir>\n");
        return 2;
    }
    outdir = argv[1];
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
            else if (strcmp(cmd, "render") == 0)
                cmd_render(arg());
            else if (strcmp(cmd, "wav") == 0)
                cmd_wav();
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
