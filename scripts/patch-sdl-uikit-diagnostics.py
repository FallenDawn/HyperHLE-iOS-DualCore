#!/usr/bin/env python3
"""Add runtime diagnostics to SDL's iOS UIWindow and EAGL presentation path."""
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit("usage: patch-sdl-uikit-diagnostics.py PATH_TO_PATCHED_SDL_SOURCE")

root = Path(sys.argv[1])
window_path = root / "src/video/uikit/SDL_uikitwindow.m"
gl_path = root / "src/video/uikit/SDL_uikitopenglview.m"
window_source = window_path.read_text()
gl_source = gl_path.read_text()

window_anchor = """        data.uiwindow.windowLevel = UIWindowLevelNormal + 2.0;
        [data.uiwindow makeKeyAndVisible];"""
window_patch = """        data.uiwindow.windowLevel = UIWindowLevelNormal + 2.0;
        [data.uiwindow makeKeyAndVisible];

        // The host creates its controls window before SDL creates this window.
        // Dump the real post-creation stack, not the earlier incomplete stack.
        if (@available(iOS 13.0, tvOS 13.0, *)) {
            UIWindowScene *scene = data.uiwindow.windowScene;
            NSLog(@"iOS SDL window diagnostic: SDLWindow=%p uiwindow=%p scene=%p activation=%ld hidden=%d alpha=%.3f opaque=%d level=%.1f key=%d frame=%@ root=%@",
                  window, data.uiwindow, scene, (long)scene.activationState,
                  data.uiwindow.hidden, data.uiwindow.alpha, data.uiwindow.opaque,
                  data.uiwindow.windowLevel, data.uiwindow.isKeyWindow,
                  NSStringFromCGRect(data.uiwindow.frame),
                  data.uiwindow.rootViewController ? NSStringFromClass([data.uiwindow.rootViewController class]) : @"nil");
            NSUInteger index = 0;
            for (UIWindow *candidate in scene.windows) {
                UIView *rootView = candidate.rootViewController.viewIfLoaded;
                NSLog(@"iOS SDL scene stack: index=%lu class=%@ hidden=%d alpha=%.3f opaque=%d level=%.1f key=%d frame=%@ root=%@ rootViewHidden=%d rootViewAlpha=%.3f rootViewOpaque=%d rootBackground=%@",
                      (unsigned long)index++, NSStringFromClass([candidate class]),
                      candidate.hidden, candidate.alpha, candidate.opaque,
                      candidate.windowLevel, candidate.isKeyWindow,
                      NSStringFromCGRect(candidate.frame),
                      candidate.rootViewController ? NSStringFromClass([candidate.rootViewController class]) : @"nil",
                      rootView ? rootView.hidden : NO, rootView ? rootView.alpha : 1.0,
                      rootView ? rootView.opaque : NO,
                      rootView ? rootView.backgroundColor : nil);
            }
        }"""
if window_patch not in window_source:
    count = window_source.count(window_anchor)
    if count != 1:
        raise SystemExit(f"SDL_uikitwindow.m: expected one show-window anchor, found {count}")
    window_source = window_source.replace(window_anchor, window_patch, 1)
    window_path.write_text(window_source)
    print("patched: post-show SDL UIWindow and UIWindowScene stack diagnostics")
else:
    print("already patched: post-show SDL UIWindow diagnostics")

gl_anchor = "    [context presentRenderbuffer:GL_RENDERBUFFER];"
gl_patch = """    BOOL didPresent = [context presentRenderbuffer:GL_RENDERBUFFER];
    static NSUInteger touchHLEPresentDiagnosticCount = 0;
    ++touchHLEPresentDiagnosticCount;
    if (touchHLEPresentDiagnosticCount <= 8 || touchHLEPresentDiagnosticCount % 120 == 0) {
        NSLog(@"iOS SDL present diagnostic: frame=%lu success=%d context=%p view=%p layer=%p renderbuffer=%u bounds=%@",
              (unsigned long)touchHLEPresentDiagnosticCount, didPresent, context,
              self, self.layer, (unsigned int)viewRenderbuffer, NSStringFromCGRect(self.bounds));
    }"""
if gl_patch not in gl_source:
    count = gl_source.count(gl_anchor)
    if count != 1:
        raise SystemExit(f"SDL_uikitopenglview.m: expected one presentRenderbuffer anchor, found {count}")
    gl_source = gl_source.replace(gl_anchor, gl_patch, 1)
    gl_path.write_text(gl_source)
    print("patched: EAGL presentRenderbuffer return-value diagnostics")
else:
    print("already patched: EAGL present diagnostics")
