"""ツールレジストリ: 定義一覧とディスパッチ"""

from typing import Any, Callable

from tools.file_ops import (
    read_file, write_file, edit_file, list_files, search_files,
    append_file, get_pdf_info, read_pdf_pages,
)
from tools.shell import run_command
from tools.git_tools import git_status, git_diff, git_log
from tools.web import fetch_url
from tools.patch_tool import apply_patch
from tools.rag_tools import rag_index, rag_search, rag_list, rag_remove, rag_clear

# ツール実装のマッピング
_TOOL_IMPLS: dict[str, Callable[..., str]] = {
    "read_file": read_file,
    "write_file": write_file,
    "append_file": append_file,
    "edit_file": edit_file,
    "list_files": list_files,
    "search_files": search_files,
    "get_pdf_info": get_pdf_info,
    "read_pdf_pages": read_pdf_pages,
    "run_command": run_command,
    "git_status": git_status,
    "git_diff": git_diff,
    "git_log": git_log,
    "fetch_url": fetch_url,
    "apply_patch": apply_patch,
    "rag_index": rag_index,
    "rag_search": rag_search,
    "rag_list": rag_list,
    "rag_remove": rag_remove,
    "rag_clear": rag_clear,
}

# 書き込み系ツール（実行前にユーザー確認が必要）
DANGEROUS_TOOLS = {"write_file", "append_file", "edit_file", "run_command", "apply_patch", "rag_clear"}

# Ollama API に渡すツール定義
TOOL_DEFINITIONS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read the contents of a file and return it as text. Supports .pdf and .docx in addition to text files (text is extracted automatically). Output is truncated at 500 lines.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "File path to read (.txt/.md/.py/.pdf/.docx etc.)"},
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
            "name": "append_file",
            "description": "Append content to the end of a file. Creates the file if it doesn't exist. Use this when writing a large document in multiple chunks.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "File path to append to"},
                    "content": {"type": "string", "description": "Content to append"},
                },
                "required": ["path", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_pdf_info",
            "description": "Get metadata of a PDF file, primarily its total page count. Use this first when processing a large PDF so you know the range.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "PDF file path"},
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_pdf_pages",
            "description": "Read a specific page range from a PDF and return its text (1-indexed, no truncation). Use this to process large PDFs in chunks, e.g. 10 pages at a time.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "PDF file path"},
                    "start_page": {"type": "integer", "description": "Start page (1-indexed, default 1)"},
                    "end_page": {"type": "integer", "description": "End page inclusive (default: same as start_page)"},
                },
                "required": ["path"],
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
    {
        "type": "function",
        "function": {
            "name": "rag_index",
            "description": "Index a file or directory into the RAG vector store so it can be searched later. Supports .txt/.md/.py/.pdf/.docx and more.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "File or directory path to index"},
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "rag_search",
            "description": "Search the RAG index for document chunks relevant to a query. Use this before answering questions about indexed documents.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"},
                    "top_k": {"type": "integer", "description": "Number of results to return (default: 5, max: 10)"},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "rag_list",
            "description": "List all documents currently indexed in the RAG store with their chunk counts.",
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
            "name": "rag_remove",
            "description": "Remove a specific file's chunks from the RAG index.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "File path to remove from the index"},
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "rag_clear",
            "description": "Clear all chunks from the RAG index. This is destructive and cannot be undone.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
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
