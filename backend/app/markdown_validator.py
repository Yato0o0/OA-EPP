"""Markdown 格式校验器 — 依照 docs/contributing.md 中的书写规范。

规则来源与编号:
  1. CN-EN 间距   — contributing.md §3.1  中英文之间需以空格分隔
  2. H1 禁用      — contributing.md §2    H1 为页面标题，文档内禁止使用
  3. 代码块语言    — contributing.md §5.1  代码块必须标注语言类型
  4. 数学公式行    — contributing.md §6    $$ 必须单独占一行
  5. 前端元数据    — contributing.md §1.1  章节文档必须有 YAML frontmatter
  6. 标题编号连续性 — contributing.md §2    章节编号不得跳号
  7. svgbob 误标   — contributing.md §4.1  必须使用 ```bob 而非 ```svgbob
"""

import re
from typing import List, Dict, Any


def validate(content_md: str) -> Dict[str, Any]:
    """对 Markdown 内容执行全部规则校验。

    返回:
        {
            "valid": bool,
            "errors": [{"rule": str, "line": int, "message": str, "suggestion": str}],
            "warnings": [{"rule": str, "line": int, "message": str}]
        }
    """
    lines = content_md.split("\n")
    errors: List[Dict[str, Any]] = []
    warnings: List[Dict[str, Any]] = []

    # 规则 1: CN-EN 间距
    errors.extend(_check_cn_en_spacing(lines))

    # 规则 2: H1 禁用
    errors.extend(_check_no_h1(lines))

    # 规则 3: 代码块语言
    warnings.extend(_check_code_block_lang(content_md))

    # 规则 4: 数学公式行
    errors.extend(_check_math_block_lines(lines))

    # 规则 5: 前端元数据
    warnings.extend(_check_frontmatter(content_md))

    # 规则 6: 标题编号连续性
    warnings.extend(_check_heading_numbers(content_md))

    # 规则 7: svgbob 误标
    errors.extend(_check_svgbob_mistag(content_md))

    valid = len(errors) == 0
    return {"valid": valid, "errors": errors, "warnings": warnings}


# ---------------------------------------------------------------------------
# 规则实现
# ---------------------------------------------------------------------------

# CJK 字符范围
CJK_RE = re.compile(r"[一-鿿㐀-䶿豈-﫿　-〿＀-￯]")
# ASCII 字母
ASCII_RE = re.compile(r"[a-zA-Z0-9]")

# 中文后紧跟英文/数字（无空格）
CN_EN_NO_SPACE_RE = re.compile(r"([一-鿿㐀-䶿豈-﫿　-〿])([a-zA-Z0-9])")
# 英文/数字后紧跟中文（无空格）
EN_CN_NO_SPACE_RE = re.compile(r"([a-zA-Z0-9])([一-鿿㐀-䶿豈-﫿　-〿])")

# 需排除的场景：Markdown 链接、代码块内、HTML 标签内
INLINE_CODE_RE = re.compile(r"`[^`]*`")
MD_LINK_RE = re.compile(r"\[([^\]]*)\]\([^)]*\)")
HTML_TAG_RE = re.compile(r"<[^>]+>")


def _check_cn_en_spacing(lines: List[str]) -> List[Dict[str, Any]]:
    """规则 1: 中英文之间必须使用空格分隔。"""
    errors = []
    for i, line in enumerate(lines, 1):
        # 跳过代码块内容
        if line.strip().startswith("```"):
            continue
        # 跳过纯注释行和空行
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or stripped.startswith("<!--"):
            continue
        # 跳过表格分隔行
        if re.match(r"^\|[\s\-:|]+\|$", stripped):
            continue

        # 临时移除行内代码、链接、HTML标签后检查
        cleaned = INLINE_CODE_RE.sub("", line)
        cleaned = MD_LINK_RE.sub("", cleaned)
        cleaned = HTML_TAG_RE.sub("", cleaned)

        # 中文后紧跟英文/数字
        for m in CN_EN_NO_SPACE_RE.finditer(cleaned):
            ctx = line[max(0, m.start() - 10):m.end() + 10]
            errors.append({
                "rule": "cn_en_spacing",
                "line": i,
                "message": f"中文与英文/数字之间缺少空格：\"{m.group(1)}{m.group(2)}\"",
                "suggestion": f"在 \"{m.group(1)}\" 和 \"{m.group(2)}\" 之间添加半角空格",
            })

        # 英文/数字后紧跟中文
        for m in EN_CN_NO_SPACE_RE.finditer(cleaned):
            ctx = line[max(0, m.start() - 10):m.end() + 10]
            errors.append({
                "rule": "cn_en_spacing",
                "line": i,
                "message": f"英文/数字与中文之间缺少空格：\"{m.group(1)}{m.group(2)}\"",
                "suggestion": f"在 \"{m.group(1)}\" 和 \"{m.group(2)}\" 之间添加半角空格",
            })

    return errors[:20]  # 最多 20 条，避免过多


