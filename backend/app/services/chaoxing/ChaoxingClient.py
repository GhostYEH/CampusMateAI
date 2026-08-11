from __future__ import annotations

import httpx
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
                courses.append({
                    "name": course_name,
                    "link": (
                        "https://mooc2-ans.chaoxing.com/mycourse/stu"
                        f"?courseid={course_id}&clazzid={clazz_id}"
                    ),
                    "course_id": course_id,
                    "clazz_id": clazz_id,
                    "external_id": external_id,
                })
        return courses

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
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.93 Safari/537.36"}
        )

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
            response = await self.client.get(course_url)
            auth_error = _auth_error(response)
            if auth_error:
                raise ChaoxingFetchError(auth_error)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "lxml")

            query = urllib.parse.parse_qs(urllib.parse.urlparse(course_url).query)
            course_elem = soup.find("input", {"name": "courseid"}) or soup.find("input", {"id": "courseId"})
            class_elem = soup.find("input", {"name": "clazzid"}) or soup.find("input", {"id": "classId"})
            course_id = _identifier(course_elem.get("value") if course_elem else None, *(query.get("courseid") or query.get("courseId") or []))
            class_id = _identifier(class_elem.get("value") if class_elem else None, *(query.get("clazzid") or query.get("classId") or []))

            work_link = soup.find("a", {"title": "作业"})
            work_enc_elem = soup.find("input", {"name": "workEnc"})
            if not course_id or not class_id or not work_link or not work_link.get("data-url"):
                raise ChaoxingFetchError("structure_changed")
            work_url_base = urllib.parse.urljoin(course_url, work_link["data-url"])
            work_enc = _identifier(work_enc_elem.get("value") if work_enc_elem else None)

            parsed_work_url = urllib.parse.urlparse(work_url_base)
            work_query = urllib.parse.parse_qs(parsed_work_url.query)
            work_query.update({"courseId": [course_id], "classId": [class_id]})
            if work_enc:
                work_query["enc"] = [work_enc]
            assignments_url = urllib.parse.urlunparse(parsed_work_url._replace(query=urllib.parse.urlencode(work_query, doseq=True)))

            response = await self.client.get(assignments_url)
            auth_error = _auth_error(response)
            if auth_error:
                raise ChaoxingFetchError(auth_error)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "lxml")

            assignments = []
            for item in soup.select(".work-item, li, tr"):
                title_elem = item.select_one(".work-title, .title, h3, .name")
                if not title_elem:
                    continue
                title = title_elem.text.strip()

                deadline_elem = item.select_one(".work-deadline, .deadline, .time")
                deadline = deadline_elem.text.strip() if deadline_elem else ""

                # Extract external_id
                external_id = item.get("data-workid") or item.get("data-jobid") or item.get("data-id") or item.get("id")
                
                link_elem = item.select_one("a")
                link = link_elem["href"] if link_elem and link_elem.has_attr("href") else ""
                
                if not external_id and link:
                    match = re.search(r'(?:workId|jobId|taskId|assignmentId|id)=([A-Za-z0-9_-]+)', link, re.IGNORECASE)
                    if match:
                        external_id = match.group(1)

                if not external_id and item.get("onclick"):
                    match = re.search(r'(?:workId|jobId|taskId|assignmentId|id)=([A-Za-z0-9_-]+)', item.get("onclick"), re.IGNORECASE)
                    if match:
                        external_id = match.group(1)
                
                if not external_id:
                    input_id = item.select_one("input[name='workId'], input[name='jobId'], input[name='taskId']")
                    if input_id:
                        external_id = input_id.get("value")

                if not external_id:
                    continue # Do not use title+deadline

                status_text = ""
                status_elem = item.select_one(".status, .state, .work-status, .type, .sub-status")
                if status_elem:
                    status_text = status_elem.text.strip()
                elif item.select_one(".btn-submit, .submit-btn"):
                    status_text = "未交"
                
                status = "pending"
                if any(x in status_text for x in ["未交", "未完成", "未提交", "待完成"]):
                    status = "pending"
                elif any(x in status_text for x in ["已交", "已完成", "已提交", "已批阅", "待批阅"]):
                    status = "completed"

                if link and link.startswith("/"):
                    link = "https://mooc2-ans.chaoxing.com" + link

                assignments.append({
                    "title": title,
                    "deadline": deadline,
                    "external_id": external_id,
                    "status": status,
                    "link": link
                })

            return {"assignments": assignments, "notices": []}
        except ChaoxingFetchError:
            raise
        except httpx.RequestError as e:
            raise ChaoxingFetchError("network_error") from e
        except httpx.HTTPStatusError as e:
            raise ChaoxingFetchError(f"http_error_{e.response.status_code}") from e

    async def get_notices(self, course_url: str) -> list[dict]:
        """获取课程通知。"""
        try:
            # 1. 访问课程页提取 courseid 和 classid
            response = await self.client.get(course_url)
            auth_error = _auth_error(response)
            if auth_error:
                raise ChaoxingFetchError(auth_error)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "lxml")
            
            course_id_elem = soup.find("input", {"name": "courseid"}) or soup.find("input", {"id": "courseId"})
            class_id_elem = soup.find("input", {"name": "clazzid"}) or soup.find("input", {"id": "classId"})
            
            query = urllib.parse.parse_qs(urllib.parse.urlparse(course_url).query)
            course_id = _identifier(course_id_elem.get("value") if course_id_elem else None, *(query.get("courseid") or query.get("courseId") or []))
            class_id = _identifier(class_id_elem.get("value") if class_id_elem else None, *(query.get("clazzid") or query.get("classId") or []))
            if not course_id or not class_id:
                raise ChaoxingFetchError("structure_changed")

            # 2. 访问通知列表接口 (尝试找 stable API，回退到 HTML 解析)
            # 根据经验，学习通的通知接口通常是 /notice/getNoticeList?courseId=xxx&classId=xxx 等
            # 由于题目要求优先稳定接口，这里假设用 HTML 回退的方式处理
            
            notice_url = f"https://mooc1.chaoxing.com/notice/getNoticeList?courseId={course_id}&classId={class_id}"
            notice_resp = await self.client.get(notice_url)
            auth_error = _auth_error(notice_resp)
            if auth_error:
                raise ChaoxingFetchError(auth_error)
            notice_resp.raise_for_status()
            
            notices = []
            
            # 尝试 JSON
            try:
                data = notice_resp.json()
                notice_list = data.get("list") or (data.get("data") or {}).get("list")
                if notice_list is not None:
                    for item in notice_list:
                        nid = item.get("id") or item.get("noticeId")
                        if not nid:
                            continue
                        notices.append({
                            "external_id": str(nid),
                            "title": item.get("title", "无标题"),
                            "content": item.get("content", ""),
                            "published_at": item.get("insertTime") or item.get("publishTime"),
                            "link": f"https://mooc1.chaoxing.com/notice/noticeDetail?noticeId={nid}&courseId={course_id}&classId={class_id}"
                        })
                    return notices
            except Exception:
                pass
                
            # fallback: HTML 提取
            notice_soup = BeautifulSoup(notice_resp.text, "lxml")
            for item in notice_soup.select(".notice-item, .noticeList li, tr"):
                title_elem = item.select_one(".title, .name, h3, a")
                if not title_elem:
                    continue
                title = title_elem.text.strip()
                
                content_elem = item.select_one(".content, .summary, p")
                content = content_elem.text.strip() if content_elem else ""
                
                time_elem = item.select_one(".time, .date")
                published_at = time_elem.text.strip() if time_elem else ""
                
                link_elem = item.select_one("a")
                link = link_elem["href"] if link_elem and link_elem.has_attr("href") else ""
                
                external_id = item.get("data-noticeid") or item.get("data-id") or item.get("id")
                
                if not external_id and link:
                    import re
                    match = re.search(r'(?:noticeId|id|announcementId)=(\d+)', link, re.IGNORECASE)
                    if match:
                        external_id = match.group(1)
                
                if not external_id:
                    input_id = item.select_one("input[name='noticeId'], input[name='id']")
                    if input_id:
                        external_id = input_id.get("value")
                        
                if not external_id:
                    continue
                    
                if link and link.startswith("/"):
                    link = "https://mooc1.chaoxing.com" + link
                    
                notices.append({
                    "external_id": str(external_id),
                    "title": title,
                    "content": content,
                    "published_at": published_at,
                    "link": link
                })
                
            return notices
        except ChaoxingFetchError:
            raise
        except httpx.RequestError as e:
            raise ChaoxingFetchError("network_error") from e
        except httpx.HTTPStatusError as e:
            raise ChaoxingFetchError(f"http_error_{e.response.status_code}") from e
