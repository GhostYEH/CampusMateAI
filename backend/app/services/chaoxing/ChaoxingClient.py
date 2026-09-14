from __future__ import annotations

import asyncio
import httpx
import json
import re
import urllib.parse
from datetime import datetime, timedelta, timezone
from bs4 import BeautifulSoup

# 学习通所有时间字段均为北京时间(UTC+8)，解析出的时间统一按此归一，
# 便于 learner_event_service 直接消费(它要求 occurred_at 带时区)。
_CST = timezone(timedelta(hours=8))


class ChaoxingFetchError(RuntimeError):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def _identifier(*values) -> str:
    for value in values:
        if value is not None and str(value).strip() not in ("", "None"):
            return str(value).strip()
    return ""


def _response_text(response) -> str:
    text = getattr(response, "text", "")
    return text if isinstance(text, str) else ""


def _auth_error(response) -> str | None:
    text = _response_text(response)
    if any(keyword in text for keyword in ("验证码", "安全验证", "异常访问")):
        return "verification_required"
    if any(keyword in text for keyword in ("用户登录", "请登录", "登录后查看")):
        return "reauth_required"
    if response.status_code in (301, 302, 303, 307, 308, 401, 403):
        return "reauth_required"
    return None

class ChaoxingParser:
    @staticmethod
    def parse_courses_json(data: dict) -> list[dict]:
        courses = []
        for channel in data.get("channelList") or []:
            content = channel.get("content") or {}
            course_info = content.get("course") or {}
            for item in course_info.get("data") or []:
                course_id = _identifier(item.get("id"), item.get("courseId"), content.get("courseId"))
                clazz_id = _identifier(
                    item.get("clazzId"), item.get("classId"),
                    content.get("clazzId"), content.get("classId"), content.get("id"),
                    channel.get("clazzId"), channel.get("classId"), channel.get("id"), channel.get("key"),
                )
                course_name = str(item.get("name") or "").strip()
                if not course_name or not course_id:
                    continue
                external_id = f"{course_id}_{clazz_id}" if clazz_id else course_id
                course = {
                    "name": course_name,
                    "link": (
                        "https://mooc2-ans.chaoxing.com/mycourse/stu"
                        f"?courseid={course_id}&clazzid={clazz_id}"
                    ),
                    "course_id": course_id,
                    "clazz_id": clazz_id,
                    "external_id": external_id,
                }
                teacher_name = str(item.get("teacherfactor") or "").strip()
                if teacher_name:
                    course["teacher_name"] = teacher_name
                optional_fields = {
                    "cpi": _identifier(content.get("cpi")),
                    "school_name": str(item.get("schools") or "").strip(),
                    "class_name": str(content.get("name") or "").strip(),
                    "student_count": content.get("studentcount"),
                    "cover_url": str(item.get("imageurl") or "").strip(),
                    "starts_at": content.get("beginDate"),
                    "ends_at": content.get("endDate"),
                }
                for key, value in optional_fields.items():
                    if value not in (None, ""):
                        course[key] = value
                courses.append(course)
        return courses

    @staticmethod
    def parse_course_chapters(data: dict, *, course_id: str, clazz_id: str,
                              cpi: str) -> dict:
        chapters: list[dict] = []
        resources: list[dict] = []
        course_meta: dict = {}
        clazzes = data.get("data") or []
        for clazz in clazzes:
            clazz_meta = {
                "bbsid": _identifier(clazz.get("bbsid")),
                "chatid": _identifier(clazz.get("chatid")),
                "classscore": clazz.get("classscore"),
                "allowdownload": clazz.get("allowdownload"),
                "state": clazz.get("state"),
                "isstart": clazz.get("isstart"),
                "begindate": clazz.get("begindate"),
            }
            clazz_meta = {k: v for k, v in clazz_meta.items()
                          if v is not None and str(v).strip() not in ("", "None")}
            if clazz_meta:
                course_meta.setdefault("clazz", {}).update(clazz_meta)
            for course in ((clazz.get("course") or {}).get("data") or []):
                course_level_meta = {
                    "belongschoolid": _identifier(course.get("belongschoolid")),
                    "mappingcourseid": _identifier(course.get("mappingcourseid")),
                    "objectid": _identifier(course.get("objectid")),
                    "jobcount": course.get("jobcount"),
                    "infocontent": course.get("infocontent"),
                    "course_state": course.get("state"),
                }
                course_level_meta = {k: v for k, v in course_level_meta.items()
                                     if v is not None and str(v).strip() not in ("", "None")}
                if course_level_meta:
                    course_meta.setdefault("course", {}).update(course_level_meta)
                for position, node in enumerate(
                    ((course.get("knowledge") or {}).get("data") or []), start=1
                ):
                    external_id = _identifier(node.get("id"))
                    title = str(node.get("name") or "").strip()
                    if not external_id or not title:
                        continue
                    parent_id = _identifier(node.get("parentnodeid"))
                    if parent_id == "0":
                        parent_id = ""
                    layer = node.get("layer")
                    try:
                        depth = max(0, int(layer) - 1) if layer is not None else 0
                    except (TypeError, ValueError):
                        depth = 0
                    chapter_url = (
                        "https://mooc1-api.chaoxing.com/knowledge/cards"
                        f"?courseid={course_id}&clazzid={clazz_id}&knowledgeid={external_id}&cpi={cpi}"
                    )
                    raw_status = node.get("status")
                    chapter_metadata: dict = {
                        "job_count": int(node.get("jobcount") or 0),
                        "raw_status": raw_status,
                    }
                    for opt_key in ("isReview", "label", "begintime", "endtime"):
                        opt_value = node.get(opt_key)
                        if opt_value is not None and str(opt_value).strip() not in ("", "None"):
                            chapter_metadata[opt_key] = opt_value
                    chapters.append({
                        "external_id": external_id,
                        "parent_external_id": parent_id or None,
                        "kind": "chapter",
                        "title": title,
                        "position": int(node.get("indexOrder") or position),
                        "depth": depth,
                        "status": "completed" if raw_status in (1, "1", "completed") else "unknown",
                        "source_url": chapter_url,
                        "metadata": chapter_metadata,
                    })
                    attachments = (node.get("attachment") or {}).get("data") or []
                    for attachment_position, attachment in enumerate(attachments, start=1):
                        attachment_id = _identifier(attachment.get("id"), attachment.get("objectid"))
                        if not attachment_id:
                            continue
                        raw_type = str(attachment.get("type") or "").lower()
                        extension = str(attachment.get("extension") or "").lower().lstrip(".")
                        kind = raw_type if raw_type in {"video", "audio", "image", "document"} else "material"
                        attachment_title = str(attachment.get("name") or attachment.get("title") or "").strip()
                        if not attachment_title:
                            attachment_title = f"{kind}-{attachment_id}"
                            if extension:
                                attachment_title += f".{extension}"
                        resources.append({
                            "external_id": attachment_id,
                            "parent_external_id": external_id,
                            "kind": kind,
                            "title": attachment_title,
                            "position": attachment_position,
                            "depth": depth + 1,
                            "status": "unknown",
                            "remote_object_id": _identifier(attachment.get("objectid")) or None,
                            "mime_type": attachment.get("mimeType"),
                            "file_size": attachment.get("size"),
                            "source_url": chapter_url,
                            "metadata": {"extension": extension, "attachment_type": raw_type},
                        })
        return {"chapters": chapters, "resources": resources, "course_meta": course_meta}

    @staticmethod
    def parse_chapter_card_resources(html: str, *, chapter_id: str,
                                     card_url: str) -> dict:
        match = re.search(r"mArg\s*=\s*(\{.*?\})\s*;", html, re.DOTALL)
        if not match:
            if "knowledge-card" in html or "card-content" in html or '"card"' in html:
                return {"status": "structure_changed", "items": [], "error": "marg_not_found"}
            return {"status": "empty", "items": [], "error": None}
        try:
            payload = json.loads(match.group(1))
        except (ValueError, TypeError):
            return {"status": "structure_changed", "items": [], "error": "marg_parse_failed"}
        resources: list[dict] = []
        kind_map = {
            "video": "video", "audio": "audio", "document": "document",
            "image": "image", "link": "link",
            "vote": "poll", "work": "task",
            "test": "quiz", "live": "live",
        }
        for position, attachment in enumerate(payload.get("attachments") or [], start=1):
            if not isinstance(attachment, dict):
                continue
            prop = attachment.get("property") or {}
            raw_type = str(attachment.get("type") or prop.get("module") or "material").lower()
            kind = kind_map.get(raw_type, "material")
            object_id = _identifier(
                attachment.get("objectId"), attachment.get("objectid"),
                prop.get("objectid"), prop.get("objectId"),
            )
            external_id = _identifier(
                attachment.get("aid"), attachment.get("id"),
                attachment.get("jobid"), prop.get("jobid"), object_id,
            )
            if not external_id:
                continue
            title = str(prop.get("name") or prop.get("title") or attachment.get("title") or "").strip()
            if not title:
                title = f"{kind}-{external_id}"
            extension = str(prop.get("type") or "").lower().lstrip(".")
            metadata: dict = {
                "extension": extension,
                "attachment_type": raw_type,
                "raw_type": raw_type,
            }
            for opt_key in ("jobid", "aid", "objectId", "objectid", "module"):
                opt_value = attachment.get(opt_key) or prop.get(opt_key)
                if opt_value is not None and str(opt_value).strip() not in ("", "None"):
                    metadata[opt_key] = str(opt_value)
            if raw_type in ("test", "work", "vote", "live"):
                metadata["card_url"] = card_url
                if object_id:
                    metadata["object_id"] = object_id
            resources.append({
                "external_id": external_id,
                "parent_external_id": chapter_id,
                "kind": kind,
                "title": title,
                "position": position,
                "status": "unknown",
                "remote_object_id": object_id or None,
                "file_size": prop.get("size"),
                "source_url": card_url,
                "metadata": metadata,
            })
        if not resources:
            return {"status": "empty", "items": [], "error": None}
        return {"status": "complete", "items": resources, "error": None}

    @staticmethod
    def parse_courses_html(html: str) -> list[dict]:
        soup = BeautifulSoup(html, "lxml")
        courses = []
        for item in soup.select(".course-item, li.course"):  # Handle possible different DOM structures
            name_elem = item.select_one(".course-name, .course-title, h3, span.name")
            if not name_elem:
                continue
            course_name = name_elem.text.strip()
            
            link_elem = item.select_one("a")
            if not link_elem or "href" not in link_elem.attrs:
                continue
            course_link = link_elem["href"]
            
            # Extract courseid and clazzid from link
            # e.g., /mycourse/stu?courseid=234234&clazzid=4234234
            parsed_url = urllib.parse.urlparse(course_link)
            qs = urllib.parse.parse_qs(parsed_url.query)
            
            course_id = qs.get("courseid", qs.get("courseId", [""]))[0]
            clazz_id = qs.get("clazzid", qs.get("classId", [""]))[0]
            
            if not course_id:
                # Fallback: try to find in onclick or other attributes if needed, or regex on the whole link
                match = re.search(r'course[iI]d=(\d+)', course_link)
                course_id = match.group(1) if match else ""
                
            if not clazz_id:
                match = re.search(r'class[iI]d=(\d+)|clazz[iI]d=(\d+)', course_link)
                clazz_id = _identifier(*(match.groups() if match else ()))

            # If still not found, try to extract from the item's attributes
            if not course_id:
                course_id = item.get("courseid", item.get("data-courseid", ""))
            if not clazz_id:
                clazz_id = item.get("clazzid", item.get("data-classid", ""))
                
            external_id = f"{course_id}_{clazz_id}" if course_id and clazz_id else course_id or clazz_id
            if not external_id:
                continue # Skip if no stable ID can be found

            # Ensure link is absolute
            if course_link.startswith("/"):
                course_link = "https://mooc2-ans.chaoxing.com" + course_link
                
            courses.append({
                "name": course_name,
                "link": course_link,
                "course_id": course_id,
                "clazz_id": clazz_id,
                "external_id": external_id
            })
        return courses

    # ------------------------------------------------------------------
    # 成绩事实解析 —— 学习通页面结构不稳定，以下解析全部为"尽力而为":
    # 解析不到时返回 None，调用方保持原有降级行为，绝不因为解析失败中断同步。
    # ------------------------------------------------------------------

    @staticmethod
    def _to_float(value) -> float | None:
        if value is None:
            return None
        try:
            return float(str(value).strip())
        except (TypeError, ValueError):
            return None

    @staticmethod
    def to_iso(value) -> str | None:
        """把学习通的时间表示转换为带时区的 ISO 字符串。

        支持毫秒/秒级时间戳(学习通章节卡片常用)与 "2024-03-05 12:30" 文本。
        学习通时间均为北京时间，统一按 UTC+8 归一。
        """
        if value is None:
            return None
        text = str(value).strip()
        if not text or text in ("0", "None"):
            return None
        if re.fullmatch(r"\d{10,13}", text):
            timestamp = float(text)
            if timestamp > 1e11:  # 毫秒级时间戳
                timestamp /= 1000.0
            try:
                return datetime.fromtimestamp(timestamp, tz=timezone.utc).astimezone(_CST).isoformat()
            except (OverflowError, OSError, ValueError):
                return None
        normalized = (
            text.replace("年", "-").replace("月", "-").replace("日", " ")
            .replace("/", "-").replace("T", " ")
        )
        normalized = re.sub(r"\s+", " ", normalized).strip()
        try:
            parsed = datetime.fromisoformat(normalized)
        except ValueError:
            return None
        return parsed.replace(tzinfo=_CST).isoformat()

    @staticmethod
    def parse_score(text) -> tuple[float | None, float | None]:
        """从自由文本中解析 (得分, 满分)，解析不到返回 (None, None)。

        学习通列表页文案噪声很大，"满分100分""共 20 分""权重 30分"都不是得分，
        裸 "X分" 一律采信会把满分当成实得分。因此分三档由严到宽:
          1. 带明确关键词(成绩/得分/分数/评分) —— 直接采信;
          2. "X/Y" 形式 —— 日期片段已剔除，误判风险低;
          3. 裸 "X分" —— 只在批阅语境下采信，且先剔掉满分类描述。
        """
        if not text:
            return (None, None)
        raw = str(text)
        # 先剔除日期/时间片段，避免把 2024/03/05 或 12:30 误判成分数。
        cleaned = re.sub(r"\d{4}\s*[-/年]\s*\d{1,2}\s*[-/月]\s*\d{1,2}\s*日?", " ", raw)
        cleaned = re.sub(r"\d{1,2}:\d{2}(:\d{2})?", " ", cleaned)

        def _pair(match) -> tuple[float | None, float | None]:
            score = ChaoxingParser._to_float(match.group(1))
            if score is None:
                return (None, None)
            score_max = None
            if match.lastindex and match.lastindex > 1:
                candidate = ChaoxingParser._to_float(match.group(2))
                score_max = candidate if (candidate and candidate > 0) else None
            return (score, score_max)

        match = re.search(
            r"(?:成绩|得分|分数|评分)\D{0,4}(\d{1,3}(?:\.\d+)?)"
            r"(?:\s*(?:/|／)\s*(\d{1,3}(?:\.\d+)?))?",
            cleaned,
        )
        if match:
            result = _pair(match)
            if result[0] is not None:
                return result

        match = re.search(
            r"(\d{1,3}(?:\.\d+)?)\s*(?:/|／)\s*(\d{1,3}(?:\.\d+)?)", cleaned
        )
        if match:
            result = _pair(match)
            if result[0] is not None:
                return result

        # 裸 "X分": 没有批阅语义时宁可放弃，也不能把满分当实得分。
        if not re.search(r"(批阅|已阅|已评|评分|得分|成绩)", cleaned):
            return (None, None)
        if re.search(r"(满分|总分|分制|权重)", cleaned):
            return (None, None)
        stripped = re.sub(r"[共占]\s*\d{1,3}(?:\.\d+)?\s*分", " ", cleaned)
        match = re.search(r"(\d{1,3}(?:\.\d+)?)\s*分(?!钟)", stripped)
        if match:
            return _pair(match)
        return (None, None)

    # 作业报告页(selectWorkQuestionYiPiYue)的得分结构: 大号数字 + "分"。
    # 实测同页不含满分与提交时间，因此满分只能留空。
    _REPORT_SCORE_RE = re.compile(
        r'class="numberH2"[^>]*>\s*<span>\s*(\d+(?:\.\d+)?)\s*</span>'
    )

    @classmethod
    def parse_report_score(cls, html) -> tuple[float | None, float | None]:
        """从作业报告页解析 (得分, 满分)。解析不到返回 (None, None)。"""
        if not html:
            return (None, None)
        match = cls._REPORT_SCORE_RE.search(str(html))
        if not match:
            return (None, None)
        return (ChaoxingParser._to_float(match.group(1)), None)

    @staticmethod
    def parse_submitted_at(text) -> str | None:
        """从自由文本中解析真实提交时间，返回带时区 ISO 字符串。"""
        if not text:
            return None
        match = re.search(
            r"(?:提交时间|交卷时间|完成时间|提交于|提交)\D{0,6}"
            r"(\d{4}\s*[-/年]\s*\d{1,2}\s*[-/月]\s*\d{1,2}(?:\s*日)?"
            r"(?:\s+\d{1,2}:\d{2}(?::\d{2})?)?)",
            str(text),
        )
        if not match:
            return None
        return ChaoxingParser.to_iso(match.group(1))

    # 课程图谱页(stat2-ans.chaoxing.com/study-knowledge/index)的课程级统计节点。
    # 注意 "knowldegeCount" 是平台自身的拼写错误，必须照抄。
    _GRAPH_NUMBER_IDS = {
        "knowledge_point_count": "knowldegeCount",
        "own_mastery_rate": "ownGraspWeightRate",
        "class_mastery_rate": "graspWeightRate",
        "own_completion_rate": "ownCompleteWeightRate",
        "class_completion_rate": "completeWeightRate",
    }
    # 标签下拉里混着"一级~七级"(层级)和"父子关系/前后置关系"(关系类型)，
    # 它们不是知识点分类，需要剔除。
    _GRAPH_TAG_NOISE = ("级", "关系")

    @classmethod
    def parse_knowledge_graph(cls, html) -> dict:
        """解析课程图谱页: 课程级统计 + 知识点清单 + 分类标签。

        解析不到时返回空 dict / 空列表，由调用方降级，绝不抛异常。
        """
        if not html:
            return {}
        text = str(html)
        result: dict = {}
        for key, element_id in cls._GRAPH_NUMBER_IDS.items():
            match = re.search(rf'id="{element_id}"[^>]*>\s*([\d.]+)', text)
            if match:
                value = ChaoxingParser._to_float(match.group(1))
                if value is not None:
                    result[key] = value
        points: list[dict] = []
        seen: set[str] = set()
        for match in re.finditer(r'id="firstLevel-(\d+)"[^>]*>([^<]+)</li>', text):
            external_id = match.group(1)
            name = match.group(2).strip()
            if not name or external_id in seen:
                continue
            seen.add(external_id)
            points.append({"external_id": external_id, "name": name})
        result["knowledge_points"] = points
        raw_tags = set(re.findall(
            r'<label for="cb_\d+">\s*<div class="ellips">([^<]+)</div>', text
        ))
        result["tags"] = sorted(
            tag for tag in raw_tags
            if not any(noise in tag for noise in cls._GRAPH_TAG_NOISE)
        )
        return result

    @staticmethod
    def parse_exam_at(metadata: dict) -> str | None:
        """从章节卡片 metadata 中解析考试时间(优先开始时间，其次结束时间)。"""
        if not isinstance(metadata, dict):
            return None
        for key in ("begintime", "starttime", "startDate", "beginDate",
                    "startTime", "beginTime", "endtime", "endDate", "endTime"):
            iso = ChaoxingParser.to_iso(metadata.get(key))
            if iso:
                return iso
        return None

    @staticmethod
    def parse_metadata_score(metadata: dict) -> tuple[float | None, float | None]:
        """从章节卡片 metadata 中解析结构化分数(仅在字段明确存在时取值)。"""
        if not isinstance(metadata, dict):
            return (None, None)
        score = None
        for key in ("score", "grade", "finalScore", "studentScore"):
            if key in metadata:
                score = ChaoxingParser._to_float(metadata.get(key))
                if score is not None:
                    break
        score_max = None
        for key in ("scoreMax", "totalScore", "fullScore", "scoreTotal"):
            if key in metadata:
                score_max = ChaoxingParser._to_float(metadata.get(key))
                if score_max is not None:
                    break
        if score is None and score_max is None:
            # 退化为从自由文本中尽力提取，例如 "已批阅 88分"。
            return ChaoxingParser.parse_score(
                " ".join(str(metadata.get(key) or "") for key in ("raw_status", "label", "statusText"))
            )
        return (score, score_max)


