global efi_main
extern entry

section .bss
stack_bottom:
    resb 16384
stack_top:

section .text

efi_main:
    cli

    mov rsp, stack_top

    ; rdi = ImageHandle
    ; rsi = SystemTable
    call entry

hang:
    hlt
    jmp hang