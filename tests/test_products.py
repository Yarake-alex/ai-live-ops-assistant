import io

import pytest

# 商品基础数据。测试共享 session 级数据库，商品名使用类内唯一前缀避免互相干扰。
PRODUCT_DATA = {
    "name": "玻尿酸保湿精华-基础测试",
    "price": 99.5,
    "selling_points": "深层补水，长效保湿",
    "target_audience": "干性皮肤人群",
    "pain_points": "皮肤干燥起皮",
    "promotion": "买二送一",
    "stock": 100,
    "live_status": "待上播",
    "notes": "测试商品",
}


def login(client):
    """辅助函数：用 test-password 登录管理员。"""
    client.cookies.clear()
    resp = client.post("/auth/login", json={"password": "test-password"})
    assert resp.status_code == 200


def _create_second_user(client, username, password="second-user-password"):
    """管理员创建第二个用户并返回登录后的客户端（同一 TestClient 换 Cookie）。"""
    login(client)
    resp = client.post(
        "/auth/users",
        json={"username": username, "password": password},
    )
    assert resp.status_code == 200, f"Failed to create {username}: {resp.json()}"
    client.cookies.clear()
    resp = client.post("/auth/login", json={"username": username, "password": password})
    assert resp.status_code == 200
    return client


def _csv_upload(client, filename, content):
    return client.post(
        "/products/import",
        files={"file": (filename, content.encode("utf-8"), "text/csv")},
    )


# ─── 鉴权 ───

class TestProductAuth:
    def test_products_require_login(self, client):
        client.cookies.clear()
        for method, url, kwargs in [
            ("get", "/products", {}),
            ("get", "/products/search", {}),
            ("post", "/products", {"json": PRODUCT_DATA}),
            ("get", "/products/export", {}),
            ("post", "/products/import", {}),
        ]:
            resp = getattr(client, method)(url, **kwargs)
            assert resp.status_code == 401, f"{method.upper()} {url} 未登录应返回 401"

    def test_products_accessible_after_login(self, client):
        login(client)
        resp = client.get("/products")
        assert resp.status_code == 200


# ─── 商品 CRUD ───

@pytest.fixture
def product_id(client):
    """创建一个测试商品，返回其 id。"""
    login(client)
    resp = client.post("/products", json=PRODUCT_DATA)
    assert resp.status_code == 200
    return resp.json()["id"]


