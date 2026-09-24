"""DELETE — удаление ресурсов и работа с Корзиной."""

from __future__ import annotations

import pytest

from src.disk_client import DiskClient
from tests.conftest import TEST_ROOT, unique_name

pytestmark = pytest.mark.delete


class TestDeleteResource:
    """DELETE /v1/disk/resources."""

    def test_delete_empty_folder_returns_204(
        self, client: DiskClient, cleanup_paths: list[str]
    ):
        """Пустая папка удаляется синхронно: 204 и пустое тело."""
        path = f"{TEST_ROOT}{unique_name()}"
        client.create_folder(path)

        response = client.delete(path, permanently=True)

        assert response.status_code == 204
        assert response.text == ""

    def test_deleted_resource_is_gone(self, client: DiskClient):
        path = f"{TEST_ROOT}{unique_name()}"
        client.create_folder(path)

        client.delete(path, permanently=True)

        assert client.get_resource(path).status_code == 404

    def test_delete_file_returns_204(self, client: DiskClient, folder: str):
        path = f"{folder}/to_delete.txt"
        client.upload_bytes(path, b"temporary")

        response = client.delete(path, permanently=True)

        assert response.status_code == 204

    def test_delete_non_empty_folder_returns_202(
        self, client: DiskClient, folder_with_file: tuple[str, str]
    ):
        """Непустая папка удаляется асинхронно: 202 и ссылка на операцию.

        Разные коды для пустой и непустой папки — поведение, которое легко
        сломать оптимизацией на стороне сервиса, поэтому проверяется отдельно.
        """
        folder_path, _ = folder_with_file

        response = client.delete(folder_path, permanently=True)

        assert response.status_code == 202
        assert "href" in response.json()

    def test_delete_nonexistent_returns_404(self, client: DiskClient):
        response = client.delete(f"{TEST_ROOT}{unique_name('missing')}")

        assert response.status_code == 404

    def test_delete_is_not_idempotent_for_missing_resource(self, client: DiskClient):
        """Повторное удаление отвечает 404, а не 204.

        Проверка фиксирует текущий контракт: клиент по коду ответа может
        отличить «удалил» от «нечего удалять».
        """
        path = f"{TEST_ROOT}{unique_name()}"
        client.create_folder(path)

        first = client.delete(path, permanently=True)
        second = client.delete(path, permanently=True)

        assert first.status_code == 204
        assert second.status_code == 404


class TestTrash:
    """Удаление в Корзину против безвозвратного."""

    def test_soft_delete_puts_resource_in_trash(self, client: DiskClient):
        name = unique_name()
        path = f"{TEST_ROOT}{name}"
        client.create_folder(path)

        client.delete(path, permanently=False)

        trash = client.get_trash("trash:/", limit=100).json()
        names = [item["name"] for item in trash["_embedded"]["items"]]
        assert name in names

        client.clear_trash(path=name)

    def test_permanent_delete_skips_trash(self, client: DiskClient):
        name = unique_name()
        path = f"{TEST_ROOT}{name}"
        client.create_folder(path)

        client.delete(path, permanently=True)

        trash = client.get_trash("trash:/", limit=100).json()
        names = [item["name"] for item in trash["_embedded"]["items"]]
        assert name not in names
