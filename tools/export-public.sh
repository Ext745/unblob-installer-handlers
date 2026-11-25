#!/usr/bin/env bash
# Export the public copy of this repository (docs/decisions/0007-public-copy.md).
#
# The internal repository is the source of truth. This builds the public
# history from a fresh clone of its main branch and tags:
#   - internal-only paths removed from every commit (INTERNAL below);
#   - identities rewritten by .public-export/mailmap;
#   - strings replaced by .public-export/replace.txt (git filter-repo syntax).
# Both rule files hold personal data, so .public-export/ is gitignored and must
# never be committed. Never edit them for old commits: the export is
# deterministic, and changing a rule changes every hash after the first commit
# it touches, so the next push would no longer fast-forward.
#
# Usage:
#   tools/export-public.sh              build and verify only (default)
#   tools/export-public.sh --push       also push main and tags (fast-forward only)
#   tools/export-public.sh --releases   also copy missing releases and their files
# Needs: git-filter-repo 2.47.0 (pipx install git-filter-repo==2.47.0), gh.
set -euo pipefail

PUBLIC_REPO="Ext745/unblob-installer-handlers"
INTERNAL_REPO="Ext745/unblob-installer-handlers-internal"
INTERNAL=(docs/Method/ docs/Functionality/ testing/ PLAN.md)

push=0; releases=0
for a in "$@"; do
  case "$a" in
    --push) push=1 ;;
    --releases) releases=1 ;;
    *) echo "usage: $0 [--push] [--releases]" >&2; exit 2 ;;
  esac
done

root=$(git rev-parse --show-toplevel)
rules="$root/.public-export"
for f in mailmap replace.txt; do
  [[ -s "$rules/$f" ]] || { echo "export: missing $rules/$f" >&2; exit 2; }
done
git -C "$root" check-ignore -q "$rules/mailmap" || { echo "export: .public-export/ is not gitignored" >&2; exit 2; }
command -v git-filter-repo >/dev/null || { echo "export: git-filter-repo not on PATH" >&2; exit 2; }

work="${PUBLIC_EXPORT_DIR:-$HOME/.cache/unblob-installer-handlers/public-export}"
rm -rf "$work"; mkdir -p "$(dirname "$work")"
git clone -q --no-local --single-branch --branch main "$root" "$work"
git -C "$work" fetch -q origin 'refs/tags/*:refs/tags/*'
git -C "$work" remote remove origin

paths=$(mktemp); trap 'rm -f "$paths"' EXIT
printf '%s\n' "${INTERNAL[@]}" > "$paths"
(cd "$work" && git-filter-repo --force --quiet --invert-paths --paths-from-file "$paths" \
    --mailmap "$rules/mailmap" --replace-text "$rules/replace.txt")

# Verify: no old identity, no replaced string, no internal path, anywhere.
fail=0
olds=$(sed -nE 's/.*<[^>]+>.*<([^>]+)>.*/\1/p' "$rules/mailmap")
needles=$(sed -nE 's/^(regex:|literal:)?(\(\?i\))?([^=]+)==>.*/\3/p' "$rules/replace.txt")
dump=$(git -C "$work" cat-file --batch-all-objects --batch | tr -d '\0')
while IFS= read -r n; do
  [[ -z "$n" ]] && continue
  if grep -qiF -- "$n" <<<"$dump"; then echo "export: FAIL, a rewritten string is still present" >&2; fail=1; fi
done <<<"$olds"$'\n'"$needles"
for p in "${INTERNAL[@]}"; do
  if [[ -n $(git -C "$work" log --all --format=%H -- "$p" | head -1) ]]; then
    echo "export: FAIL, $p still in history" >&2; fail=1
  fi
done
((fail == 0)) || exit 1
echo "export: $(git -C "$work" rev-list --count main) commits, tags: $(git -C "$work" tag | tr '\n' ' ')"
echo "export: verified, in $work"

if ((push)); then
  git -C "$work" remote add public "git@github.com:$PUBLIC_REPO.git"  # scrub:allow SSH remote, not an address
  git -C "$work" push public main        # refused unless it fast-forwards
  git -C "$work" push public --tags
fi

if ((releases)); then
  have=$(gh release list -R "$PUBLIC_REPO" --limit 200 --json tagName -q '.[].tagName')
  # Oldest first, so the newest release ends up marked "latest".
  for tag in $(gh release list -R "$INTERNAL_REPO" --limit 200 --json tagName -q '.[].tagName' | tac); do
    grep -qxF "$tag" <<<"$have" && continue
    d="$work/release-$tag"; mkdir -p "$d"
    gh release download "$tag" -R "$INTERNAL_REPO" -D "$d"
    title=$(gh release view "$tag" -R "$INTERNAL_REPO" --json name -q .name)
    gh release view "$tag" -R "$INTERNAL_REPO" --json body -q .body > "$d.notes"
    gh release create "$tag" -R "$PUBLIC_REPO" --verify-tag --title "$title" \
       --notes-file "$d.notes" "$d"/*
    (cd "$d" && sha256sum ./*)
  done
fi
