# headhunter-agent

**An AI headhunter agent for Claude Code.** It keeps a database of your candidates, reads job boards, scores each job against each candidate, writes tailored bilingual resumes, and tracks every application with feedback.

**給 Claude Code 用的 AI 獵頭。** 建立候選人資料庫、讀取職缺網站、評估適合度與成功率、產出中英雙版客製履歷，並追蹤每一次投遞的進度與回饋。

> **Status:** in development. The specification is complete; features are being built phase by phase. See [docs/SPEC.md](docs/SPEC.md).
>
> **狀態：** 開發中。規格已定案，功能依階段實作中，詳見 [docs/SPEC.md](docs/SPEC.md)。

---

## Why

Most job-search tools serve one job seeker. Headhunters and career coaches work for **many candidates at once**, and need to remember everything about each of them: their history, every job they were matched with, how each application went, and what to fix next time. `headhunter-agent` is built for that.

## Features

- **Candidate database** — Import notes, work logs, photos, existing resumes and GitHub repos. Every fact keeps a link to its source. Create, read, update and archive candidates; search them by role, industry, seniority, skills or status.
- **Job board reading** — Paste a listing URL from 104, CakeResume, Yourator, a company careers page or LinkedIn. It reads the listing, screens the titles, then reads each job in full.
- **Fit and success scoring** — For one candidate, or across your whole database: a fit score, the reasons for the recommendation, gaps and risks, and a high / medium / low success rating with its reasoning.
- **Tailored resumes** — A Chinese and an English resume for each job, in Markdown and PDF, built only from facts with a source.
- **Application tracking** — Every candidate × job pair moves through stages (found → evaluated → preparing → applied → interview rounds → offer → closed), with a next step and a due date.
- **Feedback loop** — Log feedback from HR, interviewers, the candidate and yourself, with a cause and a concrete fix. Recurring problems update the candidate's strategy; feedback about the same company builds up into company notes; results calibrate the scoring.

## Install

```
/plugin marketplace add codeotter0201/headhunter-agent
/plugin install headhunter@headhunter-agent
```

Then run `/headhunter` in Claude Code.

## Your data stays local

Candidate data never goes into this repository. It lives in `~/headhunter-data/` on your machine (or the folder set in `HEADHUNTER_DATA_DIR`) and is not sent to any third-party service.

---

## 中文說明

### 為什麼需要它

多數求職工具只服務一位求職者。獵頭和職涯顧問同時替**很多位候選人**操作，需要記住每個人的經歷、配對過的每個職缺、每次投遞的結果，以及下次要修正什麼。`headhunter-agent` 就是為這種工作方式設計的。

### 功能

- **候選人資料庫**：匯入筆記、工作紀錄、照片、舊履歷和 GitHub repo，每一條事實都保留出處。支援新增、查看、更新、封存，可依職能、產業、年資、技能、狀態查詢。
- **讀取職缺網站**：貼上 104、CakeResume、Yourator、企業官網或 LinkedIn 的職缺列表網址，先讀標題粗篩，再逐一讀取完整職缺內容。
- **適合度與成功率評估**：可針對一位候選人，或從整個資料庫找出適合的人。產出適合度分數、推薦原因、缺口與風險，以及高／中／低的成功率等級與理由。
- **客製履歷**：每個職缺產出中文與英文兩版，Markdown 與 PDF 格式，只使用有出處的事實。
- **投遞進度追蹤**：每組「候選人 × 職缺」依階段推進（發現 → 已評估 → 準備中 → 已投遞 → 面試 → Offer → 結案），附下一步與期限。
- **回饋與修正**：記錄來自 HR、面試官、候選人與獵頭的回饋、原因分類與具體修正方向。重複出現的問題會更新候選人的求職策略，同一家公司的回饋會累積成公司情報，實際結果用來校準評分。

### 安裝

```
/plugin marketplace add codeotter0201/headhunter-agent
/plugin install headhunter@headhunter-agent
```

安裝後在 Claude Code 輸入 `/headhunter`。

### 資料只存在本機

候選人資料永遠不會進入這個 repo，只存在你電腦上的 `~/headhunter-data/`（或 `HEADHUNTER_DATA_DIR` 指定的資料夾），也不會上傳到任何第三方服務。

---

Keywords: headhunter, recruiter, recruiting, executive search, talent agent, career coach, job search, job matching, resume tailoring, ATS resume, applicant tracking, candidate management, interview feedback, Claude Code skill, 獵頭, 猎头, 求職, 履歷, 職缺評估, 人力銀行

## License

[MIT](LICENSE)
