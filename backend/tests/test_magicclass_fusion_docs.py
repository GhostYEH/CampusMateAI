"""文档与代码的一致性测试。

`docs/` 下的文档一旦与代码分叉，读文档的人就会按错误的状态排障，所以这里把文档里
可机械核对的部分钉住：

- 共享文档不得写入盘符 / 用户名 / 本机绝对路径（仓库级规则）；
- NOTICE 的来源声明不得再出现未展开的占位符，且生成器必须产出同样的三行。
"""
from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DOCS = REPO_ROOT / "docs"


def test_magicclass_docs_carry_no_machine_specific_paths():
    """共享文档不得写入盘符 / 用户名 / 本机绝对路径（仓库级规则）。"""
    machine_path = re.compile(r"(?<![A-Za-z0-9])[A-Za-z]:[\\/]{1,2}\S")
    for path in sorted(DOCS.glob("magicclass-*.md")):
        text = path.read_text(encoding="utf-8")
        match = machine_path.search(text)
        assert match is None, f"{path.name} 含本机绝对路径: {match.group(0) if match else ''}"


def test_provenance_notice_states_repository_tag_and_commit():
    """NOTICE 必须把三个可核对事实分开写清楚，且不留未展开的占位符。"""
    notice = (REPO_ROOT / "third_party" / "magicclass" / "NOTICE.md").read_text(encoding="utf-8")
    assert not re.search(r"\$[A-Za-z]", notice)
    assert "- Repository: `https://github.com/THU-MAIC/OpenMAIC.git`" in notice
    assert "- Tag: `v1.0.3`" in notice
    assert "- Commit: `e693e11a81644f84c258df73dbda378643520a62`" in notice
    # 生成器必须产出同样的三行，否则"重新生成"会与已提交的 NOTICE 分叉。
    generator = (REPO_ROOT / "scripts" / "magicclass-source-audit.mjs").read_text(encoding="utf-8")
    assert re.search(r"`- Tag: \\`\$\{tag\}\\``", generator)
    assert "`- Repository: \\`${repository}\\``" in generator
    assert "`- Commit: \\`${commit}\\``" in generator