"""GitHub API 客户端 — 用于从需求文档中提取功能块并创建 GitHub Issues。

通过 PyGithub 封装访问 GitHub REST API。
环境变量:
    GITHUB_TOKEN        — GitHub Personal Access Token
    GITHUB_REPO_OWNER   — 仓库所有者 (默认: uwislab)
    GITHUB_REPO_NAME    — 仓库名称   (默认: robotics-systems-course)
"""

import os
import re
import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Feature extraction from Markdown
# ---------------------------------------------------------------------------

# 匹配 ### F-xxx 标题行
FEATURE_RE = re.compile(r"^###\s+(F-[A-Z]-\d{3})\s+(.*)$", re.MULTILINE)

# 功能需求块内的属性标记
ACCEPTANCE_RE = re.compile(r"\*\*验收标准\*\*[：:]?\s*\n(.*?)(?=\n\n|\*\*安全|\*\*优先|\Z)", re.DOTALL)
SECURITY_RE = re.compile(r"\*\*安全属性\*\*[：:]?\s*\n(.*?)(?=\n\n|\*\*优先|\Z)", re.DOTALL)
PRIORITY_RE = re.compile(r"\*\*优先级\*\*[：:]?\s*(P[0-3])", re.IGNORECASE)

# 章节分隔符或下一个 ### 标题
NEXT_SECTION_RE = re.compile(r"\n\n(?=###\s+|##\s+|---)")


def extract_features(content_md: str) -> List[Dict[str, Any]]:
    """从 Markdown 文档中提取所有功能需求块。

    返回:
        [{
            "code": "F-S-001",
            "title": "登录功能",
            "requirement_text": "...",
            "acceptance_criteria": "...",
            "security_attributes": "...",
            "priority": "P0",
            "full_text": "完整的 ### F-xxx 段落内容"
        }]
    """
    features = []
    matches = list(FEATURE_RE.finditer(content_md))

    for idx, m in enumerate(matches):
        code = m.group(1)
        title = m.group(2)

        # 提取从当前标题到下一个功能块或章节分隔符之间的内容
        start = m.end()
        end = len(content_md)

        # 查找结束位置
        next_feature = FEATURE_RE.search(content_md, start)
        if next_feature:
            end = next_feature.start()
        else:
            # 查找下一个 ## 或 ---
            next_boundary = re.search(r"\n(?=##\s+|---)", content_md[start:])
            if next_boundary:
                end = start + next_boundary.start()

        block = content_md[start:end].strip()

        # 提取需求描述（功能块的开头部分，在第一个 **属性标记** 之前）
        requirement_parts = re.split(r"\*\*验收标准\*\*|\*\*安全属性\*\*|\*\*优先级\*\*", block, maxsplit=1)
        requirement_text = requirement_parts[0].strip() if requirement_parts else block

        # 提取验收标准
        acc_match = ACCEPTANCE_RE.search(block)
        acceptance = acc_match.group(1).strip() if acc_match else ""

        # 提取安全属性
        sec_match = SECURITY_RE.search(block)
        security = sec_match.group(1).strip() if sec_match else ""

        # 提取优先级
        pri_match = PRIORITY_RE.search(block)
        priority = pri_match.group(1) if pri_match else "P1"

        features.append({
            "code": code,
            "title": title,
            "requirement_text": requirement_text[:2000],  # 截断
            "acceptance_criteria": acceptance[:2000],
            "security_attributes": security[:2000],
            "priority": priority,
        })

    return features


# ---------------------------------------------------------------------------
# Issue body template
# ---------------------------------------------------------------------------

FEATURE_ISSUE_TEMPLATE = """## 需求描述
{requirement_text}

## 验收标准
{acceptance_criteria}

{security_block}
---
:label: Feature Code: {feature_code}
:pushpin: 优先级: {priority}
"""


def build_issue_body(feature: Dict[str, Any], doc_title: str = "", doc_version: int = 1) -> str:
    """根据功能块数据组装 Issue 正文。"""
    security_block = ""
    if feature.get("security_attributes"):
        security_block = f"## 安全属性\n{feature['security_attributes']}\n"

    body = FEATURE_ISSUE_TEMPLATE.format(
        requirement_text=feature.get("requirement_text", "*待补充*"),
        acceptance_criteria=feature.get("acceptance_criteria", "*待补充*"),
        security_block=security_block,
        feature_code=feature["code"],
        priority=feature.get("priority", "P1"),
    )

    if doc_title:
        body += f"\n:page_facing_up: 来源：{doc_title} (v{doc_version})\n"

    return body


# ---------------------------------------------------------------------------
# GitHub API
# ---------------------------------------------------------------------------

def _get_github_client() -> Any:
    """获取 PyGithub 客户端（懒加载）。"""
    from github import Github, GithubException

    token = os.environ.get("GITHUB_TOKEN", "")
    if not token:
        raise RuntimeError("GITHUB_TOKEN 环境变量未设置")

    return Github(token)


def get_repo():
    """获取仓库对象。"""
    g = _get_github_client()
    owner = os.environ.get("GITHUB_REPO_OWNER", "uwislab")
    repo_name = os.environ.get("GITHUB_REPO_NAME", "robotics-systems-course")
    return g.get_repo(f"{owner}/{repo_name}")


def create_issue(title: str, body: str, labels: Optional[List[str]] = None) -> int:
    """在 GitHub 仓库中创建一个 Issue，返回 Issue 编号。

    如果 GITHUB_TOKEN 未配置，返回 0 表示跳过（不会报错）。
    """
    if not os.environ.get("GITHUB_TOKEN"):
        logger.warning("GITHUB_TOKEN 未设置，跳过 Issue 创建")
        return 0

    from github import GithubException

    try:
        repo = get_repo()
        issue = repo.create_issue(
            title=title,
            body=body,
            labels=labels or ["requirement"],
        )
        logger.info(f"GitHub Issue 创建成功: #{issue.number} - {title}")
        return issue.number
    except GithubException as e:
        logger.error(f"GitHub API 错误: {e.status} {e.data}")
        raise


def create_issues_batch(
    features: List[Dict[str, Any]],
    doc_title: str = "",
    doc_version: int = 1,
    delay: float = 1.0,
) -> List[Dict[str, Any]]:
    """批量创建 Issues，结果按原顺序返回。

    返回:
        [{
            "code": "F-S-001",
            "title": "登录功能",
            "issue_number": 42,   # 成功时
            "status": "created"   # created | skipped | failed
            "error": "..."        # 仅失败时有
        }]
    """
    import time

    if not os.environ.get("GITHUB_TOKEN"):
        # Token 未设置：全部跳过
        return [{
            "code": f["code"],
            "title": f["title"],
            "issue_number": None,
            "status": "skipped",
            "error": "GITHUB_TOKEN 未配置",
        } for f in features]

    results = []
    for f in features:
        try:
            body = build_issue_body(f, doc_title, doc_version)
            issue_no = create_issue(
                title=f"[{f['code']}] {f['title']}",
                body=body,
                labels=["requirement", f["priority"].lower()],
            )
            results.append({
                "code": f["code"],
                "title": f["title"],
                "issue_number": issue_no,
                "status": "created",
            })
        except Exception as e:
            results.append({
                "code": f["code"],
                "title": f["title"],
                "issue_number": None,
                "status": "failed",
                "error": str(e),
            })

        # 避免触发速率限制
        if len(results) < len(features):
            time.sleep(delay)

    return results
