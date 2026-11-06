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


# Instrument the guest application's GLES 1.1 entry points. The EAGL
# renderbuffer can be black either because the guest never issues draws or
# because its draw state/data is not accepted by the native driver. These
# counters distinguish those cases without logging every call indefinitely.
guest_path = CORE / "src/frameworks/opengles/gles_guest.rs"
guest = guest_path.read_text()

def guest_replace(old: str, new: str, label: str) -> None:
    global guest
    if new in guest:
        print(f"already patched: {label}")
        return
    count = guest.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected one guest GLES source anchor, found {count}")
    guest = guest.replace(old, new, 1)
    print(f"patched: {label}")

guest_replace(
'''fn glViewport(env: &mut Environment, x: GLint, y: GLint, width: GLsizei, height: GLsizei) {
    // apply scale hack: assume framebuffer's size is larger than the app thinks
    // and scale viewport appropriately
    let factor = env.options.scale_hack.get() as GLsizei;
    let (x, y) = (x * factor, y * factor);
    let (width, height) = (width * factor, height * factor);
    with_ctx_and_mem(env, |gles, _mem| unsafe {
        gles.Viewport(x, y, width, height)
    })
}''',
'''fn glViewport(env: &mut Environment, x: GLint, y: GLint, width: GLsizei, height: GLsizei) {
    // apply scale hack: assume framebuffer's size is larger than the app thinks
    // and scale viewport appropriately
    let factor = env.options.scale_hack.get() as GLsizei;
    let (x, y) = (x * factor, y * factor);
    let (width, height) = (width * factor, height * factor);
    #[cfg(target_os = "ios")]
    {
        use std::sync::atomic::{AtomicU64, Ordering};
        static COUNT: AtomicU64 = AtomicU64::new(0);
        let n = COUNT.fetch_add(1, Ordering::Relaxed) + 1;
        if n <= 24 {
            log!("iOS guest GLES: glViewport #{} guest=({}, {}, {}, {}) scaled=({}, {}, {}, {}) factor={}",
                n, x / factor, y / factor, width / factor, height / factor,
                x, y, width, height, factor);
        }
    }
    with_ctx_and_mem(env, |gles, _mem| unsafe {
        gles.Viewport(x, y, width, height)
    })
}''',
"guest glViewport calls")

guest_replace(
'''fn glDrawArrays(env: &mut Environment, mode: GLenum, first: GLint, count: GLsizei) {
    with_ctx_and_mem(env, |gles, _mem| unsafe {
        let fog_state_backup = clamp_fog_state_values(gles);
        gles.DrawArrays(mode, first, count);
        restore_fog_state_values(gles, fog_state_backup);
    })
}''',
'''fn glDrawArrays(env: &mut Environment, mode: GLenum, first: GLint, count: GLsizei) {
    #[cfg(target_os = "ios")]
    {
        use std::sync::atomic::{AtomicU64, Ordering};
        static COUNT: AtomicU64 = AtomicU64::new(0);
        let n = COUNT.fetch_add(1, Ordering::Relaxed) + 1;
        if n <= 48 || n % 500 == 0 {
            log!("iOS guest GLES: glDrawArrays #{} mode=0x{:x} first={} count={}", n, mode, first, count);
        }
    }
    with_ctx_and_mem(env, |gles, _mem| unsafe {
        #[cfg(target_os = "ios")]
        {
            use std::sync::atomic::{AtomicU64, Ordering};
            static DRAW_STATE_COUNT: AtomicU64 = AtomicU64::new(0);
            let state_n = DRAW_STATE_COUNT.fetch_add(1, Ordering::Relaxed) + 1;
            if state_n <= 8 {
                let mut viewport = [0; 4];
                let mut scissor = [0; 4];
                let mut vertex_size = 0;
                let mut vertex_type = 0;
                let mut vertex_stride = 0;
                let mut vertex_buffer = 0;
                let mut tex_size = 0;
                let mut tex_type = 0;
                let mut tex_stride = 0;
                let mut tex_buffer = 0;
                let mut texture_binding = 0;
                let mut matrix_mode = 0;
                let mut tex_env_mode = 0;
                let mut current_color = [0.0; 4];
                gles.GetIntegerv(gles11::VIEWPORT, viewport.as_mut_ptr());
                gles.GetIntegerv(gles11::SCISSOR_BOX, scissor.as_mut_ptr());
                gles.GetIntegerv(gles11::VERTEX_ARRAY_SIZE, &mut vertex_size);
                gles.GetIntegerv(gles11::VERTEX_ARRAY_TYPE, &mut vertex_type);
                gles.GetIntegerv(gles11::VERTEX_ARRAY_STRIDE, &mut vertex_stride);
                gles.GetIntegerv(gles11::VERTEX_ARRAY_BUFFER_BINDING, &mut vertex_buffer);
                gles.GetIntegerv(gles11::TEXTURE_COORD_ARRAY_SIZE, &mut tex_size);
                gles.GetIntegerv(gles11::TEXTURE_COORD_ARRAY_TYPE, &mut tex_type);
                gles.GetIntegerv(gles11::TEXTURE_COORD_ARRAY_STRIDE, &mut tex_stride);
                gles.GetIntegerv(gles11::TEXTURE_COORD_ARRAY_BUFFER_BINDING, &mut tex_buffer);
                gles.GetIntegerv(gles11::TEXTURE_BINDING_2D, &mut texture_binding);
                gles.GetIntegerv(gles11::MATRIX_MODE, &mut matrix_mode);
                gles.GetTexEnviv(gles11::TEXTURE_ENV, gles11::TEXTURE_ENV_MODE, &mut tex_env_mode);
                gles.GetFloatv(gles11::CURRENT_COLOR, current_color.as_mut_ptr());
                log!("iOS guest GLES state: draw={} viewport={:?} scissor={:?} vertex(enabled={},size={},type=0x{:x},stride={},vbo={}) texcoord(enabled={},size={},type=0x{:x},stride={},vbo={}) texture2d={} texture_binding={} blend={} alpha={} depth={} scissor_test={} fog={} matrix_mode=0x{:x} tex_env=0x{:x} current_color={:?}",
                    state_n, viewport, scissor,
                    gles.IsEnabled(gles11::VERTEX_ARRAY), vertex_size, vertex_type, vertex_stride, vertex_buffer,
                    gles.IsEnabled(gles11::TEXTURE_COORD_ARRAY), tex_size, tex_type, tex_stride, tex_buffer,
                    gles.IsEnabled(gles11::TEXTURE_2D), texture_binding,
                    gles.IsEnabled(gles11::BLEND), gles.IsEnabled(gles11::ALPHA_TEST),
                    gles.IsEnabled(gles11::DEPTH_TEST), gles.IsEnabled(gles11::SCISSOR_TEST),
                    gles.IsEnabled(gles11::FOG), matrix_mode, tex_env_mode, current_color);
            }
        }
        let fog_state_backup = clamp_fog_state_values(gles);
        gles.DrawArrays(mode, first, count);
        restore_fog_state_values(gles, fog_state_backup);
    })
}''',
"guest glDrawArrays calls")

