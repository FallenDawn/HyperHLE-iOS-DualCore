#!/usr/bin/env python3
"""Make HyperHLE's iOS host UI compile with the Xcode 16 / iOS 18 SDK."""
from pathlib import Path
import re
import sys

if len(sys.argv) != 2:
    raise SystemExit("usage: patch-hyperhle-ios-ui.py PATH_TO_NativeHost.swift")

path = Path(sys.argv[1])
text = path.read_text()

# UIButton.Configuration.glass() is unavailable in the iOS 18 SDK.
button_pattern = re.compile(
    r"""if #available\(iOS 26\.0, \*\) \{
(?P<indent>\s*)configuration = \.glass\(\)
(?P=indent)\} else \{
(?P=indent)configuration = \.gray\(\)
(?P=indent)\}"""
)
text, button_count = button_pattern.subn(
    lambda m: f"{m.group('indent')}configuration = .gray()", text
)
if button_count not in (0, 2):
    raise SystemExit(f"expected 2 iOS 26 glass button blocks or 0 if already patched; found {button_count}")
if button_count == 0 and ".glass()" in text:
    raise SystemExit("unrecognized UIButton.Configuration.glass() block; refusing an unsafe partial patch")

# SwiftUI glassEffect is also an iOS 26 API. Keep the existing material-based
# fallback unconditionally; it preserves the intended appearance on iOS 15+.
extension_start = "private extension View {"
extension_end = "private struct LibraryBackground: View {"
if text.count(extension_start) != 1 or text.count(extension_end) != 1:
    raise SystemExit("could not uniquely locate the SwiftUI View style extension")
start = text.index(extension_start)
end = text.index(extension_end, start)
old_extension = text[start:end]
if "glassEffect(" in old_extension:
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
    if old_extension.count("glassEffect(") != 2:
        raise SystemExit(
            f"expected exactly 2 SwiftUI glassEffect calls in View extension; found {old_extension.count('glassEffect(')}"
        )
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
