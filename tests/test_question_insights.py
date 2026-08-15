import pytest

from app.question_insights import classify_question, normalize_question
from tests.test_products import login


# ─── 归一化与分类（纯函数） ───


class TestQuestionNormalize:
    def test_normalize_lower_strip_punctuation(self):
        assert normalize_question(" 多少钱？ ") == "多少钱"
        assert normalize_question("Hello, World!") == "helloworld"
        assert normalize_question("") == ""

    def test_normalize_truncates_to_500(self):
        assert len(normalize_question("长" * 600)) == 500


class TestQuestionClassify:
    CASES = [
        ("多少钱", "price"),
        ("有库存吗", "stock"),
        ("有没有优惠", "promotion"),
        ("适合什么人", "audience"),
        ("有什么卖点", "selling_points"),
        ("怎么用", "usage"),
        ("怎么退换货", "after_sales"),
        ("孕妇能不能用", "risk"),
        ("今天天气不错", "other"),
    ]

    @pytest.mark.parametrize("question,expected", CASES)
    def test_classify(self, question, expected):
        assert classify_question(question) == expected

    def test_risk_priority_over_audience(self):
        # 含 risk 关键词时不得被误判为 audience
        assert classify_question("孕妇敏感肌能不能用") == "risk"
        assert classify_question("儿童适合什么人用") == "risk"


# ─── 接口埋点（session client，mock LLM，无真实外部 API） ───


