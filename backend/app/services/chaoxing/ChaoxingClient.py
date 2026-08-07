from __future__ import annotations

import httpx
import re
import urllib.parse
from bs4 import BeautifulSoup

class ChaoxingParser:
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
                clazz_id = match.group(1) if match else (match.group(2) if match and match.group(2) else "")

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
            verify_url = "http://mooc2-ans.chaoxing.com/visit/courses/list"
            verify_res = await self.client.get(verify_url, follow_redirects=False)
            if verify_res.status_code == 302 or verify_res.status_code == 403:
                return False, "Session verification failed after login"
            
            return True, "success"
            
        except httpx.RequestError as e:
            print(f"An error occurred while requesting {e.request.url!r}.")
            return False, "request_error"
        except httpx.HTTPStatusError as e: 
            print(f"Error response {e.response.status_code} while requesting {e.request.url!r}.")
            return False, f"http_error_{e.response.status_code}"


    async def get_courses(self) -> tuple[bool, list | str]:
        """获取课程列表。
        返回 (是否成功, 课程列表或错误信息)
        """
        # Try JSON API first
        api_url = "https://mooc1-api.chaoxing.com/mycourse/backclazzdata"
        try:
            res = await self.client.get(api_url, follow_redirects=False)
            if res.status_code == 200:
                try:
                    data = res.json()
                    if isinstance(data, dict):
                        if data.get("result") == 0 and "登录" in str(data.get("msg", "")):
                            return False, "reauth_required"
                        # Try to extract courses from JSON
                        courses = []
                        channel_list = data.get("channelList", [])
                        for channel in channel_list:
                            content = channel.get("content", {})
                            course_info = content.get("course", {})
                            data_info = course_info.get("data", [])
                            for item in data_info:
                                course_id = str(item.get("id", ""))
                                course_name = item.get("name", "")
                                # Check if clazzid is available somewhere, or use course_id as fallback external_id
                                clazz_id = str(item.get("clazzId", "")) # Need actual key if available
                                external_id = f"{course_id}_{clazz_id}" if course_id and clazz_id else course_id or clazz_id
                                if course_name and external_id:
                                    link = f"https://mooc2-ans.chaoxing.com/mycourse/stu?courseid={course_id}&clazzid={clazz_id}"
                                    courses.append({
                                        "name": course_name,
                                        "link": link,
                                        "course_id": course_id,
                                        "clazz_id": clazz_id,
                                        "external_id": external_id
                                    })
                        if courses:
                            return True, courses
                except Exception:
                    pass
            elif res.status_code in (302, 403):
                return False, "reauth_required"
        except httpx.RequestError:
            pass
            
        # Fallback to HTML parsing if JSON API fails or returns no data
        courses_url = "http://mooc2-ans.chaoxing.com/visit/courses/list"
        try:
            # First verify session validity
            response = await self.client.get(courses_url, follow_redirects=False)
            if response.status_code in (302, 403):
                return False, "reauth_required"
            response.raise_for_status()
            
            # If the response contains login keywords, session might be invalid even with 200 OK
            if "用户登录" in response.text or "请登录" in response.text:
                return False, "reauth_required"
                
            courses = ChaoxingParser.parse_courses_html(response.text)
            return True, courses
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
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "lxml")

            course_id = soup.find("input", {"name": "courseid"})["value"]
            class_id = soup.find("input", {"name": "clazzid"})["value"]

            work_url_base = soup.find("a", {"title": "作业"})["data-url"]
            work_enc = soup.find("input", {"name": "workEnc"})["value"]

            assignments_url = f"{work_url_base}?courseId={course_id}&classId={class_id}&enc={work_enc}"

            response = await self.client.get(assignments_url)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "lxml")

            assignments = []
            for item in soup.select(".work-item"):
                title = item.select_one(".work-title").text.strip()
                deadline = item.select_one(".work-deadline").text.strip()
                assignments.append({"title": title, "deadline": deadline})

            return {"assignments": assignments, "notices": []}
        except (httpx.RequestError, httpx.HTTPStatusError) as e:
            print(f"Error while fetching assignments and notices: {e}")
            return {"assignments": [], "notices": []}
