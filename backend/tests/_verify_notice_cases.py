"""通知抽取验收脚本 — 10 个真实测试用例。

运行: python -m tests._verify_notice_cases
"""
from __future__ import annotations

import json
import sys
import urllib.request


BASE = "http://127.0.0.1:8000"


CASES = [
    {
        "name": "case1_社会实践申请",
        "text": "请2024级计算机科学与技术专业学生于7月30日前填写社会实践申请表，"
                "并将申请表、实践计划书和指导教师确认表提交至信息楼305办公室。",
        "expect": {
            "deadline": True,
            "needs_confirmation": True,  # 缺年份
            "materials_min": 3,
            "location_contains": "信息楼305",
            "audience_contains": "2024",
        },
    },
    {
        "name": "case2_综合测评",
        "text": "各班班长请于2026年8月3日18:00前将综合测评汇总表上传至学生工作平台。",
        "expect": {
            "deadline": True,
            "needs_confirmation_any": True,
            "audience_contains": "班长",
            "method_contains": "学生工作平台",
        },
    },
    {
        "name": "case3_相对时间",
        "text": "软件工程1班和软件工程2班学生请在本周五前完成问卷。",
        "expect": {
            "deadline_any": True,
            "needs_confirmation": True,  # 相对时间需确认
        },
    },
    {
        "name": "case4_无截止时间",
        "text": "奖学金申请材料包括申请表、成绩单、获奖证明及家庭经济情况说明。",
        "expect": {
            "no_deadline": True,
            "materials_min": 4,
            "needs_confirmation": True,
        },
    },
    {
        "name": "case5_明确无截止",
        "text": "本通知未说明截止时间。",
        "expect": {
            "no_deadline": True,
            "needs_confirmation": True,
        },
    },
    {
        "name": "case6_非通知聊天",
        "text": "今天天气不错，我们去打球吧。",
        "expect": {
            "http_status_4xx": True,  # 422/400 均可,关键是不能 500
            "code_contains": "NOTICE_UNPARSEABLE",
        },
    },
    {
        "name": "case7_空文本",
        "text": "",
        "expect": {
            "http_status_4xx": True,  # 400/422 均可,关键是不能 500
            "code_contains": "NOTICE_EMPTY",
        },
    },
    {
        "name": "case8_多日期超长",
        "text": "请各位同学尽快完成本学期期末教学评价。请于2026年8月3日18:00前完成。"
                "请于2026年8月5日12:00前完成宿舍登记。请于2026年8月10日前完成课程补退选申请。"
                "请将以上材料提交至学院办公室。请认真对待，逾期不予受理。",
        "expect": {
            "deadline": True,
            "importance": "urgent",
        },
    },
    {
        "name": "case9_开始与截止",
        "text": "社会实践报名开始时间为2026年7月15日，报名截止时间为2026年7月30日。",
        "expect": {
            "deadline": True,
            "deadline_is": "2026-07-30",  # 必须取截止时间，不是开始时间
        },
    },
    {
        "name": "case10_完整通知",
        "text": "请2026级软件工程专业1班学生于2026年7月30日17:00前，"
                "将奖学金申请表、成绩单原件及复印件、获奖证明复印件、家庭经济情况说明、"
                "身份证复印件提交至行政楼301办公室。逾期不予受理。",
        "expect": {
            "deadline": True,
            "needs_confirmation": False,
            "materials_min": 5,
            "location_contains": "行政楼301",
            "audience_contains": "2026",
            "importance": "urgent",
        },
    },
]


