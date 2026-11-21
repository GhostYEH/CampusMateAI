"""经典课堂（session_id/classroom_id）的版本化原生播放数据构建。

数据来源只有一个：服务端已保存的 session + 上游 `GET /api/classroom?id=`
回读的课堂文档。客户端不提交课堂正文，也不决定课程/课件归属。

设计边界：
- 本模块不访问数据库、不解析账号，只把“已授权的课堂正文”转换成稳定契约。
- 受管工作台的 workspace_id/stage_id/scene_id 不在这里伪造；经典课堂没有
  workspace 映射，互动动作按真实能力标注为 supported/unsupported。
- 所有媒体引用改写成本站相对地址；任何上游内部 Origin 都不进入响应体。
"""
from __future__ import annotations

import copy
import hashlib
import json
import math
import re
from collections import OrderedDict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional, Tuple
from urllib.parse import unquote, urlsplit

from ...schemas.magicclass import (
    ClassroomPlaybackActionOut,
    ClassroomPlaybackCompatOut,
    ClassroomPlaybackDegradedOut,
    ClassroomPlaybackDroppedActionOut,
    ClassroomPlaybackMediaOut,
    ClassroomPlaybackNativeOut,
    ClassroomPlaybackOut,
    ClassroomPlaybackRenderOut,
    ClassroomPlaybackSceneOut,
    ClassroomPlaybackStepOut,
    ClassroomPlaybackWarningOut,
)

CONTRACT_VERSION = "classroom-playback/1"

KNOWN_SCENE_TYPES = {"slide", "quiz", "interactive", "pbl"}
KNOWN_WIDGET_TYPES = {
    "simulation",
    "diagram",
    "code",
    "game",
    "visualization3d",
    "procedural-skill",
}
KNOWN_ACTION_TYPES = {
    "spotlight",
    "laser",
    "play_video",
    "speech",
    "wb_open",
    "wb_draw_text",
    "wb_draw_shape",
    "wb_draw_chart",
    "wb_draw_latex",
    "wb_draw_table",
    "wb_draw_line",
    "wb_draw_code",
    "wb_edit_code",
    "wb_clear",
    "wb_delete",
    "wb_close",
    "discussion",
    "widget_highlight",
    "widget_setState",
    "widget_annotation",
    "widget_reveal",
}
FIRE_AND_FORGET_ACTIONS = {"spotlight", "laser"}
SLIDE_ONLY_ACTIONS = {"spotlight", "laser"}
WHITEBOARD_ACTIONS = {name for name in KNOWN_ACTION_TYPES if name.startswith("wb_")}
WIDGET_ACTIONS = {
    "widget_highlight",
    "widget_setState",
    "widget_annotation",
    "widget_reveal",
}

_MEDIA_REL_RE = re.compile(r"^(media|audio)/[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
_CLASSROOM_MEDIA_PREFIX = "/api/classroom-media/"
_CONTENT_TYPES = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".gif": "image/gif",
    ".svg": "image/svg+xml",
    ".bmp": "image/bmp",
    ".mp4": "video/mp4",
    ".webm": "video/webm",
    ".mov": "video/quicktime",
    ".m4v": "video/mp4",
    ".mp3": "audio/mpeg",
    ".m4a": "audio/mp4",
    ".wav": "audio/wav",
    ".ogg": "audio/ogg",
    ".aac": "audio/aac",
    ".flac": "audio/flac",
}


class ClassroomDocumentCache:
    """进程内课堂正文缓存：正文只读、按 classroom_id 复用。

    只缓存“已经通过账号/课程校验后取回”的正文；媒体接口不经过这里，
    每次媒体请求仍会重新做账号与会话校验。
    """

    def __init__(self, *, max_entries: int = 24, max_bytes: int = 24 * 1024 * 1024):
        self._max_entries = max_entries
        self._max_bytes = max_bytes
        self._entries: "OrderedDict[str, Tuple[Dict[str, Any], str, int]]" = OrderedDict()
        self._total_bytes = 0

    def get(self, classroom_id: str) -> Optional[Tuple[Dict[str, Any], str]]:
        entry = self._entries.get(classroom_id)
        if entry is None:
            return None
        self._entries.move_to_end(classroom_id)
        return entry[0], entry[1]

    def put(self, classroom_id: str, classroom: Dict[str, Any], content_version: str, size: int) -> None:
        previous = self._entries.pop(classroom_id, None)
        if previous is not None:
            self._total_bytes -= previous[2]
        self._entries[classroom_id] = (classroom, content_version, max(0, size))
        self._total_bytes += max(0, size)
        while len(self._entries) > self._max_entries or self._total_bytes > self._max_bytes:
            _, evicted = self._entries.popitem(last=False)
            self._total_bytes -= evicted[2]

    def clear(self) -> None:
        self._entries.clear()
        self._total_bytes = 0


