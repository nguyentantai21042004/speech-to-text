#!/usr/bin/env python3
"""Find VAD model path offset in whisper params structure."""

import ctypes
import os
import struct
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from core.config import get_settings
    settings = get_settings()
    artifacts_dir = settings.whisper_artifacts_dir
    model_size = settings.whisper_model_size
except ImportError:
    artifacts_dir = os.getenv("WHISPER_ARTIFACTS_DIR", "models")
    model_size = os.getenv("WHISPER_MODEL_SIZE", "base")

lib_dir = f"{artifacts_dir}/whisper_{model_size}_xeon"
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
