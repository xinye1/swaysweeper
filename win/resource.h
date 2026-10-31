/* Resource ids, shared by swaysweeper.rc and main.c. */
#ifndef SWAYSWEEPER_RESOURCE_H
#define SWAYSWEEPER_RESOURCE_H

#define IDI_APP 1               /* lowest id: Explorer's icon for the exe */
#define IDM_MENU 100
#define IDA_ACCEL 101

#define IDD_CUSTOM 200
#define IDD_NAME 201
#define IDD_BEST 202
#define IDD_KEYS 203
#define IDD_ABOUT 204

#define IDC_HEIGHT 300
#define IDC_WIDTH 301
#define IDC_MINES 302
#define IDC_PROMPT 303
#define IDC_NAME 304
#define IDC_SECS0 310           /* IDC_SECS0 + Level */
#define IDC_SECS1 311
#define IDC_SECS2 312
#define IDC_NAME0 320           /* IDC_NAME0 + Level */
#define IDC_NAME1 321
#define IDC_NAME2 322
#define IDC_RESET 330
#define IDC_KEYS_TEXT 331
#define IDC_ABOUT_TEXT 332

#define ID_NEW 1000
#define ID_BEGINNER 1001        /* ID_BEGINNER + Level, through ID_CUSTOM */
#define ID_INTERMEDIATE 1002
#define ID_EXPERT 1003
#define ID_CUSTOM 1004
#define ID_MARKS 1005
#define ID_COLOR 1006
#define ID_SOUND 1007
#define ID_BEST 1009
#define ID_EXIT 1010
#define ID_KEYS 1011
#define ID_ABOUT 1012
#define ID_ZOOM_IN 1013
#define ID_ZOOM_OUT 1014
#define ID_ZOOM_100 1020        /* ID_ZOOM_100 + zoom_index, through 1026 */

#endif
