"""文档与代码的一致性测试。

`docs/magicclass-*.md` 是运维和验收的判据来源。它们一旦与代码分叉，读文档的人
就会按错误的状态表排障，所以这里把文档里可机械核对的部分钉住：

- 状态表的取值必须与 `FusionState` 完全一致（顺序、数量、字面量）；
- 文档写出的 recent 默认值与上限必须与路由常量一致；
- 三份文档对"整体完成度"必须给同一个结论（不允许一处说已完成、另一处说未开始）；
- 来源声明不得再出现未展开的占位符。
"""
from __future__ import annotations

import re
from pathlib import Path

from app.api.routes.magicclass_fusion import RECENT_DEFAULT_LIMIT, RECENT_MAX_LIMIT
from app.schemas.magicclass_fusion import FusionState

REPO_ROOT = Path(__file__).resolve().parents[2]
DOCS = REPO_ROOT / "docs"


def _read(name: str) -> str:
    return (DOCS / name).read_text(encoding="utf-8")


def test_deployment_state_table_matches_the_schema():
    text = _read("magicclass-deployment.md")
    documented = re.findall(r"^\s*\|\s*`(disabled|unavailable|degraded|ready)`\s*\|", text, re.M)
    assert documented == [state.value for state in FusionState]


def test_deployment_documents_the_recent_limits_from_the_route():
    text = _read("magicclass-deployment.md")
    assert f"limit={RECENT_DEFAULT_LIMIT}" in text
    assert f"上限 {RECENT_MAX_LIMIT}" in text


def test_deployment_documents_the_deep_link_shape():
    text = _read("magicclass-deployment.md")
    assert "/courses/{courseId}?tab=mentoring&session={sessionId}" in text


def test_every_magicclass_doc_agrees_the_migration_is_partial():
    for name in (
        "magicclass-capability-matrix.md",
        "magicclass-deployment.md",
        "magicclass-student-integration-design.md",
    ):
        text = _read(name)
        assert "部分完成" in text, name
        # 不允许任何一份文档声称整体已完成
        assert not re.search(r"完整迁移[^\n]{0,12}已完成", text), name


def test_capability_matrix_names_the_aggregate_endpoints():
    text = _read("magicclass-capability-matrix.md")
    assert "/api/v1/magicclass/fusion/status" in text
    assert "/api/v1/magicclass/fusion/recent" in text


def test_magicclass_docs_carry_no_machine_specific_paths():
    """共享文档不得写入盘符 / 用户名 / 本机绝对路径（仓库级规则）。"""
    import re as _re

    machine_path = _re.compile(r"(?<![A-Za-z0-9])[A-Za-z]:[\\/]{1,2}\S")
    for path in sorted(DOCS.glob("magicclass-*.md")):
        text = path.read_text(encoding="utf-8")
        match = machine_path.search(text)
        assert match is None, f"{path.name} 含本机绝对路径: {match.group(0) if match else ''}"


def test_provenance_notice_states_repository_tag_and_commit():
    """NOTICE 必须把三个可核对事实分开写清楚，且不留未展开的占位符。"""
    notice = (REPO_ROOT / "third_party" / "magicclass" / "NOTICE.md").read_text(encoding="utf-8")
    assert not re.search(r"\$[A-Za-z]", notice)
    assert "- Repository: `https://github.com/THU-MAIC/magicclass.git`" in notice
    assert "- Tag: `v1.0.3`" in notice
    assert "- Commit: `e693e11a81644f84c258df73dbda378643520a62`" in notice
    # 生成器必须产出同样的三行，否则"重新生成"会与已提交的 NOTICE 分叉。
    generator = (REPO_ROOT / "scripts" / "magicclass-source-audit.mjs").read_text(encoding="utf-8")
    assert re.search(r"`- Tag: \\`\$\{tag\}\\``", generator)
    assert "`- Repository: \\`${repository}\\``" in generator
    assert "`- Commit: \\`${commit}\\``" in generator
