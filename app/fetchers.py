from __future__ import annotations

import email.utils
import html
import json
import re
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from typing import Iterable

from app.models import NewsItem, Source

USER_AGENT = "FinancialDailyReporter/1.0 (+local hourly market monitor)"
TIMEOUT_SECONDS = 20


class RedirectHandler(urllib.request.HTTPRedirectHandler):
    def http_error_307(self, req, fp, code, msg, headers):  # noqa: ANN001
        return self.http_error_302(req, fp, code, msg, headers)

    def http_error_308(self, req, fp, code, msg, headers):  # noqa: ANN001
        return self.http_error_302(req, fp, code, msg, headers)


def fetch_all(sources: Iterable[Source]) -> tuple[list[NewsItem], list[str]]:
    items: list[NewsItem] = []
    errors: list[str] = []
    for source in sources:
        if not source.enabled:
            continue
        try:
            if source.kind == "json":
                items.extend(fetch_json_feed(source))
            else:
                items.extend(fetch_rss(source))
        except Exception as exc:  # noqa: BLE001 - report source failure but keep pipeline alive.
            errors.append(f"{source.name}: {exc}")
    return items, errors


def http_get(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    opener = urllib.request.build_opener(RedirectHandler)
    with opener.open(request, timeout=TIMEOUT_SECONDS) as response:
        return response.read()


def fetch_rss(source: Source) -> list[NewsItem]:
    body = http_get(source.url)
    root = ET.fromstring(body)
    entries = list(root.findall(".//item")) or list(root.findall(".//{http://www.w3.org/2005/Atom}entry"))
    items: list[NewsItem] = []
    for entry in entries[:80]:
        title = first_text(entry, ["title", "{http://www.w3.org/2005/Atom}title"])
        link = first_link(entry)
        published = first_text(
            entry,
            [
                "pubDate",
                "published",
                "updated",
                "{http://www.w3.org/2005/Atom}published",
                "{http://www.w3.org/2005/Atom}updated",
            ],
        )
        summary = first_text(
            entry,
            [
                "description",
                "summary",
                "{http://www.w3.org/2005/Atom}summary",
                "{http://purl.org/rss/1.0/modules/content/}encoded",
            ],
        )
        if not title:
            continue
        items.append(
            NewsItem(
                title=clean_text(title),
                url=link or source.url,
                source=source.name,
                market=source.market,
                published_at=parse_datetime(published),
                summary=clean_text(summary),
            )
        )
    return items


def fetch_json_feed(source: Source) -> list[NewsItem]:
    data = json.loads(http_get(source.url).decode("utf-8"))
    raw_items = data.get("items") if isinstance(data, dict) else data
    items: list[NewsItem] = []
    for raw in (raw_items or [])[:80]:
        if not isinstance(raw, dict):
            continue
        title = raw.get("title") or raw.get("headline") or raw.get("name")
        if not title:
            continue
        items.append(
            NewsItem(
                title=clean_text(str(title)),
                url=str(raw.get("url") or raw.get("link") or source.url),
                source=source.name,
                market=source.market,
                published_at=parse_datetime(str(raw.get("published_at") or raw.get("published") or raw.get("time") or "")),
                summary=clean_text(str(raw.get("summary") or raw.get("description") or raw.get("content") or "")),
            )
        )
    return items


def first_text(entry: ET.Element, tags: list[str]) -> str:
    for tag in tags:
        node = entry.find(tag)
        if node is not None and node.text:
            return node.text
    return ""


def first_link(entry: ET.Element) -> str:
    text_link = first_text(entry, ["link", "{http://www.w3.org/2005/Atom}link"])
    if text_link:
        return text_link.strip()
    atom_link = entry.find("{http://www.w3.org/2005/Atom}link")
    if atom_link is not None:
        return atom_link.attrib.get("href", "").strip()
    return ""


def parse_datetime(value: str) -> datetime:
    value = (value or "").strip()
    if not value:
        return datetime.now(timezone.utc)
    try:
        parsed = email.utils.parsedate_to_datetime(value)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed
    except Exception:
        pass
    for fmt in ("%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%d %H:%M:%S"):
        try:
            parsed = datetime.strptime(value, fmt)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed
        except ValueError:
            continue
    return datetime.now(timezone.utc)


def clean_text(value: str) -> str:
    text = html.unescape(value or "")
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()
