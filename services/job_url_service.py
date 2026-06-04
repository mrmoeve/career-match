import json
import re
from dataclasses import dataclass
from datetime import datetime
from html import unescape
from typing import Any
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup


REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}

JUNK_PATTERNS = [
    "skip to main content",
    "search jobs",
    "saved jobs",
    "back to search results",
    "share to twitter",
    "share to facebook",
    "share to linkedin",
    "apply now",
    "save job",
    "privacy preference center",
    "cookie preferences",
]


class JobExtractionError(Exception):
    pass


@dataclass
class JobPostingContent:
    url: str
    title: str
    company_name: str
    location: str
    date_posted: str
    category: str
    description_text: str
    extraction_confidence: int


def validate_job_url(url: str) -> str:
    cleaned = (url or "").strip()
    parsed = urlparse(cleaned)
    if not cleaned:
        raise JobExtractionError("Enter a job posting URL to continue.")
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise JobExtractionError("Enter a valid URL starting with http:// or https://.")
    return cleaned


def _clean_text(text: str) -> str:
    text = unescape(text or "")
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _is_junk_title(text: str) -> bool:
    lowered = _clean_text(text).lower()
    if not lowered:
        return True
    if any(lowered == pattern or lowered.startswith(pattern) for pattern in JUNK_PATTERNS):
        return True
    if any(marker in lowered for marker in ["share to ", "search jobs", "saved jobs", "apply now"]):
        return True
    if len(lowered.split()) > 14:
        return True
    return False


def _strip_junk_phrases(text: str) -> str:
    cleaned = text or ""
    for pattern in JUNK_PATTERNS:
        cleaned = re.sub(re.escape(pattern), " ", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def _clean_multiline_text(text: str) -> str:
    lines = []
    seen = set()
    for raw_line in (text or "").splitlines():
        line = _clean_text(raw_line)
        line = _strip_junk_phrases(line)
        lowered = line.lower()
        if not line:
            continue
        if lowered in seen:
            continue
        seen.add(lowered)
        lines.append(line)
    return "\n".join(lines)


def _extract_json_ld_objects(soup: BeautifulSoup) -> list[dict[str, Any]]:
    objects: list[dict[str, Any]] = []
    for tag in soup.find_all("script", attrs={"type": "application/ld+json"}):
        raw = tag.string or tag.get_text()
        if not raw or not raw.strip():
            continue
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, list):
            objects.extend([item for item in parsed if isinstance(item, dict)])
        elif isinstance(parsed, dict):
            objects.append(parsed)
    return objects


def _pick_job_posting_object(objects: list[dict[str, Any]]) -> dict[str, Any]:
    for item in objects:
        item_type = item.get("@type")
        if item_type == "JobPosting" or (isinstance(item_type, list) and "JobPosting" in item_type):
            return item
    return {}


def _extract_meta_content(soup: BeautifulSoup, *attrs: tuple[str, str]) -> str:
    for key, value in attrs:
        tag = soup.find("meta", attrs={key: value})
        if tag:
            content = _clean_text(tag.get("content", ""))
            if content:
                return content
    return ""


def _extract_title(soup: BeautifulSoup, job_posting: dict[str, Any]) -> tuple[str, int]:
    candidates: list[tuple[str, int]] = [
        (_clean_text(job_posting.get("title", "")), 30),
        (_extract_meta_content(soup, ("property", "og:title"), ("name", "twitter:title")), 24),
    ]
    h1 = soup.find("h1")
    if h1:
        candidates.append((_clean_text(h1.get_text(" ", strip=True)), 20))
    if soup.title:
        candidates.append((_clean_text(soup.title.get_text(" ", strip=True)), 16))

    for node in soup.select("h1, h2, [class*='title'], [data-testid*='title'], [class*='job-title']"):
        candidates.append((_clean_text(node.get_text(" ", strip=True)), 12))

    for candidate, score in candidates:
        candidate = _strip_junk_phrases(candidate)
        if not candidate or len(candidate) < 4:
            continue
        parts = [part.strip() for part in re.split(r"\s+[|\-–]\s+|\s*:\s*", candidate) if part.strip()]
        for part in parts:
            part = _strip_junk_phrases(part)
            if part and not _is_junk_title(part):
                return part[:140], score
    return "Unknown Role", 0


