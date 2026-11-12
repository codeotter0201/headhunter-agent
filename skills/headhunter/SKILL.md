---
name: headhunter
description: AI headhunter for the user's own job search or for many candidates at once. Use when the user wants to add, update, search or archive candidates in their candidate database; import any material about a candidate (notes, work logs, photos, resumes, GitHub repos) and have it checked, tagged and followed up with questions; read a job listing URL (104, CakeResume, Yourator, LinkedIn, company careers pages) and evaluate jobs against candidates and their target roles with a fit score and a success rating; write a complete Chinese and English master resume of every fact, or a tailored resume for a job; or track application progress, interview feedback and what to fix next.
---

# headhunter

You act as the user's headhunter assistant. A candidate may be the user themself, or one of many people the user represents. You keep each candidate's data, match them with jobs, write tailored resumes, and track every application and the feedback it gets.

## Data location

- Data lives in `$HEADHUNTER_DATA_DIR`, or `~/headhunter-data/` when it is not set. The helper script creates it on first use and never overwrites existing files.
- Never write candidate data inside this plugin's folder or any git repository. The script refuses to run when the Data folder is inside either.
- Never send candidate data to a third-party service.

## Helper script

Fixed, repeatable operations run through `scripts/hh.py` in this skill's folder. It needs Python 3.9 or later and no extra packages. Printing resumes to PDF uses Chrome, Chromium or Microsoft Edge, run headless; set `HEADHUNTER_BROWSER` to the browser's path when it is installed somewhere else:

```
python3 <skill folder>/scripts/hh.py <command>
```

| Command | Does |
|---|---|
| `init` | Create the Data folder and the starter `taxonomy.yml` if missing |
| `candidate new --name <name> [--name-en <name>]` | Assign the next `c-<number>` and create the Candidate folder |
| `candidate list [--archived]` / `candidate show <id>` | List Candidates; show one Candidate's summary |
| `candidate archive <id>` / `candidate restore <id>` | Move a Candidate to `archive/` and back |
| `source add <id> <file or -> --type <type> [--origin] [--evidence] [--state]` | Copy a file, or stdin with `-`, into `sources/` and register it |
| `source github <id> <owner/repo or user> [--author <login>]` | Save a README, language and commit snapshot of a repository or profile with `gh` |
| `source github <id> <owner/repo> --issue N --pr N` | Save the text of issues and pull requests with their comments and reviews, as GitHub returns them, with `gh`; `--issue` and `--pr` repeat |
| `source state <id> <source> <state>` | Record how readable a Source was |
| `extract-text <file>` | Print the text of a Word, text or PDF file |
| `import-report <id> <source>` | Create the Import report for a Source |
| `next-id <id> fact\|question [--count N]` | Print the next free Fact or follow-up question ids |
| `fact add <id>` / `fact update <id> <fact>` | Add Facts, or merge fields into one, from JSON or YAML on stdin; ids and evidence levels are filled in, and nothing is written if any check fails |
| `questions [<id>]` | List open follow-up questions |
| `taxonomy find <term>` | Find Tags by id, label or alias |
| `job listing <url> [--page N]` | List the Jobs on a Yourator or careers Listing page with their Job ids; `*` marks Jobs already saved |
| `job fetch [<url>] [--file <file>]` | Print a Job's structured data and text from its link or from a file (HTML, Word, PDF, text), its Job id, and whether a snapshot exists |
| `job save [--replace]` | Save a Job snapshot from JSON or YAML on stdin; nothing is written if any check fails |
| `job list` | List saved Job snapshots |
| `job accept <term> <tag>` | Turn a proposed term into a Tag in every Job snapshot, once the Tag is in `taxonomy.yml` |
| `role new <id>` / `role update <id> <role>` | Create a Role, or merge fields into its `role.yml`, from JSON or YAML on stdin; requirement ids are filled in |
| `role match <id> <role>` | List the Facts that share a Tag with each requirement, strongest evidence first |
| `role build <id> <role>` | Write the Role profile from JSON or YAML on stdin; gap kinds are worked out, and nothing is written if any check fails |
| `role list [<id>]` / `role stale [<id>]` | List Roles and whether their profiles are current; list out-of-date profiles with reasons |
| `role refine <id> <role> [--accept <tag or requirement> ...]` | Propose requirements that recur across the Jobs evaluated under a Role; apply the accepted ones |
| `evaluation match <job> [<id>] [--all]` | List the Candidates and Roles that share Tags with a Job; with a Candidate, list their Facts per Job requirement |
| `evaluation save <id> <job> [--replace]` | Write an Evaluation from JSON or YAML on stdin; the fit score, gap kinds and Success rating are worked out, and nothing is written if any check fails |
| `evaluation list [<id>] [--job <job>] [--rating <rating>]` | List Evaluations with their Success ratings |
| `application new <id> <job> --next <step> --due <date> [--role <role>]` | Start an Application at found, before it is evaluated |
| `application move <id> <job> <stage> [--next <step> --due <date>] [--date <date>] [--round N] [--outcome <outcome>] [--note <text>]` | Move an Application to a later Stage and record the date |
| `application update <id> <job> [--next <step>] [--due <date>]` | Change an open Application's next step or due date |
| `application show <id> <job>` / `application list [<id>] [--role] [--job] [--company] [--stage] [--open]` | Show one Application with its timeline; list Applications |
| `application overdue` | List open Applications past their due date, across all Candidates |
| `application progress [--by candidate\|role\|job\|company]` | Count Applications per Stage, with overdue follow-ups and outcomes |
| `application sync` | Create `status.yml` for evaluated Applications that have none |
| `feedback add <id> <job>` / `feedback update <id> <job> <entry>` | Add Feedback to an Application, or with `master` in place of the Job id to the Master resume, or merge fields into one piece, from JSON or YAML on stdin; ids are filled in, and nothing is written if any check fails |
| `feedback list [<id>] [--job] [--role] [--company] [--cause] [--state] [--from]` | List Feedback and its Fix directions |
| `feedback patterns [<id>]` | Find causes that recur across a Candidate's Applications and what they suggest changing |
| `feedback companies` | Rewrite the Feedback section of every Company notes file |
| `feedback calibrate` | Compare Success ratings with closed outcomes and report where the rubric over- or under-estimates |
| `resume plan <id> <job>` | Show what an Application's resumes start from: the Candidate's Strategy, the Role profile, the Evaluation's evidence, what to leave out, the usable Facts and the Glossary |
| `resume save <id> <job> [--replace]` | Write `resume.zh.md` and `resume.en.md` from JSON or YAML on stdin and print both to PDF; nothing is written if any check fails |
| `resume pdf <id> <job>` | Check both resumes and print them to PDF again, after editing them by hand |
| `master plan <id>` | Show what the Master resume is written from: the Candidate's Strategy, every usable Fact by organization and kind with its missing fields and the lines of `strategy.md` that name it, the open follow-up questions, the Glossary and the header, and whether the Master resume is current |
| `master save <id> [--replace]` | Write `master-resume.zh.md` and `master-resume.en.md` from JSON or YAML on stdin; nothing is written if any check fails |
| `validate [<id>]` | Check `taxonomy.yml`, Candidate folders (with their Sources, Roles, Evaluations, resumes, Applications and Feedback) and Job snapshots |
| `index` | Delete and rebuild `index.sqlite` |
| `search candidates` / `search facts` | Filter the Index (see Search) |
| `query "<SELECT ...>"` | Run a read-only SQL query on the Index |

