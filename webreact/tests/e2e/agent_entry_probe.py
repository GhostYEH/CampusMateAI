"""首页 Agent 工作台入口的共用探针。

三条黄金路径都改为从首页入口进入，而「入口存在」并不等于「用户点得到」：
HTMLElement.click() 对 display:none、opacity:0、pointer-events:none、被其它层盖住
的元素一样会派发点击事件。所以只断言存在性的测试，会被一个藏在首屏背后或压在
上升层下面的入口骗过去——那恰好就是入口缺失这类 bug 的常见形态。

本模块在点击前先做四道检查（尺寸 / 计算样式 / 视口内 / 命中测试），
把结果结构化返回，让调用方能分别断言「存在 / 可见 / 未被遮挡 / 点击生效」，
失败时给出具体原因而不是笼统的 False。
"""
from __future__ import annotations

ENTRY_SELECTOR = "button.sylva-agent-entry"

_PROBE_JS = """
async ([selector, label, timeoutMs]) => {
  const deadline = Date.now() + timeoutMs;
  const miss = (reason, extra) => Object.assign(
    { found: true, visible: false, hittable: false, clicked: false, reason },
    extra || {},
  );
  // 首页首屏有 GSAP 入场动画,入口可能只是"暂时"尺寸为 0 或被上升层盖住。
  // 因此检出问题时不立刻失败,而是记下原因继续轮询,直到可点或超时,
  // 超时后再把最后一次的原因报出来——否则一次瞬时遮挡就会误判成入口不可达。
  let last = null;

  while (Date.now() < deadline) {
    const target = Array.from(document.querySelectorAll(selector))
      .find((node) => (node.textContent || "").trim() === label);
    if (target) {
      const rect = target.getBoundingClientRect();
      if (rect.width < 1 || rect.height < 1) {
        last = miss("zero-size", { width: rect.width, height: rect.height });
      } else {
        const style = getComputedStyle(target);
        const cx = Math.round(rect.left + rect.width / 2);
        const cy = Math.round(rect.top + rect.height / 2);
        const hit = document.elementFromPoint(cx, cy);
        const onTop = !!hit && (hit === target || target.contains(hit));

        if (style.display === "none") last = miss("display:none");
        else if (style.visibility === "hidden") last = miss("visibility:hidden");
        else if (Number(style.opacity) === 0) last = miss("opacity:0");
        else if (style.pointerEvents === "none") last = miss("pointer-events:none");
        else if (cx < 0 || cy < 0 || cx > window.innerWidth || cy > window.innerHeight) {
          last = miss("offscreen", { cx, cy });
        } else if (!onTop) {
          last = miss("covered", {
            cx,
            cy,
            hitTag: hit ? hit.tagName : null,
            hitClass: hit ? String(hit.className || "") : null,
          });
        } else {
          target.click();
          return {
            found: true, visible: true, hittable: true, clicked: true, reason: "",
            width: rect.width, height: rect.height,
          };
        }
      }
    }
    await new Promise((resolve) => setTimeout(resolve, 100));
  }

  return last || { found: false, visible: false, hittable: false, clicked: false, reason: "not-found" };
}
"""


def enter_from_home_entry(page, label, check, failures, timeout_ms=15000):
    """在首页找到入口、校验可见且未被遮挡，然后点击。

    check 由调用方传入（各脚本自己的 _check），保持失败信息的输出风格一致。
    """
    result = page.evaluate(_PROBE_JS, [ENTRY_SELECTOR, label, timeout_ms])

    if not result.get("found"):
        check(False, f"首页存在「{label}」入口", failures)
        return result

    check(True, f"首页存在「{label}」入口", failures)
    check(
        result.get("visible") is True,
        f"首页「{label}」入口可见({result.get('reason') or 'ok'})",
        failures,
    )
    check(
        result.get("hittable") is True,
        f"首页「{label}」入口未被遮挡且可点击({result.get('reason') or 'ok'})",
        failures,
    )
    check(result.get("clicked") is True, f"首页「{label}」入口点击生效", failures)
    return result
