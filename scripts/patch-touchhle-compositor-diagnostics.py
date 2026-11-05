#!/usr/bin/env python3
"""Instrument the touchHLE v0.3.0 Core Animation compositor on iOS."""
from pathlib import Path

core = Path(__file__).resolve().parents[1] / "upstream" / "touchHLE"
path = core / "src/frameworks/core_animation/composition.rs"
source = path.read_text()

def replace_once(old: str, new: str, label: str) -> None:
    global source
    if new in source:
        print(f"already patched: {label}")
        return
    count = source.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected one source anchor, found {count}")
    source = source.replace(old, new, 1)
    print(f"patched: {label}")

replace_once(
'''    if find_fullscreen_eagl_layer(env) != nil {
        // No composition done, EAGLContext will present directly.
        log_dbg!("Using CAEAGLLayer fast path, skipping composition");
        return None;
    }

    if env.options.print_fps {''',
'''    if find_fullscreen_eagl_layer(env) != nil {
        // No composition done, EAGLContext will present directly.
        log_dbg!("Using CAEAGLLayer fast path, skipping composition");
        return None;
    }

    #[cfg(target_os = "ios")]
    {
        use std::sync::atomic::{AtomicU64, Ordering};
        static COMPOSITOR_FRAMES: AtomicU64 = AtomicU64::new(0);
        let frame = COMPOSITOR_FRAMES.fetch_add(1, Ordering::Relaxed) + 1;
        if frame <= 8 || frame % 60 == 0 {
            let visible = windows.iter().filter(|&&window| !msg![env; window isHidden]).count();
            log!("iOS compositor diagnostic: frame={} windows={} visible={} force={}",
                frame, windows.len(), visible, force);
        }
    }

    if env.options.print_fps {''',
"compositor entry and visible-window count")

replace_once(
'''    let fb_width = screen_bounds.size.width as u32 * scale_hack;
    let fb_height = screen_bounds.size.height as u32 * scale_hack;
    let present_frame_args = (''',
'''    let fb_width = screen_bounds.size.width as u32 * scale_hack;
    let fb_height = screen_bounds.size.height as u32 * scale_hack;
    #[cfg(target_os = "ios")]
    {
        use std::sync::atomic::{AtomicU64, Ordering};
        static SIZE_LOG_COUNT: AtomicU64 = AtomicU64::new(0);
        let frame = SIZE_LOG_COUNT.fetch_add(1, Ordering::Relaxed) + 1;
        if frame <= 4 || frame % 120 == 0 {
            log!("iOS compositor diagnostic: screen_bounds={:?} framebuffer={}x{} scale_hack={}",
                screen_bounds, fb_width, fb_height, scale_hack);
        }
    }
    let present_frame_args = (''',
"compositor framebuffer dimensions")

replace_once(
'''    std::mem::drop(gles);
    window.swap_window();

    animation_state.update_started_and_finished_animations(env);''',
'''    std::mem::drop(gles);
    window.swap_window();
    #[cfg(target_os = "ios")]
    {
        use std::sync::atomic::{AtomicU64, Ordering};
        static SWAP_COUNT: AtomicU64 = AtomicU64::new(0);
        let frame = SWAP_COUNT.fetch_add(1, Ordering::Relaxed) + 1;
        if frame <= 8 || frame % 60 == 0 {
            log!("iOS compositor diagnostic: SDL window swap completed frame={}", frame);
        }
    }

    animation_state.update_started_and_finished_animations(env);''',
"compositor final SDL swap")

replace_once(
'''    let need_texture = host_obj.presented_pixels.is_some()
        || host_obj.contents != nil
        || host_obj.cg_context.is_some();
    let need_update = need_texture && !host_obj.gles_texture_is_up_to_date;''',
'''    let need_texture = host_obj.presented_pixels.is_some()
        || host_obj.contents != nil
        || host_obj.cg_context.is_some();
    let need_update = need_texture && !host_obj.gles_texture_is_up_to_date;

    #[cfg(target_os = "ios")]
    if let Some((pixels, width, height)) = &host_obj.presented_pixels {
        use std::sync::atomic::{AtomicU64, Ordering};
        static EAGL_LAYER_LOG_COUNT: AtomicU64 = AtomicU64::new(0);
        let frame = EAGL_LAYER_LOG_COUNT.fetch_add(1, Ordering::Relaxed) + 1;
        if frame <= 8 || frame % 60 == 0 {
            let pixel_count = pixels.len() / 4;
            let non_black = pixels.chunks_exact(4)
                .filter(|p| p[0] != 0 || p[1] != 0 || p[2] != 0)
                .count();
            log!("iOS compositor diagnostic: CAEAGLLayer={:?} bounds={:?} pixels={}x{} bytes={} non_black={}/{} opaque={} texture={:?} texture_current={} need_update={}",
                layer, host_obj.bounds, width, height, pixels.len(), non_black,
                pixel_count, host_obj.opaque, host_obj.gles_texture,
                host_obj.gles_texture_is_up_to_date, need_update);
        }
    }''',
"CAEAGLLayer pending pixel buffer inspection")

