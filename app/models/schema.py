from typing import Any, Optional
from pydantic import BaseModel, ConfigDict, Field


class ColumnInfo(BaseModel):
    name: str
    type: str
    udt_name: str
    nullable: bool
    default: Optional[str] = None


class IndexInfo(BaseModel):
    name: str
    definition: str


class ConstraintInfo(BaseModel):
    name: str
    constraint_type: str
    definition: str


class TriggerInfo(BaseModel):
    name: str
    timing: str
    events: list[str] = Field(default_factory=list)
    statement: str


class PolicyInfo(BaseModel):
    name: str
    permissive: str
    command: str
    roles: list[str] = Field(default_factory=list)
    using_expression: Optional[str] = None
    with_check_expression: Optional[str] = None


class TableInfo(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    schema_name: str = Field(alias="schema")
    name: str
    columns: list[ColumnInfo]
    indexes: list[IndexInfo] = Field(default_factory=list)
    constraints: list[ConstraintInfo] = Field(default_factory=list)
    triggers: list[TriggerInfo] = Field(default_factory=list)
    policies: list[PolicyInfo] = Field(default_factory=list)


class SchemaSnapshot(BaseModel):
    captured_at: str
    tables: dict[str, TableInfo]


class MigrationRecord(BaseModel):
    filename: str
    status: str       # "applied" | "pending" | "checksum_mismatch"
    checksum: str
    applied_at: Optional[str] = None
    applied_by: Optional[str] = None


class SQLRequest(BaseModel):
    query: str


class SQLResponse(BaseModel):
    query: str
    status: str
    row_count: int
    rows: list[dict[str, Any]]
    duration_ms: int
    executed_at: str