def content_version_for(classroom: Dict[str, Any]) -> Tuple[str, int]:
    """返回 (正文版本, 序列化体积)。版本只由正文决定，不含课程/会话 ID。"""
    try:
        payload = json.dumps(
            classroom, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str
        )
    except (TypeError, ValueError):
        payload = json.dumps(str(classroom), ensure_ascii=False)
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]
    return f"sha256:{digest}", len(payload.encode("utf-8"))


@dataclass
class _MediaCollector:
    classroom_id: str
    media_base: str
    origins: Tuple[str, ...]
    items: Dict[str, ClassroomPlaybackMediaOut] = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)

    def resolve(
        self,
        value: Any,
        *,
        kind: str,
        role: str,
        element_id: Optional[str],
    ) -> Optional[str]:
        """解析媒体引用；返回本站 URL（不可用时返回 None 并登记原因）。"""
        status, relpath = _classify_media_ref(value, self.classroom_id, self.origins)
        if status == "inline":
            self._warn("inline_media_present")
            return str(value)
        if status == "ok" and relpath:
            content_type = _content_type(relpath)
            entry = ClassroomPlaybackMediaOut(
                id=relpath,
                kind=kind,
                role=role,
                element_id=element_id,
                content_type=content_type,
                url=f"{self.media_base}/{relpath}",
                available=True,
            )
            self.items[relpath] = entry
            return entry.url
        reason = {
            "external": "external_media_not_proxied",
            "other_classroom": "media_owned_by_other_classroom",
            "missing": "media_src_missing",
            "placeholder": "media_reference_unresolved",
        }.get(status, "media_reference_invalid")
        self.unavailable(kind=kind, role=role, element_id=element_id, reason=reason, source=value)
        return None

    def unavailable(
        self,
        *,
        kind: str,
        role: str,
        element_id: Optional[str],
        reason: str,
        source: Any = None,
        content_type: str = "application/octet-stream",
    ) -> None:
        key = f"unavailable:{role}:{element_id or '-'}:{len(self.items)}"
        self.items[key] = ClassroomPlaybackMediaOut(
            id=key,
            kind=kind,
            role=role,
            element_id=element_id,
            content_type=content_type,
            url=None,
            available=False,
            reason=reason,
        )
        self._warn(reason)

    def _warn(self, code: str) -> None:
        if code not in self.warnings:
            self.warnings.append(code)

    def as_list(self) -> List[ClassroomPlaybackMediaOut]:
        return list(self.items.values())


def _classify_media_ref(
    value: Any, classroom_id: str, origins: Tuple[str, ...]
) -> Tuple[str, Optional[str]]:
    """把文档里的媒体引用归类。

    只接受：data: 内联、当前课堂的 `/api/classroom-media/{cid}/(media|audio)/file`
    （可带受信 Origin）、以及当前课堂的 `media/file` / `audio/file` 相对引用。
    其它一律不猜地址。
    """
    if not isinstance(value, str) or not value.strip():
        return "missing", None
    raw = value.strip()
    if raw.startswith("data:"):
        return "inline", None
    parsed = urlsplit(raw)
    if parsed.scheme in ("http", "https"):
        origin = f"{parsed.scheme}://{parsed.netloc}"
        if origin not in origins:
            return "external", None
        path = parsed.path
    elif parsed.scheme or raw.startswith("//"):
        return "external", None
    else:
        path = raw.split("?", 1)[0].split("#", 1)[0]
    if path.startswith("/"):
        path = path
    if path.startswith(_CLASSROOM_MEDIA_PREFIX):
        parts = path[len(_CLASSROOM_MEDIA_PREFIX):].split("/")
        if len(parts) != 3:
            return "placeholder", None
        cid, directory, filename = parts
        if cid != classroom_id:
            return "other_classroom", None
        if directory not in ("media", "audio"):
            return "placeholder", None
        relpath = f"{directory}/{unquote(filename)}"
        if not _MEDIA_REL_RE.match(relpath):
            return "placeholder", None
        return "ok", relpath
    if path.startswith("media/") or path.startswith("audio/"):
        relpath = path
        if _MEDIA_REL_RE.match(relpath):
            return "ok", relpath
    return "placeholder", None


