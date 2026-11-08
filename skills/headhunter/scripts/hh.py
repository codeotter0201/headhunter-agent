#!/usr/bin/env python3
"""headhunter helper: fixed, repeatable operations on the Data folder.

Usage: python3 hh.py <command> [options]; run with --help for the commands.
Needs only the Python 3.9+ standard library. Work that needs judgment, such as
extracting Facts or writing Import reports, is done by the agent following
SKILL.md; this script assigns ids, moves folders, validates files, and builds
and queries the Index.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time
import unicodedata
import zipfile
import zlib
from collections import Counter
from html import escape
from pathlib import Path
from typing import Any
from xml.etree import ElementTree

sys.dont_write_bytecode = True  # keep the plugin folder free of __pycache__
sys.path.insert(0, str(Path(__file__).resolve().parent))
import hhweb  # noqa: E402
import hhyaml  # noqa: E402

SKILL_DIR = Path(__file__).resolve().parent.parent
PLUGIN_ROOT = SKILL_DIR.parent.parent
STARTER_TAXONOMY = SKILL_DIR / "assets" / "taxonomy.yml"
LAYOUT = ("candidates", "jobs", "companies", "archive")

SOURCE_TYPES = ("note", "work-log", "photo", "resume", "github", "interview", "other")
EVIDENCE = ("documented", "third-party", "self-reported")  # strongest first
SOURCE_STATES = ("read", "partly-readable", "unreadable")
FACT_KINDS = ("experience", "project", "achievement", "skill", "education", "certificate")
ORIGINS = ("sourced", "inferred")
FACT_STATES = ("active", "conflict", "superseded")
MISSING_FIELDS = ("who", "what", "when", "where", "result")
CANDIDATE_STATUS = ("active", "paused", "closed")
SENIORITY = ("intern", "junior", "mid", "senior", "lead", "manager", "director", "executive")
GLOSSARY_KINDS = ("company", "title", "school", "term")
DEFAULT_EVIDENCE = {
    "note": "self-reported",
    "work-log": "self-reported",
    "resume": "self-reported",
    "interview": "self-reported",
    "github": "third-party",
}
FACT_ORDER = (
    "id", "kind", "statement", "org", "period", "tags", "sources", "evidence", "origin",
    "derived_from", "reasoning", "missing", "state", "conflicts_with", "superseded_by",
)
REPORT_SECTIONS = (
    "Facts extracted", "Missing fields", "Conflicts", "Rejected", "Proposed Tags", "Follow-up questions",
)
READ_WITH = ("fetch", "browser", "pasted", "file")
ROLE_STATES = ("active", "paused", "dropped")
REQUIREMENT_KINDS = ("must", "nice")
REQUIREMENT_ORIGINS = ("user", "assumed", "job")
GAP_KINDS = ("missing", "to-confirm", "weak-evidence")
ROLE_ORDER = ("title", "level", "industries", "priority", "state", "created", "requirements")
REQUIREMENT_ORDER = ("id", "kind", "text", "tags", "origin", "jobs")
JOB_ORDER = (
    "id", "site", "site_id", "url", "title", "company", "location", "salary", "work_mode",
    "employment_type", "posted", "read", "read_with", "must_haves", "nice_to_haves", "duties",
)
HARD_KINDS = ("degree", "years", "certificate", "language")
CONDITIONS = ("salary", "location", "work_mode")
CONDITION_FITS = {"match": 100, "partial": 50, "mismatch": 0, "unknown": 50}
RUBRIC = (  # dimension, weight in percent, label
    ("skills", 35, "Skill overlap"),
    ("seniority", 20, "Seniority"),
    ("industry", 20, "Industry and domain"),
    ("achievements", 15, "Achievement evidence"),
    ("conditions", 10, "Salary, location, work mode"),
)
RATINGS = ("high", "medium", "low")
RATING_FLOORS = (75, 55, 0)  # lowest fit score for each rating
INDEX_VERSION = 2  # raise when SCHEMA changes, so existing indexes are rebuilt
STAGES = ("found", "evaluated", "preparing", "applied", "interview", "offer", "closed")
OUTCOMES = ("hired", "declined", "rejected", "withdrawn")
STATUS_ORDER = ("job", "role", "stage", "round", "outcome", "next_step", "due", "timeline")
DECIDE_STEP, DECIDE_DAYS = "Decide whether to apply", 7  # the next step an Evaluation leaves
RESUME_LANGS = ("zh", "en")
RESUME_HEADINGS = {
    "zh": {"experience": "工作經歷", "projects": "專案", "education": "學歷", "certificates": "證照", "skills": "技能"},
    "en": {"experience": "Experience", "projects": "Projects", "education": "Education", "certificates": "Certificates",
           "skills": "Skills"},
}
RESUME_FIELDS = ("headline", "summary", "experience", "projects", "education", "certificates", "skills")
BROWSERS = (  # Chrome, Chromium or Edge, used headless to print resumes to PDF
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
    "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
    "google-chrome", "google-chrome-stable", "chromium", "chromium-browser", "microsoft-edge", "msedge", "chrome",
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
)
HAN = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]")
NUMBER = re.compile(r"\d+(?:\.\d+)?")
CITATION = re.compile(r"\s*<!-- ((?:f-\d+|profile)(?:, (?:f-\d+|profile))*) -->$")
QUESTION_LINE = re.compile(r"^\s*- \[( |x|X)\] (q-\d+):?\s*(.*)$")
YEAR_MONTH = re.compile(r"^(\d{4})(?:-(\d{2}))?$")
DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class HHError(Exception):
    pass


def today() -> str:
    return dt.date.today().isoformat()


# ---------------------------------------------------------------- data folder


def guard(path: Path) -> None:
    if path == PLUGIN_ROOT or PLUGIN_ROOT in path.parents:
        raise HHError(
            f"the Data folder {path} is inside the plugin folder {PLUGIN_ROOT}. "
            "Set HEADHUNTER_DATA_DIR to a folder outside it."
        )
    for parent in (path, *path.parents):
        if (parent / ".git").exists():
            raise HHError(
                f"the Data folder {path} is inside the git working tree at {parent}. "
                "Candidate data must never enter a repository; set HEADHUNTER_DATA_DIR "
                "to a folder outside any git repository."
            )


def ensure_layout(root: Path) -> list:
    created = []
    if not root.exists():
        root.mkdir(parents=True)
        created.append(str(root))
    for name in LAYOUT:
        if not (root / name).exists():
            (root / name).mkdir()
            created.append(f"{name}/")
    if not (root / "taxonomy.yml").exists():
        shutil.copyfile(STARTER_TAXONOMY, root / "taxonomy.yml")
        created.append("taxonomy.yml")
    return created


def data_dir() -> Path:
    raw = os.environ.get("HEADHUNTER_DATA_DIR") or "~/headhunter-data"
    root = Path(raw).expanduser().resolve()
    guard(root)
    ensure_layout(root)
    return root


def read_yaml(path: Path, default=None):
    if not path.exists():
        return default
    try:
        value = hhyaml.load(path)
    except hhyaml.YamlError as exc:
        raise HHError(f"{path}: {exc}") from None
    return default if value is None else value


def read_list(path: Path) -> list:
    value = read_yaml(path, [])
    if not isinstance(value, list):
        raise HHError(f"{path} must be a YAML list")
    return value


def write_yaml(path: Path, obj) -> None:
    tmp = path.with_name(path.name + ".tmp")
    hhyaml.dump(obj, tmp)
    os.replace(tmp, path)


# ---------------------------------------------------------------- ids and candidates


def id_number(value, prefix: str):
    match = re.fullmatch(prefix + r"-(\d+)", str(value))
    return int(match.group(1)) if match else None


def make_id(prefix: str, number: int) -> str:
    return f"{prefix}-{number:03d}"


def next_number(ids, prefix: str) -> int:
    return max((id_number(i, prefix) or 0 for i in ids), default=0) + 1


def candidate_id(text: str) -> str:
    match = re.fullmatch(r"(?:c-)?(\d+)", text.strip().lower())
    if not match:
        raise HHError(f"{text!r} is not a Candidate id such as c-001")
    return make_id("c", int(match.group(1)))


def candidate_dirs(root: Path, archived: bool = False) -> list:
    base = root / ("archive" if archived else "candidates")
    found = []
    for folder in base.iterdir() if base.exists() else []:
        match = re.match(r"^(c-\d+)(?:-|$)", folder.name)
        if folder.is_dir() and match:
            found.append((match.group(1), folder))
    return sorted(found, key=lambda item: id_number(item[0], "c") or 0)


def find_candidate(root: Path, text: str, archived=None) -> Path:
    cid = candidate_id(text)
    for is_archived in (False, True):
        for found, folder in candidate_dirs(root, is_archived):
            if found == cid:
                if archived is not None and archived != is_archived:
                    state = "archived" if is_archived else "not archived"
                    raise HHError(f"{cid} is {state}")
                return folder
    raise HHError(f"no Candidate {cid} in {root}")


def slugify(name: str) -> str:
    text = unicodedata.normalize("NFC", name).strip().lower()
    text = re.sub(r"\s+", "-", text)
    text = "".join(ch for ch in text if ch == "-" or ch.isalnum())
    return re.sub(r"-+", "-", text).strip("-") or "candidate"


def safe_filename(name: str) -> str:
    stem = "".join(ch if ch.isalnum() or ch in ".-_" else "-" for ch in unicodedata.normalize("NFC", name))
    return re.sub(r"-+", "-", stem).strip("-.") or "source"


def load_candidate(folder: Path) -> dict:
    return {
        "profile": read_yaml(folder / "profile.yml", {}),
        "sources": read_list(folder / "sources.yml"),
        "facts": read_list(folder / "facts.yml"),
        "glossary": read_yaml(folder / "glossary.yml", []),
    }


def report_questions(folder: Path) -> list:
    questions = []
    for report in sorted((folder / "imports").glob("*.md")):
        section = None
        for line in report.read_text(encoding="utf-8").splitlines():
            if line.startswith("## "):
                section = line[3:].strip().lower()
                continue
            if section == "follow-up questions":
                match = QUESTION_LINE.match(line)
                if match:
                    questions.append({
                        "id": match.group(2),
                        "open": match.group(1) == " ",
                        "text": match.group(3).strip(),
                        "report": report.name,
                    })
    return questions


# ---------------------------------------------------------------- taxonomy


def load_taxonomy(root: Path) -> dict:
    taxonomy = read_yaml(root / "taxonomy.yml", {})
    if not isinstance(taxonomy, dict):
        raise HHError("taxonomy.yml must be a mapping with dimensions and tags")
    return taxonomy


def tag_ids(taxonomy: dict) -> set:
    return {tag.get("id") for tag in taxonomy.get("tags") or [] if isinstance(tag, dict)}


def tag_terms(taxonomy: dict) -> dict:
    terms = {}
    for tag in taxonomy.get("tags") or []:
        if not isinstance(tag, dict):
            continue
        for term in [tag.get("id"), tag.get("en"), tag.get("zh"), *(tag.get("aliases") or [])]:
            if term:
                terms.setdefault(str(term).strip().lower(), tag.get("id"))
    return terms


def resolve_tag(taxonomy: dict, text: str, dimension: str | None = None) -> str:
    term = text.strip().lower()
    ids = tag_ids(taxonomy)
    if dimension and "/" not in term and f"{dimension}/{term.replace(' ', '-')}" in ids:
        return f"{dimension}/{term.replace(' ', '-')}"
    found = term if term in ids else tag_terms(taxonomy).get(term)
    if found and (dimension is None or found.startswith(dimension + "/")):
        return found
    scope = f" in the {dimension} dimension" if dimension else ""
    raise HHError(f"{text!r} is not a Tag{scope}; run `taxonomy find {text}`")


def validate_taxonomy(taxonomy: dict) -> list:
    errors = []
    dimensions = taxonomy.get("dimensions")
    if not isinstance(dimensions, list) or not dimensions:
        return ["taxonomy.yml: dimensions must be a non-empty list"]
    seen_ids, seen_terms = set(), {}
    for n, tag in enumerate(taxonomy.get("tags") or [], 1):
        if not isinstance(tag, dict):
            errors.append(f"taxonomy.yml: tag {n} is not a mapping")
            continue
        tid = str(tag.get("id") or "")
        where = f"taxonomy.yml: {tid or 'tag ' + str(n)}"
        if not re.fullmatch(r"[a-z0-9-]+/[a-z0-9+#.-]+", tid) or tid.split("/")[0] not in dimensions:
            errors.append(f"{where}: id must be <dimension>/<slug> with a listed dimension")
        if tid in seen_ids:
            errors.append(f"{where}: duplicate id")
        seen_ids.add(tid)
        for key in ("en", "zh"):
            if not str(tag.get(key) or "").strip():
                errors.append(f"{where}: {key} label is required")
        aliases = tag.get("aliases") or []
        if not isinstance(aliases, list):
            errors.append(f"{where}: aliases must be a list")
            aliases = []
        for term in {str(t).strip().lower() for t in [tid, tag.get("en"), tag.get("zh"), *aliases] if t}:
            other = seen_terms.get(term)
            if other and other != tid:
                errors.append(f"{where}: term {term!r} already belongs to {other}")
            seen_terms[term] = tid
    return errors


# ---------------------------------------------------------------- facts


def parse_period(value):
    text = str(value).strip()
    first, sep, last = text.partition("..")
    start_match = YEAR_MONTH.match(first)
    if not start_match:
        return None
    start = (int(start_match.group(1)), int(start_match.group(2) or 1))
    if not sep:
        end = (start[0], int(start_match.group(2) or 12))
    elif last in ("present", ""):
        end = "present"
    else:
        end_match = YEAR_MONTH.match(last)
        if not end_match:
            return None
        end = (int(end_match.group(1)), int(end_match.group(2) or 12))
    for point in (start, end):
        if point != "present" and not 1 <= point[1] <= 12:
            return None
    if end != "present" and end < start:
        return None
    return start, end


def month_index(point) -> int:
    return point[0] * 12 + point[1] - 1


def period_months(value):
    parsed = parse_period(value) if value is not None else None
    if not parsed:
        return None, None
    start, end = parsed
    return month_index(start), (None if end == "present" else month_index(end))


def years_experience(facts: list) -> float:
    now = month_index((dt.date.today().year, dt.date.today().month))
    spans = []
    for fact in facts:
        if fact.get("kind") != "experience" or fact.get("state") != "active" or fact.get("origin") != "sourced":
            continue
        start, end = period_months(fact.get("period"))
        if start is not None:
            spans.append((start, (now if end is None else end) + 1))
    total, current_end = 0, None
    for start, end in sorted(spans):
        if current_end is None or start > current_end:
            total += end - start
            current_end = end
        elif end > current_end:
            total += end - current_end
            current_end = end
    return round(total / 12, 1)


def ordered_fact(fact: dict) -> dict:
    out = {key: fact[key] for key in FACT_ORDER if key in fact}
    out.update({key: value for key, value in fact.items() if key not in out})
    return out


def apply_evidence(facts: list, sources: list) -> None:
    levels = {s.get("id"): s.get("evidence") for s in sources if isinstance(s, dict)}
    for fact in facts:
        if not isinstance(fact, dict):
            continue
        if fact.get("origin") == "sourced":
            cited = [levels.get(c.get("id")) for c in fact.get("sources") or [] if isinstance(c, dict)]
            ranks = [EVIDENCE.index(level) for level in cited if level in EVIDENCE]
            if ranks:
                fact["evidence"] = EVIDENCE[min(ranks)]
        else:
            fact.pop("evidence", None)


def check_facts(facts: list, sources: list, known_tags: set) -> list:
    errors = []
    source_ids = {s.get("id") for s in sources if isinstance(s, dict)}
    levels = {s.get("id"): s.get("evidence") for s in sources if isinstance(s, dict)}
    seen = set()
    for n, fact in enumerate(facts, 1):
        if not isinstance(fact, dict):
            errors.append(f"fact entry {n} is not a mapping")
            continue
        fid = fact.get("id")
        where = f"fact {fid or '#' + str(n)}"
        if id_number(fid, "f") is None:
            errors.append(f"{where}: id must look like f-001")
        elif fid in seen:
            errors.append(f"{where}: duplicate id")
        seen.add(fid)
        if fact.get("kind") not in FACT_KINDS:
            errors.append(f"{where}: kind must be one of {', '.join(FACT_KINDS)}")
        if not str(fact.get("statement") or "").strip():
            errors.append(f"{where}: statement is required")
        if fact.get("period") is not None and parse_period(fact["period"]) is None:
            errors.append(f"{where}: period must look like 2023-03..2024-06, 2021..present or 2024-05")
        tags = fact.get("tags")
        if not isinstance(tags, list) or not tags:
            errors.append(f"{where}: needs at least one Tag")
        else:
            for tag in tags:
                if tag not in known_tags:
                    errors.append(f"{where}: Tag {tag!r} is not in taxonomy.yml; propose it in the Import report")
        origin = fact.get("origin")
        if origin not in ORIGINS:
            errors.append(f"{where}: origin must be sourced or inferred")
        cites = fact.get("sources")
        if not isinstance(cites, list):
            errors.append(f"{where}: sources must be a list")
            cites = []
        for cite in cites:
            if not isinstance(cite, dict) or not cite.get("id") or cite.get("at") in (None, ""):
                errors.append(f"{where}: each source needs id and at (where in the Source)")
            elif cite["id"] not in source_ids:
                errors.append(f"{where}: cites unknown Source {cite['id']}")
        if origin == "sourced":
            if not cites:
                errors.append(f"{where}: a sourced Fact must cite at least one Source")
            ranks = [EVIDENCE.index(levels[c["id"]]) for c in cites
                     if isinstance(c, dict) and levels.get(c.get("id")) in EVIDENCE]
            if ranks and fact.get("evidence") != EVIDENCE[min(ranks)]:
                errors.append(f"{where}: evidence must be {EVIDENCE[min(ranks)]}, the strongest of its Sources")
        if origin == "inferred":
            if not fact.get("derived_from"):
                errors.append(f"{where}: an inferred Fact needs derived_from")
            if not str(fact.get("reasoning") or "").strip():
                errors.append(f"{where}: an inferred Fact needs reasoning")
            if "evidence" in fact:
                errors.append(f"{where}: an inferred Fact has no evidence level until it is confirmed")
        missing = fact.get("missing") or []
        if not isinstance(missing, list) or any(m not in MISSING_FIELDS for m in missing):
            errors.append(f"{where}: missing may list only {', '.join(MISSING_FIELDS)}")
        state = fact.get("state")
        if state not in FACT_STATES:
            errors.append(f"{where}: state must be one of {', '.join(FACT_STATES)}")
        if state == "conflict" and not fact.get("conflicts_with"):
            errors.append(f"{where}: a conflict Fact needs conflicts_with")
        if state == "superseded" and not fact.get("superseded_by"):
            errors.append(f"{where}: a superseded Fact needs superseded_by")
    for fact in facts:
        if not isinstance(fact, dict):
            continue
        refs = list(fact.get("derived_from") or []) + list(fact.get("conflicts_with") or [])
        if fact.get("superseded_by"):
            refs.append(fact["superseded_by"])
        for ref in refs:
            if ref not in seen:
                errors.append(f"fact {fact.get('id')}: refers to unknown Fact {ref}")
    return errors


def read_payload(args):
    text = Path(args.file).read_text(encoding="utf-8") if args.file else sys.stdin.read()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        try:
            return hhyaml.loads(text)
        except hhyaml.YamlError as exc:
            raise HHError(f"input is neither JSON nor YAML: {exc}") from None


def save_facts(root: Path, folder: Path, facts: list, sources: list) -> None:
    apply_evidence(facts, sources)
    errors = check_facts(facts, sources, tag_ids(load_taxonomy(root)))
    if errors:
        raise HHError("nothing written:\n  " + "\n  ".join(errors))
    write_yaml(folder / "facts.yml", [ordered_fact(f) for f in facts])


# ---------------------------------------------------------------- validation


def validate_candidate(folder: Path, known_tags: set) -> list:
    errors = []
    name = folder.name

    def err(message):
        errors.append(f"{name}: {message}")

    try:
        data = load_candidate(folder)
    except HHError as exc:
        return [str(exc)]
    profile, sources, facts, glossary = data["profile"], data["sources"], data["facts"], data["glossary"]
    if not isinstance(profile, dict):
        return [f"{name}: profile.yml must be a mapping"]
    if not name.startswith(str(profile.get("id")) + "-") and name != profile.get("id"):
        err("profile.yml id does not match the folder name")
    if not str(profile.get("name") or "").strip():
        err("profile.yml needs a name")
    if profile.get("status") not in CANDIDATE_STATUS:
        err(f"profile.yml status must be one of {', '.join(CANDIDATE_STATUS)}")
    if profile.get("seniority") not in (None, *SENIORITY):
        err(f"profile.yml seniority must be one of {', '.join(SENIORITY)}")
    for required in ("strategy.md", "sources", "imports"):
        if not (folder / required).exists():
            err(f"{required} is missing")
    if not isinstance(sources, list):
        err("sources.yml must be a list")
        sources = []
    seen = set()
    for n, source in enumerate(sources, 1):
        if not isinstance(source, dict):
            err(f"source entry {n} is not a mapping")
            continue
        sid = source.get("id")
        where = f"source {sid or '#' + str(n)}"
        if id_number(sid, "s") is None:
            err(f"{where}: id must look like s-001")
        elif sid in seen:
            err(f"{where}: duplicate id")
        seen.add(sid)
        checks = (
            ("type", SOURCE_TYPES), ("evidence", EVIDENCE), ("state", SOURCE_STATES),
        )
        for key, allowed in checks:
            if source.get(key) not in allowed:
                err(f"{where}: {key} must be one of {', '.join(allowed)}")
        if not str(source.get("origin") or "").strip():
            err(f"{where}: origin is required")
        if not DATE.match(str(source.get("received") or "")):
            err(f"{where}: received must be a date such as 2026-01-31")
        if not source.get("file") or not (folder / str(source["file"])).is_file():
            err(f"{where}: file {source.get('file')!r} not found")
    if not isinstance(facts, list):
        err("facts.yml must be a list")
    else:
        errors.extend(f"{name}: {e}" for e in check_facts(facts, sources, known_tags))
    if not isinstance(glossary, list):
        err("glossary.yml must be a list")
    else:
        zh_seen, en_seen = set(), set()
        for n, entry in enumerate(glossary, 1):
            if not isinstance(entry, dict) or not entry.get("zh") or not entry.get("en"):
                err(f"glossary entry {n} needs zh and en")
                continue
            if entry.get("kind") not in GLOSSARY_KINDS:
                err(f"glossary entry {entry['zh']}: kind must be one of {', '.join(GLOSSARY_KINDS)}")
            if entry["zh"] in zh_seen or str(entry["en"]).lower() in en_seen:
                err(f"glossary entry {entry['zh']} / {entry['en']}: each name may have only one pair")
            zh_seen.add(entry["zh"])
            en_seen.add(str(entry["en"]).lower())
    question_ids = [q["id"] for q in report_questions(folder)]
    for qid, count in Counter(question_ids).items():
        if count > 1:
            err(f"follow-up question {qid} appears {count} times")
    for slug, path in role_dirs(folder):
        try:
            role = load_role(path)
        except HHError as exc:
            err(str(exc))
            continue
        errors.extend(f"{name}: {e}" for e in check_role(role, slug, folder, known_tags))
        if (path / "profile.md").exists():
            try:
                front, _ = read_job(path / "profile.md")
            except HHError as exc:
                err(str(exc))
                continue
            if front.get("role") != slug:
                err(f"role {slug}: profile.md names the Role {front.get('role')!r}")
            if any(g.get("kind") not in GAP_KINDS for g in front.get("gaps") or [] if isinstance(g, dict)):
                err(f"role {slug}: gap kinds must be {', '.join(GAP_KINDS)}")
    by_id = {f.get("id"): f for f in facts if isinstance(f, dict)} if isinstance(facts, list) else {}
    fact_ids = set(by_id)
    for jid, path in evaluation_files(folder):
        try:
            front, _ = read_job(path)
        except HHError as exc:
            err(str(exc))
            continue
        errors.extend(f"{name}: {e}" for e in check_evaluation(front, jid, folder, fact_ids))
    for jid, lang, path in resume_files(folder):
        if lang not in RESUME_LANGS:
            err(f"resume {jid}: {path.name} must be resume.zh.md or resume.en.md")
            continue
        errors.extend(f"{name}: {e}" for e in check_resume(path, lang, by_id))
    for jid, path in application_dirs(folder):
        if not (path / "status.yml").exists():
            if (path / "evaluation.md").exists() or list(path.glob("resume.*")):
                err(f"application {jid}: status.yml is missing; run application sync")
            continue
        try:
            status = read_yaml(path / "status.yml", {})
        except HHError as exc:
            err(str(exc))
            continue
        errors.extend(f"{name}: {e}" for e in check_status(status, jid, folder))
    return errors


# ---------------------------------------------------------------- index

SCHEMA = """
CREATE TABLE candidates (id TEXT PRIMARY KEY, name TEXT, name_en TEXT, folder TEXT,
  status TEXT, seniority TEXT, location TEXT, years_experience REAL, created TEXT);
