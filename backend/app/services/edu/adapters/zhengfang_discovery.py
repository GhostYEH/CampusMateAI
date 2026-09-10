"""Discover Zhengfang schedule requests from authenticated, same-origin pages."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
from html.parser import HTMLParser
import json
import re
from typing import Optional
from urllib.parse import parse_qs, urljoin, urlsplit


_SCHEDULE_PATH_PATTERN = re.compile(r"(?:xskbcx|xskb|xsKb|grkb|kbcx)", re.IGNORECASE)
_SEMESTER_NAMES = frozenset({"xnm", "xqm", "xnxq01id", "xn", "xq", "semester", "semesterId"})


class ScheduleDiscoveryError(ValueError):
    """Authenticated pages did not declare a safe schedule request."""


@dataclass(frozen=True)
class ScheduleCandidate:
    entry_path: str
    function_id: Optional[str]
    source: str = "authenticated_menu"
    score: int = 0


@dataclass(frozen=True)
class ScheduleProtocol:
    entry_path: str
    data_path: str
    method: str
    semester_params: tuple[str, ...]
    response_format: str
    source: str
    fingerprint: str

    def to_dict(self) -> dict:
        data = asdict(self)
        data["semester_params"] = list(self.semester_params)
        return data

    @classmethod
    def from_dict(cls, data: dict) -> "ScheduleProtocol":
        return cls(
            entry_path=str(data["entry_path"]),
            data_path=str(data["data_path"]),
            method=str(data["method"]).upper(),
            semester_params=tuple(str(item) for item in data.get("semester_params", [])),
            response_format=str(data.get("response_format") or "auto"),
            source=str(data.get("source") or "cached_discovered"),
            fingerprint=str(data["fingerprint"]),
        )


class _EvidenceParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.anchors: list[dict] = []
        self.forms: list[dict] = []
        self.scripts: list[str] = []
        self._anchor: Optional[dict] = None
        self._form: Optional[dict] = None
        self._script_parts: Optional[list[str]] = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, Optional[str]]]) -> None:
        values = {name.lower(): value or "" for name, value in attrs}
        if tag.lower() == "a":
            self._anchor = {"href": values.get("href", ""), "function_id": values.get("data-gnmkdm"), "text": ""}
        elif tag.lower() == "form":
            self._form = {"action": values.get("action", ""), "method": values.get("method", "GET").upper(), "fields": []}
            self.forms.append(self._form)
        elif tag.lower() in {"input", "select"} and self._form is not None:
            name = values.get("name")
            if name:
                self._form["fields"].append(name)
        elif tag.lower() == "script":
            self._script_parts = []

    def handle_data(self, data: str) -> None:
        if self._anchor is not None:
            self._anchor["text"] += data
        if self._script_parts is not None:
            self._script_parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "a" and self._anchor is not None:
            self.anchors.append(self._anchor)
            self._anchor = None
        elif tag.lower() == "form":
            self._form = None
        elif tag.lower() == "script" and self._script_parts is not None:
            self.scripts.append("".join(self._script_parts))
            self._script_parts = None


class ZhengfangCapabilityDiscoverer:
    """Extract explicit schedule capabilities without enumerating guessed paths."""

    def __init__(self, allowed_origin: str) -> None:
        self._origin = self._exact_https_origin(allowed_origin)
        if self._origin is None:
            raise ValueError("allowed_origin must be an exact HTTPS origin")

    @staticmethod
    def _exact_https_origin(value: str) -> Optional[str]:
        try:
            parsed = urlsplit(value)
            port = parsed.port
        except (TypeError, ValueError):
            return None
        if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
            return None
        suffix = "" if port in (None, 443) else f":{port}"
        return f"https://{parsed.hostname.lower()}{suffix}"

    def _same_origin_path(self, href: str, *, page_url: str) -> Optional[str]:
        if not href or href.startswith("//"):
            return None
        resolved = urljoin(page_url, href)
        if self._exact_https_origin(resolved) != self._origin:
            return None
        parsed = urlsplit(resolved)
        path = parsed.path or "/"
        return f"{path}?{parsed.query}" if parsed.query else path

    def menu_candidates(self, html: str, *, page_url: str) -> list[ScheduleCandidate]:
        parser = _EvidenceParser()
        parser.feed(html or "")
        found: dict[str, ScheduleCandidate] = {}
        for anchor in parser.anchors:
            text = re.sub(r"\s+", "", anchor["text"])
            href = anchor["href"].strip()
            semantic = "课表" in text and ("个人" in text or "学生" in text or "我的" in text)
            signature = bool(_SCHEDULE_PATH_PATTERN.search(href))
            if not semantic and not signature:
                continue
            path = self._same_origin_path(href, page_url=page_url)
            if path is None:
                continue
            query_function = (parse_qs(urlsplit(path).query).get("gnmkdm") or [None])[0]
            function_id = anchor.get("function_id") or query_function
            score = (20 if semantic else 0) + (10 if signature else 0) + (5 if function_id else 0)
            candidate = ScheduleCandidate(path, function_id, score=score)
            previous = found.get(path)
            if previous is None or candidate.score > previous.score:
                found[path] = candidate
        return sorted(found.values(), key=lambda item: (-item.score, item.entry_path))

    def page_protocol(
        self,
        html: str,
        *,
        page_url: str,
        candidate: ScheduleCandidate,
    ) -> ScheduleProtocol:
        parser = _EvidenceParser()
        parser.feed(html or "")
        declarations: list[tuple[str, str, tuple[str, ...]]] = []
        for form in parser.forms:
            action = form["action"] or page_url
            path = self._same_origin_path(action, page_url=page_url)
            if path is None or not _SCHEDULE_PATH_PATTERN.search(path):
                continue
            method = form["method"] if form["method"] in {"GET", "POST"} else "GET"
            semester_params = tuple(name for name in form["fields"] if name in _SEMESTER_NAMES)
            declarations.append((path, method, semester_params))

        if not declarations:
            for script in parser.scripts:
                for quoted in re.findall(r"[\"']([^\"']*(?:xskbcx|xskb|xsKb|grkb|kbcx)[^\"']*)[\"']", script, re.IGNORECASE):
                    path = self._same_origin_path(quoted, page_url=page_url)
                    if path is not None:
                        declarations.append((path, "POST", ()))

        if not declarations:
            raise ScheduleDiscoveryError("已认证课表页面未声明可验证的课表数据请求")

        data_path, method, semester_params = declarations[0]
        structure = {
            "entry_path": candidate.entry_path,
            "data_path": data_path,
            "method": method,
            "semester_params": list(semester_params),
            "function_id": candidate.function_id,
        }
        fingerprint = sha256(json.dumps(structure, ensure_ascii=True, sort_keys=True).encode("utf-8")).hexdigest()
        return ScheduleProtocol(
            entry_path=candidate.entry_path,
            data_path=data_path,
            method=method,
            semester_params=semester_params,
            response_format="auto",
            source="live_discovered",
            fingerprint=fingerprint,
        )


__all__ = [
    "ScheduleCandidate",
    "ScheduleDiscoveryError",
    "ScheduleProtocol",
    "ZhengfangCapabilityDiscoverer",
]
