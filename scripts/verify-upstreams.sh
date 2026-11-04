#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "$0")/../config/upstreams.env"
verify_tag() {
  local repo="$1" ref="$2"
  echo "Checking ${repo} @ ${ref}"
  git ls-remote --exit-code --tags "$repo" "refs/tags/${ref}" "refs/tags/${ref}^{}" >/dev/null
}
verify_tag "$HYPERHLE_REPO" "$HYPERHLE_REF"
verify_tag "$TOUCHHLE_REPO" "$TOUCHHLE_REF"
echo "Pinned upstream tags are reachable."
