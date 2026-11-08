"""Read job sites for the headhunter skill: site rules, polite fetching, and
turning Listing and Job pages into plain data.

Fetching identifies itself with a User-Agent that names this project, honors
robots.txt, and stops at any refusal or bot check instead of working around
it. Sites that block automated reading are read in a browser or from text the
user copies; the agent follows SKILL.md for those.
"""

from __future__ import annotations

import hashlib
import html
import json
import re
import urllib.error
import urllib.parse
import urllib.request

USER_AGENT = "headhunter-agent (+https://github.com/codeotter0201/headhunter-agent)"
TIMEOUT = 20

# read: fetch = the script may fetch it; browser = read in a browser; manual =
# only a page open in the user's signed-in browser, or text the user pastes.
SITES = {
    "104": {
        "hosts": ("104.com.tw",),
        "job": r"/job/([0-9a-z]+)",
        "read": "browser",
        "why": "104 refuses automated requests, including its robots.txt",
    },
    "cakeresume": {
        "hosts": ("cake.me", "cakeresume.com"),
        "job": r"/companies/([^/?#]+)/jobs/([^/?#]+)",
        "read": "browser",
        "why": "CakeResume shows a bot check to automated requests",
    },
    "yourator": {
        "hosts": ("yourator.co",),
        "job": r"/companies/[^/?#]+/jobs/(\d+)",
        "read": "fetch",
        "why": "",
    },
    "linkedin": {
        "hosts": ("linkedin.com",),
        "job": r"/jobs/view/(?:[^/?#]*?-)?(\d+)",
        "read": "manual",
        "why": "LinkedIn is read only from a page open in the user's signed-in browser or from pasted text",
    },
}
BOT_CHECK = re.compile(r"Just a moment\.\.\.|cf-chl|captcha|Performing security verification", re.I)
TRACKING = re.compile(r"^(utm_|fbclid$|gclid$|jobsource$|ref$|trk)", re.I)


class WebError(Exception):
    pass


def host_of(url: str) -> str:
    host = (urllib.parse.urlsplit(url).hostname or "").lower()
    return host[4:] if host.startswith("www.") else host


def site_of(url: str):
    host = host_of(url)
    for name, site in SITES.items():
        if any(host == h or host.endswith("." + h) for h in site["hosts"]):
            return name
    return None


def clean_url(url: str) -> str:
    parts = urllib.parse.urlsplit(url.strip())
    if parts.scheme not in ("http", "https") or not parts.hostname:
        raise WebError(f"{url!r} is not a web address")
    query = [(k, v) for k, v in urllib.parse.parse_qsl(parts.query, keep_blank_values=True) if not TRACKING.match(k)]
    return urllib.parse.urlunsplit((parts.scheme, parts.netloc, parts.path, urllib.parse.urlencode(query), ""))


def job_id(url: str) -> tuple:
    """Return (job id, site, site id) for a Job URL."""
    url = clean_url(url)
    site = site_of(url)
    path = urllib.parse.urlsplit(url).path
    if site:
        match = re.search(SITES[site]["job"], path)
        if site == "linkedin" and not match:
            current = urllib.parse.parse_qs(urllib.parse.urlsplit(url).query).get("currentJobId")
            if current and current[0].isdigit():
                return f"j-linkedin-{current[0]}", site, current[0]
        if not match:
            raise WebError(f"{url} does not look like a single {site} Job page")
        site_id = "-".join(match.groups()).lower()
        return f"j-{site}-{site_id}", site, site_id
    host = host_of(url)
    digest = hashlib.sha1(url.encode("utf-8")).hexdigest()[:8]
    return f"j-{host.replace('.', '-')}-{digest}", host, digest


def read_method(url: str) -> str:
    site = site_of(url)
    return SITES[site]["read"] if site else "fetch"


def refusal(url: str) -> str:
    site = site_of(url)
    if site == "linkedin":
        return SITES[site]["why"]
    return ("Read it in a browser, or ask the user to copy the page text; "
            "pass a Job's text with --file")


def _get(url: str) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.8"})
    with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
        charset = response.headers.get_content_charset() or "utf-8"
        return response.read().decode(charset, errors="replace")