replace_once(
'''            upload_rgba8_pixels(gles.as_mut(), pixels, (width, height));
        }
    }

    // Update texture with CGImageRef or CGContextRef pixels, if any''',
'''            upload_rgba8_pixels(gles.as_mut(), pixels, (width, height));
            #[cfg(target_os = "ios")]
            {
                use std::sync::atomic::{AtomicU64, Ordering};
                static UPLOAD_LOG_COUNT: AtomicU64 = AtomicU64::new(0);
                let frame = UPLOAD_LOG_COUNT.fetch_add(1, Ordering::Relaxed) + 1;
                if frame <= 8 || frame % 60 == 0 {
                    let gl_error = unsafe { gles.GetError() };
                    log!("iOS compositor diagnostic: CAEAGLLayer texture upload frame={} layer={:?} size={}x{} GL_error=0x{:x}",
                        frame, layer, width, height, gl_error);
                }
            }
        }
    }

    // Update texture with CGImageRef or CGContextRef pixels, if any''',
"CAEAGLLayer texture upload result")

path.write_text(source)


# The compositor and splash-screen path use a separate internal GLES context.
# Do not inherit fixed-function state from earlier internal draws: a stale
# scissor/depth/stencil/alpha/cull state or texture-env mode can make the
# final textured quad appear blank or partially clipped on iOS.
present_path = core / "src/gles/present.rs"
present_source = present_path.read_text()
present_anchor = """    // Draw the quad
    gles.Viewport("""
present_replacement = """    // Normalize the fixed-function state required by this presentation pass.
    // The EAGL fast path backs up and restores these states around this call;
    // the Core Animation compositor uses its private context and intentionally
    // leaves it in a known state for the next composition frame.
    gles.Disable(gles11::SCISSOR_TEST);
    gles.Disable(gles11::ALPHA_TEST);
    gles.Disable(gles11::DEPTH_TEST);
    gles.Disable(gles11::STENCIL_TEST);
    gles.Disable(gles11::CULL_FACE);
    gles.Disable(gles11::BLEND);
    gles.TexEnvi(
        gles11::TEXTURE_ENV,
        gles11::TEXTURE_ENV_MODE,
        gles11::REPLACE as _,
    );

    // Draw the quad
    gles.Viewport("""
if present_replacement in present_source:
    print("already patched: deterministic present_frame state")
else:
    count = present_source.count(present_anchor)
    if count != 1:
        raise SystemExit(f"deterministic present_frame state: expected one source anchor, found {count}")
    present_source = present_source.replace(present_anchor, present_replacement, 1)
    present_path.write_text(present_source)
    print("patched: deterministic present_frame state")


# OpenGL ES 1.1 requires non-power-of-two textures to use CLAMP_TO_EDGE
# wrapping (and non-mipmap minification filters). The compositor framebuffer
# is sized to the iPhone screen (320x480 on the tested iPad host), so it is
# NPOT. Leaving the default REPEAT wrap makes this texture incomplete on
# implementations without unrestricted NPOT support and sampling it can
# produce a black final presentation even while the source EAGL buffer is
# populated. Apply the required NPOT-safe parameters to the compositor FBO
# texture immediately after allocation and also when reusing it.
npot_anchor = """            gles.TexParameteri(
                gles11::TEXTURE_2D,
                gles11::TEXTURE_MAG_FILTER,
                gles11::LINEAR as _,
            );

            gles.GenFramebuffersOES(1, &mut framebuffer);"""
npot_replacement = """            gles.TexParameteri(
                gles11::TEXTURE_2D,
                gles11::TEXTURE_MAG_FILTER,
                gles11::LINEAR as _,
            );
            gles.TexParameteri(
                gles11::TEXTURE_2D,
                gles11::TEXTURE_WRAP_S,
                gles11::CLAMP_TO_EDGE as _,
            );
            gles.TexParameteri(
                gles11::TEXTURE_2D,
                gles11::TEXTURE_WRAP_T,
                gles11::CLAMP_TO_EDGE as _,
            );

            gles.GenFramebuffersOES(1, &mut framebuffer);"""
if npot_replacement in source:
    print("already patched: NPOT-safe compositor framebuffer texture")
else:
    count = source.count(npot_anchor)
    if count != 1:
        raise SystemExit(f"NPOT-safe compositor framebuffer texture: expected one source anchor, found {count}")
    source = source.replace(npot_anchor, npot_replacement, 1)
    print("patched: NPOT-safe compositor framebuffer texture")

# Existing framebuffer textures survive between frames. Explicitly bind the
# texture before each composition pass so later layer uploads cannot leave a
# different texture bound when the FBO is reused.



