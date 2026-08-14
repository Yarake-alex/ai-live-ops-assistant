import pytest

from tests.test_products import PRODUCT_DATA, _create_second_user, login


REVIEW_SECTIONS = ["用户关注点", "常见异议", "高频问题", "下场直播优化建议"]


@pytest.fixture
def review_product_id(client):
    login(client)
    resp = client.post(
        "/products",
        json={**PRODUCT_DATA, "name": "复盘测试商品"},
    )
    assert resp.status_code == 200
    return resp.json()["id"]


class TestLiveReviews:
    @pytest.fixture(autouse=True)
    def _auth(self, client):
        login(client)

    def test_generate_review_for_own_product(self, client, review_product_id):
        resp = client.post(f"/products/{review_product_id}/live-reviews")
        assert resp.status_code == 200
        data = resp.json()
        assert data["product_id"] == review_product_id
        assert data["status"] == "success"
        for section in REVIEW_SECTIONS:
            assert section in data["content"]

    def test_review_record_saved_and_detail(self, client, review_product_id):
        created = client.post(f"/products/{review_product_id}/live-reviews").json()

        history = client.get(f"/products/{review_product_id}/live-reviews")
        assert history.status_code == 200
        assert any(r["id"] == created["id"] for r in history.json())

        detail = client.get(f"/live-reviews/{created['id']}")
        assert detail.status_code == 200
        assert detail.json()["id"] == created["id"]
        assert detail.json()["product_id"] == review_product_id

    def test_other_user_cannot_access(self, client, review_product_id):
        created = client.post(f"/products/{review_product_id}/live-reviews").json()

        other = _create_second_user(client, "review-other-user")
        assert other.post(f"/products/{review_product_id}/live-reviews").status_code == 404
        assert other.get(f"/products/{review_product_id}/live-reviews").status_code == 404
        assert other.get(f"/live-reviews/{created['id']}").status_code == 404

    def test_ai_failure_returns_local_fallback(self, client, review_product_id, monkeypatch):
        from fastapi.routing import APIRoute

        route = next(
            r for r in client.app.routes
            if isinstance(r, APIRoute) and r.path == "/products/{product_id}/live-reviews"
        )

        def unavailable_llm(*args, **kwargs):
            return route.endpoint.__globals__["FALLBACK_MESSAGE"]

        monkeypatch.setitem(route.endpoint.__globals__, "call_llm", unavailable_llm)

        resp = client.post(f"/products/{review_product_id}/live-reviews")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "fallback"
        assert data["error_message"]
        for section in REVIEW_SECTIONS:
            assert section in data["content"]

    def test_ai_and_fallback_failure_saves_failed_record(
        self, client, review_product_id, monkeypatch
    ):
        from fastapi.routing import APIRoute

        route = next(
            r for r in client.app.routes
            if isinstance(r, APIRoute) and r.path == "/products/{product_id}/live-reviews"
        )

        def unavailable_llm(*args, **kwargs):
            return route.endpoint.__globals__["FALLBACK_MESSAGE"]

        def broken_fallback(*args, **kwargs):
            raise RuntimeError("review-internal-secret")

        monkeypatch.setitem(route.endpoint.__globals__, "call_llm", unavailable_llm)
        monkeypatch.setitem(
            route.endpoint.__globals__, "build_live_review_fallback", broken_fallback
        )

        resp = client.post(f"/products/{review_product_id}/live-reviews")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "failed"
        assert data["error_message"] == "AI 服务暂时不可用，且本地兜底复盘生成失败，请稍后重试"
        assert "review-internal-secret" not in resp.text

        history = client.get(f"/products/{review_product_id}/live-reviews").json()
        assert any(r["id"] == data["id"] for r in history)

    def test_mock_review_triggered_by_feature(self):
        from app.llm import call_llm

        content = call_llm("任意提示词", feature="live_review")
        assert "用户关注点" in content
        assert "下场直播优化建议" in content

    def test_review_prompt_contains_comment_and_reply(self, client, review_product_id):
        """复盘数据源必须包含评论内容和 AI 回复内容。"""
        reply_record = client.post(
            f"/products/{review_product_id}/comment-replies",
            json={"comment": "适合学生吗？"},
        ).json()

        review = client.post(f"/products/{review_product_id}/live-reviews").json()
        assert "适合学生吗？" in review["prompt"]
        assert "回复：" in review["prompt"]
        assert reply_record["reply"][:60] in review["prompt"]

    def test_fallback_detects_missing_product_fields(self, client, monkeypatch):
        """资料不全的商品，兜底复盘应基于原始字段正确识别缺失项。"""
        from fastapi.routing import APIRoute

        login(client)
        resp = client.post("/products", json={"name": "资料不全商品"})
        assert resp.status_code == 200
        pid = resp.json()["id"]

        route = next(
            r for r in client.app.routes
            if isinstance(r, APIRoute) and r.path == "/products/{product_id}/live-reviews"
        )

        def unavailable_llm(*args, **kwargs):
            return route.endpoint.__globals__["FALLBACK_MESSAGE"]

        monkeypatch.setitem(route.endpoint.__globals__, "call_llm", unavailable_llm)

        review = client.post(f"/products/{pid}/live-reviews").json()
        assert review["status"] == "fallback"
        assert "核心卖点" in review["content"]
        assert "适用人群" in review["content"]
        assert "用户痛点" in review["content"]
        # 无评论样本时必须明确说明
        assert "当前评论样本较少" in review["content"]
