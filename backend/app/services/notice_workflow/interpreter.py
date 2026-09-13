import re

from ...models.notice_workflow import InterpretedNotice


_MANUAL_ONLY = re.compile(r"(付款|转账|缴费|密码|验证码|身份证|银行卡)")
_ACTIONABLE = re.compile(r"(提交|填写|报名|参加|完成|办理|截止|作业|考试)")
_DATE = re.compile(r"(20\d{2}[-年/.]\d{1,2}[-月/.]\d{1,2}(?:日)?)")


def interpret_notice(title: str, content: str) -> InterpretedNotice:
    deadline_match = _DATE.search(content)
    actionable = bool(_ACTIONABLE.search(content))
    uncertainty: list[str] = []
    if actionable and deadline_match is None:
        uncertainty.append("DEADLINE_UNCONFIRMED")
    risk = "MANUAL_ONLY" if _MANUAL_ONLY.search(content) else "CONFIRM_REQUIRED" if actionable else "AUTO_SAFE"
    checklist = (title,) if actionable else ()
    return InterpretedNotice(
        facts={"title": title, "actionable": actionable, "deadline_text": deadline_match.group(1) if deadline_match else None},
        uncertainty_codes=tuple(uncertainty),
        checklist=checklist,
        action_risk=risk,
    )