CREATE TABLE sources (candidate_id TEXT, id TEXT, type TEXT, origin TEXT, received TEXT,
  evidence TEXT, state TEXT, file TEXT, PRIMARY KEY (candidate_id, id));
CREATE TABLE facts (candidate_id TEXT, id TEXT, kind TEXT, statement TEXT, org TEXT,
  period TEXT, start_month INTEGER, end_month INTEGER, evidence TEXT, origin TEXT,
  state TEXT, missing TEXT, PRIMARY KEY (candidate_id, id));
CREATE TABLE fact_tags (candidate_id TEXT, fact_id TEXT, tag TEXT);
CREATE TABLE fact_sources (candidate_id TEXT, fact_id TEXT, source_id TEXT, at TEXT);
CREATE TABLE tags (id TEXT PRIMARY KEY, dimension TEXT, en TEXT, zh TEXT);
CREATE TABLE tag_terms (term TEXT, tag TEXT);
CREATE TABLE questions (candidate_id TEXT, id TEXT, text TEXT, report TEXT, open INTEGER);
CREATE TABLE roles (candidate_id TEXT, slug TEXT, title TEXT, title_other TEXT, level TEXT,
  state TEXT, priority INTEGER, built TEXT, stale INTEGER, PRIMARY KEY (candidate_id, slug));
CREATE TABLE role_requirements (candidate_id TEXT, role TEXT, id TEXT, kind TEXT, text TEXT, origin TEXT);
CREATE TABLE role_requirement_tags (candidate_id TEXT, role TEXT, requirement TEXT, tag TEXT);
CREATE TABLE role_evidence (candidate_id TEXT, role TEXT, requirement TEXT, fact_id TEXT, why TEXT);
CREATE TABLE role_gaps (candidate_id TEXT, role TEXT, requirement TEXT, kind TEXT);
CREATE TABLE evaluations (candidate_id TEXT, job_id TEXT, role TEXT, evaluated TEXT, score INTEGER,
  rating TEXT, gate TEXT, PRIMARY KEY (candidate_id, job_id));
CREATE TABLE evaluation_gaps (candidate_id TEXT, job_id TEXT, requirement TEXT, kind TEXT);
CREATE TABLE applications (candidate_id TEXT, job_id TEXT, role TEXT, company TEXT, title TEXT, stage TEXT,
  round INTEGER, outcome TEXT, next_step TEXT, due TEXT, PRIMARY KEY (candidate_id, job_id));
CREATE TABLE application_timeline (candidate_id TEXT, job_id TEXT, stage TEXT, round INTEGER, date TEXT, note TEXT);
CREATE VIEW candidate_tags AS
  SELECT DISTINCT f.candidate_id, t.tag FROM facts f
  JOIN fact_tags t ON t.candidate_id = f.candidate_id AND t.fact_id = f.id
  WHERE f.state = 'active' AND f.origin = 'sourced';
"""


def rebuild_index(root: Path) -> dict:
    taxonomy = load_taxonomy(root)
    tmp = root / "index.sqlite.tmp"
    if tmp.exists():
        tmp.unlink()
    con = sqlite3.connect(str(tmp))
    con.executescript(SCHEMA)
    for tag in taxonomy.get("tags") or []:
        if isinstance(tag, dict) and tag.get("id"):
            tid = str(tag["id"])
            con.execute("INSERT OR IGNORE INTO tags VALUES (?, ?, ?, ?)",
                        (tid, tid.split("/")[0], tag.get("en"), tag.get("zh")))
    con.executemany("INSERT INTO tag_terms VALUES (?, ?)", tag_terms(taxonomy).items())
    counts = Counter()
    for cid, folder in candidate_dirs(root):
        data = load_candidate(folder)
        profile, facts = data["profile"], data["facts"]
        con.execute("INSERT INTO candidates VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", (
            cid, profile.get("name"), profile.get("name_en"), folder.name, profile.get("status"),
            profile.get("seniority"), profile.get("location"), years_experience(facts),
            str(profile.get("created") or ""),
        ))
        for s in data["sources"]:
            con.execute("INSERT INTO sources VALUES (?, ?, ?, ?, ?, ?, ?, ?)", (
                cid, s.get("id"), s.get("type"), s.get("origin"), str(s.get("received")),
                s.get("evidence"), s.get("state"), s.get("file"),
            ))
        for f in facts:
            start, end = period_months(f.get("period"))
            con.execute("INSERT INTO facts VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (
                cid, f.get("id"), f.get("kind"), f.get("statement"), f.get("org"),
                None if f.get("period") is None else str(f["period"]), start, end,
                f.get("evidence"), f.get("origin"), f.get("state"), ",".join(f.get("missing") or []),
            ))
            con.executemany("INSERT INTO fact_tags VALUES (?, ?, ?)",
                            [(cid, f.get("id"), t) for t in f.get("tags") or []])
            con.executemany("INSERT INTO fact_sources VALUES (?, ?, ?, ?)",
                            [(cid, f.get("id"), c.get("id"), str(c.get("at"))) for c in f.get("sources") or []])
        for q in report_questions(folder):
            con.execute("INSERT INTO questions VALUES (?, ?, ?, ?, ?)",
                        (cid, q["id"], q["text"], q["report"], int(q["open"])))
        titles = glossary_titles(data["glossary"])
        for slug, path in role_dirs(folder):
            role = load_role(path)
            front = read_job(path / "profile.md")[0] if (path / "profile.md").exists() else {}
            con.execute("INSERT INTO roles VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", (
                cid, slug, role.get("title"), titles.get(str(role.get("title"))), role.get("level"), role.get("state"),
                role.get("priority"), front.get("built"), int(bool(role_stale(path, role, facts))),
            ))
            for req in role.get("requirements") or []:
                con.execute("INSERT INTO role_requirements VALUES (?, ?, ?, ?, ?, ?)",
                            (cid, slug, req.get("id"), req.get("kind"), req.get("text"), req.get("origin")))
                con.executemany("INSERT INTO role_requirement_tags VALUES (?, ?, ?, ?)",
                                [(cid, slug, req.get("id"), t) for t in req.get("tags") or []])
            for entry in front.get("evidence") or []:
                con.executemany("INSERT INTO role_evidence VALUES (?, ?, ?, ?, ?)",
                                [(cid, slug, entry.get("requirement"), c.get("id"), c.get("why"))
                                 for c in entry.get("facts") or []])
            con.executemany("INSERT INTO role_gaps VALUES (?, ?, ?, ?)",
                            [(cid, slug, g.get("requirement"), g.get("kind")) for g in front.get("gaps") or []])
            counts["roles"] += 1
        for jid, path in evaluation_files(folder):
            ev = read_job(path)[0]
            con.execute("INSERT INTO evaluations VALUES (?, ?, ?, ?, ?, ?, ?)", (
                cid, jid, ev.get("role"), str(ev.get("evaluated") or ""), ev.get("score"), ev.get("rating"),
                ev.get("gate"),
            ))
            con.executemany("INSERT INTO evaluation_gaps VALUES (?, ?, ?, ?)",
                            [(cid, jid, g.get("requirement"), g.get("kind")) for g in ev.get("gaps") or []])
            counts["evaluations"] += 1
        for jid, path in application_dirs(folder):
            if not (path / "status.yml").exists():
                continue
            status = read_yaml(path / "status.yml", {})
            job_path = root / "jobs" / f"{jid}.md"
            job = read_job(job_path)[0] if job_path.exists() else {}
            con.execute("INSERT INTO applications VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (
                cid, jid, status.get("role"), job.get("company"), job.get("title"), status.get("stage"),
                status.get("round"), status.get("outcome"), status.get("next_step"),
                None if status.get("due") is None else str(status["due"]),
            ))
            con.executemany("INSERT INTO application_timeline VALUES (?, ?, ?, ?, ?, ?)",
                            [(cid, jid, e.get("stage"), e.get("round"), str(e.get("date")), e.get("note"))
                             for e in status.get("timeline") or []])
            counts["applications"] += 1
        counts["candidates"] += 1
        counts["facts"] += len(facts)
    con.execute(f"PRAGMA user_version = {INDEX_VERSION}")
    con.commit()
    con.close()
    os.replace(tmp, root / "index.sqlite")
    return counts


def index_stale(root: Path) -> bool:
    index = root / "index.sqlite"
    if not index.exists():
        return True
    built = index.stat().st_mtime
    paths = [root / "taxonomy.yml", root / "candidates", root / "jobs", *job_files(root)]
    for _, folder in candidate_dirs(root):
        paths += [folder, folder / "profile.yml", folder / "sources.yml", folder / "facts.yml", folder / "imports",
                  folder / "glossary.yml", folder / "roles", folder / "applications"]
        paths += list((folder / "imports").glob("*.md"))
        for _, path in role_dirs(folder):
            paths += [path, path / "role.yml", path / "profile.md"]
        for _, path in application_dirs(folder):
            paths += [path, path / "evaluation.md", path / "status.yml"]
    if any(p.exists() and p.stat().st_mtime > built for p in paths):
        return True
    con = sqlite3.connect(index.as_uri() + "?mode=ro", uri=True)
    try:
        return con.execute("PRAGMA user_version").fetchone()[0] != INDEX_VERSION
    finally:
        con.close()


def open_index(root: Path) -> sqlite3.Connection:
    if index_stale(root):
        rebuild_index(root)
    return sqlite3.connect((root / "index.sqlite").as_uri() + "?mode=ro", uri=True)


# ---------------------------------------------------------------- sources


def register_source(folder: Path, kind: str, origin: str, evidence, state: str, filename: str, data: bytes) -> tuple:
    if kind not in SOURCE_TYPES:
        raise HHError(f"type must be one of {', '.join(SOURCE_TYPES)}")
    evidence = evidence or DEFAULT_EVIDENCE.get(kind)
    if evidence not in EVIDENCE:
        raise HHError(f"--evidence ({', '.join(EVIDENCE)}) is required for type {kind}")
    sources = read_list(folder / "sources.yml")
    sid = make_id("s", next_number([s.get("id") for s in sources], "s"))
    name = f"{sid}-{safe_filename(filename)}"
    (folder / "sources" / name).write_bytes(data)
    sources.append({
        "id": sid, "type": kind, "origin": origin, "received": today(),
        "evidence": evidence, "state": state, "file": f"sources/{name}",
    })
    write_yaml(folder / "sources.yml", sources)
    return sid, folder / "sources" / name


def gh(args: list, raw: bool = False) -> Any:
    try:
        result = subprocess.run(["gh", "api", *args], check=True, capture_output=True, text=True)
    except FileNotFoundError:
        raise HHError("the GitHub CLI `gh` is not installed; install it or paste the repository content") from None
    except subprocess.CalledProcessError as exc:
        raise HHError(f"gh api {' '.join(args)} failed: {exc.stderr.strip()}") from None
    if raw:
        return result.stdout
    return json.loads(result.stdout) if result.stdout.strip() else None


def github_repo_snapshot(repo: str, author) -> tuple:
    info = gh([f"repos/{repo}"])
    languages = gh([f"repos/{repo}/languages"]) or {}
    query = f"repos/{repo}/commits?per_page=100" + (f"&author={author}" if author else "")
    commits = gh([query]) or []
    try:
        readme = gh(["-H", "Accept: application/vnd.github.raw", f"repos/{repo}/readme"], raw=True)
    except HHError:
        readme = ""
    total = sum(languages.values()) or 1
    lines = [
        f"# GitHub repository: {info['full_name']}", "",
        f"- URL: {info['html_url']}",
        f"- Read: {today()} with gh",
        f"- Description: {info.get('description') or '-'}",
        f"- Stars: {info.get('stargazers_count', 0)} · Forks: {info.get('forks_count', 0)}",
        f"- Created: {str(info.get('created_at'))[:10]} · Last push: {str(info.get('pushed_at'))[:10]}",
        f"- Topics: {', '.join(info.get('topics') or []) or '-'}",
        "", "## Languages", "",
    ]
    lines += [f"- {k}: {v * 100 / total:.1f}%" for k, v in sorted(languages.items(), key=lambda kv: -kv[1])] or ["- none"]
    months = Counter(str(c["commit"]["author"]["date"])[:7] for c in commits)
    by = f" by {author}" if author else ""
    lines += ["", f"## Commit activity (latest {len(commits)} commits{by}, by month)", ""]
    lines += [f"- {month}: {count}" for month, count in sorted(months.items(), reverse=True)] or ["- none"]
    lines += ["", "## README (first 6000 characters)", "", readme[:6000].strip() or "(no README)", ""]
    return info["html_url"], "\n".join(lines)


def github_user_snapshot(user: str) -> tuple:
    info = gh([f"users/{user}"])
    repos = gh([f"users/{user}/repos?sort=pushed&per_page=20"]) or []
    own = [r for r in repos if not r.get("fork")]
    languages = Counter(r.get("language") for r in own if r.get("language"))
    lines = [
        f"# GitHub profile: {info['login']}", "",
        f"- URL: {info['html_url']}",
        f"- Read: {today()} with gh",
        f"- Name: {info.get('name') or '-'}",
        f"- Bio: {info.get('bio') or '-'}",
        f"- Company: {info.get('company') or '-'}",
        f"- Location: {info.get('location') or '-'}",
        f"- Public repositories: {info.get('public_repos', 0)} · Joined: {str(info.get('created_at'))[:10]}",
        "", "## Languages across recently pushed repositories", "",
    ]
    lines += [f"- {lang}: {count} {'repository' if count == 1 else 'repositories'}"
              for lang, count in languages.most_common()] or ["- none"]
    lines += ["", "## Recently pushed repositories", ""]
    for r in repos:
        fork = " (fork)" if r.get("fork") else ""
        lines.append(
            f"- {r['name']}{fork}: {r.get('language') or '-'}, {r.get('stargazers_count', 0)} stars, "
            f"last push {str(r.get('pushed_at'))[:10]}. {r.get('description') or ''}".rstrip()
        )
    return info["html_url"], "\n".join(lines) + "\n"


def docx_text(path: Path) -> str:
    ns = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
    try:
        with zipfile.ZipFile(path) as archive:
            root = ElementTree.fromstring(archive.read("word/document.xml"))
    except (zipfile.BadZipFile, KeyError, ElementTree.ParseError) as exc:
        raise HHError(f"{path} is not a readable Word document ({exc})") from None
    paragraphs = ["".join(t.text or "" for t in p.iter(ns + "t")) for p in root.iter(ns + "p")]
    return "\n".join(paragraphs).strip()


# ---------------------------------------------------------------- jobs


def job_files(root: Path) -> list:
    return sorted((root / "jobs").glob("j-*.md"))


def read_job(path: Path) -> tuple:
    text = path.read_text(encoding="utf-8")
    match = re.match(r"^---\n(.*?)\n---\n?(.*)$", text, re.S)
    if not match:
        raise HHError(f"{path}: a Job snapshot starts with a YAML block between --- lines")
    try:
        front = hhyaml.loads(match.group(1))
    except hhyaml.YamlError as exc:
        raise HHError(f"{path}: {exc}") from None
    if not isinstance(front, dict):
        raise HHError(f"{path}: the block between --- lines must be a mapping")
    return front, match.group(2)


def requirement_tags(front: dict) -> list:
    tags = []
    for key in ("must_haves", "nice_to_haves"):
        for item in front.get(key) or []:
            if isinstance(item, dict):
                tags += [t for t in item.get("tags") or [] if t not in tags]
    return tags


def identify_job(job: dict) -> tuple:
    """(Job id, site, site id) from the Job's url, or from its company and title when the user gave no link."""
    if job.get("url"):
        return web(hhweb.job_id, str(job["url"]))
    company, title = str(job.get("company") or "").strip(), str(job.get("title") or "").strip()
    if not company or not title:
        raise HHError("a Job without a url needs company and title for its id")
    key = unicodedata.normalize("NFC", f"{company}|{title}").lower()
    digest = hashlib.sha1(key.encode("utf-8")).hexdigest()[:8]
    return f"j-user-{digest}", "user", digest


def check_job(front: dict, body: str, taxonomy: dict, filename=None) -> list:
    errors = []
    jid = front.get("id")
    where = f"job {jid or filename}"
    known, terms = tag_ids(taxonomy), tag_terms(taxonomy)
    try:
        expected, site, site_id = identify_job(front)
    except HHError as exc:
        return [f"{where}: {exc}"]
    if jid != expected:
        errors.append(f"{where}: id must be {expected} for its url, or for its company and title without one")
    if filename and filename != f"{expected}.md":
        errors.append(f"{where}: file name must be {expected}.md")
    if front.get("site") != site or str(front.get("site_id")) != site_id:
        errors.append(f"{where}: site and site_id must be {site} and {site_id}")
    for key in ("title", "company", "location", "salary"):
        if not str(front.get(key) or "").strip():
            errors.append(f"{where}: {key} is required (write 'not stated' when the posting has none)")
    if not DATE.match(str(front.get("read") or "")):
        errors.append(f"{where}: read must be the date the Job was read")
    read_with = front.get("read_with")
    if read_with not in READ_WITH:
        errors.append(f"{where}: read_with must be one of {', '.join(READ_WITH)}")
    elif read_with == "fetch" and (not front.get("url") or hhweb.read_method(str(front["url"])) != "fetch"):
        errors.append(f"{where}: the script never fetched this Job; read_with must be browser, pasted or file")
    for key in ("must_haves", "nice_to_haves"):
        items = front.get(key)
        if not isinstance(items, list):
            errors.append(f"{where}: {key} must be a list")
            continue
        for n, item in enumerate(items, 1):
            label = f"{where}: {key} {n}"
            if not isinstance(item, dict) or not str(item.get("text") or "").strip():
                errors.append(f"{label} needs text")
                continue
            tags, proposed = item.get("tags") or [], item.get("proposed") or []
            if not isinstance(tags, list) or not isinstance(proposed, list):
                errors.append(f"{label}: tags and proposed must be lists")
                continue
            if not tags and not proposed:
                errors.append(f"{label} needs a Tag, or a proposed term waiting for the user")
            for tag in tags:
                if tag not in known:
                    errors.append(f"{label}: Tag {tag!r} is not in taxonomy.yml; list it under proposed")
            for term in proposed:
                if str(term).strip().lower() in terms:
                    errors.append(f"{label}: {term!r} is already the Tag {terms[str(term).strip().lower()]}")
    duties = front.get("duties")
    if not isinstance(duties, list) or not all(str(d).strip() for d in duties):
        errors.append(f"{where}: duties must be a list of statements")
    if "## Posting text" not in body:
        errors.append(f"{where}: the snapshot needs a '## Posting text' section")
    return errors


def render_job(front: dict, text: str) -> str:
    header = hhyaml.dumps({key: front[key] for key in JOB_ORDER if key in front})
    summary = " · ".join(str(front.get(k)) for k in ("company", "location", "salary") if front.get(k))
    return f"---\n{header}---\n\n# {front['title']}\n\n{summary}\n\n## Posting text\n\n{text.strip()}\n"


