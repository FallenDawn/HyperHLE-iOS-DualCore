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
    paths.write_text(ptext)
    print("patched: iOS bundle resources, Documents data path and core-specific options")

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

if __name__ == "__main__":
    main()
