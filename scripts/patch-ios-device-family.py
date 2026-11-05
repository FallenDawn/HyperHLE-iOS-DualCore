#!/usr/bin/env python3
"""Ensure the iOS host advertises both iPhone and native iPad support."""
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit("usage: patch-ios-device-family.py PATH_TO_Info.plist")

path = Path(sys.argv[1])
source = path.read_text()
key = "<key>UIDeviceFamily</key>"
if key in source:
    if "<integer>2</integer>" not in source[source.index(key):]:
        raise SystemExit("UIDeviceFamily exists but does not include iPad (2)")
    print("already patched: UIDeviceFamily includes iPad")
else:
    anchor = "<key>LSRequiresIPhoneOS</key>\n\t<true/>"
    if source.count(anchor) != 1:
        raise SystemExit("could not uniquely locate LSRequiresIPhoneOS in Info.plist")
    replacement = anchor + "\n\t<key>UIDeviceFamily</key>\n\t<array>\n\t\t<integer>1</integer>\n\t\t<integer>2</integer>\n\t</array>"
    path.write_text(source.replace(anchor, replacement, 1))
    print("patched: UIDeviceFamily=[iPhone, iPad]")
