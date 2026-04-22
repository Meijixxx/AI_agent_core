"""ツールレジストリ: 定義一覧とディスパッチ"""

from typing import Any, Callable

from tools.file_ops import read_file, write_file, edit_file, list_files, search_files
from tools.shell import run_command
from tools.git_tools import git_status, git_diff, git_log
from tools.web import fetch_url
from tools.patch_tool import apply_patch

# ツール実装のマッピング
_TOOL_IMPLS: dict[str, Callable[..., str]] = {
    "read_file": read_file,
    "write_file": write_file,
    "edit_file": edit_file,
    "list_files": list_files,
    "search_files": search_files,
    "run_command": run_command,
    "git_status": git_status,
    "git_diff": git_diff,
    "git_log": git_log,
    "fetch_url": fetch_url,
    "apply_patch": apply_patch,
}

# 書き込み系ツール（実行前にユーザー確認が必要）
DANGEROUS_TOOLS = {"write_file", "edit_file", "run_command", "apply_patch"}

# Ollama API に渡すツール定義
TOOL_DEFINITIONS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read the contents of a file and return it as text",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "File path to read"},
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Create or overwrite a file with the given content",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "File path to write"},
                    "content": {"type": "string", "description": "Content to write"},
                },
                "required": ["path", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "edit_file",
            "description": "Replace a specific text in a file with new text",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "File path to edit"},
                    "old_text": {"type": "string", "description": "Text to find and replace"},
                    "new_text": {"type": "string", "description": "Replacement text"},
                },
                "required": ["path", "old_text", "new_text"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_files",
            "description": "List files in a directory, optionally filtered by glob pattern",
            "parameters": {
                "type": "object",
                "properties": {
                    "directory": {"type": "string", "description": "Directory to list (default: current dir)"},
                    "pattern": {"type": "string", "description": "Glob pattern like '*.py' or '**/*.md'"},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_files",
            "description": "Search for a text pattern in files (like grep). Returns matching lines with file paths.",
            "parameters": {
                "type": "object",
                "properties": {
                    "pattern": {"type": "string", "description": "Text or regex pattern to search for"},
                    "directory": {"type": "string", "description": "Directory to search in (default: current dir)"},
                },
                "required": ["pattern"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_command",
            "description": "Execute a shell command and return stdout/stderr",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "Shell command to execute"},
                },
                "required": ["command"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "git_status",
            "description": "Show git working tree status (short format)",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "git_diff",
            "description": "Show git diff. Set staged=true for staged changes, or specify a path to limit scope.",
            "parameters": {
                "type": "object",
                "properties": {
                    "staged": {"type": "boolean", "description": "Show staged diff instead of working tree diff"},
                    "path": {"type": "string", "description": "Limit diff to this path"},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "git_log",
            "description": "Show recent git commit log (oneline format)",
            "parameters": {
                "type": "object",
                "properties": {
                    "n": {"type": "integer", "description": "Number of commits to show (default: 10, max: 100)"},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "fetch_url",
            "description": "Fetch content of a public HTTP/HTTPS URL. HTML is stripped to text. Internal addresses are blocked.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "URL to fetch"},
                },
                "required": ["url"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "apply_patch",
            "description": "Apply a unified diff patch to files. The diff must include `+++ b/path` lines identifying targets.",
            "parameters": {
                "type": "object",
                "properties": {
                    "diff_text": {"type": "string", "description": "Unified diff content"},
                },
                "required": ["diff_text"],
            },
        },
    },
]


def execute_tool(name: str, arguments: dict[str, Any]) -> str:
    """ツールを名前で実行し、結果を文字列で返す。"""
    impl = _TOOL_IMPLS.get(name)
    if impl is None:
        return f"[エラー] 不明なツール: {name}"
    try:
        return impl(**arguments)
    except Exception as e:
        return f"[エラー] {name} の実行に失敗: {e}"