def _content_type(relpath: str) -> str:
    dot = relpath.rfind(".")
    if dot < 0:
        return "application/octet-stream"
    return _CONTENT_TYPES.get(relpath[dot:].lower(), "application/octet-stream")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _iso_timestamp(value: Any) -> Optional[str]:
    if value is None or value == "":
        return None
    if isinstance(value, str):
        return value
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        number = float(value)
        if not math.isfinite(number) or number <= 0:
            return None
        if number > 1_000_000_000_000:
            number /= 1000.0
        try:
            return datetime.fromtimestamp(number, tz=timezone.utc).isoformat()
        except (OverflowError, OSError, ValueError):
            return None
    return None


def _warning(code: str, message: str, scene_id: Optional[str] = None) -> ClassroomPlaybackWarningOut:
    return ClassroomPlaybackWarningOut(code=code, message=message, scene_id=scene_id)


def _strip_internal_origins(value: Any, origins: Iterable[str]) -> Tuple[Any, bool]:
    """递归移除字符串里的内部 Origin，避免把内部服务地址带给客户端。"""
    changed = False
    real_origins = tuple(origin for origin in origins if origin)
    if isinstance(value, str):
        result = value
        for origin in real_origins:
            if origin in result:
                result = result.replace(origin, "")
                changed = True
        return result, changed
    if isinstance(value, list):
        output = []
        for item in value:
            new_item, item_changed = _strip_internal_origins(item, real_origins)
            output.append(new_item)
            changed = changed or item_changed
        return output, changed
    if isinstance(value, dict):
        output_dict: Dict[Any, Any] = {}
        for key, item in value.items():
            new_item, item_changed = _strip_internal_origins(item, real_origins)
            output_dict[key] = new_item
            changed = changed or item_changed
        return output_dict, changed
    return value, changed


def _rewrite_interactive_html(
    html: str,
    *,
    classroom_id: str,
    media_base: str,
    collector: _MediaCollector,
) -> Tuple[str, bool]:
    """把 sandbox HTML 里的课堂媒体改成本站相对地址，并登记媒体清单。

    返回 (新 HTML, 是否出现课堂媒体)。客户端需以 API Base 作为 WebView base URL，
    并在子资源请求上补 Authorization；否则该场景应走兼容入口。
    """
    found = False
    rewritten = html
    for origin in collector.origins:
        rewritten = rewritten.replace(
            f"{origin}{_CLASSROOM_MEDIA_PREFIX}{classroom_id}/",
            f"{media_base}/",
        )
    rewritten = rewritten.replace(
        f"{_CLASSROOM_MEDIA_PREFIX}{classroom_id}/",
        f"{media_base}/",
    )
    pattern = re.compile(
        rf"{re.escape(media_base)}/(media|audio)/([A-Za-z0-9][A-Za-z0-9._-]{{0,127}})"
    )
    for match in pattern.finditer(rewritten):
        relpath = f"{match.group(1)}/{unquote(match.group(2))}"
        if _MEDIA_REL_RE.match(relpath):
            found = True
            collector.items[relpath] = ClassroomPlaybackMediaOut(
                id=relpath,
                kind="image" if match.group(1) == "media" else "audio",
                role="interactive_asset",
                element_id=None,
                content_type=_content_type(relpath),
                url=f"{media_base}/{relpath}",
                available=True,
            )
    return rewritten, found


