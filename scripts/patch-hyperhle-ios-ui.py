#!/usr/bin/env python3
"""Patch iOS 26-only glass UI APIs for the Xcode 16 / iOS 18 SDK."""
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit("usage: patch-hyperhle-ios-ui.py PATH_TO_NativeHost.swift")

path = Path(sys.argv[1])
text = path.read_text()

# Keep the availability branches but replace the unavailable API call itself.
# This is intentionally whitespace-independent and safe to run repeatedly.
button_count = text.count("configuration = .glass()")
if button_count not in (0, 2):
    raise SystemExit(
        f"expected exactly 2 UIButton.Configuration.glass() calls or 0 if already patched; found {button_count}"
    )
text = text.replace("configuration = .glass()", "configuration = .gray()")

# SwiftUI glassEffect is unavailable before iOS 26. Preserve the existing
# iOS 15+ material fallback unconditionally.
extension_start = "private extension View {"
extension_end = "private struct LibraryBackground: View {"
if text.count(extension_start) != 1 or text.count(extension_end) != 1:
    raise SystemExit("could not uniquely locate the SwiftUI View style extension")
start = text.index(extension_start)
end = text.index(extension_end, start)
old_extension = text[start:end]

if "glassEffect(" in old_extension:
    if old_extension.count("glassEffect(") != 2:
        raise SystemExit(
            f"expected exactly 2 SwiftUI glassEffect calls in View extension; found {old_extension.count('glassEffect(')}"
        )
    replacement = """private extension View {
    func touchHLEImportButtonStyle() -> some View {
        background(.ultraThinMaterial, in: Capsule())
            .overlay {
                Capsule().stroke(.blue.opacity(0.2), lineWidth: 1)
            }
    }

    func touchHLELaunchOverlayStyle() -> some View {
        background(
            .ultraThinMaterial,
            in: RoundedRectangle(cornerRadius: 24, style: .continuous)
        )
    }
}

"""
    text = text[:start] + replacement + text[end:]
elif "glassEffect(" in text:
    raise SystemExit("found glassEffect outside the expected View extension; refusing an unsafe patch")

if ".glass()" in text or "glassEffect(" in text:
    raise SystemExit("iOS 26 glass APIs remain after patch")

path.write_text(text)
print(
    "patched: UIKit glass buttons use .gray(); SwiftUI glass styles use "
    "the existing iOS 15+ material fallbacks"
)
