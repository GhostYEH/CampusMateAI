from __future__ import annotations

import asyncio
import httpx
import json
import re
import urllib.parse
from bs4 import BeautifulSoup


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
        clazzes = data.get("data") or []
        for clazz in clazzes:
            for course in ((clazz.get("course") or {}).get("data") or []):
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
                    chapters.append({
                        "external_id": external_id,
                        "parent_external_id": parent_id or None,
                        "kind": "chapter",
                        "title": title,
                        "position": int(node.get("indexOrder") or position),
                        "depth": depth,
                        "status": "completed" if node.get("status") in (1, "1", "completed") else "unknown",
                        "source_url": chapter_url,
                        "metadata": {"job_count": int(node.get("jobcount") or 0)},
                    })
                    attachments = (node.get("attachment") or {}).get("data") or []
                    for attachment_position, attachment in enumerate(attachments, start=1):
                        attachment_id = _identifier(attachment.get("id"), attachment.get("objectid"))
                        if not attachment_id:
                            continue
                        raw_type = str(attachment.get("type") or "").lower()
                        extension = str(attachment.get("extension") or "").lower().lstrip(".")
                        kind = raw_type if raw_type in {"video", "audio", "image", "document"} else "material"
                        title = str(attachment.get("name") or attachment.get("title") or "").strip()
                        if not title:
                            title = f"{kind}-{attachment_id}"
                            if extension:
                                title += f".{extension}"
                        resources.append({
                            "external_id": attachment_id,
                            "parent_external_id": external_id,
                            "kind": kind,
                            "title": title,
                            "position": attachment_position,
                            "depth": depth + 1,
                            "status": "unknown",
                            "remote_object_id": _identifier(attachment.get("objectid")) or None,
                            "mime_type": attachment.get("mimeType"),
                            "file_size": attachment.get("size"),
                            "source_url": chapter_url,
                            "metadata": {"extension": extension, "attachment_type": raw_type},
                        })
        return {"chapters": chapters, "resources": resources}

    @staticmethod
    def parse_chapter_card_resources(html: str, *, chapter_id: str,
                                     card_url: str) -> list[dict]:
        match = re.search(r"mArg\s*=\s*(\{.*?\})\s*;", html, re.DOTALL)
        if not match:
            return []
        try:
            payload = json.loads(match.group(1))
        except (ValueError, TypeError):
            return []
        resources: list[dict] = []
        kind_map = {
            "video": "video", "audio": "audio", "document": "document",
            "image": "image", "vote": "quiz", "work": "quiz",
            "test": "quiz", "link": "link", "live": "video",
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
                "metadata": {"extension": extension, "attachment_type": raw_type},
            })
        return resources

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


class ChaoxingClient:
    def __init__(self, cookies: dict | None = None):
        self.client = httpx.AsyncClient(
            cookies=cookies,
            timeout=httpx.Timeout(30.0, connect=10.0),
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.93 Safari/537.36"}
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
            return {"status": cached["status"], "items": list(cached["items"]), "error": cached["error"]}
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
            }
            self._course_chapters_cache[cache_key] = result
            return {"status": result["status"], "items": list(result["items"]), "error": result["error"]}
        except (ValueError, TypeError, AttributeError):
            return {"status": "failed", "items": [], "error": "structure_changed"}
        except httpx.RequestError:
            return {"status": "failed", "items": [], "error": "network_error"}
        except httpx.HTTPStatusError as error:
            return {"status": "failed", "items": [], "error": f"http_error_{error.response.status_code}"}

    async def get_course_materials(self, context: dict) -> dict:
        chapter_result = await self.get_course_chapters(context)
        if chapter_result["status"] != "complete":
            return chapter_result
        kinds = {"document", "video", "audio", "image", "material", "link"}
        resources = [item for item in chapter_result["items"] if item.get("kind") in kinds]
        seen = {(str(item.get("kind")), str(item.get("external_id"))) for item in resources}
        course_id = _identifier(context.get("course_id"))
        clazz_id = _identifier(context.get("clazz_id"), context.get("remote_class_id"))
        cpi = _identifier(context.get("cpi"), context.get("remote_cpi"))
        async def fetch_card(chapter: dict) -> tuple[list[dict], str | None]:
            chapter_id = str(chapter.get("external_id") or "")
            if not chapter_id:
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
                return ChaoxingParser.parse_chapter_card_resources(
                    response.text, chapter_id=chapter_id, card_url=str(response.url)
                ), None
            except httpx.RequestError:
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

    async def get_course_exams(self, context: dict) -> dict:
        # Exams are already present in the authenticated task feed on tenants
        # that expose them. Dedicated exam pages often require signed task IDs;
        # without those IDs an empty result would be misleading.
        return {"status": "unavailable", "items": [], "error": "signed_exam_feed_unavailable"}

    async def get_course_discussions(self, context: dict) -> dict:
        # Discussion feeds vary by tenant and require a course bbs token. Keep
        # the status explicit until the authenticated course response supplies it.
        return {"status": "unavailable", "items": [], "error": "discussion_feed_unavailable"}

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
                    "metadata": {"course_id": course_id, "clazz_id": clazz_id},
                })
            return {"status": "complete", "items": items, "error": None}
        except ChaoxingFetchError as error:
            return {"status": "failed", "items": [], "error": str(error)}

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
            
        except httpx.RequestError as e:
            print(f"An error occurred while requesting {e.request.url!r}.")
            return False, "request_error"
        except httpx.HTTPStatusError as e: 
            print(f"Error response {e.response.status_code} while requesting {e.request.url!r}.")
            return False, f"http_error_{e.response.status_code}"
        except (ValueError, TypeError):
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
        except httpx.RequestError:
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
        except httpx.RequestError as e:
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
        except httpx.RequestError as e:
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
                assignments.append({
                    "title": title_elem.get_text(" ", strip=True),
                    "deadline": deadline_elem.get_text(" ", strip=True) if deadline_elem else "",
                    "external_id": external_id,
                    "status": "completed" if completed else "pending",
                    "remote_status": status_text,
                    "course_id": item_course_id,
                    "clazz_id": item_clazz_id,
                    "link": work_url,
                })
            if use_cache:
                self._assignments_cache = assignments
            return list(assignments)
        except ChaoxingFetchError:
            raise
        except httpx.RequestError as e:
            raise ChaoxingFetchError("network_error") from e
        except httpx.HTTPStatusError as e:
            raise ChaoxingFetchError(f"http_error_{e.response.status_code}") from e

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
        except httpx.RequestError as e:
            raise ChaoxingFetchError("network_error") from e
        except httpx.HTTPStatusError as e:
            raise ChaoxingFetchError(f"http_error_{e.response.status_code}") from e

    async def get_notices(self, course_url: str) -> list[dict]:
        """Compatibility wrapper returning notices belonging to one course."""
        query = urllib.parse.parse_qs(urllib.parse.urlparse(course_url).query)
        course_id = _identifier(*(query.get("courseid") or query.get("courseId") or []))
        notices = await self.get_all_notices()
        return [item for item in notices if item.get("course_id") == course_id]