def _scene_render(scene_type: str, content: Any, *, external_3d_available: bool) -> ClassroomPlaybackRenderOut:
    if scene_type == "slide":
        if isinstance(content, dict) and isinstance(content.get("canvas"), dict):
            return ClassroomPlaybackRenderOut(kind="native")
        return ClassroomPlaybackRenderOut(
            kind="unsupported", reason="slide_content_missing"
        )
    if scene_type == "quiz":
        if isinstance(content, dict) and isinstance(content.get("questions"), list):
            return ClassroomPlaybackRenderOut(kind="native")
        return ClassroomPlaybackRenderOut(
            kind="unsupported", reason="quiz_content_missing"
        )
    if scene_type == "interactive":
        if not isinstance(content, dict):
            return ClassroomPlaybackRenderOut(
                kind="unsupported", reason="interactive_content_missing"
            )
        html = content.get("html")
        widget_type = content.get("widgetType")
        if isinstance(html, str) and html.strip():
            return ClassroomPlaybackRenderOut(
                kind="sandbox-html", sandbox="allow-scripts", widget_type=widget_type
            )
        url = content.get("url")
        if isinstance(url, str) and url.strip():
            parsed = urlsplit(url.strip())
            if parsed.scheme not in ("http", "https"):
                return ClassroomPlaybackRenderOut(
                    kind="unsupported", reason="interactive_url_scheme_unsupported"
                )
            if widget_type == "visualization3d" and not external_3d_available:
                return ClassroomPlaybackRenderOut(
                    kind="unsupported", reason="widget_requires_external_cdn"
                )
            return ClassroomPlaybackRenderOut(
                kind="sandbox-url", sandbox="allow-scripts", widget_type=widget_type
            )
        if widget_type == "visualization3d" and not external_3d_available:
            return ClassroomPlaybackRenderOut(
                kind="unsupported", reason="widget_requires_external_cdn"
            )
        return ClassroomPlaybackRenderOut(
            kind="unsupported", reason="interactive_payload_missing"
        )
    if scene_type == "pbl":
        return ClassroomPlaybackRenderOut(
            kind="unsupported", reason="pbl_requires_compat_runtime"
        )
    return ClassroomPlaybackRenderOut(kind="unsupported", reason="scene_type_unsupported")


def _action_support(
    action_type: str,
    *,
    action: Dict[str, Any],
    scene_type: str,
    render_kind: str,
    media_items: List[ClassroomPlaybackMediaOut],
) -> Tuple[bool, Optional[str]]:
    if action_type not in KNOWN_ACTION_TYPES:
        return False, "action_type_unknown"
    if action_type in SLIDE_ONLY_ACTIONS:
        if scene_type != "slide":
            return False, "action_requires_slide_scene"
        return True, None
    if action_type == "speech":
        return True, None
    if action_type == "play_video":
        target = action.get("elementId")
        if not isinstance(target, str) or not target:
            return False, "video_media_unavailable"
        for item in media_items:
            if item.kind == "video" and item.element_id == target and item.available:
                return True, None
        return False, "video_media_unavailable"
    if action_type in WHITEBOARD_ACTIONS:
        return True, None
    if action_type == "discussion":
        return False, "discussion_requires_compat_runtime"
    if action_type in WIDGET_ACTIONS:
        if render_kind in ("sandbox-html", "sandbox-url"):
            return True, None
        return False, "widget_action_requires_interactive_scene"
    return False, "action_type_unsupported"



