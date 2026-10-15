"""Read question text/options from authorized work pages; never submit answers."""

from __future__ import annotations

import re
from urllib.parse import urlencode, urljoin, urlsplit

from bs4 import BeautifulSoup

from .ChaoxingClient import ChaoxingFetchError, _auth_error

WORK_HOSTS = {"mooc1.chaoxing.com", "mooc1-api.chaoxing.com", "mooc2-ans.chaoxing.com"}


def validate_work_url(url: str) -> str:
    parsed = urlsplit(url)
    if (
        parsed.scheme != "https"
        or parsed.hostname not in WORK_HOSTS
        or parsed.username
        or parsed.password
        or parsed.port not in (None, 443)
        or "/work/" not in parsed.path
    ):
        raise ChaoxingFetchError("assignment_url_not_allowed")
    return url


def _text(node) -> str:
    if node is None:
        return ""
    # Work from a copy: removing labels must not mutate other question selectors.
    fragment = BeautifulSoup(str(node), "html.parser")
    for ignored in fragment.select(
        "script, style, input, textarea, button, .score, .colorShallow"
    ):
        ignored.decompose()
    for image in fragment.select("img"):
        image.replace_with(
            image.get("alt") or image.get("title") or "[图片内容未转成文字]"
        )
    return fragment.get_text(" ", strip=True)


def parse_assignment_questions(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    blocks = soup.select(".questionLi, .TiMu, .question-list, .marBom60")
    # Keep the innermost containers that have a stem. A spacing wrapper can
    # contain several questionLi nodes and must not collapse them into one.
    candidates = [
        block
        for block in blocks
        if block.select_one(".mark_name, .Zy_TItle, .question-title, .topic-title")
    ]
    ancestor_ids = {id(parent) for block in candidates for parent in block.parents}
    blocks = [block for block in candidates if id(block) not in ancestor_ids]
    questions = []
    for block in blocks:
        stem = _text(
            block.select_one(".mark_name, .Zy_TItle, .question-title, .topic-title")
        )
        if not stem:
            continue
        options = [
            _text(option)
            for option in block.select(
                ".mark_letter > li, .Zy_ulTop > li, .topic-options > li, .stem_answer > li"
            )
        ]
        if not options:
            options = [_text(option) for option in block.select(".stem_answer")]
        questions.append(
            {
                "number": len(questions) + 1,
                "stem": stem,
                "options": [option for option in options if option],
            }
        )
    return questions


def report_url(html: str) -> str | None:
    soup = BeautifulSoup(html, "html.parser")
    params = {}
    for key in ("workId", "workAnswerId", "courseId", "classId", "cpi"):
        field = soup.find("input", attrs={"name": key}) or soup.find("input", id=key)
        value = str(field.get("value", "")) if field else ""
        if not value.isdigit():
            match = re.search(rf"\b{key}\s*[=:]\s*['\"]?(\d+)", html)
            value = match.group(1) if match else ""
        params[key] = value
    if not all(
        params[key] for key in ("workId", "workAnswerId", "courseId", "classId")
    ):
        return None
    params.update({"knowledgeId": "0", "status": "4", "mooc": "1", "ut": "s"})
    return (
        "https://mooc1.chaoxing.com/mooc-ans/work/phone/selectWorkQuestionYiPiYue?"
        + urlencode(params)
    )


async def fetch_assignment_questions(client, url: str) -> list[dict]:
    async def fetch(target):
        for _ in range(6):
            validate_work_url(target)
            response = await client.client.get(target, follow_redirects=False)
            if response.status_code in (301, 302, 303, 307, 308):
                target = urljoin(target, response.headers.get("location", ""))
                redirect = urlsplit(target)
                if redirect.hostname in {
                    "passport2.chaoxing.com",
                    "passport.chaoxing.com",
                }:
                    raise ChaoxingFetchError("reauth_required")
                continue
            error = _auth_error(response)
            if error:
                raise ChaoxingFetchError(error)
            response.raise_for_status()
            if len(response.content) > 4 * 1024 * 1024:
                raise ChaoxingFetchError("assignment_content_too_large")
            return response.text
        raise ChaoxingFetchError("assignment_redirect_limit")

    html = await fetch(url)
    questions = parse_assignment_questions(html)
    if not questions:
        report = report_url(html)
        if report:
            questions = parse_assignment_questions(await fetch(report))
    if not questions:
        raise ChaoxingFetchError("assignment_questions_unavailable")
    return questions
