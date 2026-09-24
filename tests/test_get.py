"""GET — чтение данных о Диске и его ресурсах."""

from __future__ import annotations

import pytest

from src.disk_client import DiskClient
from tests.conftest import unique_name

pytestmark = pytest.mark.get


class TestDiskInfo:
    """GET /v1/disk — сведения о Диске."""

    def test_returns_200(self, client: DiskClient):
        assert client.get_disk_info().status_code == 200

    def test_quota_fields_present_and_numeric(self, client: DiskClient):
        body = client.get_disk_info().json()

        for field in ("total_space", "used_space", "trash_size"):
            assert field in body, f"В ответе нет поля {field}"
            assert isinstance(body[field], int), f"{field} должно быть числом"

    def test_used_space_not_greater_than_total(self, client: DiskClient):
        """Занято не может быть больше, чем всего.

        Проверка на внутреннюю согласованность: на конкретные числа
        полагаться нельзя, они меняются, а это соотношение обязано
        выполняться всегда.
        """
        body = client.get_disk_info().json()
        assert body["used_space"] <= body["total_space"]

    def test_fields_parameter_narrows_response(self, client: DiskClient):
        """Параметр fields должен урезать ответ ровно до запрошенного."""
        body = client.get_disk_info(fields="total_space").json()

        assert "total_space" in body
        assert "system_folders" not in body


class TestResourceMeta:
    """GET /v1/disk/resources — метаданные ресурса."""

    def test_root_is_a_directory(self, client: DiskClient):
        body = client.get_resource("disk:/").json()

        assert body["type"] == "dir"
        assert body["path"] == "disk:/"

    def test_created_folder_metadata(self, client: DiskClient, folder: str):
        response = client.get_resource(folder)

        assert response.status_code == 200
        body = response.json()
        assert body["type"] == "dir"
        assert body["path"] == folder
        assert body["name"] == folder.split("/")[-1]

    def test_new_folder_is_empty(self, client: DiskClient, folder: str):
        body = client.get_resource(folder).json()

        assert body["_embedded"]["items"] == []

    def test_uploaded_file_is_visible_in_folder(
        self, client: DiskClient, folder_with_file: tuple[str, str]
    ):
        folder_path, file_path = folder_with_file
        body = client.get_resource(folder_path).json()

        names = [item["name"] for item in body["_embedded"]["items"]]
        assert "sample.txt" in names

    def test_uploaded_file_metadata(
        self, client: DiskClient, folder_with_file: tuple[str, str]
    ):
        _, file_path = folder_with_file
        body = client.get_resource(file_path).json()

        assert body["type"] == "file"
        assert body["size"] > 0
        assert "md5" in body

    def test_limit_parameter_limits_embedded_items(self, client: DiskClient):
        body = client.get_resource("disk:/", limit=1).json()

        assert body["_embedded"]["limit"] == 1
        assert len(body["_embedded"]["items"]) <= 1

    def test_nonexistent_resource_returns_404(self, client: DiskClient):
        response = client.get_resource(f"disk:/{unique_name('missing')}")

        assert response.status_code == 404
        assert response.json()["error"] == "DiskNotFoundError"


class TestDownloadLink:
    """GET /v1/disk/resources/download — ссылка на скачивание."""

    def test_returns_link_for_existing_file(
        self, client: DiskClient, folder_with_file: tuple[str, str]
    ):
        _, file_path = folder_with_file
        response = client.get_download_link(file_path)

        assert response.status_code == 200
        assert response.json()["href"].startswith("https://")