def _rewrite_content(
    scene_type: str,
    content: Any,
    *,
    classroom_id: str,
    media_base: str,
    origins: Tuple[str, ...],
    external_3d_available: bool,
) -> Tuple[Any, _MediaCollector, bool]:
    collector = _MediaCollector(classroom_id=classroom_id, media_base=media_base, origins=origins)
    if not isinstance(content, dict):
        return content, collector, False
    working = copy.deepcopy(content)
    interactive_media = False

    if scene_type == "slide":
        canvas = working.get("canvas")
        if isinstance(canvas, dict):
            background = canvas.get("background")
            if isinstance(background, dict) and background.get("type") == "image":
                # 上游 DSL 同时存在 `background.image.src` 与扁平
                # `background.src` 两种历史写法；两者都必须改成本站地址。
                image = background.get("image")
                target = image if isinstance(image, dict) else background
                src = collector.resolve(
                    target.get("src"), kind="image", role="background", element_id=None
                )
                if src is not None and not str(src).startswith("data:"):
                    target["src"] = src
                elif src is None:
                    target["src"] = ""
            elements = canvas.get("elements")
            if isinstance(elements, list):
                for index, element in enumerate(elements):
                    if not isinstance(element, dict):
                        continue
                    element_type = element.get("type")
                    element_id = element.get("id") if isinstance(element.get("id"), str) else None
                    if element_type == "image":
                        src = collector.resolve(
                            element.get("src"),
                            kind="image",
                            role="slide_element",
                            element_id=element_id,
                        )
                        element["src"] = src or ""
                    elif element_type == "audio":
                        src = collector.resolve(
                            element.get("src"),
                            kind="audio",
                            role="slide_element",
                            element_id=element_id,
                        )
                        element["src"] = src or ""
                    elif element_type == "video":
                        src = collector.resolve(
                            element.get("src"),
                            kind="video",
                            role="slide_element",
                            element_id=element_id,
                        )
                        element["src"] = src or ""
                        media_ref = element.get("mediaRef")
                        if isinstance(media_ref, str):
                            resolved = collector.resolve(
                                media_ref,
                                kind="video",
                                role="slide_element",
                                element_id=element_id,
                            )
                            if resolved is not None:
                                element["mediaRef"] = resolved
                        poster = element.get("poster")
                        if isinstance(poster, str) and poster:
                            resolved_poster = collector.resolve(
                                poster,
                                kind="image",
                                role="video_poster",
                                element_id=element_id,
                            )
                            if resolved_poster is not None:
                                element["poster"] = resolved_poster
                            else:
                                element.pop("poster", None)

    if scene_type == "interactive":
        html = working.get("html")
        if isinstance(html, str) and html.strip():
            new_html, found = _rewrite_interactive_html(
                html,
                classroom_id=classroom_id,
                media_base=media_base,
                collector=collector,
            )
            working["html"] = new_html
            interactive_media = found
            if found:
                collector._warn("interactive_media_requires_auth_header")

    working, stripped = _strip_internal_origins(working, origins)
    if stripped:
        collector._warn("internal_origin_references_removed")
    return working, collector, interactive_media


def _action_payload(action: Dict[str, Any]) -> Dict[str, Any]:
    return {
        key: value
        for key, value in action.items()
        if key not in ("id", "type", "mode")
    }


def _rewrite_actions(
    actions: List[Any],
    *,
    classroom_id: str,
    media_base: str,
    origins: Tuple[str, ...],
    collector: _MediaCollector,
) -> Tuple[List[Dict[str, Any]], List[str]]:
    output: List[Dict[str, Any]] = []
    warnings: List[str] = []
    for index, raw in enumerate(actions):
        if not isinstance(raw, dict):
            warnings.append("action_entry_invalid")
            continue
        action = copy.deepcopy(raw)
        action_id = action.get("id") if isinstance(action.get("id"), str) else ""
        action_type = action.get("type") if isinstance(action.get("type"), str) else "unknown"
        audio_url = action.get("audioUrl")
        if action_type == "speech" and isinstance(audio_url, str) and audio_url.strip():
            resolved = collector.resolve(
                audio_url,
                kind="audio",
                role="narration",
                element_id=action_id or None,
            )
            if resolved is not None and not resolved.startswith("data:"):
                action["audioUrl"] = resolved
            else:
                action.pop("audioUrl", None)
                if collector.warnings and "external_media_not_proxied" in collector.warnings:
                    warnings.append("narration_audio_unavailable")
                elif collector.warnings and "media_reference_unresolved" in collector.warnings:
                    warnings.append("narration_audio_asset_ref_only")
        action, stripped = _strip_internal_origins(action, origins)
        if stripped:
            warnings.append("internal_origin_references_removed")
        output.append(action if isinstance(action, dict) else {"id": action_id, "type": action_type})
    return output, warnings