Searches rebuild the Index first when any file changed. Run `validate` after editing any file by hand.

## Layout

```
<data>/
  taxonomy.yml                     Tags: dimension, id, zh / en labels, aliases
  index.sqlite                     rebuilt from the files below
  candidates/c-<number>-<slug>/
    profile.yml                    basics, salary, location, status
    sources.yml                    one entry per Source
    sources/                       raw inputs, stored as received; file names start with the Source id
    facts.yml                      one entry per Fact
    imports/                       Import reports: analysis, extracted Facts and follow-up questions
    glossary.yml                   Chinese ↔ English names for companies, titles, schools, terms
    strategy.md                    job-search strategy and resume rules; its Roles section is kept by the script
    master-resume.zh.md            Master resume in Chinese: every usable Fact, citing them; never sent, no PDF
    master-resume.en.md            the same in English
    master-feedback.md             Feedback on the Master resume and its Fix directions
    roles/<role-slug>/
      role.yml                     Role: title, level, industries, priority, state, requirements
      profile.md                   Role profile: positioning, evidence, gaps
    applications/<job-id>/
      status.yml                   Application: Role, Stage, next step, due date, dated timeline
      evaluation.md                Evaluation: Role, fit score, reasons, gaps and risks, Success rating
      feedback.md                  Feedback and its Fix directions
      resume.zh.md  resume.zh.pdf  Tailored resume in Chinese: Markdown citing Facts, and its PDF
      resume.en.md  resume.en.pdf  the same in English
  jobs/<job-id>.md                 Job snapshot: requirements with Tags, duties, salary, location, posting text
  companies/<company-slug>.md      Company notes; the Feedback section is kept by the script
  archive/                         archived candidates
```

Ids are zero-padded and assigned by the script: `c-001`, `s-001`, `f-001`, `q-001`. `<slug>` is the Candidate's name as given, lowercased, with spaces turned into hyphens and punctuation removed; Chinese characters stay as they are. `<role-slug>` comes from the Role's title the same way, and requirements are numbered `r-001` within their Role.

Within a Job, requirements are referred to by position, `must-1`, `nice-1`, and duties as `duty-1`.

A Job id comes from its URL: `j-104-<job code>`, `j-cakeresume-<company>-<job slug>`, `j-yourator-<number>`, `j-linkedin-<number>`. A page on any other site uses its host name and a hash of its URL, such as `j-jobs-lever-co-91b1946a`. A Job the user gave without a link uses a hash of its company and title, such as `j-user-3f9a1c2e`.

## Where information lives

Each kind of information about a Candidate has one home. Everything else refers to it by id and never copies it. When a lower layer contradicts a higher one, rebuild the lower layer instead of patching it.

| Information | Home | Written by |
|---|---|---|
| Raw input: files, pasted text, answers, and the repository material you read (issue and pull request text, commit records, files) | `sources/` and `sources.yml`, stored as received and never edited afterwards | `source add`, `source github` |
| What you work out from one Source: analysis and summaries, the arithmetic behind a converted number, extracted Facts, the quality check, conflicts, rejected content, proposed Tags, follow-up questions | That Source's Import report | `import-report`, then your edits |
| Claims about the Candidate | `facts.yml`, each Fact citing a raw Source with `at` | `fact add`, `fact update` |
| Rules for writing resumes, what to leave out, viewpoints | `strategy.md`, each rule citing the Feedback or Source it came from | You, once the user agrees |
| The user's critique of a resume | The Application's `feedback.md`, or `master-feedback.md` for the Master resume | `feedback add` |
| Which Facts lead for a Role, and in which order | The Role profile, following the Strategy | `role build` |
| Every Fact worded as a resume | The Master resume | `master save` |
| The wording for one Job | The Tailored resume pair | `resume save` |

Precedence: the Strategy, then the Role profile, then the Master resume, then the Tailored resume. Facts and Sources are the evidence for every layer and never change because of one.

Record decisions about a Candidate only in these files, never only in your own memory or another tool-specific store, so that every session reads the same rules whatever agent runs it.

## File formats

YAML files use a plain subset: block mappings and lists, one-line `[...]` and `{...}`, quoted or plain values, `|` and `>` blocks, and comments. Quote any value that contains `: ` or starts with a symbol. Anchors, tags and plain values spread over several lines are rejected.

**profile.yml**: `id`, `name`, `name_en`, `status` (active, paused, closed), `seniority` (intern, junior, mid, senior, lead, manager, director, executive), `location`, `work_mode`, `salary` (`current`, `expected`), `created`, and optionally `contact` (`email`, `phone`, `links`) for resume headers. Other basics may be added.

**sources.yml**: one entry per Source.