def call_api(text: str) -> tuple[int, dict]:
    """调用通知抽取接口，返回 (http_status, body)。失败 body 含 error 字段。"""
    payload = json.dumps({"content": text}, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        f"{BASE}/api/v1/notices/extract",
        data=payload,
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8")
        try:
            return e.code, json.loads(body)
        except json.JSONDecodeError:
            return e.code, {"_raw": body}


def verify(case: dict) -> tuple[bool, list[str]]:
    """运行用例并验证期望。返回 (通过, 失败原因列表)。"""
    name = case["name"]
    text = case["text"]
    expect = case.get("expect", {})
    status, body = call_api(text)
    failures: list[str] = []

    if "http_status" in expect:
        if status != expect["http_status"]:
            failures.append(f"http_status 期望 {expect['http_status']} 实际 {status}")
        return (not failures, failures)

    if "http_status_4xx" in expect:
        if not (400 <= status < 500):
            failures.append(f"http_status 期望 4xx 实际 {status}")
        code = body.get("code", "")
        if "code_contains" in expect and expect["code_contains"] not in code:
            failures.append(f"code 期望含 '{expect['code_contains']}' 实际 '{code}'")
        return (not failures, failures)

    if status != 200:
        failures.append(f"http_status 期望 200 实际 {status} body={body}")
        return (not failures, failures)

    # 字段检查
    deadline = body.get("deadline")
    if expect.get("deadline") and not deadline:
        failures.append(f"deadline 期望非空 实际 {deadline}")
    if expect.get("no_deadline") and deadline:
        failures.append(f"deadline 期望空 实际 {deadline}")
    if expect.get("deadline_any") and not deadline:
        failures.append(f"deadline 期望非空(相对时间) 实际 {deadline}")
    if expect.get("deadline_is") and deadline:
        if not deadline.startswith(expect["deadline_is"]):
            failures.append(
                f"deadline 期望 {expect['deadline_is']} 实际 {deadline}"
            )

    nc = body.get("needs_confirmation")
    if "needs_confirmation" in expect and nc != expect["needs_confirmation"]:
        failures.append(f"needs_confirmation 期望 {expect['needs_confirmation']} 实际 {nc}")
    if expect.get("needs_confirmation_any") and nc is not True:
        failures.append(f"needs_confirmation 期望 True 实际 {nc}")

    materials = body.get("materials") or []
    if "materials_min" in expect and len(materials) < expect["materials_min"]:
        failures.append(
            f"materials 数量期望 >= {expect['materials_min']} 实际 {len(materials)}: "
            f"{[m.get('name') for m in materials]}"
        )

    location = body.get("location") or ""
    if "location_contains" in expect and expect["location_contains"] not in location:
        failures.append(
            f"location 期望含 '{expect['location_contains']}' 实际 '{location}'"
        )

    audience = body.get("target_students") or ""
    if "audience_contains" in expect and expect["audience_contains"] not in audience:
        failures.append(
            f"audience 期望含 '{expect['audience_contains']}' 实际 '{audience}'"
        )

    method = body.get("submission_method") or ""
    if "method_contains" in expect and expect["method_contains"] not in method:
        failures.append(
            f"method 期望含 '{expect['method_contains']}' 实际 '{method}'"
        )

    importance = body.get("importance")
    if "importance" in expect and importance != expect["importance"]:
        failures.append(f"importance 期望 {expect['importance']} 实际 {importance}")

    return (not failures, failures)


def main() -> int:
    print(f"\n=== 通知抽取验收: {len(CASES)} 个用例 ===\n")
    all_pass = True
    for case in CASES:
        name = case["name"]
        text = case["text"]
        status, body = call_api(text)
        ok, failures = verify(case)

        # 打印紧凑结果
        if status == 200:
            mats = [m.get("name") for m in (body.get("materials") or [])]
            print(f"[{'PASS' if ok else 'FAIL'}] {name}")
            print(f"  status={status}")
            print(f"  text={text[:60]}{'...' if len(text) > 60 else ''}")
            print(f"  title={body.get('title')}")
            print(f"  audience={body.get('target_students')}")
            print(f"  deadline={body.get('deadline')}")
            print(f"  needs_confirmation={body.get('needs_confirmation')}")
            print(f"  materials({len(mats)})={mats}")
            print(f"  location={body.get('location')}")
            print(f"  method={body.get('submission_method')}")
            print(f"  importance={body.get('importance')} confidence={body.get('confidence')}")
            print(f"  mode={body.get('extractor_mode')}")
            warnings = body.get("warnings") or []
            if warnings:
                print(f"  warnings={warnings}")
        else:
            print(f"[{'PASS' if ok else 'FAIL'}] {name}")
            print(f"  status={status} (expected non-200)")
            print(f"  body={body}")
        if failures:
            for f in failures:
                print(f"  FAILURE: {f}")
            all_pass = False
        print()

    print("=== 总结 ===")
    if all_pass:
        print("ALL PASS")
        return 0
    print("SOME FAILED")
    return 1


if __name__ == "__main__":
    sys.exit(main())
