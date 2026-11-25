from datetime import UTC, datetime
from uuid import uuid4

import pytest

from backend.integrations.base import ProviderRequestContext
from backend.integrations.postgres_raw_repository import PostgresRawPayloadRepository
from backend.integrations.raw import RawPayload

pytestmark = pytest.mark.db


async def test_store_if_new_deduplicates(db_session) -> None:
    repo = PostgresRawPayloadRepository(db_session)
    context = ProviderRequestContext(
        provider_name="test_provider",
        endpoint="/teams",
        requested_at=datetime.now(UTC),
        request_id=str(uuid4()),
    )
    payload = RawPayload.from_request_context(context, {"teams": [{"id": 1, "name": "Arsenal"}]})

    key, created = await repo.store_if_new(payload)
    assert created
    assert await repo.exists(key)

    _, created_again = await repo.store_if_new(payload)
    assert not created_again
    assert await repo.count_by_provider("test_provider") == 1
