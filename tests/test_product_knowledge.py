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
        # 用非本地快答类问题（本地快答见 test_question_insights）验证资料检索链路
        resp = client.post(
            f"/products/{kb_product_id}/knowledge/ask",
            json={"question": "这款商品适合什么肤质？"},
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

    def test_view_chunks_and_reindex_document(self, client, kb_product_id):
        """「查看片段」「重建该文件索引」按钮对应的接口行为。"""
        resp = client.post(
            f"/products/{kb_product_id}/knowledge/upload",
            files={"file": ("chunk-test.txt", ("片段一内容。" + "补水" * 600).encode("utf-8"), "text/plain")},
        )
        assert resp.status_code == 200
        uploaded_chunks = resp.json()["chunks"]
        assert uploaded_chunks >= 2

        chunks = client.get(f"/products/{kb_product_id}/knowledge/documents/chunk-test.txt/chunks")
        assert chunks.status_code == 200
        data = chunks.json()
        assert data["filename"] == "chunk-test.txt"
        assert len(data["chunks"]) == uploaded_chunks
        assert data["chunks"][0]["chunk_index"] == 1
        assert "片段一内容" in data["chunks"][0]["content"]

        reindex = client.post(f"/products/{kb_product_id}/knowledge/documents/chunk-test.txt/reindex")
        assert reindex.status_code == 200
        assert reindex.json()["reindexed"] is False
        assert "资料索引功能未启用" in reindex.json()["message"]

        assert client.get(f"/products/{kb_product_id}/knowledge/documents/不存在.txt/chunks").status_code == 404
        assert client.post(f"/products/{kb_product_id}/knowledge/documents/不存在.txt/reindex").status_code == 404

    def test_chunks_scoped_by_user(self, client, kb_product_id):
        other = _create_second_user(client, "kb-chunks-other")
        assert other.get(f"/products/{kb_product_id}/knowledge/documents/manual.txt/chunks").status_code == 404
        assert other.post(f"/products/{kb_product_id}/knowledge/documents/manual.txt/reindex").status_code == 404

    def test_ask_prompt_contains_product_and_chunks(self, client, kb_product_id, monkeypatch):
        """问答 prompt 必须包含商品信息与检索到的知识片段（不真实调用外部 AI）。"""
        from fastapi.routing import APIRoute

        route = next(
            r for r in client.app.routes
            if isinstance(r, APIRoute) and r.path == "/products/{product_id}/knowledge/ask"
        )

        captured = {}

        def fake_llm(prompt, *args, **kwargs):
            captured["prompt"] = prompt
            return "回答内容"

        monkeypatch.setitem(route.endpoint.__globals__, "call_llm", fake_llm)

        resp = client.post(
            f"/products/{kb_product_id}/knowledge/ask",
            json={"question": "补水效果怎么样？"},
        )
        assert resp.status_code == 200
        prompt = captured["prompt"]
        assert "知识库测试商品" in prompt          # 商品名称
        assert "补水保湿" in prompt                  # 知识片段内容
        assert "补水效果怎么样？" in prompt          # 用户问题

    def test_ask_prompt_requires_natural_language_output(self, client, kb_product_id, monkeypatch):
        """prompt 必须要求把资料整理成自然语言，不得原样输出 Markdown 表格。"""
        from fastapi.routing import APIRoute

        resp = client.post(
            f"/products/{kb_product_id}/knowledge/upload",
            files={
                "file": (
                    "faq.md",
                    "| 用户问题 | 标准回答 |\n|---|---|\n| 赠品能换吗？ | 亲，赠品以页面展示为准 |".encode("utf-8"),
                    "text/markdown",
                )
            },
        )
        assert resp.status_code == 200

        route = next(
            r for r in client.app.routes
            if isinstance(r, APIRoute) and r.path == "/products/{product_id}/knowledge/ask"
        )
        captured = {}

        def fake_llm(prompt, *args, **kwargs):
            captured["prompt"] = prompt
            return "赠品以页面展示为准。"

        monkeypatch.setitem(route.endpoint.__globals__, "call_llm", fake_llm)

        resp = client.post(
            f"/products/{kb_product_id}/knowledge/ask",
            json={"question": "赠品能换吗？"},
        )
        assert resp.status_code == 200
        data = resp.json()
        # 返回结构不变：answer + sources
        assert "answer" in data
        assert "sources" in data
        prompt = captured["prompt"]
        assert "不要原样复制 Markdown 表格" in prompt
        assert "分点说明" in prompt
        assert "赠品能换吗？" in prompt           # 表格内容仍作为检索上下文传入

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


class TestLiveOpsDashboard:
    @pytest.fixture(autouse=True)
    def _auth(self, client):
        login(client)

    def test_dashboard_counts_and_lists(self, client):
        resp = client.post(
            "/products",
            json={"name": "看板新接口商品", "live_status": "直播中"},
        )
        assert resp.status_code == 200
        pid = resp.json()["id"]

        client.post(f"/products/{pid}/live-scripts")
        client.post(f"/products/{pid}/comment-replies", json={"comment": "高频问题唯一标记"})
        client.post(f"/products/{pid}/comment-replies", json={"comment": "高频问题唯一标记"})
        client.post(f"/products/{pid}/live-reviews")

        data = client.get("/live-ops/dashboard").json()
        assert data["product_count"] >= 1
        assert data["live_product_count"] >= 1
        assert data["live_script_count"] >= 1
        assert data["comment_reply_count"] >= 2
        assert data["live_review_count"] >= 1
        assert len(data["recent_comment_replies"]) >= 2
        assert len(data["recent_live_reviews"]) >= 1
        hot = {h["comment"]: h["count"] for h in data["hot_questions"]}
        assert hot.get("高频问题唯一标记") == 2

    def test_dashboard_empty_for_new_user(self, client):
        other = _create_second_user(client, "dashboard-new-user")
        data = other.get("/live-ops/dashboard").json()
        assert data["product_count"] == 0
        assert data["live_script_count"] == 0
        assert data["comment_reply_count"] == 0
        assert data["live_review_count"] == 0
        assert data["knowledge_document_count"] == 0
        assert data["hot_questions"] == []
        assert data["recent_comment_replies"] == []
        assert data["recent_live_reviews"] == []

    def test_dashboard_scoped_by_user(self, client):
        login(client)
        resp = client.post("/products", json={"name": "看板隔离商品"})
        assert resp.status_code == 200
        pid = resp.json()["id"]
        client.post(f"/products/{pid}/comment-replies", json={"comment": "隔离评论标记"})

        other = _create_second_user(client, "dashboard-iso-user")
        data = other.get("/live-ops/dashboard").json()
        assert data["product_count"] == 0
        assert data["comment_reply_count"] == 0
        assert data["recent_comment_replies"] == []


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


class TestProductReadiness:
    """商品资料完整度评分接口测试（GET /products/{id}/readiness）。

    纯确定性规则计算：不调用 LLM、不依赖 Embedding API。
    """

    @pytest.fixture(autouse=True)
    def _auth(self, client):
        login(client)

    def test_empty_product_returns_low_score_with_missing_items(self, client):
        resp = client.post("/products", json={"name": "完整度空商品"})
        assert resp.status_code == 200
        pid = resp.json()["id"]
        data = client.get(f"/products/{pid}/readiness").json()
        comp = data["completeness"]
        assert 0 <= comp["score"] <= 100
        assert comp["score"] <= 30, f"空商品分数应较低，got {comp['score']}"
        assert "商品资料文档" in comp["missing_items"]
        assert "售后规则" in comp["missing_items"]
        assert "风险边界" in comp["missing_items"]
        assert "上传商品资料文档" in comp["suggestions"]
        assert data["prep_checklist"] == []

    def test_full_product_and_docs_reach_full_score(self, client):
        resp = client.post("/products", json={
            "name": "完整度完整商品",
            "price": 99,
            "stock": 50,
            "selling_points": "核心卖点",
            "target_audience": "适用人群",
            "pain_points": "用户痛点",
            "promotion": "优惠信息",
            "live_status": "直播中",
            "notes": "不可承诺治疗功效",
        })
        assert resp.status_code == 200
        pid = resp.json()["id"]
        client.post(
            f"/products/{pid}/knowledge/upload",
            files={"file": ("FAQ.md", "常见问题内容".encode("utf-8"), "text/markdown")},
        )
        client.post(
            f"/products/{pid}/knowledge/upload",
            files={"file": ("售后政策.md", "七天无理由退换".encode("utf-8"), "text/markdown")},
        )
        comp = client.get(f"/products/{pid}/readiness").json()["completeness"]
        assert comp["score"] == 100, f"完整商品应为 100 分，got {comp['score']}: {comp}"
        assert comp["missing_items"] == []
        assert comp["suggestions"] == []

    def test_faq_filename_detection(self, client):
        resp = client.post("/products", json={"name": "完整度FAQ商品", "price": 10, "stock": 5})
        pid = resp.json()["id"]
        client.post(
            f"/products/{pid}/knowledge/upload",
            files={"file": ("产品Q&A.txt", "问答内容".encode("utf-8"), "text/plain")},
        )
        comp = client.get(f"/products/{pid}/readiness").json()["completeness"]
        assert "FAQ 或问答资料" not in comp["missing_items"]

    def test_aftersale_filename_detection(self, client):
        resp = client.post("/products", json={"name": "完整度售后商品", "price": 10, "stock": 5})
        pid = resp.json()["id"]
        client.post(
            f"/products/{pid}/knowledge/upload",
            files={"file": ("AfterSales说明.txt", "售后说明".encode("utf-8"), "text/plain")},
        )
        comp = client.get(f"/products/{pid}/readiness").json()["completeness"]
        assert "售后规则" not in comp["missing_items"]

    def test_risk_notes_detection(self, client):
        resp = client.post(
            "/products",
            json={"name": "完整度风险商品", "price": 10, "stock": 5, "notes": "不要承诺治疗功效"},
        )
        pid = resp.json()["id"]
        comp = client.get(f"/products/{pid}/readiness").json()["completeness"]
        assert "风险边界" not in comp["missing_items"]

    def test_risk_filename_detection(self, client):
        resp = client.post("/products", json={"name": "完整度风险文件商品", "price": 10, "stock": 5})
        pid = resp.json()["id"]
        client.post(
            f"/products/{pid}/knowledge/upload",
            files={"file": ("禁用话术.txt", "不可承诺内容".encode("utf-8"), "text/plain")},
        )
        comp = client.get(f"/products/{pid}/readiness").json()["completeness"]
        assert "风险边界" not in comp["missing_items"]

    def test_readiness_scoped_by_user(self, client):
        resp = client.post("/products", json={"name": "完整度隔离商品"})
        pid = resp.json()["id"]
        other = _create_second_user(client, "readiness-other-user")
        assert other.get(f"/products/{pid}/readiness").status_code == 404

    def test_readiness_requires_login(self, client):
        client.cookies.clear()
        assert client.get("/products/1/readiness").status_code == 401


class TestProductKnowledgeVector:
    """商品资料向量检索最小闭环测试（ChromaDB + test embedding provider）。

    使用 conftest 的 vector_client（独立临时 SQLite + Chroma + EMBEDDING_PROVIDER=test）。
    """

    @staticmethod
    def _admin_user_id():
        from app.database import SessionLocal
        from app.models import User
        with SessionLocal() as db:
            return db.query(User).filter(User.username == "admin").first().id

    @staticmethod
    def _make_product_with_doc(vc, name, filename, content):
        resp = vc.post("/products", json={"name": name})
        assert resp.status_code == 200
        pid = resp.json()["id"]
        resp = vc.post(
            f"/products/{pid}/knowledge/upload",
            files={"file": (filename, content.encode("utf-8"), "text/plain")},
        )
        assert resp.status_code == 200
        return pid

    def test_upload_builds_product_vector_index(self, vector_client):
        """上传商品资料后应建立独立的商品资料向量索引。"""
        from app.vector_store import get_vector_store

        pid = self._make_product_with_doc(
            vector_client, "向量商品A", "va.txt", "这款舒缓精华适合敏感肌人群，主打修护屏障。"
        )
        vs = get_vector_store()
        assert vs is not None
        assert vs.count_product_chunks(self._admin_user_id(), pid) >= 1

    def test_ask_uses_vector_search_scoped_by_user_and_product(self, vector_client):
        """商品资料问答应优先走向量检索，且带 user_id + product_id 过滤。"""
        from app.vector_store import get_vector_store

        pid = self._make_product_with_doc(
            vector_client, "向量商品B", "vb.txt", "这款暖杯垫三档恒温，适合办公室人群。"
        )
        uid = self._admin_user_id()
        vs = get_vector_store()
        calls = []
        orig = vs.search_product_chunks

        def spy(query_emb, user_id, product_id, top_k):
            calls.append((user_id, product_id))
            return orig(query_emb, user_id, product_id, top_k)

        vs.search_product_chunks = spy
        try:
            resp = vector_client.post(
                f"/products/{pid}/knowledge/ask", json={"question": "适合什么人群？"}
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["sources"], "问答应返回参考片段"
            assert data["sources"][0]["filename"] == "vb.txt"
        finally:
            vs.search_product_chunks = orig

        assert calls, "问答未走向量检索路径"
        assert all(u == uid and p == pid for u, p in calls), "向量检索未按 user+product 过滤"

    def test_ask_falls_back_to_tfidf_when_vector_disabled(self, vector_client, monkeypatch):
        """向量被关闭时，问答自动降级到 TF-IDF 且仍可返回资料片段。"""
        import app.rag as rag_mod

        pid = self._make_product_with_doc(
            vector_client, "向量商品C", "vc.txt", "这款商品主打补水保湿，适合干性皮肤。"
        )
        monkeypatch.setattr(rag_mod.settings, "VECTOR_SEARCH_ENABLED", False)
        resp = vector_client.post(
            f"/products/{pid}/knowledge/ask", json={"question": "补水"}
        )
        assert resp.status_code == 200
        assert resp.json()["sources"][0]["filename"] == "vc.txt"

    def test_ask_falls_back_when_vector_store_unavailable(self, vector_client, monkeypatch):
        """向量存储不可用时，问答自动降级到 TF-IDF。"""
        import app.rag as rag_mod

        pid = self._make_product_with_doc(
            vector_client, "向量商品D", "vd.txt", "这款商品有防晒能力，适合户外人群。"
        )
        monkeypatch.setattr(rag_mod, "get_vector_store", lambda: None)
        resp = vector_client.post(
            f"/products/{pid}/knowledge/ask", json={"question": "防晒"}
        )
        assert resp.status_code == 200
        assert resp.json()["sources"][0]["filename"] == "vd.txt"

    def test_ask_falls_back_when_embedding_unavailable(self, vector_client, monkeypatch):
        """embedding 服务异常时，问答自动降级到 TF-IDF。"""
        import app.rag as rag_mod

        pid = self._make_product_with_doc(
            vector_client, "向量商品D2", "vd2.txt", "这款商品有防晒能力，适合户外人群。"
        )

        def _raise_embedding_error():
            raise RuntimeError("embedding service unavailable")

        monkeypatch.setattr(rag_mod, "get_embedding_service", _raise_embedding_error)
        resp = vector_client.post(
            f"/products/{pid}/knowledge/ask", json={"question": "防晒"}
        )
        assert resp.status_code == 200
        assert resp.json()["sources"][0]["filename"] == "vd2.txt"

    def test_ask_falls_back_when_product_index_unsupported(self, vector_client, monkeypatch):
        """向量存储不支持商品资料索引（如 pgvector 场景）时，问答自动降级到 TF-IDF。"""
        from app.vector_store import get_vector_store

        pid = self._make_product_with_doc(
            vector_client, "向量商品D3", "vd3.txt", "这款商品有防晒能力，适合户外人群。"
        )
        vs = get_vector_store()
        assert vs is not None and vs.supports_product_knowledge is True
        monkeypatch.setattr(vs, "supports_product_knowledge", False)

        resp = vector_client.post(
            f"/products/{pid}/knowledge/ask", json={"question": "防晒"}
        )
        assert resp.status_code == 200
        assert resp.json()["sources"][0]["filename"] == "vd3.txt"

    def test_ask_falls_back_when_vector_returns_stale_ids(self, vector_client, monkeypatch):
        """向量返回残留失效 id 时，应过滤后自动降级到 TF-IDF，而不是空结果。"""
        from app.vector_store import get_vector_store

        pid = self._make_product_with_doc(
            vector_client, "向量商品L", "vl.txt", "这款商品主打补水保湿，适合干性皮肤。"
        )
        vs = get_vector_store()
        # 模拟 Chroma 残留旧 id：向量只返回当前商品不存在的片段 id
        monkeypatch.setattr(
            vs, "search_product_chunks", lambda emb, uid, pid_, k: [999999]
        )

        resp = vector_client.post(
            f"/products/{pid}/knowledge/ask", json={"question": "补水"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["sources"], "失效 id 过滤后为空时应用 TF-IDF 兜底"
        assert data["sources"][0]["filename"] == "vl.txt"

    def test_ask_fills_results_with_tfidf_when_vector_partial(self, vector_client, monkeypatch):
        """向量只返回部分有效 id 时，用 TF-IDF 补齐且不重复。"""
        from app.database import SessionLocal
        from app.models import ProductKnowledgeChunk
        from app.vector_store import get_vector_store

        pid = self._make_product_with_doc(
            vector_client,
            "向量商品M",
            "vm.txt",
            "片段一：补水。" + "保" * 900 + "片段二：保湿。",
        )
        with SessionLocal() as db:
            first_id = (
                db.query(ProductKnowledgeChunk)
                .filter(
                    ProductKnowledgeChunk.user_id == self._admin_user_id(),
                    ProductKnowledgeChunk.product_id == pid,
                    ProductKnowledgeChunk.chunk_index == 1,
                )
                .first()
                .id
            )
        vs = get_vector_store()
        # 向量只返回 1 个有效 id（top_k=4）→ 应由 TF-IDF 补齐
        monkeypatch.setattr(
            vs, "search_product_chunks", lambda emb, uid, pid_, k: [first_id]
        )

        resp = vector_client.post(
            f"/products/{pid}/knowledge/ask", json={"question": "保湿"}
        )
        assert resp.status_code == 200
        sources = resp.json()["sources"]
        assert len(sources) >= 2, "向量结果不足 top_k 时应用 TF-IDF 补齐"
        indexes = [s["chunk_index"] for s in sources]
        assert len(indexes) == len(set(indexes)), "补齐结果不应重复"

    def test_reindex_returns_false_when_index_service_unavailable(self, vector_client, monkeypatch):
        """索引服务初始化失败时，reindex 返回 reindexed=false，而不是 503。"""
        import app.embeddings as emb_mod

        pid = self._make_product_with_doc(
            vector_client, "向量商品N", "rn.txt", "这款商品有资料内容。"
        )

        def _raise_init_error():
            raise RuntimeError("embedding init failed")

        monkeypatch.setattr(emb_mod, "get_embedding_service", _raise_init_error)
        resp = vector_client.post(f"/products/{pid}/knowledge/documents/rn.txt/reindex")
        assert resp.status_code == 200
        data = resp.json()
        assert data["reindexed"] is False
        assert data["filename"] == "rn.txt"
        assert data["chunks"] >= 1
        assert "资料索引服务暂不可用" in data["message"]

    def test_reindex_returns_false_when_embedding_call_fails(self, vector_client, monkeypatch):
        """embedding 实际调用失败（如 API 网络异常）时，reindex 返回 false 而非 500。"""
        from app.embeddings import get_embedding_service

        pid = self._make_product_with_doc(
            vector_client, "向量商品N2", "rn2.txt", "这款商品有资料内容。"
        )

        def _raise_call_error(texts):
            raise RuntimeError("embedding api network error")

        svc = get_embedding_service()
        monkeypatch.setattr(svc, "embed_documents", _raise_call_error)
        resp = vector_client.post(f"/products/{pid}/knowledge/documents/rn2.txt/reindex")
        assert resp.status_code == 200
        data = resp.json()
        assert data["reindexed"] is False
        assert data["filename"] == "rn2.txt"
        assert data["chunks"] >= 1
        assert "资料索引服务暂不可用" in data["message"]

    def test_reindex_really_rebuilds_product_index(self, vector_client):
        """「重建资料索引」应真实重建该文件的向量索引。"""
        from app.vector_store import get_vector_store

        pid = self._make_product_with_doc(
            vector_client, "向量商品E", "rx.txt", "片段一。" + "保" * 900
        )
        vs = get_vector_store()
        uid = self._admin_user_id()
        before = vs.count_product_chunks(uid, pid)
        assert before >= 2

        # 模拟索引丢失：清空该文件向量
        vs.delete_product_file_chunks(uid, pid, "rx.txt")
        assert vs.count_product_chunks(uid, pid) == 0

        resp = vector_client.post(f"/products/{pid}/knowledge/documents/rx.txt/reindex")
        assert resp.status_code == 200
        data = resp.json()
        assert data["reindexed"] is True
        assert data["chunks"] == before
        assert vs.count_product_chunks(uid, pid) == before

    def test_delete_document_cleans_product_vectors(self, vector_client):
        """删除商品资料文档应同步清理其向量索引。"""
        from app.vector_store import get_vector_store

        pid = self._make_product_with_doc(
            vector_client, "向量商品F", "dx.txt", "这款商品支持七天无理由退换。"
        )
        vs = get_vector_store()
        uid = self._admin_user_id()
        assert vs.count_product_chunks(uid, pid) == 1

        resp = vector_client.delete(f"/products/{pid}/knowledge/documents/dx.txt")
        assert resp.status_code == 200
        assert vs.count_product_chunks(uid, pid) == 0

    def test_reupload_replaces_vectors_without_stale_entries(self, vector_client):
        """同名文件重传后不残留旧索引，且不影响其他商品的同名文件。"""
        from app.vector_store import get_vector_store

        pid_a = self._make_product_with_doc(
            vector_client, "向量商品G", "same.txt", "旧内容只有一个片段。"
        )
        pid_b = self._make_product_with_doc(
            vector_client, "向量商品H", "same.txt", "另一个商品的同名文件内容。"
        )
        vs = get_vector_store()
        uid = self._admin_user_id()
        assert vs.count_product_chunks(uid, pid_a) == 1
        assert vs.count_product_chunks(uid, pid_b) == 1

        resp = vector_client.post(
            f"/products/{pid_a}/knowledge/upload",
            files={
                "file": ("same.txt", ("更新后内容。" + "保" * 900).encode("utf-8"), "text/plain")
            },
        )
        assert resp.status_code == 200
        assert resp.json()["chunks"] == 2

        # A 重传后索引数与新片段一致（无旧残留）；B 的同名文件不受影响
        assert vs.count_product_chunks(uid, pid_a) == 2
        assert vs.count_product_chunks(uid, pid_b) == 1

    def test_vector_search_scoped_by_product(self, vector_client):
        """向量检索不允许跨商品召回。"""
        from app.database import SessionLocal
        from app.embeddings import get_embedding_service
        from app.models import ProductKnowledgeChunk
        from app.vector_store import get_vector_store

        pid_a = self._make_product_with_doc(
            vector_client, "向量商品I", "ia.txt", "这款是保湿精华液，适合干皮。"
        )
        pid_b = self._make_product_with_doc(
            vector_client, "向量商品J", "jb.txt", "这款是便携暖杯垫，适合办公室。"
        )
        uid = self._admin_user_id()
        vs = get_vector_store()
        query_emb = get_embedding_service().embed_query("精华液")

        ids_a = vs.search_product_chunks(query_emb, uid, pid_a, top_k=10)
        assert ids_a

        with SessionLocal() as db:
            valid_a = {
                c.id
                for c in db.query(ProductKnowledgeChunk)
                .filter(
                    ProductKnowledgeChunk.user_id == uid,
                    ProductKnowledgeChunk.product_id == pid_a,
                )
                .all()
            }
            valid_b = {
                c.id
                for c in db.query(ProductKnowledgeChunk)
                .filter(
                    ProductKnowledgeChunk.user_id == uid,
                    ProductKnowledgeChunk.product_id == pid_b,
                )
                .all()
            }

        assert set(ids_a) <= valid_a, "跨商品召回：返回了不属于该商品的片段"
        assert not (set(ids_a) & valid_b), "跨商品召回：返回了其他商品的片段"

    def test_reindex_all_empty_chunks_returns_friendly_message(self, vector_client, monkeypatch):
        """全空片段：不调用 embedding，返回 reindexed=false 与运营语言。"""
        from app.database import SessionLocal
        from app.embeddings import get_embedding_service
        from app.models import ProductKnowledgeChunk

        pid = self._make_product_with_doc(
            vector_client, "向量空片段商品", "empty.txt", "有内容的一段。"
        )
        with SessionLocal() as db:
            db.query(ProductKnowledgeChunk).filter(
                ProductKnowledgeChunk.product_id == pid
            ).update({"content": "   "})
            db.commit()

        svc = get_embedding_service()
        calls = []
        orig = svc.embed_documents

        def spy(texts):
            calls.append(texts)
            return orig(texts)

        svc.embed_documents = spy
        try:
            resp = vector_client.post(
                f"/products/{pid}/knowledge/documents/empty.txt/reindex"
            )
        finally:
            svc.embed_documents = orig

        assert resp.status_code == 200
        data = resp.json()
        assert data["reindexed"] is False
        assert "没有可索引内容" in data["message"]
        assert calls == [], "全空片段不应调用 embedding"

    def test_reindex_partial_empty_only_indexes_non_empty(self, vector_client):
        """部分空片段：只对非空片段建索引。"""
        from app.database import SessionLocal
        from app.models import ProductKnowledgeChunk
        from app.vector_store import get_vector_store

        pid = self._make_product_with_doc(
            vector_client, "向量部分空商品", "part.txt", "片段一。" + "保" * 900
        )
        with SessionLocal() as db:
            db.query(ProductKnowledgeChunk).filter(
                ProductKnowledgeChunk.product_id == pid,
                ProductKnowledgeChunk.chunk_index == 2,
            ).update({"content": ""})
            db.commit()

        resp = vector_client.post(
            f"/products/{pid}/knowledge/documents/part.txt/reindex"
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["reindexed"] is True
        assert data["chunks"] == 1  # 只统计非空片段

        vs = get_vector_store()
        assert vs.count_product_file_chunks(self._admin_user_id(), pid, "part.txt") == 1

    def test_upload_skips_empty_chunks_when_indexing(self, vector_client, monkeypatch):
        """上传建索引时过滤空片段：SQL 保留原逻辑，向量只索引非空。"""
        from fastapi.routing import APIRoute

        from app.database import SessionLocal
        from app.models import ProductKnowledgeChunk
        from app.vector_store import get_vector_store

        resp = vector_client.post("/products", json={"name": "向量上传空片段商品"})
        assert resp.status_code == 200
        pid = resp.json()["id"]

        route = next(
            r for r in vector_client.app.routes
            if isinstance(r, APIRoute)
            and r.path == "/products/{product_id}/knowledge/upload"
        )
        monkeypatch.setitem(
            route.endpoint.__globals__,
            "split_text",
            lambda text: ["", "有内容的一段。", "   "],
        )

        resp = vector_client.post(
            f"/products/{pid}/knowledge/upload",
            files={"file": ("mix.txt", b"x", "text/plain")},
        )
        assert resp.status_code == 200

        with SessionLocal() as db:
            sql_count = (
                db.query(ProductKnowledgeChunk)
                .filter(ProductKnowledgeChunk.product_id == pid)
                .count()
            )
        assert sql_count == 3  # SQL 保留原有切分逻辑

        vs = get_vector_store()
        assert vs.count_product_file_chunks(self._admin_user_id(), pid, "mix.txt") == 1

    def test_reindex_embedding_error_returns_friendly_message(self, vector_client, monkeypatch):
        """embedding API 抛异常时，响应不含底层错误文本。"""
        from app.embeddings import get_embedding_service

        pid = self._make_product_with_doc(
            vector_client, "向量报错商品", "err.txt", "有内容。"
        )
        svc = get_embedding_service()

        def _raise(texts):
            raise RuntimeError("Error code: 400 - input.contents should not be larger than 10")

        monkeypatch.setattr(svc, "embed_documents", _raise)
        resp = vector_client.post(
            f"/products/{pid}/knowledge/documents/err.txt/reindex"
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["reindexed"] is False
        assert "Error code" not in data["message"]
        assert "400" not in data["message"]
        assert "资料索引服务暂不可用" in data["message"]

    def test_ask_does_not_use_empty_chunk_as_source(self, vector_client, monkeypatch):
        """问答来源不得包含空内容片段。"""
        from fastapi.routing import APIRoute

        from app.database import SessionLocal
        from app.models import ProductKnowledgeChunk

        pid = self._make_product_with_doc(
            vector_client, "向量问答空源商品", "ask.txt", "补水保湿的卖点内容。" + "水" * 100
        )
        with SessionLocal() as db:
            max_idx = (
                db.query(ProductKnowledgeChunk)
                .filter(ProductKnowledgeChunk.product_id == pid)
                .count()
            )
            db.add(ProductKnowledgeChunk(
                user_id=self._admin_user_id(),
                product_id=pid,
                filename="ask.txt",
                chunk_index=max_idx + 1,
                content="   ",
            ))
            db.commit()

        route = next(
            r for r in vector_client.app.routes
            if isinstance(r, APIRoute)
            and r.path == "/products/{product_id}/knowledge/ask"
        )
        monkeypatch.setitem(
            route.endpoint.__globals__, "call_llm", lambda *a, **k: "回答内容"
        )
        resp = vector_client.post(
            f"/products/{pid}/knowledge/ask", json={"question": "补水保湿"}
        )
        assert resp.status_code == 200
        sources = resp.json()["sources"]
        assert sources, "应返回有效片段"
        for s in sources:
            assert (s["content"] or "").strip(), "空内容不得作为问答来源"

    def test_vector_search_scoped_by_user(self, vector_client_dual_user):
        """向量检索不允许跨用户召回；业务接口同样隔离。"""
        from app.database import SessionLocal
        from app.embeddings import get_embedding_service
        from app.models import User
        from app.vector_store import get_vector_store

        admin_vc, user2_vc = vector_client_dual_user
        pid = self._make_product_with_doc(
            admin_vc, "向量商品K", "ka.txt", "管理员的商品资料内容。"
        )
        vs = get_vector_store()
        with SessionLocal() as db:
            admin_id = db.query(User).filter(User.username == "admin").first().id
            user2_id = db.query(User).filter(User.username == "user2").first().id

        query_emb = get_embedding_service().embed_query("资料")
        ids_admin = vs.search_product_chunks(query_emb, admin_id, pid, top_k=10)
        assert ids_admin, "管理员应能召回自己的商品资料"

        # user2 在 admin 的商品下没有任何向量 → 向量层不可召回
        assert vs.search_product_chunks(query_emb, user2_id, pid, top_k=10) == []

        # SQL / 接口层隔离：user2 访问 admin 的商品资料返回 404
        assert user2_vc.get(f"/products/{pid}/knowledge/documents").status_code == 404
        assert (
            user2_vc.post(f"/products/{pid}/knowledge/ask", json={"question": "x"}).status_code
            == 404
        )


class TestEmbeddingBatch:
    """Embedding API 批量分批（单次最多 10 条，OpenAI-compatible 限制）。

    用伪造客户端直接测 EmbeddingService 层，不依赖真实 API。
    """

    @staticmethod
    def _make_service():
        from app.embeddings import EmbeddingService

        svc = EmbeddingService()
        svc._loaded = True
        svc._provider = "openai_compatible"
        svc._model = None

        calls = []
        counter = {"n": 0}

        class _Item:
            def __init__(self):
                self.embedding = [float(counter["n"])]
                counter["n"] += 1

        class _Resp:
            def __init__(self, texts):
                self.data = [_Item() for _ in texts]

        class _Embeddings:
            def create(self, **kwargs):
                texts = list(kwargs["input"])
                calls.append(texts)
                return _Resp(texts)

        class _FakeClient:
            def __init__(self):
                self.embeddings = _Embeddings()

        svc._client = _FakeClient()
        return svc, calls

    def test_eleven_texts_split_into_two_batches(self):
        svc, calls = self._make_service()
        texts = [f"文本{i}" for i in range(11)]
        result = svc.embed_documents(texts)

        assert len(calls) == 2
        assert [len(c) for c in calls] == [10, 1]
        assert len(result) == 11
        # 顺序不乱：第 i 条结果的 embedding 值等于 i
        assert result == [[float(i)] for i in range(11)]

    def test_twenty_five_texts_split_into_three_batches(self):
        svc, calls = self._make_service()
        texts = [f"文本{i}" for i in range(25)]
        result = svc.embed_documents(texts)

        assert [len(c) for c in calls] == [10, 10, 5]
        assert len(result) == 25
        assert result == [[float(i)] for i in range(25)]

    def test_small_batch_single_call(self):
        svc, calls = self._make_service()
        result = svc.embed_documents(["a", "b", "c"])

        assert len(calls) == 1
        assert len(calls[0]) == 3
        assert len(result) == 3

    def test_batch_failure_propagates(self):
        svc, calls = self._make_service()

        def _raise(**kwargs):
            raise RuntimeError("batch size is invalid, it should not be larger than 10")

        svc._client.embeddings.create = _raise
        with pytest.raises(RuntimeError):
            svc.embed_documents(["a"] * 11)
