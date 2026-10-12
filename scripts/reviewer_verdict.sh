#!/usr/bin/env bash
# Reviewer agent only: record the verdict on a PR's current head commit.
# The ruleset accepts the `reviewer-verdict` check only from the reviewer app, so this
# works only with a token minted from the reviewer app's key. A new push to the PR creates a
# new head commit with no verdict, so every push needs a fresh review.
#
#   GH_TOKEN=<reviewer app token> scripts/reviewer_verdict.sh 57 approve "reference reproduces all 4 new cases"
#   GH_TOKEN=<reviewer app token> scripts/reviewer_verdict.sh 57 reject  "§9.2 closure condition ambiguous; see review"
set -euo pipefail
PR="${1:?PR number}"; VERDICT="${2:?approve|reject}"; NOTE="${3:?one-line reason}"
REPO="${REPO:-$(gh repo view --json nameWithOwner -q .nameWithOwner)}"
case "$VERDICT" in approve) state=success ;; reject) state=failure ;; *) echo "approve|reject"; exit 2 ;; esac
sha=$(gh pr view "$PR" -R "$REPO" --json headRefOid -q .headRefOid)
gh api -X POST "repos/$REPO/statuses/$sha" -f state="$state" -f context=reviewer-verdict \
  -f description="${NOTE:0:140}" >/dev/null
gh pr comment "$PR" -R "$REPO" --body "**reviewer-verdict: $VERDICT** on \`${sha:0:7}\`

$NOTE"
echo "reviewer-verdict=$state on $sha"