class TestProducts:
    @pytest.fixture(autouse=True)
    def _auth(self, client):
        login(client)

    def test_create_product(self, client):
        resp = client.post("/products", json=PRODUCT_DATA)
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == PRODUCT_DATA["name"]
        assert data["price"] == 99.5
        assert data["stock"] == 100
        assert data["selling_points"] == "深层补水，长效保湿"
        assert data["target_audience"] == "干性皮肤人群"
        assert data["pain_points"] == "皮肤干燥起皮"
        assert data["promotion"] == "买二送一"
        assert data["live_status"] == "待上播"
        assert "id" in data

    def test_create_product_defaults(self, client):
        resp = client.post("/products", json={"name": "默认值测试商品-甲"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["price"] == 0
        assert data["stock"] == 0
        assert data["live_status"] == "未上播"

    def test_list_products_contains_created(self, client):
        resp = client.post("/products", json={"name": "列表测试商品-乙"})
        assert resp.status_code == 200
        resp = client.get("/products")
        assert resp.status_code == 200
        names = [p["name"] for p in resp.json()]
        assert "列表测试商品-乙" in names

    def test_get_product_detail(self, client, product_id):
        resp = client.get(f"/products/{product_id}")
        assert resp.status_code == 200
        assert resp.json()["name"] == PRODUCT_DATA["name"]


class TestProductEditDelete:
    @pytest.fixture(autouse=True)
    def _auth(self, client):
        login(client)

    def test_update_own_product(self, client, product_id):
        updated = {**PRODUCT_DATA, "name": "玻尿酸保湿精华-已编辑", "price": 129.9, "stock": 50}
        resp = client.put(f"/products/{product_id}", json=updated)
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "玻尿酸保湿精华-已编辑"
        assert data["price"] == 129.9
        assert data["stock"] == 50

    def test_delete_own_product(self, client, product_id):
        resp = client.delete(f"/products/{product_id}")
        assert resp.status_code == 200
        resp = client.get(f"/products/{product_id}")
        assert resp.status_code == 404

    def test_update_other_users_product_forbidden(self, client, product_id):
        other = _create_second_user(client, "prod-edit-other-user")
        resp = other.put(f"/products/{product_id}", json={**PRODUCT_DATA, "name": "越权修改"})
        assert resp.status_code == 404

    def test_delete_other_users_product_forbidden(self, client, product_id):
        other = _create_second_user(client, "prod-del-other-user")
        resp = other.delete(f"/products/{product_id}")
        assert resp.status_code == 404


# ─── 搜索 / 筛选 / 分页 ───

class TestProductSearch:
    @pytest.fixture(autouse=True)
    def _auth(self, client):
        login(client)

    @pytest.fixture(autouse=True)
    def _seed(self, client):
        """为搜索测试准备独立关键词的商品，测试结束后清理。"""
        ids = []
        for payload in [
            {"name": "搜索测试-保湿面霜", "selling_points": "锁水屏障修护", "live_status": "待上播"},
            {"name": "搜索测试-洁面泡沫", "pain_points": "敏感肌泛红刺痛", "live_status": "直播中"},
            {"name": "搜索测试-防晒乳", "target_audience": "户外运动爱好者", "live_status": "已下播"},
        ]:
            resp = client.post("/products", json=payload)
            assert resp.status_code == 200
            ids.append(resp.json()["id"])
        yield
        for pid in ids:
            client.delete(f"/products/{pid}")

    def test_search_by_name_keyword(self, client):
        resp = client.get("/products/search", params={"q": "洁面泡沫"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["items"][0]["name"] == "搜索测试-洁面泡沫"

    def test_search_by_selling_points(self, client):
        resp = client.get("/products/search", params={"q": "锁水屏障"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1
        assert any(p["name"] == "搜索测试-保湿面霜" for p in data["items"])

    def test_search_by_pain_points(self, client):
        resp = client.get("/products/search", params={"q": "敏感肌"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1
        assert any(p["name"] == "搜索测试-洁面泡沫" for p in data["items"])

    def test_filter_by_live_status(self, client):
        resp = client.get("/products/search", params={"live_status": "直播中"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1
        assert all(p["live_status"] == "直播中" for p in data["items"])


class TestProductPagination:
    """用独立 live_status 标记分页测试数据，避免共享库中其他数据干扰。"""

    MARKER = "分页专用"

    @pytest.fixture(autouse=True)
    def _auth(self, client):
        login(client)

    @pytest.fixture(autouse=True)
    def _seed(self, client):
        ids = []
        for i in range(1, 13):
            resp = client.post(
                "/products",
                json={"name": f"分页测试商品-{i}", "live_status": self.MARKER},
            )
            assert resp.status_code == 200
            ids.append(resp.json()["id"])
        yield
        for pid in ids:
            client.delete(f"/products/{pid}")

    def test_pagination_returns_correct_page(self, client):
        resp = client.get(
            "/products/search",
            params={"live_status": self.MARKER, "page": 2, "page_size": 5},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 12
        assert data["page"] == 2
        assert data["page_size"] == 5
        assert data["pages"] == 3
        assert len(data["items"]) == 5

    def test_pagination_page_beyond_range_clamps_to_last(self, client):
        resp = client.get(
            "/products/search",
            params={"live_status": self.MARKER, "page": 999, "page_size": 5},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["page"] == data["pages"] == 3
        assert len(data["items"]) == 2

    def test_pagination_does_not_leak_other_products(self, client):
        """分页只返回当前筛选范围内的数据。"""
        resp = client.get(
            "/products/search",
            params={"live_status": self.MARKER, "page": 1, "page_size": 100},
        )
        data = resp.json()
        assert data["total"] == 12
        assert all(p["live_status"] == self.MARKER for p in data["items"])


# ─── 用户数据隔离 ───

class TestProductIsolation:
    def test_other_user_cannot_see_my_products(self, client):
        login(client)
        resp = client.post("/products", json={"name": "隔离测试-我的商品"})
        assert resp.status_code == 200
        product_id = resp.json()["id"]

        other = _create_second_user(client, "prod-iso-user-a")

        resp = other.get("/products")
        assert resp.status_code == 200
        assert all(p["name"] != "隔离测试-我的商品" for p in resp.json())

        assert other.get(f"/products/{product_id}").status_code == 404
        assert other.put(f"/products/{product_id}", json={"name": "越权"}).status_code == 404
        assert other.delete(f"/products/{product_id}").status_code == 404

        # 管理员自己仍可见
        login(client)
        resp = client.get(f"/products/{product_id}")
        assert resp.status_code == 200

    def test_import_only_creates_for_current_user(self, client):
        login(client)
        csv_content = "name,price,stock,live_status\n隔离导入商品,59.9,10,待上播\n"
        resp = _csv_upload(client, "iso_import.csv", csv_content)
        assert resp.status_code == 200
        assert resp.json()["created"] == 1

        other = _create_second_user(client, "prod-iso-user-b")
        resp = other.get("/products")
        assert all(p["name"] != "隔离导入商品" for p in resp.json())

    def test_export_only_contains_current_user_products(self, client):
        login(client)
        resp = client.post("/products", json={"name": "导出隔离测试-管理员的商品"})
        assert resp.status_code == 200

        # 管理员导出包含自己的商品
        resp = client.get("/products/export")
        assert resp.status_code == 200
        assert "导出隔离测试-管理员的商品" in resp.text

        # 第二个用户导出不包含管理员的商品
        other = _create_second_user(client, "prod-iso-user-c")
        resp = other.get("/products/export")
        assert resp.status_code == 200
        assert "导出隔离测试-管理员的商品" not in resp.text


# ─── CSV 导入 / 导出 ───

class TestProductCsv:
    @pytest.fixture(autouse=True)
    def _auth(self, client):
        login(client)

    def test_import_english_headers(self, client):
        csv_content = (
            "name,price,selling_points,target_audience,pain_points,promotion,stock,live_status,notes\n"
            "导入英文表头商品,19.9,提亮肤色,熬夜人群,肤色暗沉,第二件半价,88,直播中,英文表头测试\n"
        )
        resp = _csv_upload(client, "products_en.csv", csv_content)
        assert resp.status_code == 200
        data = resp.json()
        assert data["created"] == 1
        assert data["errors"] == []

        resp = client.get("/products/search", params={"q": "导入英文表头商品"})
        product = resp.json()["items"][0]
        assert product["price"] == 19.9
        assert product["stock"] == 88
        assert product["live_status"] == "直播中"
        assert product["selling_points"] == "提亮肤色"

    def test_import_chinese_headers(self, client):
        csv_content = (
            "商品名称,价格,核心卖点,适用人群,用户痛点,优惠信息,库存,直播状态,备注\n"
            "导入中文表头商品,29.9,清爽不油腻,油皮人群,出油脱妆,满100减20,66,待上播,中文表头测试\n"
        )
        resp = _csv_upload(client, "products_zh.csv", csv_content)
        assert resp.status_code == 200
        data = resp.json()
        assert data["created"] == 1
        assert data["errors"] == []

        resp = client.get("/products/search", params={"q": "导入中文表头商品"})
        product = resp.json()["items"][0]
        assert product["price"] == 29.9
        assert product["stock"] == 66
        assert product["live_status"] == "待上播"

    def test_import_skips_duplicate_names_in_batch(self, client):
        csv_content = (
            "name,price\n"
            "批量去重商品,10\n"
            "批量去重商品,20\n"
        )
        resp = _csv_upload(client, "products_dup.csv", csv_content)
        assert resp.status_code == 200
        data = resp.json()
        assert data["created"] == 1
        assert data["skipped"] == 1

    def test_import_skips_existing_product(self, client):
        csv_content = "name,price\n重复导入商品,10\n"
        resp = _csv_upload(client, "products_existing.csv", csv_content)
        assert resp.status_code == 200
        assert resp.json()["created"] == 1

        # 再次导入同一名称 → 跳过
        resp = _csv_upload(client, "products_existing.csv", csv_content)
        assert resp.status_code == 200
        assert resp.json()["created"] == 0
        assert resp.json()["skipped"] == 1

    def test_import_invalid_price_reports_error(self, client):
        csv_content = "name,price\n坏价格商品,abc\n"
        resp = _csv_upload(client, "products_badprice.csv", csv_content)
        assert resp.status_code == 200
        data = resp.json()
        assert data["created"] == 0
        assert len(data["errors"]) == 1
        assert "price" in data["errors"][0]["reason"]

    def test_import_missing_name_reports_error(self, client):
        csv_content = "name,price\n,10\n"
        resp = _csv_upload(client, "products_noname.csv", csv_content)
        assert resp.status_code == 200
        data = resp.json()
        assert data["created"] == 0
        assert len(data["errors"]) == 1
        assert "name" in data["errors"][0]["reason"]

    def test_import_rejects_non_csv_file(self, client):
        resp = client.post(
            "/products/import",
            files={"file": ("data.txt", b"not csv", "text/plain")},
        )
        assert resp.status_code == 400

    def test_export_contains_headers_and_rows(self, client):
        resp = client.post("/products", json={"name": "导出内容测试商品", "price": 39.9, "stock": 7})
        assert resp.status_code == 200

        resp = client.get("/products/export")
        assert resp.status_code == 200
        assert resp.content.startswith(b"\xef\xbb\xbf")  # UTF-8 BOM（原始字节）
        text = resp.text  # TestClient 按 charset=utf-8-sig 解码后不含 BOM
        assert "name,price,selling_points,target_audience,pain_points,promotion,stock,live_status,notes,created_at" in text
        assert "导出内容测试商品" in text

    def test_export_import_roundtrip(self, client):
        """导出后再导入，字段保持一致（除 created_at 外）。

        全程在第二个用户账号内进行，避免共享库中管理员的商品干扰导出结果。
        """
        other = _create_second_user(client, "prod-roundtrip-user")

        resp = other.post(
            "/products",
            json={
                "name": "往返测试商品",
                "price": 49.9,
                "selling_points": "卖点A",
                "target_audience": "人群A",
                "pain_points": "痛点A",
                "promotion": "优惠A",
                "stock": 33,
                "live_status": "待上播",
                "notes": "备注A",
            },
        )
        assert resp.status_code == 200
        product_id = resp.json()["id"]

        # 导出该用户的商品（此时只有这一个商品）
        resp = other.get("/products/export")
        assert resp.status_code == 200
        exported = resp.text

        # 删除原商品后重新导入，验证字段往返一致
        assert other.delete(f"/products/{product_id}").status_code == 200
        resp = other.post(
            "/products/import",
            files={"file": ("roundtrip.csv", exported.encode("utf-8-sig"), "text/csv")},
        )
        assert resp.status_code == 200
        assert resp.json()["created"] == 1

        resp = other.get("/products/search", params={"q": "往返测试商品"})
        product = resp.json()["items"][0]
        assert product["price"] == 49.9
        assert product["selling_points"] == "卖点A"
        assert product["target_audience"] == "人群A"
        assert product["pain_points"] == "痛点A"
        assert product["promotion"] == "优惠A"
        assert product["stock"] == 33
        assert product["live_status"] == "待上播"
        assert product["notes"] == "备注A"
