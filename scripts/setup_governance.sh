#!/usr/bin/env bash
# One-time setup for the two-agent model using two GitHub Apps (no extra accounts).
# Run as the repository OWNER with `gh` authenticated as you.
#
# Before running, create two GitHub Apps under your account
# (Settings -> Developer settings -> GitHub Apps -> New GitHub App). For each one: give it
# any homepage URL, untick "Webhook: Active", and choose "Only on this account".
#
#   hfe-author   Repository permissions:
#                  Contents: Read & write, Pull requests: Read & write,
#                  Issues: Read & write, Metadata: Read.
#                  Leave Workflows, Commit statuses and Administration at "No access".
#   hfe-reviewer Repository permissions:
#                  Contents: Read & write, Pull requests: Read & write,
#                  Issues: Read & write, Commit statuses: Read & write, Metadata: Read.
#                  Leave Workflows and Administration at "No access".
#
# For each app: "Install App" on eenky/huffman-eda only, then "Generate a private key"
# (.pem). Note each app's App ID and slug (the URL name). Then run:
#
#   AUTHOR_APP_SLUG=hfe-author REVIEWER_APP_SLUG=hfe-reviewer REVIEWER_APP_ID=123456 \
#     ./scripts/setup_governance.sh
set -euo pipefail

: "${AUTHOR_APP_SLUG:?set AUTHOR_APP_SLUG}"
: "${REVIEWER_APP_SLUG:?set REVIEWER_APP_SLUG}"
: "${REVIEWER_APP_ID:?set REVIEWER_APP_ID}"
REPO="${REPO:-$(gh repo view --json nameWithOwner -q .nameWithOwner)}"
OWNER_LOGIN="${OWNER_LOGIN:-$(gh api user -q .login)}"
ACTIONS_APP_ID=15368   # GitHub Actions; binds `test` and `spec-policy` to real workflow runs

[ "$AUTHOR_APP_SLUG" != "$REVIEWER_APP_SLUG" ] || { echo "apps must differ"; exit 1; }

echo "== repository variables"
gh variable set OWNER_LOGIN    --body "$OWNER_LOGIN"              -R "$REPO"
gh variable set AUTHOR_LOGIN   --body "${AUTHOR_APP_SLUG}[bot]"   -R "$REPO"
gh variable set REVIEWER_LOGIN --body "${REVIEWER_APP_SLUG}[bot]" -R "$REPO"

echo "== labels"
gh label create owner-approved --color B60205 -R "$REPO" --force \
  --description "Owner allows a change to frozen ground truth (policy checks who applied it)"
gh label create peer-reviewed --color 0E8A16 -R "$REPO" --force \
  --description "Re-runs spec-policy after the author app approves a reviewer PR"
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
      "required_approving_review_count": 0,
      "dismiss_stale_reviews_on_push": true,
      "require_code_owner_review": false,
      "require_last_push_approval": false,
      "required_review_thread_resolution": true}},
    {"type": "required_status_checks", "parameters": {
      "strict_required_status_checks_policy": true,
      "required_status_checks": [
        {"context": "test", "integration_id": $ACTIONS_APP_ID},
        {"context": "spec-policy", "integration_id": $ACTIONS_APP_ID},
        {"context": "reviewer-verdict", "integration_id": $REVIEWER_APP_ID}
      ]}}
  ]
}
JSON

cat <<MSG

Done for $REPO.
  owner:    $OWNER_LOGIN (admin; bypasses the ruleset; needed only for owner-approved and governance)
  author:   ${AUTHOR_APP_SLUG}[bot]
  reviewer: ${REVIEWER_APP_SLUG}[bot]  (only this app can satisfy reviewer-verdict)

Hermes: give each profile only its own key, and remove your personal GitHub login from both:
  author profile:   export GH_TOKEN=\$(APP_ID=<author id>   APP_KEY=<author.pem>   scripts/app_token.sh $REPO)
  reviewer profile: export GH_TOKEN=\$(APP_ID=$REVIEWER_APP_ID APP_KEY=<reviewer.pem> scripts/app_token.sh $REPO)
Tokens last 1 hour; mint a new one per session.
MSG