def robots_allows(url: str) -> bool:
    """Apply the site's robots.txt to url: the group for this agent or *, wildcards, longest rule wins."""
    parts = urllib.parse.urlsplit(url)
    try:
        text = _get(f"{parts.scheme}://{parts.netloc}/robots.txt")
    except urllib.error.HTTPError as exc:
        if exc.code in (404, 410):
            return True
        return False
    except (urllib.error.URLError, OSError) as exc:
        raise WebError(f"could not read robots.txt of {parts.netloc}: {exc}") from None
    groups, agents, in_rules = [], [], False
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].strip()
        if ":" not in line:
            continue
        key, value = (s.strip() for s in line.split(":", 1))
        key = key.lower()
        if key == "user-agent":
            if in_rules:
                agents, in_rules = [], False
            agents.append(value.lower())
            if len(agents) == 1:
                groups.append((agents, []))
        elif key in ("allow", "disallow") and groups:
            in_rules = True
            groups[-1][1].append((key, value))
    mine = [rules for names, rules in groups if any(n != "*" and n in USER_AGENT.lower() for n in names)]
    rules = mine[0] if mine else next((rules for names, rules in groups if "*" in names), [])
    target = parts.path or "/"
    if parts.query:
        target += "?" + parts.query
    best = ("allow", -1)
    for kind, pattern in rules:
        if not pattern:
            continue
        regex = re.escape(pattern).replace(r"\*", ".*")
        if regex.endswith(r"\$"):
            regex = regex[:-2] + "$"
        if re.match(regex, target) and (len(pattern) > best[1] or (len(pattern) == best[1] and kind == "allow")):
            best = (kind, len(pattern))
    return best[0] == "allow"


def fetch(url: str) -> str:
    url = clean_url(url)
    site = site_of(url)
    if read_method(url) != "fetch":
        reason = SITES[site]["why"] if site else "this site refuses automated reading"
        raise WebError(reason if site == "linkedin" else f"{reason}. {refusal(url)}")
    host = urllib.parse.urlsplit(url).netloc
    if not robots_allows(url):
        raise WebError(f"robots.txt of {host} does not allow reading {url}. {refusal(url)}")
    try:
        body = _get(url)
    except urllib.error.HTTPError as exc:
        if exc.code in (401, 403, 429, 503):
            raise WebError(f"{host} refused the request (HTTP {exc.code}). {refusal(url)}") from None
        raise WebError(f"{url}: HTTP {exc.code}") from None
    except (urllib.error.URLError, OSError) as exc:
        raise WebError(f"{url}: {exc}") from None
    if BOT_CHECK.search(body[:5000]):
        raise WebError(f"{host} answered with a bot check. {refusal(url)}")
    return body


def fetch_json(url: str):
    return json.loads(fetch(url))


# ---------------------------------------------------------------- parsing


def html_to_text(page: str) -> str:
    body = re.sub(r"(?is)<(script|style|noscript|svg|head|template)[^>]*>.*?</\1>", " ", page)
    body = re.sub(r"(?i)<br\s*/?>|</(p|div|li|h[1-6]|tr|section|article|ul|ol|header|footer|dt|dd)>", "\n", body)
    body = re.sub(r"(?i)<li[^>]*>", "\n- ", body)
    text = html.unescape(re.sub(r"<[^>]+>", " ", body))
    lines = [re.sub(r"[ \t　\xa0]+", " ", line).strip() for line in text.splitlines()]
    out = []
    for line in lines:
        if line and line != "-" and (not out or out[-1] != line):
            out.append(line)
    return "\n".join(out)


def job_posting(page: str):
    """Return the schema.org JobPosting embedded in a page, or None."""
    for block in re.findall(r'(?is)<script[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>', page):
        try:
            data = json.loads(html.unescape(block.strip()))
        except json.JSONDecodeError:
            continue
        items = data if isinstance(data, list) else data.get("@graph", [data]) if isinstance(data, dict) else []
        for item in items:
            kind = item.get("@type") if isinstance(item, dict) else None
            if kind == "JobPosting" or (isinstance(kind, list) and "JobPosting" in kind):
                return item
    return None


