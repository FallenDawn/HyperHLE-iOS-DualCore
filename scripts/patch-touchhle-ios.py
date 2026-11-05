#!/usr/bin/env python3
"""Apply the small, auditable iOS host-integration patch to official touchHLE v0.3.0."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CORE = Path(__file__).resolve().parents[1] / "upstream" / "touchHLE"

def replace_once(path: str, old: str, new: str, label: str) -> None:
    p = CORE / path
    text = p.read_text()
    if new in text:
        print(f"already patched: {label}")
        return
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected exactly one anchor in {path}, found {count}")
    p.write_text(text.replace(old, new, 1))
    print(f"patched: {label}")

def main() -> None:
    cargo = CORE / "Cargo.toml"
    text = cargo.read_text()
    if 'dynamic-sdl = ["touchHLE_openal_soft_wrapper/static"]' not in text:
        anchor = 'static = ["sdl2/bundled", "sdl2/static-link", "touchHLE_openal_soft_wrapper/static"]\n'
        if text.count(anchor) != 1:
            raise SystemExit("Cargo.toml: static feature anchor not found exactly once")
        text = text.replace(anchor, anchor + '\n# Link SDL2 dynamically from the iOS host application.\ndynamic-sdl = ["touchHLE_openal_soft_wrapper/static"]\n', 1)
        cargo.write_text(text)
    else:
        print("already patched: dynamic-sdl feature")

    lib_insert = '''
#[cfg(target_os = "ios")]
use std::sync::atomic::{AtomicBool, AtomicU32, Ordering};

#[cfg(target_os = "ios")]
static HOST_EXIT_REQUESTED: AtomicBool = AtomicBool::new(false);
#[cfg(target_os = "ios")]
static HOST_FPS_BITS: AtomicU32 = AtomicU32::new(0);

#[cfg(target_os = "ios")]
pub fn request_host_exit() {
    HOST_EXIT_REQUESTED.store(true, Ordering::Release);
}

#[cfg(target_os = "ios")]
pub fn clear_host_exit_request() {
    HOST_EXIT_REQUESTED.store(false, Ordering::Release);
    HOST_FPS_BITS.store(0, Ordering::Release);
}

#[cfg(target_os = "ios")]
pub fn host_fps() -> f32 {
    f32::from_bits(HOST_FPS_BITS.load(Ordering::Acquire))
}

#[cfg(target_os = "ios")]
pub struct HostAppMetadata {
    pub display_name: String,
    pub bundle_identifier: String,
    pub orientation_capabilities: u32,
    pub icon_rgba: Vec<u8>,
    pub icon_width: u32,
    pub icon_height: u32,
}

#[cfg(target_os = "ios")]
pub fn inspect_host_app(path: &std::path::Path) -> Result<HostAppMetadata, String> {
    let bundle_data = fs::BundleData::open_any(path)?;
    let (bundle, fs) =
        bundle::Bundle::new_bundle_and_fs_from_host_path(bundle_data, true)?;
    let display_name = if bundle.display_name().is_empty() {
        bundle.bundle_name()
    } else {
        bundle.display_name()
    }.to_owned();
    let bundle_identifier = bundle.bundle_identifier().to_owned();
    let supported_orientations = bundle.supported_interface_orientations();
    let supports_portrait = supported_orientations.iter().any(|o| o.contains("Portrait"));
    let supports_landscape = supported_orientations.iter().any(|o| o.contains("Landscape"));
    let orientation_capabilities =
        u32::from(supports_portrait) | (u32::from(supports_landscape) << 1);
    let (icon_rgba, icon_width, icon_height) = match bundle.load_icon(&fs) {
        Ok(icon) => {
            let (width, height) = icon.dimensions();
            (icon.pixels().to_vec(), width, height)
        }
        Err(_) => (Vec::new(), 0, 0),
    };
    Ok(HostAppMetadata {
        display_name, bundle_identifier, orientation_capabilities,
        icon_rgba, icon_width, icon_height,
    })
}

#[cfg(target_os = "ios")]
fn take_host_exit_request() -> bool {
    HOST_EXIT_REQUESTED.swap(false, Ordering::AcqRel)
}
'''
    replace_once("src/lib.rs", "pub use touchHLE_version::*;\n", "pub use touchHLE_version::*;\n" + lib_insert, "iOS lifecycle and metadata API")
    replace_once(
        "src/cpu/dynarmic_wrapper/build.rs",
        '    let dynarmic_root = workspace_root.join("vendor/dynarmic");',
        '    let dynarmic_root = env::var_os("TOUCHHLE_DYNARMIC_DIR")\n        .map(std::path::PathBuf::from)\n        .unwrap_or_else(|| workspace_root.join("vendor/dynarmic"));',
        "external patched Dynarmic source override",
    )

    replace_once(
        "src/environment.rs",
        "        loop {\n            if self.threads[self.current_thread].state == ThreadState::Stepping {",
        "        loop {\n            #[cfg(target_os = \"ios\")]\n            if crate::take_host_exit_request() {\n                echo!(\"Returning to the iOS host library.\");\n                let thread = &mut self.threads[self.current_thread];\n                assert!(thread.host_context.is_none());\n                thread.host_context = Some(curr_host_context);\n                return;\n            }\n            if self.threads[self.current_thread].state == ThreadState::Stepping {",
        "cooperative return to iOS host",
    )

    # Emit the actual Info.plist device-family decision and SDL drawable metrics.
    replace_once(
        "src/environment.rs",
        "        let device_family_array = bundle.device_family_array();",
        "        let device_family_array = bundle.device_family_array();\n        #[cfg(target_os = \"ios\")]\n        log!(\"iOS diagnostic: bundle path={:?}, parsed UIDeviceFamily={:?}\", bundle.bundle_path(), device_family_array);",
        "iOS bundle UIDeviceFamily diagnostic",
    )
    replace_once(
        "src/window.rs",
        "        if let Some(icon) = icon {",
        "        #[cfg(target_os = \"ios\")]\n        log!(\"iOS diagnostic: SDL window size={:?}, drawable size={:?}, family={:?}, orientation={:?}\", window.size(), window.drawable_size(), device_family, device_orientation);\n\n        if let Some(icon) = icon {",
        "iOS SDL window and drawable diagnostic",
    )
    replace_once(
        "src/window.rs",
        "    pub fn swap_window(&self) {\n        self.window.gl_swap_window();\n    }",
        "    pub fn swap_window(&self) {\n        #[cfg(target_os = \"ios\")]\n        {\n            static FIRST_PRESENT: std::sync::atomic::AtomicBool = std::sync::atomic::AtomicBool::new(true);\n            if FIRST_PRESENT.swap(false, std::sync::atomic::Ordering::Relaxed) {\n                log!(\"iOS diagnostic: first GL present; window={:?}, drawable={:?}, viewport={:?}\", self.window.size(), self.window.drawable_size(), self.viewport());\n            }\n        }\n        self.window.gl_swap_window();\n    }",
        "iOS first OpenGL present diagnostic",
    )

    paths = CORE / "src/paths.rs"
    ptext = paths.read_text()
    if "pub fn default_options_file()" not in ptext:
        anchor = 'pub const DEFAULT_OPTIONS_FILE: &str = "touchHLE_default_options.txt";\n'
        if ptext.count(anchor) != 1:
            raise SystemExit("paths.rs: DEFAULT_OPTIONS_FILE anchor not found")
        addition = '''
/// Select a core-specific default options file when hosted by a multi-core app.
pub fn default_options_file() -> String {
    std::env::var("TOUCHHLE_DEFAULT_OPTIONS_FILE")
        .ok()
        .filter(|name| !name.is_empty())
        .unwrap_or_else(|| DEFAULT_OPTIONS_FILE.to_string())
}
'''
        ptext = ptext.replace(anchor, anchor + addition, 1)
    old_resource_fn = """/// macOS-only: If touchHLE is located in a .app bundle, return the path of the
