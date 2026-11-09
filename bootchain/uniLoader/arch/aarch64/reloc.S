/* SPDX-License-Identifier: GPL-2.0 */
/*
 * Copyright (c) 2025, Ivaylo Ivanov <ivo.ivanov.ivanov1@gmail.com>
 */
#include "asmdefs.h"

#ifdef CONFIG_LINUX_KRNL_HEADER_IMG
#include "linux-kernel-image-header.h"
#endif

.extern _reloc_size
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
	.quad _reloc_size

ENTRY_ALIAS( _reloc_entry)
	adr	x7, _head		/* where we were loaded, for main() */
	/* Copy exactly [_reloc_start, _reloc_end): source starts at
	 * _head, including the header/preamble. The old code copied from
	 * _start with the larger _reloc_size and overran the source.
	 */
	adr	x4, _head
	ldr	x5, _rel_stack_base
	cmp	x4, x5
	beq	_entry
	ldr	x6,  _rel_stack_size

_copy:
	ldp	x2, x3, [x4], #16
	stp	x2, x3, [x5], #16
	subs	x6, x6, #16
	b.ne	_copy
_entry:
	/* Branch to code entry, not the beginning of the Image header. */
	ldr	x5, _rel_stack_entry
	br	x5

_dead: /* we should never get here */
	b	_dead

ENTRY_ALIAS(_relocated_uni)
