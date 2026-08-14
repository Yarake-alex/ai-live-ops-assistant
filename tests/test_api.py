import pytest

def login(client):
    """辅助函数：用 test-password 登录。"""
    client.cookies.clear()
    resp = client.post("/auth/login", json={"password": "test-password"})
    assert resp.status_code == 200


# ─── Auth Tests ───

class TestAuth:
    def test_health_check_public(self, client):
        """GET /health 不需要登录，返回 {"status": "ok"}。"""
        client.cookies.clear()
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}

    def test_no_login_returns_401(self, client):
        client.cookies.clear()
        resp = client.get("/products")
        assert resp.status_code == 401

    def test_wrong_password_returns_401(self, client):
        client.cookies.clear()
        resp = client.post("/auth/login", json={"password": "wrong-password"})
        assert resp.status_code == 401

    def test_correct_password_logs_in(self, client):
        client.cookies.clear()
        resp = client.post("/auth/login", json={"password": "test-password"})
        assert resp.status_code == 200
        data = resp.json()
        assert "登录成功" in data["message"]

    def test_login_cookie_has_httponly(self, client):
        """登录返回的 Set-Cookie 必须包含 HttpOnly。"""
        client.cookies.clear()
        resp = client.post("/auth/login", json={"password": "test-password"})
        set_cookie = resp.headers.get("set-cookie", "")
        assert "HttpOnly" in set_cookie, "Cookie 缺少 HttpOnly 标志"

    def test_login_cookie_no_plain_password(self, client):
        """Cookie 中不能包含明文密码。"""
        client.cookies.clear()
        resp = client.post("/auth/login", json={"password": "test-password"})
        set_cookie = resp.headers.get("set-cookie", "")
        assert "test-password" not in set_cookie, "Cookie 中不应出现明文密码"

    def test_auth_me_unauthenticated(self, client):
        """未登录时 GET /auth/me 返回 logged_in=false。"""
        client.cookies.clear()
        resp = client.get("/auth/me")
        assert resp.status_code == 200
        assert resp.json() == {"logged_in": False}

    def test_auth_me_authenticated(self, client):
        """登录后 GET /auth/me 返回 logged_in=true。"""
        client.cookies.clear()
        login(client)
        resp = client.get("/auth/me")
        assert resp.status_code == 200
        assert resp.json()["logged_in"] is True
        assert resp.json()["username"] == "admin"

    def test_root_public(self, client):
        """首页 / 不需要登录。"""
        client.cookies.clear()
        resp = client.get("/")
        assert resp.status_code == 200

    def test_login_then_access_protected_route(self, client):
        client.cookies.clear()
        login(client)
        resp = client.get("/products")
        assert resp.status_code == 200

    def test_logout_clears_session(self, client):
        client.cookies.clear()
        login(client)
        resp = client.post("/auth/logout")
        assert resp.status_code == 200
        resp = client.get("/products")
        assert resp.status_code == 401

    def test_rag_ask_no_login(self, client):
        client.cookies.clear()
        resp = client.post("/rag/ask", json={"question": "test"})
        assert resp.status_code == 401

    def test_dev_mode_no_password(self, client, monkeypatch):
        monkeypatch.setattr("app.config.settings.APP_ACCESS_PASSWORD", "")
        client.cookies.clear()
        resp = client.get("/products")
        assert resp.status_code == 200

    def test_admin_can_create_user(self, client):
        client.cookies.clear()
        login(client)
        resp = client.post(
            "/auth/users",
            json={"username": "sales-user", "password": "sales-user-password"},
        )
        assert resp.status_code in (200, 409)

