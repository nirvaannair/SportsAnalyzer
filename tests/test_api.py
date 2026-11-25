import pytest
from httpx import ASGITransport, AsyncClient

pytestmark = pytest.mark.db


async def test_health_and_providers(db_session) -> None:  # db_session skips if DB is down
    from backend.api.main import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        health = (await client.get("/api/health")).json()
        assert health["database"]["ok"] is True

        providers = (await client.get("/api/providers")).json()
        names = {p["name"] for p in providers}
        assert {"api_football", "stake"} <= names
        assert all("configured" in p for p in providers)