def _extract_company_from_domain(url: str) -> str:
    host = urlparse(url).netloc.lower().replace("www.", "")
    host = host.split(":")[0]
    parts = [part for part in re.split(r"[.\-]", host) if part and part not in {"jobs", "careers", "boards", "greenhouse", "lever", "workday"}]
    if parts:
        return parts[0].title()
    return ""


def _extract_company(soup: BeautifulSoup, job_posting: dict[str, Any], url: str) -> tuple[str, int]:
    hiring_org = job_posting.get("hiringOrganization")
    if isinstance(hiring_org, dict):
        name = _clean_text(hiring_org.get("name", ""))
        if name:
            return name[:140], 26

    meta_candidates = [
        _extract_meta_content(soup, ("property", "og:site_name")),
        _extract_meta_content(soup, ("name", "author")),
    ]
    for candidate in meta_candidates:
        if candidate and len(candidate.split()) <= 8:
            return candidate[:140], 18

    selectors = [
        "[data-company]",
        "[class*='company']",
        "[data-testid*='company']",
        "[class*='employer']",
    ]
    for selector in selectors:
        node = soup.select_one(selector)
        if node:
            cleaned = _clean_text(node.get_text(" ", strip=True))
            if cleaned and len(cleaned.split()) <= 10:
                return cleaned[:140], 16

    title_blob = " ".join(
        filter(
            None,
            [
                _extract_meta_content(soup, ("property", "og:title")),
                soup.title.get_text(" ", strip=True) if soup.title else "",
            ],
        )
    )
    company_match = re.search(r"\bat\s+([A-Z][A-Za-z0-9&.\- ]{2,60})", title_blob)
    if company_match:
        return _clean_text(company_match.group(1))[:140], 14

    domain_company = _extract_company_from_domain(url)
    if domain_company:
        return domain_company[:140], 8

    return "Unknown Company", 0


def _extract_location(soup: BeautifulSoup, job_posting: dict[str, Any]) -> tuple[str, int]:
    location = job_posting.get("jobLocation")
    if isinstance(location, dict):
        address = location.get("address", {})
        if isinstance(address, dict):
            pieces = [
                _clean_text(address.get("addressLocality", "")),
                _clean_text(address.get("addressRegion", "")),
                _clean_text(address.get("addressCountry", "")),
            ]
            cleaned = ", ".join([piece for piece in pieces if piece])
            if cleaned:
                return cleaned, 22
    if isinstance(location, list):
        for item in location:
            if isinstance(item, dict):
                extracted, score = _extract_location(soup, {"jobLocation": item})
                if extracted:
                    return extracted, score

    meta_location = _extract_meta_content(soup, ("property", "og:location"))
    if meta_location:
        return meta_location, 12

    selectors = [
        "[data-testid*='location']",
        "[class*='location']",
        "[class*='job-location']",
    ]
    for selector in selectors:
        node = soup.select_one(selector)
        if node:
            cleaned = _clean_text(node.get_text(" ", strip=True))
            if cleaned and len(cleaned) < 120:
                return cleaned, 12
    return "", 0


def _format_date(value: str) -> str:
    value = _clean_text(value)
    for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%dT%H:%M:%SZ"):
        try:
            return datetime.strptime(value, fmt).strftime("%b %-d, %Y")
        except ValueError:
            continue
    return value


def _extract_date_posted(soup: BeautifulSoup, job_posting: dict[str, Any]) -> tuple[str, int]:
    for key in ["datePosted", "validThrough"]:
        if isinstance(job_posting.get(key), str):
            return _format_date(job_posting[key]), 16

    selectors = [
        "time",
        "[data-testid*='date']",
        "[class*='posted']",
        "[class*='date']",
    ]
    for selector in selectors:
        node = soup.select_one(selector)
        if not node:
            continue
        cleaned = _clean_text(node.get("datetime") or node.get_text(" ", strip=True))
        if cleaned and any(char.isdigit() for char in cleaned):
            return _format_date(cleaned), 10
    return "", 0


