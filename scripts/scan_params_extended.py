#!/usr/bin/env python3
"""Scan whisper params structure to find VAD-related fields - extended range."""

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

# Read 600 bytes (larger structure)
raw = bytes((ctypes.c_char * 600).from_address(params_ptr))

# Look for bool (0 or 1) followed by pointer (8 bytes)
# VAD structure is likely: bool vad; char* vad_model_path;
print("\nLooking for bool + pointer pattern (VAD settings):")
for i in range(200, 500, 8):
    # Check if this could be a bool (0 or 1 in first byte, rest zeros)
    val = struct.unpack_from("<Q", raw, i)[0]
    if val == 0 or val == 1:
        # Check next 8 bytes for pointer
        if i + 8 < len(raw):
            next_val = struct.unpack_from("<Q", raw, i + 8)[0]
            if next_val == 0:
                print(f"  Offset {i}: bool={val}, next=NULL (potential VAD disabled)")
            elif next_val > 0x1000 and next_val < 0x7FFFFFFFFFFF:
                print(
                    f"  Offset {i}: bool={val}, next={hex(next_val)} (potential VAD with path)"
                )

# Also look for any non-zero values in extended range
print("\nNon-zero 8-byte values in range 200-500:")
for i in range(200, 500, 8):
    val = struct.unpack_from("<Q", raw, i)[0]
    if val != 0:
        print(f"  Offset {i}: {val} ({hex(val)})")

# Check for callback pointers (function pointers are usually in high memory)
print("\nPotential callback/function pointers:")
for i in range(0, 500, 8):
    val = struct.unpack_from("<Q", raw, i)[0]
    if val > 0x555555000000 and val < 0x7FFFFFFFFFFF:
        print(f"  Offset {i}: {hex(val)}")
