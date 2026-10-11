# make -C win            the Windows exe (MinGW-w64; MSYS2 UCRT64 on CI)
# make -C win test       the portable core's own tests, with any C compiler
# make -C win zigcheck   compile-check every Windows source on Linux with zig

CFLAGS  ?= -std=c11 -O2 -Wall -Wextra -pedantic -Werror
WINDEFS := -DUNICODE -D_UNICODE -D_WIN32_WINNT=0x0A00 -DWINVER=0x0A00
WINLIBS := -lwinmm -lcomctl32 -lshell32 -lole32 -luuid
WINDRES ?= windres
ZIG     ?= uvx --from ziglang python -m ziglang
ZIGCC   := $(ZIG) cc -target x86_64-windows-gnu

.PHONY: all test zigcheck clean

all: swaysweeper.exe

test: replay test_core
	./test_core

replay: replay.c core.c core.h sprites.h
	$(CC) $(CFLAGS) -o $@ replay.c core.c -lm

test_core: test_core.c core.c core.h sprites.h
	$(CC) $(CFLAGS) -o $@ test_core.c core.c -lm

clean:
	rm -f replay replay.exe test_core test_core.exe swaysweeper.exe swaysweeper.res.o \
	      wintest.exe zig-*.exe zig-*.pdb