# Read back the actual composition FBO before it is copied to SDL's default
# framebuffer. This separates layer composition failures from presentation.
replace_once(
'''    // Present our rendered frame (bound to TEXTURE_2D). This copies it to the
    // default framebuffer (0) so we need to unbind our internal framebuffer.
    unsafe {''',
'''    // iOS diagnostic: inspect the composition FBO before presentation.
    #[cfg(target_os = "ios")]
    {
        use std::sync::atomic::{AtomicU64, Ordering};
        static FBO_READBACK_COUNT: AtomicU64 = AtomicU64::new(0);
        let frame = FBO_READBACK_COUNT.fetch_add(1, Ordering::Relaxed) + 1;
        if frame <= 8 || frame % 60 == 0 {
            let mut pixels = vec![0u8; fb_width as usize * fb_height as usize * 4];
            unsafe {
                gles.Finish();
                gles.ReadPixels(
                    0, 0, fb_width as _, fb_height as _,
                    gles11::RGBA, gles11::UNSIGNED_BYTE,
                    pixels.as_mut_ptr() as *mut _,
                );
            }
            let non_black = pixels.chunks_exact(4)
                .filter(|p| p[0] != 0 || p[1] != 0 || p[2] != 0)
                .count();
            let alpha_nonzero = pixels.chunks_exact(4).filter(|p| p[3] != 0).count();
            let gl_error = unsafe { gles.GetError() };
            log!("iOS compositor readback: stage=composition_fbo frame={} size={}x{} non_black={}/{} alpha_nonzero={}/{} gl_error=0x{:x}",
                frame, fb_width, fb_height, non_black, fb_width as usize * fb_height as usize,
                alpha_nonzero, fb_width as usize * fb_height as usize, gl_error);
        }
    }

    // Present our rendered frame (bound to TEXTURE_2D). This copies it to the
    // default framebuffer (0) so we need to unbind our internal framebuffer.
    unsafe {''',
"composition FBO pixel readback")

# Read back SDL's default framebuffer after present_frame and before swap.
replace_once(
'''    std::mem::drop(gles);
    window.swap_window();''',
'''    #[cfg(target_os = "ios")]
    {
        use std::sync::atomic::{AtomicU64, Ordering};
        static SDL_READBACK_COUNT: AtomicU64 = AtomicU64::new(0);
        let frame = SDL_READBACK_COUNT.fetch_add(1, Ordering::Relaxed) + 1;
        if frame <= 8 || frame % 60 == 0 {
            let (vx, vy, vw, vh) = present_frame_args.0;
            let mut pixels = vec![0u8; vw as usize * vh as usize * 4];
            unsafe {
                gles.Finish();
                gles.ReadPixels(
                    vx as _, vy as _, vw as _, vh as _,
                    gles11::RGBA, gles11::UNSIGNED_BYTE,
                    pixels.as_mut_ptr() as *mut _,
                );
            }
            let non_black = pixels.chunks_exact(4)
                .filter(|p| p[0] != 0 || p[1] != 0 || p[2] != 0)
                .count();
            let alpha_nonzero = pixels.chunks_exact(4).filter(|p| p[3] != 0).count();
            let gl_error = unsafe { gles.GetError() };
            log!("iOS compositor readback: stage=sdl_default_framebuffer frame={} viewport=({}, {}, {}, {}) non_black={}/{} alpha_nonzero={}/{} gl_error=0x{:x}",
                frame, vx, vy, vw, vh, non_black, vw as usize * vh as usize,
                alpha_nonzero, vw as usize * vh as usize, gl_error);
        }
    }
    std::mem::drop(gles);
    window.swap_window();''',
"SDL default framebuffer pixel readback")

# Persist the NPOT fix added above; the earlier write_text() belongs to the
# diagnostics patch section and runs before this additional source rewrite.
path.write_text(source)


// On iOS, SDL's logical window size can differ from the actual OpenGL
// drawable size (e.g. 1440x960 vs 1024x768 on the tested iPad). The old
// non-fullscreen fast return produced a viewport larger than the drawable.
// The final presentation quad was therefore rendered/read back against
// mismatched dimensions. Always compute the iOS viewport from drawable_size,
// retaining the guest aspect ratio and centering it inside the real drawable.
window_path = core / "src/window.rs"
window_source = window_path.read_text()
window_anchor = """        if !self.fullscreen && !Self::rotatable_fullscreen() {
            return (0, 0, app_width, app_height);
        }

        let (screen_width, screen_height) = self.window.drawable_size();"""
window_replacement = """        // SDL iOS may report a logical window size different from the GL
        // drawable size. The viewport is consumed by OpenGL, so it must use
        // drawable pixels even when the SDL window is not marked fullscreen.
        if !self.fullscreen
            && !Self::rotatable_fullscreen()
            && !cfg!(target_os = "ios")
        {
            return (0, 0, app_width, app_height);
        }

        let (screen_width, screen_height) = self.window.drawable_size();"""
if window_replacement in window_source:
    print("already patched: iOS drawable-sized viewport")
else:
    count = window_source.count(window_anchor)
    if count != 1:
        raise SystemExit(
            f"iOS drawable-sized viewport: expected one source anchor, found {count}"
        )
    window_source = window_source.replace(window_anchor, window_replacement, 1)
    window_path.write_text(window_source)
    print("patched: iOS drawable-sized viewport")