class TestQuestionLogRecording:
    @pytest.fixture(autouse=True)
    def _auth(self, client):
        login(client)

    @staticmethod
    def _app_objects(client):
        """从 client 所属 app 的模块命名空间取 SessionLocal / 模型 / helper 模块。

        其他测试文件（如向量测试）会重载 app.* 模块，直接 import 会拿到
        过期模块并指向已被删除的临时库；这里从 app 自身引用解析，保证
        与 session 级 client 使用同一套对象。
        """
        from fastapi.routing import APIRoute

        route = next(
            r for r in client.app.routes
            if isinstance(r, APIRoute) and r.path == "/products/{product_id}/knowledge/ask"
        )
        g = route.endpoint.__globals__
        session_local = g["get_db"].__globals__["SessionLocal"]
        qi_module = g["record_product_question"].__globals__
        model = qi_module["ProductQuestionLog"]
        return session_local, model, qi_module

    def _logs_for_product(self, client, product_id):
        session_local, model, _ = self._app_objects(client)
        with session_local() as db:
            return (
                db.query(model)
                .filter(model.product_id == product_id)
                .order_by(model.id.asc())
                .all()
            )

    @staticmethod
    def _create_product(client):
        resp = client.post(
            "/products", json={"name": "问题日志商品", "price": 99, "stock": 50}
        )
        assert resp.status_code == 200
        return resp.json()["id"]

    @staticmethod
    def _patch_llm(monkeypatch, client, answer="回答内容"):
        """把 ask 路由的 call_llm 替换为固定回答，保证 answer_mode 确定。"""
        from fastapi.routing import APIRoute

        route = next(
            r for r in client.app.routes
            if isinstance(r, APIRoute) and r.path == "/products/{product_id}/knowledge/ask"
        )
        monkeypatch.setitem(
            route.endpoint.__globals__, "call_llm", lambda *a, **k: answer
        )

    def test_ask_records_log_with_knowledge_answer(self, client, monkeypatch):
        pid = self._create_product(client)
        client.post(
            f"/products/{pid}/knowledge/upload",
            files={
                "file": (
                    "faq.txt",
                    "这款商品适合干性皮肤人群，买二送一。".encode("utf-8"),
                    "text/plain",
                )
            },
        )
        self._patch_llm(monkeypatch, client)

        resp = client.post(
            f"/products/{pid}/knowledge/ask", json={"question": "适合什么人群？"}
        )
        assert resp.status_code == 200

        logs = self._logs_for_product(client, pid)
        assert len(logs) == 1
        log = logs[0]
        assert log.source == "product_knowledge_ask"
        assert log.question == "适合什么人群？"
        assert log.normalized_question == "适合什么人群"
        assert log.category == "audience"
        assert log.answer_mode == "product_knowledge"
        assert log.was_answered is True

    def test_ask_without_docs_records_no_match(self, client):
        pid = self._create_product(client)
        # 用非本地快答类问题（usage）验证无资料 → no_match
        resp = client.post(
            f"/products/{pid}/knowledge/ask", json={"question": "怎么用？"}
        )
        assert resp.status_code == 200

        logs = self._logs_for_product(client, pid)
        assert len(logs) == 1
        assert logs[0].answer_mode == "no_match"
        assert logs[0].was_answered is False
        assert logs[0].category == "usage"

    def test_ask_without_retrieval_records_no_match(self, client):
        pid = self._create_product(client)
        client.post(
            f"/products/{pid}/knowledge/upload",
            files={
                "file": (
                    "faq.txt",
                    "苹果香蕉梨的内容。".encode("utf-8"),
                    "text/plain",
                )
            },
        )
        resp = client.post(
            f"/products/{pid}/knowledge/ask", json={"question": "敏感肌能用吗？"}
        )
        assert resp.status_code == 200

        logs = self._logs_for_product(client, pid)
        assert len(logs) == 1
        assert logs[0].answer_mode == "no_match"
        assert logs[0].was_answered is False

    def test_comment_reply_records_log(self, client):
        pid = self._create_product(client)
        resp = client.post(
            f"/products/{pid}/comment-replies", json={"comment": "有优惠吗？"}
        )
        assert resp.status_code == 200

        logs = self._logs_for_product(client, pid)
        assert len(logs) == 1
        log = logs[0]
        assert log.source == "comment_reply"
        assert log.question == "有优惠吗？"
        assert log.category == "promotion"
        assert log.answer_mode == "llm"  # mock LLM 生成成功
        assert log.was_answered is True

    def test_logs_scoped_by_user_and_product(self, client):
        pid_a = self._create_product(client)
        client.post(
            f"/products/{pid_a}/knowledge/upload",
            files={"file": ("faq.txt", "商品A的资料内容。".encode("utf-8"), "text/plain")},
        )
        # 商品 A 提问一次
        client.post(
            f"/products/{pid_a}/knowledge/ask", json={"question": "适合什么人群？"}
        )
        # 商品 B 提问一次
        resp = client.post("/products", json={"name": "问题日志商品B"})
        pid_b = resp.json()["id"]
        client.post(
            f"/products/{pid_b}/knowledge/ask", json={"question": "多少钱？"}
        )

        logs_a = self._logs_for_product(client, pid_a)
        logs_b = self._logs_for_product(client, pid_b)
        assert len(logs_a) == 1 and logs_a[0].question == "适合什么人群？"
        assert len(logs_b) == 1 and logs_b[0].question == "多少钱？"
        assert logs_a[0].product_id == pid_a
        assert logs_b[0].product_id == pid_b

        # 其他用户访问商品 A 的问答直接 404，不会产生该商品的日志
        other = self._create_second_user(client, "qlog-other")
        assert (
            other.post(
                f"/products/{pid_a}/knowledge/ask", json={"question": "x"}
            ).status_code
            == 404
        )
        session_local, model, _ = self._app_objects(client)
        with session_local() as db:
            cross = (
                db.query(model)
                .filter(model.product_id == pid_a)
                .count()
            )
        assert cross == 1

    def test_record_failure_does_not_break_ask(self, client, monkeypatch):
        pid = self._create_product(client)
        client.post(
            f"/products/{pid}/knowledge/upload",
            files={"file": ("faq.txt", "这款商品适合干性皮肤。".encode("utf-8"), "text/plain")},
        )
        self._patch_llm(monkeypatch, client)

        class _Boom:
            def __init__(self, **kwargs):
                raise RuntimeError("db unavailable")

        # qi_globals 是 app 所引用旧模块的 __dict__（模块本身不在 sys.modules 中），
        # 直接改字典即可让 app 内的 record_product_question 看到替换后的模型类。
        _, _, qi_globals = self._app_objects(client)
        monkeypatch.setitem(qi_globals, "ProductQuestionLog", _Boom)
        resp = client.post(
            f"/products/{pid}/knowledge/ask", json={"question": "适合什么人群？"}
        )
        # 记录失败绝不能影响问答主流程
        assert resp.status_code == 200
        assert resp.json()["answer"]

    # ── helpers ──

    @staticmethod
    def _create_second_user(client, username):
        login(client)
        client.post(
            "/auth/users",
            json={"username": username, "password": "second-user-password"},
        )
        client.cookies.clear()
        resp = client.post(
            "/auth/login",
            json={"username": username, "password": "second-user-password"},
        )
        assert resp.status_code == 200
        return client


# ─── 本地快答（V3 阶段 B） ───


FULL_PRODUCT = {
    "name": "快答商品",
    "price": 129,
    "stock": 50,
    "selling_points": "舒缓泛红、修护屏障",
    "target_audience": "熬夜肌、换季敏感人群",
    "promotion": "直播间拍一发二",
    "live_status": "直播中",
}


