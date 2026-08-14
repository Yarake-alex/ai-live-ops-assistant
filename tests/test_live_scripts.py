import pytest

from tests.test_products import PRODUCT_DATA, _create_second_user, login


LIVE_SCRIPT_SECTIONS = [
    "开场引入",
    "商品卖点讲解",
    "用户痛点刺激",
    "互动提问",
    "优惠逼单",
    "异议回应",
    "结尾转化",
]


@pytest.fixture
def live_script_product_id(client):
    login(client)
    resp = client.post(
        "/products",
        json={**PRODUCT_DATA, "name": "话术测试商品-玻尿酸精华"},
    )
    assert resp.status_code == 200
    return resp.json()["id"]


class TestLiveScriptGeneration:
    @pytest.fixture(autouse=True)
    def _auth(self, client):
        login(client)

    def test_generate_live_script_for_own_product(self, client, live_script_product_id):
        resp = client.post(f"/products/{live_script_product_id}/live-scripts")
        assert resp.status_code == 200

        data = resp.json()
        assert data["product_id"] == live_script_product_id
        assert data["status"] == "success"
        assert data["content"]
        for section in LIVE_SCRIPT_SECTIONS:
            assert section in data["content"]

    def test_generation_record_is_saved(self, client, live_script_product_id):
        create_resp = client.post(f"/products/{live_script_product_id}/live-scripts")
        assert create_resp.status_code == 200
        created = create_resp.json()

        list_resp = client.get(f"/products/{live_script_product_id}/live-scripts")
        assert list_resp.status_code == 200
        records = list_resp.json()
        assert any(item["id"] == created["id"] for item in records)
        assert records[0]["product_id"] == live_script_product_id

    def test_get_live_script_detail(self, client, live_script_product_id):
        create_resp = client.post(f"/products/{live_script_product_id}/live-scripts")
        assert create_resp.status_code == 200
        script_id = create_resp.json()["id"]

        detail_resp = client.get(f"/live-scripts/{script_id}")
        assert detail_resp.status_code == 200
        data = detail_resp.json()
        assert data["id"] == script_id
        assert data["product_id"] == live_script_product_id
        assert "开场引入" in data["content"]

    def test_other_user_cannot_generate_for_my_product(self, client, live_script_product_id):
        other = _create_second_user(client, "live-script-other-user-a")
        resp = other.post(f"/products/{live_script_product_id}/live-scripts")
        assert resp.status_code == 404

    def test_other_user_cannot_view_product_script_history(self, client, live_script_product_id):
        create_resp = client.post(f"/products/{live_script_product_id}/live-scripts")
        assert create_resp.status_code == 200
        script_id = create_resp.json()["id"]

        other = _create_second_user(client, "live-script-other-user-b")
        assert other.get(f"/products/{live_script_product_id}/live-scripts").status_code == 404
        assert other.get(f"/live-scripts/{script_id}").status_code == 404

    def test_llm_failure_returns_local_fallback_script(self, client, live_script_product_id, monkeypatch):
        from fastapi.routing import APIRoute

        route = next(
            r for r in client.app.routes
            if isinstance(r, APIRoute) and r.path == "/products/{product_id}/live-scripts"
        )

        def unavailable_llm(*args, **kwargs):
            return route.endpoint.__globals__["FALLBACK_MESSAGE"]

        monkeypatch.setitem(route.endpoint.__globals__, "call_llm", unavailable_llm)

        resp = client.post(f"/products/{live_script_product_id}/live-scripts")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "fallback"
        assert data["error_message"]
        for section in LIVE_SCRIPT_SECTIONS:
            assert section in data["content"]
