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
