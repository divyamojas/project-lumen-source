from app.services import s3_sync


def test_sync_entry_to_s3_returns_disabled_result_when_backup_is_off(monkeypatch):
    monkeypatch.setattr(s3_sync, "S3_SYNC_ENABLED", False)
    monkeypatch.setattr(s3_sync, "BUCKET", "test-bucket")
    monkeypatch.setattr(s3_sync, "_boto3_available", True)

    result = s3_sync.sync_entry_to_s3("user-1", {"id": "entry-1", "title": "Hello"})

    assert result["success"] is False
    assert result["action"] == "upsert"
    assert result["entry_id"] == "entry-1"
    assert "disabled or unavailable" in result["error"]


def test_sync_entry_to_s3_returns_success_metadata(monkeypatch):
    class FakeS3Client:
        def put_object(self, **kwargs):
            self.kwargs = kwargs

    fake_client = FakeS3Client()
    monkeypatch.setattr(s3_sync, "S3_SYNC_ENABLED", True)
    monkeypatch.setattr(s3_sync, "BUCKET", "test-bucket")
    monkeypatch.setattr(s3_sync, "REGION", "us-east-1")
    monkeypatch.setattr(s3_sync, "_boto3_available", True)
    monkeypatch.setattr(s3_sync, "_get_s3", lambda: fake_client)

    result = s3_sync.sync_entry_to_s3("user-1", {"id": "entry-1", "title": "Hello"})

    assert result["success"] is True
    assert result["bucket"] == "test-bucket"
    assert result["region"] == "us-east-1"
    assert result["object_key"] == "journals/user-1/entry-1.json"


def test_delete_entry_from_s3_returns_failure_details(monkeypatch):
    class FakeS3Client:
        def delete_object(self, **kwargs):
            raise RuntimeError("boom")

    monkeypatch.setattr(s3_sync, "S3_SYNC_ENABLED", True)
    monkeypatch.setattr(s3_sync, "BUCKET", "test-bucket")
    monkeypatch.setattr(s3_sync, "_boto3_available", True)
    monkeypatch.setattr(s3_sync, "_get_s3", lambda: FakeS3Client())

    result = s3_sync.delete_entry_from_s3("user-1", "entry-9")

    assert result["success"] is False
    assert result["action"] == "delete"
    assert result["entry_id"] == "entry-9"
    assert result["object_key"] == "journals/user-1/entry-9.json"
    assert result["error"] == "boom"