def _extract_category(soup: BeautifulSoup, job_posting: dict[str, Any]) -> tuple[str, int]:
    category = job_posting.get("occupationalCategory")
    if isinstance(category, str):
        cleaned = _clean_text(category)
        if cleaned:
            return cleaned[:120], 16

    selectors = [
        "[data-testid*='department']",
        "[data-testid*='category']",
        "[class*='department']",
        "[class*='category']",
    ]
    for selector in selectors:
        node = soup.select_one(selector)
        if node:
            cleaned = _clean_text(node.get_text(" ", strip=True))
            if cleaned and len(cleaned) < 80:
                return cleaned[:120], 10
    return "", 0


def _extract_description(soup: BeautifulSoup, job_posting: dict[str, Any]) -> tuple[str, int]:
    description = job_posting.get("description")
    if isinstance(description, str):
        cleaned = _clean_multiline_text(BeautifulSoup(description, "html.parser").get_text("\n", strip=True))
        if len(cleaned) > 120:
            return cleaned, 28

    selectors = [
        "[data-testid*='jobDescription']",
        "[class*='job-description']",
        "[class*='description']",
        "[id*='job-description']",
        "article",
        "main",
    ]
    for selector in selectors:
        node = soup.select_one(selector)
        if not node:
            continue
        cleaned = _clean_multiline_text(node.get_text("\n", strip=True))
        if len(cleaned) > 120:
            return cleaned, 20

    cleaned_body = _clean_multiline_text(soup.get_text("\n", strip=True))
    return cleaned_body, 8


def _detect_blocked_response(response: requests.Response, text: str) -> None:
    if response.status_code in {403, 429}:
        raise JobExtractionError(
            "This page appears to block automated access. Use the advanced manual fallback to paste the description."
        )
    lowered = text.lower()
    blocked_markers = [
        "access denied",
        "captcha",
        "enable javascript",
        "verify you are human",
        "bot detection",
    ]
    if any(marker in lowered for marker in blocked_markers):
        raise JobExtractionError(
            "This page appears to be blocked or protected. Use the advanced manual fallback to paste the description."
        )


def fetch_job_posting_from_url(url: str, timeout: int = 15) -> JobPostingContent:
    validated_url = validate_job_url(url)
    try:
        response = requests.get(validated_url, headers=REQUEST_HEADERS, timeout=timeout)
    except requests.RequestException as exc:
        raise JobExtractionError(f"Unable to fetch that URL right now: {exc}") from exc

    html = response.text or ""
    _detect_blocked_response(response, html)
    if response.status_code >= 400:
        raise JobExtractionError(
            f"Unable to fetch the job posting. The page returned status code {response.status_code}."
        )

    soup = BeautifulSoup(html, "html.parser")
    json_ld_objects = _extract_json_ld_objects(soup)
    job_posting = _pick_job_posting_object(json_ld_objects)

    title, title_score = _extract_title(soup, job_posting)
    company_name, company_score = _extract_company(soup, job_posting, validated_url)
    location, location_score = _extract_location(soup, job_posting)
    date_posted, date_score = _extract_date_posted(soup, job_posting)
    category, category_score = _extract_category(soup, job_posting)
    description_text, description_score = _extract_description(soup, job_posting)

    if len(description_text) < 120:
        raise JobExtractionError(
            "The page loaded, but the job description could not be extracted clearly. "
            "The site may be empty, heavily scripted, or blocked. Use the advanced manual fallback."
        )

    confidence = min(
        100,
        title_score + company_score + location_score + date_score + category_score + description_score,
    )

    return JobPostingContent(
        url=validated_url,
        title=title,
        company_name=company_name,
        location=location,
        date_posted=date_posted,
        category=category,
        description_text=description_text,
        extraction_confidence=confidence,
    )