class TestUpload:
    @pytest.fixture(autouse=True)
    def _auth(self, client):
        login(client)

    def test_upload_too_large(self, client):
        """超过 MAX_UPLOAD_SIZE_MB=1 的文件应返回 413。"""
        content = b"x" * (1024 * 1024 + 1)
        resp = client.post(
            "/rag/upload",
            files={"file": ("big.txt", content, "text/plain")},
        )
        assert resp.status_code == 413
        assert "文件过大" in resp.text

    def test_upload_small_file(self, client):
        """小于限制的文本文件应上传成功并返回片段数。"""
        content = b"hello world, this is a test document for RAG knowledge base."
        resp = client.post(
            "/rag/upload",
            files={"file": ("test.txt", content, "text/plain")},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["chunks"] > 0
        assert data["filename"] == "test.txt"


class TestRagAsk:
    @pytest.fixture(autouse=True)
    def _auth(self, client):
        login(client)

    def test_rag_ask_auth_passed(self, client):
        """已登录，鉴权通过（结果可能因知识库有无资料而异，但不返回 401）。"""
        resp = client.post("/rag/ask", json={"question": "test"})
        assert resp.status_code != 401


class TestVectorUpload:
    """向量索引路径的上传测试。"""

    def test_upload_indexes_vectors(self, vector_client):
        """上传文件后，per-file vector_indexed > 0。"""
        resp = vector_client.post(
            "/rag/upload",
            files={"file": ("test.txt", b"Hello world. This is a test document for vector indexing.")},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["chunks"] > 0

        list_resp = vector_client.get("/rag/documents")
        assert list_resp.status_code == 200
        docs = list_resp.json()
        assert len(docs) == 1
        assert docs[0]["filename"] == "test.txt"
        assert docs[0]["vector_indexed"] is not None
        assert docs[0]["vector_indexed"] == data["chunks"], (
            f"Expected per-file indexed={data['chunks']}, got {docs[0]['vector_indexed']}"
        )

    def test_per_file_vector_counts(self, vector_client):
        """每个文件独立上报 vector_indexed，互不干扰。"""
        vector_client.post(
            "/rag/upload",
            files={"file": ("a.txt", b"Document A content for vector testing.")},
        )
        vector_client.post(
            "/rag/upload",
            files={"file": ("b.txt", b"Document B different content for indexing.")},
        )

        docs = vector_client.get("/rag/documents").json()
        docs.sort(key=lambda d: d["filename"])

        assert docs[0]["filename"] == "a.txt"
        assert docs[0]["vector_indexed"] == docs[0]["chunks"]
        assert docs[1]["filename"] == "b.txt"
        assert docs[1]["vector_indexed"] == docs[1]["chunks"]

    def test_vector_search_after_upload(self, vector_client):
        """上传资料后，向量检索应返回相关片段。"""
        vector_client.post(
            "/rag/upload",
            files={"file": ("product.txt", b"LCD display panel for automotive dashboard.")},
        )

        resp = vector_client.post(
            "/rag/ask",
            json={"question": "car display panel"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "answer" in data
        assert len(data["sources"]) > 0
        assert data["sources"][0]["filename"] == "product.txt"

    def test_reupload_same_file(self, vector_client):
        """同名文件重传：旧向量清除 → 新向量写入，无重复 ID，列表唯一。"""
        resp1 = vector_client.post(
            "/rag/upload",
            files={"file": ("same.txt", b"Version one content for testing reupload.")},
        )
        assert resp1.status_code == 200

        resp2 = vector_client.post(
            "/rag/upload",
            files={"file": ("same.txt", b"Version two updated content for testing reupload.")},
        )
        assert resp2.status_code == 200

        docs = vector_client.get("/rag/documents").json()
        filenames = [d["filename"] for d in docs]
        assert filenames.count("same.txt") == 1
        # After reupload, all chunks should be indexed
        assert docs[0]["vector_indexed"] == docs[0]["chunks"]


class TestVectorDelete:
    """向量索引路径的删除测试。"""

    def test_delete_clears_vectors(self, vector_client):
        """删除文件后向量同步清除，保留的文件不受影响。"""
        vector_client.post(
            "/rag/upload",
            files={"file": ("keep.txt", b"This file should remain in the knowledge base.")},
        )
        vector_client.post(
            "/rag/upload",
            files={"file": ("remove.txt", b"This file will be deleted from the knowledge base.")},
        )

        import urllib.parse
        encoded = urllib.parse.quote("remove.txt", safe="")
        del_resp = vector_client.delete(f"/rag/documents/{encoded}")
        assert del_resp.status_code == 200
        # vector_warning should NOT be present when sync succeeds
        assert "vector_warning" not in del_resp.json()

        docs = vector_client.get("/rag/documents").json()
        filenames = [d["filename"] for d in docs]
        assert "keep.txt" in filenames
        assert "remove.txt" not in filenames
        # Remaining file should have full vector coverage
        assert docs[0]["vector_indexed"] == docs[0]["chunks"]

    def test_clear_all_vectors(self, vector_client):
        """清空全部后列表为空。"""
        vector_client.post(
            "/rag/upload",
            files={"file": ("clear_me.txt", b"Content that will be cleared.")},
        )

        del_resp = vector_client.delete("/rag/documents")
        assert del_resp.status_code == 200
        assert "vector_warning" not in del_resp.json()

        docs = vector_client.get("/rag/documents").json()
        assert len(docs) == 0


class TestVectorDualUserIsolation:
    """真正的双用户向量隔离测试。"""

    def test_dual_user_isolation(self, vector_client_dual_user):
        """用户 A 和用户 B 互相看不到对方的资料和检索结果。"""
        admin, user2 = vector_client_dual_user

        # Admin uploads doc A
        admin.post(
            "/rag/upload",
            files={"file": ("admin_doc.txt", b"Admin proprietary knowledge about LCD displays.")},
        )
        # User2 uploads doc B
        user2.post(
            "/rag/upload",
            files={"file": ("user2_doc.txt", b"User2 proprietary knowledge about OLED displays.")},
        )

        # Admin lists documents — only admin_doc
        admin_docs = admin.get("/rag/documents").json()
        admin_files = [d["filename"] for d in admin_docs]
        assert "admin_doc.txt" in admin_files
        assert "user2_doc.txt" not in admin_files

        # User2 lists documents — only user2_doc
        user2_docs = user2.get("/rag/documents").json()
        user2_files = [d["filename"] for d in user2_docs]
        assert "user2_doc.txt" in user2_files
        assert "admin_doc.txt" not in user2_files

        # Admin searches — should only find LCD results
        admin_ask = admin.post("/rag/ask", json={"question": "display technology"})
        assert admin_ask.status_code == 200
        for s in admin_ask.json()["sources"]:
            assert s["filename"] == "admin_doc.txt", f"Admin saw {s['filename']}"

        # User2 searches — should only find OLED results
        user2_ask = user2.post("/rag/ask", json={"question": "display technology"})
        assert user2_ask.status_code == 200
        for s in user2_ask.json()["sources"]:
            assert s["filename"] == "user2_doc.txt", f"User2 saw {s['filename']}"


class TestVectorReindex:
    """向量索引重建测试。"""

    def test_reindex_endpoint(self, vector_client):
        """重建索引后，per-file vector_indexed 恢复完整。"""
        vector_client.post(
            "/rag/upload",
            files={"file": ("reindex_test.txt", b"Reindex test content for vector database.")},
        )

        reindex_resp = vector_client.post("/rag/reindex")
        assert reindex_resp.status_code == 200
        data = reindex_resp.json()
        assert data["reindexed"] is True
        assert data["chunks"] > 0
        assert "重新索引完成" in data["message"]

        # Verify per-file counts match
        docs = vector_client.get("/rag/documents").json()
        assert docs[0]["vector_indexed"] == docs[0]["chunks"]

    def test_reindex_empty_knowledge_base(self, vector_client):
        """空知识库调用 reindex 应返回 400。"""
        resp = vector_client.post("/rag/reindex")
        assert resp.status_code == 400
        assert "为空" in resp.json()["detail"]


class TestVectorFallback:
    """向量异常回退测试。"""

    def test_vector_disabled_falls_back(self, logged_in_client):
        """VECTOR_SEARCH_ENABLED=false 时，应回退到 TF-IDF 检索。"""
        logged_in_client.post(
            "/rag/upload",
            files={"file": ("fallback.txt", b"TF-IDF fallback test content.")},
        )

        resp = logged_in_client.post(
            "/rag/ask",
            json={"question": "fallback test"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "answer" in data
        # mock TF-IDF fallback marker
        assert "【AI模拟RAG回答】" in data["answer"]


# ═══════════════════════════════════════════════════════════════
# User model & admin tests
# ═══════════════════════════════════════════════════════════════


class TestUserModel:
    """User 模型字段测试。"""

    def test_default_admin_has_role_admin(self, client):
        """默认 admin 用户 role 为 admin，is_active 为 true。"""
        login(client)
        resp = client.get("/auth/me")
        assert resp.status_code == 200
        data = resp.json()
        assert data["role"] == "admin"
        assert data["is_active"] is True

    def test_auth_me_returns_role_and_is_active(self, client):
        """auth/me 返回 role 和 is_active。"""
        login(client)
        resp = client.get("/auth/me")
        assert resp.status_code == 200
        assert "role" in resp.json()
        assert "is_active" in resp.json()


class TestOldDatabaseUpgrade:
    """旧数据库升级测试：users 表缺少 role/is_active 时不应启动失败。"""

    def test_old_db_without_role_and_is_active_upgrades(self, tmp_path, monkeypatch):
        """旧 SQLite 数据库无 role/is_active 列时，init_database 不应报错。"""
        import sqlite3
        import sys
        import os as _os

        db_path = tmp_path / "old_v3.db"
        conn = sqlite3.connect(str(db_path))
        # Old V3 users table: no role, no is_active
        conn.execute("""
            CREATE TABLE users (
                id INTEGER PRIMARY KEY,
                username VARCHAR(50) UNIQUE NOT NULL,
                password_hash VARCHAR(255) NOT NULL,
                is_admin BOOLEAN DEFAULT 0 NOT NULL,
                created_at DATETIME
            )
        """)
        conn.execute(
            "INSERT INTO users (username, password_hash, is_admin, created_at) VALUES (?, ?, ?, datetime('now'))",
            ("admin", "dummy-hash", 1),
        )
        conn.commit()
        conn.close()

        # Point to this old DB
        _prev_db_url = _os.environ.get("DATABASE_URL", "")
        _os.environ["DATABASE_URL"] = f"sqlite:///{db_path}"
        _os.environ["VECTOR_SEARCH_ENABLED"] = "false"

        # Reload app modules so new DB takes effect
        for mod in sorted(sys.modules):
            if mod.startswith("app."):
                del sys.modules[mod]

        from app.db_init import init_database
        init_database()

        # Verify role and is_active columns now exist and have correct values
        conn = sqlite3.connect(str(db_path))
        cur = conn.execute("PRAGMA table_info('users')")
        columns = [row[1] for row in cur.fetchall()]
        assert "role" in columns, f"role column missing after upgrade. Columns: {columns}"
        assert "is_active" in columns, f"is_active column missing after upgrade. Columns: {columns}"

        cur = conn.execute("SELECT username, role, is_active FROM users WHERE username = 'admin'")
        row = cur.fetchone()
        assert row is not None
        assert row[1] == "admin", f"Expected admin role, got {row[1]}"
        assert row[2] == 1, f"Expected is_active=1, got {row[2]}"
        conn.close()

        # Restore test env and reload modules so后续测试（例如 test_ai.py 的
        # settings monkeypatch）不受影响 — 否则测试顺序会引入不确定性。
        if _prev_db_url:
            _os.environ["DATABASE_URL"] = _prev_db_url
        else:
            _os.environ.pop("DATABASE_URL", None)
        for mod in sorted(sys.modules):
            if mod.startswith("app."):
                del sys.modules[mod]


class TestAdminCreateUser:
    """管理员创建用户测试。"""

    @pytest.fixture(autouse=True)
    def _auth(self, client):
        login(client)

    def test_admin_can_create_user_with_defaults(self, client):
        """管理员创建用户，默认 role=user，is_active=true。"""
        resp = client.post("/auth/users", json={
            "username": "new-user-1", "password": "new-user-pass",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["username"] == "new-user-1"
        assert data["role"] == "user"
        assert data["is_active"] is True
        assert "password_hash" not in data

    def test_admin_can_create_user_with_role(self, client):
        """管理员可指定 role。"""
        resp = client.post("/auth/users", json={
            "username": "new-admin-1", "password": "new-admin-pass", "role": "admin",
        })
        assert resp.status_code == 200
        assert resp.json()["role"] == "admin"

    def test_normal_user_cannot_create_user(self, client):
        """普通用户不能创建用户，返回 403。"""
        # Admin creates a normal user first
        client.post("/auth/users", json={
            "username": "normal-guy", "password": "normal-pass",
        })
        # Login as normal user
        client.cookies.clear()
        resp = client.post("/auth/login", json={
            "username": "normal-guy", "password": "normal-pass",
        })
        assert resp.status_code == 200
        # Try to create another user
        resp = client.post("/auth/users", json={
            "username": "illegal-user", "password": "illegal-pass",
        })
        assert resp.status_code == 403

    def test_cannot_create_duplicate_username(self, client):
        """不能创建重名用户。"""
        client.post("/auth/users", json={
            "username": "dup-user", "password": "dup-pass",
        })
        resp = client.post("/auth/users", json={
            "username": "dup-user", "password": "another-pass",
        })
        assert resp.status_code == 409


class TestListUsers:
    """管理员查看用户列表测试。"""

    def test_admin_can_list_users(self, client):
        """管理员可以查看用户列表，响应不含 password_hash。"""
        login(client)
        resp = client.get("/auth/users")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) >= 1
        for u in data:
            assert "id" in u
            assert "username" in u
            assert "role" in u
            assert "is_active" in u
            assert "password_hash" not in u

    def test_normal_user_cannot_list_users(self, client):
        """普通用户不能查看用户列表，返回 403。"""
        login(client)
        client.post("/auth/users", json={
            "username": "list-denied", "password": "list-denied-pass",
        })
        client.cookies.clear()
        resp = client.post("/auth/login", json={
            "username": "list-denied", "password": "list-denied-pass",
        })
        assert resp.status_code == 200
        resp = client.get("/auth/users")
        assert resp.status_code == 403


class TestUserStatus:
    """管理员启用/禁用用户测试。"""

    @pytest.fixture(autouse=True)
    def _auth(self, client):
        login(client)

    def test_admin_can_disable_user(self, client):
        """管理员可以禁用其他用户。"""
        resp = client.post("/auth/users", json={
            "username": "disable-me", "password": "disable-me-pass",
        })
        uid = resp.json()["id"]
        resp = client.patch(f"/auth/users/{uid}/status", json={"is_active": False})
        assert resp.status_code == 200
        assert resp.json()["is_active"] is False

    def test_admin_cannot_disable_self(self, client):
        """管理员不能禁用自己。"""
        me = client.get("/auth/me").json()
        # Get admin user id from user list
        users = client.get("/auth/users").json()
        admin_user = [u for u in users if u["role"] == "admin"][0]
        resp = client.patch(f"/auth/users/{admin_user['id']}/status", json={"is_active": False})
        assert resp.status_code == 400

    def test_disabled_user_cannot_login(self, client):
        """禁用用户不能登录。"""
        resp = client.post("/auth/users", json={
            "username": "disabled-login", "password": "disabled-pass",
        })
        uid = resp.json()["id"]
        client.patch(f"/auth/users/{uid}/status", json={"is_active": False})

        client.cookies.clear()
        resp = client.post("/auth/login", json={
            "username": "disabled-login", "password": "disabled-pass",
        })
        assert resp.status_code == 403
        assert "已被禁用" in resp.json()["detail"]

    def test_disabled_user_session_rejected(self, client):
        """禁用用户已有旧 session 访问受保护接口应被拒绝。"""
        # Create and login as a user
        resp = client.post("/auth/users", json={
            "username": "session-kill", "password": "session-kill-pass",
        })
        uid = resp.json()["id"]
        client.cookies.clear()
        resp = client.post("/auth/login", json={
            "username": "session-kill", "password": "session-kill-pass",
        })
        assert resp.status_code == 200
        # Save the session cookie value from set-cookie header
        set_cookie = resp.headers.get("set-cookie", "")
        # Extract session=<value> from set-cookie
        saved_session = None
        for part in set_cookie.split(";"):
            part = part.strip()
            if part.startswith("session="):
                saved_session = part.split("=", 1)[1]
                break
        assert saved_session is not None, "No session cookie found in login response"

        # Admin disables this user
        client.cookies.clear()
        login(client)
        client.patch(f"/auth/users/{uid}/status", json={"is_active": False})

        # Restore the disabled user's OLD session cookie
        client.cookies.clear()
        client.cookies.set("session", saved_session)

        # Old session should be rejected on protected endpoint
        resp = client.get("/products")
        assert resp.status_code == 403, f"Expected 403 for disabled user session, got {resp.status_code}"

        # Also verify re-login is rejected
        client.cookies.clear()
        resp = client.post("/auth/login", json={
            "username": "session-kill", "password": "session-kill-pass",
        })
        assert resp.status_code == 403

    def test_admin_can_reenable_user(self, client):
        """管理员可以重新启用用户，启用后可以登录。"""
        resp = client.post("/auth/users", json={
            "username": "reenable-me", "password": "reenable-pass",
        })
        uid = resp.json()["id"]
        client.patch(f"/auth/users/{uid}/status", json={"is_active": False})
        client.patch(f"/auth/users/{uid}/status", json={"is_active": True})

        client.cookies.clear()
        resp = client.post("/auth/login", json={
            "username": "reenable-me", "password": "reenable-pass",
        })
        assert resp.status_code == 200

    def test_normal_user_cannot_change_status(self, client):
        """普通用户不能修改用户状态。"""
        resp = client.post("/auth/users", json={
            "username": "status-denied", "password": "status-denied-pass",
        })
        uid = resp.json()["id"]
        client.cookies.clear()
        resp = client.post("/auth/login", json={
            "username": "status-denied", "password": "status-denied-pass",
        })
        assert resp.status_code == 200
        resp = client.patch(f"/auth/users/{uid}/status", json={"is_active": False})
        assert resp.status_code == 403


class TestChangePassword:
    """修改密码测试。"""

    @pytest.fixture(autouse=True)
    def _auth(self, client):
        login(client)

    def test_change_password_success(self, client):
        """当前用户修改密码成功，然后恢复原密码避免影响其他测试。"""
        resp = client.post("/auth/change-password", json={
            "old_password": "test-password",
            "new_password": "new-test-password",
        })
        assert resp.status_code == 200
        assert "成功" in resp.json()["message"]
        # Restore original password so subsequent tests can log in
        client.post("/auth/change-password", json={
            "old_password": "new-test-password",
            "new_password": "test-password",
        })

    def test_old_password_cannot_login_after_change(self, client):
        """修改密码后旧密码不能登录，新密码可以登录。"""
        # Create a fresh user
        client.post("/auth/users", json={
            "username": "pw-test-user", "password": "pw-old-pass",
        })
        client.cookies.clear()
        client.post("/auth/login", json={
            "username": "pw-test-user", "password": "pw-old-pass",
        })
        # Change password
        client.post("/auth/change-password", json={
            "old_password": "pw-old-pass",
            "new_password": "pw-new-pass",
        })
        client.cookies.clear()
        # Old password should fail
        resp = client.post("/auth/login", json={
            "username": "pw-test-user", "password": "pw-old-pass",
        })
        assert resp.status_code == 401
        # New password should succeed
        resp = client.post("/auth/login", json={
            "username": "pw-test-user", "password": "pw-new-pass",
        })
        assert resp.status_code == 200

    def test_change_password_wrong_old_fails(self, client):
        """修改密码时 old_password 错误会失败。"""
        resp = client.post("/auth/change-password", json={
            "old_password": "wrong-password",
            "new_password": "irrelevant",
        })
        assert resp.status_code == 400
        assert "错误" in resp.json()["detail"]

    def test_change_password_short_new_fails(self, client):
        """新密码太短会失败。"""
        resp = client.post("/auth/change-password", json={
            "old_password": "test-password",
            "new_password": "ab",
        })
        assert resp.status_code == 400

    def test_disabled_user_cannot_change_password(self, client):
        """禁用用户不能修改密码。"""
        resp = client.post("/auth/users", json={
            "username": "cp-disabled", "password": "cp-disabled-pass",
        })
        uid = resp.json()["id"]
        client.patch(f"/auth/users/{uid}/status", json={"is_active": False})
        client.cookies.clear()
        # Try to login (should fail)
        resp = client.post("/auth/login", json={
            "username": "cp-disabled", "password": "cp-disabled-pass",
        })
        assert resp.status_code == 403
