from typing import Any, Optional
from pydantic import BaseModel


class ColumnInfo(BaseModel):
    name: str
    type: str
    udt_name: str
    nullable: bool
    default: Optional[str] = None


class IndexInfo(BaseModel):
    name: str
    definition: str


class TableInfo(BaseModel):
    schema: str
    name: str
    columns: list[ColumnInfo]
    indexes: list[IndexInfo] = []


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
