# Contributing to headhunter-agent

This guide is the day-to-day entry point for contributors. Humans and AI agents follow the same rules. Project principles and agent instructions are in [AGENTS.md](AGENTS.md), and shared terms are in [CONTEXT.md](CONTEXT.md).

## Contents

- [Getting started](#getting-started)
- [Working with AI agents](#working-with-ai-agents)
- [Development workflow](#development-workflow)
- [Validation](#validation)
- [Issues](#issues)
- [Pull requests](#pull-requests)
- [Releases](#releases)
- [Resources](#resources)

---

## Getting started

### Requirements

| Tool | Purpose |
|---|---|
| Git | Version control |
| [GitHub CLI](https://cli.github.com) | Issues, pull requests and labels |
| An AI coding agent that supports `AGENTS.md` and Agent Skills | Implementing issues |
| [Claude Code](https://claude.com/claude-code) CLI | Validating and loading the plugin locally |

### First-time setup

```bash
git clone https://github.com/codeotter0201/headhunter-agent.git
cd headhunter-agent
```

Load the plugin from this checkout to test a skill you are changing:

```bash
claude --plugin-dir .
```

Develop and test with fictional Candidates only. Point `HEADHUNTER_DATA_DIR` at a test location outside the repository, never at your real Candidate data:

```bash
export HEADHUNTER_DATA_DIR="$HOME/headhunter-data-dev"
```

### Language

Write repository files, issues, pull requests and commit messages in English. `README.zh-TW.md` is the only Traditional Chinese file; keep it in step with `README.md`.

---

## Working with AI agents

An issue is the task contract handed to an agent. Every agent builds its context in this order:

1. `AGENTS.md`: project principles, privacy rules, repository rules
2. `CONTEXT.md`: shared terms
3. The issue: problem, acceptance criteria, out-of-scope items
4. The matching section of this guide: branch, commit and pull request rules

Roles:

- **Humans** write or confirm issues, set priority, review pull requests, and decide whether to merge.
- **Agents** make the smallest complete change on the issue branch, run validation, open a pull request from the template, and record in it the commands they ran and the results.

Agent boundaries:

- The issue's acceptance criteria define done. When requirements are unclear, ask in the issue instead of widening the scope.
- Report problems outside the scope separately; open a new issue only after agreement, and keep them out of the current pull request.
- Opening a pull request does not authorize merging. Merging, deleting branches and releasing require an explicit human request.

---

## Development workflow

```text
Issue triage and confirmation
  → branch from latest origin/main
  → smallest complete change
  → local validation
  → PR to main
  → review
  → squash merge
  → delete branch, refresh local main
```

### Branch names

```text
<type>/issue-<number>-<slug>
```

`type` is one of `feat`, `fix`, `refactor`, `perf`, `docs`, `chore` or `test`. Every pull request targets `main`.

```text
feat/issue-12-candidate-crud
fix/issue-34-104-listing-pagination
docs/issue-56-clarify-success-rating
```

### Parallel work

When working on several issues at once, give each issue its own `git worktree`: one worktree, one branch, one pull request.

```bash
git fetch origin
git worktree add ../headhunter-agent-issue-12 -b feat/issue-12-candidate-crud origin/main
```

After the pull request is merged, remove the worktree and the local branch, then update local `main`.

### Commit messages

Use [Conventional Commits](https://www.conventionalcommits.org/):

```text
<type>(<scope>): <subject>
```

`type` is one of `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore` or `perf`. `scope` names the area actually affected, usually matching an `area/*` label: `candidate-db`, `ingest`, `job-sources`, `evaluation`, `resume`, `tracking`, `feedback`, `plugin`, `agent-instructions`, `docs`, `ci`, or `workflow`.

```text
feat(job-sources): read CakeResume listing pages
fix(resume): keep glossary names in English resumes
docs(workflow): clarify agent review boundaries
```

Reasons, alternatives and validation evidence go in the commit body, pull request or issue. Current-state files do not accumulate history.

---

## Validation

Run the checks for what you changed, from the repository root:

| Change | Check |
|---|---|
| `.claude-plugin/`, `skills/` | `claude plugin validate .` and `claude plugin validate .claude-plugin/plugin.json` |
| Skill behavior | Load with `claude --plugin-dir .` and walk through the affected flow with fictional Candidates |
| JSON / YAML files | Parse the file to confirm the syntax |

`claude plugin validate .claude-plugin/plugin.json` warns that `CLAUDE.md` at the plugin root is not loaded as plugin context. This is expected: `CLAUDE.md` is for agents working on this repository, not for plugin users.

Record the commands you ran and their results in the pull request. State any check you did not run; never claim it passed.

---

## Issues

### Specifications live in issues

Planned features and their specifications live in issues, not in repository files. The roadmap is an epic issue (`type/epic`) with one sub-issue per phase. To change a plan, edit its issue; the labels and sub-issue links keep it traceable.

When a change lands, the behavior it delivers is described in `skills/headhunter/SKILL.md` and the READMEs, and the issue is closed.

### Writing an issue

Use the [Bug Report](.github/ISSUE_TEMPLATE/bug_report.yml) or [Feature Request](.github/ISSUE_TEMPLATE/feature_request.yml) form. Describe the problem, verifiable acceptance criteria, the evidence needed, and what is out of scope. Do not prescribe one implementation as the only answer.

**Never include a real Candidate's personal data in an issue.** Reproduce problems with fictional people and fictional data.

### Title

```text
[<Type>] <concise description>
```

### Labels

| Family | Rule |
|---|---|
| `type/*` | Exactly one per issue |
| `priority/*` | Exactly one per confirmed issue |
| `area/*` | At least one per confirmed issue |
| `scope/*` | Add when relevant, such as `scope/breaking`, `scope/data-schema`, `scope/privacy` |
| `status/*` | Updated through the lifecycle |
| `exp/*` | Add when the issue suits newcomers or community contributions |

Issue forms add only the initial type and `status/triage`; triage adds the priority and final areas. GitHub holds the current label list:

```bash
gh label list
```

### Lifecycle

```text
status/triage
  → status/needs-info or status/confirmed
  → status/in-progress or status/blocked
  → closed, status/deferred, or status/wontfix
```

---

## Pull requests

### Title and body

Pull request titles use the Conventional Commit format:

```text
<type>(<scope>): <description>
```

Add `!` after the type or scope for a breaking change. The body follows the [pull request template](.github/pull_request_template.md) and includes at least the summary, related issue, change type, validation record and documentation updates.

When a pull request is opened, the labeler adds `area/*` labels from the changed paths and a `type/*` label from the title.

### Merging

1. Branch `<type>/issue-<number>-<slug>` from the latest `origin/main`.
2. Make the smallest complete change and run the affected validation.
3. Target `main` and link the issue with `Fixes #<number>` or `Closes #<number>`.
4. A human reviews. An agent's self-review does not replace human review.
5. Before merging, confirm the pull request head is the last validated commit; any new commit needs validating again.
6. Squash merge into `main` and delete the issue branch.

### Draft pull requests

Use a draft pull request to track work in progress or get early feedback:

```bash
gh pr create --draft --base main \
  --title "feat(candidate-db): add candidate archive" \
  --body "Refs #12"
gh pr ready
```

---

## Releases

The version is the `version` field in `.claude-plugin/plugin.json`, following [Semantic Versioning](https://semver.org/).

1. Open a release pull request that changes only the version and the necessary documentation.
2. After it is merged, create a GitHub Release on the merge commit with the tag `v<version>`, and list the changes in the release notes.

Do not push to `main` directly or create tags by hand in place of a release pull request.

---

## Resources

| Resource | Location |
|---|---|
| Agent instructions and principles | [AGENTS.md](AGENTS.md) |
| Shared terms | [CONTEXT.md](CONTEXT.md) |
| Skill behavior and data layout | [skills/headhunter/SKILL.md](skills/headhunter/SKILL.md) |
| Roadmap | [Epic issues](https://github.com/codeotter0201/headhunter-agent/issues?q=label%3Atype%2Fepic) |
| Issue forms and pull request template | [.github/](.github) |

When you need help, leave the confirmed facts, the commands you ran and the remaining blockers in the relevant issue or pull request.
