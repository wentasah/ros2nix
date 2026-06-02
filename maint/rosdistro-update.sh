#!/usr/bin/env bash

set -euo pipefail

pr_body=${1:-/tmp/.body}

filter_nixos() {
    yq 'with_entries(select(.value.nixos != null) | .value = .value.nixos)' "$1"/rosdep/{base,python,ruby}.yaml
}

nix build .#rosdistro --out-link /tmp/rosdistro-old
nix flake update rosdistro
nix build .#rosdistro --out-link /tmp/rosdistro-new
filter_nixos /tmp/rosdistro-old > /tmp/rosdistro-old.txt
filter_nixos /tmp/rosdistro-new > /tmp/rosdistro-new.txt
git reset --hard
if ! git diff -U0 /tmp/rosdistro-old.txt /tmp/rosdistro-new.txt > /tmp/rosdistro-diff; then
    # redo update with nice commit message
    nix flake update rosdistro --commit-lock-file
    GIT_EDITOR='sed -i -e "1crosdistro update"' git commit --amend
    GIT_EDITOR='sed -i -e "\$r/tmp/rosdistro-diff"' git commit --amend
    cat <<EOF > "$pr_body"
Diff:
\`\`\`diff
$(cat /tmp/rosdistro-diff)
\`\`\`
EOF
else
    echo "No relevant changes"
    touch "$pr_body" # prevent create-pull-request action from failing
fi
