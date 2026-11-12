# headhunter-agent

**English** | [繁體中文](README.zh-TW.md)

**An AI headhunter agent for Claude Code and other AI agents.** Use it for your own job search, or run searches for many candidates at once. It keeps a candidate database, reads job boards, scores each job against each candidate, writes tailored bilingual resumes, and tracks every application with feedback.

> **Status:** in development. The roadmap and feature specifications are tracked in the [roadmap epic](https://github.com/codeotter0201/headhunter-agent/issues/3).

## Why

A job search piles up more than anyone can keep straight: old resumes, notes, work logs, certificates and repositories, every job you looked at, how each application went, and what to fix next time. `headhunter-agent` works as your personal headhunter: you are its candidate, and it remembers all of this, with a source for every fact. Headhunters and career coaches run the same workflow for **many candidates at once**.

## Features

- **Candidate database** — Hand it anything about a candidate: notes, work logs, photos, existing resumes, GitHub repos. It checks each piece for missing details, vague claims and contradictions, asks follow-up questions, and tags every fact from a shared bilingual taxonomy. Every fact keeps a link to its source, and nothing is filled in without your confirmation. Create, read, update and archive candidates; search candidates and facts by skill, industry, seniority, years of experience, evidence or status.
- **Role profiles** — One candidate can pursue several roles at once, such as backend engineer and tech lead. For each role it lists the requirements, links the facts that support each one with a reason, and names the gaps: no evidence, only unconfirmed inferences, or only self-reported evidence, each with a way to close it. When facts change, it tells you which profiles are out of date. Search candidates by role, by required skill, or by roles with no must-have gaps.
- **Job reading** — Give it jobs in any form: a listing or job link from 104, CakeResume, Yourator, a company careers page or LinkedIn, a PDF or HTML file, a screenshot, or copied text, one job or many. It reads the listing, screens the titles, then reads each job in full and saves a snapshot: must-haves, nice-to-haves, duties, salary and location, with requirements tagged from the same taxonomy as candidate facts. Yourator and careers pages are read directly, following each site's robots.txt. 104 and CakeResume block automated requests, so the skill guides you instead: scroll the search results until every job has loaded, copy the page and paste it, and job pages are read in your browser or from text you copy. LinkedIn is read only from your signed-in browser or pasted text.
- **Job evaluation** — For one candidate, or across your whole database: it finds the candidates whose roles fit a job and evaluates each against the role that fits, or against all of the candidate's facts when none does, then offers to create a role from the job. Each evaluation gives a fit score from a fixed rubric (skill overlap, seniority, industry and domain, achievements, salary, location and work mode), reasons tied to specific facts and job requirements, gaps and risks with how to close them, and a high / medium / low success rating with its reasons. Failing a hard requirement, such as minimum years or a required degree, lowers the rating by one level. Requirements that keep appearing in the jobs evaluated under a role are proposed as changes to that role, applied only when you accept them.
- **Master resume** — One complete Chinese and English resume per candidate, kept for your own review rather than sent. It writes out every fact with a source in full: a summary, grouped skills, highlights when the strategy asks for them, then each job with what the organization is, the candidate's scope, achievements grouped by project, each one event told as the problem, the decision, the action and the measured result, and the tools used, followed by projects, education, certificates and training, awards and publications, and languages. The candidate's strategy decides what it leads with. Every fact is either written or left out by a strategy rule that names it, so the file doubles as a readable overview of the candidate's facts. Whatever is missing, such as a result or a team size, is marked in place with the follow-up question that asks for it, and you are told when new or changed facts, or a changed strategy, leave it out of date.
- **Tailored resumes** — A Chinese and an English resume for each evaluated application, in Markdown and PDF. Each starts from the profile of the role the job was evaluated under, follows the resume decisions recorded in the candidate's strategy, such as which title to use or which experience to leave out, puts the most relevant facts first, and uses only facts with a source: every line names the facts it comes from, numbers must match them, skills the candidate lacks stay out, and companies, titles and schools always get the same English names from the candidate's glossary. The PDFs are printed with Chrome, Chromium or Edge, and their text copies cleanly into applicant tracking systems.
- **Application tracking** — Every candidate × job pair moves through stages (found → evaluated → preparing → applied → interview rounds → offer → closed), with a dated timeline, each interview round recorded separately, and a next step with a due date while it is open. It lists overdue follow-ups across all candidates, shows progress by candidate, role, job and company, and records how each closed application ended: hired, declined, rejected or withdrawn.
- **Feedback loop** — Log feedback from HR, interviewers, the candidate and yourself, with a cause and a concrete fix, and track each fix until it is done; a fix that produces new material, such as a portfolio piece, ends with importing it as a source. Causes that recur across a candidate's applications or under one role turn into proposed changes to the strategy, role profiles and resumes, applied only when you agree. What feedback says about a company builds up into company notes across candidates. Closed applications are compared with their success ratings to show where the scoring over- or under-estimates, and any rubric change stays your decision.

## Install

The skill's helper script needs Python 3.9 or later, with no extra packages. Importing a GitHub repository or profile uses the [GitHub CLI](https://cli.github.com) (`gh`). Printing resumes to PDF uses Google Chrome, Chromium or Microsoft Edge.

### Clone and run (any AI agent)

```bash
git clone https://github.com/codeotter0201/headhunter-agent.git
cd headhunter-agent
```

Start your AI agent in this folder and tell it what you want, such as "add me as a candidate and import this resume". In Claude Code you can also run `/headhunter`. To update, run `git pull` in this folder.

Agents find the skill in `.claude/skills/` or `.agents/skills/`, and agents without skill discovery are sent to it by `AGENTS.md`. The agent must be able to read files and run commands, so chat-only AI services cannot run the skill. The two skill folders are symbolic links: on Windows, enable them before cloning, or use an agent that reads `AGENTS.md`.

### Claude Code plugin

To use the skill from any folder in Claude Code:

```
/plugin marketplace add codeotter0201/headhunter-agent
/plugin install headhunter@headhunter-agent
```

Then run `/headhunter:headhunter` in Claude Code.

### Other AI agents, from any folder

Agents that support the Agent Skills format can use the skill anywhere: copy `skills/headhunter/` into that agent's skills folder.

## Your data stays local

Candidate data never goes into this repository. It lives in `~/headhunter-data/` on your machine (or the folder set in `HEADHUNTER_DATA_DIR`) and is not sent to any third-party service.

## Contributing

Work happens through issues and pull requests, with humans and AI agents following the same rules. Start with [CONTRIBUTING.md](CONTRIBUTING.md); agents read [AGENTS.md](AGENTS.md) first.

---

Keywords: headhunter, recruiter, recruiting, executive search, talent agent, career coach, job search, job matching, resume tailoring, ATS resume, applicant tracking, candidate management, interview feedback, Claude Code skill, Agent Skills

## License

[MIT](LICENSE)