def _sort_scenes(raw_scenes: List[Any]) -> List[Tuple[int, Dict[str, Any]]]:
    indexed: List[Tuple[int, Dict[str, Any]]] = []
    for index, raw in enumerate(raw_scenes):
        if isinstance(raw, dict):
            indexed.append((index, raw))
    def key(item: Tuple[int, Dict[str, Any]]) -> Tuple[int, int]:
        index, scene = item
        order = scene.get("order")
        if isinstance(order, (int, float)) and not isinstance(order, bool) and math.isfinite(order):
            return int(order), index
        return index, index
    return sorted(indexed, key=key)


def build_classroom_playback(
    *,
    document: Dict[str, Any],
    session: Any,
    media_base: str,
    content_version: Optional[str] = None,
    compat_url: Optional[str] = None,
    compat_url_unavailable_reason: Optional[str] = None,
    browser_embed_available: bool = False,
    browser_embed_reason: Optional[str] = None,
    external_3d_available: bool = False,
    origins: Iterable[str] = (),
    scene_id: Optional[str] = None,
) -> ClassroomPlaybackOut:
    """把已授权课堂正文转换成版本化播放数据。"""
    classroom = document.get("classroom") if isinstance(document, dict) else None
    if not isinstance(classroom, dict):
        raise ValueError("classroom_missing")
    stage = classroom.get("stage") if isinstance(classroom.get("stage"), dict) else {}
    raw_scenes = classroom.get("scenes")
    if not isinstance(raw_scenes, list):
        raise ValueError("scenes_missing")

    expected_classroom_id = str(getattr(session, "classroom_id", "") or "")
    document_classroom_id = classroom.get("id")
    warnings: List[ClassroomPlaybackWarningOut] = []
    if not stage:
        warnings.append(_warning("stage_missing", "课堂缺少 stage 元数据，标题回退为空"))
    if document_classroom_id and str(document_classroom_id) != expected_classroom_id:
        warnings.append(
            _warning(
                "classroom_id_mismatch",
                "课堂正文 id 与会话记录不一致，已按会话记录构造媒体地址",
            )
        )

    if content_version is None:
        content_version, _ = content_version_for(classroom)

    origin_list = tuple(origin for origin in origins if origin)
    scenes: List[ClassroomPlaybackSceneOut] = []
    degraded: List[ClassroomPlaybackDegradedOut] = []
    supported_count = 0

    used_scene_ids: set[str] = set()
    for source_index, raw_scene in _sort_scenes(raw_scenes):
        scene_id_value = raw_scene.get("id") if isinstance(raw_scene.get("id"), str) else ""
        scene_type = raw_scene.get("type") if isinstance(raw_scene.get("type"), str) else "unknown"
        title = raw_scene.get("title") if isinstance(raw_scene.get("title"), str) else ""
        scene_id_missing = not scene_id_value
        scene_id_duplicate = False
        if scene_id_missing:
            safe_type = re.sub(r"[^A-Za-z0-9_-]", "_", scene_type) or "unknown"
            scene_id_value = f"sc_{safe_type}_{source_index + 1}"
        elif scene_id_value in used_scene_ids:
            scene_id_duplicate = True
            scene_id_value = f"{scene_id_value}_{source_index + 1}"
        used_scene_ids.add(scene_id_value)
        order_value = raw_scene.get("order")
        order = (
            int(order_value)
            if isinstance(order_value, (int, float)) and not isinstance(order_value, bool)
            else source_index
        )
        content = raw_scene.get("content")
        render = _scene_render(
            scene_type, content, external_3d_available=external_3d_available
        )
        scene_warnings: List[str] = []
        if scene_id_missing:
            scene_warnings.append("scene_id_missing")
        if scene_id_duplicate:
            scene_warnings.append("scene_id_duplicate")
        if content is None or not isinstance(content, dict):
            scene_warnings.append("scene_content_missing")
        if scene_type not in KNOWN_SCENE_TYPES:
            scene_warnings.append("scene_type_unknown")
        if isinstance(content, dict):
            declared_type = content.get("type")
            if isinstance(declared_type, str) and declared_type != scene_type:
                scene_warnings.append("content_type_mismatch")

        working_content, collector, interactive_media = _rewrite_content(
            scene_type,
            content,
            classroom_id=expected_classroom_id,
            media_base=media_base,
            origins=origin_list,
            external_3d_available=external_3d_available,
        )
        if isinstance(working_content, dict) and scene_type == "interactive":
            if render.kind == "sandbox-url":
                url_value = working_content.get("url")
                if not isinstance(url_value, str) or urlsplit(url_value).scheme not in ("http", "https"):
                    render = ClassroomPlaybackRenderOut(
                        kind="unsupported",
                        widget_type=render.widget_type,
                        reason="interactive_url_requires_internal_access",
                    )
                    scene_warnings.append("interactive_url_requires_internal_access")
            if interactive_media:
                scene_warnings.append("interactive_media_requires_auth_header")
            if isinstance(working_content.get("html"), str):
                if "internal_origin_references_removed" in collector.warnings:
                    scene_warnings.append("internal_origin_references_removed")

        raw_actions = raw_scene.get("actions")
        actions_list = raw_actions if isinstance(raw_actions, list) else []
        if raw_actions is not None and not isinstance(raw_actions, list):
            scene_warnings.append("actions_invalid")
        rewritten_actions, action_warnings = _rewrite_actions(
            actions_list,
            classroom_id=expected_classroom_id,
            media_base=media_base,
            origins=origin_list,
            collector=collector,
        )
        scene_warnings.extend(action_warnings)

        action_models: List[ClassroomPlaybackActionOut] = []
        steps: List[ClassroomPlaybackStepOut] = []
        dropped: List[ClassroomPlaybackDroppedActionOut] = []
        media_items = collector.as_list()
        for action in rewritten_actions:
            action_id = action.get("id") if isinstance(action.get("id"), str) else ""
            action_type = action.get("type") if isinstance(action.get("type"), str) else "unknown"
            mode = "fire_and_forget" if action_type in FIRE_AND_FORGET_ACTIONS else "sync"
            supported, reason = _action_support(
                action_type,
                action=action,
                scene_type=scene_type,
                render_kind=render.kind,
                media_items=media_items,
            )
            action_models.append(
                ClassroomPlaybackActionOut(
                    id=action_id,
                    type=action_type,
                    mode=mode,
                    supported=supported,
                    reason=reason,
                    payload=_action_payload(action),
                )
            )
            if supported:
                if mode == "sync":
                    steps.append(
                        ClassroomPlaybackStepOut(
                            action_id=action_id, type=action_type, mode=mode
                        )
                    )
            else:
                dropped.append(
                    ClassroomPlaybackDroppedActionOut(
                        action_id=action_id,
                        type=action_type,
                        reason=reason or "action_unsupported",
                    )
                )

        whiteboards = raw_scene.get("whiteboards")
        whiteboard_count = len(whiteboards) if isinstance(whiteboards, list) else 0
        multi_agent = bool(raw_scene.get("multiAgent"))
        if raw_scene.get("agents") not in (None, []):
            multi_agent = True

        for code in collector.warnings:
            if code not in scene_warnings:
                scene_warnings.append(code)

        scenes.append(
            ClassroomPlaybackSceneOut(
                id=scene_id_value,
                source_index=source_index,
                type=scene_type,
                title=title,
                order=order,
                content=working_content if isinstance(working_content, dict) else None,
                render=render,
                actions=action_models,
                steps=steps,
                dropped_actions=dropped,
                media=media_items,
                whiteboards=whiteboard_count,
                multi_agent=multi_agent,
                warnings=_unique(scene_warnings),
            )
        )
        if render.kind == "unsupported":
            degraded.append(
                ClassroomPlaybackDegradedOut(
                    scene_id=scene_id_value or f"index:{source_index}",
                    reason=render.reason or "scene_unsupported",
                )
            )
        else:
            supported_count += 1
        for code in _unique(scene_warnings):
            if code in {"scene_id_missing", "scene_content_missing", "scene_type_unknown",
                        "content_type_mismatch", "actions_invalid", "action_entry_invalid",
                        "inline_media_present", "external_media_not_proxied",
                        "media_reference_unresolved", "media_owned_by_other_classroom",
                        "media_src_missing", "media_reference_invalid",
                        "internal_origin_references_removed",
                        "interactive_media_requires_auth_header",
                        "narration_audio_unavailable", "narration_audio_asset_ref_only"}:
                warnings.append(_warning(code, _warning_message(code), scene_id_value or None))

    start_index = 0
    if scene_id:
        matched = None
        for index, scene in enumerate(scenes):
            if scene.id == scene_id:
                matched = index
                break
        if matched is None:
            raise LookupError("scene_not_found")
        start_index = matched

    source_scenes_count = len(raw_scenes)
    scenes_count = len(scenes)
    unsupported_count = scenes_count - supported_count
    if scenes_count == 0:
        native = ClassroomPlaybackNativeOut(
            available=False,
            reason="classroom_has_no_scenes",
            supported_scene_count=0,
            unsupported_scene_count=0,
        )
    else:
        native = ClassroomPlaybackNativeOut(
            available=supported_count > 0,
            reason=None if supported_count > 0 else "no_supported_scenes",
            supported_scene_count=supported_count,
            unsupported_scene_count=unsupported_count,
        )

    if native.available:
        recommended = "native"
        compat_reason = None
    elif browser_embed_available and compat_url:
        recommended = "web"
        compat_reason = native.reason
    else:
        recommended = "none"
        compat_reason = native.reason

    return ClassroomPlaybackOut(
        contract_version=CONTRACT_VERSION,
        course_id=str(getattr(session, "course_id", "") or ""),
        session_id=str(getattr(session, "session_id", "") or ""),
        classroom_id=expected_classroom_id,
        content_version=content_version,
        document_updated_at=_iso_timestamp(stage.get("updatedAt") or stage.get("createdAt")),
        generated_at=str(getattr(session, "created_at", "") or ""),
        title=str(stage.get("name") or ""),
        mode=str(getattr(session, "mode", "") or ""),
        partial=bool(getattr(session, "partial", False)),
        scenes_count=scenes_count,
        source_scenes_count=source_scenes_count,
        start_index=start_index,
        scenes=scenes,
        degraded=degraded,
        warnings=warnings,
        native=native,
        compat=ClassroomPlaybackCompatOut(
            browser_embed_available=browser_embed_available,
            browser_embed_reason=browser_embed_reason,
            url=compat_url,
            url_unavailable_reason=compat_url_unavailable_reason or browser_embed_reason,
            recommended=recommended,
            reason=compat_reason,
        ),
    )