class TestLocalProductAnswer:
    @pytest.fixture(autouse=True)
    def _auth(self, client):
        login(client)

    @staticmethod
    def _create_product(client, data=None):
        resp = client.post("/products", json=data if data is not None else FULL_PRODUCT)
        assert resp.status_code == 200
        return resp.json()["id"]

    @staticmethod
    def _ask(client, pid, question):
        return client.post(f"/products/{pid}/knowledge/ask", json={"question": question})

    @staticmethod
    def _logs_for_product(client, pid):
        session_local, model, _ = TestQuestionLogRecording._app_objects(client)
        with session_local() as db:
            return (
                db.query(model)
                .filter(model.product_id == pid)
                .order_by(model.id.asc())
                .all()
            )

    @staticmethod
    def _patch_llm_raise(monkeypatch, client):
        from fastapi.routing import APIRoute

        route = next(
            r for r in client.app.routes
            if isinstance(r, APIRoute) and r.path == "/products/{product_id}/knowledge/ask"
        )

        def _raise(*a, **k):
            raise RuntimeError("LLM must not be called for local rule")

        monkeypatch.setitem(route.endpoint.__globals__, "call_llm", _raise)

    def test_price_local_answer(self, client, monkeypatch):
        pid = self._create_product(client)
        self._patch_llm_raise(monkeypatch, client)
        resp = self._ask(client, pid, "多少钱")
        assert resp.status_code == 200
        data = resp.json()
        assert "129" in data["answer"]
        assert data["sources"] == []

        logs = self._logs_for_product(client, pid)
        assert len(logs) == 1
        assert logs[0].answer_mode == "local_rule"
        assert logs[0].category == "price"
        assert logs[0].was_answered is True

    def test_stock_local_answer(self, client):
        pid = self._create_product(client)
        data = self._ask(client, pid, "还有库存吗").json()
        assert "50" in data["answer"] and "库存" in data["answer"]
        assert data["sources"] == []
        assert self._logs_for_product(client, pid)[0].answer_mode == "local_rule"

    def test_promotion_local_answer(self, client):
        pid = self._create_product(client)
        data = self._ask(client, pid, "有什么优惠").json()
        assert "直播间拍一发二" in data["answer"]
        assert data["sources"] == []
        assert self._logs_for_product(client, pid)[0].answer_mode == "local_rule"

    def test_audience_local_answer(self, client):
        pid = self._create_product(client)
        data = self._ask(client, pid, "适合什么人").json()
        assert "熬夜肌、换季敏感人群" in data["answer"]
        assert data["sources"] == []
        assert self._logs_for_product(client, pid)[0].answer_mode == "local_rule"

    def test_selling_points_local_answer(self, client):
        pid = self._create_product(client)
        data = self._ask(client, pid, "有什么卖点").json()
        assert "舒缓泛红、修护屏障" in data["answer"]
        assert data["sources"] == []
        assert self._logs_for_product(client, pid)[0].answer_mode == "local_rule"

    def test_empty_field_does_not_force_local_answer(self, client):
        # promotion 为空：快答不命中 → 继续走资料检索 → 无资料 → no_match
        pid = self._create_product(client, {**FULL_PRODUCT, "promotion": ""})
        resp = self._ask(client, pid, "有什么优惠")
        assert resp.status_code == 200
        log = self._logs_for_product(client, pid)[0]
        assert log.answer_mode != "local_rule"
        assert log.answer_mode == "no_match"
        assert log.was_answered is False

    def test_high_risk_question_not_local_answered(self, client):
        # 商品有 audience 字段，但 risk 优先级最高，不得被 audience 快答
        pid = self._create_product(client)
        resp = self._ask(client, pid, "孕妇敏感肌能不能用")
        assert resp.status_code == 200
        log = self._logs_for_product(client, pid)[0]
        assert log.category == "risk"
        assert log.answer_mode != "local_rule"
        assert log.answer_mode == "no_match"

    def test_local_answer_does_not_use_vector_retrieval(self, client, monkeypatch):
        from fastapi.routing import APIRoute

        pid = self._create_product(client)
        route = next(
            r for r in client.app.routes
            if isinstance(r, APIRoute) and r.path == "/products/{product_id}/knowledge/ask"
        )

        def _raise(*a, **k):
            raise RuntimeError("vector retrieval must not be called for local rule")

        monkeypatch.setitem(
            route.endpoint.__globals__, "retrieve_product_chunks_vector", _raise
        )
        resp = self._ask(client, pid, "多少钱")
        assert resp.status_code == 200
        assert "129" in resp.json()["answer"]

    def test_local_answer_scoped_by_user(self, client):
        pid = self._create_product(client)
        other = TestQuestionLogRecording._create_second_user(client, "local-other")
        # 他人访问该商品问答 → 404，不产生本地快答与日志
        assert other.post(
            f"/products/{pid}/knowledge/ask", json={"question": "多少钱"}
        ).status_code == 404
        assert self._logs_for_product(client, pid) == []
