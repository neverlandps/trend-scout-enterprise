"""Tests for dialect-agnostic vector search (embeddings, similar, semantic search)."""

import uuid

import pytest

from trend_scout_enterprise.core.config import settings
from trend_scout_enterprise.models.models import LlmProvider, RawItem, Source
from trend_scout_enterprise.models.signal_embedding import SignalEmbedding
from trend_scout_enterprise.services import embedding_service as emb_module
from trend_scout_enterprise.services.embedding_service import (
    EmbeddingService,
    cosine_similarity,
)
from trend_scout_enterprise.services.llm_service import LlmService

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_source(test_db, workspace_id: str, owner_id: str) -> Source:
    source = Source(
        id=uuid.uuid4().hex,
        workspace_id=workspace_id,
        name="Test Source",
        source_type="rss",
        config_encrypted="",
        category="ai",
        owner_id=owner_id,
    )
    test_db.add(source)
    test_db.commit()
    return source


def _make_item(test_db, workspace_id: str, source_id: str, title: str = "Item") -> RawItem:
    item = RawItem(
        id=uuid.uuid4().hex,
        workspace_id=workspace_id,
        source_id=source_id,
        url=f"http://example.com/{uuid.uuid4().hex}",
        title=title,
        summary="summary",
    )
    test_db.add(item)
    test_db.commit()
    return item


def _make_embedding(
    test_db, item: RawItem, vector: list[float], model: str = "test-embed"
) -> SignalEmbedding:
    row = SignalEmbedding(
        id=uuid.uuid4().hex,
        raw_item_id=item.id,
        workspace_id=item.workspace_id,
        embedding=vector,
        model=model,
    )
    test_db.add(row)
    test_db.commit()
    return row


def _fake_llm_service() -> LlmService:
    return LlmService(base_url="http://llm.fake", api_key="k", model="m")


@pytest.fixture
def vector_search_on(monkeypatch):
    monkeypatch.setattr(settings, "vector_search_enabled", True)
    return settings


# ---------------------------------------------------------------------------
# cosine_similarity
# ---------------------------------------------------------------------------


def test_cosine_similarity_orthogonal_is_zero():
    assert cosine_similarity([1.0, 0.0], [0.0, 1.0]) == pytest.approx(0.0)


def test_cosine_similarity_same_direction_is_one():
    assert cosine_similarity([1.0, 2.0, 3.0], [2.0, 4.0, 6.0]) == pytest.approx(1.0)


def test_cosine_similarity_zero_vector_is_zero():
    assert cosine_similarity([0.0, 0.0], [1.0, 1.0]) == 0.0
    assert cosine_similarity([], []) == 0.0


# ---------------------------------------------------------------------------
# EmbeddingService.embed_texts
# ---------------------------------------------------------------------------


class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


class _FakeAsyncClient:
    """Minimal httpx.AsyncClient stand-in returning deterministic embeddings."""

    calls: list[dict] = []

    def __init__(self, timeout=None):
        self.timeout = timeout

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def post(self, url, headers=None, json=None):
        assert url.endswith("/embeddings")
        _FakeAsyncClient.calls.append(json)
        inputs = json["input"]
        return _FakeResponse(
            {
                "data": [
                    {"index": i, "embedding": [float(i), 1.0]}
                    for i, _ in enumerate(inputs)
                ]
            }
        )


async def test_embed_texts_success(monkeypatch):
    _FakeAsyncClient.calls = []
    monkeypatch.setattr(emb_module.httpx, "AsyncClient", _FakeAsyncClient)
    service = EmbeddingService(_fake_llm_service(), model="test-embed")

    vectors = await service.embed_texts(["a", "b"])

    assert vectors == [[0.0, 1.0], [1.0, 1.0]]
    assert _FakeAsyncClient.calls[0]["model"] == "test-embed"


async def test_embed_texts_batches_at_32(monkeypatch):
    _FakeAsyncClient.calls = []
    monkeypatch.setattr(emb_module.httpx, "AsyncClient", _FakeAsyncClient)
    service = EmbeddingService(_fake_llm_service())

    vectors = await service.embed_texts([f"t{i}" for i in range(40)])

    assert len(vectors) == 40
    assert len(_FakeAsyncClient.calls) == 2
    assert len(_FakeAsyncClient.calls[0]["input"]) == 32
    assert len(_FakeAsyncClient.calls[1]["input"]) == 8


# ---------------------------------------------------------------------------
# EmbeddingService.generate_for_items
# ---------------------------------------------------------------------------


async def test_generate_for_items_creates_embeddings(test_db, default_workspace, default_api_key):
    api_key, _ = default_api_key
    source = _make_source(test_db, default_workspace.id, api_key.id)
    items = [_make_item(test_db, default_workspace.id, source.id, title=f"t{i}") for i in range(3)]

    service = EmbeddingService(_fake_llm_service())

    async def fake_embed(texts):
        return [[float(i), 1.0] for i, _ in enumerate(texts)]

    service.embed_texts = fake_embed
    result = await service.generate_for_items(test_db, items)

    assert result == {"embedded": 3, "failed": 0}
    rows = test_db.query(SignalEmbedding).all()
    assert len(rows) == 3
    assert {row.workspace_id for row in rows} == {default_workspace.id}


