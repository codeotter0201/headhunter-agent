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
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import unicodedata
import zipfile
from collections import Counter
from pathlib import Path
from typing import Any
from xml.etree import ElementTree

sys.dont_write_bytecode = True  # keep the plugin folder free of __pycache__
sys.path.insert(0, str(Path(__file__).resolve().parent))
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
        counts["candidates"] += 1
        counts["facts"] += len(facts)
    con.commit()
    con.close()
    os.replace(tmp, root / "index.sqlite")
    return counts


def index_stale(root: Path) -> bool:
    index = root / "index.sqlite"
    if not index.exists():
        return True
    built = index.stat().st_mtime
    paths = [root / "taxonomy.yml", root / "candidates"]
    for _, folder in candidate_dirs(root):
        paths += [folder, folder / "profile.yml", folder / "sources.yml", folder / "facts.yml", folder / "imports"]
        paths += list((folder / "imports").glob("*.md"))
    return any(p.exists() and p.stat().st_mtime > built for p in paths)


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
        lines = [line.strip() for line in strategy.read_text(encoding="utf-8").splitlines()
                 if line.strip() and not line.startswith("#")]
        print("Strategy: " + (" ".join(lines[:3]) if lines else "-"))


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


def cmd_extract_text(args):
    path = Path(args.path).expanduser()
    suffix = path.suffix.lower()
    if suffix == ".docx":
        print(docx_text(path))
    elif suffix in (".txt", ".md", ".csv", ".json", ".yml", ".yaml", ".html", ".htm"):
        print(path.read_text(encoding="utf-8", errors="replace"))
    elif suffix == ".pdf" and shutil.which("pdftotext"):
        subprocess.run(["pdftotext", "-layout", str(path), "-"], check=False)
    elif suffix == ".pdf":
        raise HHError("no PDF text extractor is installed; read the PDF with your own file reading, "
                      "or mark the Source partly-readable or unreadable")
    else:
        raise HHError(f"{suffix or 'this'} file is not text; read it with your own file reading "
                      "(images only if you can see images), or mark the Source unreadable")


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
    if errors:
        print("\n".join(errors))
        return 1
    print(f"OK: taxonomy.yml and {len(targets)} Candidate folder(s) are valid.")
    return 0


def cmd_index(args):
    root = data_dir()
    counts = rebuild_index(root)
    print(f"Rebuilt {root / 'index.sqlite'}: {counts['candidates']} Candidates, {counts['facts']} Facts.")


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
    rows = con.execute(sql + " ORDER BY id", params).fetchall()
    for cid, name, status, seniority, years in rows:
        print(f"{cid}  {name}  ({status}, {seniority or '-'}, {years} years)")
        for tag in tags:
            print(f"    {tag}: {', '.join(matched_facts(con, cid, tag))}")
    if not rows:
        print("No matching Candidates.")


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

    p = sub.add_parser("validate", help="check taxonomy.yml and Candidate folders")
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