class ChaoxingClient:
    def __init__(self, cookies: dict | None = None):
        self.client = httpx.AsyncClient(
            cookies=cookies,
            timeout=httpx.Timeout(30.0, connect=10.0),
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.93 Safari/537.36"},
            proxy=None,
            trust_env=False,
        )
        self._assignments_cache: list[dict] | None = None
        self._notices_cache: list[dict] | None = None
        self._course_chapters_cache: dict[tuple[str, str, str], dict] = {}

    @staticmethod
    def _mobile_headers() -> dict[str, str]:
        return {
            "User-Agent": (
                "Dalvik/2.1.0 (Linux; U; Android 12; SM-N9006 Build/70e2a6b.1) "
                "Language/zh_CN com.chaoxing.mobile/ChaoXingStudy_3_6.3.7_android_phone_10822_249"
            ),
            "Accept-Language": "zh_CN",
            "Connection": "Keep-Alive",
        }

    async def get_course_chapters(self, context: dict) -> dict:
        course_id = _identifier(context.get("course_id"))
        clazz_id = _identifier(context.get("clazz_id"), context.get("remote_class_id"))
        cpi = _identifier(context.get("cpi"), context.get("remote_cpi"))
        if not course_id or not clazz_id or not cpi:
            return {"status": "unavailable", "items": [], "error": "missing_course_context"}
        cache_key = (course_id, clazz_id, cpi)
        if cache_key in self._course_chapters_cache:
            cached = self._course_chapters_cache[cache_key]
            return {
                "status": cached["status"],
                "items": list(cached["items"]),
                "error": cached["error"],
                "course_meta": dict(cached.get("course_meta") or {}),
            }
        fields = (
            "id,bbsid,classscore,isstart,allowdownload,chatid,name,state,isfiled,"
            "visiblescore,hideclazz,begindate,forbidintoclazz,"
            "coursesetting.fields(id,courseid,hiddencoursecover,coursefacecheck),"
            "course.fields(id,belongschoolid,name,infocontent,objectid,app,bulletformat,"
            "mappingcourseid,imageurl,teacherfactor,jobcount,"
            "knowledge.fields(id,name,indexOrder,parentnodeid,status,isReview,layer,label,"
            "jobcount,begintime,endtime,attachment.fields(id,type,objectid,extension,name,title,size,mimeType)))"
        )
        try:
            response = await self.client.get(
                "https://mooc1-api.chaoxing.com/gas/clazz",
                params={"id": clazz_id, "personid": cpi, "fields": fields, "view": "json"},
                headers=self._mobile_headers(),
            )
            if response.status_code in (401, 403):
                return {"status": "unavailable", "items": [], "error": f"http_error_{response.status_code}"}
            response.raise_for_status()
            data = response.json()
            parsed = ChaoxingParser.parse_course_chapters(
                data, course_id=course_id, clazz_id=clazz_id, cpi=cpi
            )
            result = {
                "status": "complete",
                "items": parsed["chapters"] + parsed["resources"],
                "error": None,
                "course_meta": parsed.get("course_meta") or {},
            }
            self._course_chapters_cache[cache_key] = result
            return {
                "status": result["status"],
                "items": list(result["items"]),
                "error": result["error"],
                "course_meta": dict(result["course_meta"]),
            }
        except (ValueError, TypeError, AttributeError):
            return {"status": "failed", "items": [], "error": "structure_changed"}
        except (httpx.RequestError, OSError):
            return {"status": "failed", "items": [], "error": "network_error"}
        except httpx.HTTPStatusError as error:
            return {"status": "failed", "items": [], "error": f"http_error_{error.response.status_code}"}

    async def get_course_materials(self, context: dict, *,
                                   force_refresh: bool = False,
                                   unchanged_chapter_ids: set[str] | None = None) -> dict:
        chapter_result = await self.get_course_chapters(context)
        if chapter_result["status"] != "complete":
            return chapter_result
        kinds = {"document", "video", "audio", "image", "material", "link"}
        resources = [item for item in chapter_result["items"] if item.get("kind") in kinds]
        seen = {(str(item.get("kind")), str(item.get("external_id"))) for item in resources}
        course_id = _identifier(context.get("course_id"))
        clazz_id = _identifier(context.get("clazz_id"), context.get("remote_class_id"))
        cpi = _identifier(context.get("cpi"), context.get("remote_cpi"))
        skip_ids = set() if force_refresh else (unchanged_chapter_ids or set())

        async def fetch_card(chapter: dict) -> tuple[list[dict], str | None]:
            chapter_id = str(chapter.get("external_id") or "")
            if not chapter_id:
                return [], None
            if chapter_id in skip_ids:
                return [], None
            card_url = "https://mooc1.chaoxing.com/mooc-ans/knowledge/cards"
            try:
                response = await self.client.get(
                    card_url,
                    params={"clazzid": clazz_id, "courseid": course_id,
                            "knowledgeid": chapter_id, "num": "0", "ut": "s",
                            "cpi": cpi, "mooc2": "1"},
                    headers=self._mobile_headers(),
                )
                if response.status_code in (401, 403):
                    return [], f"chapter_cards_http_{response.status_code}"
                response.raise_for_status()
                parsed = ChaoxingParser.parse_chapter_card_resources(
                    response.text, chapter_id=chapter_id, card_url=str(response.url)
                )
                if parsed["status"] == "structure_changed":
                    return [], parsed.get("error") or "structure_changed"
                return parsed.get("items") or [], None
            except (httpx.RequestError, OSError):
                return [], "chapter_cards_network_error"
            except httpx.HTTPStatusError as error:
                return [], f"chapter_cards_http_{error.response.status_code}"

        chapters = [item for item in chapter_result["items"] if item.get("kind") == "chapter"]
        semaphore = asyncio.Semaphore(6)

        async def bounded_fetch(chapter: dict) -> tuple[list[dict], str | None]:
            async with semaphore:
                return await fetch_card(chapter)

        card_results = await asyncio.gather(*(bounded_fetch(chapter) for chapter in chapters))
        errors: list[str] = []
        for card_items, error in card_results:
            if error:
                errors.append(error)
                continue
            for item in card_items:
                key = (str(item.get("kind")), str(item.get("external_id")))
                if key not in seen:
                    resources.append(item)
                    seen.add(key)
        if errors:
            return {"status": "partial", "items": resources, "error": errors[0]}
        return {
            "status": "complete",
            "items": resources,
            "error": None,
        }

    async def get_course_exams(self, context: dict, *,
                               force_refresh: bool = False,
                               unchanged_chapter_ids: set[str] | None = None) -> dict:
        """利用 chapter card 中的 test/work 信息获取考试/作业候选条目。

        学习通专用考试页通常需要签名 task ID，无法直接获取完整考试详情。
        但 chapter card 中的 test/work 类型附件携带了 jobid/aid/objectId 等信息，
        可以保存为 exam_candidate，供前端跳转到学习通完成考试。
        需要真实学习通账号验证 chapter card 中 test/work 的 metadata 完整性。
        """
        materials_result = await self.get_course_materials(
            context, force_refresh=force_refresh,
            unchanged_chapter_ids=unchanged_chapter_ids,
        )
        if materials_result["status"] not in ("complete", "partial"):
            return materials_result
        course_id = _identifier(context.get("course_id"))
        clazz_id = _identifier(context.get("clazz_id"), context.get("remote_class_id"))
        exam_items: list[dict] = []
        for item in materials_result["items"]:
            metadata = item.get("metadata") or {}
            raw_type = str(metadata.get("raw_type") or metadata.get("attachment_type") or "").lower()
            kind = item.get("kind")
            candidate_type = None
            if kind == "quiz" and raw_type == "test":
                candidate_type = "test"
            elif kind == "task" and raw_type == "work":
                candidate_type = "work"
            if not candidate_type:
                continue
            exam_at = ChaoxingParser.parse_exam_at(metadata)
            score, score_max = ChaoxingParser.parse_metadata_score(metadata)
            exam_items.append({
                "kind": "exam_candidate",
                "external_id": item.get("external_id"),
                "title": item.get("title") or "未命名考试",
                "parent_external_id": item.get("parent_external_id"),
                "status": "unknown",
                "source_url": item.get("source_url"),
                "metadata": {
                    **metadata,
                    "candidate_type": candidate_type,
                    "course_id": course_id,
                    "clazz_id": clazz_id,
                    **({
                        "exam_at": exam_at,
                        "score": score,
                        "score_max": score_max,
                    } if (exam_at or score is not None) else {}),
                },
            })
        return {"status": "complete", "items": exam_items, "error": None}

    async def get_course_discussions(self, context: dict) -> dict:
        """利用 bbsid 获取课程讨论区数据。

        需要 gas/clazz 返回的 bbsid。如果 bbsid 不存在或请求失败，
        返回 unavailable 但不绕过权限/验证。
        需要真实学习通账号验证讨论区端点与字段结构。
        """
        chapter_result = await self.get_course_chapters(context)
        if chapter_result["status"] != "complete":
            return {"status": "unavailable", "items": [], "error": "chapters_not_available"}
        course_meta = chapter_result.get("course_meta") or {}
        bbsid = _identifier((course_meta.get("clazz") or {}).get("bbsid"))
        if not bbsid:
            return {"status": "unavailable", "items": [], "error": "bbsid_not_available"}
        course_id = _identifier(context.get("course_id"))
        clazz_id = _identifier(context.get("clazz_id"), context.get("remote_class_id"))
        cpi = _identifier(context.get("cpi"), context.get("remote_cpi"))
        try:
            response = await self.client.get(
                "https://mooc1-api.chaoxing.com/gas/clazzthread",
                params={
                    "bbsid": bbsid,
                    "clazzid": clazz_id,
                    "courseid": course_id,
                    "cpi": cpi,
                    "fields": "id,title,creatername,istop,lastreplytime,replycount,clickcount,sectionid",
                    "view": "json",
                },
                headers=self._mobile_headers(),
            )
            if response.status_code in (401, 403):
                return {"status": "unavailable", "items": [], "error": f"http_error_{response.status_code}"}
            response.raise_for_status()
            data = response.json()
            discussions: list[dict] = []
            for item in (data.get("data") or []):
                external_id = _identifier(item.get("id"))
                if not external_id:
                    continue
                discussions.append({
                    "kind": "discussion",
                    "external_id": external_id,
                    "title": str(item.get("title") or "无标题").strip(),
                    "author_name": str(item.get("creatername") or "").strip() or None,
                    "status": "unknown",
                    "source_url": (
                        f"https://mooc1.chaoxing.com/mycourse/comment"
                        f"?bbsid={bbsid}&courseid={course_id}&clazzid={clazz_id}"
                    ),
                    "metadata": {
                        "bbsid": bbsid,
                        "reply_count": item.get("replycount"),
                        "click_count": item.get("clickcount"),
                        "is_top": item.get("istop"),
                        "last_reply_time": item.get("lastreplytime"),
                        "section_id": item.get("sectionid"),
                    },
                })
            return {"status": "complete", "items": discussions, "error": None}
        except (ValueError, TypeError):
            return {"status": "failed", "items": [], "error": "structure_changed"}
        except (httpx.RequestError, OSError):
            return {"status": "failed", "items": [], "error": "network_error"}
        except httpx.HTTPStatusError as error:
            return {"status": "unavailable", "items": [], "error": f"http_error_{error.response.status_code}"}

    async def get_course_assignments(self, context: dict) -> dict:
        """Return the account work feed entries that belong to one real class."""
        course_id = _identifier(context.get("course_id"))
        clazz_id = _identifier(context.get("clazz_id"), context.get("remote_class_id"))
        if not course_id or not clazz_id:
            return {"status": "unavailable", "items": [], "error": "missing_course_context"}
        try:
            items = []
            for assignment in await self.get_all_assignments():
                if _identifier(assignment.get("course_id")) != course_id:
                    continue
                if _identifier(assignment.get("clazz_id")) != clazz_id:
                    continue
                external_id = _identifier(assignment.get("external_id"))
                if not external_id:
                    continue
                items.append({
                    "kind": "assignment",
                    "external_id": external_id,
                    "title": str(assignment.get("title") or "无标题").strip(),
                    "description": assignment.get("remote_status"),
                    "status": assignment.get("status") or "unknown",
                    "deadline": assignment.get("deadline") or None,
                    "source_url": assignment.get("link") or None,
                    "metadata": {
                        "course_id": course_id,
                        "clazz_id": clazz_id,
                        **{
                            key: value
                            for key, value in (
                                ("submitted_at", assignment.get("submitted_at")),
                                ("score", assignment.get("score")),
                                ("score_max", assignment.get("score_max")),
                                ("remote_status", assignment.get("remote_status")),
                            )
                            if value is not None
                        },
                    },
                })
            return {"status": "complete", "items": items, "error": None}
        except ChaoxingFetchError as error:
            return {"status": "failed", "items": [], "error": str(error)}

    async def get_course_knowledge_graph(self, context: dict) -> dict:
        """抓课程图谱页，返回课程级统计 + 知识点清单。

        新版泛雅(fanya V3)的"课程图谱"发布课程/学校的知识点体系与掌握率，
        比作业分数细一个量级。页面是服务端渲染，课程级统计与知识点清单
        直接内联在 HTML 里；知识点**逐个**的掌握率需要另外请求，此处不取。
        """
        course_id = _identifier(context.get("course_id"))
        clazz_id = _identifier(context.get("clazz_id"), context.get("remote_class_id"))
        if not course_id or not clazz_id:
            return {"status": "unavailable", "items": [], "graph": {},
                    "error": "missing_course_context"}
        url = (
            "https://stat2-ans.chaoxing.com/study-knowledge/index"
            f"?courseId={course_id}&clazzId={clazz_id}"
        )
        html = await self._get_text(url)
        if not html:
            return {"status": "failed", "items": [], "graph": {}, "error": "network_error"}
        parsed = ChaoxingParser.parse_knowledge_graph(html)
        if not parsed.get("knowledge_points") and not parsed.get("knowledge_point_count"):
            return {"status": "unavailable", "items": [], "graph": {},
                    "error": "structure_changed"}
        return {
            "status": "complete",
            "graph": parsed,
            "items": parsed.get("knowledge_points", []),
            "error": None,
        }

    async def get_course_notices(self, context: dict) -> dict:
        """Return only notices carrying matching course and class identifiers."""
        course_id = _identifier(context.get("course_id"))
        clazz_id = _identifier(context.get("clazz_id"), context.get("remote_class_id"))
        if not course_id or not clazz_id:
            return {"status": "unavailable", "items": [], "error": "missing_course_context"}
        try:
            items = []
            for notice in await self.get_all_notices():
                if _identifier(notice.get("course_id")) != course_id:
                    continue
                notice_clazz_id = _identifier(notice.get("clazz_id"))
                if notice_clazz_id and notice_clazz_id != clazz_id:
                    continue
                external_id = _identifier(notice.get("external_id"))
                if not external_id:
                    continue
                items.append({
                    "kind": "notice",
                    "external_id": external_id,
                    "title": str(notice.get("title") or "无标题").strip(),
                    "description": notice.get("content") or None,
                    "author_name": notice.get("creator_name") or None,
                    "published_at": notice.get("published_at") or None,
                    "source_url": notice.get("link") or None,
                    "metadata": {"course_id": course_id, "clazz_id": notice_clazz_id or clazz_id},
                })
            return {"status": "complete", "items": items, "error": None}
        except ChaoxingFetchError as error:
            return {"status": "failed", "items": [], "error": str(error)}

    async def login(self, username: str, password: str) -> tuple[bool, str]:
        """使用账号密码登录学习通并获取 cookies。
        返回 (是否成功, 状态信息/错误信息)
        """
        login_url = "https://passport2.chaoxing.com/api/login"
        params = {
            "name": username,
            "pwd": password,
            "verify": "0",
            "schoolid": "",
        }
        try:
            response = await self.client.get(login_url, params=params)
            response.raise_for_status()
            
            data = response.json()
            # 风控/验证页会返回 HTML 或 JSON 数组，非 dict 时直接判为结构变化，
            # 否则 data.get 抛 AttributeError 逃逸出去让调用方 500。
            if not isinstance(data, dict):
                return False, "structure_changed"
            if not data.get("result"):
                error_msg = data.get("errorMsg", "Unknown error")
                if "验证码" in error_msg or "异常" in error_msg or "短信" in error_msg:
                    return False, "verification_required"
                return False, error_msg

            # 登录后必须访问一个需要认证的学习通页面，确认 Session 真正有效
            verify_url = "https://mooc2-ans.chaoxing.com/visit/courses/list"
            verify_res = await self.client.get(verify_url, follow_redirects=False)
            auth_error = _auth_error(verify_res)
            if auth_error:
                return False, auth_error
            if verify_res.status_code >= 400:
                return False, f"http_error_{verify_res.status_code}"
            
            return True, "success"
            
        except (httpx.RequestError, OSError) as e:
            print(f"An error occurred while requesting {e.request.url!r}.")
            return False, "request_error"
        except httpx.HTTPStatusError as e: 
            print(f"Error response {e.response.status_code} while requesting {e.request.url!r}.")
            return False, f"http_error_{e.response.status_code}"
        except (ValueError, TypeError, AttributeError):
            return False, "structure_changed"


    async def get_courses(self) -> tuple[bool, list | str]:
        """获取课程列表。
        返回 (是否成功, 课程列表或错误信息)
        """
        # Try JSON API first
        api_url = "https://mooc1-api.chaoxing.com/mycourse/backclazzdata"
        try:
            res = await self.client.get(api_url, follow_redirects=False)
            auth_error = _auth_error(res)
            if auth_error:
                return False, auth_error
            if res.status_code == 200:
                try:
                    data = res.json()
                    if isinstance(data, dict):
                        message = str(data.get("msg") or data.get("errorMsg") or "")
                        if data.get("result") == 0 and "登录" in message:
                            return False, "reauth_required"
                        if any(keyword in message for keyword in ("验证码", "安全验证", "异常")):
                            return False, "verification_required"
                        courses = ChaoxingParser.parse_courses_json(data)
                        if courses:
                            return True, courses
                except Exception:
                    pass
            elif res.status_code in (302, 403):
                return False, "reauth_required"
        except (httpx.RequestError, OSError):
            pass
            
        # Fallback to HTML parsing if JSON API fails or returns no data
        courses_url = "https://mooc2-ans.chaoxing.com/visit/courses/list"
        try:
            # First verify session validity
            response = await self.client.get(courses_url, follow_redirects=False)
            auth_error = _auth_error(response)
            if auth_error:
                return False, auth_error
            response.raise_for_status()

            courses = ChaoxingParser.parse_courses_html(response.text)
            if courses or any(marker in response.text for marker in ("暂无课程", "还没有课程", "course-list")):
                return True, courses
            return False, "structure_changed"
        except (httpx.RequestError, OSError) as e:
            print(f"Network error while fetching courses: {e}")
            return False, "network_error"
        except httpx.HTTPStatusError as e:
            print(f"HTTP error while fetching courses: {e.response.status_code}")
            return False, f"http_error_{e.response.status_code}"

    async def get_assignments_and_notices(self, course_url: str) -> dict:
        """获取单个课程的作业和通知。"""
        try:
            query = urllib.parse.parse_qs(urllib.parse.urlparse(course_url).query)
            course_id = _identifier(*(query.get("courseid") or query.get("courseId") or []))
            class_id = _identifier(*(query.get("clazzid") or query.get("classId") or []))
            if not course_id or not class_id:
                assignments = await self.get_all_assignments(course_url)
                return {"assignments": assignments, "notices": []}

            assignments = await self.get_all_assignments()
            return {
                "assignments": [
                    item for item in assignments
                    if item.get("course_id") == course_id and item.get("clazz_id") == class_id
                ],
                "notices": [],
            }
        except ChaoxingFetchError:
            raise
        except (httpx.RequestError, OSError) as e:
            raise ChaoxingFetchError("network_error") from e
        except httpx.HTTPStatusError as e:
            raise ChaoxingFetchError(f"http_error_{e.response.status_code}") from e

    async def get_all_assignments(
        self, feed_url: str = "https://mooc1-api.chaoxing.com/work/stu-work"
    ) -> list[dict]:
        """Fetch the authenticated account's work feed exactly once.

        The current endpoint ignores courseId/classId and returns a global feed.
        Parsing it once prevents N courses from causing N identical requests and
        preserves the real course/class IDs carried by every work URL.
        """
        use_cache = feed_url == "https://mooc1-api.chaoxing.com/work/stu-work"
        if use_cache and self._assignments_cache is not None:
            return list(self._assignments_cache)
        try:
            response = await self.client.get(feed_url)
            auth_error = _auth_error(response)
            if auth_error:
                raise ChaoxingFetchError(auth_error)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "lxml")
            course_id = ""
            clazz_id = ""
            legacy_work_link = soup.find("a", {"title": "作业"})
            if legacy_work_link and legacy_work_link.get("data-url"):
                course_id = _identifier(
                    (soup.find("input", {"name": "courseid"}) or {}).get("value")
                )
                clazz_id = _identifier(
                    (soup.find("input", {"name": "clazzid"}) or {}).get("value")
                )
                enc = _identifier(
                    (soup.find("input", {"name": "workEnc"}) or {}).get("value")
                )
                work_url = urllib.parse.urljoin(
                    "https://mooc2-ans.chaoxing.com",
                    str(legacy_work_link.get("data-url")),
                )
                work_url = f"{work_url}?{urllib.parse.urlencode({'courseId': course_id, 'classId': clazz_id, 'enc': enc})}"
                response = await self.client.get(work_url)
                response.raise_for_status()
                soup = BeautifulSoup(response.text, "lxml")
            assignments: list[dict] = []
            items = soup.select("li[onclick*='goTask']")
            if not items:
                items = soup.select(".work-item, li, tr")
            for item in items:
                work_url = str(item.get("data") or "")
                link_elem = item.select_one("a[href]")
                if not work_url and link_elem:
                    work_url = urllib.parse.urljoin(
                        "https://mooc2-ans.chaoxing.com", str(link_elem.get("href") or "")
                    )
                query = urllib.parse.parse_qs(urllib.parse.urlparse(work_url).query)
                item_course_id = _identifier(
                    *(query.get("courseId") or query.get("courseid") or []), course_id
                )
                item_clazz_id = _identifier(
                    *(query.get("clazzId") or query.get("classId") or []), clazz_id
                )
                external_id = _identifier(
                    *(query.get("taskrefId") or query.get("workId") or query.get("jobId") or []),
                    item.get("data-workid"), item.get("data-jobid"), item.get("data-id"), item.get("id"),
                )
                title_elem = item.select_one("p, .work-title, .title, h3, .name")
                if not (item_course_id and item_clazz_id and external_id and title_elem):
                    continue
                deadline_elem = item.select_one(".work-deadline, .deadline, .time")
                texts = [node.get_text(" ", strip=True) for node in item.find_all("span")]
                status_elem = item.select_one(".status, .state, .work-status, .type, .sub-status")
                status_text = status_elem.get_text(" ", strip=True) if status_elem else next(
                    (text for text in texts if text in {
                        "未交", "未完成", "未提交", "待完成", "已交", "已完成",
                        "已提交", "已批阅", "待批阅",
                    }),
                    item.get_text(" ", strip=True),
                )
                completed = any(
                    marker in status_text
                    for marker in ("已交", "已完成", "已提交", "已批阅", "待批阅")
                )
                # 仅在已提交/已批阅时尝试解析真实提交时间与得分: 学习通把这两个
                # 事实放在同一个条目文本里，未提交的条目不应该产出成绩假象。
                score: float | None = None
                score_max: float | None = None
                submitted_at: str | None = None
                if completed:
                    item_text = item.get_text(" ", strip=True)
                    score, score_max = ChaoxingParser.parse_score(item_text)
                    submitted_at = ChaoxingParser.parse_submitted_at(item_text)
                assignments.append({
                    "title": title_elem.get_text(" ", strip=True),
                    "deadline": deadline_elem.get_text(" ", strip=True) if deadline_elem else "",
                    "external_id": external_id,
                    "status": "completed" if completed else "pending",
                    "remote_status": status_text,
                    "submitted_at": submitted_at,
                    "score": score,
                    "score_max": score_max,
                    "course_id": item_course_id,
                    "clazz_id": item_clazz_id,
                    "link": work_url,
                })
            if use_cache:
                self._assignments_cache = assignments
            return list(assignments)
        except ChaoxingFetchError:
            raise
        except (httpx.RequestError, OSError) as e:
            raise ChaoxingFetchError("network_error") from e
        except httpx.HTTPStatusError as e:
            raise ChaoxingFetchError(f"http_error_{e.response.status_code}") from e

    async def _get_text(self, url: str, attempts: int = 2) -> str:
        """带一次重试的文本抓取。学习通 TLS 偶发 SSLV3_ALERT_BAD_RECORD_MAC，
        失败返回空串由调用方降级，绝不抛出中断同步。"""
        for attempt in range(attempts):
            try:
                response = await self.client.get(url, follow_redirects=True)
                return response.text or ""
            except (httpx.RequestError, httpx.HTTPStatusError, OSError):
                if attempt + 1 < attempts:
                    await asyncio.sleep(0.8)
        return ""

    async def get_assignment_report(self, work_url: str) -> tuple[float | None, float | None]:
        """抓单个作业的报告页取分，返回 (得分, 满分)。

        学习通作业列表页只给状态(未提交/待批阅/已完成)，**不含分数**；
        得分只出现在作业报告页: 先用作业详情页里的 workId/workAnswerId 等参数
        拼出 selectWorkQuestionYiPiYue 地址，再解析大号分数节点。
        任何失败都返回 (None, None) —— 分数属于增量信息，绝不能中断同步。
        """
        if not work_url:
            return (None, None)
        detail_html = await self._get_text(str(work_url))
        if not detail_html:
            return (None, None)
        params: dict[str, str] = {}
        for key, pattern in (
            ("workId", r"workId=(\d+)"),
            ("workAnswerId", r"workAnswerId=(\d+)"),
            ("courseId", r"courseId=(\d+)"),
            ("classId", r"classId=(\d+)"),
            ("cpi", r"cpi=(\d+)"),
        ):
            match = re.search(pattern, detail_html)
            params[key] = match.group(1) if match else ""
        if not all(params[key] for key in ("workId", "workAnswerId", "courseId", "classId")):
            return (None, None)
        report_url = (
            "https://mooc1.chaoxing.com/mooc-ans/work/phone/selectWorkQuestionYiPiYue"
            f"?courseId={params['courseId']}&workAnswerId={params['workAnswerId']}"
            f"&workId={params['workId']}&knowledgeId=0&status=4&classId={params['classId']}"
            f"&oldWorkId=&mooc=1&ut=s&cpi={params['cpi']}"
        )
        report_html = await self._get_text(report_url)
        return ChaoxingParser.parse_report_score(report_html)

    async def enrich_assignment_scores(self, assignments: list[dict], *,
                                       limit: int = 20, concurrency: int = 3,
                                       budget_seconds: float = 45.0) -> int:
        """为"已提交但还没有分数"的作业补抓报告页得分，就地写回并返回成功条数。

        逐作业请求不可避免(列表页没有分数)，每个作业需要详情页 + 报告页两次请求，
        因此用三道闸限制对同步接口的影响:
        - limit: 单次最多处理多少个作业;
        - concurrency: 并发上限;
        - budget_seconds: 整批总时间预算。前端同步请求超时是 120 秒，补抓必须留出
          余量，超预算的作业本轮直接跳过，下次同步继续补(渐进收敛)。
        失败静默跳过，绝不抛出。
        """
        targets = [
            item for item in assignments
            if item.get("status") == "completed"
            and item.get("score") is None
            and item.get("link")
        ][:max(0, limit)]
        if not targets:
            return 0
        loop = asyncio.get_running_loop()
        deadline = loop.time() + max(1.0, budget_seconds)
        semaphore = asyncio.Semaphore(max(1, concurrency))
        fetched = 0

        async def worker(item: dict) -> None:
            nonlocal fetched
            if loop.time() >= deadline:
                return
            async with semaphore:
                if loop.time() >= deadline:
                    return
                score, score_max = await self.get_assignment_report(str(item["link"]))
                if score is not None:
                    item["score"] = score
                    if score_max is not None:
                        item["score_max"] = score_max
                    fetched += 1

        await asyncio.gather(*(worker(item) for item in targets), return_exceptions=True)
        return fetched

    async def get_all_notices(self) -> list[dict]:
        """Fetch the authenticated notification inbox returned by Chaoxing."""
        if self._notices_cache is not None:
            return list(self._notices_cache)
        try:
            notice_url = "https://notice.chaoxing.com/pc/notice/getNoticeList"
            notice_resp = await self.client.get(notice_url, follow_redirects=False)
            auth_error = _auth_error(notice_resp)
            if auth_error:
                raise ChaoxingFetchError(auth_error)
            notice_resp.raise_for_status()
            try:
                data = notice_resp.json()
            except Exception:
                data = None
            if not isinstance(data, dict):
                soup = BeautifulSoup(notice_resp.text, "lxml")
                course_input = soup.find("input", {"name": "courseid"}) or soup.find("input", {"id": "courseId"})
                clazz_input = soup.find("input", {"name": "clazzid"}) or soup.find("input", {"id": "classId"})
                if not (course_input and clazz_input):
                    raise ChaoxingFetchError("structure_changed")
                course_id = _identifier(course_input.get("value"))
                clazz_id = _identifier(clazz_input.get("value"))
                legacy_url = "https://mooc1.chaoxing.com/notice/getNoticeList"
                notice_resp = await self.client.get(
                    legacy_url, params={"courseId": course_id, "classId": clazz_id}
                )
                notice_resp.raise_for_status()
                try:
                    data = notice_resp.json()
                except Exception:
                    html_notices = []
                    for item in BeautifulSoup(notice_resp.text, "lxml").select(
                        ".notice-item, .noticeList li, tr"
                    ):
                        title_elem = item.select_one(".title, .name, h3, a")
                        if not title_elem:
                            continue
                        link_elem = item.select_one("a[href]")
                        link = str(link_elem.get("href") or "") if link_elem else ""
                        external_id = _identifier(
                            item.get("data-noticeid"), item.get("data-id"), item.get("id")
                        )
                        if not external_id and link:
                            match = re.search(
                                r"(?:noticeId|id|announcementId)=([A-Za-z0-9_-]+)", link, re.IGNORECASE
                            )
                            external_id = match.group(1) if match else ""
                        if not external_id:
                            continue
                        content_elem = item.select_one(".content, .summary, p")
                        time_elem = item.select_one(".time, .date")
                        html_notices.append({
                            "external_id": external_id,
                            "title": title_elem.get_text(" ", strip=True),
                            "content": content_elem.get_text(" ", strip=True) if content_elem else "",
                            "published_at": time_elem.get_text(" ", strip=True) if time_elem else None,
                            "course_id": course_id or None,
                            "clazz_id": clazz_id or None,
                            "course_name": None,
                            "creator_name": None,
                            "link": urllib.parse.urljoin("https://mooc1.chaoxing.com", link),
                        })
                    self._notices_cache = html_notices
                    return list(html_notices)
            envelope = data.get("notices") or data.get("data") or data
            raw_items = envelope.get("list") if isinstance(envelope, dict) else None
            if not isinstance(raw_items, list):
                raise ChaoxingFetchError("structure_changed")
            notices: list[dict] = []
            for item in raw_items:
                external_id = _identifier(
                    item.get("idCode"), item.get("uuid"), item.get("id"), item.get("noticeId")
                )
                if not external_id:
                    continue
                course_id = ""
                clazz_id = ""
                course_name = ""
                receivers = item.get("receiverArray") or []
                if isinstance(receivers, list):
                    receiver = next((value for value in receivers if isinstance(value, dict)), None)
                    if receiver:
                        course_id = _identifier(receiver.get("courseId"))
                        clazz_id = _identifier(receiver.get("clazzId"))
                        course_name = str(receiver.get("name") or "").strip()
                cparams = (item.get("extendParam") or {}).get("cparams")
                if cparams:
                    try:
                        content = ((json.loads(cparams).get("funConfig") or {}).get("content") or {})
                        course_id = _identifier(course_id, content.get("courseId"))
                        course_name = course_name or str(content.get("courseName") or "").strip()
                        key = str(content.get("key") or "")
                        if "-" in key:
                            clazz_id = _identifier(clazz_id, key.rsplit("-", 1)[-1])
                    except (ValueError, TypeError, AttributeError):
                        pass
                notices.append({
                    "external_id": external_id,
                    "title": str(item.get("title") or "无标题").strip(),
                    "content": str(item.get("content") or item.get("rtf_content") or "").strip(),
                    "published_at": item.get("insertTime") or item.get("sendTime"),
                    "creator_name": str(item.get("createrName") or "").strip() or None,
                    "course_id": course_id or None,
                    "clazz_id": clazz_id or None,
                    "course_name": course_name or None,
                    "link": f"https://notice.chaoxing.com/pc/notice/detail/{external_id}",
                })
            self._notices_cache = notices
            return list(notices)
        except ChaoxingFetchError:
            raise
        except (ValueError, TypeError) as e:
            raise ChaoxingFetchError("structure_changed") from e
        except (httpx.RequestError, OSError) as e:
            raise ChaoxingFetchError("network_error") from e
        except httpx.HTTPStatusError as e:
            raise ChaoxingFetchError(f"http_error_{e.response.status_code}") from e

    async def get_notices(self, course_url: str) -> list[dict]:
        """Compatibility wrapper returning notices belonging to one course."""
        query = urllib.parse.parse_qs(urllib.parse.urlparse(course_url).query)
        course_id = _identifier(*(query.get("courseid") or query.get("courseId") or []))
        notices = await self.get_all_notices()
        return [item for item in notices if item.get("course_id") == course_id]
