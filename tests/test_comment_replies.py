import pytest

from tests.test_products import PRODUCT_DATA, _create_second_user, login


@pytest.fixture
def comment_reply_product_id(client):
    login(client)
    resp = client.post(
        "/products",
        json={**PRODUCT_DATA, "name": "评论测试商品-保湿精华"},
    )
    assert resp.status_code == 200
    return resp.json()["id"]


class TestCommentReplyGeneration:
    @pytest.fixture(autouse=True)
    def _auth(self, client):
        login(client)

    def test_generate_comment_reply_for_own_product(self, client, comment_reply_product_id):
        resp = client.post(
            f"/products/{comment_reply_product_id}/comment-replies",
            json={"comment": "多少钱？"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["product_id"] == comment_reply_product_id
        assert data["comment"] == "多少钱？"
        assert data["reply"]
        assert data["status"] == "success"
        # prompt 已模板化保存，包含商品资料与评论内容
        assert "评论测试商品-保湿精华" in data["prompt"]
        assert "多少钱？" in data["prompt"]

    def test_mock_success_reply_contains_product_context(self, client, comment_reply_product_id):
        """mock 成功路径的回复必须结合商品信息，而不是固定通用文案。"""
        resp = client.post(
            f"/products/{comment_reply_product_id}/comment-replies",
            json={"comment": "多少钱？"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"
        reply = data["reply"]
        assert "评论测试商品-保湿精华" in reply          # 商品名称
        assert "99.50" in reply                            # 价格
        assert PRODUCT_DATA["promotion"] in reply          # 优惠信息
        assert (
            PRODUCT_DATA["target_audience"] in reply
            or PRODUCT_DATA["selling_points"] in reply
        )                                                   # 适用人群或核心卖点
        for banned in ["全网最低", "百分百", "永久解决"]:
            assert banned not in reply

    def test_mock_reply_conservative_for_sensitive_question(self, client, comment_reply_product_id):
        """敏感肌/效果类问题必须保守表达，不夸大承诺。"""
        resp = client.post(
            f"/products/{comment_reply_product_id}/comment-replies",
            json={"comment": "敏感肌能用吗？"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"
        reply = data["reply"]
        assert "资料里确认过" in reply
        for banned in ["全网最低", "百分百", "永久解决", "绝对有效"]:
            assert banned not in reply

    def test_extract_fields_from_prompt(self):
        """字段解析 helper：能从 prompt 中提取商品字段与评论正文。"""
        from app.llm import _extract_live_comment_reply_fields

        prompt = (
            "商品资料：\n"
            "- 商品名称：测试商品甲\n"
            "- 价格：99.5\n"
            "- 核心卖点：补水保湿\n"
            "- 适用人群：干性皮肤人群\n"
            "- 用户痛点：未填写\n"
            "- 优惠信息：买二送一\n"
            "观众评论：\n"
            "多少钱？\n"
        )
        fields = _extract_live_comment_reply_fields(prompt)
        assert fields["name"] == "测试商品甲"
        assert fields["price"] == "99.5"
        assert fields["selling_points"] == "补水保湿"
        assert fields["target_audience"] == "干性皮肤人群"
        assert fields["pain_points"] == "未填写"
        assert fields["promotion"] == "买二送一"
        assert fields["comment"] == "多少钱？"

    def test_reply_record_is_saved(self, client, comment_reply_product_id):
        create_resp = client.post(
            f"/products/{comment_reply_product_id}/comment-replies",
            json={"comment": "有没有优惠？"},
        )
        assert create_resp.status_code == 200
        created = create_resp.json()

        list_resp = client.get(f"/products/{comment_reply_product_id}/comment-replies")
        assert list_resp.status_code == 200
        records = list_resp.json()
        assert any(item["id"] == created["id"] for item in records)
        assert records[0]["product_id"] == comment_reply_product_id

    def test_get_comment_reply_detail(self, client, comment_reply_product_id):
        create_resp = client.post(
            f"/products/{comment_reply_product_id}/comment-replies",
            json={"comment": "质量怎么样？"},
        )
        assert create_resp.status_code == 200
        reply_id = create_resp.json()["id"]

        detail = client.get(f"/comment-replies/{reply_id}")
        assert detail.status_code == 200
        data = detail.json()
        assert data["id"] == reply_id
        assert data["product_id"] == comment_reply_product_id
        assert data["comment"] == "质量怎么样？"
        assert data["reply"]

    def test_fallback_reply_combines_product_info_and_comment(
        self, client, comment_reply_product_id, monkeypatch
    ):
        """本地兜底回复必须结合商品信息，并针对评论问题给出对应内容。"""
        from fastapi.routing import APIRoute

        route = next(
            r for r in client.app.routes
            if isinstance(r, APIRoute) and r.path == "/products/{product_id}/comment-replies"
        )

        def unavailable_llm(*args, **kwargs):
            return route.endpoint.__globals__["FALLBACK_MESSAGE"]

        monkeypatch.setitem(route.endpoint.__globals__, "call_llm", unavailable_llm)

        # 优惠问题 → 回复包含商品名与优惠信息
        resp = client.post(
            f"/products/{comment_reply_product_id}/comment-replies",
            json={"comment": "有没有优惠？"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "fallback"
        assert "评论测试商品-保湿精华" in data["reply"]
        assert PRODUCT_DATA["promotion"] in data["reply"]

        # 价格问题 → 回复包含价格（Numeric(10,2) 序列化为 99.50）
        resp2 = client.post(
            f"/products/{comment_reply_product_id}/comment-replies",
            json={"comment": "多少钱？"},
        )
        assert resp2.status_code == 200
        assert "99.50" in resp2.json()["reply"]

    def test_other_user_cannot_generate_for_my_product(self, client, comment_reply_product_id):
        other = _create_second_user(client, "comment-other-user-a")
        resp = other.post(
            f"/products/{comment_reply_product_id}/comment-replies",
            json={"comment": "多少钱？"},
        )
        assert resp.status_code == 404

    def test_other_user_cannot_view_history_or_detail(self, client, comment_reply_product_id):
        create_resp = client.post(
            f"/products/{comment_reply_product_id}/comment-replies",
            json={"comment": "多少钱？"},
        )
        assert create_resp.status_code == 200
        reply_id = create_resp.json()["id"]

        other = _create_second_user(client, "comment-other-user-b")
        assert other.get(f"/products/{comment_reply_product_id}/comment-replies").status_code == 404
        assert other.get(f"/comment-replies/{reply_id}").status_code == 404

    def test_empty_comment_rejected(self, client, comment_reply_product_id):
        for bad in ["", "   "]:
            resp = client.post(
                f"/products/{comment_reply_product_id}/comment-replies",
                json={"comment": bad},
            )
            assert resp.status_code == 422

    def test_ai_failure_returns_local_fallback(self, client, comment_reply_product_id, monkeypatch):
        from fastapi.routing import APIRoute

        route = next(
            r for r in client.app.routes
            if isinstance(r, APIRoute) and r.path == "/products/{product_id}/comment-replies"
        )

        def unavailable_llm(*args, **kwargs):
            return route.endpoint.__globals__["FALLBACK_MESSAGE"]

        monkeypatch.setitem(route.endpoint.__globals__, "call_llm", unavailable_llm)

        resp = client.post(
            f"/products/{comment_reply_product_id}/comment-replies",
            json={"comment": "敏感肌能用吗？"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "fallback"
        assert data["error_message"]
        assert data["reply"]

    def test_ai_and_fallback_failure_saves_failed_record(
        self, client, comment_reply_product_id, monkeypatch
    ):
        """AI 与本地兜底均失败：记录仍保存，status=failed，error_message 为通用提示。"""
        from fastapi.routing import APIRoute

        route = next(
            r for r in client.app.routes
            if isinstance(r, APIRoute) and r.path == "/products/{product_id}/comment-replies"
        )

        def unavailable_llm(*args, **kwargs):
            return route.endpoint.__globals__["FALLBACK_MESSAGE"]

        def broken_fallback(product, comment):
            raise RuntimeError("fallback-internal-secret")

        monkeypatch.setitem(route.endpoint.__globals__, "call_llm", unavailable_llm)
        monkeypatch.setitem(
            route.endpoint.__globals__, "build_live_comment_reply_fallback", broken_fallback
        )

        resp = client.post(
            f"/products/{comment_reply_product_id}/comment-replies",
            json={"comment": "多少钱？"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "failed"
        assert data["error_message"] == "AI 服务暂时不可用，且本地兜底回复生成失败，请稍后重试"
        assert "fallback-internal-secret" not in resp.text

        history = client.get(f"/products/{comment_reply_product_id}/comment-replies").json()
        assert any(item["id"] == data["id"] for item in history)

    def test_mock_comment_reply_triggered_by_feature(self):
        """mock 评论回复由 feature="live_comment_reply" 显式分发。"""
        from app.llm import call_llm

        reply = call_llm("任意提示词", feature="live_comment_reply")
        assert reply
