# headhunter-agent Domain Context

Shared terms for everyone working on this repository, human or agent. Use these
words in issues, pull requests, documents, and skill instructions.

## Language

**Candidate**:
A person the user represents in their job search. Identified by `c-<number>`.
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
One raw input about a Candidate: a note, work log, photo, existing resume, or
GitHub repository, kept under `sources/`.
_Avoid_: attachment, upload

**Fact**:
One statement about a Candidate's experience, skill, or achievement that cites
the Source it came from.
_Avoid_: claim, info, data point

**Glossary**:
The Candidate's fixed Chinese ↔ English names for companies, titles, and terms,
used so every English resume translates them the same way.
_Avoid_: dictionary, translation memory

**Strategy**:
The Candidate's current plan: target roles, positioning, and what to strengthen.
Updated from Feedback.
_Avoid_: plan, roadmap

**Listing**:
A web page that lists many jobs, such as a search result page on 104 or
CakeResume.
_Avoid_: feed, board

**Job**:
One job posting, stored as a snapshot of its content at the time it was read.
Identified by `j-<site>-<site id>`.
_Avoid_: JD, position, opening

**Application**:
One Candidate × Job pair, from the first Evaluation until it is closed.
_Avoid_: submission, match, pipeline item

**Stage**:
Where an Application is: found, evaluated, preparing, applied, interview
(round N), offer, or closed (hired, declined, rejected, withdrawn).
_Avoid_: status (reserved for issue labels)

**Evaluation**:
The assessment of one Application: fit score, reasons for the recommendation,
gaps and risks, and a Success rating.
_Avoid_: review, analysis

**Success rating**:
High, medium, or low, with reasons. A rule-based estimate, never a probability.
_Avoid_: success probability, chance, odds

**Tailored resume**:
The pair of resumes written for one Application, one in Chinese and one in
English, using only Facts.
_Avoid_: CV variant, generated resume

**Feedback**:
One piece of input about how an Application went, from HR, an interviewer, the
Candidate, or the user, with its cause.
_Avoid_: comment, note

**Fix direction**:
A concrete action that responds to Feedback, with its own completion state.
_Avoid_: suggestion, todo

**Company notes**:
What has been learned about one company across all Candidates' Feedback.
_Avoid_: company profile, research
