# make -C win            the Windows exe (MinGW-w64; MSYS2 UCRT64 on CI)
# make -C win test       the portable core's own tests, with any C compiler
# make -C win zigcheck   compile-check every Windows source on Linux with zig

CFLAGS  ?= -std=c11 -O2 -Wall -Wextra -pedantic -Werror
WINDEFS := -DUNICODE -D_UNICODE -D_WIN32_WINNT=0x0A00 -DWINVER=0x0A00
WINLIBS := -lwinmm -lcomctl32 -lshell32 -lole32 -luuid
WINDRES ?= windres
ZIG     ?= uvx --from ziglang python -m ziglang
ZIGCC   := $(ZIG) cc -target x86_64-windows-gnu -U_WIN32_WINNT -UWINVER

.PHONY: all test zigcheck clean

all: swaysweeper.exe

test: replay test_core
	./test_core

replay: replay.c core.c core.h sprites.h
	$(CC) $(CFLAGS) -o $@ replay.c core.c -lm

test_core: test_core.c core.c core.h sprites.h
	$(CC) $(CFLAGS) -o $@ test_core.c core.c -lm

swaysweeper.exe: main.c core.c core.h sprites.h resource.h swaysweeper.res.o
	$(CC) $(CFLAGS) $(WINDEFS) -municode -mwindows -o $@ main.c core.c swaysweeper.res.o \
	      $(WINLIBS) $(LDFLAGS)

swaysweeper.res.o: swaysweeper.rc swaysweeper.manifest swaysweeper.ico core.h resource.h
	$(WINDRES) -O coff -o $@ swaysweeper.rc

wintest.exe: wintest.c resource.h
	$(CC) $(CFLAGS) $(WINDEFS) -municode -o $@ wintest.c -lgdi32 -luser32 $(LDFLAGS)

# Compile-only check on Linux: zig ships the mingw-w64 headers and an .rc compiler.
zigcheck:
	$(ZIGCC) $(CFLAGS) $(WINDEFS) -municode -o zig-swaysweeper.exe \
	    main.c core.c swaysweeper.rc $(WINLIBS) -lgdi32 -luser32
	$(ZIGCC) $(CFLAGS) -o zig-replay.exe replay.c core.c
	$(ZIGCC) $(CFLAGS) $(WINDEFS) -municode -o zig-wintest.exe wintest.c -lgdi32 -luser32
	rm -f zig-*.exe zig-*.pdb
	@echo zigcheck: ok

clean:
	rm -f replay replay.exe test_core test_core.exe swaysweeper.exe swaysweeper.res.o \
	      wintest.exe zig-*.exe zig-*.pdb
