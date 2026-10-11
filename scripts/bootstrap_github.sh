#!/usr/bin/env bash
# Create the private GitHub repo, push the initial commit, and set up labels
# (and optionally issues). Requires the GitHub CLI (`gh`), already authenticated.
#
#   OWNER=eenky REPO=huffman-eda ./scripts/bootstrap_github.sh
#   CREATE_ISSUES=1 ./scripts/bootstrap_github.sh   # also open one issue per task
set -euo pipefail

OWNER="${OWNER:-eenky}"
REPO="${REPO:-huffman-eda}"
FULL="$OWNER/$REPO"

command -v gh >/dev/null || { echo "Install the GitHub CLI: https://cli.github.com"; exit 1; }
gh auth status >/dev/null

cd "$(dirname "$0")/.."

if [ ! -d .git ]; then
  git init -b main
  git add -A
  git commit -m "chore(T000): bootstrap repository (scaffold, CI, AGENTS, SEMANTICS §1-7, golden)"
fi

if gh repo view "$FULL" >/dev/null 2>&1; then
  echo "Repo $FULL already exists; adding remote and pushing."
  git remote get-url origin >/dev/null 2>&1 || git remote add origin "https://github.com/$FULL.git"
  git push -u origin main
else
  gh repo create "$FULL" --private --source . --remote origin --push \
    --description "Verification-first toolkit for Huffman-model asynchronous circuits"
fi

label() { gh label create "$1" --color "$2" --description "$3" -R "$FULL" --force >/dev/null; }
label spec-approved  B60205 "Owner-approved change to protected spec/golden paths"
label spec-question  FBCA04 "Agent believes the spec or golden data is wrong or ambiguous"
label task           0E8A16 "One task file = one PR"
label owner-task     5319E7 "Spec task owned by the repository owner"
for m in M1 M2 M3 M4 M5 M6 M7 M8; do label "$m" C5DEF5 "Milestone $m"; done

if [ "${CREATE_ISSUES:-0}" = "1" ]; then
  for f in tasks/M*/T*.md; do
    title=$(head -n1 "$f" | sed 's/^# //')
    milestone=$(basename "$(dirname "$f")" | cut -d- -f1)
    kind=task
    grep -q '^\*\*Owner:\*\* owner' "$f" && kind=owner-task
    gh issue create -R "$FULL" --title "$title" --body-file "$f" \
      --label "$kind" --label "$milestone" >/dev/null
    echo "issue: $title"
  done
fi

cat <<MSG

Done: https://github.com/$FULL

Recommended next steps (Settings -> Branches / Rules on GitHub):
  - Protect 'main': require PRs, require the 'test' and 'protected-paths' checks,
    and require Code Owner review.
  - Note: enforced branch protection on PRIVATE repos needs GitHub Pro/Team.
    Without it the CI checks still run and show red; you just merge manually.
MSG
