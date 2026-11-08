# headhunter-agent Domain Context

Shared terms for everyone working on this repository, human or agent. Use these
words in issues, pull requests, documents, and skill instructions.

## Language

**Candidate**:
A person whose job search the agent runs: the user themself, or someone the user
represents. Identified by `c-<number>`. When the user is their own Candidate,
still call them the Candidate when talking about their data and job search.
_Avoid_: user, applicant, profile

**Data folder**:
The local folder that holds all candidate data, `$HEADHUNTER_DATA_DIR` or
`~/headhunter-data/`. Never inside a repository.
_Avoid_: database, storage

**Index**:
`index.sqlite`, rebuilt from the files in the Data folder for search and
classification. Files are the source of truth; the Index can be deleted and
rebuilt at any time.
_Avoid_: database of record

**Source**:
One raw input about a Candidate, such as a note, work log, photo, existing
resume, GitHub repository, or the user's answers to follow-up questions, kept
under `sources/` with an evidence level: documented, third-party, or
self-reported. Identified by `s-<number>`.
_Avoid_: attachment, upload

**Fact**:
One statement about a Candidate's experience, skill, or achievement that cites
the Source it came from. An inferred Fact is drawn from other Facts instead,
and is usable in resumes only after the user confirms it. Identified by
`f-<number>`.
_Avoid_: claim, info, data point

**Import report**:
The result of importing one Source: Facts extracted, missing fields,
conflicts, rejected content, proposed Tags, and follow-up questions.
_Avoid_: import log, quality report

**Tag**:
A classification label on a Fact, taken from the Taxonomy, such as
`skill/python` or `industry/finance`.
_Avoid_: label, keyword, category

**Taxonomy**:
The shared list of Tags in `taxonomy.yml`, each with a fixed id, Chinese and
English labels, and aliases.
_Avoid_: tag list, vocabulary

**Glossary**:
The Candidate's fixed Chinese ↔ English names for companies, titles, and terms,
used so every English resume translates them the same way.
_Avoid_: dictionary, translation memory

**Strategy**:
The Candidate's current plan: which Roles to pursue and in what order,
positioning, and what to strengthen. Updated from Feedback.
_Avoid_: plan, roadmap

**Role**:
A kind of job a Candidate pursues, such as "backend engineer": title, target
level, industries, and must-have and nice-to-have requirements. A Candidate can
have several Roles at once.
_Avoid_: target role, persona, track

**Role profile**:
The Candidate's case for one Role: a positioning summary, the Facts that
support each requirement with reasons, and the gaps. It cites Facts by id and
never changes them.
_Avoid_: role resume, role summary

**Listing**:
Many jobs together: a web page that lists them, such as a search result page
on 104 or CakeResume, or a file or copied text that holds several.
_Avoid_: feed, board

**Job**:
One job posting, stored as a snapshot of its content at the time it was read:
must-haves and nice-to-haves with Tags, duties, salary, location, and the
posting text. Identified by `j-<site>-<site id>`; a page on any other site uses
its host name and a hash of its URL, and a Job the user gave without a link
uses `j-user-` and a hash of its company and title.
_Avoid_: JD, position, opening

**Application**:
One Candidate × Job pair, from when the Job is picked up or first evaluated until
it is closed. It records its Role, Stage, a dated timeline, and a next step with
a due date while open.
_Avoid_: submission, match, pipeline item

**Stage**:
Where an Application is: found, evaluated, preparing, applied, interview
(round N), offer, or closed (hired, declined, rejected, withdrawn).
_Avoid_: status (reserved for issue labels)

**Evaluation**:
The assessment of one Application, made for one of the Candidate's Roles, or
against all of the Candidate's Facts when no Role fits: Fit score, reasons tied
to Facts and Job requirements, gaps and risks, and a Success rating.
_Avoid_: review, analysis

**Fit score**:
An Evaluation's score from 0 to 100: the weighted sum of skill overlap,
seniority, industry and domain, achievement evidence, and salary, location and
work mode.
_Avoid_: match score, fit percentage

**Hard requirement**:
A must-have that gates a Job instead of adding to the Fit score: a degree,
minimum years, or a required certificate or language. Failing one lowers the
Success rating by one level.
_Avoid_: knockout, deal-breaker

**Success rating**:
High, medium, or low, with reasons, from the Fit score and the Hard
requirements. A rule-based estimate, never a probability.
_Avoid_: success probability, chance, odds

**Tailored resume**:
The pair of resumes written for one Application, one in Chinese and one in
English, starting from the Role profile of the Application's Role and using only
sourced Facts, each line citing the Facts it comes from.
_Avoid_: CV variant, generated resume

**Feedback**:
One piece of input about how an Application went, from HR, an interviewer, the
Candidate, or the user, with its cause: skill gap, experience, communication,
salary, culture fit, or resume presentation.
_Avoid_: comment, note

**Fix direction**:
A concrete action that responds to Feedback, with its own completion state. One
that produces new material ends with importing it as a Source.
_Avoid_: suggestion, todo

**Company notes**:
What has been learned about one company across all Candidates' Feedback.
_Avoid_: company profile, research
