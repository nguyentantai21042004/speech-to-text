#!/usr/bin/env python3
"""Test setting VAD model path at different offsets."""

import ctypes
import struct
import os

lib_dir = "/app/whisper_base_xeon"
vad_model_path = "/app/whisper_base_xeon/silero-vad.onnx"

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

# Read current value at offset 104
current_ptr = ctypes.c_void_p.from_address(params_ptr + 104)
print(
    f"Current value at offset 104: {hex(current_ptr.value) if current_ptr.value else 'NULL'}"
)

# Try to read as string
if current_ptr.value:
    try:
        s = ctypes.string_at(current_ptr.value, 100)
        print(f"String at offset 104: {s[:50]}")
    except:
        print("Could not read as string")

# Create a persistent string buffer for the path
path_buffer = ctypes.create_string_buffer(vad_model_path.encode("utf-8"))
path_ptr = ctypes.cast(path_buffer, ctypes.c_void_p)
print(f"New path pointer: {hex(path_ptr.value)}")

# Set the new path at offset 104
ctypes.c_void_p.from_address(params_ptr + 104).value = path_ptr.value
print(f"Set vad_model_path at offset 104")

# Verify
verify_ptr = ctypes.c_void_p.from_address(params_ptr + 104)
print(
    f"Verified value at offset 104: {hex(verify_ptr.value) if verify_ptr.value else 'NULL'}"
)

# Try to read back
if verify_ptr.value:
    try:
        s = ctypes.string_at(verify_ptr.value, 100)
        print(f"Verified string: {s}")
    except Exception as e:
        print(f"Could not read back: {e}")

print("\nDone - path_buffer must stay in scope!")
