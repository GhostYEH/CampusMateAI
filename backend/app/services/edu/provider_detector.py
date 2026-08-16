"""ProviderDetector — 教务系统厂商识别器。

多维度识别 ZHENGFANG / QIANGZHI / QINGGUO / URP / NEW_URP / SHUWEI / CUSTOM / UNKNOWN，
不仅依靠 URL 子串单一判断。每条识别结果附带 evidence 列表。

识别维度（按权重）：
1. HTML <title> 关键词（强信号）
2. HTML <meta generator/copyright/author>（强信号）
3. HTML <script src> / <link href> 路径特征（中信号）
4. HTML <form action> 路径特征（中信号）
5. HTML 正文版权/厂商名称（中信号）
6. URL 路径子串（弱信号，单独不足以定论）
7. HTTP header Server/X-Powered-By（弱信号）
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional
from urllib.parse import urlparse

from .discovery_constants import (
    PROVIDER_ZHENGFANG,
    PROVIDER_QIANGZHI,
    PROVIDER_QINGGUO,
    PROVIDER_URP,
    PROVIDER_NEW_URP,
    PROVIDER_SHUWEI,
    PROVIDER_CUSTOM,
    PROVIDER_UNKNOWN,
)


@dataclass
class ProviderEvidence:
    """单条识别证据。"""
    dimension: str        # title / meta / script / form / body / url / header
    provider: str
    pattern: str
    matched: str          # 实际匹配到的片段（截断）
    weight: float


@dataclass
class ProviderDetectResult:
    """ProviderDetector 识别结果。"""
    provider: str = PROVIDER_UNKNOWN
    confidence: float = 0.0
    evidence: list[ProviderEvidence] = field(default_factory=list)
    title: Optional[str] = None
    copyright_text: Optional[str] = None
    generator: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "provider": self.provider,
            "confidence": round(self.confidence, 4),
            "evidence": [
                {
                    "dimension": e.dimension,
                    "provider": e.provider,
                    "pattern": e.pattern,
                    "matched": e.matched[:200],
                    "weight": e.weight,
                }
                for e in self.evidence
            ],
            "title": self.title,
            "copyright_text": self.copyright_text,
            "generator": self.generator,
        }


# ===== 各 Provider 指纹规则 =====
# 每条规则: (pattern_regex, weight)
# weight 含义: 命中后累加，最终 confidence = min(sum, 1.0)

PROVIDER_RULES: dict[str, dict[str, list[tuple[str, float]]]] = {
    PROVIDER_ZHENGFANG: {
        # 正方教务管理系统
        "title": [
            (r"正方教务", 0.45),
            (r"正方现代教务", 0.5),
            (r"正方软件", 0.4),
            (r"学生成绩查询系统", 0.25),
            (r"正方.*?教务", 0.4),
        ],
        "meta": [
            (r"正方软件股份有限公司", 0.5),
            (r"正方软件", 0.35),
            (r"ZFSoft", 0.4),
            (r"zfsoft", 0.4),
        ],
        "script": [
            (r"/jwglxt/", 0.3),
            (r"/jsxsd/", 0.3),
            (r"jwglxt", 0.25),
            (r"jsxsd", 0.25),
            (r"/newton/", 0.25),
            (r"newtonsoft", 0.15),
        ],
        "form": [
            (r"/jwglxt/xtgl/login", 0.4),
            (r"/jsxsd/sso/login", 0.35),
            (r"/xtgl/login_slogin", 0.4),
            (r"login\.jsp", 0.15),
        ],
        "body": [
            (r"正方软件股份有限公司", 0.4),
            (r"正方教务管理系统", 0.4),
            (r"Copyright.*?正方", 0.4),
        ],
        "url": [
            (r"/jwglxt/", 0.2),
            (r"/jsxsd/", 0.2),
            (r"/xtgl/", 0.2),
            (r"/newton/", 0.15),
        ],
        "header": [
            (r"ZFSoft", 0.3),
        ],
    },
    PROVIDER_QIANGZHI: {
        # 湖南强智科技
        "title": [
            (r"强智教务", 0.45),
            (r"强智科技", 0.4),
            (r"教务一体化系统", 0.3),
            (r"强智.*?教务", 0.4),
        ],
        "meta": [
            (r"湖南强智", 0.5),
            (r"强智科技", 0.4),
            (r"qzsoft", 0.35),
        ],
        "script": [
            (r"/qzsoft/", 0.3),
            (r"qzsoft", 0.25),
            (r"run\.js", 0.15),
            (r"/jsxsd/", 0.15),  # 强智也用 jsxsd，弱信号
        ],
        "form": [
            (r"/loginRun\.do", 0.4),
            (r"/verifycode\.do", 0.35),
            (r"/xjltuRun\.do", 0.3),
        ],
        "body": [
            (r"湖南强智", 0.45),
            (r"强智科技", 0.35),
            (r"Copyright.*?强智", 0.4),
        ],
        "url": [
            (r"/qzsoft/", 0.2),
            (r"/loginRun\.do", 0.2),
        ],
        "header": [],
    },
    PROVIDER_QINGGUO: {
        # 青果网络 / 金智 Kingosoft（同源）
        "title": [
            (r"青果教务", 0.45),
            (r"青果科技", 0.4),
            (r"金智教务", 0.4),
            (r"Kingosoft", 0.4),
            (r"青果.*?教务", 0.4),
        ],
        "meta": [
            (r"KINGOSOFT", 0.5),
            (r"kingosoft", 0.45),
            (r"青果网络", 0.45),
            (r"金智教育", 0.4),
        ],
        "script": [
            (r"kingosoft", 0.3),
            (r"qingguo", 0.25),
            (r"/cas/", 0.15),
        ],
        "form": [
            (r"/cas/login\.action", 0.4),
            (r"cas/login", 0.25),
            (r"/jwweb/", 0.3),
        ],
        "body": [
            (r"青果网络", 0.4),
            (r"金智教育科技", 0.4),
            (r"Copyright.*?Kingosoft", 0.4),
            (r"Copyright.*?青果", 0.4),
        ],
        "url": [
            (r"/cas/", 0.15),
            (r"/jwweb/", 0.2),
            (r"kingosoft", 0.2),
        ],
        "header": [],
    },
    PROVIDER_URP: {
        # URP 综合教务（旧版，JSP）
        "title": [
            (r"URP综合教务", 0.45),
            (r"URP教务", 0.4),
            (r"URP综合教务管理系统", 0.5),
        ],
        "meta": [
            (r"URP", 0.25),
        ],
        "script": [
            (r"/urp/", 0.25),
            (r"urp", 0.15),
        ],
        "form": [
            (r"/urp/", 0.3),
            (r"/login\.jsp", 0.15),
        ],
        "body": [
            (r"URP综合教务", 0.4),
            (r"Copyright.*?URP", 0.3),
        ],
        "url": [
            (r"/urp/", 0.2),
        ],
        "header": [],
    },
    PROVIDER_NEW_URP: {
        # 新版 URP（SpringBoot / 前后端分离）
        "title": [
            (r"新URP", 0.45),
            (r"NewURP", 0.45),
            (r"新版URP", 0.45),
        ],
        "meta": [],
        "script": [
            (r"/newurp/", 0.3),
            (r"new-urp", 0.25),
            (r"/urp/.*?api", 0.2),
        ],
        "form": [
            (r"/newurp/", 0.3),
        ],
        "body": [
            (r"新.*?URP", 0.3),
        ],
        "url": [
            (r"/newurp/", 0.2),
            (r"new-urp", 0.2),
        ],
        "header": [],
    },
    PROVIDER_SHUWEI: {
        # 厦门树维信息科技
        "title": [
            (r"树维", 0.45),
            (r"树维信息", 0.4),
        ],
        "meta": [
            (r"树维", 0.4),
            (r"shuwei", 0.35),
        ],
        "script": [
            (r"shuwei", 0.25),
            (r"/sw/", 0.15),
        ],
        "form": [],
        "body": [
            (r"厦门树维", 0.45),
            (r"树维信息科技", 0.4),
            (r"Copyright.*?树维", 0.4),
        ],
        "url": [
            (r"shuwei", 0.2),
        ],
        "header": [],
    },
}


# 通用教务关键词（用于判断是否为教务系统页面，不区分 Provider）
EDU_SYSTEM_KEYWORDS = [
    "教务", "教务系统", "教务管理", "课表", "成绩", "选课", "排课",
    "学生登录", "教师登录", "教务处", "jwxt", "jwgl", "jwc",
    "academic", "jwglxt", "jsxsd",
]


def _extract_title(html: str) -> Optional[str]:
    m = re.search(r"<title[^>]*>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
    if m:
        return re.sub(r"\s+", " ", m.group(1).strip())[:200]
    return None


def _extract_meta(html: str, name: str) -> Optional[str]:
    """提取 <meta name=... content=...> 或 <meta property=... content=...>。"""
    pattern = (
        rf'<meta[^>]+(?:name|property)=["\']?{re.escape(name)}["\']?[^>]*'
        rf'content=["\']?([^"\'>]+)["\']?[^>]*>'
    )
    m = re.search(pattern, html, re.IGNORECASE)
    if m:
        return m.group(1).strip()[:300]
    # 反过来顺序
    pattern2 = (
        rf'<meta[^>]+content=["\']?([^"\'>]+)["\']?[^>]*'
        rf'(?:name|property)=["\']?{re.escape(name)}["\']?[^>]*>'
    )
    m2 = re.search(pattern2, html, re.IGNORECASE)
    if m2:
        return m2.group(1).strip()[:300]
    return None


def _extract_copyright(html: str) -> Optional[str]:
    """提取页面版权声明。"""
    patterns = [
        r"Copyright[^<]{0,200}",
        r"©[^<]{0,200}",
        r"版权所有[^<]{0,100}",
        r"技术支持[^<]{0,100}",
        r"Powered by[^<]{0,100}",
    ]
    for p in patterns:
        m = re.search(p, html, re.IGNORECASE)
        if m:
            return re.sub(r"\s+", " ", m.group(0).strip())[:200]
    return None


def _extract_scripts(html: str) -> str:
    """提取所有 <script src=...> 和 <link href=...> 拼成字符串。"""
    parts = []
    for m in re.finditer(r'<script[^>]+src=["\']?([^"\'>\s]+)', html, re.IGNORECASE):
        parts.append(m.group(1))
    for m in re.finditer(r'<link[^>]+href=["\']?([^"\'>\s]+)', html, re.IGNORECASE):
        parts.append(m.group(1))
    return " ".join(parts)


def _extract_forms(html: str) -> str:
    """提取所有 <form action=...> 拼成字符串。"""
    parts = []
    for m in re.finditer(r'<form[^>]+action=["\']?([^"\'>\s]+)', html, re.IGNORECASE):
        parts.append(m.group(1))
    return " ".join(parts)


def _match_rules(
    text: str,
    rules: list[tuple[str, float]],
    provider: str,
    dimension: str,
) -> list[ProviderEvidence]:
    evidence = []
    for pattern, weight in rules:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            evidence.append(ProviderEvidence(
                dimension=dimension,
                provider=provider,
                pattern=pattern,
                matched=m.group(0)[:120],
                weight=weight,
            ))
    return evidence


class ProviderDetector:
    """教务系统厂商识别器。"""

    def detect(
        self,
        *,
        url: str = "",
        html: str = "",
        headers: Optional[dict] = None,
    ) -> ProviderDetectResult:
        """综合 URL + HTML + headers 识别 Provider。

        Args:
            url: 候选 URL（用于 URL 路径弱信号）
            html: HTTP 响应 HTML 正文（用于 title/meta/script/form/body 强信号）
            headers: HTTP 响应头（用于 Server/X-Powered-By 弱信号）

        Returns:
            ProviderDetectResult，含 provider / confidence / evidence 列表。
        """
        result = ProviderDetectResult()
        all_evidence: list[ProviderEvidence] = []
        scores: dict[str, float] = {}

        if html:
            result.title = _extract_title(html)
            result.copyright_text = _extract_copyright(html)
            result.generator = _extract_meta(html, "generator") or _extract_meta(html, "author")

        for provider, dims in PROVIDER_RULES.items():
            score = 0.0

            # title 维度
            if result.title and dims.get("title"):
                ev = _match_rules(result.title, dims["title"], provider, "title")
                all_evidence.extend(ev)
                score += sum(e.weight for e in ev)

            # meta 维度（generator + copyright + 其他 meta）
            meta_text = " ".join(filter(None, [
                result.generator,
                _extract_meta(html, "description") if html else None,
                _extract_meta(html, "keywords") if html else None,
            ]))
            if meta_text and dims.get("meta"):
                ev = _match_rules(meta_text, dims["meta"], provider, "meta")
                all_evidence.extend(ev)
                score += sum(e.weight for e in ev)

            # script/link 维度
            if html and dims.get("script"):
                scripts = _extract_scripts(html)
                if scripts:
                    ev = _match_rules(scripts, dims["script"], provider, "script")
                    all_evidence.extend(ev)
                    score += sum(e.weight for e in ev)

            # form action 维度
            if html and dims.get("form"):
                forms = _extract_forms(html)
                if forms:
                    ev = _match_rules(forms, dims["form"], provider, "form")
                    all_evidence.extend(ev)
                    score += sum(e.weight for e in ev)

            # body 维度（copyright + 厂商名）
            if result.copyright_text and dims.get("body"):
                ev = _match_rules(result.copyright_text, dims["body"], provider, "body")
                all_evidence.extend(ev)
                score += sum(e.weight for e in ev)

            # url 维度（弱信号）
            if url and dims.get("url"):
                ev = _match_rules(url, dims["url"], provider, "url")
                all_evidence.extend(ev)
                score += sum(e.weight for e in ev)

            # header 维度
            if headers and dims.get("header"):
                header_text = " ".join(
                    f"{k}:{v}" for k, v in headers.items()
                    if k.lower() in ("server", "x-powered-by", "x-generator")
                )
                if header_text:
                    ev = _match_rules(header_text, dims["header"], provider, "header")
                    all_evidence.extend(ev)
                    score += sum(e.weight for e in ev)

            if score > 0:
                scores[provider] = min(score, 1.0)

        # 选择得分最高者；但要求至少有一条非 url 维度证据（避免仅 URL 子串误判）
        if scores:
            # 过滤：仅依靠 url 维度的 provider 降权
            qualified = {}
            for prov, sc in scores.items():
                non_url_ev = [e for e in all_evidence if e.provider == prov and e.dimension != "url"]
                if non_url_ev:
                    qualified[prov] = sc
                else:
                    # 仅 URL 信号，置信度上限 0.3
                    qualified[prov] = min(sc, 0.3)
            if qualified:
                best = max(qualified, key=qualified.get)
                result.provider = best
                result.confidence = qualified[best]
                # 只保留命中 provider 的 evidence
                result.evidence = [e for e in all_evidence if e.provider == best]
            else:
                result.provider = PROVIDER_UNKNOWN
                result.confidence = 0.0
        else:
            result.provider = PROVIDER_UNKNOWN
            result.confidence = 0.0

        return result

    def detect_from_url_only(self, url: str) -> ProviderDetectResult:
        """仅根据 URL 做弱信号识别（无 HTML 时）。

        置信度上限 0.3，且 provider 仅作参考，必须经 HTTP 验证后才能定论。
        """
        return self.detect(url=url, html="", headers=None)

    def is_edu_system_page(self, html: str, title: Optional[str] = None) -> bool:
        """判断页面是否为教务系统页面（不区分 Provider）。"""
        text = (title or "") + " " + html[:20000]
        for kw in EDU_SYSTEM_KEYWORDS:
            if kw.lower() in text.lower():
                return True
        return False


__all__ = ["ProviderDetector", "ProviderDetectResult", "ProviderEvidence"]