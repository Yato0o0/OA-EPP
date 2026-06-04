"""基于规则的智能补全引擎 — 识别 Markdown 段落类型，返回上下文适当的补全建议。

用于 F-T-006 Copilot 辅助功能：当用户在编辑器中编写需求文档时，
根据光标所在段落类型，自动推荐匹配的功能属性 / 验收标准 / 安全声明等。
"""

import re
from typing import List, Dict, Any

# ---------------------------------------------------------------------------
# 段落类型识别规则
# ---------------------------------------------------------------------------

# H2 章节标题
CHAPTER_HEADING_RE = re.compile(r"^##\s+\d+\s+.+", re.MULTILINE)

# H3 功能需求块
FEATURE_RE = re.compile(r"^###\s+(F-[A-Z]-\d{3})\s+(.*)", re.MULTILINE)
FEATURE_GENERIC_RE = re.compile(r"^###\s+F-", re.MULTILINE)

# 验收标准标记
ACCEPTANCE_CRITERIA_RE = re.compile(r"\*\*验收标准\*\*")

# 安全属性标记
SECURITY_ATTRIBUTES_RE = re.compile(r"\*\*安全属性\*\*")

# 非功能需求标记
NFR_RE = re.compile(r"^###\s+NFR-", re.MULTILINE)

# 分隔线（暗示新段落开始）
SEPARATOR_RE = re.compile(r"^---\s*$", re.MULTILINE)

# 空行后紧跟 H3（可能是新功能块起点）
NEW_SECTION_HINT_RE = re.compile(r"\n\n(?=###\s+)", re.MULTILINE)

# 数据模型块
TABLE_DEF_RE = re.compile(r"\*\*表名\*\*|\*\*数据模型\*\*|^\| .+ \|$", re.MULTILINE)

# ---------------------------------------------------------------------------
# 知识库: 上下文适当的补全建议
# ---------------------------------------------------------------------------

# 通用功能需求补全
FUNCTIONAL_COMPLETIONS = [
    {
        "type": "completion",
        "label": "用户认证需求",
        "text": "- 用户可通过学号/邮箱 + 密码登录系统。\n- 支持记住登录状态（JWT Token，过期时间 2h）。\n- 连续 5 次登录失败锁定账号 15 分钟。",
    },
    {
        "type": "completion",
        "label": "数据列表查询",
        "text": "- 支持分页查询，默认每页 20 条。\n- 支持按关键字模糊搜索。\n- 支持按时间范围筛选。",
    },
    {
        "type": "completion",
        "label": "文件上传需求",
        "text": "- 支持单个文件上传，大小限制 10MB。\n- 支持格式：CSV / Excel / Markdown。\n- 上传后自动校验文件格式合规性。",
    },
    {
        "type": "completion",
        "label": "通知推送需求",
        "text": "- 站内通知实时推送（WebSocket）。\n- 支持按角色（学生/教师/管理员）定向推送。\n- 支持通知模板配置。",
    },
    {
        "type": "completion",
        "label": "权限校验需求",
        "text": "- 所有 API 接口需要 JWT Token 校验。\n- 教师角色可访问管理功能。\n- 学生角色只能访问本人数据。\n- 管理员角色可进行系统配置。",
    },
]

# 验收标准模板
ACCEPTANCE_TEMPLATES = [
    {
        "type": "attribute",
        "label": "验收标准模板（标准）",
        "text": "**验收标准**：\n- [ ] 功能可按预期正常使用\n- [ ] 边界输入有合理处理\n- [ ] 异常场景有清晰的错误提示\n- [ ] 操作结果在 2s 内反馈\n- [ ] 通过安全审查（OWASP Top 10）",
    },
    {
        "type": "attribute",
        "label": "验收标准模板（详细）",
        "text": "**验收标准**：\n\n- [ ] **正常流程**：\n  - \n- [ ] **边界条件**：\n  - \n- [ ] **异常场景**：\n  - \n- [ ] **性能指标**：\n  - 响应时间 P95 < 200ms\n  - 支持 100 并发用户",
    },
    {
        "type": "attribute",
        "label": "验收标准模板（API）",
        "text": "**验收标准**：\n- [ ] API 返回正确的 HTTP 状态码\n- [ ] 输入参数校验覆盖所有边界值\n- [ ] 未经认证的请求返回 401\n- [ ] 无权限的操作返回 403\n- [ ] 接口响应时间 < 200ms (P95)",
    },
]