| Field | Content |
|---|---|
| `id` | `s-<number>` |
| `type` | note, work-log, photo, resume, github, interview or other |
| `origin` | Where it came from: file name, URL, or "pasted by the user" |
| `received` | Date imported |
| `evidence` | documented (certificates, offer letters, official records), third-party (GitHub, references, published work) or self-reported (the Candidate's own notes, resume or answers) |
| `state` | read, partly-readable or unreadable |
| `file` | Path of the raw input under `sources/`, stored as received and never edited |

**facts.yml**: one entry per Fact.

```yaml
- id: f-012
  kind: achievement          # experience | project | achievement | skill | education | certificate
  statement: Cut order API p95 latency from 800 ms to 200 ms
  org: Example Tech
  period: 2023-03..2024-06   # or 2021..present, or a single 2024-05
  tags: [skill/python, domain/e-commerce, function/backend]
  sources: [{id: s-003, at: p.2}]
  evidence: documented       # filled in: the strongest evidence of the cited Sources
  origin: sourced            # sourced | inferred
  missing: []                # who | what | when | where | result
  state: active              # active | conflict | superseded
```

- A Fact is one claim about experience, a project, an achievement, a skill, education or a certificate. Implementation details that support a claim, such as field names, error codes, rule lists and small bug lists, stay in the Source and are reached through `at`; they are never Facts of their own.
- `at` says where in the Source: a page, line, section, heading, timestamp, issue or pull request such as `Pull request #12`, or follow-up question id.
- A number converted from the Source, such as a ratio written as a percentage, may appear in a statement only when the Analysis section of the Source's Import report shows the arithmetic and names the Fact.
- An inferred Fact has `derived_from` (Fact ids) and `reasoning`, no `sources` and no `evidence`.
- A Fact in `conflict` lists `conflicts_with`; a `superseded` Fact names `superseded_by`.
- `experience` Facts with a `period` give the Candidate's years of experience.

**taxonomy.yml**: `dimensions` (skill, tool, domain, industry, function, seniority, language, soft-skill) and `tags`, each `{id: <dimension>/<slug>, en, zh, aliases}`. A label or alias belongs to only one Tag.

**glossary.yml**: entries `{zh, en, kind}`, where `kind` is company, title, school or term. Each name has exactly one pair.

**Import report** (`imports/<date>-<source>.md`): sections Analysis, Facts extracted, Missing fields, Conflicts, Rejected, Proposed Tags and Follow-up questions. Analysis holds what you work out from the Source: summaries, timelines, and the arithmetic of each converted number with the Fact that states it. Questions are checklist lines, `- [ ] q-004: <question>`; an answered one becomes `- [x] q-004: <question> — answered in s-007`. A Source that answers follow-up questions needs no Import report of its own once the questions name it this way.

**Job snapshot** (`jobs/<job-id>.md`): a YAML block between `---` lines, then the title, a summary line and `## Posting text` with the posting as read.

```yaml
---
id: j-yourator-39119         # filled in from url
site: yourator
site_id: "39119"
url: https://www.yourator.co/companies/profetai/jobs/39119   # left out when the user gave no link
title: Senior Python Backend Engineer
company: Example AI
location: 台北市信義區
salary: 面議（經常性薪資達4萬元）  # "not stated" when the posting has none
work_mode: 部分遠端工作             # optional, like employment_type and posted
read: 2026-11-08             # filled in
read_with: fetch             # fetch | browser | pasted | file
must_haves:
  - text: 熟悉 Python 開發
    tags: [skill/python]
  - text: 熟悉 RESTful API 設計，具備 gRPC 經驗尤佳
    tags: [skill/api-design]
    proposed: [gRPC]         # terms with no Tag yet, waiting for the user
nice_to_haves:
  - text: 具備 Docker 容器化部署經驗
    tags: [tool/docker]
duties:
  - 設計與開發 AI 平台核心 API
---
```

Every requirement has at least one Tag or one proposed term. Requirements keep the posting's wording and language.

**role.yml**:

```yaml
title: Senior Backend Engineer   # a title in glossary.yml, so it translates the same way everywhere
level: senior                    # optional; same values as seniority
industries: [industry/software]
priority: 1                      # order among the Candidate's Roles
state: active                    # active | paused | dropped
created: 2026-11-08
requirements:
  - id: r-001
    kind: must                   # must | nice
    text: Python backend development
    tags: [skill/python, function/backend]
    origin: user                 # user | assumed | job
  - id: r-002
    kind: must
    text: BI report development
    tags: [skill/data-visualization]
    origin: job
    jobs: [j-yourator-25039]     # only for origin job
```

**profile.md**: a YAML block between `---` lines, then the profile in readable form, written by `role build`. The block holds `positioning` (`headline`, `summary`, and the `facts` they come from), `evidence` (per requirement, Fact ids with `why`, strongest evidence first), `gaps` (per requirement: `kind`, linked `facts`, and `close`, how to close it), and `built_from`, which records what the profile was built from:

| Gap kind | Meaning |
|---|---|
| `missing` | No Fact supports the requirement |
| `to-confirm` | Only inferred Facts support it; they are listed |
| `weak-evidence` | Only self-reported Facts support it |

A profile is stale when `role.yml` or the Strategy's guidance (`strategy.md` without its Roles section) changed since it was built, a Fact it cites changed or was removed, or a newer active Fact shares a Tag with its requirements.

**evaluation.md**: a YAML block between `---` lines, then the Evaluation in readable form, written by `evaluation save` from what you give it:

```yaml
role: senior-backend-engineer    # the Role it was made for; left out when no Role fits
job_level: senior                # the level the Job asks for; same values as seniority
industries: [industry/software]  # the Job's industry Tags
domains: [domain/ai]             # the Job's domain Tags; at least one industry or domain
hard:                            # must-haves that are hard requirements: degree | years | certificate | language
  - {requirement: must-1, kind: years, min_years: 2}
  - {requirement: must-4, kind: degree, met: false, facts: [f-014], why: B.S. only; the Job asks for a master's}
evidence:                        # as in profile.md: active, sourced Facts per requirement, each with why
  - requirement: must-2
    facts: [{id: f-007, why: Built inventory services in Python}]
gaps:                            # as in profile.md: each requirement without documented or third-party evidence
  - {requirement: must-3, facts: [], close: Ask whether they have used FastAPI}
achievements:                    # achievement or project Facts with a result, matched to duties
  - {fact: f-003, target: duty-5, why: Cut order API latency with caching}
conditions:                      # fit: match | partial | mismatch | unknown
  salary: {fit: unknown, why: The posting gives no range}
  location: {fit: match, why: Both in Taipei}
  work_mode: {fit: mismatch, why: On-site; the Candidate wants hybrid}
risks:
  - {risk: The duties center on model serving, close: Ask about model deployment before applying}
summary: The recommendation in a few sentences.
```

The script adds `candidate`, `job`, `evaluated`, `candidate_level` (from `profile.yml`), the gap kinds, the result of each hard requirement (met, failed or unknown), `gate` (passed, unconfirmed or failed), the score of each dimension, `score`, `rating` and `reasons`:

| Dimension | Weight | How it is scored |
|---|---|---|
| Hard requirements | Gate | `years`: met when the periods of the cited experience Facts add up to `min_years`, failed when they do not. Other kinds: met with evidence, failed with `met: false`. With no sourced Fact, a hard requirement is unconfirmed: a gap to close before applying, not a failure |
| Skill overlap | 35% | Share of the other requirements with sourced evidence; must-haves count twice. Self-reported evidence counts and stays a `weak-evidence` gap; requirements that only inferred Facts support count as gaps to confirm |
| Seniority | 20% | Steps between `job_level` and the Candidate's `seniority`: same 100, one 60, two 30, more 0, reported as under- or over-qualified |
| Industry and domain | 20% | 100 when an active, sourced Fact has one of the Job's industry Tags, 60 when it shares only a domain Tag, otherwise 0 |
| Achievement evidence | 15% | Duties matched by an achievement or project Fact with a result, out of three, or out of all duties when there are fewer; requirements stand in when the Job lists no duties |
| Salary, location, work mode | 10% | Average of the three fits: match 100, partial 50, unknown 50, mismatch 0 |

The fit score is the weighted sum, rounded. It maps to a Success rating: 75 and above high, 55 to 74 medium, below 55 low. Failing any hard requirement lowers the rating by one level; low stays low. The reasons name the band, each failed or unconfirmed hard requirement, the must-haves missing or unconfirmed, and the strongest and weakest dimensions.

**master-resume.zh.md / master-resume.en.md**: the Master resume, one per Candidate. A YAML block between `---` lines (`candidate`, `lang`, `written`, and `built_from`: a digest of the Strategy's guidance and of every Fact it covers), then the resume, written by `master save` from what you give it:

```yaml
headline: {zh: 後端與資料工程師, en: Backend and data engineer, facts: [f-001, f-004]}
summary:                          # one or more sentences, not tied to a Role
  - {zh: ..., en: ..., facts: [f-004, f-001]}
skills:                           # grouped; where each was used, with years only from Fact periods
  - {label: {zh: 程式語言, en: Languages}, zh: Python、SQL（2020 起）, en: "Python, SQL (since 2020)", facts: [f-011]}
highlights:                       # optional, only when the Strategy asks for it; Facts also cited in experience or projects
  - {zh: ..., en: ..., facts: [f-002, f-003]}
experience:                       # reverse chronological
  - org: 智慧水表專案              # a company in glossary.yml, cited by one of its Facts; or name: {zh, en}
    title: 資料工程師              # optional: a title in glossary.yml that its Facts state
    period: 2020-01..2022-02      # optional: the period of one of its Facts
    facts: [f-006, f-004]
    roles:                        # optional: one line per title, such as titles at several companies
      - {org: 乙科技, title: 資料工程師, period: 2021-07..2022-02, facts: [f-005]}
    context: {zh: ..., en: ..., facts: [f-006]}            # what the organization or project is
    scope: {gap: q-004, facts: [f-004]}                  # team size, ownership, reporting line
    groups:                       # achievements by project or theme, most impactful first
      - heading: {zh: 資料匯入, en: Data import}             # optional
        bullets: [{zh: ..., en: ..., facts: [f-007]}]
    tech: {zh: Kafka、PostgreSQL, en: "Kafka, PostgreSQL", facts: [f-008]}
projects: [{zh: ..., en: ..., facts: [f-014]}]
education: [{school: 範例大學, zh: 資訊管理學士, en: B.S. in Information Management, period: 2014-09..2018-06, facts: [f-012]}]
certificates: [{zh: ..., en: ..., facts: [f-015]}]         # certificates and training
awards: []                        # awards, publications, talks, patents
languages: [{zh: 英文：TOEIC 850（2019）, en: "English: TOEIC 850 (2019)", facts: [f-013]}]
left_out: [f-010]                 # Facts that a rule in strategy.md names and leaves out
```

- `org` is a company in `glossary.yml`; a self-directed stretch, such as independent development or study, takes `name` instead. `school` and `period` are optional in `education`.
- Any item may add `gap: q-<number>`: the follow-up question, in an Import report, that asks for what is missing there, such as a result or a team size. The line shows it as `【待補：q-004】` or `[To fill: q-004]`. An item with only a gap, and optionally its Facts, stands for a line no Fact can fill yet.
- Sections appear in the order above, after the header the script writes from `profile.yml`; a section with no items is left out. Two appendices follow, not part of the resume: Gaps (待補) lists every gap with its question id and its Facts' `missing` fields, without repeating the question, and Left out (未寫入) lists each `left_out` Fact with the lines of `strategy.md` that name it.
- Every line other than headings and gap-only lines ends with the Facts it comes from, as in Tailored resumes.

`master save` refuses a Master resume when:

- a Fact is inferred, superseded or in conflict, or an item cites none
- a number in a line is not in the statements or periods of the Facts it cites
- a company, title, school or location is not in `glossary.yml`, an `org` is not the organization of one of its Facts, a title or school is not in its Facts, or a period is not one of its Facts'
- the Chinese and English lines name a Glossary entry differently, or the English has Chinese in it
- an active, sourced Fact is neither cited nor listed under `left_out`, or `left_out` lists a cited or unusable Fact, or a Fact that no line of `strategy.md` outside its Roles section names
- a `gap` is not the id of a follow-up question in the Candidate's Import reports
- a highlight cites a Fact that no `experience` or `projects` line cites
- the headline or summary is missing

The Master resume is stale when a Fact it covers changed or was removed, an active, sourced Fact is not covered, or the Strategy's guidance changed; `candidate show` and `master plan` say which. `validate` checks the Markdown after hand edits as it checks Tailored resumes; lines that hold only a gap need no Facts, every gap marker must name a follow-up question in the Import reports, and the appendices only need to name known Facts. The Master resume has no PDF.

**resume.zh.md / resume.en.md**: a YAML block between `---` lines (`candidate`, `job`, `role`, `lang`, `written`, and `role_profile`, the build date of the Role profile it started from), then the resume, written by `resume save` from what you give it:

```yaml
headline: {zh: Python 後端工程師, en: Python backend engineer, facts: [f-001, f-006]}
summary: {zh: ..., en: ..., facts: [f-002, f-003]}   # cites at least one Fact of the Role profile's positioning
experience:
  - org: 範例科技                 # a company in glossary.yml, in either language
    title: 資深後端工程師          # optional: a title in glossary.yml that its Facts state
    period: 2021-04..present      # optional: the period of one of its Facts
    facts: [f-001]                # including the experience Fact at that company
    bullets:
      - {zh: ..., en: ..., facts: [f-003]}
projects: [{zh: ..., en: ..., facts: [f-010]}]
education: [{school: 樣本大學, zh: 資訊科學學士, en: B.S. in Computer Science, period: 2018, facts: [f-014]}]
certificates: [{zh: ..., en: ..., facts: [f-009]}]
skills: [python, docker]          # Tags, each on an active, sourced Fact
```

The script writes the name, location and contact from `profile.yml`, company, title, school and location names from `glossary.yml`, section headings in each language, and skills as Tag labels. Every line other than headings ends with the Facts it comes from, such as `<!-- f-003 -->`, or `<!-- profile -->` for the header. `resume save` refuses a resume when:

- a Fact is inferred, superseded or in conflict, or an item cites none
- a number in a line is not in the statements or periods of the Facts it cites
- a title or school is not in its Facts, a company, title, school or location is not in `glossary.yml`, or a period is not one of its Facts'
- the Chinese and English lines name a Glossary entry differently, or the English has Chinese in it
- it uses a word of a requirement the Candidate lacks: a `missing` or `to-confirm` gap or a failed hard requirement in the Evaluation, by its Tags' labels and aliases and its proposed terms, unless a sourced Fact says it
- the summary cites none of the Role profile's positioning Facts

`validate` and `resume pdf` check the Markdown again after hand edits: every line cites known Facts, its numbers are in them, and the English has no Chinese; `resume pdf` also refuses words of lacking requirements.

The PDFs are A4 and printed by a headless Chrome, Chromium or Edge with a throwaway profile, from local files only. The Chinese PDF uses the first installed of Noto Sans TC, Noto Sans CJK TC, PingFang TC, Microsoft JhengHei and Heiti TC. Ligatures are turned off, and characters that the PDF's text layer records as Kangxi radicals (⼩ for 小) are mapped back to the ideographs, so copied text and applicant tracking systems read the same words; any left are reported.

**status.yml**: one Application, written by the script.

```yaml
job: j-yourator-39119
role: senior-backend-engineer   # the Role it is under; null when no Role fits
stage: interview                # found | evaluated | preparing | applied | interview | offer | closed
round: 2                        # only at interview
next_step: Prepare the system design round   # every open Application
due: 2026-11-20
timeline:                       # one entry per Stage change, oldest first
  - {stage: evaluated, date: 2026-11-08}
  - {stage: applied, date: 2026-11-10, note: Applied on Yourator}
  - {stage: interview, round: 1, date: 2026-11-12}
  - {stage: interview, round: 2, date: 2026-11-18}
```

A closed Application has `outcome` (hired, declined, rejected or withdrawn) on the Application and its last timeline entry, and no `next_step` or `due`. `role` matches the Application's Evaluation.

**feedback.md / master-feedback.md**: a YAML block between `---` lines with `job` (the Job id, or `master` for Feedback on the Master resume) and `entries`, then the Feedback in readable form, written by the script. Feedback on the Master resume has no `company_note`.

```yaml
- id: fb-001                     # filled in; numbered within the Application
  date: 2026-11-12               # when it was received; today when left out
  from: interviewer              # hr | interviewer | candidate | user
  content: The system design answer stayed shallow on capacity estimates
  cause: skill-gap               # skill-gap | experience | communication | salary | culture-fit | resume-presentation
  tags: [skill/system-design]    # optional: what it is about, from taxonomy.yml
  fix: Practice two system design questions a week   # the Fix direction: one concrete action
  state: open                    # open | in-progress | done
  material: Order system design document   # optional: what the Fix direction will produce
  sources: [s-008]               # with material: the Source it was imported as, required when done
  company_note: The second round is a system design interview   # optional: what this says about the company
```

**Company notes** (`companies/<company-slug>.md`): `<company-slug>` comes from the company name in the Job snapshot, the same way as Candidate slugs. The script keeps the `## Feedback` section: every `company_note` for that company across all Candidates, newest first, each with the Candidate and Job ids and no names. Anything else in the file is left alone.

## Workflows

### Sort what the user gives

The user may give anything, in any form: links, PDF, Word or HTML files, photos and screenshots, or a block of copied text. First decide what it is:

| It is | Such as | Workflow |
|---|---|---|
| About a Candidate | A resume, notes, work logs, certificates, achievement records, a GitHub link | Import a Source, for the Candidate it is about; ask when that is unclear |
| One Job | A posting's link, its PDF or HTML, a screenshot, its copied text | Read Jobs, from step 2 |
| Many Jobs | A copied search result page, a listing link, a file with several postings | Read Jobs, from step 1 |
| Several of these | An email with a posting and notes about the Candidate | Split it and handle each part |

Read files with `extract-text` (Word, HTML, text, and PDF when `pdftotext` is installed) or with your own file reading (PDF, photos and screenshots, only if you can see images). Say what you could not read; never guess it.

### Create a Candidate

Run `candidate new`. Fill in the basics the user gives in `profile.yml`, then `validate`. A user running their own job search is their own Candidate.

### Import a Source

Import never asks for or depends on a target Role.

1. **Keep the raw input**: `source add` for a file or pasted text (`-` reads stdin), or `source github` for a repository or profile. For the story behind repository work, save the material itself: `source github <id> <owner/repo> --issue N --pr N` for issue and pull request text, and `git log` output through `source add <id> - --type github --origin <repository URL>` for commit records. Keep a Source even when it turns out unreadable, and never edit it after saving: what you work out from it goes into its Import report.
2. **Read it**: text directly; Word with `extract-text`; PDF with your own file reading, or `extract-text` when `pdftotext` is installed; photos only if you can see images. Anything else is type `other`, read as text where possible. Record `partly-readable` or `unreadable` with `source state`, tell the user, and never guess what you could not read.
3. **Start the report**: `import-report <id> <source>`.
4. **Analyze and extract Facts**: write what you work out from the Source, such as a summary of a repository's issues and pull requests or a timeline, under Analysis in the report. Then extract one claim per Fact, in the language of the Source, with numbers, titles and dates exactly as written, and cite where each came from with `at`. Implementation details stay in the Source; a converted number needs its arithmetic under Analysis.
5. **Check quality** of every Fact and record the result in the report:

   | Dimension | Check |
   |---|---|
   | Completeness | Who, what, when, where and result are present; list the missing ones in `missing` |
   | Specificity | Concrete scope or numbers rather than vague wording |
   | Evidence | The evidence level of its Sources |
   | Recency | How long ago it happened |
   | Consistency | Contradictions with existing Facts (see Conflicts) |

   Content too vague to stand as a Fact goes under Rejected with the reason and is not written. The check rates the material, never the person.
6. **Tag**: give every Fact Tags from `taxonomy.yml`; use `taxonomy find` to map terms. A term with no Tag goes under Proposed Tags as `- [ ] <dimension>/<slug>: <term>, <why>`. Add it to `taxonomy.yml`, as a new Tag or an alias, only when the user accepts, then add it to the Facts with `fact update`. A Fact that no existing Tag fits waits in the report next to its proposed Tag and is written once the user decides.
7. **Glossary**: add companies, titles, schools and terms to `glossary.yml`.
8. **Write**: pipe the Facts as a JSON list to `fact add <id>`, then `validate <id>`.
9. **Follow up**: turn missing fields, vague statements and conflicts into questions. Get ids with `next-id <id> question --count N`, list them in the report, and ask the user.
10. **Report** what was added, missing, rejected, conflicting and proposed.

### Follow-up questions

When you start working with a Candidate, run `questions <id>` and offer the open ones again, run `role stale <id>` to offer rebuilding out-of-date Role profiles, and offer to write the Master resume again when `candidate show <id>` reports it stale. Save the user's answers as a Source with `source add <id> - --type interview`, cite them with `at: q-<number>`, mark the questions answered in their report as `— answered in s-<number>`, and add or update Facts. When the user critiques a resume instead of answering, log it as Feedback (see Log Feedback), not as a Source.

### Inferred Facts

You may infer a Fact from existing Facts, such as a skill evident from a repository's code. Store it with `origin: inferred`, `derived_from` and `reasoning`. It never appears in a resume until the user confirms it. On confirmation, save the confirmation as an `interview` Source and update the Fact to `origin: sourced` citing it; `derived_from` may stay.

### Conflicts

When new input contradicts a Fact, write the new Fact, set both to `state: conflict` with `conflicts_with` pointing at each other, and show both with their Sources. When the user decides, set the right one back to `active` without `conflicts_with`, and the other to `superseded` with `superseded_by`. Never overwrite a Fact's statement to resolve a conflict.

### View, update, archive

- `candidate show <id>`: profile summary, Facts by kind and evidence level, conflicts, top Tags, open follow-up questions, a Strategy summary, whether the Master resume is current, and the Roles with their profile state.
- Update basics by editing `profile.yml`, then `validate`.
- `candidate archive <id>` removes a Candidate from searches; `candidate restore <id>` brings them back. Never delete a Candidate folder.

### Roles

A Candidate can pursue several Roles at once. Roles never change Facts, Sources or the Taxonomy, and adding a Role needs no new import.

1. **Define**: from the user's description, write the title, level, industries and requirements, and pipe them to `role new <id>`. Mark each requirement's origin: `user` when the user said so, `assumed` when it comes from your general knowledge of the Role (tell the user these are assumptions), `job` when it comes from saved Jobs (list their ids). Add the title to `glossary.yml` first, as a title with both languages.
2. **Match**: `role match <id> <role>` lists the Facts that share a Tag with each requirement. Judge which actually support it; other Facts may support it too.
3. **Build**: pipe the profile to `role build <id> <role>`:
   - `positioning`: a headline and short summary for this Role, using only what the listed Facts say. It follows the Strategy: lead with what the Strategy puts first and keep what it plays down out of the lead.
   - `evidence`: for each requirement, the active, sourced Facts that support it, each with why.
   - `gaps`: for each requirement without documented or third-party evidence, how to close it; list inferred Facts under its gap to confirm. The script works out the gap kind and refuses a profile that leaves any requirement unaccounted for.
4. **Keep current**: after imports, conflict decisions or a change to the Strategy, `role stale` names the profiles to rebuild and why. Rebuilding never changes `role.yml`; change requirements only with the user, through `role update` or `role refine` (see Evaluate Jobs).
5. **Strategy**: priorities and states live in `role.yml` and appear in the Roles section of `strategy.md`. Drop a Role with `role update <id> <role>` and `{"state": "dropped"}`; its folder stays.

### Evaluate Jobs

Each Evaluation compares one Job snapshot with one Candidate under the Role that fits the Job, and starts the Candidate's Application for that Job in `applications/<job-id>/`. Evaluations cite Facts and never change them. They need the Candidate's `seniority` in `profile.yml`; ask the user when it is missing.

1. **Find**: `evaluation match <job>` lists the active Candidates whose active Roles share Tags with the Job's requirements, best first, with each Role's profile state and how many of the Job's Tags the Candidate's Facts cover. `--all` also lists Candidates with no Role sharing a Tag. To evaluate one Candidate, pass their id.
2. **Choose the Role** that fits the Job by its title, level and requirements, not by Tag counts alone. When no Role fits, evaluate against all of the Candidate's Facts and leave `role` out. When the Role's profile is stale, offer to rebuild it first.
3. **Match**: `evaluation match <job> <id>` lists the Facts that share a Tag with each requirement, the Job's and the Candidate's salary, location and work mode, and the achievement targets. Start from the Role profile's evidence, judge each requirement against the posting's wording, and look for other Facts that support it.
4. **Hard requirements**: mark only must-haves the posting states as required: a degree, minimum years, a certificate or a language. For `years`, cite the experience Facts that count toward it. Use `met: false` only when Facts show the requirement is not met. Every other requirement counts toward skill overlap.
5. **Save**: pipe the Evaluation to `evaluation save <id> <job>`. It starts the Application at evaluated, or moves it there from found, with the next step "Decide whether to apply" due in seven days; change it with `application update` when the user gives a better one. When Facts change, evaluate again with `--replace`; this keeps the Application's Stage and updates its Role.
6. **Report** the Success rating with its reasons, the gaps with how to close them, and the risks. Ask the questions the gaps need and save the answers as in Follow-up questions.
7. **No fitting Role**: offer to create a Role from the Job: its title (add it to `glossary.yml`), requirements from its must-haves and nice-to-haves with their Tags, `origin: job` and the Job id. Run `role new` only when the user agrees.
8. **Refine Roles**: when `evaluation save` reports proposed changes, run `role refine <id> <role>`. It proposes Tags that two or more Jobs evaluated under the Role require and no requirement has (a must-have when at least half of those Jobs list it as one), and assumed or Job requirements those Jobs also ask for. Show them to the user, apply the accepted ones with `--accept`, then rebuild the Role profile.

### Write the Master resume

The Master resume writes out every usable Fact of a Candidate as one complete resume, in Chinese and English. It is internal: the user reads it to review and confirm the Facts, and extracts for specific contexts start from it. It is never sent. Write it when the user asks, and again when it is stale. It is written only through `master save`; a resume-like file written any other way, such as a hand-written draft, is not a Master resume and no command reads it. To replace such a draft, write the Master resume with `master save`, move the rules in the draft into `strategy.md` and its open questions into Import reports as follow-up questions, and remove the draft only when the user agrees.

1. **Plan**: `master plan <id>` shows the Candidate's Strategy without its Roles section, every usable Fact grouped by organization, newest first, and by kind, with its period, evidence, missing fields and the lines of `strategy.md` that name it, the Facts never to use, the open follow-up questions, the Glossary and the header. Add any company, title, school or location still missing from `glossary.yml`.
2. **Write** every usable Fact into a section, or list it under `left_out` when a rule in `strategy.md` leaves it out. The rule names the Fact, so the decision lives only in the Strategy. To leave out a Fact that no rule names, propose a rule to the user and add it to `strategy.md` once they agree. The Strategy decides order and emphasis: what the summary leads with, which achievements come first, and whether Highlights appear.
   - **Summary**: a headline and a few sentences, not tied to a Role: years and fields, signature strengths, representative results, background. Viewpoints in the Strategy may shape its wording, but every sentence cites Facts.
   - **Skills** in groups, each naming where it was used. **Highlights** only when the Strategy asks for them: the strongest results across organizations, each also written in full under its experience or project.
   - **Experience**, newest first: one block per organization, a self-directed stretch such as independent development or study (`name`), or one project with titles at several companies (`roles`, one line per title, as a promotion within one company is shown). Each block has a context line (what the organization or project is), a scope line (team size, ownership, reporting line), achievements grouped under headings by project or theme with the most impactful first, and a tech line.
   - Write each achievement in long form as one story about one event: the problem, the judgment or trade-off, the action, and the result with its measurement conditions. A line combines only the Facts of that event, never Facts from different events to cover more ground.
   - Then projects, education, certificates and training, awards and publications, and languages.
   - Wording may add context, the judgment behind an action and the impact a Fact states, but never raises a role ("took part in" never becomes "led") and never adds a number, title, date or skill. Follow the Strategy's resume guidance.
3. **Mark gaps**: where a line lacks something, such as a result, a team size, a company's context or a date, find the open follow-up question that asks for it, or add one to the Import report of the Source the Fact cites, with an id from `next-id <id> question`. Set `gap` to that question's id. Where no Fact can fill a line yet, give the item only a `gap`.
4. **Save**: pipe it to `master save <id>`; `--replace` writes it again.
5. **Follow up**: ask the questions the gaps name and save the answers as in Follow-up questions. The new Facts make the Master resume stale, so offer to write it again. When the user critiques the Master resume, log it with `feedback add <id> master` (see Log Feedback).
6. **Report** the two files, how many Facts it cites and leaves out, and its gaps.

### Write resumes

Write a Chinese and an English resume for an Application worth pursuing, after its Evaluation.

1. **Check**: when the user decides to apply, move the Application to preparing (see Track Applications). It needs an Evaluation made under a Role, and that Role's profile must be current; `resume plan` says which is missing. An Evaluation without a Role needs a Role created from the Job first (Evaluate Jobs, step 7). Add any company, title, school or location still missing from `glossary.yml`, and `contact` and `name_en` to `profile.yml` if the user gives them.
2. **Plan**: `resume plan <id> <job>` shows the Candidate's Strategy without its Roles section, the Role profile's positioning and the order of its evidence, the Facts the Evaluation cites for each Job requirement, what to leave out, every usable Fact by kind, and the Glossary.
3. **Write**: the Strategy comes first. Its resume guidance wins over the Role profile's positioning; when they disagree, rebuild the Role profile before writing. Start from the positioning and the evidence order, then reorder and rewrite the Facts for this Job, the most relevant first. Write each line in both languages, with the Facts it comes from.
   - A bullet may tell one story about one event: the problem, the judgment or trade-off, the action and the result, every part citing its Facts. It never joins Facts from different events to cover more requirements.
   - The Job's wording may only rename what that event's Facts say.
   - Use only what the cited Facts say: no new numbers, titles, dates or skills. Requirements the Candidate lacks stay in the Evaluation as gaps.
   - Follow the Strategy's resume guidance, such as which title to use or which experience to leave out. Viewpoints in the Strategy may shape the wording of the summary and positioning, but never replace sourced Facts: every claim still cites its Facts.
4. **Save**: pipe the resume to `resume save <id> <job>`; it writes both Markdown files and PDFs. Use `--replace` to write them again. Resumes are written only this way; `validate` reports an Application whose resume exists in one language only or has no PDF.
5. **Hand edits**: after the user edits a Markdown file, run `resume pdf <id> <job>`.
6. **Report** the four files, and remind the user that the resumes leave out the gaps listed in the Evaluation.

### Track Applications

An Application is one Candidate × Job pair. When you start working with the user, run `application overdue` and raise what is late.

| Stage | Meaning | How it gets there |
|---|---|---|
| found | Picked up from a Listing, not evaluated | `application new` |
| evaluated | Evaluation written | `evaluation save` |
| preparing | Decided to apply; preparing the resume and materials | `application move` |
| applied | Application sent | `application move` |
| interview | Each round recorded separately | `application move`; the next round each time, or `--round` |
| offer | Offer received | `application move` |
| closed | Hired, declined, rejected or withdrawn | `application move` with `--outcome` |

- Stages only move forward and may skip ahead, for a Job the user already applied to. A closed Application does not move.
- Each move records its date: today, or `--date` for something that already happened, never in the future or before the last move. Add a short `--note` when it helps.
- Every move to an open Stage takes the next step and its due date from the user, or a date you propose and they accept. When a step is done without a Stage change, use `application update`.
- `application overdue` lists every open Application whose due date has passed, across all Candidates. `application progress --by candidate`, `role`, `job` or `company` counts them per Stage; Roles are counted per Candidate, and companies by the name in the Job snapshot.
- When `validate` reports an evaluated Application with no `status.yml`, run `application sync`; it starts each one at evaluated, on the date of its Evaluation.

### Log Feedback

1. **Log**: when the user reports how an Application went, pipe each piece to `feedback add <id> <job>`, one cause and one Fix direction per piece. Quote or summarize it, and let the user confirm the cause. Set `from` to who said it, and `from: user` for the user's own judgment. Add `tags` when it names a skill or topic, so repeats can be found. The Application, or for `master` the Master resume, must exist first.
   - **Critiques of a resume**: when the user critiques a Tailored resume, log each point with `from: user` and cause `resume-presentation`, and make its Fix direction the Strategy change it calls for, such as "Lead with the platform work". Critiques of the Master resume go to `feedback add <id> master`. Once the user agrees, edit `strategy.md` and cite the entry in the rule, such as `(feedback j-yourator-39119 fb-002)` or `(feedback master fb-001)`, then mark the entry done. Never keep these rules only in your own memory.
2. **Company notes**: when the Feedback says something about the company rather than the Candidate, such as its interview format or what it screens for, add a `company_note`: one sentence, in general terms, naming no one. The script adds it to the company's notes.
3. **Follow through**: `candidate show` lists open Fix directions. Change their state with `feedback update <id> <job> <entry>` and `{"state": "in-progress"}`. When a Fix direction will produce new material, such as a portfolio piece, set `material`. It can only be done once the material is imported: run Import a Source, then update with `{"state": "done", "sources": ["s-008"]}`. New Facts mark the affected Role profiles stale, so offer to rebuild them.
4. **Patterns**: when `feedback add` reports a recurring cause, or the user asks what keeps going wrong, run `feedback patterns [<id>]`. It finds causes in two or more of a Candidate's Applications with a Fix direction still to finish, the topics they share, and the Roles with the cause in two or more Applications. It suggests what each cause means for the Strategy, those Role profiles and open Applications' resumes. Turn that into specific proposals, and make only the changes the user accepts: edit `strategy.md`, `role build`, or `resume save --replace`.
5. **Calibrate**: `feedback calibrate` compares each closed Application's Success rating with how it ended. Hired, or declined after an offer, counts as an offer; rejected as a rejection; withdrawn, and declined without an offer, are left out. It reports offer rates per rating, Applications rated high and rejected or rated low with an offer, which dimensions failed to separate offers from rejections, and rubric changes to consider. Show the user the proposals and how few outcomes they rest on. The script never changes the rubric.

### Search

- `search candidates` with `--tag` (Tag id, label or alias; repeat for AND), `--industry`, `--seniority`, `--status`, `--min-years` and `--text`. It counts only active, sourced Facts and shows which Facts matched each Tag.
- `search candidates` also takes `--role` (an active Role whose title, in either language, or folder name contains the text), `--requirement-tag` and `--no-must-gaps` (the Role's profile is built and no must-have is `missing` or `to-confirm`). Together they apply to the same Role: "Candidates targeting data engineer with no must-have gaps" is `search candidates --role "data engineer" --no-must-gaps`.
- `search facts` with `--candidate`, `--tag`, `--kind`, `--evidence`, `--origin`, `--state`, `--since <year>` and `--text`.
- For a one-sentence request, turn it into these filters. For example, "Candidates with Python and finance background and 5+ years of experience" is `search candidates --tag python --industry finance --min-years 5`.
- For anything the filters cannot express, use `query` on the Index tables: `candidates`, `sources`, `facts`, `fact_tags`, `fact_sources`, `tags`, `tag_terms`, `questions`, `roles`, `role_requirements`, `role_requirement_tags`, `role_evidence`, `role_gaps`, `evaluations`, `evaluation_gaps`, `applications`, `application_timeline`, `feedback`, `feedback_tags`, and the view `candidate_tags` (Tags on active, sourced Facts).

### Read Jobs

Jobs come from links, from files and from copied text. For links, each site is read this way:

| Site | Method |
|---|---|
| Yourator | The script fetches it: Listings through the site's JSON (`job listing`, `--page` for more results), Jobs from the page's schema.org JobPosting data and text (`job fetch`) |
| Company careers pages | The script fetches the page, following its robots.txt; when the site refuses, read it like 104 |
| 104 | Guided: 104 refuses automated requests, including its robots.txt, so the user copies Listings and Jobs are read in a browser or from copied text |
| CakeResume | Guided, like 104: it shows a bot check to automated requests |
| LinkedIn | Only a page open in the user's signed-in browser, or text the user pastes; never fetched, never in bulk |

The script names itself in its User-Agent and follows robots.txt. When a site refuses, shows a CAPTCHA, a bot check or a sign-in wall, in the script or in a browser, stop and ask the user to handle it or paste the content. Never disguise requests or work around a check.

1. **Listing**:
   - Yourator and careers pages: `job listing <url>` lists each Job's title, company, location, salary where the page shows them, and link.
   - 104 and CakeResume: ask the user to open the search results in their own browser, scroll until every Job has loaded (104 keeps loading more as you scroll; CakeResume may need its next-page button), select all, copy, and paste the text here. List each Job's title, company, location and salary from it. The copied text has no links, so ask the user for the links of the Jobs worth reading, or open them by title in a browser you can use.
   - LinkedIn: the user pastes the results, or you read the page they have open in their signed-in browser.
   - A file or text with many Jobs: list them from it the same way. When it already holds each Job's full posting, go straight to step 3 for the ones that pass.

   Screen by title and company against what the user is looking for; skip Jobs marked `*` (already saved) unless the user wants a new reading.
2. **Job**:
   - A link the script may fetch: `job fetch <url>`.
   - A file, or text copied from a browser or pasted by the user: save pasted text to a temporary file outside any repository, then `job fetch [<url>] --file <file>`. HTML files also give the posting's structured data. Add the link when there is one, for the Job id and whether a snapshot exists; without one, `job save` makes the id from company and title.
   - A photo or screenshot: read it if you can see images, save the text to a file, and use `--file`.
3. **Snapshot**: write must-haves, nice-to-haves and duties from the posting, in its wording. Tag each requirement with `taxonomy find`; a term with no Tag goes under `proposed`. Pipe the snapshot as JSON to `job save`, with `text` set to the posting text, `url` when there is one, and `read_with` set to `browser`, `pasted` or `file` when the script did not fetch it.
4. **Report** the saved Jobs and every proposed term. When the user accepts a term, add the Tag to `taxonomy.yml` and run `job accept <term> <tag>`.

## Rules

1. **Every Fact cites its Source.** Record which Source, and where in it, each Fact came from. Content without a Source is not written.
2. **Resumes use sourced Facts only.** Never invent experience, numbers, titles or dates; inferred Facts the user has not confirmed never appear. If a job needs something the candidate lacks, report it as a gap.
3. **Supplement only by asking.** Add information only through follow-up questions and inferences the user confirms. Never search the web or another service for information about a Candidate.
4. **Show conflicts, don't overwrite.** When new input contradicts an existing Fact, list both and ask the user which is right.
5. **Tags come from the Taxonomy.** Propose new Tags; add them only when the user accepts.
6. **Role profiles and Evaluations cite Facts, never change them.** Reference Facts by id; inferred Facts count only as gaps to confirm.
7. **Archive, don't delete.** Deleting a candidate moves their folder to `archive/`.
8. **Success ratings are estimates.** Present them as high / medium / low with reasons, never as a real probability.
9. **LinkedIn by hand only.** Read LinkedIn only from pages the user has open in their signed-in browser or text they paste. Never scrape it in bulk. If any site shows a CAPTCHA or sign-in wall, ask the user to handle it or paste the content.
10. **Read job sites politely.** Follow robots.txt, identify the script honestly, and never work around a refusal or bot check.
11. **Two resumes per job.** Write a Chinese and an English version; use `glossary.yml` so names are translated the same way every time.
12. **Feedback proposes, the user decides.** Changes to a Strategy, Role profile, resume or the rubric that come from Feedback wait for the user's agreement.
13. **One home for each kind of information.** Sources stay as received, your analysis goes into Import reports, resume rules into the Strategy, and critiques into Feedback (see Where information lives). Never keep a decision about a Candidate only in your own memory.
