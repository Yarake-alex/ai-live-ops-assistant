import pytest

from tests.test_products import PRODUCT_DATA, _create_second_user, login


LIVE_SCRIPT_SECTIONS = [
    "开场",
    "商品介绍",
    "核心卖点",
    "互动与异议处理",
    "促单收口",
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
            assert f"# {section}" in data["content"]

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
        assert "# 开场" in data["content"]

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
            assert f"# {section}" in data["content"]

    def test_ai_exception_returns_fallback_status(self, client, live_script_product_id, monkeypatch):
        """AI 调用直接抛异常时：不 500，返回本地兜底话术，status=fallback。"""
        from fastapi.routing import APIRoute

        route = next(
            r for r in client.app.routes
            if isinstance(r, APIRoute) and r.path == "/products/{product_id}/live-scripts"
        )

        def raising_llm(*args, **kwargs):
            raise RuntimeError("ai-internal-secret")

        monkeypatch.setitem(route.endpoint.__globals__, "call_llm", raising_llm)

        resp = client.post(f"/products/{live_script_product_id}/live-scripts")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "fallback"
        assert data["error_message"] == "AI 服务暂时不可用，已返回本地兜底话术"
        for section in LIVE_SCRIPT_SECTIONS:
            assert f"# {section}" in data["content"]
        # 内部异常细节不得出现在响应中
        assert "ai-internal-secret" not in resp.text

    def test_ai_and_fallback_failure_saves_failed_record(self, client, live_script_product_id, monkeypatch):
        """AI 与本地兜底均失败：记录仍保存，status=failed，error_message 为通用提示。"""
        from fastapi.routing import APIRoute

        route = next(
            r for r in client.app.routes
            if isinstance(r, APIRoute) and r.path == "/products/{product_id}/live-scripts"
        )

        def unavailable_llm(*args, **kwargs):
            return route.endpoint.__globals__["FALLBACK_MESSAGE"]

        def broken_fallback(product):
            raise RuntimeError("fallback-internal-secret")

        monkeypatch.setitem(route.endpoint.__globals__, "call_llm", unavailable_llm)
        monkeypatch.setitem(route.endpoint.__globals__, "build_live_script_fallback", broken_fallback)

        resp = client.post(f"/products/{live_script_product_id}/live-scripts")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "failed"
        assert data["error_message"] == "AI 服务暂时不可用，且本地兜底话术生成失败，请稍后重试"
        assert "fallback-internal-secret" not in resp.text

        # failed 记录也已保存，可通过历史列表追踪
        history = client.get(f"/products/{live_script_product_id}/live-scripts").json()
        assert any(item["id"] == data["id"] for item in history)

    def test_mock_live_script_triggered_by_feature_not_keywords(self):
        """mock 直播话术由 feature 触发，prompt 不含任何话术关键词也应返回七模块。"""
        from app.llm import call_llm

        content = call_llm("请生成一段内容", feature="live_script_generation")
        for section in LIVE_SCRIPT_SECTIONS:
            assert section in content

    def test_record_provider_model_matches_resolver(self, client, live_script_product_id):
        """记录中的 provider/model 与 resolve_llm_provider_model 保持一致。"""
        from app.llm import resolve_llm_provider_model

        resp = client.post(f"/products/{live_script_product_id}/live-scripts")
        assert resp.status_code == 200
        data = resp.json()
        assert (data["provider"], data["model"]) == resolve_llm_provider_model()


class TestScriptQuestionContext:
    """V4 阶段 5：话术生成参考商品问题洞察。"""

    @pytest.fixture(autouse=True)
    def _auth(self, client):
        login(client)

    @staticmethod
    def _create_product(client, name):
        resp = client.post("/products", json={**PRODUCT_DATA, "name": name})
        assert resp.status_code == 200
        return resp.json()["id"]

    @staticmethod
    def _ask(client, pid, question):
        return client.post(f"/products/{pid}/knowledge/ask", json={"question": question})

    def _capture_prompt(self, client, monkeypatch):
        from fastapi.routing import APIRoute

        route = next(
            r for r in client.app.routes
            if isinstance(r, APIRoute) and r.path == "/products/{product_id}/live-scripts"
        )
        captured = {}

        def fake_llm(prompt, *args, **kwargs):
            captured["prompt"] = prompt
            return "话术内容"

        monkeypatch.setitem(route.endpoint.__globals__, "call_llm", fake_llm)
        return captured

    def test_script_without_questions_has_no_qna_module(self, client, monkeypatch):
        pid = self._create_product(client, "话术上下文-无问题商品")
        captured = self._capture_prompt(client, monkeypatch)
        resp = client.post(f"/products/{pid}/live-scripts")
        assert resp.status_code == 200
        # 无问题数据时，prompt 不带问题洞察数据段（指令性文字始终存在）
        assert "直播间问题洞察（来自真实观众" not in captured["prompt"]
        assert "多少钱" not in captured["prompt"]

    def test_script_with_high_freq_questions_contains_qna_module(self, client, monkeypatch):
        pid = self._create_product(client, "话术上下文-高频商品")
        self._ask(client, pid, "多少钱")
        self._ask(client, pid, "多少钱")
        captured = self._capture_prompt(client, monkeypatch)
        resp = client.post(f"/products/{pid}/live-scripts")
        assert resp.status_code == 200
        prompt = captured["prompt"]
        # 高频问题不再新增第六个模块，统一归入固定的「互动与异议处理」标题。
        assert "# 互动与异议处理" in prompt
        assert "多少钱" in prompt
        assert "直播间问题洞察" in prompt

    def test_risk_question_prompt_requires_no_commitment(self, client, monkeypatch):
        pid = self._create_product(client, "话术上下文-风险商品")
        self._ask(client, pid, "孕妇能不能用")
        captured = self._capture_prompt(client, monkeypatch)
        resp = client.post(f"/products/{pid}/live-scripts")
        assert resp.status_code == 200
        prompt = captured["prompt"]
        assert "孕妇能不能用" in prompt
        assert "风险问题只做谨慎引导" in prompt
        assert "资料暂未明确" in prompt

    def test_fallback_script_contains_qna_module_with_questions(self, client, monkeypatch):
        from fastapi.routing import APIRoute

        pid = self._create_product(client, "话术上下文-兜底商品")
        self._ask(client, pid, "多少钱")
        self._ask(client, pid, "多少钱")
        self._ask(client, pid, "孕妇能不能用")

        route = next(
            r for r in client.app.routes
            if isinstance(r, APIRoute) and r.path == "/products/{product_id}/live-scripts"
        )

        def unavailable_llm(*args, **kwargs):
            return route.endpoint.__globals__["FALLBACK_MESSAGE"]

        monkeypatch.setitem(route.endpoint.__globals__, "call_llm", unavailable_llm)
        resp = client.post(f"/products/{pid}/live-scripts")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "fallback"
        assert "# 互动与异议处理" in data["content"]
        assert "多少钱" in data["content"]
        assert "孕妇能不能用" in data["content"]
        assert "医疗" in data["content"]

    def test_helper_failure_does_not_break_script(self, client, monkeypatch):
        from fastapi.routing import APIRoute

        pid = self._create_product(client, "话术上下文-兜底异常商品")
        route = next(
            r for r in client.app.routes
            if isinstance(r, APIRoute) and r.path == "/products/{product_id}/live-scripts"
        )

        def _raise(*args, **kwargs):
            raise RuntimeError("context helper down")

        monkeypatch.setitem(
            route.endpoint.__globals__, "build_script_context_from_questions", _raise
        )
        resp = client.post(f"/products/{pid}/live-scripts")
        assert resp.status_code == 200
        assert resp.json()["content"]

    def test_script_context_scoped_by_user(self, client, monkeypatch):
        # user2 在自己的商品上提问，管理员商品的话术 prompt 不应包含该问题
        pid_admin = self._create_product(client, "话术上下文-用户隔离A")
        other = _create_second_user(client, "script-ctx-other")
        resp = other.post("/products", json={**PRODUCT_DATA, "name": "话术上下文-用户隔离B"})
        assert resp.status_code == 200
        pid_other = resp.json()["id"]
        other.post(f"/products/{pid_other}/knowledge/ask", json={"question": "多少钱"})
        other.post(f"/products/{pid_other}/knowledge/ask", json={"question": "多少钱"})

        login(client)
        from fastapi.routing import APIRoute

        route = next(
            r for r in client.app.routes
            if isinstance(r, APIRoute) and r.path == "/products/{product_id}/live-scripts"
        )
        captured = {}

        def fake_llm(prompt, *args, **kwargs):
            captured["prompt"] = prompt
            return "话术内容"

        monkeypatch.setitem(route.endpoint.__globals__, "call_llm", fake_llm)
        resp = client.post(f"/products/{pid_admin}/live-scripts")
        assert resp.status_code == 200
        assert "多少钱" not in captured["prompt"]

    def test_script_context_scoped_by_user_and_product(self, client, monkeypatch):
        # 商品 A 有"多少钱"问题；商品 B 无问题 → B 的话术 prompt 不应出现"多少钱"
        pid_a = self._create_product(client, "话术上下文-隔离A")
        pid_b = self._create_product(client, "话术上下文-隔离B")
        self._ask(client, pid_a, "多少钱")
        self._ask(client, pid_a, "多少钱")

        captured_b = {}
        from fastapi.routing import APIRoute

        route = next(
            r for r in client.app.routes
            if isinstance(r, APIRoute) and r.path == "/products/{product_id}/live-scripts"
        )

        def fake_llm(prompt, *args, **kwargs):
            captured_b["prompt"] = prompt
            return "话术内容"

        monkeypatch.setitem(route.endpoint.__globals__, "call_llm", fake_llm)
        resp = client.post(f"/products/{pid_b}/live-scripts")
        assert resp.status_code == 200
        # B 商品没有"多少钱"问题 → 其 prompt 不应包含该问题数据
        assert "多少钱" not in captured_b["prompt"]
        assert "直播间问题洞察（来自真实观众" not in captured_b["prompt"]


class TestResolveProviderModel:
    def test_mock_provider_returns_mock(self, monkeypatch):
        from app.config import settings

        monkeypatch.setattr(settings, "LLM_PROVIDER", "mock")
        from app.llm import resolve_llm_provider_model

        assert resolve_llm_provider_model() == ("mock", "mock")

    def test_openai_without_key_returns_mock(self, monkeypatch):
        from app.config import settings

        monkeypatch.setattr(settings, "LLM_PROVIDER", "openai_compatible")
        monkeypatch.setattr(settings, "OPENAI_API_KEY", "")
        from app.llm import resolve_llm_provider_model

        assert resolve_llm_provider_model() == ("mock", "mock")

    def test_openai_with_key_returns_model(self, monkeypatch):
        from app.config import settings

        monkeypatch.setattr(settings, "LLM_PROVIDER", "openai_compatible")
        monkeypatch.setattr(settings, "OPENAI_API_KEY", "sk-test-key")
        monkeypatch.setattr(settings, "OPENAI_MODEL", "deepseek-chat")
        from app.llm import resolve_llm_provider_model

        assert resolve_llm_provider_model() == ("openai_compatible", "deepseek-chat")
