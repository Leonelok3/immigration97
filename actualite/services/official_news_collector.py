from __future__ import annotations

import html
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime
from email.utils import parsedate_to_datetime
from typing import Iterable
from urllib.parse import parse_qsl, urlencode, urljoin, urlparse, urlunparse
from urllib.request import Request, urlopen

from django.utils import timezone


KEYWORDS = (
    "immigration",
    "migration",
    "migrant",
    "refugee",
    "asylum",
    "visa",
    "work permit",
    "study permit",
    "permanent residence",
    "integration",
    "newcomer",
    "foreign worker",
    "skilled worker",
    "africa",
    "african",
    "cameroon",
    "conference",
    "event",
    "consultation",
)

OFFICIAL_HOSTS = (
    "canada.ca",
    "cicnews",  # not used as source; kept out by OFFICIAL_SOURCES unless added manually
    "bamf.de",
    "bmi.bund.de",
    "make-it-in-germany.com",
    "home-affairs.ec.europa.eu",
    "migrant-integration.ec.europa.eu",
    "ec.europa.eu",
    "commission.europa.eu",
)


@dataclass(frozen=True)
class OfficialNewsSource:
    label: str
    country: str
    category: str
    url: str


@dataclass(frozen=True)
class OfficialNewsCandidate:
    title: str
    summary: str
    url: str
    source_label: str
    country: str
    category: str
    published_at: datetime


OFFICIAL_SOURCES: tuple[OfficialNewsSource, ...] = (
    OfficialNewsSource("IRCC - Canada news", "CA", "law", "https://www.canada.ca/en/immigration-refugees-citizenship/news.html"),
    OfficialNewsSource("IRCC - Canada notices", "CA", "alert", "https://www.canada.ca/en/immigration-refugees-citizenship/news/notices.html"),
    OfficialNewsSource("BAMF - Allemagne", "DE", "law", "https://www.bamf.de/EN/Service/ServiceCenter/Aktuelles/aktuelles-node.html"),
    OfficialNewsSource("BMI - Allemagne", "DE", "law", "https://www.bmi.bund.de/EN/topics/migration/migration-node.html"),
    OfficialNewsSource("Make it in Germany", "DE", "opportunity", "https://www.make-it-in-germany.com/en/service/news"),
    OfficialNewsSource("Commission européenne - Migration", "EU", "law", "https://home-affairs.ec.europa.eu/news_en"),
    OfficialNewsSource("European Migration Network", "EU", "law", "https://home-affairs.ec.europa.eu/networks/european-migration-network-emn/emn-news_en"),
    OfficialNewsSource("European Website on Integration - News", "EU", "advice", "https://migrant-integration.ec.europa.eu/news_en"),
    OfficialNewsSource("European Website on Integration - Events", "EU", "conference", "https://migrant-integration.ec.europa.eu/events_en"),
)


def collect_official_news(limit: int = 12, timeout: int = 20) -> list[OfficialNewsCandidate]:
    candidates: list[OfficialNewsCandidate] = []
    seen: set[str] = set()
    for source in OFFICIAL_SOURCES:
        for candidate in _collect_from_source(source, timeout=timeout):
            key = canonical_url(candidate.url)
            if not key or key in seen:
                continue
            seen.add(key)
            candidates.append(candidate)
    candidates.sort(key=lambda item: item.published_at, reverse=True)
    return candidates[:limit]


def canonical_url(url: str) -> str:
    parsed = urlparse(url or "")
    if not parsed.scheme or not parsed.netloc:
        return ""
    ignored_prefixes = ("utm_",)
    ignored_keys = {"fbclid", "gclid", "msclkid", "source", "ref", "referrer"}
    query = [
        (key, value)
        for key, value in parse_qsl(parsed.query, keep_blank_values=True)
        if key.lower() not in ignored_keys and not key.lower().startswith(ignored_prefixes)
    ]
    normalized = parsed._replace(
        scheme=parsed.scheme.lower(),
        netloc=parsed.netloc.lower().removeprefix("www."),
        query=urlencode(query, doseq=True),
        fragment="",
    )
    return urlunparse(normalized).rstrip("/").lower()


