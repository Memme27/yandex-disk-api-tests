"""Общие фикстуры.

Главный принцип: каждый тест получает чистое окружение и убирает за собой.
Тесты идут против живого API, поэтому мусор, оставленный упавшим тестом,
ломает следующий прогон. Отсюда две вещи:

1. Уникальные имена. Каждая папка называется autotest_<8 hex-символов>.
   Два прогона подряд не конфликтуют, параллельный запуск тоже.
2. Уборка в teardown через yield. Она выполняется, даже если тест упал,
   и намеренно игнорирует ошибки удаления: если тест и так красный,
   второе исключение из фикстуры только спрячет настоящую причину.
"""

from __future__ import annotations

import os
import uuid

import pytest
import requests

from src.disk_client import BASE_URL, DiskClient

TOKEN_ENV = "YANDEX_DISK_TOKEN"
TEST_ROOT = "disk:/"


def unique_name(prefix: str = "autotest") -> str:
    """Имя, не совпадающее с уже существующими на Диске."""
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


@pytest.fixture(scope="session")
def token() -> str:
    """OAuth-токен тестового аккаунта.

    Токен читается только из окружения и никогда не попадает в репозиторий.
    Если его нет — тесты пропускаются, а не падают: красный прогон означал бы
    дефект в продукте, а здесь дефект в настройке запуска.
    """
    value = os.environ.get(TOKEN_ENV, "").strip()
    if not value:
        pytest.skip(
            f"Не задан {TOKEN_ENV}. Токен получается на полигоне: "
            "https://yandex.ru/dev/disk/poligon/"
        )
    return value


@pytest.fixture(scope="session")
def client(token: str) -> DiskClient:
    """Один клиент на сессию — переиспользуем TCP-соединение."""
    return DiskClient(token)


@pytest.fixture(scope="session")
def anonymous_client() -> DiskClient:
    """Клиент с заведомо неверным токеном — для проверок авторизации."""
    return DiskClient("invalid-token-for-negative-tests")


@pytest.fixture
def folder(client: DiskClient) -> str:
    """Пустая папка в корне Диска. Удаляется после теста.

    Возвращает путь вида `disk:/autotest_1a2b3c4d`.
    """
    path = f"{TEST_ROOT}{unique_name()}"
    response = client.create_folder(path)
    assert response.status_code == 201, (
        f"Не удалось подготовить папку для теста: "
        f"{response.status_code} {response.text}"
    )

    yield path

    client.delete(path, permanently=True)


@pytest.fixture
def folder_with_file(client: DiskClient, folder: str) -> tuple[str, str]:
    """Папка с одним небольшим текстовым файлом внутри.

    Отдельная фикстура, потому что часть проверок (копирование, публикация,
    скачивание, удаление непустой папки) требует именно файла, а не пустой
    директории — у них разное поведение и разные коды ответа.
    """
    file_path = f"{folder}/sample.txt"
    response = client.upload_bytes(file_path, b"yandex disk autotest payload")
    assert response.status_code in (201, 202), (
        f"Не удалось загрузить файл для теста: "
        f"{response.status_code} {response.text}"
    )
    return folder, file_path


@pytest.fixture
def cleanup_paths(client: DiskClient):
    """Список путей, которые нужно удалить после теста.

    Нужна там, где ресурс создаёт сам тест (например, проверяет копирование
    и заранее не знает путь копии). Тест дописывает путь в список,
    фикстура удаляет всё в обратном порядке.
    """
    paths: list[str] = []

    yield paths

    for path in reversed(paths):
        client.delete(path, permanently=True)
