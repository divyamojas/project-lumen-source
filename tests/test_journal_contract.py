import pytest
from pydantic import ValidationError

from app.models.entry import EntryCreate, EntryUpdate, JournalType, normalize_type_metadata
from app.routes.users import UserPreferences, UserPreferencesUpdate


def build_entry_payload(**overrides):
    payload = {
        "id": "entry-123",
        "title": "Science note",
        "body": "Observed the seedlings at noon.",
        "createdAt": "2026-04-20T10:00:00.000Z",
        "updatedAt": "2026-04-20T10:00:00.000Z",
        "accentColor": {"name": "Sky", "bg": "#7BC0FF"},
        "theme": "reflective",
        "tags": ["science"],
        "favorite": False,
        "pinned": False,
        "collection": "Lab",
        "checklist": [],
        "templateId": "",
        "promptId": "",
        "relatedEntryIds": ["entry-100"],
        "journal_type": "science",
        "type_metadata": {
            "hypothesis": "Blue light increases growth rate",
            "method": "Expose tray A to blue light for 4 hours",
            "results": "Tray A grew faster",
            "conclusion": "Promising early signal",
        },
    }
    payload.update(overrides)
    return payload


def test_entry_create_accepts_frontend_metadata_shape():
    entry = EntryCreate(**build_entry_payload())

    assert entry.journal_type.value == "science"
    assert entry.type_metadata["hypothesis"] == "Blue light increases growth rate"


def test_entry_create_rejects_metadata_keys_from_wrong_journal_type():
    with pytest.raises(ValidationError) as exc_info:
        EntryCreate(**build_entry_payload(
            journal_type="travel",
            type_metadata={"hypothesis": "Should not be here"},
        ))

    assert "unsupported fields for travel" in str(exc_info.value)


def test_metadata_validator_rejects_non_numeric_numeric_metadata():
    with pytest.raises(ValueError) as exc_info:
        normalize_type_metadata(JournalType.fitness, {"duration_min": "forty-five"})

    assert "type_metadata.duration_min must be a number" in str(exc_info.value)


def test_user_preferences_require_default_to_be_enabled():
    with pytest.raises(ValidationError) as exc_info:
        UserPreferences(
            enabled_journal_types=["personal", "science"],
            default_journal_type="travel",
        )

    assert "default_journal_type must be included" in str(exc_info.value)


def test_user_preferences_update_deduplicates_enabled_types():
    prefs = UserPreferencesUpdate(
        enabled_journal_types=["personal", "science", "science"],
        default_journal_type="science",
    )

    assert [item.value for item in prefs.enabled_journal_types] == ["personal", "science"]
