/* SPDX-License-Identifier: GPL-2.0 */
/*
 * Copyright (c) 2025, Ivaylo Ivanov <ivo.ivanov.ivanov1@gmail.com>
 */
#include "asmdefs.h"

#ifdef CONFIG_LINUX_KRNL_HEADER_IMG
#include "linux-kernel-image-header.h"
#endif

.extern _reloc_copy_size
.extern _reloc_start
.extern _start

ENTRY_ALIAS(_head)
#ifdef CONFIG_LINUX_KRNL_HEADER_IMG
	linux_image_header _reloc_entry
#else
	adr	x1, _relocated_uni
	b	 _reloc_entry
#endif

/* Destination of the WHOLE relocatable image, beginning at _head.
 * _start is the entry point AFTER the ARM64 header, not its copy base.
 */
ENTRY_ALIAS(_rel_stack_base)
	.quad _reloc_start

ENTRY_ALIAS(_rel_stack_entry)
	.quad _start

ENTRY_ALIAS(_rel_stack_size)
	.quad _reloc_copy_size

ENTRY_ALIAS( _reloc_entry)
	adr	x7, _head		/* where we were loaded, for main() */
	/* Copy ONLY the initialized raw file. BSS and stack are absent from
	 * the input image and must never be read as source bytes.
	 * BSS is initialized in start.S after relocation.
	 */
	adr	x4, _head
	ldr	x5, _rel_stack_base
	cmp	x4, x5
	beq	_entry
	ldr	x6, _rel_stack_size

	/* Reject source/destination overlap instead of executing through a
	 * self-overwriting copy. This is an emergency stop, NOT proof that
	 * Samsung's source address or the destination DRAM is usable.
	 *
	 * Source: [x4, x4+x6); destination: [x5, x5+x6).
	 * Reject overflow rather than allowing wrapped range comparisons.
	 */
	adds	x8, x4, x6
	b.cs	_dead
	adds	x9, x5, x6
	b.cs	_dead
	cmp	x4, x9
	b.hs	_copy16
	cmp	x5, x8
	b.lo	_dead

	/* Fast 16-byte copies followed by exact byte tail (if any). */
_copy16:
	cmp	x6, #16
	b.lo	_copy_tail
	ldp	x2, x3, [x4], #16
	stp	x2, x3, [x5], #16
	sub	x6, x6, #16
	b	_copy16

_copy_tail:
	cbz	x6, _entry
	ldrb	w2, [x4], #1
	strb	w2, [x5], #1
	sub	x6, x6, #1
	b	_copy_tail
_entry:
	/* Branch to code entry, not the beginning of the Image header. */
	ldr	x5, _rel_stack_entry
	br	x5

_dead: /* we should never get here */
	b	_dead

ENTRY_ALIAS(_relocated_uni)
