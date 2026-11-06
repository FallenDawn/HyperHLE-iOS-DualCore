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

# The game controls are hosted in a higher-level UIWindow above SDL. A clear
# background alone is insufficient: UIWindow inherits UIView's opaque default,
# which can composite the overlay as black and hide the SDL game window beneath.
host_window_anchor = '        controlsWindow.backgroundColor = .clear\n'
host_window_patch = (
    '        controlsWindow.backgroundColor = .clear\n'
    '        controlsWindow.isOpaque = false\n'
)
if host_window_patch not in text:
    if text.count(host_window_anchor) != 1:
        raise SystemExit("could not uniquely locate game-controls UIWindow clear background")
    text = text.replace(host_window_anchor, host_window_patch, 1)

view_anchor = '        viewController.loadViewIfNeeded()\n'
view_patch = (
    '        viewController.loadViewIfNeeded()\n'
    '        viewController.view.isOpaque = false\n'
)
if view_patch not in text:
    if text.count(view_anchor) != 1:
        raise SystemExit("could not uniquely locate game-controls root view load")
    text = text.replace(view_anchor, view_patch, 1)

if 'controlsWindow.isOpaque = false' not in text or 'viewController.view.isOpaque = false' not in text:
    raise SystemExit("transparent game-controls window patch did not apply")

# Capture the actual UIKit window stack while the game is on screen. The
# renderer diagnostics already prove that EAGL and SDL have non-black pixels;
# this identifies whether SDL's UIWindow is hidden, covered, transparent, or
# below the controls overlay at the final presentation boundary.
window_anchor = '        gameControlsWindow = controlsWindow\\n'
window_patch = (
    '        gameControlsWindow = controlsWindow\\n'
    '        for (index, candidate) in windowScene.windows.enumerated() {\\n'
    '            let rootName = candidate.rootViewController.map { String(describing: type(of: $0)) } ?? "nil"\\n'
    '            let viewState: String\\n'
    '            if let rootView = candidate.rootViewController?.viewIfLoaded {\\n'
    '                viewState = "rootViewHidden=\\(rootView.isHidden) rootViewAlpha=\\(rootView.alpha) rootViewOpaque=\\(rootView.isOpaque) rootViewBackground=\\(String(describing: rootView.backgroundColor))"\\n'
    '            } else {\\n'
    '                viewState = "rootView=not-loaded"\\n'
    '            }\\n'
    '            NSLog("iOS window diagnostic: index=\\(index) class=\\(type(of: candidate)) hidden=\\(candidate.isHidden) alpha=\\(candidate.alpha) opaque=\\(candidate.isOpaque) level=\\(candidate.windowLevel.rawValue) key=\\(candidate.isKeyWindow) frame=\\(NSStringFromCGRect(candidate.frame)) root=\\(rootName) layerHidden=\\(candidate.layer.isHidden) layerOpacity=\\(candidate.layer.opacity) \\(viewState)")\\n'
    '        }\\n'
)
if window_patch not in text:
    if text.count(window_anchor) != 1:
        raise SystemExit("could not uniquely locate game-controls window registration")
    text = text.replace(window_anchor, window_patch, 1)


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