# 安全属性模板
SECURITY_TEMPLATES = [
    {
        "type": "attribute",
        "label": "安全属性模板（标准）",
        "text": "**安全属性**：\n- **认证**：JWT Token 校验，过期时间 2h\n- **授权**：RBAC 角色权限控制\n- **数据保护**：传输 TLS 1.3 / 存储 AES-256-GCM\n- **审计**：关键操作写入 audit_logs\n- **输入校验**：参数白名单 + 类型检查\n- **Session**：单设备登录，异常 IP 检测",
    },
    {
        "type": "attribute",
        "label": "安全属性模板（数据隐私）",
        "text": "**安全属性**：\n- **数据分类**：个人信息（PII）加密存储\n- **访问控制**：最小权限原则，按需授权\n- **脱敏**：导出数据时自动脱敏手机号/邮箱\n- **留存**：毕业后自动清理学生数据\n- **合规**：符合《个人信息保护法》要求",
    },
    {
        "type": "attribute",
        "label": "安全属性模板（API 安全）",
        "text": "**安全属性**：\n- **防注入**：所有 SQL 参数使用参数化查询\n- **防 XSS**：用户输入 HTML 实体编码\n- **防 CSRF**：SameSite Cookie + Token 校验\n- **速率限制**：API 单 IP 100 次/分钟\n- **日志**：所有 API 调用记录访问日志",
    },
]

# 新功能块模板
NEW_FEATURE_TEMPLATES = [
    {
        "type": "template",
        "label": "新建功能需求块",
        "text": "### F-xxx 功能名称\n\n**需求描述**：\n\n- \n\n**验收标准**：\n- [ ] \n\n**安全属性**：\n- \n\n**优先级**：P1\n\n**关联功能**：\n",
    },
    {
        "type": "template",
        "label": "新建非功能需求块",
        "text": "### NFR-xxx 非功能需求名称\n\n**性能**：\n- 响应时间 P95 < 200ms\n\n**可用性**：\n- 系统可用性 ≥ 99.5%\n\n**安全性**：\n- OWASP Top 10 防护\n",
    },
]

# 数据模型补全
DATA_MODEL_COMPLETIONS = [
    {
        "type": "template",
        "label": "数据模型定义模板",
        "text": "**表名**：`table_name`\n\n| 字段 | 类型 | 约束 | 说明 |\n|------|------|------|------|\n| id | BIGINT | PK AUTO_INCREMENT | 主键 |\n| created_at | DATETIME | NOT NULL DEFAULT CURRENT_TIMESTAMP | 创建时间 |\n| updated_at | DATETIME | NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP | 更新时间 |\n\n```sql\nCREATE TABLE table_name (\n    id BIGINT NOT NULL AUTO_INCREMENT,\n    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,\n    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,\n    PRIMARY KEY (id)\n) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;\n```",
    },
]


# ---------------------------------------------------------------------------
# 主入口
# ---------------------------------------------------------------------------


