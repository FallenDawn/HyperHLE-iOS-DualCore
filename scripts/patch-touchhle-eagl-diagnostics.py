#!/usr/bin/env python3
"""Add low-volume iOS EAGL/framebuffer diagnostics to official touchHLE v0.3.0."""
from pathlib import Path

CORE = Path(__file__).resolve().parents[1] / "upstream" / "touchHLE"
path = CORE / "src/frameworks/opengles/eagl.rs"
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
'''    let renderbuffer = {
        // Unclear from documentation if this method requires an appropriate
        // context to already be active, but that seems to be the case
        // in practice?
        let mut gles = super::sync_context(&mut env.framework_state.opengles, &mut env.objc, window, env.current_thread);
        unsafe {
            gles.RenderbufferStorageOES(target, internalformat, width.try_into().unwrap(), height.try_into().unwrap());
            let mut renderbuffer = 0;
            gles.GetIntegerv(gles11::RENDERBUFFER_BINDING_OES, &mut renderbuffer);
            renderbuffer as _
        }
    };

    retain(env, drawable);''',
'''    let renderbuffer = {
        // Unclear from documentation if this method requires an appropriate
        // context to already be active, but that seems to be the case
        // in practice?
        let mut gles = super::sync_context(&mut env.framework_state.opengles, &mut env.objc, window, env.current_thread);
        unsafe {
            gles.RenderbufferStorageOES(target, internalformat, width.try_into().unwrap(), height.try_into().unwrap());
            let mut renderbuffer = 0;
            gles.GetIntegerv(gles11::RENDERBUFFER_BINDING_OES, &mut renderbuffer);
            renderbuffer as _
        }
    };

    #[cfg(target_os = "ios")]
    log!("iOS EAGL diagnostic: renderbufferStorage drawable={:?}, renderbuffer={}, size={}x{}, format={:?}", drawable, renderbuffer, width, height, format);

    retain(env, drawable);''',
"renderbuffer allocation diagnostics")

replace_once(
'''    let renderbuffer: GLuint = unsafe {
        let mut renderbuffer = 0;
        gles.GetIntegerv(gles11::RENDERBUFFER_BINDING_OES, &mut renderbuffer);
        renderbuffer as _
    };

    std::mem::drop(gles);''',
'''    let (renderbuffer, renderbuffer_width, renderbuffer_height): (GLuint, GLsizei, GLsizei) = unsafe {
        let mut renderbuffer = 0;
        gles.GetIntegerv(gles11::RENDERBUFFER_BINDING_OES, &mut renderbuffer);
        let (width, height) = get_renderbuffer_size(gles.as_mut());
        (renderbuffer as _, width, height)
    };

    let framebuffer_binding: GLint = unsafe {
        let mut framebuffer = 0;
        gles.GetIntegerv(gles11::FRAMEBUFFER_BINDING_OES, &mut framebuffer);
        framebuffer
    };
    #[cfg(target_os = "ios")]
    log!("iOS EAGL diagnostic: present state renderbuffer={} size={}x{} framebuffer_binding={}",
        renderbuffer, renderbuffer_width, renderbuffer_height, framebuffer_binding);

    std::mem::drop(gles);''',
"presentRenderbuffer bound buffer dimensions")

replace_once(
'''    };

    // We're presenting to the opaque CAEAGLLayer that covers the screen.
    // We can use the fast path where we skip composition and present directly.''',
'''    };

    #[cfg(target_os = "ios")]
    {
        use std::sync::atomic::{AtomicU64, Ordering};
        static PRESENT_COUNT: AtomicU64 = AtomicU64::new(0);
        let frame = PRESENT_COUNT.fetch_add(1, Ordering::Relaxed) + 1;
        if frame <= 8 || frame % 60 == 0 {
            log!("iOS EAGL diagnostic: present #{} renderbuffer={} size={}x{} drawable={:?} fullscreen_layer={:?} force_composition={}",
                frame, renderbuffer, renderbuffer_width, renderbuffer_height,
                drawable, fullscreen_layer, env.options.force_composition);
        }
    }

    // We're presenting to the opaque CAEAGLLayer that covers the screen.
    // We can use the fast path where we skip composition and present directly.''',
"present path and drawable binding diagnostics")

replace_once(
'''        let (pixels_vec, width, height) = {
            let mut gles = super::sync_context(&mut env.framework_state.opengles, &mut env.objc, env.window.as_mut().unwrap(), env.current_thread);
            unsafe {
                read_renderbuffer(gles.as_mut(), pixels_vec)
            }
        };
        present_pixels(env, drawable, pixels_vec, width, height);''',
'''        let (pixels_vec, width, height) = {
            let mut gles = super::sync_context(&mut env.framework_state.opengles, &mut env.objc, env.window.as_mut().unwrap(), env.current_thread);
            unsafe {
                read_renderbuffer(gles.as_mut(), pixels_vec)
            }
        };
        #[cfg(target_os = "ios")]
        {
            use std::sync::atomic::{AtomicU64, Ordering};
            static READBACK_COUNT: AtomicU64 = AtomicU64::new(0);
            let frame = READBACK_COUNT.fetch_add(1, Ordering::Relaxed) + 1;
            if frame <= 8 || frame % 60 == 0 {
                let pixel_count = pixels_vec.len() / 4;
                let non_black = pixels_vec.chunks_exact(4)
                    .filter(|p| p[0] != 0 || p[1] != 0 || p[2] != 0)
                    .count();
                let alpha_nonzero = pixels_vec.chunks_exact(4)
                    .filter(|p| p[3] != 0)
                    .count();
                let mut min_rgb = [u8::MAX; 3];
                let mut max_rgb = [u8::MIN; 3];
                let mut colors = std::collections::HashSet::<u16>::new();
                let mut hash: u64 = 0xcbf29ce484222325;
                for p in pixels_vec.chunks_exact(4) {
                    for channel in 0..3 {
                        min_rgb[channel] = min_rgb[channel].min(p[channel]);
                        max_rgb[channel] = max_rgb[channel].max(p[channel]);
                    }
                    colors.insert(((p[0] as u16 >> 3) << 10) | ((p[1] as u16 >> 3) << 5) | (p[2] as u16 >> 3));
                    for byte in &p[..3] { hash = (hash ^ *byte as u64).wrapping_mul(0x100000001b3); }
                }
                log!("iOS EAGL diagnostic: readback #{} size={}x{} bytes={} non_black_pixels={}/{} alpha_nonzero={}/{} unique_rgb555={} min_rgb={:?} max_rgb={:?} fnv64={:016x}",
                    frame, width, height, pixels_vec.len(), non_black, pixel_count,
                    alpha_nonzero, pixel_count, colors.len(), min_rgb, max_rgb, hash);
            }
        }
        present_pixels(env, drawable, pixels_vec, width, height);
        #[cfg(target_os = "ios")]
        log_dbg!("iOS EAGL diagnostic: copied readback pixels into CAEAGLLayer {:?}", drawable);''',
"readback pixel-content diagnostics")

path.write_text(source)
