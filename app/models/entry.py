from enum import Enum
from typing import Optional
from pydantic import BaseModel, field_validator, model_validator


class JournalType(str, Enum):
    personal = "personal"
    science = "science"
    travel = "travel"
    fitness = "fitness"
    work = "work"
    creative = "creative"

class Theme(str, Enum):
    neutral = "neutral"
    calm = "calm"
    energised = "energised"
    reflective = "reflective"
    heavy = "heavy"
    anxious = "anxious"


JOURNAL_TYPE_METADATA_SCHEMA: dict[JournalType, dict[str, str]] = {
    JournalType.personal: {},
    JournalType.science: {
        "hypothesis": "text",
        "method": "text",
        "results": "text",
        "conclusion": "text",
    },
    JournalType.travel: {
        "location": "text",
        "weather": "text",
        "transport_mode": "text",
    },
    JournalType.fitness: {
        "workout_type": "text",
        "duration_min": "number",
        "rpe": "number",
    },
    JournalType.work: {
        "project": "text",
        "stakeholders": "text",
    },
    JournalType.creative: {
        "genre": "text",
        "word_count_target": "number",
        "draft_number": "number",
    },
}


def _normalize_text_metadata(field_name: str, value: object) -> str:
    if not isinstance(value, str):
        raise ValueError(f"type_metadata.{field_name} must be a string")
    return value.strip()


def _normalize_number_metadata(field_name: str, value: object) -> int | float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"type_metadata.{field_name} must be a number")
    return value


def normalize_type_metadata(journal_type: JournalType, metadata: object) -> dict:
    if metadata is None:
        return {}
    if not isinstance(metadata, dict):
        raise ValueError("type_metadata must be an object")

    allowed_fields = JOURNAL_TYPE_METADATA_SCHEMA[journal_type]
    unexpected_fields = [key for key in metadata.keys() if key not in allowed_fields]
    if unexpected_fields:
        raise ValueError(
            f"type_metadata contains unsupported fields for {journal_type.value}: {', '.join(sorted(unexpected_fields))}"
        )

    normalized = {}
    for field_name, field_kind in allowed_fields.items():
        if field_name not in metadata:
            continue

        raw_value = metadata[field_name]
        if raw_value is None:
            continue

        if field_kind == "text":
            normalized[field_name] = _normalize_text_metadata(field_name, raw_value)
            continue

        if field_kind == "number":
            normalized[field_name] = _normalize_number_metadata(field_name, raw_value)
            continue

        raise ValueError(f"Unsupported metadata field configuration for {field_name}")

    return normalized


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
    theme: Theme = Theme.neutral
    tags: list[str] = []
    favorite: bool = False
    pinned: bool = False
    collection: str = ""
    checklist: list[ChecklistItem] = []
    templateId: str = ""
    promptId: str = ""
    relatedEntryIds: list[str] = []
    journal_type: JournalType = JournalType.personal
    type_metadata: dict = {}

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

    @field_validator("relatedEntryIds")
    @classmethod
    def related_entry_ids_limit(cls, v):
        if len(v) > 8:
            raise ValueError("relatedEntryIds must contain at most 8 ids")
        return v

    @model_validator(mode="after")
    def validate_type_metadata(self):
        self.type_metadata = normalize_type_metadata(self.journal_type, self.type_metadata)
        return self


class EntryUpdate(BaseModel):
    title: Optional[str] = None
    body: Optional[str] = None
    updatedAt: str
    accentColor: Optional[dict] = None
    theme: Optional[Theme] = None
    tags: Optional[list[str]] = None
    favorite: Optional[bool] = None
    pinned: Optional[bool] = None
    collection: Optional[str] = None
    checklist: Optional[list[ChecklistItem]] = None
    templateId: Optional[str] = None
    promptId: Optional[str] = None
    relatedEntryIds: Optional[list[str]] = None
    journal_type: Optional[JournalType] = None
    type_metadata: Optional[dict] = None

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

    @field_validator("relatedEntryIds")
    @classmethod
    def related_entry_ids_limit(cls, v):
        if v is not None and len(v) > 8:
            raise ValueError("relatedEntryIds must contain at most 8 ids")
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
    journal_type: JournalType = JournalType.personal
    type_metadata: dict = {}


class EntryListResponse(BaseModel):
    data: list[EntryResponse]
    total: int
    page: int
    page_size: int
    has_next: bool
