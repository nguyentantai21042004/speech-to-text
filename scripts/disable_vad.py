#!/usr/bin/env python3
"""Test disabling VAD by setting bool at offset 320 to 0."""

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

# Read current value at offset 320
current = ctypes.c_uint64.from_address(params_ptr + 320)
print(f"Current value at offset 320: {current.value}")

# Set to 0 (disable VAD)
ctypes.c_uint64.from_address(params_ptr + 320).value = 0
print(f"Set offset 320 to 0")

# Verify
verify = ctypes.c_uint64.from_address(params_ptr + 320)
print(f"Verified value at offset 320: {verify.value}")

print("\nVAD should now be disabled!")
