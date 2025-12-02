#!/usr/bin/env python3
"""Find and disable all potential VAD flags."""

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

# Read 600 bytes
raw = bytearray((ctypes.c_char * 600).from_address(params_ptr))

# Find all bytes that are 1 (potential bool flags)
print("\nAll bytes with value 1:")
for i in range(len(raw)):
    if raw[i] == 1:
        print(f"  Offset {i}: 1")

# Set all 1s in range 300-400 to 0 (likely VAD area)
print("\nSetting all 1s in range 300-400 to 0:")
for i in range(300, 400):
    if raw[i] == 1:
        print(f"  Setting offset {i} from 1 to 0")
        ctypes.c_uint8.from_address(params_ptr + i).value = 0

# Verify
print("\nVerifying changes:")
raw2 = bytes((ctypes.c_char * 600).from_address(params_ptr))
for i in range(300, 400):
    if raw2[i] == 1:
        print(f"  Offset {i} still has value 1")
    elif raw[i] == 1:
        print(f"  Offset {i} successfully set to 0")

print("\nDone")
