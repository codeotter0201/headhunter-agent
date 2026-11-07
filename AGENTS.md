# AGENTS.md

headhunter-agent is an AI headhunter packaged as an agent skill. It keeps a local
database of many candidates, reads job boards, scores jobs against candidates,
writes tailored bilingual resumes, and tracks every application with feedback.
This repository holds the skill, its plugin packaging, and its specification.

This file is the single instruction source for every AI agent working in this
repository, whatever tool or model runs it.

## Project Constitution

- **Ownership:** Treat the active checkout, branch, and existing work as
  user-owned task context. Preserve unrelated state. Repository topology changes
  require explicit user intent.
- **Scope:** Deliver the smallest complete change required by the issue or
  request. Analysis and review are read-only unless implementation is requested.
  Report unrelated cleanup and adjacent problems separately, as new issues when
  asked.
- **Truth:** Treat current files and canonical documentation as the source of
  truth. Verify repository facts before relying on assumptions. Record history in
  commits, pull requests, issues, and GitHub Releases, never in current-state
  documents.
- **Current source:** Documents, skill instructions, and code describe only
  current behavior. Do not add issue or PR narration, retired names, or "old /
  new" comparisons.
- **Evolution:** Evolve existing files in place. Parallel, versioned, or
  replacement implementations are architectural decisions that require explicit
  user intent. Remove superseded content within the requested scope.
- **Design:** Reuse existing structure, naming, and patterns before introducing
  new ones. Design for the current requirement, not speculative future use.
- **Evidence:** Do not weaken validation to make a change pass. Verify changed
  behavior with the narrowest relevant check before reporting completion, and
  report checks that were not run.

## Agent-Neutral Collaboration

- `AGENTS.md` is the canonical instruction file. `CLAUDE.md` and
  `.gemini/settings.json` only point agents to it. Never put project rules in a
  tool-specific file or maintain a second copy.
- Write instructions in plain task terms: read a file, search, run a command.
  Do not depend on one tool's command names, model names, or invocation syntax in
  shared content.
- Skills use the open Agent Skills format: a folder with a `SKILL.md` that starts
  with `name` and `description` frontmatter.
- Shared domain terms are defined in `CONTEXT.md`. Use those terms in issues,
  pull requests, documents, and skill instructions.

## Language

- Write all repository files, issues, pull requests, and commit messages in
  English.
- `README.zh-TW.md` is the only Traditional Chinese file. It carries the same
  content as `README.md`, and each links to the other at the top.

## Where Information Lives

- Planned features and their specifications live in labeled issues: the
  roadmap epic and its phase issues. Iterate on a plan by updating its issue.
- Repository files hold only stable, current information, each in one place:

| Information | Owner |
|---|---|
| Agent rules | `AGENTS.md` |
| Domain terms | `CONTEXT.md` |
| Issue, branch, commit, pull request and release workflow | `CONTRIBUTING.md` |
| Current skill behavior and data layout | `skills/headhunter/SKILL.md` |
| Product overview and installation | `README.md`, `README.zh-TW.md` |

- Do not add a documentation folder or a second copy of any of these.

## Privacy Invariants

- Candidate data lives only in the user's data folder (`$HEADHUNTER_DATA_DIR`,
  default `~/headhunter-data/`). It never enters this repository.
- Examples, fixtures, screenshots, issues, and pull requests use fictional people
  only. Never paste real names, contact details, resumes, or feedback about a real
  person.
- The skill never sends candidate data to a third-party service.

## Repository Invariants

- The development unit is one issue / branch / pull request. Branches start from
  the latest `origin/main`, are named `<type>/issue-<number>-<slug>`, and target
  `main`.
- A change to product behavior or data layout updates
  `skills/headhunter/SKILL.md`, `README.md`, and `README.zh-TW.md` in the same
  pull request.
- A change to the data layout states how existing data folders are migrated.
- The plugin version in `.claude-plugin/plugin.json` changes only in a release
  pull request.

## Layout

```
AGENTS.md                     canonical agent instructions (this file)
CLAUDE.md                     imports AGENTS.md
CONTEXT.md                    shared domain terms
CONTRIBUTING.md               issue, branch, commit, pull request and release rules
README.md                     product overview (English)
README.zh-TW.md               product overview (Traditional Chinese)
skills/headhunter/SKILL.md    the headhunter skill: current behavior and data layout
.claude-plugin/               plugin and marketplace manifests
.github/                      issue forms, PR template, labeler
.gemini/settings.json         points Gemini CLI to AGENTS.md
```

## Navigation

- When creating or changing an issue, branch, commit, or pull request, read the
  matching section of `CONTRIBUTING.md` and the forms in `.github/`.
- When changing what the skill does or how data is stored, read the issue that
  specifies the change and `skills/headhunter/SKILL.md` first.
- When changing plugin packaging, run `claude plugin validate .` and
  `claude plugin validate .claude-plugin/plugin.json` from the repository root.
