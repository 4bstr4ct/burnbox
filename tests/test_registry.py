from burnbox.models import Session
from burnbox.providers.registry import ProviderRegistry, select_provider
import pytest


class FakeProvider:
    name: str
    supports_custom_url: bool = False

    def __init__(self, name: str, alive: bool = True):
        self.name = name
        self._alive = alive

    async def is_alive(self) -> bool:
        return self._alive

    async def register(self) -> Session:
        return Session(
            address=f"test@{self.name}.com",
            account_id="1",
            token="t",
            provider_name=self.name,
            created_at=0.0,
        )

    async def restore(self, session: Session) -> None:
        pass

    async def fetch_messages(self, seen_ids: set[str]) -> list:
        return []

    async def delete_account(self, account_id: str) -> bool:
        return True

    async def aclose(self) -> None:
        pass


class TestProviderRegistry:
    def test_register_provider(self):
        reg = ProviderRegistry()
        p = FakeProvider("test")
        reg.register(p)
        assert "test" in reg.list_names()

    def test_get_by_name(self):
        reg = ProviderRegistry()
        p = FakeProvider("test")
        reg.register(p)
        assert reg.get("test") is p

    def test_get_missing_returns_none(self):
        reg = ProviderRegistry()
        assert reg.get("nonexistent") is None

    def test_list_names_ordered(self):
        reg = ProviderRegistry()
        reg.register(FakeProvider("b"))
        reg.register(FakeProvider("a"))
        reg.register(FakeProvider("c"))
        assert reg.list_names() == ["b", "a", "c"]

    def test_all(self):
        reg = ProviderRegistry()
        reg.register(FakeProvider("x"))
        reg.register(FakeProvider("y"))
        assert len(reg.all()) == 2


class TestSelectProvider:
    @pytest.mark.asyncio
    async def test_select_first_alive(self):
        providers = [
            FakeProvider("dead1", alive=False),
            FakeProvider("alive", alive=True),
            FakeProvider("dead2", alive=False),
        ]
        result = await select_provider(providers)
        assert result.name == "alive"

    @pytest.mark.asyncio
    async def test_all_dead_falls_back_to_first(self):
        providers = [
            FakeProvider("dead1", alive=False),
            FakeProvider("dead2", alive=False),
        ]
        result = await select_provider(providers)
        assert result is not None
        assert result.name == "dead1"

    @pytest.mark.asyncio
    async def test_select_specific_provider(self):
        providers = [
            FakeProvider("a", alive=True),
            FakeProvider("b", alive=True),
        ]
        result = await select_provider(providers, preferred="b")
        assert result.name == "b"

    @pytest.mark.asyncio
    async def test_preferred_dead_falls_back(self):
        providers = [
            FakeProvider("a", alive=True),
            FakeProvider("b", alive=False),
        ]
        result = await select_provider(providers, preferred="b")
        assert result.name == "a"

    @pytest.mark.asyncio
    async def test_preferred_not_found(self):
        providers = [FakeProvider("a", alive=True)]
        result = await select_provider(providers, preferred="missing")
        assert result.name == "a"

    @pytest.mark.asyncio
    async def test_empty_list(self):
        result = await select_provider([])
        assert result is None
