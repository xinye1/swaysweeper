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
    CHECK(s.level == BEGINNER && s.marks && s.color && !s.sound && s.zoom == 100 && !s.has_pos);
    s.level = CUSTOM;
    s.custom[0] = 30;
    s.custom[1] = 24;
    s.custom[2] = 667;
    s.sound = 1;
    s.zoom = 125;
    s.has_pos = 1;
    s.x = -1200;
    s.y = 40;
    char buf[INI_MAX];
    CHECK(settings_format(&s, buf, sizeof buf) > 0);
    CHECK(settings_parse(buf, &t) == 0);
    CHECK(t.level == CUSTOM && t.custom[0] == 30 && t.custom[1] == 24 && t.custom[2] == 667);
    CHECK(t.marks == 1 && t.color == 1 && t.sound == 1 && t.zoom == 125);
    CHECK(strstr(buf, "\nzoom=1.25\n") != NULL);
    CHECK(t.has_pos && t.x == -1200 && t.y == 40);
    CHECK(settings_format(&s, buf, 8) == 0);
}

static void test_settings_tolerate_bom_and_crlf(void)
{
    Settings s;
    CHECK(settings_parse("\xEF\xBB\xBF" "difficulty=expert\r\nsound=1\r\n\r\nzoom=2\r\n", &s) == 0);
    CHECK(s.level == EXPERT && s.sound == 1 && s.zoom == 200 && s.marks == 1);
}

static void test_settings_tolerate_spaces_around_values(void)
{
    Settings s;
    CHECK(settings_parse("difficulty = expert\nzoom = 2 \n\tsound\t=\t1\t\r\n", &s) == 0);
    CHECK(s.level == EXPERT && s.zoom == 200 && s.sound == 1);
}

static void test_settings_rules(void)
{
    Settings s;
    CHECK(settings_parse("custom=99,99,9999\nfuture=thing\n", &s) == 0);
    CHECK(s.custom[0] == 30 && s.custom[1] == 24 && s.custom[2] == 667);
    CHECK(settings_parse("x=5\n", &s) == 0 && !s.has_pos);
    CHECK(settings_parse("difficulty=hard\n", &s) == -1);
    CHECK(settings_parse("zoom=3.5\n", &s) == -1);
    CHECK(settings_parse("zoom=1.3\n", &s) == -1);
    CHECK(settings_parse("zoom=0\n", &s) == -1);
    CHECK(settings_parse("zoom=125\n", &s) == -1);
    CHECK(settings_parse("marks=yes\n", &s) == -1);
    CHECK(settings_parse("custom=9,9\n", &s) == -1);
    CHECK(settings_parse("sound\n", &s) == -1);
}

/* settings.ini writes a zoom as Linux's settings.json does: 1, 1.25 ... 3. */
static void test_settings_every_zoom_level(void)
{
    static const char *names[N_ZOOMS] = {"1", "1.25", "1.5", "1.75", "2", "2.5", "3"};
    for (int i = 0; i < N_ZOOMS; i++) {
        char text[32], buf[INI_MAX];
        Settings s;
        snprintf(text, sizeof text, "zoom=%s\n", names[i]);
        CHECK(settings_parse(text, &s) == 0 && s.zoom == ZOOMS[i]);
        CHECK(settings_format(&s, buf, sizeof buf) > 0 && strstr(buf, text) != NULL);
        CHECK(zoom_index(ZOOMS[i]) == i);
    }
    CHECK(zoom_index(130) == -1);
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

int main(void)
{
    test_clamp_custom();
    test_layout_of_beginner();
    test_board_rejects_out_of_range();
    test_settings_round_trip();
    test_settings_tolerate_bom_and_crlf();
    test_settings_tolerate_spaces_around_values();
    test_settings_rules();
    test_settings_every_zoom_level();
    test_best_round_trip_and_names();
    test_game_round_trip();
    test_game_rejects();
    test_rng_boards();
    if (!failures)
        printf("ok\n");
    return failures != 0;
}
