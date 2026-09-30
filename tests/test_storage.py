"""Tests for the S3 storage adapter (boto3 client mocked)."""
import io
from unittest.mock import MagicMock

import pytest
from botocore.exceptions import ClientError, EndpointConnectionError

from app.storage.s3 import ObjectNotFoundError, S3Storage, StorageError


def _client_error(code: str) -> ClientError:
    return ClientError({"Error": {"Code": code, "Message": code}}, "Operation")


@pytest.fixture
def client():
    return MagicMock()


@pytest.fixture
def s3(client):
    return S3Storage("http://s3:8333", "key", "secret", "meetings", client=client)


def test_upload_streams_with_content_type(s3, client):
    body = io.BytesIO(b"audio")
    s3.upload("meetings/1/original.wav", body, "audio/wav")
    client.upload_fileobj.assert_called_once_with(
        body, "meetings", "meetings/1/original.wav", ExtraArgs={"ContentType": "audio/wav"}
    )


def test_download_writes_to_destination(s3, client, tmp_path):
    destination = tmp_path / "original.mp3"
    s3.download("meetings/1/original.mp3", destination)
    client.download_file.assert_called_once_with("meetings", "meetings/1/original.mp3", str(destination))


@pytest.mark.parametrize("code", ["404", "NoSuchKey", "NotFound"])
def test_missing_object_raises_not_found(s3, client, tmp_path, code):
    client.download_file.side_effect = _client_error(code)
    with pytest.raises(ObjectNotFoundError):
        s3.download("missing", tmp_path / "x.wav")


def test_other_client_error_raises_storage_error(s3, client):
    client.upload_fileobj.side_effect = _client_error("AccessDenied")
    with pytest.raises(StorageError) as info:
        s3.upload("k", io.BytesIO(b"x"), "audio/wav")
    assert not isinstance(info.value, ObjectNotFoundError)
    assert "AccessDenied" in str(info.value)


def test_connection_error_raises_storage_error(s3, client):
    client.delete_object.side_effect = EndpointConnectionError(endpoint_url="http://s3:8333")
    with pytest.raises(StorageError, match="EndpointConnectionError"):
        s3.delete("k")


def test_delete_uses_bucket_and_key(s3, client):
    s3.delete("meetings/1/original.wav")
    client.delete_object.assert_called_once_with(Bucket="meetings", Key="meetings/1/original.wav")


def test_from_settings_builds_path_style_client():
    from app.core.config import Settings

    settings = Settings(_env_file=None, S3_ENDPOINT="http://s3:8333", S3_ACCESS_KEY="a",
                        S3_SECRET_KEY="b", S3_BUCKET="bucket")
    storage = S3Storage.from_settings(settings)
    assert storage.bucket == "bucket"
    assert storage.client.meta.endpoint_url == "http://s3:8333"
    assert storage.client.meta.config.s3 == {"addressing_style": "path"}
