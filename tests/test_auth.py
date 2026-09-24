"""Негативные проверки авторизации и валидации параметров.

Вынесены в отдельный файл: они не про конкретный HTTP-метод, а про то,
как сервис ведёт себя на некорректном входе. Для платного облачного
хранилища это не менее важно, чем happy path.
"""

from __future__ import annotations

import pytest

from src.disk_client import DiskClient

pytestmark = pytest.mark.negative


class TestAuthorization:
    def test_invalid_token_returns_401(self, anonymous_client: DiskClient):
        response = anonymous_client.get_disk_info()

        assert response.status_code == 401

    def test_invalid_token_body_has_error_code(self, anonymous_client: DiskClient):
        """В теле ошибки должен приходить машиночитаемый код.

        Клиентскому приложению нужен не текст на русском, а поле error,
        по которому можно ветвить логику.
        """
        body = anonymous_client.get_disk_info().json()

        assert "error" in body
        assert isinstance(body["error"], str)

    @pytest.mark.parametrize(
        "method_name,args",
        [
            pytest.param("get_resource", ("disk:/",), id="get-resources"),
            pytest.param("create_folder", ("disk:/nope",), id="put-create-folder"),
            pytest.param("delete", ("disk:/nope",), id="delete-resource"),
        ],
    )
    def test_all_endpoints_require_token(
        self, anonymous_client: DiskClient, method_name: str, args: tuple
    ):
        """Ни один эндпоинт не должен пускать без валидного токена."""
        response = getattr(anonymous_client, method_name)(*args)

        assert response.status_code == 401


class TestParameterValidation:
    def test_missing_path_returns_400(self, client: DiskClient):
        """Обязательный параметр path отсутствует — ожидаем 400, не 500."""
        response = client.request("GET", "/resources")

        assert response.status_code == 400

    def test_invalid_sort_field_is_ignored(self, client: DiskClient):
        """Неизвестное значение sort не вызывает ошибку.

        Документация описывает код 400 для некорректных параметров,
        но API игнорирует нераспознанное значение sort и возвращает 200.
        Тест фиксирует фактическое поведение; расхождение отмечено в README.
        """
        response = client.get_resource("disk:/", sort="not_a_field")

        assert response.status_code == 200

    def test_client_rejects_empty_token_early(self):
        """Пустой токен отсекается на конструкторе, без похода в сеть.

        Быстрое падение на очевидно неверной конфигурации экономит время
        отладки: иначе ошибка всплыла бы как невнятный 401 в середине прогона.
        """
        with pytest.raises(ValueError):
            DiskClient("")
