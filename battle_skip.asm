; HaruDX opening X skip: 65C816 instruction source (Asar-style notation).
; Exact byte generation / hash gate / checksum / image protection is provided
; by apply_x_skip.py, the tested build entry. No external assembler was run
; for this source handoff. Do not apply these fixed addresses to another ROM.
;
; ROM: 4 MiB unheadered HiROM; file = CPU & $3FFFFF for these ROM addresses.
; Entry is a tail jump from the native command handler, NOT a JSL/RTL wrapper.

hirom

org $839204                 ; file $039204: replace C2 30 A5 AC
    jml SkipOpening        ; 5C AA 78 FB

org $FB78AA                 ; file $3B78AA, exactly 58 owned bytes
SkipOpening:
    rep #$30               ; A/X/Y16, same initial setup as displaced code
    lda.b $92
    cmp #$3DA7             ; script pointer low16
    bne Original
    lda.b $93
    cmp #$CB3D             ; overlapping read checks script pointer bank
    bne Original

    lda.w $03EC            ; game-held pad bits, DBR=$83 low WRAM mirror
    ora.w $03F0            ; game new-press bits
    bit #$0040             ; SNES pad X in this game's shadow registers
    bne SkipMovie

    lda.b $AB              ; native command phase byte (16-bit read)
    and #$00FF             ; discard adjacent $AC operand byte
    cmp #$001E             ; 30 frame waits
    bcs Original
    sep #$20               ; A8 for the byte-sized phase increment
    inc.b $AB
    jml [$F5FB]            ; bank00 indirect -> $80F64E -> $80F546 frame wait

SkipMovie:                 ; CPU $FB78D6
    lda #$3DC0             ; native common post-movie script; bank stays $CB
    sta.b $92
    jml [$F5F8]            ; -> $80F643: clear $AA/$AB, resume interpreter

Original:                  ; CPU $FB78DE
    lda.b $AC              ; replay displaced operand load (REP already ran)
    jml $839208            ; continue original native condition handler

; End CPU $FB78E4 / file $3B78E4 (exclusive).
; HiROM checksum/complement at file $00FFDC..$00FFDF must be recomputed.
