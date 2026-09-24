"""Клиент REST API Яндекс Диска.

Клиент отвечает только за транспорт: базовый URL, заголовок авторизации,
таймауты, единая сессия. Здесь намеренно нет ни одного assert — проверки
живут в тестах. Если смешать, при падении непонятно, что именно сломалось:
запрос или ожидание теста.

Методы возвращают сырой requests.Response, а не распакованный JSON. Тесту
почти всегда нужен и статус-код, и тело, а иногда только код (204 приходит
с пустым телом) — поэтому разбор оставлен вызывающей стороне.

Документация API: https://yandex.ru/dev/disk/api/concepts/about-docpage/
"""

from __future__ import annotations

from typing import Any

import requests

BASE_URL = "https://cloud-api.yandex.net/v1/disk"
DEFAULT_TIMEOUT = 15


class DiskClient:
    """Обёртка над эндпоинтами Диска, которые покрыты тестами."""

    def __init__(
        self,
        token: str,
        base_url: str = BASE_URL,
        timeout: int = DEFAULT_TIMEOUT,
    ) -> None:
        if not token:
            raise ValueError(
                "OAuth-токен пустой. Задайте переменную окружения YANDEX_DISK_TOKEN."
            )
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Authorization": f"OAuth {token}",
                "Accept": "application/json",
            }
        )

    # ── низкий уровень ──────────────────────────────────────────────

    def request(self, method: str, endpoint: str = "", **kwargs: Any) -> requests.Response:
        """Единая точка выхода наружу.

        Все параметры передаём через `params=`, а не склеиваем строку руками:
        requests сам кодирует путь, а в путях Диска регулярно встречаются
        пробелы и кириллица.
        """
        url = f"{self.base_url}{endpoint}"
        kwargs.setdefault("timeout", self.timeout)
        return self.session.request(method, url, **kwargs)

    # ── GET ─────────────────────────────────────────────────────────

    def get_disk_info(self, **params: Any) -> requests.Response:
        """GET /v1/disk — сведения о Диске: квота, системные папки."""
        return self.request("GET", "", params=params)

    def get_resource(self, path: str, **params: Any) -> requests.Response:
        """GET /v1/disk/resources — метаданные файла или папки."""
        return self.request("GET", "/resources", params={"path": path, **params})

    def get_files(self, **params: Any) -> requests.Response:
        """GET /v1/disk/resources/files — плоский список всех файлов."""
        return self.request("GET", "/resources/files", params=params)

    def get_trash(self, path: str = "/", **params: Any) -> requests.Response:
        """GET /v1/disk/trash/resources — содержимое Корзины."""
        return self.request("GET", "/trash/resources", params={"path": path, **params})

    def get_upload_link(self, path: str, overwrite: bool = False) -> requests.Response:
        """GET /v1/disk/resources/upload — одноразовая ссылка для заливки файла."""
        return self.request(
            "GET",
            "/resources/upload",
            params={"path": path, "overwrite": str(overwrite).lower()},
        )

    def get_download_link(self, path: str) -> requests.Response:
        """GET /v1/disk/resources/download — ссылка на скачивание."""
        return self.request("GET", "/resources/download", params={"path": path})

    # ── PUT ─────────────────────────────────────────────────────────

    def create_folder(self, path: str) -> requests.Response:
        """PUT /v1/disk/resources — создание папки. Успех: 201."""
        return self.request("PUT", "/resources", params={"path": path})

    def publish(self, path: str) -> requests.Response:
        """PUT /v1/disk/resources/publish — открыть публичный доступ. Успех: 200."""
        return self.request("PUT", "/resources/publish", params={"path": path})

    def unpublish(self, path: str) -> requests.Response:
        """PUT /v1/disk/resources/unpublish — закрыть публичный доступ. Успех: 200."""
        return self.request("PUT", "/resources/unpublish", params={"path": path})

    # ── POST ────────────────────────────────────────────────────────

    def copy(self, source: str, destination: str, overwrite: bool = False) -> requests.Response:
        """POST /v1/disk/resources/copy — копирование. Успех: 201, конфликт: 409."""
        return self.request(
            "POST",
            "/resources/copy",
            params={
                "from": source,
                "path": destination,
                "overwrite": str(overwrite).lower(),
            },
        )

    def move(self, source: str, destination: str, overwrite: bool = False) -> requests.Response:
        """POST /v1/disk/resources/move — перемещение или переименование."""
        return self.request(
            "POST",
            "/resources/move",
            params={
                "from": source,
                "path": destination,
                "overwrite": str(overwrite).lower(),
            },
        )

    # ── DELETE ──────────────────────────────────────────────────────

    def delete(self, path: str, permanently: bool = False) -> requests.Response:
        """DELETE /v1/disk/resources.

        204 — удалён файл или пустая папка.
        202 — удаление непустой папки запущено асинхронно.
        """
        return self.request(
            "DELETE",
            "/resources",
            params={"path": path, "permanently": str(permanently).lower()},
        )

    def clear_trash(self, path: str | None = None) -> requests.Response:
        """DELETE /v1/disk/trash/resources — очистка Корзины."""
        params = {"path": path} if path else {}
        return self.request("DELETE", "/trash/resources", params=params)

    # ── составная операция ──────────────────────────────────────────

    def upload_bytes(self, path: str, content: bytes, overwrite: bool = False) -> requests.Response:
        """Загрузка файла: сначала ссылка, затем PUT по ней.

        Второй запрос идёт на другой хост (uploader*.dst.yandex.net) и уже
        без OAuth-заголовка — ссылка сама по себе является пропуском,
        поэтому здесь отдельный requests.put, а не self.session.
        """
        link_response = self.get_upload_link(path, overwrite=overwrite)
        link_response.raise_for_status()
        href = link_response.json()["href"]
        return requests.put(href, data=content, timeout=self.timeout)