/// Resources directory. If touchHLE is not located in a .app bundle, return
/// [None].
#[allow(dead_code)]
fn get_macos_bundled_resources_path() -> Option<PathBuf> {
    if std::env::consts::OS != "macos" {
        return None;
    }
    let base_path = PathBuf::from(sdl2::filesystem::base_path().ok()?);
    if base_path.file_name().is_some_and(|p| p == "Resources") {
        Some(base_path)
    } else {
        None
    }
}"""
    new_resource_fn = """/// On Apple hosts, return the resources directory inside the application bundle.
#[allow(dead_code)]
fn get_bundled_resources_path() -> Option<PathBuf> {
    if !matches!(std::env::consts::OS, "ios" | "macos") {
        return None;
    }
    let base_path = PathBuf::from(sdl2::filesystem::base_path().ok()?);
    if std::env::consts::OS == "ios"
        || base_path.file_name().is_some_and(|p| p == "Resources")
    {
        Some(base_path)
    } else {
        None
    }
}"""
    if new_resource_fn not in ptext:
        if ptext.count(old_resource_fn) != 1:
            raise SystemExit("paths.rs: original bundled-resource helper not found exactly once")
        ptext = ptext.replace(old_resource_fn, new_resource_fn, 1)
    ptext = ptext.replace("get_macos_bundled_resources_path()", "get_bundled_resources_path()")
    ptext = ptext.replace("cfg!(not(target_os = \"android\"))", "cfg!(not(any(target_os = \"android\", target_os = \"ios\")))")
    ptext = ptext.replace(
        '    #[cfg(not(target_os = "android"))]\n    {\n        // When touchHLE is run from a .app bundle on macOS,',
        '    #[cfg(not(target_os = "android"))]\n    {\n        if std::env::consts::OS == "ios" {\n            let home = std::env::var_os("HOME").expect("iOS app container has no HOME path");\n            return Cow::from(PathBuf::from(home).join("Documents"));\n        }\n        // When touchHLE is run from a .app bundle on macOS,',
        1
    )
    ptext = ptext.replace(
        '    if std::env::consts::OS != "android" && std::env::consts::OS != "macos" {',
        '    if std::env::consts::OS != "android" && std::env::consts::OS != "macos" && std::env::consts::OS != "ios" {',
        1
    )
    # Do not let a pre-existing Documents/touchHLE_options.txt from an
    # earlier dual-core test override the official v0.3.0 defaults bundled
    # inside this installer. Keep an independent optional override file.
    old_user_options = 'pub const USER_OPTIONS_FILE: &str = "touchHLE_options.txt";'
    new_user_options = 'pub const USER_OPTIONS_FILE: &str = "touchHLE_options_coreb.txt";'
    if new_user_options not in ptext:
        if ptext.count(old_user_options) != 1:
            raise SystemExit("paths.rs: USER_OPTIONS_FILE anchor not found exactly once")
        ptext = ptext.replace(old_user_options, new_user_options, 1)

    paths.write_text(ptext)
    print("patched: iOS bundle resources, Documents data path, isolated Core B overrides and core-specific options")

    replace_once(
        "src/lib.rs",
        "    let default_options_path = paths::DEFAULT_OPTIONS_FILE;",
        "    let default_options_path = paths::default_options_file();",
        "core-specific default options selection",
    )

    replace_once(
        "src/lib.rs",
        "    match paths::ResourceFile::open(default_options_path) {",
        "    match paths::ResourceFile::open(&default_options_path) {",
        "borrow core-specific default options path",
    )


    # OpenAL Soft must use its native iOS CoreAudio/RemoteIO backend.
    # Do not allow a successful static build that silently contains no
    # usable playback backend.
    replace_once(
        "src/audio/openal_soft_wrapper/build.rs",
        '        build.define("ALSOFT_EXAMPLES", "OFF");',
        '        build.define("ALSOFT_EXAMPLES", "OFF");\n\n        if os.eq_ignore_ascii_case("ios") {\n            build.define("ALSOFT_REQUIRE_COREAUDIO", "ON");\n            build.define("ALSOFT_BACKEND_COREAUDIO", "ON");\n        }',
        "require OpenAL Soft CoreAudio backend on iOS",
    )
    replace_once(
        "src/audio/openal_soft_wrapper/build.rs",
        '        if os.eq_ignore_ascii_case("macos") {\n            link_framework("AudioToolbox");\n            link_framework("CoreAudio");\n            link_framework("CoreFoundation");\n        }',
        '        if os.eq_ignore_ascii_case("macos") {\n            link_framework("AudioToolbox");\n            link_framework("CoreAudio");\n            link_framework("CoreFoundation");\n        }\n        if os.eq_ignore_ascii_case("ios") {\n            link_framework("AudioToolbox");\n            link_framework("CoreAudio");\n            link_framework("CoreFoundation");\n        }',
        "link iOS CoreAudio frameworks",
    )

    # Log the actual OpenAL device/context creation on-device. A successful
    # compile alone does not prove that RemoteIO opened at runtime.
    replace_once(
        "src/audio/openal.rs",
        '        let device = unsafe { al_sys::alcOpenDevice(std::ptr::null()) };\n        if device.is_null() {',
        '        let device = unsafe { al_sys::alcOpenDevice(std::ptr::null()) };\n        #[cfg(target_os = "ios")]\n        log!("iOS audio diagnostic: alcOpenDevice(default) -> {:?}", device);\n        if device.is_null() {\n            #[cfg(target_os = "ios")]\n            log!("iOS audio diagnostic: OpenAL device open failed, ALC error=0x{:x}", unsafe { al_sys::alcGetError(std::ptr::null_mut()) });',
        "OpenAL iOS device-open diagnostics",
    )
    replace_once(
        "src/audio/openal.rs",
        '        let context = unsafe { al_sys::alcCreateContext(device, attrlist) };\n        if context.is_null() {',
        '        let context = unsafe { al_sys::alcCreateContext(device, attrlist) };\n        #[cfg(target_os = "ios")]\n        log!("iOS audio diagnostic: alcCreateContext(device={:?}) -> {:?}", device, context);\n        if context.is_null() {',
        "OpenAL iOS context diagnostics",
    )

    # Inspect guest PCM before and after the AudioUnit render callback.
    replace_once(
        """    // Run render callback
    let AURenderCallbackStruct {
        input_proc: inputProc,
        input_proc_ref_con: inputProcRefCon,
    } = audio_unit_host_object.render_callback.unwrap();
    let () = inputProc.call_from_host(
        env,
        (
            inputProcRefCon,
            action_flags,
            nil.cast_void().cast_const(),
            0u32,
            number_frames,
            audio_buffer_list,
        ),
    );

    let at_state = &mut env.framework_state.audio_toolbox;""",
        """    // Run render callback
    let AURenderCallbackStruct {
        input_proc: inputProc,
        input_proc_ref_con: inputProcRefCon,
    } = audio_unit_host_object.render_callback.unwrap();
    #[cfg(target_os = "ios")]
    let callback_frame = {
        use std::sync::atomic::{AtomicU64, Ordering};
        static CALLBACK_LOG_COUNT: AtomicU64 = AtomicU64::new(0);
        CALLBACK_LOG_COUNT.fetch_add(1, Ordering::Relaxed) + 1
    };
    #[cfg(target_os = "ios")]
    if callback_frame <= 10 || callback_frame % 120 == 0 {
        let bytes = env.mem.bytes_at(buffer1Data.cast(), buffer_size);
        let non_zero = bytes.iter().filter(|&&sample| sample != 0).count();
        log!("iOS audio diagnostic: guest callback BEFORE frame={} proc={:?} refcon={:?} frames={} sample_rate={} channels={} bits={} bytes={} non_zero_bytes={}",
            callback_frame, inputProc, inputProcRefCon, number_frames, sample_rate,
            stream_format.channels_per_frame, stream_format.bits_per_channel,
            bytes.len(), non_zero);
    }
    let () = inputProc.call_from_host(
        env,
        (
            inputProcRefCon,
            action_flags,
            nil.cast_void().cast_const(),
            0u32,
            number_frames,
            audio_buffer_list,
        ),
    );
    #[cfg(target_os = "ios")]
    if callback_frame <= 10 || callback_frame % 120 == 0 {
        let bytes = env.mem.bytes_at(buffer1Data.cast(), buffer_size);
        let non_zero = bytes.iter().filter(|&&sample| sample != 0).count();
        log!("iOS audio diagnostic: guest callback AFTER frame={} proc={:?} refcon={:?} bytes={} non_zero_bytes={}",
            callback_frame, inputProc, inputProcRefCon, bytes.len(), non_zero);
    }

    let at_state = &mut env.framework_state.audio_toolbox;""",
        "guest AudioUnit callback PCM before and after",
    )

    # Record AudioUnit start and whether the guest callback supplies non-zero
    # PCM before OpenAL queues it for the native output device.
    replace_once(
        "src/frameworks/audio_toolbox/audio_unit.rs",
        '    log_dbg!("AudioOutputUnitStart({:?}) -> {:?}", ci, result);',
        '    log_dbg!("AudioOutputUnitStart({:?}) -> {:?}", ci, result);\n    #[cfg(target_os = "ios")]\n    log!("iOS audio diagnostic: AudioOutputUnitStart unit={:?} source={} result={}", ci, source, result);',
        "AudioUnit output start diagnostics",
    )
    replace_once(
        "src/frameworks/audio_toolbox/audio_unit.rs",
        '    let (al_format, _sample_rate, processed_data) =\n        decode_buffer(&env.mem, &stream_format, buffer1Data.cast(), buffer_size);',
        '    let (al_format, _sample_rate, processed_data) =\n        decode_buffer(&env.mem, &stream_format, buffer1Data.cast(), buffer_size);\n    #[cfg(target_os = "ios")]\n    {\n        use std::sync::atomic::{AtomicU64, Ordering};\n        static AUDIO_PCM_LOG_COUNT: AtomicU64 = AtomicU64::new(0);\n        let frame = AUDIO_PCM_LOG_COUNT.fetch_add(1, Ordering::Relaxed) + 1;\n        if frame <= 10 || frame % 120 == 0 {\n            let non_zero = processed_data.iter().filter(|&&sample| sample != 0).count();\n            log!("iOS audio diagnostic: AudioUnit PCM frame={} frames={} sample_rate={} bytes={} non_zero_bytes={} format=0x{:x}",\n                frame, number_frames, sample_rate, processed_data.len(), non_zero, al_format);\n        }\n    }',
        "AudioUnit PCM callback diagnostics",
    )

if __name__ == "__main__":
    main()
