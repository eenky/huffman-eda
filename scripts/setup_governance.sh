#!/usr/bin/env bash
# One-time setup for the two-agent governance model (see AGENTS.md "Roles").
# Run as the repository OWNER with the GitHub CLI authenticated as the owner.
#
#   AUTHOR_LOGIN=hfe-author-bot REVIEWER_LOGIN=hfe-reviewer-bot ./scripts/setup_governance.sh
#
# Before running: create the two bot accounts (normal GitHub accounts), then sign in as each
# one afterwards to accept the collaborator invitation this script sends.
set -euo pipefail

: "${AUTHOR_LOGIN:?set AUTHOR_LOGIN}"
: "${REVIEWER_LOGIN:?set REVIEWER_LOGIN}"
REPO="${REPO:-$(gh repo view --json nameWithOwner -q .nameWithOwner)}"
OWNER_LOGIN="${OWNER_LOGIN:-$(gh api user -q .login)}"

[ "$AUTHOR_LOGIN" != "$REVIEWER_LOGIN" ] || { echo "author and reviewer must differ"; exit 1; }
[ "$OWNER_LOGIN" != "$AUTHOR_LOGIN" ] && [ "$OWNER_LOGIN" != "$REVIEWER_LOGIN" ] \
  || { echo "bots must not be the owner account"; exit 1; }

echo "== repository variables"
gh variable set OWNER_LOGIN    --body "$OWNER_LOGIN"    -R "$REPO"
gh variable set AUTHOR_LOGIN   --body "$AUTHOR_LOGIN"   -R "$REPO"
gh variable set REVIEWER_LOGIN --body "$REVIEWER_LOGIN" -R "$REPO"

echo "== collaborators (write access; accept the invitations as each bot)"
gh api -X PUT "repos/$REPO/collaborators/$AUTHOR_LOGIN"   -f permission=push >/dev/null
gh api -X PUT "repos/$REPO/collaborators/$REVIEWER_LOGIN" -f permission=push >/dev/null

echo "== labels"
gh label create owner-approved --color B60205 -R "$REPO" --force \
  --description "Owner allows a change to frozen ground truth (policy checks who applied it)"
gh label delete spec-approved -R "$REPO" --yes 2>/dev/null || true

echo "== auto-merge"
gh repo edit "$REPO" --enable-auto-merge --delete-branch-on-merge

echo "== ruleset on the default branch"
gh api -X POST "repos/$REPO/rulesets" --input - >/dev/null <<JSON
{
  "name": "main-two-agent",
  "target": "branch",
  "enforcement": "active",
  "conditions": {"ref_name": {"include": ["~DEFAULT_BRANCH"], "exclude": []}},
  "bypass_actors": [{"actor_id": 5, "actor_type": "RepositoryRole", "bypass_mode": "always"}],
  "rules": [
    {"type": "deletion"},
    {"type": "non_fast_forward"},
    {"type": "pull_request", "parameters": {
      "required_approving_review_count": 1,
      "dismiss_stale_reviews_on_push": true,
      "require_code_owner_review": false,
      "require_last_push_approval": true,
      "required_review_thread_resolution": true}},
    {"type": "required_status_checks", "parameters": {
      "strict_required_status_checks_policy": true,
      "required_status_checks": [{"context": "test"}, {"context": "spec-policy"}]}}
  ]
}
JSON

cat <<MSG

Done for $REPO.
  owner:    $OWNER_LOGIN  (admin; bypasses the ruleset; only needed for owner-approved and governance)
  author:   $AUTHOR_LOGIN
  reviewer: $REVIEWER_LOGIN
Next: accept both invitations, then give each Hermes profile its own bot token
(e.g. a fine-grained PAT scoped to this repo: Contents, Pull requests, Issues = read/write).
MSG
