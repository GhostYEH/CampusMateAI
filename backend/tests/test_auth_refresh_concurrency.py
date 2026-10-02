from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest

from app.api.routes.auth import _issue_tokens, refresh
from app.core.config import Settings
from app.core.exceptions import Unauthorized
from app.schemas.multi_role import RefreshRequest, TokenPair
from app.services.container import reset_container_for_tests


def test_concurrent_refresh_consumes_token_only_once(monkeypatch):
    settings = Settings(app_env="test", database_url="sqlite:///:memory:")
    container = reset_container_for_tests(settings)
    user = container.user_repository.create_user(
        username="refresh_race", password_hash="unused", role="student"
    )
    tokens = _issue_tokens(user, settings, container)
    request = RefreshRequest(refresh_token=tokens.refresh_token)
    repository = container.refresh_token_repository
    original_lookup = repository.get_by_hash
    both_read = Barrier(2)

    def synchronized_lookup(token_hash):
        stored = original_lookup(token_hash)
        both_read.wait(timeout=5)
        return stored

    monkeypatch.setattr(repository, "get_by_hash", synchronized_lookup)

    def attempt():
        try:
            return refresh(request, settings=settings, container=container)
        except Unauthorized as exc:
            return exc

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda _: attempt(), range(2)))
    assert sum(isinstance(result, TokenPair) for result in results) == 1
    assert sum(isinstance(result, Unauthorized) for result in results) == 1
    with container.db.query() as conn:
        assert conn.execute("SELECT COUNT(*) FROM refresh_tokens WHERE revoked=0").fetchone()[0] == 1

    monkeypatch.setattr(repository, "get_by_hash", original_lookup)
    with pytest.raises(Unauthorized):
        refresh(request, settings=settings, container=container)
    successful = next(result for result in results if isinstance(result, TokenPair))
    assert refresh(RefreshRequest(refresh_token=successful.refresh_token), settings=settings, container=container)