async def test_generate_for_items_skips_existing(test_db, default_workspace, default_api_key):
    api_key, _ = default_api_key
    source = _make_source(test_db, default_workspace.id, api_key.id)
    item = _make_item(test_db, default_workspace.id, source.id)
    _make_embedding(test_db, item, [1.0, 0.0])

    service = EmbeddingService(_fake_llm_service())

    async def fake_embed(texts):  # pragma: no cover - must not be called
        raise AssertionError("embed_texts should not run for existing embeddings")

    service.embed_texts = fake_embed
    result = await service.generate_for_items(test_db, [item])

    assert result == {"embedded": 0, "failed": 0}
    row = test_db.query(SignalEmbedding).filter_by(raw_item_id=item.id).one()
    assert row.embedding == [1.0, 0.0]


# ---------------------------------------------------------------------------
# GET /signals/{signal_id}/similar
# ---------------------------------------------------------------------------


def _setup_similarity_corpus(test_db, workspace_id: str, owner_id: str):
    """Three items: target=[1,0], near=[1,1] (cos~0.707), far=[0,1] (cos 0)."""
    source = _make_source(test_db, workspace_id, owner_id)
    target = _make_item(test_db, workspace_id, source.id, title="target")
    near = _make_item(test_db, workspace_id, source.id, title="near")
    far = _make_item(test_db, workspace_id, source.id, title="far")
    _make_embedding(test_db, target, [1.0, 0.0])
    _make_embedding(test_db, near, [1.0, 1.0])
    _make_embedding(test_db, far, [0.0, 1.0])
    return target, near, far


def test_similar_endpoint_ordering_and_excludes_self(
    client, test_db, default_workspace, default_api_key, vector_search_on
):
    api_key, _ = default_api_key
    target, near, far = _setup_similarity_corpus(test_db, default_workspace.id, api_key.id)

    resp = client.get(f"/api/v1/signals/{target.id}/similar")

    assert resp.status_code == 200
    results = resp.json()
    assert [r["signal"]["id"] for r in results] == [near.id, far.id]
    assert results[0]["similarity"] > results[1]["similarity"]
    assert all(r["signal"]["id"] != target.id for r in results)


def test_similar_endpoint_404_without_embedding(
    client, test_db, default_workspace, default_api_key, vector_search_on
):
    api_key, _ = default_api_key
    source = _make_source(test_db, default_workspace.id, api_key.id)
    item = _make_item(test_db, default_workspace.id, source.id)

    resp = client.get(f"/api/v1/signals/{item.id}/similar")

    assert resp.status_code == 404


def test_similar_endpoint_503_when_disabled(
    client, test_db, default_workspace, default_api_key
):
    api_key, _ = default_api_key
    target, _, _ = _setup_similarity_corpus(test_db, default_workspace.id, api_key.id)

    resp = client.get(f"/api/v1/signals/{target.id}/similar")

    assert resp.status_code == 503


def test_similar_endpoint_workspace_isolation(
    client, test_db, default_workspace, default_api_key, second_workspace, vector_search_on
):
    api_key, _ = default_api_key
    target, near, _ = _setup_similarity_corpus(test_db, default_workspace.id, api_key.id)
    # A perfectly matching embedding in another workspace must not leak in.
    other_source = _make_source(test_db, second_workspace.id, api_key.id)
    other_item = _make_item(test_db, second_workspace.id, other_source.id, title="other")
    _make_embedding(test_db, other_item, [1.0, 0.0])

    resp = client.get(f"/api/v1/signals/{target.id}/similar")

    assert resp.status_code == 200
    ids = [r["signal"]["id"] for r in resp.json()]
    assert other_item.id not in ids
    assert near.id in ids


# ---------------------------------------------------------------------------
# GET /signals/semantic-search
# ---------------------------------------------------------------------------


def test_semantic_search_top_k(
    client, test_db, default_workspace, default_api_key, vector_search_on, monkeypatch
):
    api_key, _ = default_api_key
    _, near, far = _setup_similarity_corpus(test_db, default_workspace.id, api_key.id)
    test_db.add(
        LlmProvider(
            id=uuid.uuid4().hex,
            name="default",
            base_url="http://llm.fake",
            model="m",
            is_default=True,
        )
    )
    test_db.commit()

    async def fake_embed_texts(self, texts):
        return [[1.0, 0.0] for _ in texts]

    monkeypatch.setattr(EmbeddingService, "embed_texts", fake_embed_texts)

    resp = client.get("/api/v1/signals/semantic-search", params={"q": "anything", "limit": 2})

    assert resp.status_code == 200
    body = resp.json()
    assert body["query"] == "anything"
    assert len(body["results"]) == 2
    # Target itself ([1,0]) ranks first, near ([1,1]) second; far ([0,1]) cut by limit.
    sims = [r["similarity"] for r in body["results"]]
    assert sims == sorted(sims, reverse=True)
    assert body["results"][0]["similarity"] == pytest.approx(1.0)
    assert all(r["signal"]["id"] != far.id for r in body["results"])


def test_semantic_search_503_when_disabled(client, test_db, default_api_key):
    resp = client.get("/api/v1/signals/semantic-search", params={"q": "x"})
    assert resp.status_code == 503
