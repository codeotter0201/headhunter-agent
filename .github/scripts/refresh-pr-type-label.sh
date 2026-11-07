#!/usr/bin/env bash

set -euo pipefail

if [[ $# -ne 1 || -z "${GH_TOKEN:-}" || -z "${GITHUB_REPOSITORY:-}" ]]; then
  echo "usage: GH_TOKEN=... GITHUB_REPOSITORY=owner/repo $0 PR_NUMBER" >&2
  exit 2
fi

pr_number="$1"
pr_json=$(gh api "repos/$GITHUB_REPOSITORY/pulls/$pr_number")
title=$(jq -r '.title' <<<"$pr_json")
prefix=$(sed -E 's/^([[:alnum:]_-]+)(\([^)]*\))?!?:.*/\1/' <<<"$title" | tr '[:upper:]' '[:lower:]')

case "$prefix" in
  feat | feature) desired="type/feature" ;;
  fix | bug) desired="type/bug" ;;
  docs) desired="type/docs" ;;
  refactor) desired="type/refactor" ;;
  perf) desired="type/perf" ;;
  build | chore | ci | test) desired="type/chore" ;;
  *)
    echo "No recognized Conventional Commit type in PR title; preserving manual type labels."
    exit 0
    ;;
esac

type_labels=(
  type/bug type/chore type/docs type/enhancement type/epic type/feature type/perf type/refactor
)
for label in "${type_labels[@]}"; do
  if [[ "$label" != "$desired" ]] && jq -e --arg label "$label" \
    '.labels[]? | select(.name == $label)' <<<"$pr_json" >/dev/null; then
    encoded=$(jq -rn --arg label "$label" '$label | @uri')
    gh api --silent --method DELETE \
      "repos/$GITHUB_REPOSITORY/issues/$pr_number/labels/$encoded"
  fi
done

if ! jq -e --arg label "$desired" \
  '.labels[]? | select(.name == $label)' <<<"$pr_json" >/dev/null; then
  jq -n --arg label "$desired" '{labels: [$label]}' | \
    gh api --silent --method POST \
      "repos/$GITHUB_REPOSITORY/issues/$pr_number/labels" --input -
fi

echo "PR #$pr_number type label: $desired"
