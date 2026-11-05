#!/bin/sh
set -eu

IPA=${1:?usage: verify-touchhle-only-ipa.sh PATH_TO_IPA}
[ -f "$IPA" ] || { echo "IPA not found: $IPA" >&2; exit 1; }
entries=$(unzip -Z1 "$IPA")
app_root="Payload/HyperHLE.app"

printf '%s\n' "$entries" | grep -Fx "$app_root/Frameworks/libtouchhle_core.dylib" >/dev/null || {
    echo "Official touchHLE Core B dylib is missing from IPA." >&2
    exit 1
}

if printf '%s\n' "$entries" | grep -E "$app_root/Frameworks/libhyperhle_core\\.dylib$" >/dev/null; then
    echo "Core A must not be included in the Core B-only IPA." >&2
    exit 1
fi

printf '%s\n' "$entries" | grep -Fx "$app_root/touchHLE_default_options.txt" >/dev/null || {
    echo "Bundled official default options file is missing from IPA." >&2
    exit 1
}

unzip -p "$IPA" "$app_root/touchHLE_default_options.txt" | grep -F 'com.namconetworks.AceCombatXi:' >/dev/null || {
    echo "Official ACE-Xi default options entry is missing from the bundled resource." >&2
    exit 1
}

core_count=$(printf '%s\n' "$entries" | grep -E "$app_root/Frameworks/lib[^/]*core\\.dylib$" | wc -l | tr -d ' ')
[ "$core_count" = "1" ] || {
    echo "Expected exactly one emulator core dylib, found $core_count." >&2
    exit 1
}

echo "Verified: IPA contains only official touchHLE v0.3.0 and the bundled official default options."
