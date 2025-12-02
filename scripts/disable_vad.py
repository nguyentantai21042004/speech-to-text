#!/usr/bin/env python3
"""Test disabling VAD by setting bool at offset 320 to 0."""

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
