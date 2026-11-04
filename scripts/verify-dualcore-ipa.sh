#!/bin/sh
set -eu

IPA=${1:?usage: verify-dualcore-ipa.sh PATH_TO_DUALCORE_IPA}
command -v unzip >/dev/null 2>&1 || { echo "unzip is required" >&2; exit 1; }
[ -f "$IPA" ] || { echo "IPA not found: $IPA" >&2; exit 1; }

entries=$(unzip -Z1 "$IPA")
for dylib in libhyperhle_core.dylib libtouchhle_core.dylib; do
    entry="Payload/HyperHLE.app/Frameworks/$dylib"
    printf '%s\n' "$entries" | grep -Fx "$entry" >/dev/null || {
        echo "Required core missing from IPA: $entry" >&2
        exit 1
    }
done

printf '%s\n' "$entries" | grep -E 'Payload/HyperHLE\.app/Frameworks/lib[^/]*core\.dylib$'
echo "Verified dual-core IPA contains exactly the expected HyperHLE and touchHLE core libraries."
