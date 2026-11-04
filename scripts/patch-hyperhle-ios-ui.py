#!/usr/bin/env python3
"""Patch HyperHLE's iOS 26-only glass button style for older installed iOS SDKs."""
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit("usage: patch-hyperhle-ios-ui.py PATH_TO_NativeHost.swift")

path = Path(sys.argv[1])
text = path.read_text()

glass_block = """if #available(iOS 26.0, *) {
            configuration = .glass()
        } else {
            configuration = .gray()
        }"""
replacement = """configuration = .gray()"""

count = text.count(glass_block)
if count == 0 and ".glass()" not in text:
    print("already patched: no iOS 26-only glass configuration remains")
elif count == 2:
    path.write_text(text.replace(glass_block, replacement))
    print("patched: replaced both iOS 26-only glass button styles with SDK-compatible gray styles")
else:
    raise SystemExit(
        f"expected exactly two known iOS 26 glass-style blocks in {path}; "
        f"found {count} matching blocks and {text.count('.glass()')} .glass() calls"
    )
