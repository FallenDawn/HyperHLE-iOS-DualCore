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
                    let gl_error = gles.GetError();
                    log!("iOS compositor diagnostic: CAEAGLLayer texture upload frame={} layer={:?} size={}x{} GL_error=0x{:x}",
                        frame, layer, width, height, gl_error);
                }
            }
        }
    }

    // Update texture with CGImageRef or CGContextRef pixels, if any''',
"CAEAGLLayer texture upload result")

path.write_text(source)
