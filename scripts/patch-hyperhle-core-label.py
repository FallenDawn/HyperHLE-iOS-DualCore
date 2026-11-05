#!/usr/bin/env python3
"""Label the secondary core as official touchHLE v0.3.0 in the iOS host."""
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit("usage: patch-hyperhle-core-label.py PATH_TO_EmulatorCore.swift")

path = Path(sys.argv[1])
source = path.read_text()

def replace_one(old: str, new: str) -> None:
    global source
    count = source.count(old)
    if count == 1:
        source = source.replace(old, new)
    elif count == 0 and new in source:
        return  # Already patched; keep the script idempotent.
    else:
        raise SystemExit(f"expected exactly one occurrence of {old!r} or its patched form; found {count}")

replace_one('case .touchHLE: return "touchHLE"', 'case .touchHLE: return "touchHLE v0.3.0"')
replace_one('case .touchHLE: return "0.2.3"', 'case .touchHLE: return "v0.3.0"')
replace_one('case .touchHLE: return "touchHLE_default_options.touchhle.txt"', 'case .touchHLE: return "touchHLE_default_options.txt"')

if 'case .touchHLE: return "0.2.3"' in source:
    raise SystemExit("legacy touchHLE 0.2.3 label remains")
path.write_text(source)
print("patched: the secondary core is labelled touchHLE v0.3.0")
