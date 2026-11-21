"""共同课堂专注监督的老师话术与阈值常量。

端侧只上报粗粒度状态（专注、可能分心、明显分心、暂离、未知），不传画面、
人脸或逐帧结果。服务端在这里把“持续异常”翻译成老师口吻的提醒；所有文案
都是规则生成，不调用模型，也不从状态推断心理或学习效果。
"""

from __future__ import annotations

ATTENTION_STATES = (
    "FOCUSED",
    "POSSIBLY_DISTRACTED",
    "DISTRACTED",
    "AWAY",
    "UNKNOWN",
)
ATTENTION_SOURCES = ("ON_DEVICE", "PAGE_VISIBILITY", "HEARTBEAT")
BAD_ATTENTION_STATES = ("POSSIBLY_DISTRACTED", "DISTRACTED", "AWAY")

# 超过这个时间没有新上报，就视为“状态未知/可能离线”，而不是继续展示旧状态。
ATTENTION_STALE_AFTER_SECONDS = 45
# 状态持续多久后，老师才自动发一句提醒。避免一次误判就打断同学。
AUTO_NUDGE_THRESHOLDS_SECONDS = {
    "POSSIBLY_DISTRACTED": 60,
    "DISTRACTED": 30,
    "AWAY": 45,
}
# 同一个同学两次自动提醒之间至少间隔 4 分钟，且每次课堂最多 4 次。
AUTO_NUDGE_COOLDOWN_SECONDS = 240
AUTO_NUDGE_MAX_PER_MEMBER = 4
TEACHER_NAME = "小伴老师"
ATTENTION_LABELS = {
    "FOCUSED": "专注听课",
    "POSSIBLY_DISTRACTED": "可能分心",
    "DISTRACTED": "明显分心",
    "AWAY": "暂时离开",
    "UNKNOWN": "状态未知",
}

_TEACHER_TEXTS = {
    "POSSIBLY_DISTRACTED": (
        "同学，老师看到你的视线离开课件了。先把这一页看完，我们继续。",
        "这一页还没讲完，别急着切走；跟着老师的节奏来。",
        "注意力有点像风筝了，老师帮你拉回来：看回课件这一行。",
    ),
    "DISTRACTED": (
        "同学，老师看到你分心了。课堂还在继续，把注意力放回这一页。",
        "老师注意到你分心了。深呼吸一下，现在把注意力放回课堂。",
        "已经提醒过一次了，老师相信你能回到听课状态。先看课件，再做别的。",
    ),
    "AWAY": (
        "你暂时离开了课堂。回到课堂页面后，老师给你留着进度。",
        "老师看不到你了。如果在，请回到课堂页面；如果不在，记得先暂停。",
        "离开太久会跟不上，回到课堂页面跟老师继续。",
    ),
    "UNKNOWN": (
        "老师暂时看不到你的课堂状态。检查一下网络和课堂观察开关。",
    ),
}

_BROADCAST_TEXT = "同学们，跟老师一起看这一页，专注听完再讨论。"
_RECOVERY_TEXT = "很好，老师看到你回到课堂了，继续保持。"


def is_attention_state(value: str) -> bool:
    return value in ATTENTION_STATES


def attention_label(state: str) -> str:
    return ATTENTION_LABELS.get(state, "状态未知")


def teacher_nudge_text(state: str, occurrence: int = 1) -> str:
    """同一状态重复发生时逐步换成更明确的老师口吻，不新增随机性。"""
    texts = _TEACHER_TEXTS.get(state)
    if not texts:
        return _BROADCAST_TEXT
    index = min(max(occurrence, 1), len(texts)) - 1
    return texts[index]


def host_nudge_text(state: str, name: str = "") -> str:
    """发起人没有自填内容时，按被提醒同学的状态给一句默认老师提醒。"""
    prefix = f"{name}，老师提醒你：" if name else "老师提醒你："
    if state == "AWAY":
        return prefix + "回到课堂页面后，我们等你。"
    if state in ("DISTRACTED", "POSSIBLY_DISTRACTED"):
        return prefix + "把注意力回到课件上，跟着这一页继续听。"
    return prefix + "课堂还在继续，跟着老师看这一页。"


def broadcast_nudge_text() -> str:
    return _BROADCAST_TEXT


def recovery_text() -> str:
    return _RECOVERY_TEXT


__all__ = [
    "ATTENTION_STATES",
    "ATTENTION_SOURCES",
    "BAD_ATTENTION_STATES",
    "ATTENTION_STALE_AFTER_SECONDS",
    "AUTO_NUDGE_THRESHOLDS_SECONDS",
    "AUTO_NUDGE_COOLDOWN_SECONDS",
    "AUTO_NUDGE_MAX_PER_MEMBER",
    "TEACHER_NAME",
    "ATTENTION_LABELS",
    "is_attention_state",
    "attention_label",
    "teacher_nudge_text",
    "host_nudge_text",
    "broadcast_nudge_text",
    "recovery_text",
]
