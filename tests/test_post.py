"""POST — копирование и перемещение ресурсов."""

from __future__ import annotations

import pytest

from src.disk_client import DiskClient
from tests.conftest import TEST_ROOT, unique_name

pytestmark = pytest.mark.post


class TestCopy:
    """POST /v1/disk/resources/copy."""

    def test_copy_file_returns_201(
        self,
        client: DiskClient,
        folder_with_file: tuple[str, str],
        cleanup_paths: list[str],
    ):
        _, source = folder_with_file
        destination = f"{TEST_ROOT}{unique_name('copy')}.txt"

        response = client.copy(source, destination)
        cleanup_paths.append(destination)

        assert response.status_code == 201

    def test_copy_keeps_original(
        self,
        client: DiskClient,
        folder_with_file: tuple[str, str],
        cleanup_paths: list[str],
    ):
        """Копирование не должно трогать источник.

        Отличие копирования от перемещения проверяется явно — это ровно та
        пара операций, которую легко перепутать при рефакторинге.
        """
        _, source = folder_with_file
        destination = f"{TEST_ROOT}{unique_name('copy')}.txt"
        client.copy(source, destination)
        cleanup_paths.append(destination)

        assert client.get_resource(source).status_code == 200
        assert client.get_resource(destination).status_code == 200

    def test_copy_preserves_size(
        self,
        client: DiskClient,
        folder_with_file: tuple[str, str],
        cleanup_paths: list[str],
    ):
        _, source = folder_with_file
        destination = f"{TEST_ROOT}{unique_name('copy')}.txt"
        client.copy(source, destination)
        cleanup_paths.append(destination)

        assert (
            client.get_resource(destination).json()["size"]
            == client.get_resource(source).json()["size"]
        )

    def test_copy_to_existing_path_returns_409(
        self,
        client: DiskClient,
        folder_with_file: tuple[str, str],
        cleanup_paths: list[str],
    ):
        _, source = folder_with_file
        destination = f"{TEST_ROOT}{unique_name('copy')}.txt"
        client.copy(source, destination)
        cleanup_paths.append(destination)

        response = client.copy(source, destination, overwrite=False)

        assert response.status_code == 409

    def test_copy_with_overwrite_succeeds(
        self,
        client: DiskClient,
        folder_with_file: tuple[str, str],
        cleanup_paths: list[str],
    ):
        _, source = folder_with_file
        destination = f"{TEST_ROOT}{unique_name('copy')}.txt"
        client.copy(source, destination)
        cleanup_paths.append(destination)

        response = client.copy(source, destination, overwrite=True)

        assert response.status_code in (201, 202)

    def test_copy_nonexistent_source_returns_404(
        self, client: DiskClient, folder: str
    ):
        missing = f"{TEST_ROOT}{unique_name('missing')}.txt"

        response = client.copy(missing, f"{folder}/never.txt")

        assert response.status_code == 404

    def test_copy_empty_folder_returns_201(
        self, client: DiskClient, folder: str, cleanup_paths: list[str]
    ):
        destination = f"{TEST_ROOT}{unique_name('copied_dir')}"

        response = client.copy(folder, destination)
        cleanup_paths.append(destination)

        assert response.status_code == 201
        assert client.get_resource(destination).json()["type"] == "dir"


class TestMove:
    """POST /v1/disk/resources/move."""

    def test_move_removes_source(
        self,
        client: DiskClient,
        folder_with_file: tuple[str, str],
        cleanup_paths: list[str],
    ):
        _, source = folder_with_file
        destination = f"{TEST_ROOT}{unique_name('moved')}.txt"

        response = client.move(source, destination)
        cleanup_paths.append(destination)

        assert response.status_code in (201, 202)
        assert client.get_resource(source).status_code == 404
        assert client.get_resource(destination).status_code == 200

    def test_rename_within_same_folder(
        self, client: DiskClient, folder_with_file: tuple[str, str]
    ):
        """Переименование — тот же move, только путь отличается именем."""
        folder_path, source = folder_with_file
        destination = f"{folder_path}/renamed.txt"

        response = client.move(source, destination)

        assert response.status_code in (201, 202)
        assert client.get_resource(destination).json()["name"] == "renamed.txt"