def get_suggestions(content_md: str, cursor_line: int = 0) -> Dict[str, Any]:
    """分析 Markdown 内容，返回针对光标位置的补全建议。

    参数:
        content_md: 完整的 Markdown 文本
        cursor_line: 光标所在行号（1-based，用于定位段落类型）

    返回:
        {
            "section_type": str,       # 识别到的段落类型
            "section_header": str,     # 所在章节标题（如有）
            "suggestions": [...]       # 建议列表
        }
    """
    lines = content_md.split("\n")
    total_lines = len(lines)

    # 如果文档为空，返回新文档引导
    if total_lines == 0 or (total_lines == 1 and not lines[0].strip()):
        return {
            "section_type": "empty_document",
            "section_header": None,
            "suggestions": NEW_FEATURE_TEMPLATES[:1],
        }

    # 获取光标附近的行（光标行及前 5 行）
    start = max(0, cursor_line - 6)
    end = min(total_lines, cursor_line + 1)
    context_lines = lines[start:end]
    context = "\n".join(context_lines)

    # 获取光标之前的全部内容（用于判断所在段落）
    before_cursor = "\n".join(lines[:cursor_line]) if cursor_line > 0 else content_md

    # 1. 检测是否在验收标准附近
    if _near_pattern(context, ACCEPTANCE_CRITERIA_RE) or _is_after_header(before_cursor, r"\*\*验收标准\*\*"):
        return {
            "section_type": "acceptance_criteria",
            "section_header": _find_nearest_feature(lines, cursor_line),
            "suggestions": ACCEPTANCE_TEMPLATES + _pick_acceptance_items(),
        }

    # 2. 检测是否在安全属性附近
    if _near_pattern(context, SECURITY_ATTRIBUTES_RE) or _is_after_header(before_cursor, r"\*\*安全属性\*\*"):
        return {
            "section_type": "security_attributes",
            "section_header": _find_nearest_feature(lines, cursor_line),
            "suggestions": SECURITY_TEMPLATES,
        }

    # 3. 检测是否在功能需求块内
    feature_match = FEATURE_RE.search(context)
    if feature_match:
        return {
            "section_type": "functional_requirement",
            "section_header": f"{feature_match.group(1)} {feature_match.group(2)}",
            "suggestions": FUNCTIONAL_COMPLETIONS + ACCEPTANCE_TEMPLATES[:1] + SECURITY_TEMPLATES[:1],
        }

    # 4. 检测是否在通用 H3 区域（可能是功能需求）
    if FEATURE_GENERIC_RE.search(context) or _has_recent_h3(before_cursor):
        return {
            "section_type": "functional_requirement",
            "section_header": _find_nearest_h3(lines, cursor_line),
            "suggestions": FUNCTIONAL_COMPLETIONS[:3] + ACCEPTANCE_TEMPLATES[:1],
        }

    # 5. 检测是否在非功能需求块
    if NFR_RE.search(context):
        return {
            "section_type": "non_functional_requirement",
            "section_header": _find_nearest_h3(lines, cursor_line),
            "suggestions": [
                {
                    "type": "completion",
                    "label": "性能指标",
                    "text": "**性能**：\n- 响应时间 P95 < 200ms\n- 并发支持 ≥ 100 用户\n- 数据库查询 < 50ms (P95)",
                },
                {
                    "type": "completion",
                    "label": "可用性指标",
                    "text": "**可用性**：\n- 系统可用性 ≥ 99.5%\n- 计划内维护窗口 ≤ 4h/月\n- 故障恢复时间 RTO < 30min",
                },
            ],
        }

    # 6. 检测分隔线后的空白区域（可能是新功能块起点）
    if _near_pattern(context, SEPARATOR_RE) and _cursor_on_empty_or_after_sep(context, lines, cursor_line):
        return {
            "section_type": "after_separator",
            "section_header": None,
            "suggestions": NEW_FEATURE_TEMPLATES,
        }

    # 7. 检测数据模型定义
    if TABLE_DEF_RE.search(context):
        return {
            "section_type": "data_model",
            "section_header": None,
            "suggestions": DATA_MODEL_COMPLETIONS,
        }

    # 8. 检测章节标题
    chapter_match = CHAPTER_HEADING_RE.search(context)
    if chapter_match:
        return {
            "section_type": "chapter_heading",
            "section_header": chapter_match.group(0).strip(),
            "suggestions": NEW_FEATURE_TEMPLATES[:1],
        }

    # 9. 光标在空行上，且文档较短（可能刚开始写）
    if cursor_line > 0 and cursor_line <= len(lines) and not lines[cursor_line - 1].strip() and total_lines < 20:
        return {
            "section_type": "near_empty_line",
            "section_header": None,
            "suggestions": NEW_FEATURE_TEMPLATES[:1] + FUNCTIONAL_COMPLETIONS[:1],
        }

    # 默认：返回通用建议
    return {
        "section_type": "general",
        "section_header": None,
        "suggestions": FUNCTIONAL_COMPLETIONS[:2] + ACCEPTANCE_TEMPLATES[:1],
    }


