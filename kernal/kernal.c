#include "globals.h"
#include "io.h"

void kmain(EFI_HANDLE image, EFI_SYSTEM_TABLE* system_table) {    
    Image = image;
    ST = system_table;
    BS = system_table->BootServices;
    
    while (1) {
        print("Yes\n");
    }
    return 0;
}