"""PUT — создание папок, публикация, заливка файла."""

from __future__ import annotations

import pytest

from src.disk_client import DiskClient
from tests.conftest import TEST_ROOT, unique_name

pytestmark = pytest.mark.put


class TestCreateFolder:
    """PUT /v1/disk/resources — создание папки."""

    def test_returns_201_and_link(self, client: DiskClient, cleanup_paths: list[str]):
        path = f"{TEST_ROOT}{unique_name()}"

        response = client.create_folder(path)
        cleanup_paths.append(path)

        assert response.status_code == 201
        body = response.json()
        assert body["method"] == "GET"
        assert "href" in body

    def test_created_folder_is_readable(
        self, client: DiskClient, cleanup_paths: list[str]
    ):
        """Создание считается успешным только если папка потом читается.

        Проверять один код ответа мало: 201 говорит, что запрос принят,
        а не что ресурс появился. Поэтому сразу за созданием идёт чтение.
        """
        path = f"{TEST_ROOT}{unique_name()}"
        client.create_folder(path)
        cleanup_paths.append(path)

        meta = client.get_resource(path)

        assert meta.status_code == 200
        assert meta.json()["type"] == "dir"

    def test_nested_folder(self, client: DiskClient, folder: str):
        """Вложенная папка создаётся, если родитель существует."""
        nested = f"{folder}/{unique_name('nested')}"

        response = client.create_folder(nested)

        assert response.status_code == 201
        assert client.get_resource(nested).status_code == 200

    def test_duplicate_folder_returns_409(self, client: DiskClient, folder: str):
        """Повторное создание той же папки — конфликт, а не молчаливый успех."""
        response = client.create_folder(folder)

        assert response.status_code == 409
        assert "error" in response.json()

    @pytest.mark.parametrize(
        "name",
        [
            pytest.param("папка с кириллицей", id="cyrillic"),
            pytest.param("folder with spaces", id="spaces"),
            pytest.param("dots.and-dashes_1", id="punctuation"),
        ],
    )
    def test_special_characters_in_name(
        self, client: DiskClient, cleanup_paths: list[str], name: str
    ):
        """Кодирование пути проверяется на именах, где оно легко ломается."""
        path = f"{TEST_ROOT}{unique_name()} {name}"

        response = client.create_folder(path)
        cleanup_paths.append(path)

        assert response.status_code == 201
        assert client.get_resource(path).json()["path"] == path


class TestUpload:
    """PUT по ссылке, полученной из GET /v1/disk/resources/upload."""

    def test_upload_creates_file(self, client: DiskClient, folder: str):
        path = f"{folder}/uploaded.txt"

        response = client.upload_bytes(path, b"hello")

        assert response.status_code in (201, 202)
        assert client.get_resource(path).status_code == 200

    def test_uploaded_size_matches_payload(self, client: DiskClient, folder: str):
        payload = b"x" * 512
        path = f"{folder}/sized.bin"

        client.upload_bytes(path, payload)

        assert client.get_resource(path).json()["size"] == len(payload)

    def test_overwrite_false_does_not_replace_existing(
        self, client: DiskClient, folder: str
    ):
        """Без overwrite повторная заливка не должна затирать файл.

        API отдаёт ошибку уже на этапе получения ссылки, поэтому
        upload_bytes падает на raise_for_status.
        """
        path = f"{folder}/once.txt"
        client.upload_bytes(path, b"original")

        link = client.get_upload_link(path, overwrite=False)

        assert link.status_code == 409


class TestPublish:
    """PUT /v1/disk/resources/publish и /unpublish."""

    def test_publish_returns_200(self, client: DiskClient, folder: str):
        response = client.publish(folder)

        assert response.status_code == 200
        assert "href" in response.json()

    def test_published_resource_gets_public_url(self, client: DiskClient, folder: str):
        """После публикации в метаданных появляются public_key и public_url."""
        client.publish(folder)

        body = client.get_resource(folder).json()

        assert "public_key" in body
        assert body["public_url"].startswith("https://")

    def test_unpublish_removes_public_url(self, client: DiskClient, folder: str):
        client.publish(folder)

        response = client.unpublish(folder)

        assert response.status_code == 200
        assert "public_url" not in client.get_resource(folder).json()