def web(call, *args):
    try:
        return call(*args)
    except hhweb.WebError as exc:
        raise HHError(str(exc)) from None


# ---------------------------------------------------------------- roles


def role_dirs(folder: Path) -> list:
    base = folder / "roles"
    return sorted((d.name, d) for d in base.iterdir() if (d / "role.yml").exists()) if base.exists() else []


def find_role(folder: Path, slug: str) -> Path:
    path = folder / "roles" / slug
    if not (path / "role.yml").exists():
        known = ", ".join(s for s, _ in role_dirs(folder)) or "none"
        raise HHError(f"no Role {slug!r} for {folder.name} (Roles: {known})")
    return path


def load_role(path: Path) -> dict:
    role = read_yaml(path / "role.yml", {})
    if not isinstance(role, dict):
        raise HHError(f"{path / 'role.yml'} must be a mapping")
    return role


def digest(value) -> str:
    return hashlib.sha1(json.dumps(value, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()[:8]


def role_digest(role: dict) -> str:
    return digest({k: role.get(k) for k in ("title", "level", "industries", "requirements")})


def role_tags(role: dict) -> set:
    return {t for r in role.get("requirements") or [] if isinstance(r, dict) for t in r.get("tags") or []}


def ordered_role(role: dict) -> dict:
    out = {k: role[k] for k in ROLE_ORDER if k in role}
    out.update({k: v for k, v in role.items() if k not in out})
    out["requirements"] = [
        {**{k: r[k] for k in REQUIREMENT_ORDER if k in r}, **{k: v for k, v in r.items() if k not in REQUIREMENT_ORDER}}
        for r in out.get("requirements") or [] if isinstance(r, dict)
    ]
    return out


def glossary_titles(glossary) -> dict:
    """Map each title in the Glossary, in either language, to its other-language form."""
    pairs = {}
    for entry in glossary if isinstance(glossary, list) else []:
        if isinstance(entry, dict) and entry.get("kind") == "title" and entry.get("zh") and entry.get("en"):
            pairs[str(entry["zh"])] = str(entry["en"])
            pairs[str(entry["en"])] = str(entry["zh"])
    return pairs


def check_role(role: dict, slug: str, folder: Path, known_tags: set) -> list:
    errors = []
    where = f"role {slug}"
    root = folder.parent.parent
    glossary = read_yaml(folder / "glossary.yml", [])
    title = str(role.get("title") or "").strip()
    if not title:
        errors.append(f"{where}: title is required")
    elif title not in glossary_titles(glossary):
        errors.append(f"{where}: add the title {title!r} to glossary.yml as a title with both languages")
    if role.get("level") not in (None, *SENIORITY):
        errors.append(f"{where}: level must be one of {', '.join(SENIORITY)}")
    industries = role.get("industries") or []
    if not isinstance(industries, list) or any(t not in known_tags or not str(t).startswith("industry/") for t in industries):
        errors.append(f"{where}: industries must be industry Tags from taxonomy.yml")
    if not isinstance(role.get("priority"), int) or role["priority"] < 1:
        errors.append(f"{where}: priority must be a whole number from 1")
    if role.get("state") not in ROLE_STATES:
        errors.append(f"{where}: state must be one of {', '.join(ROLE_STATES)}")
    requirements = role.get("requirements")
    if not isinstance(requirements, list):
        return errors + [f"{where}: requirements must be a list"]
    seen = set()
    for n, req in enumerate(requirements, 1):
        if not isinstance(req, dict):
            errors.append(f"{where}: requirement {n} is not a mapping")
            continue
        rid = req.get("id")
        label = f"{where}: requirement {rid or n}"
        if id_number(rid, "r") is None:
            errors.append(f"{label}: id must look like r-001")
        elif rid in seen:
            errors.append(f"{label}: duplicate id")
        seen.add(rid)
        if req.get("kind") not in REQUIREMENT_KINDS:
            errors.append(f"{label}: kind must be must or nice")
        if not str(req.get("text") or "").strip():
            errors.append(f"{label}: text is required")
        tags = req.get("tags") or []
        if not isinstance(tags, list) or any(t not in known_tags for t in tags):
            errors.append(f"{label}: tags must come from taxonomy.yml")
        origin = req.get("origin")
        if origin not in REQUIREMENT_ORIGINS:
            errors.append(f"{label}: origin must be user, assumed or job")
        jobs = req.get("jobs") or []
        if origin == "job" and not jobs:
            errors.append(f"{label}: a requirement from Jobs lists their Job ids")
        if origin != "job" and jobs:
            errors.append(f"{label}: only a requirement with origin job lists Jobs")
        for jid in jobs:
            if not (root / "jobs" / f"{jid}.md").exists():
                errors.append(f"{label}: Job {jid} has no snapshot in jobs/")
    return errors


def fact_problem(by_id: dict, fid, inferred: bool = False):
    """Why a Fact cannot be cited as evidence (or, with inferred, under a gap to confirm); None when it can."""
    fact = by_id.get(fid)
    if fact is None:
        return f"unknown Fact {fid}"
    if fact.get("state") != "active":
        return f"{fid} is {fact.get('state')}; only active Facts count"
    if inferred and fact.get("origin") != "inferred":
        return f"{fid} is sourced; cite it as evidence instead"
    if not inferred and fact.get("origin") != "sourced":
        return f"{fid} is inferred; list it under the requirement's gap to confirm"
    return None


def check_evidence(reqs: dict, entries, by_id: dict, errors: list) -> dict:
    """Map requirement ids to the sourced Facts cited for them, strongest evidence first."""
    rank = {level: n for n, level in enumerate(EVIDENCE)}
    evidence = {}
    for entry in entries or []:
        rid = entry.get("requirement")
        if rid not in reqs:
            errors.append(f"evidence: unknown requirement {rid}")
            continue
        cited = []
        for item in entry.get("facts") or []:
            if not str(item.get("why") or "").strip():
                errors.append(f"evidence {rid}: say why {item.get('id')} supports it")
            problem = fact_problem(by_id, item.get("id"))
            if problem:
                errors.append(f"evidence {rid}: {problem}")
            else:
                cited.append({"id": item["id"], "why": item.get("why")})
        cited.sort(key=lambda c: rank.get(str(by_id[c["id"]].get("evidence")), 9))
        if cited:
            evidence[rid] = cited
    return evidence


def check_gaps(reqs: dict, evidence: dict, entries, by_id: dict, errors: list, skip=()) -> list:
    """Work out the gap of every requirement without documented or third-party evidence."""
    rank = {level: n for n, level in enumerate(EVIDENCE)}
    given = {g.get("requirement"): g for g in entries or []}
    gaps = []
    for rid, req in reqs.items():
        gap = given.pop(rid, None)
        if rid in skip:
            if gap:
                errors.append(f"gaps: {rid} fails a hard requirement; leave it out of gaps")
            continue
        best = min((rank.get(str(by_id[c["id"]].get("evidence")), 9) for c in evidence.get(rid, [])), default=None)
        if best is not None and best < rank["self-reported"]:
            if gap:
                errors.append(f"gaps: {rid} has {EVIDENCE[best]} evidence, so it is not a gap")
            continue
        if not gap or not str(gap.get("close") or "").strip():
            errors.append(f"gaps: {rid} ({req.get('text')}) needs a gap entry saying how to close it")
            continue
        if best is not None:
            kind, linked = "weak-evidence", [c["id"] for c in evidence[rid]]
        else:
            linked = []
            for fid in gap.get("facts") or []:
                problem = fact_problem(by_id, fid, inferred=True)
                if problem:
                    errors.append(f"gap {rid}: {problem}")
                else:
                    linked.append(fid)
            kind = "to-confirm" if linked else "missing"
        gaps.append({"requirement": rid, "kind": kind, "facts": linked, "close": gap["close"]})
    for rid in given:
        errors.append(f"gaps: unknown requirement {rid}")
    return gaps


def role_stale(path: Path, role: dict, facts: list) -> list:
    """Reasons a Role profile is out of date; empty when it is current."""
    profile = path / "profile.md"
    if not profile.exists():
        return ["not built yet"]
    try:
        front, _ = read_job(profile)
    except HHError as exc:
        return [str(exc)]
    built = front.get("built_from") or {}
    reasons = []
    if built.get("role") != role_digest(role):
        reasons.append("role.yml changed")
    current = {f.get("id"): f for f in facts if isinstance(f, dict)}
    for fid, value in (built.get("facts") or {}).items():
        if fid not in current:
            reasons.append(f"{fid} was removed")
        elif digest(current[fid]) != str(value):
            reasons.append(f"{fid} changed")
    through = id_number(built.get("facts_through"), "f") or 0
    wanted = role_tags(role)
    for fact in facts:
        number = id_number(fact.get("id"), "f") or 0
        if number > through and fact.get("state") == "active" and wanted & set(fact.get("tags") or []):
            reasons.append(f"new {fact['id']} matches its requirements")
    return reasons


def update_strategy_roles(folder: Path) -> None:
    """Rewrite the Roles section of strategy.md from the role.yml files."""
    rows = []
    for slug, path in role_dirs(folder):
        role = load_role(path)
        rows.append((ROLE_STATES.index(role.get("state")) if role.get("state") in ROLE_STATES else 9,
                     role.get("priority") or 99, slug, role))
    lines = ["## Roles", "", "Kept in step with `roles/*/role.yml` by hh.py.", ""]
    if rows:
        lines += ["| Priority | Role | Level | State |", "|---|---|---|---|"]
        for _, priority, slug, role in sorted(rows):
            lines.append(f"| {priority} | {role.get('title')} (`{slug}`) | {role.get('level') or '-'} | {role.get('state')} |")
    else:
        lines.append("No Roles yet.")
    path = folder / "strategy.md"
    text = path.read_text(encoding="utf-8") if path.exists() else "# Strategy\n"
    section = "\n".join(lines) + "\n"
    match = re.search(r"(?ms)^## Roles\n.*?(?=^## |\Z)", text)
    text = text[:match.start()] + section + ("\n" + text[match.end():] if text[match.end():] else "") if match \
        else text.rstrip() + "\n\n" + section
    path.write_text(text, encoding="utf-8")


# ---------------------------------------------------------------- evaluations


def evaluation_files(folder: Path) -> list:
    base = folder / "applications"
    return sorted((p.parent.name, p) for p in base.glob("*/evaluation.md")) if base.exists() else []


def job_requirements(job: dict) -> dict:
    """The Job's requirements keyed by position: must-1, must-2, ... then nice-1, ..."""
    reqs = {}
    for key, kind in (("must_haves", "must"), ("nice_to_haves", "nice")):
        for n, item in enumerate(job.get(key) or [], 1):
            if isinstance(item, dict):
                reqs[f"{kind}-{n}"] = {"kind": kind, "text": item.get("text"), "tags": item.get("tags") or [],
                                       "proposed": item.get("proposed") or []}
    return reqs


def achievement_targets(job: dict, reqs: dict) -> dict:
    """What achievements are matched against: the Job's duties, or its requirements when it lists none."""
    duties = job.get("duties") or []
    if duties:
        return {f"duty-{n}": str(text) for n, text in enumerate(duties, 1)}
    return {rid: str(req["text"]) for rid, req in reqs.items()}


def evaluation_fact_ids(front: dict) -> set:
    ids = {c.get("id") for e in front.get("evidence") or [] for c in e.get("facts") or []}
    ids |= {fid for key in ("gaps", "hard") for e in front.get(key) or [] for fid in e.get("facts") or []}
    ids |= {a.get("fact") for a in front.get("achievements") or []}
    return {fid for fid in ids if fid}


def check_evaluation(front: dict, jid: str, folder: Path, fact_ids: set) -> list:
    errors = []
    where = f"evaluation {jid}"
    root = folder.parent.parent
    if front.get("job") != jid:
        errors.append(f"{where}: job must be {jid}, its folder name")
    if not (root / "jobs" / f"{jid}.md").exists():
        errors.append(f"{where}: Job {jid} has no snapshot in jobs/")
    cid = re.match(r"c-\d+", folder.name)
    if cid and front.get("candidate") != cid.group(0):
        errors.append(f"{where}: candidate must be {cid.group(0)}")
    role = front.get("role")
    if role is not None and not (folder / "roles" / str(role) / "role.yml").exists():
        errors.append(f"{where}: no Role {role}")
    if front.get("rating") not in RATINGS:
        errors.append(f"{where}: rating must be one of {', '.join(RATINGS)}")
    score = front.get("score")
    if not isinstance(score, int) or not 0 <= score <= 100:
        errors.append(f"{where}: score must be a whole number from 0 to 100")
    if any(g.get("kind") not in GAP_KINDS for g in front.get("gaps") or [] if isinstance(g, dict)):
        errors.append(f"{where}: gap kinds must be {', '.join(GAP_KINDS)}")
    for fid in sorted(evaluation_fact_ids(front) - fact_ids):
        errors.append(f"{where}: cites unknown Fact {fid}")
    return errors


def refine_proposals(root: Path, folder: Path, slug: str, role: dict, taxonomy: dict) -> tuple:
    """(Job ids evaluated under the Role, proposed role.yml changes from requirements recurring in 2+ of them)."""
    jobs = []
    for jid, path in evaluation_files(folder):
        job_path = root / "jobs" / f"{jid}.md"
        if read_job(path)[0].get("role") == slug and job_path.exists():
            jobs.append((jid, read_job(job_path)[0]))
    seen = {}
    for jid, job in jobs:
        for key in ("must_haves", "nice_to_haves"):
            for item in job.get(key) or []:
                for tag in item.get("tags") or []:
                    entry = seen.setdefault(tag, {"jobs": [], "must": set(), "texts": []})
                    if jid not in entry["jobs"]:
                        entry["jobs"].append(jid)
                    if key == "must_haves":
                        entry["must"].add(jid)
                    entry["texts"].append(f"{jid}: {item.get('text')}")
    labels = {t.get("id"): t.get("en") for t in taxonomy.get("tags") or [] if isinstance(t, dict)}
    requirements = [r for r in role.get("requirements") or [] if isinstance(r, dict)]
    covered = role_tags(role)
    adds, cites = [], {}
    for tag, entry in seen.items():
        if len(entry["jobs"]) < 2:
            continue
        if tag not in covered:
            kind = "must" if 2 * len(entry["must"]) >= len(entry["jobs"]) else "nice"
            adds.append({"key": tag, "kind": kind, "text": labels.get(tag) or tag, "tags": [tag], "origin": "job",
                         "jobs": entry["jobs"], "must_in": len(entry["must"]), "texts": entry["texts"]})
            continue
        for req in requirements:
            if tag in (req.get("tags") or []) and req.get("origin") in ("assumed", "job"):
                new = [j for j in entry["jobs"] if j not in (req.get("jobs") or [])]
                if new:
                    cite = cites.setdefault(req["id"], {"key": req["id"], "requirement": req, "jobs": []})
                    cite["jobs"] += [j for j in new if j not in cite["jobs"]]
    adds.sort(key=lambda p: (-len(p["jobs"]), p["key"]))
    return [jid for jid, _ in jobs], adds + sorted(cites.values(), key=lambda p: p["key"])


def render_evaluation(front: dict, job: dict, reqs: dict, role, by_id: dict, profile: dict, basis: dict) -> str:
    lines = [f"# Evaluation: {job.get('title')} · {job.get('company')}", ""]
    who = f"Candidate {front['candidate']} {profile.get('name')} · Job {front['job']}"
    if role:
        lines.append(f"{who} · Role {role.get('title')} (`{front['role']}`)")
    else:
        lines += [who, "", "No Role fits this Job, so it was evaluated against all of the Candidate's Facts. "
                  "A Role can be created from this Job."]
    lines += ["", f"**Success rating: {front['rating']}.** Fit score {front['score']} / 100.", "", front["summary"],
              "", "## Success rating", ""]
    lines += [f"- {reason}" for reason in front["reasons"]]
    lines += ["", "## Fit score", "", "| Dimension | Weight | Score | Basis |", "|---|---|---|---|"]
    lines += [f"| {label} | {weight}% | {front['dimensions'][key]} | {basis[key]} |" for key, weight, label in RUBRIC]
    lines += ["", "## Hard requirements", ""]
    for h in front["hard"]:
        req = reqs[h["requirement"]]
        if h["kind"] == "years" and "years" in h:
            detail = f"{h['years']} years from the cited experience; the Job asks for {h['min_years']}"
        elif h["result"] == "failed":
            detail = f"{', '.join(h['facts'])}: {h['why']}"
        elif h["result"] == "met":
            detail = "see Evidence"
        else:
            detail = "no sourced Fact yet; see Gaps"
        lines.append(f"- {h['requirement']} ({h['kind']}) {req['text']}: {h['result']} — {detail}")
    if not front["hard"]:
        lines.append("None.")
    lines += ["", "## Evidence", ""]
    for entry in front["evidence"]:
        req = reqs[entry["requirement"]]
        lines.append(f"### {entry['requirement']} {req['text']}")
        lines += [f"- {c['id']} ({by_id[c['id']].get('evidence')}): {by_id[c['id']].get('statement')} — {c['why']}"
                  for c in entry["facts"]]
        lines.append("")
    lines += ["## Gaps", ""]
    for gap in front["gaps"]:
        linked = f" ({', '.join(gap['facts'])})" if gap["facts"] else ""
        lines.append(f"- {gap['requirement']} {reqs[gap['requirement']]['text']}: {gap['kind']}{linked} — {gap['close']}")
    if not front["gaps"]:
        lines.append("None.")
    targets = achievement_targets(job, reqs)
    lines += ["", "## Achievements", ""]
    lines += [f"- {a['fact']}: {by_id[a['fact']].get('statement')} → {a['target']} ({targets[a['target']]}) — {a['why']}"
              for a in front["achievements"]] or ["None."]
    salary = profile.get("salary")
    salary = salary if isinstance(salary, dict) else {}
    wanted = {"salary": salary.get("expected"), "location": profile.get("location"), "work_mode": profile.get("work_mode")}
    lines += ["", "## Salary, location, work mode", ""]
    for key in CONDITIONS:
        item = front["conditions"][key]
        lines.append(f"- {key.replace('_', ' ').capitalize()} (Job: {job.get(key) or 'not stated'}; "
                     f"Candidate: {wanted[key] or 'not recorded'}): {item['fit']} — {item['why']}")
    lines += ["", "## Risks", ""]
    lines += [f"- {r['risk']} — {r['close']}" for r in front["risks"]] or ["None."]
    return f"---\n{hhyaml.dumps(front)}---\n\n" + "\n".join(lines).rstrip() + "\n"


# ---------------------------------------------------------------- resumes


def glossary_pairs(glossary, kinds=GLOSSARY_KINDS) -> dict:
    """Map each name in the Glossary, in either language, to its (zh, en) pair."""
    pairs = {}
    for entry in glossary if isinstance(glossary, list) else []:
        if isinstance(entry, dict) and entry.get("kind") in kinds and entry.get("zh") and entry.get("en"):
            pair = (str(entry["zh"]), str(entry["en"]))
            pairs[pair[0]] = pairs[pair[1]] = pair
    return pairs


def lacking_terms(job: dict, evaluation: dict, facts: list, taxonomy: dict) -> dict:
    """Words for the Job requirements the Candidate lacks, mapped to the requirement; resumes must not use them.

    A requirement is lacking when the Evaluation lists it as a missing or to-confirm gap, or it failed as a hard
    requirement. Its words are the labels and aliases of its Tags that no active, sourced Fact has, and its proposed
    terms, unless an active, sourced Fact's statement uses them.
    """
    reqs = job_requirements(job)
    lacking = [g.get("requirement") for g in evaluation.get("gaps") or [] if g.get("kind") in ("missing", "to-confirm")]
    lacking += [h.get("requirement") for h in evaluation.get("hard") or [] if h.get("result") == "failed"]
    usable = [f for f in facts if isinstance(f, dict) and f.get("state") == "active" and f.get("origin") == "sourced"]
    held = {t for f in usable for t in f.get("tags") or []}
    stated = " ".join(str(f.get("statement")) for f in usable).lower()
    labels = {t.get("id"): t for t in taxonomy.get("tags") or [] if isinstance(t, dict)}
    terms = {}
    for rid in lacking:
        req = reqs.get(rid)
        if not req:
            continue
        words = [str(w) for w in req["proposed"]]
        for tag in req["tags"]:
            if tag not in held:
                entry = labels.get(tag) or {}
                words += [*(str(entry.get(k) or "") for k in ("en", "zh")), *(str(a) for a in entry.get("aliases") or []),
                          tag.split("/")[-1].replace("-", " ")]
        for word in (w.strip() for w in words):
            if len(word) > 1 and word.lower() not in stated and word.lower() not in {t.lower() for t in terms}:
                terms[word] = rid
    return terms


def term_used(term: str, text: str) -> bool:
    if term.isascii():
        return re.search(r"(?<![A-Za-z0-9])" + re.escape(term) + r"(?![A-Za-z0-9])", text, re.I) is not None
    return term in text


def markdown_html(text: str) -> str:
    """Render the Markdown that resumes use (headings, paragraphs, lists, bold, italics, links) as HTML."""
    text = re.sub(r"<!--.*?-->", "", text, flags=re.S)
    out, items, para = [], [], []

    def inline(value: str) -> str:
        value = escape(value, quote=False)
        value = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", value)
        value = re.sub(r"(?<![*\w])\*(?!\s)(.+?)(?<!\s)\*(?![*\w])", r"<em>\1</em>", value)
        return re.sub(r"\[([^\]]+)\]\(([^)\s]+)\)", r'<a href="\2">\1</a>', value)

    def flush():
        if items:
            out.append("<ul>" + "".join(f"<li>{inline(i)}</li>" for i in items) + "</ul>")
            items.clear()
        if para:
            out.append(f"<p>{inline(' '.join(para))}</p>")
            para.clear()

    for line in text.splitlines():
        line = line.strip()
        heading = re.match(r"(#{1,3}) (.*)", line)
        if not line or heading:
            flush()
            if heading:
                level = len(heading.group(1))
                out.append(f"<h{level}>{inline(heading.group(2))}</h{level}>")
        elif line.startswith("- "):
            if para:
                flush()
            items.append(line[2:])
        else:
            if items:
                flush()
            para.append(line)
    flush()
    return "\n".join(out)


def resume_html(body: str, lang: str, title: str) -> str:
    fonts = ('"Noto Sans TC", "Noto Sans CJK TC", "PingFang TC", "Microsoft JhengHei", "Heiti TC", sans-serif'
             if lang == "zh" else '"Noto Sans", "Helvetica Neue", Arial, "Noto Sans TC", "PingFang TC", sans-serif')
    style = (
        "@page { size: A4; margin: 16mm 18mm; }"
        f"body {{ font-family: {fonts}; font-size: 10.5pt; line-height: 1.5; color: #222;"
        " font-variant-ligatures: none; }"  # ligature glyphs reach the text layer as ﬁ and ﬂ
        "h1 { font-size: 20pt; margin: 0 0 4pt; } h2 { font-size: 12pt; margin: 14pt 0 4pt; padding-bottom: 2pt;"
        " border-bottom: 1px solid #999; } h3 { font-size: 10.5pt; margin: 8pt 0 2pt; } p { margin: 3pt 0; }"
        "ul { margin: 2pt 0; padding-left: 16pt; } li { margin: 1pt 0; } a { color: inherit; text-decoration: none; }"
    )
    return (f'<!doctype html>\n<html lang="{"zh-Hant" if lang == "zh" else "en"}"><head><meta charset="utf-8">'
            f"<title>{escape(title)}</title><style>{style}</style></head>\n<body>\n{markdown_html(body)}\n</body></html>\n")


def find_browser():
    chosen = os.environ.get("HEADHUNTER_BROWSER")
    if chosen:
        if not shutil.which(chosen):
            raise HHError(f"HEADHUNTER_BROWSER is {chosen!r}, which is not a browser that can run")
        return shutil.which(chosen)
    return next((shutil.which(name) for name in BROWSERS if shutil.which(name)), None)


def print_pdf(browser: str, page: Path, target: Path) -> None:
    """Print a local HTML page to PDF with a headless browser and a throwaway profile."""
    profile = tempfile.mkdtemp(prefix="hh-browser-")
    if target.exists():
        target.unlink()
    command = [browser, "--headless", "--disable-gpu", "--no-first-run", "--no-default-browser-check",
               "--disable-extensions", "--disable-background-networking", "--disable-sync", "--disable-component-update",
               f"--user-data-dir={profile}", "--no-pdf-header-footer", f"--print-to-pdf={target}", page.resolve().as_uri()]
    try:
        proc = subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        deadline = time.time() + 60
        while time.time() < deadline and proc.poll() is None:
            if target.exists() and target.read_bytes().rstrip().endswith(b"%%EOF"):
                time.sleep(0.5)  # some browsers keep running after writing the PDF
                break
            time.sleep(0.2)
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(5)
            except subprocess.TimeoutExpired:
                proc.kill()
    finally:
        shutil.rmtree(profile, ignore_errors=True)
    if not target.exists() or not target.read_bytes().rstrip().endswith(b"%%EOF"):
        raise HHError(f"{browser} did not write {target.name}")


def fix_pdf_text(path: Path) -> list:
    """Point radicals in the PDF's text layer back at the ideographs they stand for; return the ones left.

    Some fonts draw an ideograph and its Kangxi radical (小 and ⼩) with one glyph, and browsers record the radical,
    so copied text and applicant tracking systems read ⼩程式 instead of 小程式.
    """
    data = path.read_bytes()
    table = re.search(rb"\nxref\n0 (\d+)\n((?:\d{10} \d{5} [fn] ?\r?\n)+)trailer\n(.*?)\nstartxref\n", data, re.S)
    if not table or data.count(b"\nxref\n") != 1:
        return ["the PDF layout was not recognized, so its text layer was not checked"]
    entries = re.findall(rb"(\d{10}) (\d{5}) ([fn])", table.group(2))
    offsets = {n: int(off) for n, (off, _, kind) in enumerate(entries) if kind == b"n"}
    order = sorted(offsets, key=lambda n: offsets[n])
    bounds = [offsets[n] for n in order] + [table.start() + 1]
    chunks = {n: data[bounds[i]:bounds[i + 1]] for i, n in enumerate(order)}
    left, changed = set(), False

    def swap(match):
        char = chr(int(match.group(2), 16))
        ideograph = unicodedata.normalize("NFKC", char)
        if not 0x2E80 <= ord(char) <= 0x2FDF:
            return match.group(0)
        if len(ideograph) == 1 and ideograph != char:
            return match.group(1) + b"<%04X>" % ord(ideograph)
        left.add(char)
        return match.group(0)

    for number in {int(n) for n in re.findall(rb"/ToUnicode (\d+) 0 R", data)}:
        chunk = chunks.get(number, b"")
        head = re.match(rb"\d+ \d+ obj\s*<<(.*?)>>\s*stream\r?\n", chunk, re.S)
        size = re.search(rb"/Length (\d+)", head.group(1)) if head else None
        if not head or not size:
            continue
        start, end = head.end(), head.end() + int(size.group(1))
        flate = b"/FlateDecode" in head.group(1)
        cmap = zlib.decompress(chunk[start:end]) if flate else chunk[start:end]
        fixed = re.sub(rb"beginbfchar(.*?)endbfchar", lambda block: re.sub(
            rb"(?m)^(\s*<[0-9A-Fa-f]+>\s*)<([0-9A-Fa-f]{4})>", swap, block.group(0)), cmap, flags=re.S)
        if fixed != cmap:
            stream = zlib.compress(fixed) if flate else fixed
            header = chunk[:head.start(1)] + re.sub(rb"/Length \d+", b"/Length %d" % len(stream), head.group(1))
            chunks[number] = header + chunk[head.end(1):start] + stream + chunk[end:]
            changed = True
    if changed:
        out = bytearray(data[:bounds[0]])
        moved = {}
        for number in order:
            moved[number] = len(out)
            out += chunks[number]
        start = len(out)
        out += b"xref\n0 %d\n" % len(entries)
        for n, (off, gen, kind) in enumerate(entries):
            out += b"%010d %s n \n" % (moved[n], gen) if kind == b"n" else b"%s %s f \n" % (off, gen)
        out += b"trailer\n" + table.group(3) + b"\nstartxref\n%d\n%%%%EOF\n" % start
        path.write_bytes(bytes(out))
    return sorted(left)


def resume_files(folder: Path) -> list:
    base = folder / "applications"
    return sorted((p.parent.name, p.name.split(".")[1], p) for p in base.glob("*/resume.*.md")) if base.exists() else []


def check_resume(path: Path, lang: str, by_id: dict) -> list:
    """Problems in a resume's Markdown: every statement line cites Facts or the profile, its numbers are in those
    Facts, and English has no Chinese."""
    where = f"resume {path.parent.name} {lang}"
    try:
        front, body = read_job(path)
    except HHError as exc:
        return [str(exc)]
    errors = []
    if front.get("lang") != lang or front.get("job") != path.parent.name:
        errors.append(f"{where}: lang and job must be {lang} and {path.parent.name}")
    for n, line in enumerate(body.splitlines(), 1):
        text = line.strip()
        if not text or re.match(r"#{1,2} ", text):
            continue
        cite = CITATION.search(text)
        if not cite:
            errors.append(f"{where}: line {n} cites no Fact; end it with <!-- f-001 --> or remove it: {text[:60]}")
            continue
        ids = [fid for fid in cite.group(1).split(", ") if fid != "profile"]
        for fid in ids:
            if fid not in by_id:
                errors.append(f"{where}: line {n} cites unknown Fact {fid}")
        pool = " ".join(str(by_id.get(f, {}).get(k) or "") for f in ids for k in ("statement", "period"))
        allowed = set(NUMBER.findall(re.sub(r"(?<=\d),(?=\d{3})", "", pool)))
        used = set(NUMBER.findall(re.sub(r"(?<=\d),(?=\d{3})", "", text[:cite.start()]))) if ids else set()
        for number in sorted(used - allowed):
            errors.append(f"{where}: line {n} has the number {number}, which is not in {', '.join(ids)}")
        if lang == "en" and HAN.search(text[:cite.start()]):
            errors.append(f"{where}: line {n} has Chinese text; use the English names from glossary.yml: {text[:60]}")
    return errors


def render_period(value, lang: str) -> str:
    start, sep, end = str(value).partition("..")
    if not sep:
        return start
    return f"{start} – {('至今' if lang == 'zh' else 'Present') if end in ('present', '') else end}"


# ---------------------------------------------------------------- applications


def application_dirs(folder: Path) -> list:
    base = folder / "applications"
    return sorted((d.name, d) for d in base.iterdir() if d.is_dir()) if base.exists() else []


def parse_date(value, label: str) -> dt.date:
    try:
        if not DATE.match(str(value)):
            raise ValueError
        return dt.date.fromisoformat(str(value))
    except ValueError:
        raise HHError(f"{label} must be a date such as 2026-01-31, not {value!r}") from None


def write_status(path: Path, status: dict) -> None:
    write_yaml(path, {key: status[key] for key in STATUS_ORDER if key in status})


def load_status(folder: Path, jid: str) -> tuple:
    path = folder / "applications" / jid / "status.yml"
    if not path.exists():
        raise HHError(f"{folder.name} has no Application for {jid}; start one with application new or evaluation save")
    status = read_yaml(path, {})
    if not isinstance(status, dict):
        raise HHError(f"{path} must be a mapping")
    return path, status


def record_evaluated(folder: Path, jid: str, slug) -> dict:
    """Bring the Application in step with its Evaluation; returns its status."""
    path = folder / "applications" / jid / "status.yml"
    status = read_yaml(path, {}) if path.exists() else {}
    decide = {"next_step": DECIDE_STEP, "due": (dt.date.today() + dt.timedelta(days=DECIDE_DAYS)).isoformat()}
    if not status:
        status = {"job": jid, "role": slug, "stage": "evaluated", **decide,
                  "timeline": [{"stage": "evaluated", "date": today()}]}
    else:
        status["role"] = slug
        if status.get("stage") == "found":
            status.update(stage="evaluated", **decide)
            status["timeline"] = list(status.get("timeline") or []) + [{"stage": "evaluated", "date": today()}]
    write_status(path, status)
    return status


def check_status(status, jid: str, folder: Path) -> list:
    where = f"application {jid}"
    if not isinstance(status, dict):
        return [f"{where}: status.yml must be a mapping"]
    errors = []
    root = folder.parent.parent
    if status.get("job") != jid:
        errors.append(f"{where}: job must be {jid}, its folder name")
    if not (root / "jobs" / f"{jid}.md").exists():
        errors.append(f"{where}: Job {jid} has no snapshot in jobs/")
    role = status.get("role")
    if role is not None and not (folder / "roles" / str(role) / "role.yml").exists():
        errors.append(f"{where}: no Role {role}")
    evaluation = folder / "applications" / jid / "evaluation.md"
    if evaluation.exists():
        try:
            if read_job(evaluation)[0].get("role") != role:
                errors.append(f"{where}: role must be the Role of its Evaluation")
        except HHError:
            pass  # reported with the Evaluation
    stage = status.get("stage")
    timeline = status.get("timeline")
    if stage not in STAGES:
        return errors + [f"{where}: stage must be one of {', '.join(STAGES)}"]
    if not isinstance(timeline, list) or not timeline:
        return errors + [f"{where}: timeline must list every Stage change with its date"]
    previous, last_round, last_rank = None, 0, 0
    for n, entry in enumerate(timeline, 1):
        label = f"{where}: timeline {n}"
        if not isinstance(entry, dict) or entry.get("stage") not in STAGES:
            errors.append(f"{label}: stage must be one of {', '.join(STAGES)}")
            continue
        try:
            day = parse_date(entry.get("date"), f"{label}: date")
        except HHError as exc:
            errors.append(str(exc))
            continue
        if previous and day < previous:
            errors.append(f"{label}: dates must not go backwards")
        rank = STAGES.index(entry["stage"])
        if rank < last_rank:
            errors.append(f"{label}: Stages must only move forward")
        previous, last_rank = day, rank
        if entry["stage"] == "interview":
            if not isinstance(entry.get("round"), int) or entry["round"] <= last_round:
                errors.append(f"{label}: an interview needs a round number higher than the last")
            else:
                last_round = entry["round"]
        elif "round" in entry:
            errors.append(f"{label}: only an interview has a round")
    last = timeline[-1] if isinstance(timeline[-1], dict) else {}
    if last.get("stage") != stage:
        errors.append(f"{where}: stage must be the last Stage in its timeline")
    if stage == "interview" and status.get("round") != last.get("round"):
        errors.append(f"{where}: round must be the round of the last interview")
    if stage != "interview" and "round" in status:
        errors.append(f"{where}: only an Application at interview has a round")
    if any(isinstance(e, dict) and e.get("stage") == "evaluated" for e in timeline) and not evaluation.exists():
        errors.append(f"{where}: its timeline says evaluated, but it has no evaluation.md")
    if stage == "closed":
        if status.get("outcome") not in OUTCOMES:
            errors.append(f"{where}: a closed Application records its outcome: {', '.join(OUTCOMES)}")
        if "next_step" in status or "due" in status:
            errors.append(f"{where}: a closed Application has no next step or due date")
    else:
        if "outcome" in status:
            errors.append(f"{where}: only a closed Application has an outcome")
        if not str(status.get("next_step") or "").strip():
            errors.append(f"{where}: an open Application needs a next step")
        try:
            parse_date(status.get("due"), f"{where}: due")
        except HHError as exc:
            errors.append(str(exc))
    return errors


def stage_label(stage, number) -> str:
    return f"interview round {number}" if stage == "interview" else str(stage)


# ---------------------------------------------------------------- commands


def cmd_init(args):
    raw = os.environ.get("HEADHUNTER_DATA_DIR") or "~/headhunter-data"
    root = Path(raw).expanduser().resolve()
    guard(root)
    created = ensure_layout(root)
    print(f"Data folder: {root}")
    print("Created: " + ", ".join(created) if created else "Already set up; nothing changed.")


def cmd_candidate_new(args):
    root = data_dir()
    ids = [cid for archived in (False, True) for cid, _ in candidate_dirs(root, archived)]
    cid = make_id("c", next_number(ids, "c"))
    folder = root / "candidates" / f"{cid}-{slugify(args.name)}"
    folder.mkdir()
    (folder / "sources").mkdir()
    (folder / "imports").mkdir()
    write_yaml(folder / "profile.yml", {
        "id": cid, "name": args.name, "name_en": args.name_en, "status": "active",
        "seniority": None, "location": None, "work_mode": None,
        "salary": {"current": None, "expected": None}, "created": today(),
    })
    for name in ("sources.yml", "facts.yml", "glossary.yml"):
        write_yaml(folder / name, [])
    (folder / "strategy.md").write_text(
        "# Strategy\n\nTarget Roles, positioning, and what to strengthen.\n", encoding="utf-8")
    print(f"{cid}  {folder}")


def cmd_candidate_list(args):
    root = data_dir()
    rows = candidate_dirs(root, archived=args.archived)
    for cid, folder in rows:
        data = load_candidate(folder)
        profile = data["profile"]
        print(f"{cid}  {profile.get('name', '?')}  {profile.get('status', '?')}  "
              f"{len(data['facts'])} facts  {len(data['sources'])} sources")
    if not rows:
        print("No archived Candidates." if args.archived else "No Candidates yet.")


def cmd_candidate_show(args):
    root = data_dir()
    folder = find_candidate(root, args.id)
    data = load_candidate(folder)
    profile, sources, facts = data["profile"], data["sources"], data["facts"]
    archived = "  [archived]" if folder.parent.name == "archive" else ""
    english = f" ({profile['name_en']})" if profile.get("name_en") else ""
    print(f"{profile.get('id')} {profile.get('name')}{english}{archived}")
    print(f"Status: {profile.get('status')} · Seniority: {profile.get('seniority') or '-'} · "
          f"Location: {profile.get('location') or '-'} · Experience: {years_experience(facts)} years")
    print(f"Folder: {folder}")
    states = Counter(s.get("state") for s in sources)
    print(f"Sources: {len(sources)}" + (" (" + ", ".join(f"{k} {v}" for k, v in states.items()) + ")" if sources else ""))
    live = [f for f in facts if f.get("state") != "superseded"]
    kinds = Counter(f.get("kind") for f in live)
    print(f"Facts: {len(live)}" + (" (" + ", ".join(f"{k} {kinds[k]}" for k in FACT_KINDS if kinds[k]) + ")" if live else ""))
    if live:
        levels = Counter(f.get("evidence") if f.get("origin") == "sourced" else "inferred, unconfirmed" for f in live)
        order = [*EVIDENCE, "inferred, unconfirmed"]
        print("Evidence: " + ", ".join(f"{k} {levels[k]}" for k in order if levels[k]))
    conflicts = [f["id"] for f in facts if f.get("state") == "conflict"]
    if conflicts:
        print("Conflicts waiting for the user: " + ", ".join(conflicts))
    tags = Counter(t for f in live if f.get("origin") == "sourced" and f.get("state") == "active" for t in f.get("tags") or [])
    if tags:
        print("Top Tags: " + ", ".join(f"{t} ({n})" for t, n in tags.most_common(8)))
    open_questions = [q for q in report_questions(folder) if q["open"]]
    print(f"Open follow-up questions: {len(open_questions)}")
    for q in open_questions:
        print(f"  {q['id']}: {q['text']}")
    strategy = folder / "strategy.md"
    if strategy.exists():
        text = re.split(r"(?m)^## Roles\n", strategy.read_text(encoding="utf-8"))[0]
        lines = [line.strip() for line in text.splitlines() if line.strip() and not line.startswith("#")]
        print("Strategy: " + (" ".join(lines[:3]) if lines else "-"))
    roles = role_dirs(folder)
    print(f"Roles: {len(roles)}")
    for slug, path in roles:
        role = load_role(path)
        stale = role_stale(path, role, facts)
        status = "not built" if stale == ["not built yet"] else ("profile stale" if stale else "profile current")
        print(f"  {slug}: {role.get('title')} (priority {role.get('priority')}, {role.get('state')}, {status})")
    evaluations = evaluation_files(folder)
    print(f"Evaluations: {len(evaluations)}")
    for jid, path in evaluations:
        ev = read_job(path)[0]
        written = [lang for lang in RESUME_LANGS if (path.parent / f"resume.{lang}.md").exists()]
        print(f"  {jid}: {ev.get('rating')} ({ev.get('score')}) under {ev.get('role') or 'no Role'}, {ev.get('evaluated')}"
              + (f"; resumes: {', '.join(written)}" if written else ""))
    statuses = [(jid, read_yaml(path / "status.yml", {})) for jid, path in application_dirs(folder)
                if (path / "status.yml").exists()]
    print(f"Applications: {len(statuses)}")
    for jid, status in statuses:
        if status.get("stage") == "closed":
            print(f"  {jid}: closed ({status.get('outcome')})")
        else:
            late = "  OVERDUE" if str(status.get("due")) < today() else ""
            print(f"  {jid}: {stage_label(status.get('stage'), status.get('round'))}; next: {status.get('next_step')} "
                  f"by {status.get('due')}{late}")


def move_candidate(args, to_archive: bool):
    root = data_dir()
    folder = find_candidate(root, args.id, archived=not to_archive)
    target = root / ("archive" if to_archive else "candidates") / folder.name
    if target.exists():
        raise HHError(f"{target} already exists")
    shutil.move(str(folder), str(target))
    rebuild_index(root)
    print(f"{'Archived' if to_archive else 'Restored'} {folder.name} → {target}")


def cmd_source_add(args):
    root = data_dir()
    folder = find_candidate(root, args.id, archived=False)
    if args.path == "-":
        data, filename, origin = sys.stdin.buffer.read(), f"{args.type}.md", "pasted by the user"
    else:
        path = Path(args.path).expanduser()
        if not path.is_file():
            raise HHError(f"{path} is not a file")
        data, filename, origin = path.read_bytes(), path.name, path.name
    sid, stored = register_source(folder, args.type, args.origin or origin, args.evidence, args.state, filename, data)
    print(f"{sid}  {stored}")


def cmd_source_github(args):
    root = data_dir()
    folder = find_candidate(root, args.id, archived=False)
    target = re.sub(r"^https?://github\.com/", "", args.target.strip().rstrip("/"))
    if "/" in target:
        url, text = github_repo_snapshot(target, args.author)
        filename = f"github-{target.replace('/', '-')}.md"
    else:
        url, text = github_user_snapshot(target)
        filename = f"github-{target}.md"
    sid, stored = register_source(folder, "github", url, None, "read", filename, text.encode("utf-8"))
    print(f"{sid}  {stored}")


def cmd_source_state(args):
    root = data_dir()
    folder = find_candidate(root, args.id, archived=False)
    sources = read_list(folder / "sources.yml")
    for source in sources:
        if source.get("id") == args.source:
            source["state"] = args.state
            write_yaml(folder / "sources.yml", sources)
            print(f"{args.source}  state: {args.state}")
            return
    raise HHError(f"no Source {args.source} for {folder.name}")


def cmd_fact_add(args):
    root = data_dir()
    folder = find_candidate(root, args.id, archived=False)
    facts = read_list(folder / "facts.yml")
    sources = read_list(folder / "sources.yml")
    payload = read_payload(args)
    items = payload if isinstance(payload, list) else [payload]
    number = next_number([f.get("id") for f in facts if isinstance(f, dict)], "f")
    new = []
    for item in items:
        if not isinstance(item, dict):
            raise HHError("each Fact must be a mapping")
        if "id" in item:
            raise HHError("leave id out; it is assigned")
        fact = {"id": make_id("f", number), "tags": [], "sources": [], "origin": "sourced",
                "missing": [], "state": "active"}
        fact.update(item)
        new.append(fact)
        number += 1
    save_facts(root, folder, facts + new, sources)
    for fact in new:
        print(f"{fact['id']}  {fact['kind']}  {fact['statement']}")


def cmd_fact_update(args):
    root = data_dir()
    folder = find_candidate(root, args.id, archived=False)
    facts = read_list(folder / "facts.yml")
    sources = read_list(folder / "sources.yml")
    patch = read_payload(args)
    if not isinstance(patch, dict):
        raise HHError("the update must be a mapping of fields")
    if patch.get("id", args.fact) != args.fact:
        raise HHError("a Fact id cannot change")
    for n, fact in enumerate(facts):
        if isinstance(fact, dict) and fact.get("id") == args.fact:
            updated = dict(fact)
            for key, value in patch.items():
                if value is None:
                    updated.pop(key, None)
                else:
                    updated[key] = value
            facts[n] = updated
            save_facts(root, folder, facts, sources)
            print(f"{args.fact}  updated: {', '.join(patch)}")
            return
    raise HHError(f"no Fact {args.fact} for {folder.name}")


def cmd_next_id(args):
    root = data_dir()
    folder = find_candidate(root, args.id, archived=False)
    if args.kind == "fact":
        ids, prefix = [f.get("id") for f in read_list(folder / "facts.yml")], "f"
    else:
        ids, prefix = [q["id"] for q in report_questions(folder)], "q"
    first = next_number(ids, prefix)
    print("\n".join(make_id(prefix, n) for n in range(first, first + args.count)))


def cmd_import_report(args):
    root = data_dir()
    folder = find_candidate(root, args.id, archived=False)
    source = next((s for s in read_list(folder / "sources.yml") if s.get("id") == args.source), None)
    if source is None:
        raise HHError(f"no Source {args.source} for {folder.name}")
    path = folder / "imports" / f"{today()}-{args.source}.md"
    if not path.exists():
        cid = candidate_id(folder.name.split("-")[1])
        header = [
            f"# Import report: {args.source}", "",
            f"- Candidate: {cid}",
            f"- Source: {args.source} ({source.get('type')}), `{source.get('file')}`",
            f"- Imported: {today()}",
            f"- Readable: {source.get('state')}", "",
        ]
        body = [line for section in REPORT_SECTIONS for line in (f"## {section}", "", "")]
        path.write_text("\n".join(header + body).rstrip() + "\n", encoding="utf-8")
    print(path)


def cmd_questions(args):
    root = data_dir()
    targets = [(candidate_id(args.id), find_candidate(root, args.id, archived=False))] if args.id else candidate_dirs(root)
    found = 0
    for cid, folder in targets:
        for q in report_questions(folder):
            if q["open"]:
                found += 1
                print(f"{cid}  {q['id']}  ({q['report']})  {q['text']}")
    if not found:
        print("No open follow-up questions.")


def file_text(path: Path) -> tuple:
    """Return (page HTML or None, text) for a Word, HTML, PDF or text file."""
    if not path.is_file():
        raise HHError(f"{path} is not a file")
    suffix = path.suffix.lower()
    if suffix == ".docx":
        return None, docx_text(path)
    if suffix in (".html", ".htm"):
        page = path.read_text(encoding="utf-8", errors="replace")
        return page, hhweb.html_to_text(page)
    if suffix in (".txt", ".md", ".csv", ".json", ".yml", ".yaml", ""):
        return None, path.read_text(encoding="utf-8", errors="replace")
    if suffix == ".pdf" and shutil.which("pdftotext"):
        result = subprocess.run(["pdftotext", "-layout", str(path), "-"], capture_output=True, text=True, check=False)
        return None, result.stdout
    if suffix == ".pdf":
        raise HHError("no PDF text extractor is installed; read the PDF with your own file reading and save its "
                      "text to a .txt file, or record that it could not be read")
    raise HHError(f"{suffix} files are not text; read it with your own file reading (images only if you can see "
                  "images) and save the text to a .txt file, or record that it could not be read")


def cmd_extract_text(args):
    print(file_text(Path(args.path).expanduser())[1])


def cmd_taxonomy_find(args):
    root = data_dir()
    taxonomy = load_taxonomy(root)
    term = args.term.strip().lower()
    hits = []
    for tag in taxonomy.get("tags") or []:
        terms = [tag.get("id"), tag.get("en"), tag.get("zh"), *(tag.get("aliases") or [])]
        if any(term == str(t).lower() for t in terms if t):
            hits.insert(0, tag)
        elif any(term in str(t).lower() for t in terms if t):
            hits.append(tag)
    for tag in hits:
        aliases = ", ".join(tag.get("aliases") or [])
        print(f"{tag['id']}  {tag.get('en')} / {tag.get('zh')}" + (f"  (aliases: {aliases})" if aliases else ""))
    if not hits:
        print(f"No Tag matches {args.term!r}. Propose a new Tag in the Import report.")


def cmd_validate(args):
    root = data_dir()
    taxonomy = load_taxonomy(root)
    errors = validate_taxonomy(taxonomy)
    known = tag_ids(taxonomy)
    if args.id:
        targets = [find_candidate(root, args.id)]
    else:
        targets = [folder for archived in (False, True) for _, folder in candidate_dirs(root, archived)]
    for folder in targets:
        errors.extend(validate_candidate(folder, known))
    jobs = [] if args.id else job_files(root)
    for path in jobs:
        try:
            front, body = read_job(path)
        except HHError as exc:
            errors.append(str(exc))
            continue
        errors.extend(check_job(front, body, taxonomy, path.name))
    if errors:
        print("\n".join(errors))
        return 1
    snapshots = f" and {len(jobs)} Job snapshot(s)" if not args.id else ""
    print(f"OK: taxonomy.yml, {len(targets)} Candidate folder(s){snapshots} are valid.")
    return 0


def cmd_index(args):
    root = data_dir()
    counts = rebuild_index(root)
    print(f"Rebuilt {root / 'index.sqlite'}: {counts['candidates']} Candidates, {counts['facts']} Facts, "
          f"{counts['roles']} Roles, {counts['evaluations']} Evaluations, {counts['applications']} Applications.")


def cmd_job_listing(args):
    root = data_dir()
    url = web(hhweb.clean_url, args.url)
    if hhweb.site_of(url) == "yourator":
        jobs = web(hhweb.yourator_listing, url, args.page)
    else:
        page = web(hhweb.fetch, url)
        jobs = [{"id": jid, "title": title, "url": link} for jid, title, link in hhweb.listing_links(page, url)]
    saved = 0
    for job in jobs:
        exists = (root / "jobs" / f"{job['id']}.md").exists()
        saved += exists
        details = " | ".join(job[k] for k in ("title", "company", "location", "salary") if job.get(k))
        print(f"{'*' if exists else ' '} {job['id']}  {details}  {job['url']}")
    if not jobs:
        print("No Jobs found on this page.")
    else:
        print(f"{len(jobs)} Jobs" + (f"; {saved} already saved (*)" if saved else ""))


def cmd_job_fetch(args):
    root = data_dir()
    url = web(hhweb.clean_url, args.url) if args.url else None
    if args.file:
        page, text = file_text(Path(args.file).expanduser())
        read_with = "file, pasted or browser; say which in job save"
    elif url:
        page, read_with = web(hhweb.fetch, url), "fetch"
        text = hhweb.html_to_text(page)
    else:
        raise HHError("give the Job's url, a --file with its content, or both")
    if url:
        jid, site, _ = web(hhweb.job_id, url)
        snapshot = root / "jobs" / f"{jid}.md"
        print(f"Job: {jid} ({site})")
        print(f"URL: {url}")
        print(f"Snapshot: {'already saved at ' + str(snapshot) if snapshot.exists() else 'not saved yet'}")
    else:
        print("Job: no link given; job save gives it an id from its company and title")
    print(f"Read with: {read_with}")
    posting = hhweb.job_posting(page) if page else None
    if posting:
        fields = hhweb.posting_fields(posting)
        print("\n## Structured data (JSON-LD)\n")
        for key in ("title", "company", "location", "salary", "employment_type", "posted", "valid_through"):
            print(f"- {key}: {fields[key] or '-'}")
    print("\n## Page text\n")
    print(text.strip()[:args.max_chars])


def cmd_job_save(args):
    root = data_dir()
    taxonomy = load_taxonomy(root)
    data = read_payload(args)
    if not isinstance(data, dict):
        raise HHError("the Job must be a mapping")
    url = web(hhweb.clean_url, str(data["url"])) if data.get("url") else None
    jid, site, site_id = identify_job({**data, "url": url})
    path = root / "jobs" / f"{jid}.md"
    if path.exists() and not args.replace:
        raise HHError(f"{path} already exists; pass --replace to save a new reading over it")
    default_read = "fetch" if url and hhweb.read_method(url) == "fetch" else None
    front = {
        "id": jid, "site": site, "site_id": site_id, **({"url": url} if url else {}),
        **{k: data[k] for k in ("title", "company", "location", "salary", "work_mode", "employment_type", "posted")
           if data.get(k) not in (None, "")},
        "read": today(), "read_with": data.get("read_with") or default_read,
        "must_haves": data.get("must_haves") or [], "nice_to_haves": data.get("nice_to_haves") or [],
        "duties": data.get("duties") or [],
    }
    for key in ("must_haves", "nice_to_haves"):
        front[key] = [
            {"text": item.get("text"), "tags": item.get("tags") or [],
             **({"proposed": item["proposed"]} if item.get("proposed") else {})}
            if isinstance(item, dict) else item
            for item in front[key]
        ]
    text = str(data.get("text") or "").strip()
    if not text:
        raise HHError("text (the posting text as read) is required")
    body = render_job(front, text)
    errors = check_job(front, body, taxonomy, path.name)
    if errors:
        raise HHError("nothing written:\n  " + "\n  ".join(errors))
    path.write_text(body, encoding="utf-8")
    proposed = sum(len(i.get("proposed") or []) for k in ("must_haves", "nice_to_haves") for i in front[k])
    print(f"{jid}  {path}")
    print(f"{len(front['must_haves'])} must-haves, {len(front['nice_to_haves'])} nice-to-haves, "
          f"{len(front['duties'])} duties, {len(requirement_tags(front))} Tags"
          + (f", {proposed} proposed terms" if proposed else ""))


def cmd_job_list(args):
    root = data_dir()
    paths = job_files(root)
    for path in paths:
        front, _ = read_job(path)
        print(f"{front.get('id')}  {front.get('read')}  {front.get('title')} · {front.get('company')}  "
              f"({len(front.get('must_haves') or [])} must-haves, {len(front.get('nice_to_haves') or [])} nice-to-haves)")
    if not paths:
        print("No Job snapshots yet.")


def cmd_job_accept(args):
    root = data_dir()
    taxonomy = load_taxonomy(root)
    tag = resolve_tag(taxonomy, args.tag)
    term = args.term.strip().lower()
    changed = 0
    for path in job_files(root):
        front, body = read_job(path)
        hits = 0
        for key in ("must_haves", "nice_to_haves"):
            for item in front.get(key) or []:
                proposed = [p for p in item.get("proposed") or [] if str(p).strip().lower() != term]
                if len(proposed) == len(item.get("proposed") or []):
                    continue
                hits += 1
                item["tags"] = list(item.get("tags") or []) + ([tag] if tag not in (item.get("tags") or []) else [])
                if proposed:
                    item["proposed"] = proposed
                else:
                    item.pop("proposed", None)
        if hits:
            header = hhyaml.dumps({key: front[key] for key in JOB_ORDER if key in front})
            path.write_text(f"---\n{header}---\n{body}", encoding="utf-8")
            changed += 1
            print(f"{front['id']}: {args.term!r} → {tag} in {hits} requirement(s)")
    if not changed:
        print(f"No Job snapshot proposes {args.term!r}.")


def save_role(root: Path, folder: Path, slug: str, role: dict) -> None:
    known = tag_ids(load_taxonomy(root))
    numbers = [id_number(r.get("id"), "r") for r in role.get("requirements") or [] if isinstance(r, dict)]
    following = max((n or 0 for n in numbers), default=0) + 1
    for req in role.get("requirements") or []:
        if isinstance(req, dict) and not req.get("id"):
            req["id"] = make_id("r", following)
            following += 1
        if isinstance(req, dict):
            req.setdefault("tags", [])
    errors = check_role(role, slug, folder, known)
    if errors:
        raise HHError("nothing written:\n  " + "\n  ".join(errors))
    (folder / "roles" / slug).mkdir(parents=True, exist_ok=True)
    write_yaml(folder / "roles" / slug / "role.yml", ordered_role(role))
    update_strategy_roles(folder)


def cmd_role_new(args):
    root = data_dir()
    folder = find_candidate(root, args.id, archived=False)
    data = read_payload(args)
    if not isinstance(data, dict):
        raise HHError("the Role must be a mapping")
    slug = slugify(str(data.get("title") or ""))
    if (folder / "roles" / slug).exists():
        raise HHError(f"{folder.name} already has the Role {slug}")
    role = {"priority": len(role_dirs(folder)) + 1, "state": "active", "industries": [], **data, "created": today()}
    for req in role.get("requirements") or []:
        if isinstance(req, dict) and req.get("id"):
            raise HHError("leave requirement ids out; they are assigned")
    save_role(root, folder, slug, role)
    print(f"{slug}  {folder / 'roles' / slug / 'role.yml'}")
    print(f"{len(role.get('requirements') or [])} requirements; build its profile with `role build`")


def cmd_role_update(args):
    root = data_dir()
    folder = find_candidate(root, args.id, archived=False)
    role = load_role(find_role(folder, args.role))
    patch = read_payload(args)
    if not isinstance(patch, dict):
        raise HHError("the update must be a mapping of fields")
    if "title" in patch and slugify(str(patch["title"])) != args.role:
        raise HHError("a Role's title sets its folder name; create a new Role for a different title")
    for key, value in patch.items():
        if value is None:
            role.pop(key, None)
        else:
            role[key] = value
    save_role(root, folder, args.role, role)
    stale = role_stale(folder / "roles" / args.role, role, read_list(folder / "facts.yml"))
    print(f"{args.role}  updated: {', '.join(patch)}" + (f"; profile: {'; '.join(stale)}" if stale else ""))


def cmd_role_list(args):
    root = data_dir()
    targets = [(candidate_id(args.id), find_candidate(root, args.id))] if args.id else candidate_dirs(root)
    found = 0
    for cid, folder in targets:
        facts = read_list(folder / "facts.yml")
        for slug, path in role_dirs(folder):
            found += 1
            role = load_role(path)
            reqs = role.get("requirements") or []
            stale = role_stale(path, role, facts)
            status = stale[0] if stale == ["not built yet"] else ("stale: " + "; ".join(stale) if stale else "current")
            print(f"{cid}  {slug}  {role.get('title')}  priority {role.get('priority')}, {role.get('state')}, "
                  f"{sum(r.get('kind') == 'must' for r in reqs)} must / {sum(r.get('kind') == 'nice' for r in reqs)} nice  "
                  f"profile {status}")
    if not found:
        print("No Roles yet.")


def cmd_role_match(args):
    root = data_dir()
    folder = find_candidate(root, args.id, archived=False)
    role = load_role(find_role(folder, args.role))
    facts = [f for f in read_list(folder / "facts.yml") if isinstance(f, dict) and f.get("state") != "superseded"]
    rank = {level: n for n, level in enumerate(EVIDENCE)}
    print(f"{args.role}: Facts sharing a Tag with each requirement, strongest evidence first\n")
    for req in role.get("requirements") or []:
        tags = set(req.get("tags") or [])
        hits = [f for f in facts if tags & set(f.get("tags") or [])]
        hits.sort(key=lambda f: (f.get("origin") != "sourced", rank.get(str(f.get("evidence")), 9), f.get("id")))
        print(f"{req['id']} ({req['kind']}) {req['text']}  [{', '.join(sorted(tags)) or 'no Tags'}]")
        for fact in hits:
            label = fact.get("evidence") if fact.get("origin") == "sourced" else "inferred, unconfirmed"
            extra = ", conflict" if fact.get("state") == "conflict" else ""
            print(f"    {fact['id']}  [{label}{extra}]  {fact.get('statement')}")
        if not hits:
            print("    no Fact shares a Tag; look for related Facts or record a gap")


def cmd_role_build(args):
    root = data_dir()
    folder = find_candidate(root, args.id, archived=False)
    path = find_role(folder, args.role)
    role = load_role(path)
    facts = read_list(folder / "facts.yml")
    data = read_payload(args)
    if not isinstance(data, dict):
        raise HHError("the Role profile must be a mapping")
    by_id = {f.get("id"): f for f in facts if isinstance(f, dict)}
    reqs = {r.get("id"): r for r in role.get("requirements") or [] if isinstance(r, dict)}
    errors = []
    if not reqs:
        errors.append("the Role has no requirements yet")
    positioning = data.get("positioning") or {}
    for key in ("headline", "summary"):
        if not str(positioning.get(key) or "").strip():
            errors.append(f"positioning needs a {key}")
    if not positioning.get("facts"):
        errors.append("positioning needs the Facts it is built from")
    for fid in positioning.get("facts") or []:
        problem = fact_problem(by_id, fid)
        if problem:
            errors.append(f"positioning: {problem}")
    evidence = check_evidence(reqs, data.get("evidence"), by_id, errors)
    gaps = check_gaps(reqs, evidence, data.get("gaps"), by_id, errors)
    if errors:
        raise HHError("nothing written:\n  " + "\n  ".join(errors))
    referenced = set(positioning["facts"]) | {c["id"] for cs in evidence.values() for c in cs} | {
        fid for g in gaps for fid in g["facts"]}
    front = {
        "role": args.role,
        "built": today(),
        "built_from": {
            "role": role_digest(role),
            "facts_through": make_id("f", max((id_number(f, "f") or 0 for f in by_id), default=0)),
            "facts": {fid: digest(by_id[fid]) for fid in sorted(referenced)},
        },
        "positioning": {k: positioning[k] for k in ("headline", "summary", "facts")},
        "evidence": [{"requirement": rid, "facts": evidence[rid]} for rid in reqs if rid in evidence],
        "gaps": gaps,
    }
    lines = [f"# {role.get('title')}: Role profile", "", positioning["headline"], "", positioning["summary"],
             "", f"Based on {', '.join(positioning['facts'])}.", "", "## Evidence", ""]
    for entry in front["evidence"]:
        req = reqs[entry["requirement"]]
        lines.append(f"### {entry['requirement']} ({req['kind']}) {req['text']}")
        lines += [f"- {c['id']} ({by_id[c['id']].get('evidence')}): {by_id[c['id']].get('statement')} — {c['why']}"
                  for c in entry["facts"]]
        lines.append("")
    lines += ["## Gaps", ""]
    for gap in gaps:
        req = reqs[gap["requirement"]]
        linked = f" ({', '.join(gap['facts'])})" if gap["facts"] else ""
        lines.append(f"- {gap['requirement']} ({req['kind']}) {req['text']}: {gap['kind']}{linked} — {gap['close']}")
    if not gaps:
        lines.append("None.")
    (path / "profile.md").write_text(f"---\n{hhyaml.dumps(front)}---\n\n" + "\n".join(lines).rstrip() + "\n",
                                     encoding="utf-8")
    must_gaps = sum(1 for g in gaps if reqs[g["requirement"]]["kind"] == "must" and g["kind"] != "weak-evidence")
    print(f"{args.role}  {path / 'profile.md'}")
    print(f"{len(front['evidence'])} requirements with evidence, {len(gaps)} gaps ({must_gaps} on must-haves)")


def cmd_role_stale(args):
    root = data_dir()
    targets = [(candidate_id(args.id), find_candidate(root, args.id))] if args.id else candidate_dirs(root)
    found = 0
    for cid, folder in targets:
        facts = read_list(folder / "facts.yml")
        for slug, path in role_dirs(folder):
            role = load_role(path)
            reasons = role_stale(path, role, facts)
            if reasons and role.get("state") != "dropped":
                found += 1
                print(f"{cid}  {slug}: {'; '.join(reasons)}")
    if not found:
        print("Every Role profile is current.")


def cmd_role_refine(args):
    root = data_dir()
    folder = find_candidate(root, args.id, archived=False)
    role = load_role(find_role(folder, args.role))
    jobs, proposals = refine_proposals(root, folder, args.role, role, load_taxonomy(root))
    if not args.accept:
        print(f"{args.role}: {len(jobs)} Jobs evaluated under this Role" + (f": {', '.join(jobs)}" if jobs else ""))
        adds = [p for p in proposals if "requirement" not in p]
        cites = [p for p in proposals if "requirement" in p]
        if adds:
            print("\nAdd: Tags required by 2 or more of these Jobs that no requirement has")
            for p in adds:
                print(f"  {p['key']}  ({p['text']}) in {len(p['jobs'])} Jobs, must-have in {p['must_in']} → {p['kind']}")
                print("".join(f"      {text}\n" for text in p["texts"]), end="")
        if cites:
            print("\nCite Jobs: assumed or Job requirements that these Jobs also ask for")
            for p in cites:
                req = p["requirement"]
                print(f"  {p['key']} ({req.get('origin')}) {req.get('text')} → origin job, add {', '.join(p['jobs'])}")
        if proposals:
            keys = " ".join(p["key"] for p in proposals)
            print(f"\nShow these to the user; apply the ones they accept with: role refine {args.id} {args.role} --accept {keys}")
        else:
            print("No requirement recurs in 2 or more of these Jobs beyond what role.yml has.")
        return
    by_key = {p["key"]: p for p in proposals}
    unknown = [key for key in args.accept if key not in by_key]
    if unknown:
        raise HHError(f"no proposal {', '.join(unknown)}; proposals: {', '.join(by_key) or 'none'}")
    for key in args.accept:
        p = by_key[key]
        if "requirement" in p:
            req = next(r for r in role["requirements"] if isinstance(r, dict) and r.get("id") == key)
            req["origin"] = "job"
            req["jobs"] = list(req.get("jobs") or []) + p["jobs"]
        else:
            role.setdefault("requirements", []).append(
                {k: p[k] for k in ("kind", "text", "tags", "origin", "jobs")})
    save_role(root, folder, args.role, role)
    stale = role_stale(folder / "roles" / args.role, role, read_list(folder / "facts.yml"))
    print(f"{args.role}  applied: {', '.join(args.accept)}" + (f"; profile: {'; '.join(stale)}" if stale else ""))


def cmd_evaluation_match(args):
    root = data_dir()
    job_path = root / "jobs" / f"{args.job}.md"
    if not job_path.exists():
        raise HHError(f"Job {args.job} has no snapshot in jobs/; save it with job save first")
    job, _ = read_job(job_path)
    reqs = job_requirements(job)
    job_tags = set(requirement_tags(job))
    must_tags = {t for r in reqs.values() if r["kind"] == "must" for t in r["tags"]}
    print(f"{args.job}  {job.get('title')} · {job.get('company')}")
    print(f"Job Tags: {len(job_tags)} ({len(must_tags)} on must-haves)\n")
    con = open_index(root)
    if args.id:
        find_candidate(root, args.id, archived=False)
        cids = [candidate_id(args.id)]
    else:
        cids = [r[0] for r in con.execute("SELECT id FROM candidates WHERE status = 'active' ORDER BY id")]
    found = []
    for cid in cids:
        name, seniority, years = con.execute(
            "SELECT name, seniority, years_experience FROM candidates WHERE id = ?", (cid,)).fetchone()
        have = {r[0] for r in con.execute("SELECT tag FROM candidate_tags WHERE candidate_id = ?", (cid,))}
        roles = []
        for slug, priority, built, stale in con.execute(
                "SELECT slug, priority, built, stale FROM roles WHERE candidate_id = ? AND state = 'active'", (cid,)):
            tags = {r[0] for r in con.execute(
                "SELECT tag FROM role_requirement_tags WHERE candidate_id = ? AND role = ?", (cid, slug))}
            gaps = con.execute(
                "SELECT COUNT(*) FROM role_gaps g JOIN role_requirements q ON q.candidate_id = g.candidate_id "
                "AND q.role = g.role AND q.id = g.requirement WHERE g.candidate_id = ? AND g.role = ? "
                "AND q.kind = 'must' AND g.kind != 'weak-evidence'", (cid, slug)).fetchone()[0]
            roles.append((len(tags & must_tags), len(tags & job_tags), priority or 99, slug, built, stale, gaps))
        roles.sort(key=lambda r: (-r[0], -r[1], r[2]))
        best = (roles[0][0], roles[0][1]) if roles and roles[0][1] else (0, 0)
        found.append((best, cid, name, seniority, years, have, roles))
    found.sort(key=lambda row: (-row[0][0], -row[0][1], row[1]))
    hidden = 0
    for best, cid, name, seniority, years, have, roles in found:
        if not args.id and not args.all and not best[1]:
            hidden += 1
            continue
        print(f"{cid} {name}  ({seniority or 'seniority not set'}, {years} years)  Facts cover "
              f"{len(have & job_tags)} of {len(job_tags)} Job Tags ({len(have & must_tags)} of {len(must_tags)} on must-haves)")
        for shared_must, shared, _, slug, built, stale, gaps in roles:
            profile = f"profile built {built}, must-have gaps: {gaps}" + (", stale" if stale else "") if built \
                else "profile not built"
            print(f"    role {slug}: shares {shared} of {len(job_tags)} Job Tags ({shared_must} on must-haves); {profile}")
        if not any(r[1] for r in roles):
            print("    no active Role shares a Tag with this Job")
        done = con.execute("SELECT role, score, rating FROM evaluations WHERE candidate_id = ? AND job_id = ?",
                           (cid, args.job)).fetchone()
        if done:
            print(f"    evaluated: {done[2]} ({done[1]}) under {done[0] or 'no Role'}")
    if hidden:
        print(f"Not listed: {hidden} other active {'Candidate' if hidden == 1 else 'Candidates'} with no active Role "
              "sharing a Tag with this Job; pass --all to list them.")
    if not found:
        print("No active Candidates.")
    if not args.id:
        return
    folder = find_candidate(root, args.id, archived=False)
    profile = read_yaml(folder / "profile.yml", {})
    profile = profile if isinstance(profile, dict) else {}
    salary = profile.get("salary")
    salary = salary if isinstance(salary, dict) else {}
    print(f"\nJob: {job.get('salary')} · {job.get('location')} · {job.get('work_mode') or 'work mode not stated'}")
    print(f"Candidate wants: salary {salary.get('expected') or 'not recorded'} · "
          f"{profile.get('location') or 'location not recorded'} · {profile.get('work_mode') or 'work mode not recorded'}")
    facts = [f for f in read_list(folder / "facts.yml") if isinstance(f, dict) and f.get("state") != "superseded"]
    rank = {level: n for n, level in enumerate(EVIDENCE)}
    print("\nFacts sharing a Tag with each Job requirement, strongest evidence first\n")
    for rid, req in reqs.items():
        tags = set(req["tags"])
        proposed = f"; proposed: {', '.join(req['proposed'])}" if req["proposed"] else ""
        print(f"{rid} {req['text']}  [{', '.join(sorted(tags)) or 'no Tags'}{proposed}]")
        hits = sorted((f for f in facts if tags & set(f.get("tags") or [])),
                      key=lambda f: (f.get("origin") != "sourced", rank.get(str(f.get("evidence")), 9), f.get("id")))
        for fact in hits:
            label = fact.get("evidence") if fact.get("origin") == "sourced" else "inferred, unconfirmed"
            extra = ", conflict" if fact.get("state") == "conflict" else ""
            print(f"    {fact['id']}  [{fact.get('kind')}, {label}{extra}]  {fact.get('statement')}")
        if not hits:
            print("    no Fact shares a Tag; look for related Facts or record a gap")
    print("\nAchievement targets")
    for target, text in achievement_targets(job, reqs).items():
        print(f"  {target}  {text}")


def cmd_evaluation_save(args):
    root = data_dir()
    folder = find_candidate(root, args.id, archived=False)
    job_path = root / "jobs" / f"{args.job}.md"
    if not job_path.exists():
        raise HHError(f"Job {args.job} has no snapshot in jobs/; save it with job save first")
    job, _ = read_job(job_path)
    target = folder / "applications" / args.job / "evaluation.md"
    if target.exists() and not args.replace:
        raise HHError(f"{target} already exists; pass --replace to evaluate again")
    data = read_payload(args)
    if not isinstance(data, dict):
        raise HHError("the Evaluation must be a mapping")
    known = tag_ids(load_taxonomy(root))
    profile = read_yaml(folder / "profile.yml", {})
    profile = profile if isinstance(profile, dict) else {}
    facts = read_list(folder / "facts.yml")
    by_id = {f.get("id"): f for f in facts if isinstance(f, dict)}
    reqs = job_requirements(job)
    errors = []
    allowed = ("role", "job_level", "industries", "domains", "evidence", "gaps", "hard", "achievements",
               "conditions", "risks", "summary")
    errors += [f"unknown field {key!r}; fields are {', '.join(allowed)}" for key in data if key not in allowed]
    if not reqs:
        errors.append(f"Job {args.job} lists no requirements")
    slug, role = data.get("role"), None
    if slug:
        try:
            role = load_role(find_role(folder, str(slug)))
        except HHError as exc:
            errors.append(str(exc))
        else:
            if role.get("state") == "dropped":
                errors.append(f"the Role {slug} is dropped; choose another Role or evaluate without one")

    evidence = check_evidence(reqs, data.get("evidence"), by_id, errors)
    hard, failed, details = [], set(), {}
    for entry in data.get("hard") or []:
        rid, kind = entry.get("requirement"), entry.get("kind")
        where = f"hard {rid}"
        if rid not in reqs:
            errors.append(f"hard: unknown requirement {rid}")
            continue
        if rid in details:
            errors.append(f"{where}: listed twice")
            continue
        if kind not in HARD_KINDS:
            errors.append(f"{where}: kind must be one of {', '.join(HARD_KINDS)}")
            continue
        if reqs[rid]["kind"] != "must":
            errors.append(f"{where}: only must-haves can be hard requirements")
            continue
        result = {"requirement": rid, "kind": kind}
        if kind == "years":
            minimum = entry.get("min_years")
            if isinstance(minimum, bool) or not isinstance(minimum, (int, float)) or minimum <= 0:
                errors.append(f"{where}: min_years must be the number of years the Job asks for")
                continue
            result["min_years"] = minimum
            counted = [by_id[c["id"]] for c in evidence.get(rid, [])
                       if by_id[c["id"]].get("kind") == "experience" and by_id[c["id"]].get("period") is not None]
            if evidence.get(rid) and not counted:
                errors.append(f"{where}: cite experience Facts with a period so their years can be counted")
                continue
            if counted:
                result["years"] = years_experience(counted)
                result["result"] = "met" if result["years"] >= minimum else "failed"
            else:
                result["result"] = "unknown"
        elif entry.get("met") is False:
            linked = list(entry.get("facts") or [])
            for fid in linked:
                problem = fact_problem(by_id, fid)
                if problem:
                    errors.append(f"{where}: {problem}")
            if not linked or not str(entry.get("why") or "").strip():
                errors.append(f"{where}: a failed hard requirement lists the Facts that show it and why")
            if rid in evidence:
                errors.append(f"{where}: a failed hard requirement has no evidence; remove it from evidence")
            result.update(result="failed", facts=linked, why=entry.get("why"))
        elif "met" in entry:
            errors.append(f"{where}: give met only as false, when the cited Facts show it is not met")
            continue
        else:
            result["result"] = "met" if rid in evidence else "unknown"
        if result["result"] == "failed":
            failed.add(rid)
        details[rid] = result
        hard.append(result)
    gaps = check_gaps(reqs, evidence, data.get("gaps"), by_id, errors, skip=failed)

    candidate_level, job_level = profile.get("seniority"), data.get("job_level")
    if candidate_level not in SENIORITY:
        errors.append("profile.yml has no seniority; ask the user and set it first")
    if job_level not in SENIORITY:
        errors.append(f"job_level must be the level the Job asks for: one of {', '.join(SENIORITY)}")
    industries, domains = data.get("industries") or [], data.get("domains") or []
    for key, values in (("industries", industries), ("domains", domains)):
        prefix = "industry/" if key == "industries" else "domain/"
        if not isinstance(values, list) or any(t not in known or not str(t).startswith(prefix) for t in values):
            errors.append(f"{key} must be {prefix[:-1]} Tags from taxonomy.yml")
    if not industries and not domains:
        errors.append("give the Job's industries or domains as Tags")

    targets = achievement_targets(job, reqs)
    achievements = []
    for entry in data.get("achievements") or []:
        fid, aim = entry.get("fact"), entry.get("target")
        where = f"achievement {fid}"
        problem = fact_problem(by_id, fid)
        if problem:
            errors.append(f"{where}: {problem}")
            continue
        if by_id[fid].get("kind") not in ("achievement", "project"):
            errors.append(f"{where}: {fid} is a Fact of kind {by_id[fid].get('kind')}; cite achievement or project Facts")
        elif "result" in (by_id[fid].get("missing") or []):
            errors.append(f"{where}: {fid} has no result yet; ask for it before counting it")
        if aim not in targets:
            errors.append(f"{where}: target must be one of {', '.join(targets) or 'the Job duties'}")
        if not str(entry.get("why") or "").strip():
            errors.append(f"{where}: say why it matches {aim}")
        achievements.append({"fact": fid, "target": aim, "why": entry.get("why")})

    given = data.get("conditions") or {}
    conditions = {}
    for key in CONDITIONS:
        item = given.get(key) if isinstance(given, dict) else None
        if not isinstance(item, dict) or item.get("fit") not in CONDITION_FITS:
            errors.append(f"conditions {key}: fit must be one of {', '.join(CONDITION_FITS)}")
        elif not str(item.get("why") or "").strip():
            errors.append(f"conditions {key}: say why")
        else:
            conditions[key] = {"fit": item["fit"], "why": item["why"]}
    errors += [f"conditions: unknown condition {key!r}" for key in given if key not in CONDITIONS] \
        if isinstance(given, dict) else ["conditions must be a mapping of salary, location and work_mode"]
    risks = []
    for item in data.get("risks") or []:
        if not isinstance(item, dict) or not str(item.get("risk") or "").strip() or not str(item.get("close") or "").strip():
            errors.append("each risk needs risk and close (how to reduce it)")
        else:
            risks.append({"risk": item["risk"], "close": item["close"]})
    summary = str(data.get("summary") or "").strip()
    if not summary:
        errors.append("summary is required: the recommendation in a few sentences")
    if errors:
        raise HHError("nothing written:\n  " + "\n  ".join(errors))

    scores, basis = {}, {}
    skill_reqs = [rid for rid in reqs if rid not in details]
    weights = {rid: 2 if reqs[rid]["kind"] == "must" else 1 for rid in skill_reqs}
    backed = [rid for rid in skill_reqs if rid in evidence]
    total = sum(weights.values())
    scores["skills"] = round(100 * sum(weights[r] for r in backed) / total) if total else 50
    basis["skills"] = (f"{len(backed)} of {len(skill_reqs)} requirements backed by sourced Facts; must-haves count twice"
                       if total else "the Job lists no requirements besides hard ones")
    steps = SENIORITY.index(candidate_level) - SENIORITY.index(job_level)
    scores["seniority"] = (100, 60, 30)[abs(steps)] if abs(steps) < 3 else 0
    fit = "matches" if not steps else (f"over-qualified by {steps}" if steps > 0 else f"under-qualified by {-steps}")
    basis["seniority"] = f"Job asks {job_level}; Candidate is {candidate_level} ({fit})"
    own = {t for f in facts if isinstance(f, dict) and f.get("state") == "active" and f.get("origin") == "sourced"
           for t in f.get("tags") or []}
    shared_industries, shared_domains = [t for t in industries if t in own], [t for t in domains if t in own]
    scores["industry"] = 100 if shared_industries else (60 if shared_domains else 0)
    basis["industry"] = ("same industry: " + ", ".join(shared_industries) if shared_industries
                         else "close domain: " + ", ".join(shared_domains) if shared_domains
                         else "no shared industry or domain")
    matched, needed = {a["target"] for a in achievements}, min(3, len(targets))
    scores["achievements"] = round(100 * min(1, len(matched) / needed)) if needed else 0
    counted = "duties" if job.get("duties") else "requirements"
    basis["achievements"] = f"measurable results for {len(matched)} of {needed} {counted} needed"
    scores["conditions"] = round(sum(CONDITION_FITS[c["fit"]] for c in conditions.values()) / len(CONDITIONS))
    basis["conditions"] = ", ".join(f"{key.replace('_', ' ')} {conditions[key]['fit']}" for key in CONDITIONS)
    score = round(sum(scores[key] * weight for key, weight, _ in RUBRIC) / 100)

    band = RATINGS[next(n for n, floor in enumerate(RATING_FLOORS) if score >= floor)]
    rating = RATINGS[min(RATINGS.index(band) + 1, len(RATINGS) - 1)] if failed else band
    unknown = [h for h in hard if h["result"] == "unknown"]
    gate = "failed" if failed else ("unconfirmed" if unknown else "passed")
    floors = {"high": f"{RATING_FLOORS[0]} and above", "medium": f"{RATING_FLOORS[1]} to {RATING_FLOORS[0] - 1}",
              "low": f"below {RATING_FLOORS[1]}"}
    reasons = [f"Fit score {score} is in the {band} band ({floors[band]})."]
    for h in hard:
        text = reqs[h["requirement"]]["text"]
        if h["result"] == "failed":
            why = (f"{h['years']} years of cited experience against {h['min_years']}" if h["kind"] == "years"
                   else h["why"])
            reasons.append(f"Fails the hard requirement {h['requirement']} ({text}): {why}.")
        elif h["result"] == "unknown":
            reasons.append(f"Hard requirement {h['requirement']} ({text}) is unconfirmed; confirm it before applying.")
    if failed:
        reasons.append(f"Failing a hard requirement lowers the rating from {band} to {rating}." if rating != band
                       else "Failing a hard requirement would lower the rating, but it is already low.")
    must_gaps = [g["requirement"] for g in gaps if reqs[g["requirement"]]["kind"] == "must"
                 and g["kind"] in ("missing", "to-confirm")]
    if must_gaps:
        noun = "must-have is" if len(must_gaps) == 1 else "must-haves are"
        reasons.append(f"{len(must_gaps)} {noun} missing or unconfirmed: {', '.join(must_gaps)}.")
    strongest = max(RUBRIC, key=lambda d: (scores[d[0]], d[1]))
    weakest = min(RUBRIC, key=lambda d: (scores[d[0]], -d[1]))
    reasons.append(f"Strongest: {strongest[2].lower()} ({scores[strongest[0]]}); "
                   f"weakest: {weakest[2].lower()} ({scores[weakest[0]]}).")

    front = {
        "candidate": candidate_id(args.id), "job": args.job, "role": slug or None, "evaluated": today(),
        "score": score, "rating": rating, "gate": gate, "dimensions": scores,
        "job_level": job_level, "candidate_level": candidate_level, "industries": industries, "domains": domains,
        "evidence": [{"requirement": rid, "facts": evidence[rid]} for rid in reqs if rid in evidence],
        "gaps": gaps, "hard": hard, "achievements": achievements, "conditions": conditions, "risks": risks,
        "summary": summary, "reasons": reasons,
    }
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(render_evaluation(front, job, reqs, role, by_id, profile, basis), encoding="utf-8")
    print(f"{args.job}  {target}")
    status = record_evaluated(folder, args.job, slug or None)
    print(f"Success rating: {rating} · fit score {score} · hard requirements {gate} · "
          f"{len(gaps)} {'gap' if len(gaps) == 1 else 'gaps'} ({len(must_gaps)} on must-haves missing or unconfirmed)")
    if status.get("stage") == "closed":
        print(f"Application: closed ({status.get('outcome')})")
    else:
        print(f"Application: {stage_label(status.get('stage'), status.get('round'))}; next: {status.get('next_step')} "
              f"by {status.get('due')}")
    if not role:
        print("No Role fits: offer to create one from this Job (see Evaluate Jobs in SKILL.md).")
        return
    stale = role_stale(folder / "roles" / str(slug), role, facts)
    if stale:
        print(f"Role profile {slug}: {'; '.join(stale)}; offer to rebuild it.")
    _, proposals = refine_proposals(root, folder, str(slug), role, load_taxonomy(root))
    if proposals:
        noun = "change" if len(proposals) == 1 else "changes"
        print(f"{len(proposals)} requirement {noun} proposed from the Jobs evaluated under {slug}: "
              f"run role refine {args.id} {slug}")


def cmd_evaluation_list(args):
    root = data_dir()
    con = open_index(root)
    sql = ("SELECT e.candidate_id, c.name, e.job_id, e.role, e.score, e.rating, e.gate, e.evaluated "
           "FROM evaluations e JOIN candidates c ON c.id = e.candidate_id WHERE 1 = 1")
    params: list = []
    if args.id:
        sql += " AND e.candidate_id = ?"
        params.append(candidate_id(args.id))
    if args.job:
        sql += " AND e.job_id = ?"
        params.append(args.job)
    if args.rating:
        sql += " AND e.rating = ?"
        params.append(args.rating)
    rows = con.execute(sql + " ORDER BY e.candidate_id, e.score DESC", params).fetchall()
    for cid, name, jid, role, score, rating, gate, evaluated in rows:
        path = root / "jobs" / f"{jid}.md"
        job = read_job(path)[0] if path.exists() else {}
        print(f"{cid} {name}  {jid}  {rating} ({score}, hard requirements {gate})  {role or 'no Role'}  {evaluated}  "
              f"{job.get('title', '?')} · {job.get('company', '?')}")
    if not rows:
        print("No Evaluations.")


def resume_context(root: Path, folder: Path, jid: str) -> tuple:
    """(Job, Evaluation, Role slug, Role profile block) of an evaluated Application whose Role profile is current."""
    job_path, ev_path = root / "jobs" / f"{jid}.md", folder / "applications" / jid / "evaluation.md"
    if not job_path.exists():
        raise HHError(f"Job {jid} has no snapshot in jobs/")
    if not ev_path.exists():
        raise HHError(f"{folder.name} has no Evaluation for {jid}; evaluate the Job first")
    job, evaluation = read_job(job_path)[0], read_job(ev_path)[0]
    slug = evaluation.get("role")
    if not slug:
        raise HHError(f"the Evaluation of {jid} has no Role; resumes start from a Role profile, so create a Role "
                      "from the Job (Evaluate Jobs, step 7) and evaluate it again")
    path = find_role(folder, str(slug))
    role = load_role(path)
    if role.get("state") == "dropped":
        raise HHError(f"the Role {slug} is dropped; evaluate the Job under another Role first")
    stale = role_stale(path, role, read_list(folder / "facts.yml"))
    if stale:
        raise HHError(f"the Role profile {slug} is out of date ({'; '.join(stale)}); rebuild it with role build first")
    return job, evaluation, str(slug), read_job(path / "profile.md")[0]


def write_pdfs(base: Path, name: str) -> list:
    """Print resume.zh.md and resume.en.md to PDF; return a line per PDF."""
    browser = find_browser()
    if not browser:
        raise HHError("no Chrome, Chromium or Edge found to print the PDFs; install one, or set HEADHUNTER_BROWSER to "
                      "its path, then run resume pdf")
    done = []
    for lang in RESUME_LANGS:
        body = read_job(base / f"resume.{lang}.md")[1]
        page, target = base / f".resume.{lang}.html", base / f"resume.{lang}.pdf"
        page.write_text(resume_html(body, lang, name), encoding="utf-8")
        try:
            print_pdf(browser, page, target)
        finally:
            page.unlink()
        left = fix_pdf_text(target)
        done.append(f"{target}" + (f"  (text layer still has: {' '.join(left)})" if left else ""))
    return done


def cmd_resume_plan(args):
    root = data_dir()
    folder = find_candidate(root, args.id, archived=False)
    job, evaluation, slug, profile_md = resume_context(root, folder, args.job)
    data = load_candidate(folder)
    profile, facts, glossary = data["profile"], data["facts"], data["glossary"]
    by_id = {f.get("id"): f for f in facts if isinstance(f, dict)}
    reqs = job_requirements(job)
    positioning = profile_md.get("positioning") or {}
    print(f"{candidate_id(args.id)} {profile.get('name')} × {args.job}  {job.get('title')} · {job.get('company')}")
    print(f"Evaluation: {evaluation.get('rating')} ({evaluation.get('score')}) under {slug}; Role profile built "
          f"{profile_md.get('built')} and current\n")
    print("Start from the Role profile's positioning:")
    print(f"  {positioning.get('headline')}\n  {positioning.get('summary')}")
    print(f"  Facts: {', '.join(positioning.get('facts') or [])}")
    order = [f"{e.get('requirement')} {', '.join(c.get('id') for c in e.get('facts') or [])}"
             for e in profile_md.get("evidence") or []]
    print("Its evidence, in order: " + "; ".join(order))
    print("\nJob requirements and the Facts the Evaluation cites:")
    evidence = {e.get("requirement"): [c.get("id") for c in e.get("facts") or []] for e in evaluation.get("evidence") or []}
    for rid, req in reqs.items():
        print(f"  {rid} {req['text']}: {', '.join(evidence.get(rid, [])) or '-'}")
    lacking = lacking_terms(job, evaluation, facts, load_taxonomy(root))
    gaps = sorted(set(lacking.values()), key=lambda r: list(reqs).index(r))
    print("\nLeave out (lacking in the Evaluation):" + ("" if gaps else " nothing"))
    for rid in gaps:
        print(f"  {rid} {reqs[rid]['text']}: {', '.join(t for t, r in lacking.items() if r == rid)}")
    cited = {fid for fids in evidence.values() for fid in fids} | {
        c.get("id") for e in profile_md.get("evidence") or [] for c in e.get("facts") or []}
    print("\nFacts you may use (* cited by the Evaluation or the Role profile):")
    for kind in FACT_KINDS:
        usable = [f for f in facts if f.get("kind") == kind and not fact_problem(by_id, f.get("id"))]
        for fact in usable:
            mark = "*" if fact["id"] in cited else " "
            details = " ".join(str(fact[k]) for k in ("period", "org") if fact.get(k))
            print(f"  {mark} {fact['id']} [{kind}, {fact.get('evidence')}] {details}  {fact.get('statement')}")
    unusable = [f"{f['id']} ({f.get('state') if f.get('state') != 'active' else 'inferred, unconfirmed'})"
                for f in facts if fact_problem(by_id, f.get("id"))]
    if unusable:
        print("  Never use: " + ", ".join(unusable))
    print("\nGlossary:")
    for kind in GLOSSARY_KINDS:
        names = sorted({pair for pair in glossary_pairs(glossary, (kind,)).values()})
        if names:
            print(f"  {kind}: " + "; ".join(f"{zh} = {en}" for zh, en in names))
    location = profile.get("location")
    pair = glossary_pairs(glossary).get(str(location)) if location else None
    english = pair[1] if pair else (location if location and not HAN.search(str(location)) else None)
    contact = profile.get("contact") if isinstance(profile.get("contact"), dict) else {}
    reach = [str(v) for v in [contact.get("email"), contact.get("phone"), *(contact.get("links") or [])] if v]
    print(f"\nHeader: {profile.get('name')} / {profile.get('name_en') or 'add name_en to profile.yml'}; "
          f"location {location or '-'} / {english or ('add it to glossary.yml as a term' if location else '-')}; "
          f"contact {' · '.join(reach) or 'none; add contact (email, phone, links) to profile.yml'}")


def cmd_resume_save(args):
    root = data_dir()
    folder = find_candidate(root, args.id, archived=False)
    job, evaluation, slug, profile_md = resume_context(root, folder, args.job)
    base = folder / "applications" / args.job
    if any((base / f"resume.{lang}.md").exists() for lang in RESUME_LANGS) and not args.replace:
        raise HHError(f"resumes for {args.job} already exist; pass --replace to write them again")
    data = read_payload(args)
    if not isinstance(data, dict):
        raise HHError("the resume must be a mapping")
    taxonomy = load_taxonomy(root)
    candidate = load_candidate(folder)
    profile, facts, glossary = candidate["profile"], candidate["facts"], candidate["glossary"]
    by_id = {f.get("id"): f for f in facts if isinstance(f, dict)}
    errors = [f"unknown field {key!r}; fields are {', '.join(RESUME_FIELDS)}" for key in data if key not in RESUME_FIELDS]
    texts, lines = [], {lang: [] for lang in RESUME_LANGS}

    def cited(item, where) -> list:
        ids = item.get("facts") if isinstance(item, dict) else None
        if not isinstance(ids, list) or not ids:
            errors.append(f"{where}: list the Facts it comes from")
            return []
        good = []
        for fid in ids:
            problem = fact_problem(by_id, fid)
            if problem:
                errors.append(f"{where}: {problem}")
            else:
                good.append(fid)
        return good

    def bilingual(item, where, ids) -> dict:
        text = {lang: str(item.get(lang) or "").strip() for lang in RESUME_LANGS}
        if not all(text.values()):
            errors.append(f"{where}: needs zh and en")
        pool = " ".join(str(by_id[f].get(k) or "") for f in ids for k in ("statement", "period"))
        allowed = set(NUMBER.findall(re.sub(r"(?<=\d),(?=\d{3})", "", pool)))
        used = {n for value in text.values() for n in NUMBER.findall(re.sub(r"(?<=\d),(?=\d{3})", "", value))}
        for number in sorted(used - allowed):
            errors.append(f"{where}: the number {number} is not in {', '.join(ids) or 'its Facts'}")
        texts.append((where, text))
        return text

    def add(lang_lines: dict, ids) -> None:
        note = f" <!-- {', '.join(ids)} -->"
        for lang in RESUME_LANGS:
            lines[lang].append(lang_lines[lang] + note)

    pairs = glossary_pairs(glossary)
    name_en = str(profile.get("name_en") or "").strip()
    if not name_en:
        errors.append("profile.yml needs name_en for the English resume")
    lines["zh"].append(f"# {profile.get('name')}")
    lines["en"].append(f"# {name_en}")
    header = {"zh": [], "en": []}
    location = profile.get("location")
    if location:
        pair = pairs.get(str(location))
        english = pair[1] if pair else (str(location) if not HAN.search(str(location)) else None)
        if not english:
            errors.append(f"add the location {location!r} to glossary.yml as a term so the English resume can name it")
        header["zh"].append(str(location))
        header["en"].append(english or "")
    contact = profile.get("contact") if isinstance(profile.get("contact"), dict) else {}
    for value in [contact.get("email"), contact.get("phone"), *(contact.get("links") or [])]:
        if value:
            header["zh"].append(str(value))
            header["en"].append(str(value))
    if header["zh"]:
        for lang in RESUME_LANGS:
            lines[lang] += ["", " · ".join(header[lang]) + " <!-- profile -->"]

    for key in ("headline", "summary"):
        item = data.get(key)
        if not isinstance(item, dict):
            errors.append(f"{key} is required, with zh, en and facts")
            continue
        ids = cited(item, key)
        text = bilingual(item, key, ids)
        if key == "summary" and ids and not set(ids) & set((profile_md.get("positioning") or {}).get("facts") or []):
            errors.append("summary: start from the Role profile's positioning; cite at least one of its Facts ("
                          + ", ".join((profile_md.get("positioning") or {}).get("facts") or []) + ")")
        for lang in RESUME_LANGS:
            lines[lang].append("")
        add({lang: f"**{text[lang]}**" if key == "headline" else text[lang] for lang in RESUME_LANGS}, ids)

    def section(key) -> None:
        for lang in RESUME_LANGS:
            lines[lang] += ["", f"## {RESUME_HEADINGS[lang][key]}", ""]

    companies, titles, schools = (glossary_pairs(glossary, (k,)) for k in ("company", "title", "school"))
    if data.get("experience"):
        section("experience")
    for n, item in enumerate(data.get("experience") or [], 1):
        where = f"experience {n}"
        ids = cited(item, where)
        org = str(item.get("org") or "")
        company = companies.get(org)
        if not company:
            errors.append(f"{where}: add the company {org!r} to glossary.yml")
            continue
        if not any(by_id[f].get("kind") == "experience" and by_id[f].get("org")
                   and any(str(by_id[f]["org"]) in name or name in str(by_id[f]["org"]) for name in company) for f in ids):
            errors.append(f"{where}: cite the experience Fact at {org}")
        parts = {"zh": [company[0]], "en": [company[1]]}
        if item.get("title"):
            title = titles.get(str(item["title"]))
            if not title:
                errors.append(f"{where}: add the title {item['title']!r} to glossary.yml")
            elif not any(t in str(by_id[f].get("statement")) for f in ids for t in title):
                errors.append(f"{where}: the title {item['title']!r} is not in its Facts; leave it out or ask the user")
            else:
                parts["zh"].append(title[0])
                parts["en"].append(title[1])
        if item.get("period") is not None:
            if str(item["period"]) not in {str(by_id[f].get("period")) for f in ids}:
                errors.append(f"{where}: period must be the period of one of its Facts")
            for lang in RESUME_LANGS:
                parts[lang].append(render_period(item["period"], lang))
        add({lang: f"### {' · '.join(parts[lang])}" for lang in RESUME_LANGS}, ids)
        for lang in RESUME_LANGS:
            lines[lang].append("")
        for m, bullet in enumerate(item.get("bullets") or [], 1):
            bullet_ids = cited(bullet, f"{where} bullet {m}")
            text = bilingual(bullet, f"{where} bullet {m}", bullet_ids)
            add({lang: f"- {text[lang]}" for lang in RESUME_LANGS}, bullet_ids)
        for lang in RESUME_LANGS:
            lines[lang].append("")

    for key, kind in (("projects", None), ("education", "education"), ("certificates", "certificate")):
        if data.get(key):
            section(key)
        for n, item in enumerate(data.get(key) or [], 1):
            where = f"{key} {n}"
            ids = cited(item, where)
            if kind and not any(by_id[f].get("kind") == kind for f in ids):
                errors.append(f"{where}: cite the {kind} Fact")
            text = bilingual(item, where, ids)
            if key == "education":
                school = schools.get(str(item.get("school") or ""))
                if not school:
                    errors.append(f"{where}: add the school {item.get('school')!r} to glossary.yml")
                    continue
                if not any(s in str(by_id[f].get("statement")) for f in ids for s in school):
                    errors.append(f"{where}: the school is not in its Facts")
                period = item.get("period")
                if period is not None and str(period) not in {str(by_id[f].get("period")) for f in ids}:
                    errors.append(f"{where}: period must be the period of one of its Facts")
                text = {lang: " · ".join([school[RESUME_LANGS.index(lang)], text[lang]]
                                         + ([render_period(period, lang)] if period is not None else []))
                        for lang in RESUME_LANGS}
            add({lang: f"- {text[lang]}" for lang in RESUME_LANGS}, ids)

    skills, skill_facts = [], []
    for term in data.get("skills") or []:
        try:
            tag = resolve_tag(taxonomy, str(term))
        except HHError as exc:
            errors.append(f"skills: {exc}")
            continue
        holders = [f["id"] for f in facts if isinstance(f, dict) and tag in (f.get("tags") or [])
                   and not fact_problem(by_id, f.get("id"))]
        if not holders:
            errors.append(f"skills: no active, sourced Fact has {tag}")
            continue
        entry = next(t for t in taxonomy.get("tags") or [] if isinstance(t, dict) and t.get("id") == tag)
        skills.append(entry)
        skill_facts += [fid for fid in holders if fid not in skill_facts]
    if skills:
        section("skills")
        add({"zh": "- " + "、".join(str(t.get("zh")) for t in skills),
             "en": "- " + ", ".join(str(t.get("en")) for t in skills)}, sorted(skill_facts, key=lambda f: id_number(f, "f") or 0))

    for term, rid in lacking_terms(job, evaluation, facts, taxonomy).items():
        for where, text in texts:
            if any(term_used(term, value) for value in text.values()):
                errors.append(f"{where}: {term!r} belongs to {rid}, which the Candidate lacks; leave it out")
    for zh, en in sorted(set(pairs.values())):
        for where, text in texts:
            if zh in text["zh"] and en.lower() not in text["en"].lower():
                errors.append(f"{where}: glossary.yml names {zh} as {en!r} in English")
            elif term_used(en, text["en"]) and zh not in text["zh"] or term_used(en, text["zh"]):
                errors.append(f"{where}: glossary.yml names {en} as {zh!r} in Chinese")
    for where, text in texts:
        if HAN.search(text["en"]):
            errors.append(f"{where}: the English text has Chinese in it: {text['en'][:60]}")
    if errors:
        raise HHError("nothing written:\n  " + "\n  ".join(dict.fromkeys(errors)))

    base.mkdir(parents=True, exist_ok=True)
    for lang in RESUME_LANGS:
        front = {"candidate": candidate_id(args.id), "job": args.job, "role": slug, "lang": lang, "written": today(),
                 "role_profile": profile_md.get("built")}
        body = re.sub(r"\n{3,}", "\n\n", "\n".join(lines[lang])).strip()
        (base / f"resume.{lang}.md").write_text(f"---\n{hhyaml.dumps(front)}---\n\n{body}\n", encoding="utf-8")
        print(base / f"resume.{lang}.md")
    for line in write_pdfs(base, str(profile.get("name"))):
        print(line)


def cmd_resume_pdf(args):
    root = data_dir()
    folder = find_candidate(root, args.id, archived=False)
    base = folder / "applications" / args.job
    facts = read_list(folder / "facts.yml")
    by_id = {f.get("id"): f for f in facts if isinstance(f, dict)}
    errors = []
    for lang in RESUME_LANGS:
        path = base / f"resume.{lang}.md"
        if not path.exists():
            errors.append(f"{path} is missing; write it with resume save")
            continue
        errors += check_resume(path, lang, by_id)
        job_path, ev_path = root / "jobs" / f"{args.job}.md", base / "evaluation.md"
        if job_path.exists() and ev_path.exists():
            body = re.sub(r"<!--.*?-->", "", read_job(path)[1])
            for term, rid in lacking_terms(read_job(job_path)[0], read_job(ev_path)[0], facts, load_taxonomy(root)).items():
                if term_used(term, body):
                    errors.append(f"resume {args.job} {lang}: {term!r} belongs to {rid}, which the Candidate lacks; leave it out")
    if errors:
        raise HHError("no PDF written:\n  " + "\n  ".join(errors))
    profile = read_yaml(folder / "profile.yml", {})
    for line in write_pdfs(base, str(profile.get("name") if isinstance(profile, dict) else "")):
        print(line)


def cmd_application_new(args):
    root = data_dir()
    folder = find_candidate(root, args.id, archived=False)
    if not (root / "jobs" / f"{args.job}.md").exists():
        raise HHError(f"Job {args.job} has no snapshot in jobs/; save it with job save first")
    base = folder / "applications" / args.job
    if (base / "status.yml").exists():
        raise HHError(f"{folder.name} already has an Application for {args.job}")
    if (base / "evaluation.md").exists():
        raise HHError(f"{args.job} is already evaluated; run application sync")
    if args.role:
        role = load_role(find_role(folder, args.role))
        if role.get("state") == "dropped":
            raise HHError(f"the Role {args.role} is dropped")
    if not args.next.strip():
        raise HHError("--next must say what happens next")
    parse_date(args.due, "--due")
    base.mkdir(parents=True, exist_ok=True)
    write_status(base / "status.yml", {
        "job": args.job, "role": args.role, "stage": "found", "next_step": args.next, "due": args.due,
        "timeline": [{"stage": "found", "date": today()}],
    })
    print(f"{args.job}  found; next: {args.next} by {args.due}")


def cmd_application_move(args):
    root = data_dir()
    folder = find_candidate(root, args.id, archived=False)
    path, status = load_status(folder, args.job)
    current, target = status.get("stage"), args.stage
    if current == "closed":
        raise HHError(f"{args.job} is closed ({status.get('outcome')}); a closed Application does not move")
    if STAGES.index(target) < STAGES.index(current) or (target == current and target != "interview"):
        raise HHError(f"{args.job} is at {stage_label(current, status.get('round'))}; Stages only move forward")
    timeline = list(status.get("timeline") or [])
    day = parse_date(args.date or today(), "--date")
    if day > dt.date.today():
        raise HHError("--date cannot be in the future; put what is planned in --next and --due")
    if timeline and day < parse_date(timeline[-1].get("date"), "the last timeline date"):
        raise HHError(f"--date cannot be before the last Stage change on {timeline[-1].get('date')}")
    entry = {"stage": target, "date": day.isoformat()}
    if target == "interview":
        last = max((e.get("round") or 0 for e in timeline if e.get("stage") == "interview"), default=0)
        number = args.round if args.round is not None else last + 1
        if number <= last:
            raise HHError(f"--round must be higher than the last round, {last}")
        entry["round"] = status["round"] = number
    else:
        if args.round is not None:
            raise HHError("--round is only for interviews")
        status.pop("round", None)
    if target == "closed":
        if not args.outcome:
            raise HHError(f"closing needs --outcome: {', '.join(OUTCOMES)}")
        if args.next or args.due:
            raise HHError("a closed Application has no next step or due date")
        entry["outcome"] = status["outcome"] = args.outcome
        status.pop("next_step", None)
        status.pop("due", None)
    else:
        if args.outcome:
            raise HHError("--outcome is only for closing")
        if not (args.next or "").strip() or not args.due:
            raise HHError("an open Application needs --next and --due")
        if parse_date(args.due, "--due") < day:
            raise HHError("--due cannot be before the day of this Stage change")
        status.update(next_step=args.next, due=args.due)
    if args.note:
        entry["note"] = args.note
    status["stage"] = target
    status["timeline"] = timeline + [entry]
    write_status(path, status)
    label = stage_label(target, status.get("round"))
    print(f"{args.job}  {label} on {entry['date']}"
          + (f" ({args.outcome})" if target == "closed" else f"; next: {args.next} by {args.due}"))


def cmd_application_update(args):
    root = data_dir()
    folder = find_candidate(root, args.id, archived=False)
    path, status = load_status(folder, args.job)
    if status.get("stage") == "closed":
        raise HHError(f"{args.job} is closed ({status.get('outcome')}); it has no next step")
    if args.next is None and args.due is None:
        raise HHError("give --next, --due or both")
    if args.next is not None:
        if not args.next.strip():
            raise HHError("--next must say what happens next")
        status["next_step"] = args.next
    if args.due is not None:
        parse_date(args.due, "--due")
        status["due"] = args.due
    write_status(path, status)
    print(f"{args.job}  next: {status.get('next_step')} by {status.get('due')}")


def cmd_application_show(args):
    root = data_dir()
    folder = find_candidate(root, args.id, archived=False)
    _, status = load_status(folder, args.job)
    job_path = root / "jobs" / f"{args.job}.md"
    job = read_job(job_path)[0] if job_path.exists() else {}
    print(f"{args.job}  {job.get('title', '?')} · {job.get('company', '?')}")
    print(f"Role: {status.get('role') or 'none'}")
    print(f"Stage: {stage_label(status.get('stage'), status.get('round'))}"
          + (f" ({status.get('outcome')})" if status.get("outcome") else ""))
    if status.get("stage") != "closed":
        late = "  OVERDUE" if str(status.get("due")) < today() else ""
        print(f"Next step: {status.get('next_step')} by {status.get('due')}{late}")
    print("Timeline:")
    for entry in status.get("timeline") or []:
        extra = "".join(f" ({entry[k]})" for k in ("outcome", "note") if entry.get(k))
        print(f"  {entry.get('date')}  {stage_label(entry.get('stage'), entry.get('round'))}{extra}")
    base = folder / "applications" / args.job
    files = sorted(p.name for p in base.iterdir() if p.name != "status.yml" and not p.name.startswith("."))
    print("Files: " + (", ".join(files) or "none"))


def print_application(row, extra: str = "") -> None:
    cid, name, jid, role, company, title, stage, number, outcome, next_step, due = row
    state = f"closed ({outcome})" if stage == "closed" else f"{stage_label(stage, number)}; next: {next_step} by {due}"
    print(f"{cid} {name}  {jid}  {state}{extra}  {role or 'no Role'}  {title or '?'} · {company or '?'}")


APPLICATION_COLUMNS = ("SELECT a.candidate_id, c.name, a.job_id, a.role, a.company, a.title, a.stage, a.round, a.outcome, "
                       "a.next_step, a.due FROM applications a JOIN candidates c ON c.id = a.candidate_id")


def cmd_application_list(args):
    root = data_dir()
    con = open_index(root)
    sql, params = APPLICATION_COLUMNS + " WHERE 1 = 1", []
    if args.id:
        sql += " AND a.candidate_id = ?"
        params.append(candidate_id(args.id))
    if args.job:
        sql += " AND a.job_id = ?"
        params.append(args.job)
    if args.role:
        sql += " AND a.role LIKE ?"
        params.append(f"%{args.role}%")
    if args.company:
        sql += " AND a.company LIKE ?"
        params.append(f"%{args.company}%")
    if args.stage:
        sql += " AND a.stage = ?"
        params.append(args.stage)
    if args.open:
        sql += " AND a.stage != 'closed'"
    rows = con.execute(sql + " ORDER BY a.candidate_id, a.due IS NULL, a.due, a.job_id", params).fetchall()
    for row in rows:
        print_application(row)
    print(f"{len(rows)} {'Application' if len(rows) == 1 else 'Applications'}" if rows else "No Applications.")


def cmd_application_overdue(args):
    root = data_dir()
    con = open_index(root)
    rows = con.execute(APPLICATION_COLUMNS + " WHERE a.stage != 'closed' AND a.due < ? ORDER BY a.due, a.candidate_id",
                       (today(),)).fetchall()
    for row in rows:
        days = (dt.date.today() - dt.date.fromisoformat(row[10])).days
        print_application(row, f"  ({days} {'day' if days == 1 else 'days'} overdue)")
    print(f"{len(rows)} overdue" if rows else "Nothing is overdue.")


def cmd_application_progress(args):
    root = data_dir()
    con = open_index(root)
    groups = {
        "candidate": "a.candidate_id || ' ' || c.name",
        "role": "a.candidate_id || ' ' || coalesce(a.role, '(no Role)')",
        "job": "a.job_id || ' ' || coalesce(a.title, '?') || ' · ' || coalesce(a.company, '?')",
        "company": "coalesce(a.company, '?')",
    }
    rows = con.execute(f"SELECT {groups[args.by]}, a.stage, a.outcome, a.due FROM applications a "
                       "JOIN candidates c ON c.id = a.candidate_id").fetchall()
    if not rows:
        print("No Applications.")
        return
    table, now = {}, today()
    for group, stage, outcome, due in rows + [("Total", s, o, d) for _, s, o, d in rows]:
        entry = table.setdefault(group, {"stages": Counter(), "outcomes": Counter(), "overdue": 0})
        entry["stages"][stage] += 1
        if outcome:
            entry["outcomes"][outcome] += 1
        if stage != "closed" and due and str(due) < now:
            entry["overdue"] += 1
    print(f"| {args.by.capitalize()} | " + " | ".join(STAGES) + " | overdue | outcomes |")
    print("|---|" + "---|" * (len(STAGES) + 2))
    for group in sorted(g for g in table if g != "Total") + ["Total"]:
        entry = table[group]
        outcomes = ", ".join(f"{k} {v}" for k, v in sorted(entry["outcomes"].items())) or "-"
        print(f"| {group} | " + " | ".join(str(entry["stages"][s]) for s in STAGES) + f" | {entry['overdue']} | {outcomes} |")


def cmd_application_sync(args):
    root = data_dir()
    created = 0
    for archived in (False, True):
        for cid, folder in candidate_dirs(root, archived):
            for jid, path in application_dirs(folder):
                if (path / "status.yml").exists() or not (path / "evaluation.md").exists():
                    continue
                evaluation = read_job(path / "evaluation.md")[0]
                due = (dt.date.today() + dt.timedelta(days=DECIDE_DAYS)).isoformat()
                write_status(path / "status.yml", {
                    "job": jid, "role": evaluation.get("role"), "stage": "evaluated", "next_step": DECIDE_STEP, "due": due,
                    "timeline": [{"stage": "evaluated", "date": str(evaluation.get("evaluated"))}],
                })
                created += 1
                print(f"{cid}  {jid}  evaluated; next: {DECIDE_STEP} by {due}")
    print(f"Created {created} status.yml {'file' if created == 1 else 'files'}." if created
          else "Every evaluated Application has a status.yml.")


def matched_facts(con, cid: str, tag: str) -> list:
    rows = con.execute(
        "SELECT f.id FROM facts f JOIN fact_tags t ON t.candidate_id = f.candidate_id AND t.fact_id = f.id "
        "WHERE f.candidate_id = ? AND t.tag = ? AND f.state = 'active' AND f.origin = 'sourced' ORDER BY f.id",
        (cid, tag)).fetchall()
    return [r[0] for r in rows]


def cmd_search_candidates(args):
    root = data_dir()
    taxonomy = load_taxonomy(root)
    tags = [resolve_tag(taxonomy, t) for t in args.tag]
    tags += [resolve_tag(taxonomy, t, "industry") for t in args.industry]
    con = open_index(root)
    sql = "SELECT id, name, status, seniority, years_experience FROM candidates WHERE 1 = 1"
    params: list = []
    if args.status:
        sql += " AND status = ?"
        params.append(args.status)
    if args.seniority:
        sql += " AND seniority = ?"
        params.append(args.seniority)
    if args.min_years is not None:
        sql += " AND years_experience >= ?"
        params.append(args.min_years)
    for tag in tags:
        sql += " AND id IN (SELECT candidate_id FROM candidate_tags WHERE tag = ?)"
        params.append(tag)
    if args.text:
        sql += " AND id IN (SELECT candidate_id FROM facts WHERE state = 'active' AND statement LIKE ?)"
        params.append(f"%{args.text}%")
    role_sql, role_params = role_filter(taxonomy, args)
    if role_sql:
        sql += f" AND id IN (SELECT r.candidate_id FROM roles r WHERE {role_sql})"
        params += role_params
    rows = con.execute(sql + " ORDER BY id", params).fetchall()
    for cid, name, status, seniority, years in rows:
        print(f"{cid}  {name}  ({status}, {seniority or '-'}, {years} years)")
        for tag in tags:
            print(f"    {tag}: {', '.join(matched_facts(con, cid, tag))}")
        if role_sql:
            for slug, built, stale in con.execute(
                    f"SELECT r.slug, r.built, r.stale FROM roles r WHERE r.candidate_id = ? AND {role_sql} ORDER BY r.priority",
                    [cid, *role_params]).fetchall():
                gaps = con.execute(
                    "SELECT COUNT(*) FROM role_gaps g JOIN role_requirements q ON q.candidate_id = g.candidate_id "
                    "AND q.role = g.role AND q.id = g.requirement WHERE g.candidate_id = ? AND g.role = ? "
                    "AND q.kind = 'must' AND g.kind != 'weak-evidence'", (cid, slug)).fetchone()[0]
                profile = f"built {built}" + (", stale" if stale else "") if built else "profile not built"
                print(f"    role {slug}: {gaps} must-have gaps ({profile})")
    if not rows:
        print("No matching Candidates.")


def role_filter(taxonomy: dict, args) -> tuple:
    """SQL on the roles table (alias r) for the Role options of search candidates."""
    if not (args.role or args.requirement_tag or args.no_must_gaps):
        return "", []
    sql, params = ["r.state = 'active'"], []
    if args.role:
        term = f"%{args.role.strip().lower()}%"
        sql.append("(lower(r.title) LIKE ? OR lower(coalesce(r.title_other, '')) LIKE ? OR r.slug LIKE ?)")
        params += [term, term, term]
    for tag in args.requirement_tag:
        sql.append("EXISTS (SELECT 1 FROM role_requirement_tags t WHERE t.candidate_id = r.candidate_id "
                   "AND t.role = r.slug AND t.tag = ?)")
        params.append(resolve_tag(taxonomy, tag))
    if args.no_must_gaps:
        sql.append("r.built IS NOT NULL AND NOT EXISTS (SELECT 1 FROM role_gaps g JOIN role_requirements q "
                   "ON q.candidate_id = g.candidate_id AND q.role = g.role AND q.id = g.requirement "
                   "WHERE g.candidate_id = r.candidate_id AND g.role = r.slug AND q.kind = 'must' "
                   "AND g.kind != 'weak-evidence')")
    return " AND ".join(sql), params


def cmd_search_facts(args):
    root = data_dir()
    taxonomy = load_taxonomy(root)
    tags = [resolve_tag(taxonomy, t) for t in args.tag]
    con = open_index(root)
    sql = ("SELECT f.candidate_id, c.name, f.id, f.kind, f.evidence, f.origin, f.state, f.period, f.statement "
           "FROM facts f JOIN candidates c ON c.id = f.candidate_id WHERE 1 = 1")
    params: list = []
    if args.candidate:
        sql += " AND f.candidate_id = ?"
        params.append(candidate_id(args.candidate))
    for column in ("kind", "evidence", "origin"):
        value = getattr(args, column)
        if value:
            sql += f" AND f.{column} = ?"
            params.append(value)
    if args.state:
        sql += " AND f.state = ?"
        params.append(args.state)
    else:
        sql += " AND f.state != 'superseded'"
    for tag in tags:
        sql += (" AND EXISTS (SELECT 1 FROM fact_tags t WHERE t.candidate_id = f.candidate_id "
                "AND t.fact_id = f.id AND t.tag = ?)")
        params.append(tag)
    if args.since:
        sql += " AND f.start_month IS NOT NULL AND COALESCE(f.end_month, 999999) >= ?"
        params.append(month_index((args.since, 1)))
    if args.text:
        sql += " AND f.statement LIKE ?"
        params.append(f"%{args.text}%")
    rows = con.execute(sql + " ORDER BY f.candidate_id, f.id", params).fetchall()
    for cid, name, fid, kind, evidence, origin, state, period, statement in rows:
        label = evidence if origin == "sourced" else "inferred, unconfirmed"
        extra = f", {state}" if state != "active" else ""
        print(f"{cid} {name}  {fid}  [{kind}, {label}{extra}]  {period or '-'}  {statement}")
    if not rows:
        print("No matching Facts.")


def cmd_query(args):
    root = data_dir()
    con = open_index(root)
    try:
        cursor = con.execute(args.sql)
    except sqlite3.Error as exc:
        raise HHError(f"query failed: {exc}") from None
    print("\t".join(d[0] for d in cursor.description or []))
    for row in cursor.fetchall():
        print("\t".join("" if v is None else str(v) for v in row))


# ---------------------------------------------------------------- parser


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="hh.py", description="headhunter Data folder helper")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("init", help="create the Data folder if missing").set_defaults(func=cmd_init)

    cand = sub.add_parser("candidate", help="create, list, show, archive or restore Candidates")
    csub = cand.add_subparsers(dest="action", required=True)
    p = csub.add_parser("new")
    p.add_argument("--name", required=True)
    p.add_argument("--name-en")
    p.set_defaults(func=cmd_candidate_new)
    p = csub.add_parser("list")
    p.add_argument("--archived", action="store_true")
    p.set_defaults(func=cmd_candidate_list)
    p = csub.add_parser("show")
    p.add_argument("id")
    p.set_defaults(func=cmd_candidate_show)
    p = csub.add_parser("archive")
    p.add_argument("id")
    p.set_defaults(func=lambda a: move_candidate(a, True))
    p = csub.add_parser("restore")
    p.add_argument("id")
    p.set_defaults(func=lambda a: move_candidate(a, False))

    src = sub.add_parser("source", help="keep a raw input as a Source")
    ssub = src.add_subparsers(dest="action", required=True)
    p = ssub.add_parser("add", help="copy a file (or stdin with -) into sources/")
    p.add_argument("id")
    p.add_argument("path")
    p.add_argument("--type", required=True, choices=SOURCE_TYPES)
    p.add_argument("--origin")
    p.add_argument("--evidence", choices=EVIDENCE)
    p.add_argument("--state", default="read", choices=SOURCE_STATES)
    p.set_defaults(func=cmd_source_add)
    p = ssub.add_parser("github", help="snapshot a GitHub repository (owner/repo) or profile (user) with gh")
    p.add_argument("id")
    p.add_argument("target")
    p.add_argument("--author", help="count only this login's commits")
    p.set_defaults(func=cmd_source_github)
    p = ssub.add_parser("state", help="record how readable a Source was")
    p.add_argument("id")
    p.add_argument("source")
    p.add_argument("state", choices=SOURCE_STATES)
    p.set_defaults(func=cmd_source_state)

    fact = sub.add_parser("fact", help="add or update Facts from JSON or YAML on stdin")
    fsub = fact.add_subparsers(dest="action", required=True)
    p = fsub.add_parser("add")
    p.add_argument("id")
    p.add_argument("--file")
    p.set_defaults(func=cmd_fact_add)
    p = fsub.add_parser("update", help="merge fields into a Fact; a null value removes the field")
    p.add_argument("id")
    p.add_argument("fact")
    p.add_argument("--file")
    p.set_defaults(func=cmd_fact_update)

    p = sub.add_parser("next-id", help="print the next free Fact or follow-up question ids")
    p.add_argument("id")
    p.add_argument("kind", choices=("fact", "question"))
    p.add_argument("--count", type=int, default=1)
    p.set_defaults(func=cmd_next_id)

    p = sub.add_parser("import-report", help="create the Import report for a Source")
    p.add_argument("id")
    p.add_argument("source")
    p.set_defaults(func=cmd_import_report)

    p = sub.add_parser("questions", help="list open follow-up questions")
    p.add_argument("id", nargs="?")
    p.set_defaults(func=cmd_questions)

    p = sub.add_parser("extract-text", help="print the text of a Word, text or PDF file")
    p.add_argument("path")
    p.set_defaults(func=cmd_extract_text)

    tax = sub.add_parser("taxonomy", help="look up Tags")
    tsub = tax.add_subparsers(dest="action", required=True)
    p = tsub.add_parser("find")
    p.add_argument("term")
    p.set_defaults(func=cmd_taxonomy_find)

    role = sub.add_parser("role", help="define Roles and build Role profiles")
    rsub = role.add_subparsers(dest="action", required=True)
    p = rsub.add_parser("new", help="create a Role from JSON or YAML on stdin")
    p.add_argument("id")
    p.add_argument("--file")
    p.set_defaults(func=cmd_role_new)
    p = rsub.add_parser("update", help="merge fields into role.yml; a null value removes the field")
    p.add_argument("id")
    p.add_argument("role")
    p.add_argument("--file")
    p.set_defaults(func=cmd_role_update)
    p = rsub.add_parser("list", help="list Roles and whether their profiles are current")
    p.add_argument("id", nargs="?")
    p.set_defaults(func=cmd_role_list)
    p = rsub.add_parser("match", help="list the Facts that share a Tag with each requirement")
    p.add_argument("id")
    p.add_argument("role")
    p.set_defaults(func=cmd_role_match)
    p = rsub.add_parser("build", help="write the Role profile from JSON or YAML on stdin")
    p.add_argument("id")
    p.add_argument("role")
    p.add_argument("--file")
    p.set_defaults(func=cmd_role_build)
    p = rsub.add_parser("stale", help="list Role profiles that are out of date, with reasons")
    p.add_argument("id", nargs="?")
    p.set_defaults(func=cmd_role_stale)
    p = rsub.add_parser("refine", help="propose requirements that recur across the Jobs evaluated under a Role")
    p.add_argument("id")
    p.add_argument("role")
    p.add_argument("--accept", nargs="+", default=[], metavar="TAG_OR_REQUIREMENT",
                   help="apply these proposals, once the user accepts them")
    p.set_defaults(func=cmd_role_refine)

    ev = sub.add_parser("evaluation", help="evaluate Jobs against Candidates and their Roles")
    esub = ev.add_subparsers(dest="action", required=True)
    p = esub.add_parser("match", help="find Candidates and Roles for a Job, or list one Candidate's Facts per requirement")
    p.add_argument("job")
    p.add_argument("id", nargs="?")
    p.add_argument("--all", action="store_true", help="also list Candidates with no Role sharing a Tag")
    p.set_defaults(func=cmd_evaluation_match)
    p = esub.add_parser("save", help="write an Evaluation from JSON or YAML on stdin")
    p.add_argument("id")
    p.add_argument("job")
    p.add_argument("--file")
    p.add_argument("--replace", action="store_true", help="evaluate again over an existing Evaluation")
    p.set_defaults(func=cmd_evaluation_save)
    p = esub.add_parser("list", help="list Evaluations with their Success ratings")
    p.add_argument("id", nargs="?")
    p.add_argument("--job")
    p.add_argument("--rating", choices=RATINGS)
    p.set_defaults(func=cmd_evaluation_list)

    app = sub.add_parser("application", help="track Applications: Stages, next steps, overdue follow-ups and progress")
    asub = app.add_subparsers(dest="action", required=True)
    p = asub.add_parser("new", help="start an Application at found, before it is evaluated")
    p.add_argument("id")
    p.add_argument("job")
    p.add_argument("--role")
    p.add_argument("--next", required=True, help="the next step")
    p.add_argument("--due", required=True, help="its due date, such as 2026-01-31")
    p.set_defaults(func=cmd_application_new)
    p = asub.add_parser("move", help="move an Application to a later Stage and record the date")
    p.add_argument("id")
    p.add_argument("job")
    p.add_argument("stage", choices=STAGES[2:])
    p.add_argument("--next", help="the next step; required unless closing")
    p.add_argument("--due", help="its due date; required unless closing")
    p.add_argument("--date", help="the day the Stage changed; today when left out")
    p.add_argument("--round", type=int, help="interview round; the next round when left out")
    p.add_argument("--outcome", choices=OUTCOMES, help="required when closing")
    p.add_argument("--note")
    p.set_defaults(func=cmd_application_move)
    p = asub.add_parser("update", help="change an open Application's next step or due date")
    p.add_argument("id")
    p.add_argument("job")
    p.add_argument("--next")
    p.add_argument("--due")
    p.set_defaults(func=cmd_application_update)
    p = asub.add_parser("show", help="show one Application's Stage, next step, timeline and files")
    p.add_argument("id")
    p.add_argument("job")
    p.set_defaults(func=cmd_application_show)
    p = asub.add_parser("list", help="list Applications")
    p.add_argument("id", nargs="?")
    p.add_argument("--role", help="Role folder name, or part of it")
    p.add_argument("--job")
    p.add_argument("--company", help="company name, or part of it")
    p.add_argument("--stage", choices=STAGES)
    p.add_argument("--open", action="store_true", help="only Applications that are not closed")
    p.set_defaults(func=cmd_application_list)
    asub.add_parser("overdue", help="list open Applications past their due date, across all Candidates").set_defaults(
        func=cmd_application_overdue)
    p = asub.add_parser("progress", help="count Applications per Stage")
    p.add_argument("--by", choices=("candidate", "role", "job", "company"), default="candidate")
    p.set_defaults(func=cmd_application_progress)
    asub.add_parser("sync", help="create status.yml for evaluated Applications that have none").set_defaults(
        func=cmd_application_sync)

    res = sub.add_parser("resume", help="write the Chinese and English resumes of an evaluated Application")
    vsub = res.add_subparsers(dest="action", required=True)
    p = vsub.add_parser("plan", help="show what a resume starts from: the Role profile, the Evaluation and usable Facts")
    p.add_argument("id")
    p.add_argument("job")
    p.set_defaults(func=cmd_resume_plan)
    p = vsub.add_parser("save", help="write both resumes from JSON or YAML on stdin, then print them to PDF")
    p.add_argument("id")
    p.add_argument("job")
    p.add_argument("--file")
    p.add_argument("--replace", action="store_true", help="write the resumes again")
    p.set_defaults(func=cmd_resume_save)
    p = vsub.add_parser("pdf", help="print resume.zh.md and resume.en.md to PDF again, after editing them")
    p.add_argument("id")
    p.add_argument("job")
    p.set_defaults(func=cmd_resume_pdf)

    job = sub.add_parser("job", help="read Listings and Jobs, and save Job snapshots")
    jsub = job.add_subparsers(dest="action", required=True)
    p = jsub.add_parser("listing", help="list the Jobs on a Listing page")
    p.add_argument("url")
    p.add_argument("--page", type=int, default=1, help="result page, for sites read through their JSON")
    p.set_defaults(func=cmd_job_listing)
    p = jsub.add_parser("fetch", help="print a Job's structured data and text from its url or a file")
    p.add_argument("url", nargs="?")
    p.add_argument("--file", help="the Job's content as an HTML, Word, PDF or text file (pasted text saved to a file)")
    p.add_argument("--max-chars", type=int, default=20000)
    p.set_defaults(func=cmd_job_fetch)
    p = jsub.add_parser("save", help="save a Job snapshot from JSON or YAML on stdin")
    p.add_argument("--file")
    p.add_argument("--replace", action="store_true", help="save a new reading over an existing snapshot")
    p.set_defaults(func=cmd_job_save)
    jsub.add_parser("list", help="list saved Job snapshots").set_defaults(func=cmd_job_list)
    p = jsub.add_parser("accept", help="turn a proposed term into a Tag in every Job snapshot, once the Tag exists")
    p.add_argument("term")
    p.add_argument("tag")
    p.set_defaults(func=cmd_job_accept)

    p = sub.add_parser("validate", help="check taxonomy.yml, Candidate folders and Job snapshots")
    p.add_argument("id", nargs="?")
    p.set_defaults(func=cmd_validate)

    sub.add_parser("index", help="delete and rebuild index.sqlite").set_defaults(func=cmd_index)

    search = sub.add_parser("search", help="search the Index")
    qsub = search.add_subparsers(dest="action", required=True)
    p = qsub.add_parser("candidates")
    p.add_argument("--tag", action="append", default=[], help="Tag id, label or alias; repeat for AND")
    p.add_argument("--industry", action="append", default=[])
    p.add_argument("--seniority", choices=SENIORITY)
    p.add_argument("--status", choices=CANDIDATE_STATUS)
    p.add_argument("--min-years", type=float)
    p.add_argument("--role", help="an active Role whose title (either language) or folder name contains this")
    p.add_argument("--requirement-tag", action="append", default=[], help="an active Role requires this Tag")
    p.add_argument("--no-must-gaps", action="store_true",
                   help="an active Role with a built profile and no missing or to-confirm must-haves")
    p.add_argument("--text")
    p.set_defaults(func=cmd_search_candidates)
    p = qsub.add_parser("facts")
    p.add_argument("--candidate")
    p.add_argument("--tag", action="append", default=[])
    p.add_argument("--kind", choices=FACT_KINDS)
    p.add_argument("--evidence", choices=EVIDENCE)
    p.add_argument("--origin", choices=ORIGINS)
    p.add_argument("--state", choices=FACT_STATES)
    p.add_argument("--since", type=int, help="year; only Facts that ran into or after it")
    p.add_argument("--text")
    p.set_defaults(func=cmd_search_facts)

    p = sub.add_parser("query", help="run a read-only SQL query on the Index")
    p.add_argument("sql")
    p.set_defaults(func=cmd_query)
    return parser


def main(argv=None) -> int:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure:
            try:
                reconfigure(encoding="utf-8")
            except ValueError:
                pass
    args = build_parser().parse_args(argv)
    try:
        return args.func(args) or 0
    except HHError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
