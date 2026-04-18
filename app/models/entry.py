from typing import Optional
from pydantic import BaseModel, field_validator


class ChecklistItem(BaseModel):
    id: str
    text: str
    checked: bool


class EntryCreate(BaseModel):
    id: str
    title: str
    body: str
    createdAt: str
    updatedAt: str
    accentColor: dict
    theme: str = "neutral"
    tags: list[str] = []
    favorite: bool = False
    pinned: bool = False
    collection: str = ""
    checklist: list[ChecklistItem] = []
    templateId: str = ""
    promptId: str = ""
    relatedEntryIds: list[str] = []

    @field_validator("title")
    @classmethod
    def title_max_length(cls, v):
        v = v.strip()
        if len(v) > 100:
            raise ValueError("title must be 100 characters or fewer")
        return v

    @field_validator("body")
    @classmethod
    def body_non_empty(cls, v):
        v = v.strip()
        if not v:
            raise ValueError("body must not be empty")
        return v


class EntryUpdate(BaseModel):
    title: Optional[str] = None
    body: Optional[str] = None
    updatedAt: str
    accentColor: Optional[dict] = None
    theme: Optional[str] = None
    tags: Optional[list[str]] = None
    favorite: Optional[bool] = None
    pinned: Optional[bool] = None
    collection: Optional[str] = None
    checklist: Optional[list[ChecklistItem]] = None
    templateId: Optional[str] = None
    promptId: Optional[str] = None
    relatedEntryIds: Optional[list[str]] = None

    @field_validator("title")
    @classmethod
    def title_max_length(cls, v):
        if v is None:
            return v
        v = v.strip()
        if len(v) > 100:
            raise ValueError("title must be 100 characters or fewer")
        return v

    @field_validator("body")
    @classmethod
    def body_non_empty(cls, v):
        if v is None:
            return v
        v = v.strip()
        if not v:
            raise ValueError("body must not be empty")
        return v


class EntryResponse(BaseModel):
    id: str
    user_id: str
    title: str
    body: str
    createdAt: str
    updatedAt: str
    accentColor: dict
    theme: str
    tags: list[str]
    favorite: bool
    pinned: bool
    collection: str
    checklist: list[ChecklistItem]
    templateId: str
    promptId: str
    relatedEntryIds: list[str]


class EntryListResponse(BaseModel):
    data: list[EntryResponse]
    total: int
    page: int
    page_size: int
    has_next: bool
