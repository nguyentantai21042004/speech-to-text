#!/usr/bin/env python3
"""Scan whisper params structure to find VAD-related fields."""

import ctypes
import struct

lib_dir = "/app/whisper_base_xeon"

# Load libraries
ctypes.CDLL(f"{lib_dir}/libggml-base.so.0", mode=ctypes.RTLD_GLOBAL)
ctypes.CDLL(f"{lib_dir}/libggml-cpu.so.0", mode=ctypes.RTLD_GLOBAL)
ctypes.CDLL(f"{lib_dir}/libggml.so.0", mode=ctypes.RTLD_GLOBAL)
lib = ctypes.CDLL(f"{lib_dir}/libwhisper.so")

# Get params
lib.whisper_full_default_params_by_ref.argtypes = [ctypes.c_int]
lib.whisper_full_default_params_by_ref.restype = ctypes.c_void_p

params_ptr = lib.whisper_full_default_params_by_ref(0)
print(f"Params pointer: {hex(params_ptr)}")

# Read 400 bytes
raw = bytes((ctypes.c_char * 400).from_address(params_ptr))

# Print all non-zero values
print("\nAll non-zero int32 values:")
for i in range(0, 200, 4):
    val = struct.unpack_from("<i", raw, i)[0]
    print(f"  Offset {i:3d}: {val:12d} (0x{val & 0xffffffff:08x})")

print("\nAll 8-byte values (potential pointers or bools):")
for i in range(0, 200, 8):
    val = struct.unpack_from("<Q", raw, i)[0]
    # Check if it looks like a bool (0 or 1)
    if val == 0:
        print(f"  Offset {i:3d}: 0 (NULL/false)")
    elif val == 1:
        print(f"  Offset {i:3d}: 1 (true)")
    elif val > 0x1000:
        print(f"  Offset {i:3d}: {hex(val)} (pointer?)")
    else:
        print(f"  Offset {i:3d}: {val}")

# Based on whisper.cpp source, typical structure:
# - strategy (int)
# - n_threads (int)
# - n_max_text_ctx (int)
# - offset_ms (int)
# - duration_ms (int)
# - translate (bool)
# - no_context (bool)
# - no_timestamps (bool)
# - single_segment (bool)
# - print_special (bool)
# - print_progress (bool)
# - print_realtime (bool)
# - print_timestamps (bool)
# - token_timestamps (bool)
# - thold_pt (float)
# - thold_ptsum (float)
# - max_len (int)
# - split_on_word (bool)
# - max_tokens (int)
# - debug_mode (bool)
# - audio_ctx (int)
# - tdrz_enable (bool)
# - suppress_regex (char*)
# - initial_prompt (char*)
# - prompt_tokens (int32_t*)
# - prompt_n_tokens (int)
# - language (char*)
# - detect_language (bool)
# - suppress_blank (bool)
# - suppress_nst (bool)
# - temperature (float)
# - max_initial_ts (float)
# - length_penalty (float)
# ... more fields ...
# - vad (bool)
# - vad_model_path (char*)

print("\nLooking for bool patterns (0 or 1) after offset 20:")
for i in range(20, 120):
    val = raw[i]
    if val in (0, 1):
        # Check if next few bytes are also 0 or 1 (bool packing)
        if i + 3 < len(raw):
            next_vals = [raw[i + j] for j in range(4)]
            if all(v in (0, 1) for v in next_vals):
                print(f"  Offset {i}: bool sequence {next_vals}")