# ---------------------------------------------------------------------------
# 工具函数
# ---------------------------------------------------------------------------


def _near_pattern(context: str, pattern: re.Pattern) -> bool:
    """检查上下文中是否包含指定模式。"""
    return bool(pattern.search(context))


def _is_after_header(before: str, header_pattern: str) -> bool:
    """检查光标之前的内容中最近是否出现了指定标题。"""
    lines = before.split("\n")
    # 从后往前找最近的匹配行
    for line in reversed(lines):
        if re.search(header_pattern, line):
            return True
        # 遇到其他 H2/H3 标题就停止
        if re.match(r"^(##|###)\s+", line):
            break
    return False


def _find_nearest_feature(lines: List[str], cursor_line: int) -> str:
    """找到离光标最近的 ### F-xxx 行。"""
    for i in range(min(cursor_line, len(lines)) - 1, -1, -1):
        m = FEATURE_RE.match(lines[i])
        if m:
            return f"{m.group(1)} {m.group(2)}"
        # 遇到 H2 停止搜索
        if re.match(r"^##\s+", lines[i]):
            break
    return None


def _find_nearest_h3(lines: List[str], cursor_line: int) -> str:
    """找到离光标最近的 ### 行。"""
    for i in range(min(cursor_line, len(lines)) - 1, -1, -1):
        m = re.match(r"^###\s+(.+)", lines[i])
        if m:
            return m.group(1)
        if re.match(r"^##\s+", lines[i]):
            break
    return None


def _has_recent_h3(before_cursor: str) -> bool:
    """检查光标之前最近几行是否有 H3 标题。"""
    lines = before_cursor.split("\n")
    for line in reversed(lines[-10:]):
        if re.match(r"^###\s+", line):
            return True
        if re.match(r"^##\s+", line):
            break
    return False


def _cursor_on_empty_or_after_sep(context: str, lines: List[str], cursor_line: int) -> bool:
    """检查光标是否在分隔线附近的空行上。"""
    if cursor_line < 1 or cursor_line > len(lines):
        return False
    current = lines[cursor_line - 1].strip()
    if current and not current.startswith("#"):
        return False
    # 检查前几行是否有分隔线
    for i in range(max(0, cursor_line - 5), cursor_line):
        if SEPARATOR_RE.match(lines[i].strip()):
            return True
    return False


def _pick_acceptance_items() -> List[Dict[str, Any]]:
    """为验收标准块提供单项勾选项。"""
    return [
        {
            "type": "item",
            "label": "功能正确性检查项",
            "text": "- [ ] 核心功能路径可正常走通\n- [ ] 边界输入不引发崩溃\n- [ ] UI 交互与设计稿一致",
        },
        {
            "type": "item",
            "label": "性能检查项",
            "text": "- [ ] 页面加载时间 < 2s\n- [ ] 操作响应 < 200ms\n- [ ] 支持 100 并发用户",
        },
        {
            "type": "item",
            "label": "安全合规检查项",
            "text": "- [ ] 敏感接口需认证\n- [ ] 输入参数经过校验\n- [ ] 无明文密码传输",
        },
    ]