guest_replace(
'''    indices: ConstVoidPtr,
) {
    with_ctx_and_mem(env, |gles, mem| unsafe {
        let fog_state_backup = clamp_fog_state_values(gles);''',
'''    indices: ConstVoidPtr,
) {
    #[cfg(target_os = "ios")]
    {
        use std::sync::atomic::{AtomicU64, Ordering};
        static COUNT: AtomicU64 = AtomicU64::new(0);
        let n = COUNT.fetch_add(1, Ordering::Relaxed) + 1;
        if n <= 48 || n % 500 == 0 {
            log!("iOS guest GLES: glDrawElements #{} mode=0x{:x} count={} type=0x{:x} indices={:?}", n, mode, count, type_, indices);
        }
    }
    with_ctx_and_mem(env, |gles, mem| unsafe {
        let fog_state_backup = clamp_fog_state_values(gles);''',
"guest glDrawElements calls")

guest_replace(
'''fn glClear(env: &mut Environment, mask: GLbitfield) {
    with_ctx_and_mem(env, |gles, _mem| unsafe { gles.Clear(mask) });
}''',
'''fn glClear(env: &mut Environment, mask: GLbitfield) {
    #[cfg(target_os = "ios")]
    {
        use std::sync::atomic::{AtomicU64, Ordering};
        static COUNT: AtomicU64 = AtomicU64::new(0);
        let n = COUNT.fetch_add(1, Ordering::Relaxed) + 1;
        if n <= 32 || n % 500 == 0 {
            log!("iOS guest GLES: glClear #{} mask=0x{:x}", n, mask);
        }
    }
    with_ctx_and_mem(env, |gles, _mem| unsafe { gles.Clear(mask) });
}''',
"guest glClear calls")

guest_replace(
'''    alpha: GLclampf,
) {
    with_ctx_and_mem(env, |gles, _mem| unsafe {
        gles.ClearColor(red, green, blue, alpha)
    });
}''',
'''    alpha: GLclampf,
) {
    #[cfg(target_os = "ios")]
    {
        use std::sync::atomic::{AtomicU64, Ordering};
        static COUNT: AtomicU64 = AtomicU64::new(0);
        let n = COUNT.fetch_add(1, Ordering::Relaxed) + 1;
        if n <= 32 {
            log!("iOS guest GLES: glClearColor #{} rgba=({:.3}, {:.3}, {:.3}, {:.3})", n, red, green, blue, alpha);
        }
    }
    with_ctx_and_mem(env, |gles, _mem| unsafe {
        gles.ClearColor(red, green, blue, alpha)
    });
}''',
"guest glClearColor calls")

guest_replace(
'''fn glBindFramebufferOES(env: &mut Environment, target: GLenum, framebuffer: GLuint) {
    with_ctx_and_mem(env, |gles, _mem| unsafe {
        gles.BindFramebufferOES(target, framebuffer)
    })
}''',
'''fn glBindFramebufferOES(env: &mut Environment, target: GLenum, framebuffer: GLuint) {
    #[cfg(target_os = "ios")]
    {
        use std::sync::atomic::{AtomicU64, Ordering};
        static COUNT: AtomicU64 = AtomicU64::new(0);
        let n = COUNT.fetch_add(1, Ordering::Relaxed) + 1;
        if n <= 32 {
            log!("iOS guest GLES: glBindFramebufferOES #{} target=0x{:x} framebuffer={}", n, target, framebuffer);
        }
    }
    with_ctx_and_mem(env, |gles, _mem| unsafe {
        gles.BindFramebufferOES(target, framebuffer)
    })
}''',
"guest framebuffer binding calls")

guest_path.write_text(guest)
