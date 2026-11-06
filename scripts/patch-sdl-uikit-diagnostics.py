#!/usr/bin/env python3
"""Add runtime diagnostics and an aggressive UIWindow-order test to SDL's iOS host."""
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit("usage: patch-sdl-uikit-diagnostics.py PATH_TO_PATCHED_SDL_SOURCE")

root = Path(sys.argv[1])
window_path = root / "src/video/uikit/SDL_uikitwindow.m"
gl_path = root / "src/video/uikit/SDL_uikitopenglview.m"
window_source = window_path.read_text()
gl_source = gl_path.read_text()

# The pinned HyperHLE SDL host patch already adds this window-level/show pair.
# Anchor to that real upstream-patched source rather than a diagnostic block
# that is not present in the freshly patched SDL checkout.
window_anchor = """        data.uiwindow.windowLevel = UIWindowLevelNormal + 2.0;
        [data.uiwindow makeKeyAndVisible];"""
window_patch = """        // TEMPORARY AGGRESSIVE BLACK-SCREEN TEST:
        // Raise SDL above normal/alert-level app overlays and hide the
        // separate SwiftUI controls window for this diagnostic build.
        data.uiwindow.windowLevel = UIWindowLevelAlert + 1.0;
        [data.uiwindow makeKeyAndVisible];

        if (@available(iOS 13.0, tvOS 13.0, *)) {
            UIWindowScene *scene = data.uiwindow.windowScene;
            if (scene) {
                for (UIWindow *candidate in scene.windows) {
                    if (candidate != data.uiwindow &&
                        ([candidate.accessibilityIdentifier isEqualToString:@"touchHLE.gameControls"] ||
                         [NSStringFromClass([candidate class]) containsString:@"GameControls"])) {
                        NSLog(@"iOS BLACKSCREEN TEST: hiding controls window=%@ level=%.1f",
                              candidate, candidate.windowLevel);
                        candidate.hidden = YES;
                        candidate.alpha = 0.0;
                    }
                }

                NSLog(@"iOS BLACKSCREEN TEST: SDLWindow=%p scene=%p activation=%ld level=%.1f key=%d frame=%@",
                      data.uiwindow, scene, (long)scene.activationState,
                      data.uiwindow.windowLevel, data.uiwindow.isKeyWindow,
                      NSStringFromCGRect(data.uiwindow.frame));
                NSUInteger index = 0;
                for (UIWindow *candidate in scene.windows) {
                    UIView *rootView = candidate.rootViewController.viewIfLoaded;
                    NSLog(@"iOS BLACKSCREEN TEST stack: index=%lu class=%@ hidden=%d alpha=%.3f level=%.1f key=%d root=%@",
                          (unsigned long)index++, NSStringFromClass([candidate class]),
                          candidate.hidden, candidate.alpha, candidate.windowLevel,
                          candidate.isKeyWindow,
                          candidate.rootViewController ? NSStringFromClass([candidate.rootViewController class]) : @"nil");
                    (void)rootView;
                }
            }
        }
        [data.uiwindow makeKeyAndVisible];"""

if "iOS BLACKSCREEN TEST: SDLWindow=" not in window_source:
    count = window_source.count(window_anchor)
    if count != 1:
        raise SystemExit(f"SDL_uikitwindow.m: expected one upstream show-window anchor, found {count}")
    window_source = window_source.replace(window_anchor, window_patch, 1)
    window_path.write_text(window_source)
    print("patched: aggressive SDL UIWindow ordering and controls-window suppression")
else:
    print("already patched: aggressive SDL UIWindow test")

gl_anchor = "    [context presentRenderbuffer:GL_RENDERBUFFER];"
gl_patch = """    BOOL didPresent = [context presentRenderbuffer:GL_RENDERBUFFER];
    static NSUInteger touchHLEPresentDiagnosticCount = 0;
    ++touchHLEPresentDiagnosticCount;
    if (touchHLEPresentDiagnosticCount <= 8 || touchHLEPresentDiagnosticCount % 120 == 0) {
        NSLog(@"iOS SDL present diagnostic: frame=%lu success=%d context=%p view=%p layer=%p renderbuffer=%u bounds=%@",
              (unsigned long)touchHLEPresentDiagnosticCount, didPresent, context,
              self, self.layer, (unsigned int)viewRenderbuffer, NSStringFromCGRect(self.bounds));
    }"""
if "iOS SDL present diagnostic:" not in gl_source:
    count = gl_source.count(gl_anchor)
    if count != 1:
        raise SystemExit(f"SDL_uikitopenglview.m: expected one presentRenderbuffer anchor, found {count}")
    gl_source = gl_source.replace(gl_anchor, gl_patch, 1)
    gl_path.write_text(gl_source)
    print("patched: EAGL presentRenderbuffer return-value diagnostics")
else:
    print("already patched: EAGL present diagnostics")