def is_official_url(url: str) -> bool:
    host = urlparse(url or "").netloc.lower().removeprefix("www.")
    return any(host == official or host.endswith(f".{official}") for official in OFFICIAL_HOSTS if official != "cicnews")


def _collect_from_source(source: OfficialNewsSource, timeout: int) -> list[OfficialNewsCandidate]:
    body = _fetch(source.url, timeout=timeout)
    if not body:
        return []
    rss_items = _parse_feed(body, source)
    if rss_items:
        return rss_items
    return _parse_html_links(body, source)


def _fetch(url: str, timeout: int) -> str:
    request = Request(url, headers={"User-Agent": "Immigration97OfficialNewsBot/1.0"})
    try:
        with urlopen(request, timeout=timeout) as response:
            charset = response.headers.get_content_charset() or "utf-8"
            return response.read().decode(charset, errors="ignore")
    except Exception:
        return ""


def _parse_feed(body: str, source: OfficialNewsSource) -> list[OfficialNewsCandidate]:
    try:
        root = ET.fromstring(body)
    except ET.ParseError:
        return []

    items = []
    for node in list(root.findall(".//item")) + list(root.findall("{http://www.w3.org/2005/Atom}entry")):
        title = _clean_text(_node_text(node, "title"))
        link = _node_text(node, "link")
        if not link:
            link_node = node.find("{http://www.w3.org/2005/Atom}link")
            link = link_node.attrib.get("href", "") if link_node is not None else ""
        summary = _clean_text(_node_text(node, "description") or _node_text(node, "summary") or _node_text(node, "content"))
        published = _parse_date(_node_text(node, "pubDate") or _node_text(node, "published") or _node_text(node, "updated"))
        candidate = _candidate(source, title, summary, link, published)
        if candidate:
            items.append(candidate)
    return items


def _parse_html_links(body: str, source: OfficialNewsSource) -> list[OfficialNewsCandidate]:
    items: list[OfficialNewsCandidate] = []
    for href, label in re.findall(r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', body, flags=re.I | re.S):
        title = _clean_text(label)
        if len(title) < 18:
            continue
        url = urljoin(source.url, html.unescape(href))
        context = _nearby_text(body, href)
        candidate = _candidate(source, title, context, url, timezone.now())
        if candidate:
            items.append(candidate)
    return items


def _candidate(
    source: OfficialNewsSource,
    title: str,
    summary: str,
    url: str,
    published_at: datetime,
) -> OfficialNewsCandidate | None:
    url = urljoin(source.url, url or "")
    if not title or not url or not is_official_url(url):
        return None
    text = f"{title} {summary}".lower()
    if not any(keyword in text for keyword in KEYWORDS):
        return None
    if not summary:
        summary = f"Source officielle: {source.label}."
    return OfficialNewsCandidate(
        title=title[:255],
        summary=summary[:320],
        url=url,
        source_label=source.label,
        country=source.country,
        category=source.category,
        published_at=published_at,
    )


def _node_text(node, tag: str) -> str:
    found = node.find(tag) or node.find(f"{{http://www.w3.org/2005/Atom}}{tag}")
    return found.text or "" if found is not None else ""


def _parse_date(value: str) -> datetime:
    try:
        parsed = parsedate_to_datetime(value)
        return parsed if timezone.is_aware(parsed) else timezone.make_aware(parsed)
    except Exception:
        return timezone.now()


def _nearby_text(body: str, href: str) -> str:
    index = body.find(href)
    if index < 0:
        return ""
    return _clean_text(body[max(0, index - 600): index + 900])


def _clean_text(value: str) -> str:
    value = html.unescape(value or "")
    value = re.sub(r"<[^>]+>", " ", value)
    return re.sub(r"\s+", " ", value).strip()
