#!/usr/bin/env python3
"""Keep the upstream HyperHLE build helper from clearing Core B's patched Dynarmic path."""
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit("usage: patch-hyperhle-build-rust.py PATH_TO_build-rust.sh")

path = Path(sys.argv[1])
text = path.read_text()
old = """else
    unset TOUCHHLE_DYNARMIC_DIR
fi"""
new = """else
    if [ -z "${TOUCHHLE_DYNARMIC_DIR:-}" ]; then
        echo "External core requires TOUCHHLE_DYNARMIC_DIR to point at its iOS JIT-patched Dynarmic source." >&2
        exit 1
    fi
fi"""
if new in text:
    print("already patched: preserve external core Dynarmic path")
elif text.count(old) == 1:
    path.write_text(text.replace(old, new, 1))
    print("patched: preserve external core Dynarmic path")
else:
    raise SystemExit(f"expected one external-core Dynarmic branch in {path}, found {text.count(old)}")
