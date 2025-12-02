#!/usr/bin/env python3
"""Find VAD model path offset in whisper params structure."""

import ctypes
import struct

lib_dir = "/app/whisper_base_xeon"
ctypes.CDLL(f"{lib_dir}/libggml-base.so.0", mode=ctypes.RTLD_GLOBAL)
ctypes.CDLL(f"{lib_dir}/libggml-cpu.so.0", mode=ctypes.RTLD_GLOBAL)
ctypes.CDLL(f"{lib_dir}/libggml.so.0", mode=ctypes.RTLD_GLOBAL)
lib = ctypes.CDLL(f"{lib_dir}/libwhisper.so")

lib.whisper_full_default_params_by_ref.argtypes = [ctypes.c_int]
lib.whisper_full_default_params_by_ref.restype = ctypes.c_void_p

params_ptr = lib.whisper_full_default_params_by_ref(0)
print(f"Params pointer: {hex(params_ptr)}")

# Read params structure as bytes
params_bytes = (ctypes.c_char * 500).from_address(params_ptr)
raw = bytes(params_bytes)

# Print first 100 bytes as integers
print("\nFirst 100 bytes as int32:")
for i in range(0, 100, 4):
    val = struct.unpack_from("<i", raw, i)[0]
    if val != 0:
        print(f"  Offset {i}: {val}")

# Look for pointer-like values (8 bytes on 64-bit)
print("\nPotential pointers (8-byte values):")
for i in range(0, 300, 8):
    val = struct.unpack_from("<Q", raw, i)[0]
    if val > 0x1000 and val < 0x7FFFFFFFFFFF:
        print(f"  Offset {i}: {hex(val)}")

print("\nDone")