def _check_no_h1(lines: List[str]) -> List[Dict[str, Any]]:
    """规则 2: 禁止使用 H1 标题（# 开头），应使用 H2（##）开始。"""
    errors = []
    h1_re = re.compile(r"^# [^#]")
    for i, line in enumerate(lines, 1):
        if h1_re.match(line):
            errors.append({
                "rule": "heading_h1",
                "line": i,
                "message": "禁止使用 H1 标题（# 开头），MkDocs 已将页面标题渲染为 H1",
                "suggestion": f"将 \"{line.strip()}\" 改为 \"## {line.strip()[2:]}\"",
            })
    return errors


def _check_code_block_lang(content: str) -> List[Dict[str, Any]]:
    """规则 3: 代码块必须标注语言类型（裸 ``` 不跟语言名）。"""
    warnings = []
    # 匹配以 ``` 开头但不跟字母的代码块起始
    bare_fence_re = re.compile(r"^```\s*$", re.MULTILINE)
    lines = content.split("\n")
    for m in bare_fence_re.finditer(content):
        line_no = content[:m.start()].count("\n") + 1
        warnings.append({
            "rule": "code_block_lang",
            "line": line_no,
            "message": "代码块未标注语言类型，建议添加（如 ```python, ```sql, ```bob 等）",
        })
    return warnings


def _check_math_block_lines(lines: List[str]) -> List[Dict[str, Any]]:
    """规则 4: $$ 数学公式必须单独占一行。"""
    errors = []
    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if "$$" in stripped:
            # 检查是否单独一行
            before = stripped[:stripped.index("$$")]
            after = stripped[stripped.index("$$") + 2:]
            if before.strip() or after.strip():
                errors.append({
                    "rule": "math_block_line",
                    "line": i,
                    "message": "$$ 数学公式标记必须单独占一行，前后不应有其他内容",
                    "suggestion": "将 $$ 单独放在一行上",
                })
    return errors


def _check_frontmatter(content: str) -> List[Dict[str, Any]]:
    """规则 5: 超过 30 行的章级文档建议包含 YAML frontmatter。"""
    warnings = []
    lines = content.split("\n")
    if len(lines) < 30:
        return warnings
    if not content.lstrip().startswith("---"):
        warnings.append({
            "rule": "frontmatter",
            "line": 1,
            "message": "章级文档建议包含 YAML frontmatter（`number headings: first-level 2, start-at N`）",
        })
    return warnings


def _check_heading_numbers(content: str) -> List[Dict[str, Any]]:
    """规则 6: 检测章节编号是否连续（如 ## N / ### N.M）。"""
    warnings = []
    h2_re = re.compile(r"^##\s+(\d+)\s", re.MULTILINE)
    numbers = [int(m.group(1)) for m in h2_re.finditer(content)]
    if len(numbers) >= 2:
        for i in range(len(numbers) - 1):
            if numbers[i + 1] != numbers[i] + 1:
                warnings.append({
                    "rule": "heading_numbers",
                    "line": 0,
                    "message": f"H2 章节编号不连续：{numbers[i]} → {numbers[i + 1]}（预期 {numbers[i] + 1}）",
                })
                break
    return warnings


def _check_svgbob_mistag(content: str) -> List[Dict[str, Any]]:
    """规则 7: 检测 ```svgbob 误标，应使用 ```bob。"""
    errors = []
    svgbob_re = re.compile(r"^```svgbob\b", re.MULTILINE)
    for m in svgbob_re.finditer(content):
        line_no = content[:m.start()].count("\n") + 1
        errors.append({
            "rule": "svgbob_mistag",
            "line": line_no,
            "message": "禁止使用 ```svgbob，应使用 ```bob（markdown_svgbob 扩展只识别 bob 标签）",
            "suggestion": "将 ```svgbob 改为 ```bob",
        })
    return errors
