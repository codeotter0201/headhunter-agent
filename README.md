# headhunter-agent

**English** | [繁體中文](README.zh-TW.md)

**An AI headhunter agent for Claude Code and other AI agents.** Use it for your own job search, or run searches for many candidates at once. It keeps a candidate database, reads job boards, scores each job against each candidate, writes tailored bilingual resumes, and tracks every application with feedback.

> **Status:** in development. The roadmap and feature specifications are tracked in the [roadmap epic](https://github.com/codeotter0201/headhunter-agent/issues/3).

## Why

A job search piles up more than anyone can keep straight: old resumes, notes, work logs, certificates and repositories, every job you looked at, how each application went, and what to fix next time. `headhunter-agent` works as your personal headhunter: you are its candidate, and it remembers all of this, with a source for every fact. Headhunters and career coaches run the same workflow for **many candidates at once**.

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

Other AI agents that support the Agent Skills format can use the skill too: copy `skills/headhunter/` into that agent's skills folder.

## Your data stays local

Candidate data never goes into this repository. It lives in `~/headhunter-data/` on your machine (or the folder set in `HEADHUNTER_DATA_DIR`) and is not sent to any third-party service.

## Contributing

Work happens through issues and pull requests, with humans and AI agents following the same rules. Start with [CONTRIBUTING.md](CONTRIBUTING.md); agents read [AGENTS.md](AGENTS.md) first.

---

Keywords: headhunter, recruiter, recruiting, executive search, talent agent, career coach, job search, job matching, resume tailoring, ATS resume, applicant tracking, candidate management, interview feedback, Claude Code skill, Agent Skills

## License

[MIT](LICENSE)