def _unique(values: List[str]) -> List[str]:
    seen = set()
    output: List[str] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            output.append(value)
    return output


_WARNING_MESSAGES = {
    "scene_id_missing": "场景缺少原 ID，已用 source_index 保持顺序",
    "scene_id_duplicate": "场景 ID 重复，已加后缀区分",
    "scene_content_missing": "场景缺少正文",
    "scene_type_unknown": "场景类型未知，原生播放已跳过",
    "content_type_mismatch": "场景类型与正文声明不一致",
    "actions_invalid": "场景动作不是数组",
    "action_entry_invalid": "存在非法动作条目",
    "inline_media_present": "存在内联 data: 媒体，请直接使用正文中的地址",
    "external_media_not_proxied": "外部媒体不代理，原生播放不可用",
    "media_reference_unresolved": "媒体引用无法解析为课堂资源",
    "media_owned_by_other_classroom": "媒体属于其他课堂，已拒绝",
    "media_src_missing": "媒体缺少地址",
    "media_reference_invalid": "媒体地址格式非法",
    "internal_origin_references_removed": "已移除正文中的内部服务地址",
    "interactive_media_requires_auth_header": "互动 HTML 内的媒体需要 WebView 补鉴权头",
    "narration_audio_unavailable": "讲解音频不可代理，文本仍可播放",
    "narration_audio_asset_ref_only": "讲解音频只有资源 ID，服务端无法定位文件",
    "interactive_url_requires_internal_access": "互动场景地址依赖内部访问，原生不可直接打开",
}


def _warning_message(code: str) -> str:
    return _WARNING_MESSAGES.get(code, code)


__all__ = [
    "CONTRACT_VERSION",
    "ClassroomDocumentCache",
    "build_classroom_playback",
    "content_version_for",
]
