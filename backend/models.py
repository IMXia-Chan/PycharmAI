"""请求/响应数据模型(Pydantic)。"""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class CodeInput(BaseModel):
    code: str
    language: str = "python"
    filename: Optional[str] = None
    line: Optional[int] = None


class Issue(BaseModel):
    category: str = "nonstandard"  # error | nonstandard | style
    title: str = ""
    message: str = ""
    suggestion: str = ""
    severity: str = "warning"      # error | warning | info
    line: int = 0                  # 问题所在行号(1 起);0 = 未指明


class AnalyzeResult(BaseModel):
    issues: list[Issue] = Field(default_factory=list)
    source: str = "ai"             # ai | rules | mixed


class FunctionCandidate(BaseModel):
    name: str
    signature: str = ""
    module: str = ""
    description: str = ""


class SearchResult(BaseModel):
    candidates: list[FunctionCandidate] = Field(default_factory=list)


class CompareInput(BaseModel):
    function_a: str
    function_b: str


class CompareResult(BaseModel):
    summary: str = ""
    differences: list[dict] = Field(default_factory=list)


class RecordIn(BaseModel):
    code: str = ""
    filename: str = ""
    line: int = 0
    category: str = "unknown"
    title: str = ""
    message: str = ""
    severity: str = "info"


class NoteIn(BaseModel):
    title: str = ""
    content: str = ""


class Record(BaseModel):
    id: str = ""
    code: str = ""
    filename: str = ""
    line: int = 0
    category: str = "unknown"
    title: str = ""
    message: str = ""
    severity: str = "info"
    ai_analysis: str = ""
    created_at: str = ""


class Note(BaseModel):
    id: str = ""
    title: str = ""
    content: str = ""
    created_at: str = ""


class ChatIn(BaseModel):
    question: str = ""


class ChatResult(BaseModel):
    reply: str = ""


class TextIn(BaseModel):
    text: str = ""


class TextResult(BaseModel):
    text: str = ""


class CodeResult(BaseModel):
    code: str = ""


class SnippetIn(BaseModel):
    title: str = ""
    code: str = ""
    note: str = ""


class Snippet(BaseModel):
    id: str = ""
    title: str = ""
    code: str = ""
    note: str = ""
    created_at: str = ""


class LibraryIn(BaseModel):
    name: str = ""


class LibraryItemIn(BaseModel):
    kind: str = "note"   # note | file
    ref_id: str = ""
    title: str = ""
    content: str = ""


class LibraryItem(BaseModel):
    id: str = ""
    library_id: str = ""
    kind: str = "note"   # note | file
    ref_id: str = ""
    title: str = ""
    content: str = ""
    created_at: str = ""


class Library(BaseModel):
    id: str = ""
    name: str = ""
    created_at: str = ""
    items: list[LibraryItem] = Field(default_factory=list)
