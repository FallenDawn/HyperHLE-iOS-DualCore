#!/usr/bin/env python3
"""Add UIKit-only presentation probe and EAGL present diagnostics to SDL iOS host."""
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit("usage: patch-sdl-uikit-diagnostics.py PATH_TO_PATCHED_SDL_SOURCE")

root = Path(sys.argv[1])
window_path = root / "src/video/uikit/SDL_uikitwindow.m"
gl_path = root / "src/video/uikit/SDL_uikitopenglview.m"
window_source = window_path.read_text()
gl_source = gl_path.read_text()

# This exact pair is introduced by the pinned v1.3.6 SDL host patch.
window_anchor = """        data.uiwindow.windowLevel = UIWindowLevelNormal + 2.0;
        [data.uiwindow makeKeyAndVisible];"""
window_patch = """        // TEMPORARY BLACK-SCREEN ISOLATION TEST.
        data.uiwindow.windowLevel = UIWindowLevelAlert + 1.0;
        [data.uiwindow makeKeyAndVisible];

        if (@available(iOS 13.0, tvOS 13.0, *)) {
            UIWindowScene *scene = data.uiwindow.windowScene;
            if (scene) {
                for (UIWindow *candidate in scene.windows) {
                    if (candidate != data.uiwindow &&
                        ([candidate.accessibilityIdentifier isEqualToString:@"touchHLE.gameControls"] ||
                         [NSStringFromClass([candidate class]) containsString:@"GameControls"])) {
                        NSLog(@"iOS BLACKSCREEN TEST: hiding controls window=%@", candidate);
                        candidate.hidden = YES;
                        candidate.alpha = 0.0;
                    }
                }
                NSLog(@"iOS BLACKSCREEN TEST: SDLWindow=%p scene=%p activation=%ld level=%.1f key=%d frame=%@",
                      data.uiwindow, scene, (long)scene.activationState,
                      data.uiwindow.windowLevel, data.uiwindow.isKeyWindow,
                      NSStringFromCGRect(data.uiwindow.frame));

                // Dump every window and the first two levels of its view tree.
                // This identifies a black/opaque view covering the SDL GL view.
                for (UIWindow *candidate in scene.windows) {
                    UIViewController *rootVC = candidate.rootViewController;
                    UIView *rootView = rootVC.view;
                    NSLog(@"iOS UIKit stack: window=%p class=%@ level=%.1f hidden=%d alpha=%.3f key=%d frame=%@ rootVC=%@ rootView=%@ rootFrame=%@ rootHidden=%d rootAlpha=%.3f subviews=%lu",
                          candidate, NSStringFromClass([candidate class]),
                          candidate.windowLevel, candidate.hidden, candidate.alpha,
                          candidate.isKeyWindow, NSStringFromCGRect(candidate.frame),
                          rootVC, rootView, NSStringFromCGRect(rootView.frame),
                          rootView.hidden, rootView.alpha,
                          (unsigned long)rootView.subviews.count);
                    for (UIView *child in rootView.subviews) {
                        NSLog(@"iOS UIKit view: window=%p view=%p class=%@ frame=%@ bounds=%@ hidden=%d alpha=%.3f opaque=%d bg=%@ layer=%@ z=%.2f subviews=%lu",
                              candidate, child, NSStringFromClass([child class]),
                              NSStringFromCGRect(child.frame), NSStringFromCGRect(child.bounds),
                              child.hidden, child.alpha, child.opaque, child.backgroundColor,
                              NSStringFromClass([child.layer class]), child.layer.zPosition,
                              (unsigned long)child.subviews.count);
                        for (UIView *grandchild in child.subviews) {
                            NSLog(@"iOS UIKit view: parent=%p view=%p class=%@ frame=%@ hidden=%d alpha=%.3f opaque=%d bg=%@ layer=%@ z=%.2f",
                                  child, grandchild, NSStringFromClass([grandchild class]),
                                  NSStringFromCGRect(grandchild.frame), grandchild.hidden,
                                  grandchild.alpha, grandchild.opaque, grandchild.backgroundColor,
                                  NSStringFromClass([grandchild.layer class]), grandchild.layer.zPosition);
                        }
                    }
                }
            }
        }

        [data.uiwindow makeKeyAndVisible];

        // Do not add a UIKit overlay here: the emulator can occupy the main
        // thread, preventing dispatch_get_main_queue() timers from firing.
        // Keep SDL/EAGL unobstructed from the moment the window is shown.
        NSLog(@"iOS BLACKSCREEN TEST: UIKit probe disabled; SDL/EAGL presentation unobstructed");"""

if "touchHLE.presentationProbe" not in window_source:
    count = window_source.count(window_anchor)
    if count != 1:
        raise SystemExit(f"SDL_uikitwindow.m: expected one upstream show-window anchor, found {count}")
    window_source = window_source.replace(window_anchor, window_patch, 1)
    window_path.write_text(window_source)
    print("patched: UIKit-only presentation probe and SDL window diagnostics")
else:
    print("already patched: UIKit-only presentation probe")

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
