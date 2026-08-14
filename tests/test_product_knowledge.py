import pytest

from tests.test_products import PRODUCT_DATA, _create_second_user, login


class TestProductKnowledge:
    @pytest.fixture(autouse=True)
    def _auth(self, client):
        login(client)

    @pytest.fixture
    def kb_product_id(self, client):
        resp = client.post("/products", json={**PRODUCT_DATA, "name": "知识库测试商品"})
        assert resp.status_code == 200
        pid = resp.json()["id"]
        resp = client.post(
            f"/products/{pid}/knowledge/upload",
            files={
                "file": (
                    "manual.txt",
                    "这款商品主打补水保湿，适合干性皮肤人群，活动期间买二送一。".encode("utf-8"),
                    "text/plain",
                )
            },
        )
        assert resp.status_code == 200
        return pid

    def test_upload_and_list_documents(self, client, kb_product_id):
        resp = client.get(f"/products/{kb_product_id}/knowledge/documents")
        assert resp.status_code == 200
        docs = resp.json()
        assert len(docs) == 1
        assert docs[0]["filename"] == "manual.txt"
        assert docs[0]["chunks"] == 1
        assert docs[0]["preview"]

    def test_ask_returns_answer_with_sources(self, client, kb_product_id):
        resp = client.post(
            f"/products/{kb_product_id}/knowledge/ask",
            json={"question": "这款商品适合什么人群？"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["answer"]
        assert len(data["sources"]) >= 1
        assert data["sources"][0]["filename"] == "manual.txt"

    def test_ask_empty_question_rejected(self, client, kb_product_id):
        resp = client.post(
            f"/products/{kb_product_id}/knowledge/ask",
            json={"question": "   "},
        )
        assert resp.status_code == 422

    def test_ask_without_docs_returns_friendly_answer(self, client):
        resp = client.post("/products", json={"name": "知识库空商品"})
        assert resp.status_code == 200
        pid = resp.json()["id"]
        resp = client.post(
            f"/products/{pid}/knowledge/ask",
            json={"question": "什么卖点？"},
        )
        assert resp.status_code == 200
        assert "还没有知识库资料" in resp.json()["answer"]

    def test_delete_document(self, client, kb_product_id):
        resp = client.delete(f"/products/{kb_product_id}/knowledge/documents/manual.txt")
        assert resp.status_code == 200
        resp = client.get(f"/products/{kb_product_id}/knowledge/documents")
        assert resp.json() == []

    def test_reupload_replaces_chunks(self, client, kb_product_id):
        resp = client.post(
            f"/products/{kb_product_id}/knowledge/upload",
            files={"file": ("manual.txt", "更新后的资料内容".encode("utf-8"), "text/plain")},
        )
        assert resp.status_code == 200
        docs = client.get(f"/products/{kb_product_id}/knowledge/documents").json()
        assert len(docs) == 1
        assert docs[0]["chunks"] == 1
        assert "更新后" in docs[0]["preview"]

    def test_other_user_cannot_access(self, client, kb_product_id):
        other = _create_second_user(client, "kb-other-user")
        assert other.get(f"/products/{kb_product_id}/knowledge/documents").status_code == 404
        assert (
            other.post(
                f"/products/{kb_product_id}/knowledge/ask",
                json={"question": "x"},
            ).status_code
            == 404
        )
        assert (
            other.post(
                f"/products/{kb_product_id}/knowledge/upload",
                files={"file": ("a.txt", b"x", "text/plain")},
            ).status_code
            == 404
        )
        assert (
            other.delete(f"/products/{kb_product_id}/knowledge/documents/manual.txt").status_code
            == 404
        )


class TestDashboardStats:
    @pytest.fixture(autouse=True)
    def _auth(self, client):
        login(client)

    def test_stats_reflect_operations(self, client):
        resp = client.post(
            "/products",
            json={"name": "看板统计商品", "live_status": "直播中"},
        )
        assert resp.status_code == 200
        pid = resp.json()["id"]

        client.post(f"/products/{pid}/live-scripts")
        client.post(f"/products/{pid}/comment-replies", json={"comment": "多少钱？"})
        client.post(f"/products/{pid}/live-reviews")
        client.post(
            f"/products/{pid}/knowledge/upload",
            files={"file": ("stats.txt", "看板统计资料内容".encode("utf-8"), "text/plain")},
        )

        stats = client.get("/dashboard/stats").json()
        assert stats["products"] >= 1
        assert stats["live_products"] >= 1
        assert stats["live_scripts"] >= 1
        assert stats["comment_replies"] >= 1
        assert stats["live_reviews"] >= 1
        assert stats["knowledge_documents"] >= 1

    def test_stats_scoped_by_user(self, client):
        login(client)
        client.post("/products", json={"name": "统计隔离商品"})

        other = _create_second_user(client, "stats-other-user")
        stats = other.get("/dashboard/stats").json()
        assert stats["products"] == 0
        assert stats["live_scripts"] == 0
        assert stats["comment_replies"] == 0
        assert stats["live_reviews"] == 0
        assert stats["knowledge_documents"] == 0
