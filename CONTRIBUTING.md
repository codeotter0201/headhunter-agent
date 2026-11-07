# Contributing to headhunter-agent

本指南是 contributor 的日常操作入口，人類與 AI agent 都依同一份規則工作。專案原則與 agent 指令見 [AGENTS.md](AGENTS.md)，共用名詞見 [CONTEXT.md](CONTEXT.md)，產品規格見 [docs/SPEC.md](docs/SPEC.md)。

## 目錄

- [快速開始](#快速開始)
- [與 AI agent 協作](#與-ai-agent-協作)
- [開發工作流](#開發工作流)
- [驗證](#驗證)
- [Issue 規範](#issue-規範)
- [PR 規範](#pr-規範)
- [Release 流程](#release-流程)
- [相關資源](#相關資源)

---

## 快速開始

### 環境需求

| 工具 | 用途 |
|---|---|
| Git | 版本控制 |
| [GitHub CLI](https://cli.github.com) | Issue、PR、label 操作 |
| 支援 `AGENTS.md` 與 Agent Skills 的 AI coding agent | 依 issue 實作 |
| [Claude Code](https://claude.com/claude-code) CLI | 驗證與本機載入外掛 |

### 首次設定

```bash
git clone https://github.com/codeotter0201/headhunter-agent.git
cd headhunter-agent
```

在本機直接載入這個 checkout 的外掛，測試修改中的 skill：

```bash
claude --plugin-dir .
```

開發與測試只使用虛構候選人。資料夾以 `HEADHUNTER_DATA_DIR` 指到 repository 以外的測試位置，不要用你真正的候選人資料：

```bash
export HEADHUNTER_DATA_DIR="$HOME/headhunter-data-dev"
```

---

## 與 AI agent 協作

Issue 是交給 agent 的任務契約。任何 agent 都依以下順序取得上下文：

1. `AGENTS.md`：專案原則、隱私規則、repository 規則
2. `CONTEXT.md`：共用名詞
3. Issue：問題、驗收條件、不在範圍內的項目
4. 本文件對應章節：branch、commit、PR 規則

分工：

- **人類**：撰寫或確認 issue、決定 priority、review PR、決定是否合併。
- **Agent**：在 issue branch 完成最小完整變更、執行驗證、依範本建立 PR，並在 PR 記錄實際執行過的指令與結果。

Agent 的界線：

- Issue 的驗收條件就是完成標準；需求不清楚時在 issue 留言提問，不自行擴大範圍。
- 發現範圍外的問題時另外回報，經同意後開新 issue，不混入目前的 PR。
- 建立 PR 不代表可以合併。合併、刪除 branch、發布版本都需要人類明確要求。

---

## 開發工作流

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

### Branch 命名

```text
<type>/issue-<number>-<slug>
```

`type` 使用 `feat`、`fix`、`refactor`、`perf`、`docs`、`chore` 或 `test`。所有 PR 直接以 `main` 為 base。

```text
feat/issue-12-candidate-crud
fix/issue-34-104-listing-pagination
docs/issue-56-clarify-success-rating
```

### 平行開發

同時處理多個 issue 時，每個 issue 使用自己的 `git worktree`，一個 worktree 對應一個 branch 與一個 PR：

```bash
git fetch origin
git worktree add ../headhunter-agent-issue-12 -b feat/issue-12-candidate-crud origin/main
```

PR 合併後移除 worktree 與本機 branch，再更新本機 `main`。

### Commit message

採用 [Conventional Commits](https://www.conventionalcommits.org/)：

```text
<type>(<scope>): <subject>
```

`type` 使用 `feat`、`fix`、`docs`、`style`、`refactor`、`test`、`chore` 或 `perf`。`scope` 簡短描述實際影響的範圍，通常對應 `area/*` label，例如 `candidate-db`、`ingest`、`job-sources`、`evaluation`、`resume`、`tracking`、`feedback`、`plugin`、`agent-instructions`、`ci`。

```text
feat(job-sources): read CakeResume listing pages
fix(resume): keep glossary names in English resumes
docs(workflow): clarify agent review boundaries
```

變更原因、替代方案與驗證證據放在 commit body、PR 或 issue；current-state 文件不累積歷史敘述。

---

## 驗證

從 repository root 執行受影響的檢查：

| 變更範圍 | 檢查 |
|---|---|
| `.claude-plugin/`、`skills/` | `claude plugin validate .` 與 `claude plugin validate .claude-plugin/plugin.json` |
| Skill 行為 | 以 `claude --plugin-dir .` 載入，用虛構候選人實際走過受影響的流程 |
| JSON / YAML 設定 | 解析檔案確認語法正確 |

PR 中記錄執行過的指令與結果；沒有執行的檢查明確寫出，不宣稱已通過。

---

## Issue 規範

優先使用 repository 的 [Bug Report](.github/ISSUE_TEMPLATE/bug_report.yml) 或 [Feature Request](.github/ISSUE_TEMPLATE/feature_request.yml) form。Issue 描述問題、可驗證的驗收條件、必要證據與明確的不在範圍項目；不要先指定實作方式作為唯一答案。

**Issue 裡不得出現真實候選人的任何個資。** 重現問題時改用虛構人物與虛構資料。

### 標題

```text
[<Type>] <concise description>
```

### Labels

| 類別 | 規則 |
|---|---|
| `type/*` | 每個 issue 恰好一個 |
| `priority/*` | 每個 confirmed issue 恰好一個 |
| `area/*` | 每個 confirmed issue 至少一個 |
| `scope/*` | 需要時加入，例如 `scope/breaking`、`scope/data-schema`、`scope/privacy` |
| `status/*` | 依 lifecycle 更新 |
| `exp/*` | 適合新手或歡迎社群貢獻時加入 |

Issue form 只會自動加入初始 type 與 `status/triage`；triage 時補上 priority 與最終 area。目前完整的 label 清單以 GitHub 為準：

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

## PR 規範

### 標題與內容

PR 標題使用 Conventional Commit 格式：

```text
<type>(<scope>): <description>
```

Breaking change 在 type 或 scope 後加 `!`。PR body 使用 [pull request template](.github/pull_request_template.md)，至少包含 summary、related issue、change type、驗證紀錄與必要文件更新。

開 PR 時，labeler 會依變更路徑加上 `area/*`，並依標題的 type 加上 `type/*`。

### 合併流程

1. 從最新 `origin/main` 建立 `<type>/issue-<number>-<slug>`。
2. 完成最小完整變更與受影響的驗證。
3. PR 以 `main` 為 base，用 `Fixes #<number>` 或 `Closes #<number>` 關聯 issue。
4. 由人類 review。Agent 的自我 review 不取代人類 review。
5. 合併前確認 PR 目前的 head 就是最後驗證過的 commit；有新 commit 就重新驗證。
6. Squash merge 到 `main`，刪除 issue branch。

### Draft PR

追蹤進行中的工作或想先取得回饋時使用 draft PR：

```bash
gh pr create --draft --base main \
  --title "feat(candidate-db): add candidate archive" \
  --body "Refs #12"
gh pr ready
```

---

## Release 流程

版本號以 `.claude-plugin/plugin.json` 的 `version` 為準，採用 [Semantic Versioning](https://semver.org/)。

1. 開一個 release PR，只更新版本號與必要的文件。
2. 合併後，在合併的 commit 上建立 GitHub Release，tag 為 `v<version>`，release notes 列出這個版本的變更。

不要直接 push `main` 或手動建立 tag 來取代 release PR。

---

## 相關資源

| 資源 | 位置 |
|---|---|
| Agent 指令與專案原則 | [AGENTS.md](AGENTS.md) |
| 共用名詞 | [CONTEXT.md](CONTEXT.md) |
| 產品規格 | [docs/SPEC.md](docs/SPEC.md) |
| Skill 指令 | [skills/headhunter/SKILL.md](skills/headhunter/SKILL.md) |
| Issue form 與 PR template | [.github/](.github) |

需要協助時，在相關 issue 或 PR 留下已確認的事實、執行過的指令與尚未解決的阻礙。
