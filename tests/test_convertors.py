from collections.abc import Iterator
from datetime import datetime
from uuid import UUID

import pytest

from speedy import convertors
from speedy.convertors import Convertor, register_url_convertor
from speedy.requests import Request
from speedy.responses import JSONResponse
from speedy.routing import Route, Router
from tests.types import TestClientFactory


@pytest.fixture(scope="module", autouse=True)
def refresh_convertor_types() -> Iterator[None]:
    saved = convertors.CONVERTOR_TYPES.copy()
    yield
    convertors.CONVERTOR_TYPES.clear()
    convertors.CONVERTOR_TYPES.update(saved)


class DateTimeConvertor(Convertor[datetime]):
    regex = "[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(.[0-9]+)?"

    def convert(self, value: str) -> datetime:
        return datetime.strptime(value, "%Y-%m-%dT%H:%M:%S")

    def to_string(self, value: datetime) -> str:
        return value.strftime("%Y-%m-%dT%H:%M:%S")


@pytest.fixture
def app() -> Router:
    register_url_convertor("datetime", DateTimeConvertor())

    def datetime_convertor(request: Request) -> JSONResponse:
        param = request.path_params["param"]
        assert isinstance(param, datetime)
        return JSONResponse({"datetime": param.strftime("%Y-%m-%dT%H:%M:%S")})

    return Router(
        routes=[
            Route(
                "/datetime/{param:datetime}",
                endpoint=datetime_convertor,
                name="datetime-convertor",
            )
        ]
    )


class TestCustomConvertor:
    def test_datetime(self, test_client_factory: TestClientFactory, app: Router) -> None:
        client = test_client_factory(app)
        response = client.get("/datetime/2020-01-01T00:00:00")
        assert response.json() == {"datetime": "2020-01-01T00:00:00"}

        url_path = app.url_path_for("datetime-convertor", param=datetime(1996, 1, 22, 23, 0, 0))
        assert url_path == "/datetime/1996-01-22T23:00:00"


class TestFloatConvertor:
    @pytest.mark.parametrize(
        ("param", "status_code"),
        [
            pytest.param("1.0", 200, id="decimal_point"),
            pytest.param("1-0", 404, id="dash_instead_of_point"),
        ],
    )
    def test_default(self, test_client_factory: TestClientFactory, param: str, status_code: int) -> None:
        def float_convertor(request: Request) -> JSONResponse:
            param = request.path_params["param"]
            assert isinstance(param, float)
            return JSONResponse({"float": param})

        app = Router(routes=[Route("/{param:float}", endpoint=float_convertor)])

        client = test_client_factory(app)
        response = client.get(f"/{param}")
        assert response.status_code == status_code


class TestUUIDConvertor:
    @pytest.mark.parametrize(
        ("param", "status_code"),
        [
            pytest.param("00000000-aaaa-ffff-9999-000000000000", 200, id="lowercase_with_dashes"),
            pytest.param("00000000aaaaffff9999000000000000", 200, id="lowercase_without_dashes"),
            pytest.param("00000000-AAAA-FFFF-9999-000000000000", 200, id="uppercase_with_dashes"),
            pytest.param("00000000AAAAFFFF9999000000000000", 200, id="uppercase_without_dashes"),
            pytest.param("not-a-uuid", 404, id="not_a_uuid"),
        ],
    )
    def test_default(self, test_client_factory: TestClientFactory, param: str, status_code: int) -> None:
        def uuid_convertor(request: Request) -> JSONResponse:
            param = request.path_params["param"]
            assert isinstance(param, UUID)
            return JSONResponse("ok")

        app = Router(routes=[Route("/{param:uuid}", endpoint=uuid_convertor)])

        client = test_client_factory(app)
        response = client.get(f"/{param}")
        assert response.status_code == status_code