def _name(value) -> str:
    if isinstance(value, dict):
        return str(value.get("name") or "")
    if isinstance(value, list):
        return ", ".join(filter(None, (_name(v) for v in value)))
    return str(value or "")


def _place(value) -> str:
    if isinstance(value, list):
        return "; ".join(filter(None, (_place(v) for v in value)))
    if not isinstance(value, dict):
        return str(value or "")
    address = value.get("address", value)
    if isinstance(address, str):
        return address
    parts = [address.get(k) for k in ("streetAddress", "addressLocality", "addressRegion", "addressCountry")]
    seen = []
    for part in parts:
        if part and str(part) not in seen:
            seen.append(str(part))
    return ", ".join(seen)


def _salary(value) -> str:
    if not isinstance(value, dict):
        return str(value or "")
    amount = value.get("value", {})
    if isinstance(amount, dict):
        low, high = amount.get("minValue"), amount.get("maxValue")
        number = f"{low}-{high}" if low and high else str(amount.get("value") or low or high or "")
        unit = amount.get("unitText") or ""
    else:
        number, unit = str(amount or ""), ""
    return " ".join(filter(None, (value.get("currency"), number, unit)))


def posting_fields(posting: dict) -> dict:
    return {
        "title": str(posting.get("title") or ""),
        "company": _name(posting.get("hiringOrganization")),
        "location": _place(posting.get("jobLocation")),
        "salary": _salary(posting.get("baseSalary")),
        "employment_type": _name(posting.get("employmentType")) if not isinstance(posting.get("employmentType"), str)
        else posting["employmentType"],
        "posted": str(posting.get("datePosted") or "")[:10],
        "valid_through": str(posting.get("validThrough") or "")[:10],
        "description": html_to_text(str(posting.get("description") or "")),
    }


GENERIC_LINK_TEXT = {
    "apply", "apply now", "apply for this job", "learn more", "more", "details", "view", "view job",
    "立即應徵", "應徵", "我要應徵", "詳細", "查看", "了解更多",
}


def listing_links(page: str, listing_url: str) -> list:
    """Job links on a Listing page as (job id, title, url), using each Job's most descriptive link text."""
    base = clean_url(listing_url)
    site = site_of(base)
    base_path = urllib.parse.urlsplit(base).path.rstrip("/")
    order, texts, urls = [], {}, {}
    for href, inner in re.findall(r'(?is)<a\b[^>]*href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', page):
        url = clean_url(urllib.parse.urljoin(base, html.unescape(href)))
        if site_of(url) != site or (site is None and host_of(url) != host_of(base)):
            continue
        path = urllib.parse.urlsplit(url).path.rstrip("/")
        if site is None and (path == base_path or not (
                path.startswith(base_path + "/") or re.search(r"job|career|position|opening|vacanc", path, re.I))):
            continue
        try:
            jid, _, _ = job_id(url)
        except WebError:
            continue
        text = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", inner))).strip()
        if jid not in texts:
            order.append(jid)
            texts[jid], urls[jid] = [], url
        if text and text.lower() not in GENERIC_LINK_TEXT:
            texts[jid].append(text)
    return [(jid, max(texts[jid], key=len)[:160], urls[jid]) for jid in order if texts[jid]]


def yourator_listing(listing_url: str, page: int) -> list:
    parts = urllib.parse.urlsplit(clean_url(listing_url))
    query = [(k, v) for k, v in urllib.parse.parse_qsl(parts.query, keep_blank_values=True) if k != "page"]
    query.append(("page", str(page)))
    data = fetch_json(f"https://www.yourator.co/api/v4/jobs?{urllib.parse.urlencode(query)}")
    jobs = []
    for job in (data.get("payload") or {}).get("jobs") or []:
        url = "https://www.yourator.co" + job["path"]
        jobs.append({
            "id": job_id(url)[0], "title": job.get("name", ""), "company": (job.get("company") or {}).get("brand", "").strip(),
            "location": job.get("location", ""), "salary": job.get("salary", ""), "url": url,
        })
    return jobs
