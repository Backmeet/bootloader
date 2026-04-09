#pragma once
#include "globals.h"

void print(const char* msg) {
    ST->ConOut->OutputString(ST->ConOut, (CHAR16*)msg);
}