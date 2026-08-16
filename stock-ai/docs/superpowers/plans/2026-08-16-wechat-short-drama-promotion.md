# 公众号长文短剧推广 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为公众号所有长图文接入微信 `DramaSelect` 短剧池，按内容相关度自动选择并插入一个可归因的 `short-play` 组件，同时彻底禁止普通返佣商品回退。

**Architecture:** 新建独立的 `wechat_mp_short_drama.py`，负责列表 API、缓存、过滤、去重、评分、轮换、组件构建与门禁；现有 `wechat_mp_product.py` 只保留独立 `commerce` 的普通商品能力。长文在所有正文和 CTA 重排结束后统一调用短剧附加器，推稿前检查组件类型，成功写入后按 `media_id` 回读验证。

**Tech Stack:** Python 3、`requests`、dataclass、JSON 原子缓存、微信草稿 API、pytest、现有 `wechat_mp_client` 与 `wechat_mp_content` 流水线。

## Global Constraints

- 适用稿型固定为 `hotspot`、`tv_review`、`tv`、`film`、`movie`、`sector`、`market`、`news`、`top5`、`dragons`、`workspace` 和 `temp`。
- 不处理 `newspic`、栀夏生活贴图、小绿书和独立 `commerce`。
- 每篇长文只插入一个短剧组件，位置为正文约三分之二处的完整区块边界。
- 短剧组件必须带 `data-adtype="short-play"`；长文不得生成普通返佣商品组件或 `product_info.footer_product_info`。
- 短剧失败时必须失败关闭，不得回退普通商品。
- 下线时间不足七天、状态异常、字段缺失、集数为零或分佣为零的候选不得进入短剧池。
- 同名候选依次按分佣、下线时间、热度和稳定 ID 去重。
- 排序权重固定为相关度 50%、热度 30%、分佣 20%；七天内优先避免重复。
- 短剧列表缓存默认六小时，已到期缓存不得在刷新失败时继续使用。
- `WECHAT_MP_DRAMA_KOL_ID`、Cookie、token、`wxTicket` 和编辑页 URL 不得提交到 Git。
- 在归因票据和回读验证通过前，不得默认开启全量长文短剧注入。

---

## File Structure

- Create: `stock-ai/scripts/tools/wechat_mp_short_drama.py` — 短剧 API、模型、缓存、过滤、排序、轮换、组件生成和诊断 CLI。
- Create: `stock-ai/tests/unit/test_wechat_mp_short_drama.py` — 短剧模块的单元测试真源。
- Modify: `stock-ai/scripts/tools/wechat_mp_content.py` — 在最终 HTML 完成后附加短剧，不再为长文附加普通商品。
- Modify: `stock-ai/scripts/tools/wechat_mp_product.py` — 普通返佣商品仅允许独立 `commerce` 使用，并提供普通商品识别门禁。
- Modify: `stock-ai/scripts/tools/wechat_mp_seo.py` — 正文重建后调用短剧附加器，避免 SEO 同步恢复普通商品。
- Modify: `stock-ai/scripts/tools/wechat_mp_draft.py` — dry-run 输出短剧摘要；写入前校验，写入后回读组件。
- Modify: `stock-ai/tests/unit/test_wechat_mp_product.py` — 锁定普通商品不再进入长文。
- Modify: `stock-ai/tests/unit/test_wechat_mp_disclaimer_render.py` — 锁定短剧组件位于正文区且避开免责声明。
- Modify: `stock-ai/.env.example` — 记录短剧开关和非敏感配置名。
- Modify: `.cursor/skills/wechat-mp-drafts/operations-sop.md` — 更新长文推广运维与故障处理。
- Modify: `.cursor/skills/wechat-mp-drafts/reference.md` — 增加短剧接口、缓存和诊断命令。
- Generated, do not commit: `stock-ai/data/wechat_mp_short_drama_pool.json` — 六小时短剧池缓存。
- Generated, do not commit: `stock-ai/data/wechat_mp_short_drama_usage.json` — 七天轮换使用记录。
- Generated, do not commit: `stock-ai/data/wechat_mp_short_drama_attribution.json` — 已验证归因模板或票据元数据。

### Task 1: DramaSelect 客户端、模型与缓存

**Files:**
- Create: `stock-ai/scripts/tools/wechat_mp_short_drama.py`
- Create: `stock-ai/tests/unit/test_wechat_mp_short_drama.py`
- Modify: `stock-ai/.env.example`

**Interfaces:**
- Consumes: `WECHAT_MP_DRAMA_KOL_ID`、`WECHAT_MP_DRAMA_CACHE_TTL_HOURS` 和 `DramaSelect` JSON。
- Produces: `ShortDrama`、`fetch_drama_page()`、`load_or_refresh_drama_pool()` 和 `short_drama_enabled()`。

- [ ] **Step 1: 写 DramaSelect 解析失败测试**

```python
from datetime import datetime
from zoneinfo import ZoneInfo

from scripts.tools.wechat_mp_short_drama import ShortDrama, parse_drama_response


def test_parse_drama_response_uses_recommend_list() -> None:
    payload = {
        "ret": 0,
        "total": "2145",
        "trace_id": "trace-page-1",
        "recommend_list": [{
            "drama_id": "1713873",
            "drama_name": "修好铁疙瘩转身踏青云",
            "src_appid": "wx-source",
            "play_appid": "wx-player",
            "cover_url": "https://example.test/cover.jpg",
            "era": "现代",
            "theme": "职场",
            "desc": "下岗技师修复精密机床。",
            "status": 1,
            "plan_id": "plan-1",
            "rate": "6000",
            "hot_degree": 21052623,
            "media_count": "60",
            "real_offline_time": "1797992049",
            "preview_path": "plugin-private://player/pages/playlet?dramaId=1713873",
            "preview_sn": "preview-1",
        }],
    }

    rows, total = parse_drama_response(payload, fetched_at=datetime(2026, 8, 16, tzinfo=ZoneInfo("Asia/Shanghai")))

    assert total == 2145
    assert rows == [ShortDrama(
        drama_id="1713873",
        drama_name="修好铁疙瘩转身踏青云",
        src_appid="wx-source",
        play_appid="wx-player",
        cover_url="https://example.test/cover.jpg",
        era="现代",
        theme="职场",
        description="下岗技师修复精密机床。",
        status=1,
        plan_id="plan-1",
        rate_bp=6000,
        hot_degree=21052623,
        media_count=60,
        offline_timestamp=1797992049,
        preview_path="plugin-private://player/pages/playlet?dramaId=1713873",
        preview_sn="preview-1",
        page_trace_id="trace-page-1",
        fetched_at="2026-08-16T00:00:00+08:00",
    )]
```

- [ ] **Step 2: 运行测试确认失败**

Run:

```bash
cd stock-ai
PYTHONPATH=. .venv/bin/python -m pytest tests/unit/test_wechat_mp_short_drama.py::test_parse_drama_response_uses_recommend_list -q
```

Expected: FAIL，提示模块或 `parse_drama_response` 不存在。

- [ ] **Step 3: 实现数据模型和解析器**

在新模块中定义：

```python
@dataclass(frozen=True)
class ShortDrama:
    drama_id: str
    drama_name: str
    src_appid: str
    play_appid: str
    cover_url: str
    era: str
    theme: str
    description: str
    status: int
    plan_id: str
    rate_bp: int
    hot_degree: int
    media_count: int
    offline_timestamp: int
    preview_path: str
    preview_sn: str
    page_trace_id: str
    fetched_at: str


def parse_drama_response(payload: Mapping[str, Any], *, fetched_at: datetime) -> tuple[list[ShortDrama], int]:
    if int(payload.get("ret") or 0) != 0:
        raise RuntimeError(str(payload.get("msg") or "DramaSelect 失败"))
    total = int(payload.get("total") or 0)
    trace_id = str(payload.get("trace_id") or "")
    rows = [
        ShortDrama(
            drama_id=str(row.get("drama_id") or ""),
            drama_name=str(row.get("drama_name") or "").strip(),
            src_appid=str(row.get("src_appid") or ""),
            play_appid=str(row.get("play_appid") or ""),
            cover_url=str(row.get("cover_url") or ""),
            era=str(row.get("era") or "").strip(),
            theme=str(row.get("theme") or "").strip(),
            description=str(row.get("desc") or "").strip(),
            status=_as_int(row.get("status")),
            plan_id=str(row.get("plan_id") or ""),
            rate_bp=_as_int(row.get("rate")),
            hot_degree=_as_int(row.get("hot_degree")),
            media_count=_as_int(row.get("media_count")),
            offline_timestamp=_as_int(row.get("real_offline_time")),
            preview_path=str(row.get("preview_path") or ""),
            preview_sn=str(row.get("preview_sn") or ""),
            page_trace_id=trace_id,
            fetched_at=fetched_at.isoformat(timespec="seconds"),
        )
        for row in payload.get("recommend_list") or []
        if isinstance(row, Mapping)
    ]
    return rows, total
```

数字字段使用一个私有 `_as_int()` 统一处理空字符串和异常值；不能把解析异常吞成完整候选。

- [ ] **Step 4: 写分页、配置和缓存测试**

新增测试，使用假的 `requests.Session` 断言：

```python
def test_fetch_drama_page_posts_exact_contract(monkeypatch):
    monkeypatch.setenv("WECHAT_MP_DRAMA_KOL_ID", "kol-test")
    session = FakeSession(response=DRAMA_RESPONSE)
    rows, total = fetch_drama_page(page_no=4, page_size=10, session=session)
    assert session.last_json == {
        "flow_type": 3,
        "query": {},
        "page": {"no": 4, "size": 10},
        "kol_info": {"id": "kol-test"},
    }
    assert total == 2145


def test_expired_cache_is_not_used_when_refresh_fails(tmp_path, monkeypatch):
    write_cache(tmp_path, fetched_at="2026-08-15T00:00:00+08:00")
    monkeypatch.setattr(
        "scripts.tools.wechat_mp_short_drama.refresh_drama_pool",
        lambda **kwargs: (_ for _ in ()).throw(RuntimeError("network")),
    )
    with pytest.raises(RuntimeError, match="短剧列表刷新失败"):
        load_or_refresh_drama_pool(cache_path=tmp_path, now=NOW)
```

- [ ] **Step 5: 实现分页获取和原子缓存**

实现签名：

```python
def short_drama_enabled() -> bool:
    return os.getenv("WECHAT_MP_SHORT_DRAMA", "0").strip().lower() in {"1", "true", "yes", "on"}


def drama_kol_id() -> str:
    value = os.getenv("WECHAT_MP_DRAMA_KOL_ID", "").strip()
    if not value:
        raise RuntimeError("缺少 WECHAT_MP_DRAMA_KOL_ID")
    return value


def fetch_drama_page(*, page_no: int, page_size: int = 30, session: requests.Session | None = None) -> tuple[list[ShortDrama], int]:
    client = session or requests.Session()
    client.trust_env = False
    response = client.post(
        DRAMA_SELECT_URL,
        headers={"accept": "application/json", "content-type": "application/json", "Referer": "https://file.daihuo.qq.com/", "Origin": "https://file.daihuo.qq.com"},
        json={"flow_type": 3, "query": {}, "page": {"no": page_no, "size": page_size}, "kol_info": {"id": drama_kol_id()}},
        timeout=30,
    )
    response.raise_for_status()
    return parse_drama_response(response.json(), fetched_at=datetime.now(TZ))
```

`refresh_drama_pool()` 从第一页开始调用 `fetch_drama_page()`，累计数量达到 `total`、遇到空页或达到显式 `max_pages` 后停止；写入 `{fetched_at,total,items}`。`load_or_refresh_drama_pool()` 解析 `fetched_at`，把 `fetched_at + ttl - min(30 分钟, ttl / 4)` 作为主动刷新时间，把 `fetched_at + ttl` 作为硬过期时间：主动刷新前直接使用缓存；主动刷新失败但未硬过期时继续使用旧缓存；硬过期后刷新失败则抛出 `RuntimeError("短剧列表刷新失败且缓存已过期")`。

分页在累计条目数达到 `total` 或返回空页时停止；缓存写临时文件后 `replace()`。`.env.example` 增加：

```dotenv
# WECHAT_MP_SHORT_DRAMA=0
# WECHAT_MP_DRAMA_KOL_ID=
# WECHAT_MP_DRAMA_CACHE_TTL_HOURS=6
# WECHAT_MP_DRAMA_MIN_VALID_DAYS=7
# WECHAT_MP_DRAMA_REPEAT_DAYS=7
```

- [ ] **Step 6: 运行 Task 1 测试**

Run: `cd stock-ai && PYTHONPATH=. .venv/bin/python -m pytest tests/unit/test_wechat_mp_short_drama.py -q`

Expected: PASS。

- [ ] **Step 7: 提交 Task 1**

```bash
git add stock-ai/scripts/tools/wechat_mp_short_drama.py stock-ai/tests/unit/test_wechat_mp_short_drama.py stock-ai/.env.example
git commit -m "feat: add WeChat short drama pool client"
```

### Task 2: 候选过滤、同名去重、内容评分和轮换

**Files:**
- Modify: `stock-ai/scripts/tools/wechat_mp_short_drama.py`
- Modify: `stock-ai/tests/unit/test_wechat_mp_short_drama.py`

**Interfaces:**
- Consumes: `list[ShortDrama]`、文章标题/摘要/正文和本地使用记录。
- Produces: `eligible_dramas()`、`dedupe_dramas()`、`score_drama()`、`pick_short_drama()` 和 `record_drama_usage()`。

- [ ] **Step 1: 写过滤和去重失败测试**

```python
def test_eligible_and_dedupe_dramas_keep_best_live_plan() -> None:
    rows = [
        drama("同名剧", drama_id="1", rate_bp=6000, offline_days=90, hot=100),
        drama("同名剧", drama_id="2", rate_bp=7000, offline_days=30, hot=50),
        drama("即将下线", drama_id="3", offline_days=3),
        drama("字段缺失", drama_id="4", play_appid=""),
    ]
    out = dedupe_dramas(eligible_dramas(rows, now=NOW, min_valid_days=7))
    assert [x.drama_id for x in out] == ["2"]
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd stock-ai && PYTHONPATH=. .venv/bin/python -m pytest tests/unit/test_wechat_mp_short_drama.py::test_eligible_and_dedupe_dramas_keep_best_live_plan -q`

Expected: FAIL，提示筛选函数不存在。

- [ ] **Step 3: 实现过滤和稳定去重**

实现：

```python
def normalize_drama_name(value: str) -> str:
    return re.sub(r"[^0-9A-Za-z\u4e00-\u9fff]+", "", value).lower()


def eligible_dramas(rows: Sequence[ShortDrama], *, now: datetime, min_valid_days: int) -> list[ShortDrama]:
    cutoff = int((now + timedelta(days=min_valid_days)).timestamp())
    required = lambda row: all((row.drama_id, row.drama_name, row.src_appid, row.play_appid, row.cover_url, row.plan_id, row.preview_path))
    return [row for row in rows if row.status == 1 and required(row) and row.offline_timestamp >= cutoff and row.media_count > 0 and row.rate_bp > 0]


def dedupe_dramas(rows: Sequence[ShortDrama]) -> list[ShortDrama]:
    winners: dict[str, ShortDrama] = {}
    for row in rows:
        key = normalize_drama_name(row.drama_name)
        current = winners.get(key)
        if current is None or (-row.rate_bp, -row.offline_timestamp, -row.hot_degree, row.drama_id) < (-current.rate_bp, -current.offline_timestamp, -current.hot_degree, current.drama_id):
            winners[key] = row
    return sorted(winners.values(), key=lambda row: (-row.hot_degree, row.drama_id))
```

去重比较键固定为 `(rate_bp, offline_timestamp, hot_degree, drama_id)`，前三项降序，最后一项升序；测试不得依赖输入顺序。

- [ ] **Step 4: 写相关度和轮换失败测试**

```python
def test_pick_short_drama_prefers_relevant_workplace_story(tmp_path: Path) -> None:
    rows = [
        drama("总裁甜宠", theme="爱情", description="豪门爱情", hot=1000),
        drama("报销风波后，整个公司都慌了", theme="都市、职场", description="公司报销制度", hot=500),
    ]
    article = {"title": "公司报销为什么越来越严格", "digest": "职场制度观察", "body_text": "员工提交报销单。"}
    picked = pick_short_drama(article, rows, kind="workspace", usage_path=tmp_path / "usage.json", now=NOW)
    assert picked.drama_name == "报销风波后，整个公司都慌了"


def test_pick_short_drama_avoids_same_drama_within_seven_days(tmp_path: Path) -> None:
    first = pick_short_drama(ARTICLE, ROWS, kind="hotspot", usage_path=path, now=NOW)
    record_drama_usage(first, article_title="第一篇", usage_path=path, used_at=NOW)
    second = pick_short_drama(ARTICLE, ROWS, kind="hotspot", usage_path=path, now=NOW + timedelta(days=1))
    assert second.drama_id != first.drama_id
```

- [ ] **Step 5: 实现可解释评分和使用记录**

实现：

```python
WORKPLACE_KINDS = frozenset({"sector", "market", "news", "top5", "dragons", "workspace", "temp"})


def article_match_text(article: Mapping[str, Any]) -> str:
    raw = " ".join(str(article.get(key) or "") for key in ("title", "digest", "body_text"))
    return raw[:1200]


def _bigrams(value: str) -> set[str]:
    compact = re.sub(r"[^0-9A-Za-z\u4e00-\u9fff]+", "", value).lower()
    return {compact[index:index + 2] for index in range(max(0, len(compact) - 1))}


def _minmax(value: int, values: Sequence[int]) -> float:
    low, high = min(values), max(values)
    return 0.5 if low == high else (value - low) / (high - low)


def score_drama(drama: ShortDrama, *, match_text: str, kind: str, population: Sequence[ShortDrama]) -> float:
    article_terms = _bigrams(match_text)
    drama_terms = _bigrams(" ".join((drama.drama_name, drama.era, drama.theme, drama.description)))
    relevance = len(article_terms & drama_terms) / max(1, min(20, len(drama_terms)))
    if kind in WORKPLACE_KINDS and any(term in drama.theme for term in ("职场", "都市", "励志")):
        relevance = min(1.0, relevance + 0.15)
    heat = _minmax(drama.hot_degree, [row.hot_degree for row in population])
    rate = _minmax(drama.rate_bp, [row.rate_bp for row in population])
    return relevance * 0.50 + heat * 0.30 + rate * 0.20
```

`pick_short_drama()` 先读取 usage JSON，排除 `used_at >= now - repeat_days` 的 ID；若排除后为空再恢复全部候选。对候选调用 `score_drama()`，按 `(score, hot_degree, offline_timestamp)` 降序和 `drama_id` 升序取第一名。`record_drama_usage()` 只保留最近 30 天记录，并通过临时文件加 `replace()` 原子写入 `{drama_id,drama_name,article_title,used_at}`。

相关度只使用剧名、题材、时代和简介的关键词交集；财经/科技稿为“职场、都市、励志”各加固定小额基础分。热度和分佣用当前候选的 min-max 归一化；总分严格为 `relevance * 0.50 + heat * 0.30 + rate * 0.20`。同分时按热度、有效期和 `drama_id` 稳定排序。

- [ ] **Step 6: 运行 Task 2 测试并提交**

Run: `cd stock-ai && PYTHONPATH=. .venv/bin/python -m pytest tests/unit/test_wechat_mp_short_drama.py -q`

Expected: PASS。

```bash
git add stock-ai/scripts/tools/wechat_mp_short_drama.py stock-ai/tests/unit/test_wechat_mp_short_drama.py
git commit -m "feat: rank and rotate short drama promotions"
```

### Task 3: 短剧组件解析、归因表征和失败关闭

**Files:**
- Modify: `stock-ai/scripts/tools/wechat_mp_short_drama.py`
- Modify: `stock-ai/tests/unit/test_wechat_mp_short_drama.py`

**Interfaces:**
- Consumes: 人工样本草稿 HTML、`ShortDrama` 和归因缓存。
- Produces: `ShortDramaAttribution`、`parse_short_drama_components()`、`parse_short_drama_component()`、`load_attribution_map()`、`has_attribution_for_drama()`、`load_attribution_for_drama()`、`build_short_drama_html()`、`validate_short_drama_component()` 和诊断命令 `--capture-sample`。

- [ ] **Step 1: 写人工样本解析失败测试**

使用完全虚构的票据与应用 ID：

```python
SAMPLE = '''<mp-common-cpsad data-pluginname="mpcps" data-adtype="short-play"
 data-videocarddata="{&quot;dramaName&quot;:&quot;测试短剧&quot;,&quot;categoryName&quot;:&quot;现代/职场&quot;,&quot;videoCoverUrl&quot;:&quot;https://example.test/c.jpg&quot;,&quot;dramaNum&quot;:60}"
 data-dramaid="123" data-srcappid="wx-source" data-playappid="wx-play"
 data-planid="plan-123" data-traceid="trace-old"
 data-defaultpath="plugin-private%3A%2F%2Fplayer%2Fpages%2Fplaylet%3FdramaId%3D123%26wxTicket%3Dticket-test"></mp-common-cpsad>'''


def test_parse_short_drama_component_extracts_attribution() -> None:
    parsed = parse_short_drama_component(SAMPLE)
    assert parsed.drama_id == "123"
    assert parsed.plan_id == "plan-123"
    assert parsed.wx_ticket == "ticket-test"
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd stock-ai && PYTHONPATH=. .venv/bin/python -m pytest tests/unit/test_wechat_mp_short_drama.py::test_parse_short_drama_component_extracts_attribution -q`

Expected: FAIL，提示解析器不存在。

- [ ] **Step 3: 实现安全解析和组件构建**

定义：

```python
@dataclass(frozen=True)
class ShortDramaAttribution:
    drama_id: str
    plan_id: str
    src_appid: str
    play_appid: str
    default_path: str
    wx_ticket: str
    captured_at: str


class _ShortPlayParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.matches: list[dict[str, str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = {key: value or "" for key, value in attrs}
        if tag == "mp-common-cpsad" and values.get("data-adtype") == "short-play":
            self.matches.append(values)


def parse_short_drama_components(html_text: str) -> list[ShortDramaAttribution]:
    parser = _ShortPlayParser()
    parser.feed(html_text)
    return [_attribution_from_attrs(attrs) for attrs in parser.matches]


def parse_short_drama_component(html_text: str) -> ShortDramaAttribution:
    matches = parse_short_drama_components(html_text)
    if not matches:
        raise RuntimeError("未发现 short-play 组件")
    if len(matches) != 1:
        raise RuntimeError(f"short-play 组件数量异常: {len(matches)}")
    return matches[0]


def _attribution_from_attrs(attrs: Mapping[str, str]) -> ShortDramaAttribution:
    default_path = unquote(html.unescape(attrs.get("data-defaultpath", "")))
    ticket = parse_qs(urlparse(default_path).query).get("wxTicket", [""])[0]
    required = {"drama_id": attrs.get("data-dramaid", ""), "plan_id": attrs.get("data-planid", ""), "src_appid": attrs.get("data-srcappid", ""), "play_appid": attrs.get("data-playappid", ""), "default_path": default_path, "wx_ticket": ticket}
    missing = [key for key, value in required.items() if not value]
    if missing:
        raise RuntimeError(f"短剧归因字段缺失: {','.join(missing)}")
    return ShortDramaAttribution(**required, captured_at=datetime.now(TZ).isoformat(timespec="seconds"))
```

`build_short_drama_html()` 使用 `html.escape(value, quote=True)` 生成 `data-videocarddata`，对 default path 使用 `quote(value, safe="")`，并用传入 trace ID 或 `uuid.uuid4()` 生成新 `data-traceid`。`validate_short_drama_component()` 再次解析结果，并逐项比较 `drama_id`、`plan_id`、`src_appid`、`play_appid`，同时拒绝空 `wxTicket`。

解析必须让 `HTMLParser` 处理属性实体，并对取出的属性值再做 `html.unescape()` 和 URL 解码；不得先解码整段 HTML，以免 `data-videocarddata` 内层引号破坏标签结构。构建必须重新生成 UUID trace ID，并断言 attribution 的 `drama_id`、`plan_id`、来源和播放应用都与候选一致。任何不一致抛出 `RuntimeError("短剧归因与候选不匹配")`，不得复用别剧票据。

归因读取接口固定为：

```python
ATTRIBUTION_PATH = Path("data/wechat_mp_short_drama_attribution.json")


def load_attribution_map(path: Path = ATTRIBUTION_PATH) -> dict[str, ShortDramaAttribution]:
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return {str(drama_id): ShortDramaAttribution(**item) for drama_id, item in payload.items()}


def has_attribution_for_drama(drama: ShortDrama, path: Path = ATTRIBUTION_PATH) -> bool:
    item = load_attribution_map(path).get(drama.drama_id)
    return item is not None and item.plan_id == drama.plan_id and item.src_appid == drama.src_appid and item.play_appid == drama.play_appid and bool(item.wx_ticket)


def load_attribution_for_drama(drama: ShortDrama, path: Path = ATTRIBUTION_PATH) -> ShortDramaAttribution:
    item = load_attribution_map(path).get(drama.drama_id)
    if item is None:
        raise RuntimeError(f"缺少短剧归因: {drama.drama_id}")
    if not has_attribution_for_drama(drama, path):
        raise RuntimeError("短剧归因与候选不匹配")
    return item
```

`build_short_drama_html()` 的实现顺序固定为：先验证 `drama` 与 attribution 的四个身份字段，再生成 `data-videocarddata` JSON 和新 trace ID，最后编码 `default_path` 并返回唯一一个 `mp-common-cpsad` 标签。`validate_short_drama_component()` 调用单组件解析器并复核同样四个字段和非空票据。

- [ ] **Step 4: 实现样本草稿提取命令**

新增诊断入口：

```bash
cd stock-ai
PYTHONPATH=. .venv/bin/python -m scripts.tools.wechat_mp_short_drama \
  --capture-sample-title "短剧组件测试-勿发"
```

命令通过 `draft_batchget(no_content=False)` 精确匹配标题，只允许一个匹配项，调用 `parse_short_drama_components()` 解析该草稿中的全部 `short-play` 组件，并以 `drama_id` 为键把 attribution 原子写入 `data/wechat_mp_short_drama_attribution.json`。终端只显示剧名、`drama_id`、计划 ID、是否含票据和捕获时间；不得打印票据值或完整 HTML。

- [ ] **Step 5: 增加归因表征测试草稿门禁**

实现 `--probe-component --drama-id <id>`：

1. 只从已捕获且 `drama_id` 精确匹配的 attribution 构建组件；
2. 创建标题为 `短剧组件探针-勿发-<时间>` 的最小草稿；
3. 回读同一 `media_id`；
4. 调用 `validate_short_drama_component()`；
5. 输出 media_id，要求用户在后台预览并确认跳转和归因；
6. 未获得用户确认前保持 `WECHAT_MP_SHORT_DRAMA=0`。

如果要为列表中的其他候选建立可归因组件，而现有 attribution 不匹配，命令必须报：`缺少该短剧的归因建卡数据，请抓取选择短剧时的建卡请求`。此时暂停全量启用，并让用户在开发者工具中提供“点击插入短剧”动作对应的建卡请求 URL 与 JSON payload；不得请求 Cookie 或 Authorization，也不得调用读者点击跟踪 URL 来伪造票据或制造点击数据。本计划不假定该在线接口已经存在，也不把尚未捕获归因的 2145 条列表数据视为可直接投放。后续拿到真实建卡请求后，另增 `resolve_attribution_for_drama()`，并先为请求体、响应解析和票据缺失补失败测试。

- [ ] **Step 6: 运行 Task 3 测试并提交**

Run: `cd stock-ai && PYTHONPATH=. .venv/bin/python -m pytest tests/unit/test_wechat_mp_short_drama.py -q`

Expected: PASS。

```bash
git add stock-ai/scripts/tools/wechat_mp_short_drama.py stock-ai/tests/unit/test_wechat_mp_short_drama.py
git commit -m "feat: validate attributed short drama components"
```

### Task 4: 长文主流水线替换普通返佣商品

**Files:**
- Modify: `stock-ai/scripts/tools/wechat_mp_content.py`
- Modify: `stock-ai/scripts/tools/wechat_mp_product.py`
- Modify: `stock-ai/scripts/tools/wechat_mp_seo.py`
- Modify: `stock-ai/tests/unit/test_wechat_mp_product.py`
- Modify: `stock-ai/tests/unit/test_wechat_mp_disclaimer_render.py`
- Modify: `stock-ai/tests/unit/test_wechat_mp_short_drama.py`

**Interfaces:**
- Consumes: 已完成正文 HTML、稿型和已验证 attribution。
- Produces: `attach_short_drama(article, kind=kind)`，以及只允许 `commerce` 的 `attach_footer_product()`。

- [ ] **Step 1: 写所有长文禁止普通商品的失败测试**

```python
@pytest.mark.parametrize("kind", ["hotspot", "tv_review", "sector", "market", "news", "top5", "dragons", "workspace", "temp"])
def test_longform_never_attaches_footer_product(kind, monkeypatch):
    monkeypatch.setenv("WECHAT_MP_FOOTER_PRODUCT", "1")
    monkeypatch.setenv("WECHAT_MP_FOOTER_PRODUCT_ID", "999")
    out = attach_footer_product({"content": "<p>正文</p>"}, kind=kind)
    assert "mp-common-cpsad" not in out["content"]
    assert "product_info" not in out


def test_commerce_can_still_attach_footer_product(monkeypatch):
    monkeypatch.setenv("WECHAT_MP_FOOTER_PRODUCT", "1")
    monkeypatch.setenv("WECHAT_MP_FOOTER_PRODUCT_ID", "999")
    out = attach_footer_product({"content": "<p>正文</p>"}, kind="commerce")
    assert 'data-adtype="short-play"' not in out["content"]
    assert "mp-common-cpsad" in out["content"]
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd stock-ai && PYTHONPATH=. .venv/bin/python -m pytest tests/unit/test_wechat_mp_product.py -q`

Expected: 至少 `market` 普通商品测试 FAIL。

- [ ] **Step 3: 限制普通商品为 commerce**

在 `attach_footer_product()` 开头把允许范围收敛为：

```python
if k != "commerce" and k not in PICK_KEYWORDS_BY_VERTICAL:
    return article
```

独立 `wechat_mp_commerce_draft.py` 继续传入垂直类型；长文不再调用自动商品选品和 `getcardinfo`。

- [ ] **Step 4: 写短剧位置和唯一性失败测试**

```python
def test_attach_short_drama_once_at_body_ratio(monkeypatch):
    article = {"title": "公司报销观察", "digest": "职场", "body_text": "正文", "content": SIX_PARAGRAPH_HTML}
    monkeypatch.setenv("WECHAT_MP_SHORT_DRAMA", "1")
    monkeypatch.setattr("scripts.tools.wechat_mp_short_drama.load_or_refresh_drama_pool", lambda **kwargs: [DRAMA])
    monkeypatch.setattr("scripts.tools.wechat_mp_short_drama.pick_short_drama", lambda *args, **kwargs: DRAMA)
    monkeypatch.setattr("scripts.tools.wechat_mp_short_drama.load_attribution_for_drama", lambda *args, **kwargs: ATTRIBUTION)
    out = attach_short_drama(article, kind="workspace")
    assert out["content"].count('data-adtype="short-play"') == 1
    assert out["content"].index('data-adtype="short-play"') < out["content"].index("#fff5f5")
    assert "footer_product_info" not in str(out)


def test_draft_payload_strips_local_short_drama_metadata():
    article = {"content": "<p>正文</p>", "body_text": "正文", "short_drama": {"drama_id": "123"}}
    payload = draft_article_payload(article)
    assert payload["content"] == "<p>正文</p>"
    assert "body_text" not in payload
    assert "short_drama" not in payload
```

- [ ] **Step 5: 实现最终 HTML 后附加短剧**

在短剧模块中实现：

```python
LONGFORM_KINDS = frozenset({"hotspot", "tv_review", "tv", "film", "movie", "sector", "market", "news", "top5", "dragons", "workspace", "temp"})
PLAIN_CPS_RE = re.compile(r'<mp-common-cpsad(?![^>]*data-adtype=["\']short-play["\'])', re.I)


def attach_short_drama(article: Mapping[str, Any], *, kind: str | None, now: datetime | None = None) -> dict[str, Any]:
    normalized = (kind or "").strip().lower()
    out = dict(article)
    if normalized not in LONGFORM_KINDS or not short_drama_enabled():
        return out
    rows = dedupe_dramas(eligible_dramas(load_or_refresh_drama_pool(now=now), now=now or datetime.now(TZ), min_valid_days=drama_min_valid_days()))
    attributed_rows = [row for row in rows if has_attribution_for_drama(row)]
    if not attributed_rows:
        raise RuntimeError("没有同时满足内容和归因门禁的短剧")
    drama = pick_short_drama(out, attributed_rows, kind=normalized, now=now)
    attribution = load_attribution_for_drama(drama)
    component = build_short_drama_html(drama, attribution)
    content = str(out.get("content") or "")
    if 'data-adtype="short-play"' not in content:
        position = cps_injection_index(content)
        out["content"] = content[:position] + component + content[position:]
    out["short_drama"] = {"drama_id": drama.drama_id, "drama_name": drama.drama_name, "theme": drama.theme, "media_count": drama.media_count, "rate_bp": drama.rate_bp, "plan_id": drama.plan_id}
    assert_longform_promotion_safe(out, kind=normalized)
    return out


def assert_longform_promotion_safe(article: Mapping[str, Any], *, kind: str | None) -> None:
    normalized = (kind or "").strip().lower()
    if normalized not in LONGFORM_KINDS:
        return
    content = str(article.get("content") or "")
    if PLAIN_CPS_RE.search(content) or ((article.get("product_info") or {}).get("footer_product_info")):
        raise RuntimeError("长文仍含普通返佣商品")
    count = content.count('data-adtype="short-play"')
    if short_drama_enabled() and count != 1:
        raise RuntimeError(f"长文短剧组件数量异常: {count}")
```

复用现有 `cps_injection_index()` 的区块边界算法，但短剧模块自己生成标签。`_article_shell()` 必须先完成 `attach_stock_ai_cta()` 和由此触发的 HTML 重建，再调用 `attach_short_drama()`；删除长文路径中提前调用的 `attach_footer_product()`。`sync_article_content_from_body()` 同样在重建结束后调用短剧附加器。

`draft_article_payload()` 必须删除仅供本地日志和回读使用的 `short_drama` 字段，避免把未知字段发送给微信草稿 API；新增测试断言 payload 仍保留 `content`，但不含 `body_text` 和 `short_drama`。

- [ ] **Step 6: 运行 Task 4 测试并提交**

Run:

```bash
cd stock-ai
PYTHONPATH=. .venv/bin/python -m pytest \
  tests/unit/test_wechat_mp_short_drama.py \
  tests/unit/test_wechat_mp_product.py \
  tests/unit/test_wechat_mp_disclaimer_render.py -q
```

Expected: PASS。

```bash
git add stock-ai/scripts/tools/wechat_mp_content.py stock-ai/scripts/tools/wechat_mp_product.py stock-ai/scripts/tools/wechat_mp_seo.py stock-ai/tests/unit/test_wechat_mp_short_drama.py stock-ai/tests/unit/test_wechat_mp_product.py stock-ai/tests/unit/test_wechat_mp_disclaimer_render.py
git commit -m "feat: replace longform product cards with short dramas"
```

### Task 5: 推稿前门禁、dry-run 摘要和草稿回读

**Files:**
- Modify: `stock-ai/scripts/tools/wechat_mp_draft.py`
- Modify: `stock-ai/scripts/tools/wechat_mp_short_drama.py`
- Modify: `stock-ai/tests/unit/test_wechat_mp_short_drama.py`
- Create: `stock-ai/tests/unit/test_wechat_mp_draft_short_drama.py`

**Interfaces:**
- Consumes: 最终 article、`upsert_draft_article()` 返回的 media_id。
- Produces: `promotion_summary()`、`verify_saved_short_drama()` 和写入前/后双门禁。

- [ ] **Step 1: 写写入前门禁失败测试**

```python
def test_preflight_blocks_plain_product_card_in_longform():
    article = {"content": '<mp-common-cpsad data-pid="101_1"></mp-common-cpsad>'}
    with pytest.raises(RuntimeError, match="普通返佣商品"):
        assert_longform_promotion_safe(article, kind="market")


def test_preflight_requires_short_play_when_enabled(monkeypatch):
    monkeypatch.setenv("WECHAT_MP_SHORT_DRAMA", "1")
    with pytest.raises(RuntimeError, match="缺少短剧组件"):
        assert_longform_promotion_safe({"content": "<p>正文</p>"}, kind="hotspot")
```

- [ ] **Step 2: 实现 dry-run 输出和写入前门禁**

`wechat_mp_draft --dry-run` 对长文额外输出：

```text
短剧推广: 报销风波后，整个公司都慌了 · 现代/都市、职场 · 60集 · 分佣60.00%
```

只显示公开业务字段。正式 `upsert_draft_article()` 前调用 `assert_longform_promotion_safe()`；门禁失败不得上传封面或写草稿。

- [ ] **Step 3: 写草稿回读失败测试**

```python
def test_verify_saved_short_drama_rejects_stripped_component(monkeypatch):
    monkeypatch.setattr("scripts.tools.wechat_mp_short_drama.fetch_draft_news_item", lambda **kwargs: ({"content": "<p>正文</p>"}, None))
    with pytest.raises(RuntimeError, match="回读未发现"):
        verify_saved_short_drama(media_id="m1", expected_drama_id="123", kind="market")
```

- [ ] **Step 4: 实现写入后回读**

实现：

```python
def verify_saved_short_drama(*, media_id: str, expected_drama_id: str, kind: str) -> None:
    news, err = fetch_draft_news_item(media_id=media_id)
    if err:
        raise RuntimeError(f"短剧草稿回读失败: {err.get('errmsg') or err}")
    parsed = parse_short_drama_component(str((news or {}).get("content") or ""))
    if parsed.drama_id != expected_drama_id:
        raise RuntimeError(f"短剧草稿回读不一致: expected={expected_drama_id} actual={parsed.drama_id}")
```

正式推稿成功后立即回读；只有回读通过才调用 `record_drama_usage()` 并打印 OK。回读失败时保留草稿供排查，但命令退出非零并明确提示用户不要发表。

- [ ] **Step 5: 运行 Task 5 测试并提交**

Run:

```bash
cd stock-ai
PYTHONPATH=. .venv/bin/python -m pytest \
  tests/unit/test_wechat_mp_short_drama.py \
  tests/unit/test_wechat_mp_draft_short_drama.py -q
```

Expected: PASS。

```bash
git add stock-ai/scripts/tools/wechat_mp_draft.py stock-ai/scripts/tools/wechat_mp_short_drama.py stock-ai/tests/unit/test_wechat_mp_short_drama.py stock-ai/tests/unit/test_wechat_mp_draft_short_drama.py
git commit -m "feat: gate and verify short drama drafts"
```

### Task 6: 运维文档、真实接口验证和受控启用

**Files:**
- Modify: `.cursor/skills/wechat-mp-drafts/operations-sop.md`
- Modify: `.cursor/skills/wechat-mp-drafts/reference.md`
- Modify: `stock-ai/.env.example`

**Interfaces:**
- Consumes: Task 1—5 的 CLI 和门禁。
- Produces: 可重复的短剧池刷新、样本捕获、探针草稿和全量启用 SOP。

- [ ] **Step 1: 更新文档**

在 operations SOP 写入以下顺序：

```bash
cd stock-ai
PYTHONPATH=. .venv/bin/python -m scripts.tools.wechat_mp_short_drama --refresh --limit 40
PYTHONPATH=. .venv/bin/python -m scripts.tools.wechat_mp_short_drama --capture-sample-title "短剧组件测试-勿发"
PYTHONPATH=. .venv/bin/python -m scripts.tools.wechat_mp_short_drama --probe-component --drama-id 660409
```

并写清：后台预览确认前保持 `WECHAT_MP_SHORT_DRAMA=0`；任何归因或回读失败都不得改回 `WECHAT_MP_FOOTER_PRODUCT=1`。

- [ ] **Step 2: 运行完整相关测试**

Run:

```bash
cd stock-ai
PYTHONPATH=. .venv/bin/python -m pytest \
  tests/unit/test_wechat_mp_short_drama.py \
  tests/unit/test_wechat_mp_draft_short_drama.py \
  tests/unit/test_wechat_mp_product.py \
  tests/unit/test_wechat_mp_disclaimer_render.py \
  tests/unit/test_wechat_mp_commerce_draft.py -q
```

Expected: 全部 PASS；独立 commerce 仍能生成普通商品，所有长文只允许 short-play。

- [ ] **Step 3: 运行真实短剧列表验证**

Run:

```bash
cd stock-ai
WECHAT_MP_SHORT_DRAMA=0 PYTHONPATH=. .venv/bin/python -m scripts.tools.wechat_mp_short_drama --refresh --limit 40
```

Expected: `ret=0`，打印总量、有效候选数、去重后数量和前十部摘要；缓存文件不含账号标识和票据。

- [ ] **Step 4: 创建并人工预览归因探针**

使用 Task 3 的 `--probe-component` 创建测试草稿。用户在后台确认：卡片显示正确、点击打开对应短剧、结算归因可识别。任何一项不能确认就保持关闭并停止，不进入下一步。

- [ ] **Step 5: 启用一篇 dry-run 和一篇测试草稿**

在本地 `.env` 设置 `WECHAT_MP_SHORT_DRAMA=1` 和 `WECHAT_MP_DRAMA_KOL_ID`，先运行：

```bash
cd stock-ai
WECHAT_MP_TV_TOPIC=奥德赛 PYTHONPATH=. .venv/bin/python -m scripts.tools.wechat_mp_draft --kind tv_review --dry-run
```

Expected: 正文恰有一个 short-play，无普通商品和 footer product key；输出所选短剧摘要。

再用一个非正式测试槽位写草稿并回读，确认命令退出 0。不得自动发表。

- [ ] **Step 6: 最终验证并提交文档**

Run:

```bash
cd stock-ai
git diff --check
PYTHONPATH=. .venv/bin/python -m pytest tests/unit/test_wechat_mp_short_drama.py tests/unit/test_wechat_mp_draft_short_drama.py tests/unit/test_wechat_mp_product.py tests/unit/test_wechat_mp_disclaimer_render.py tests/unit/test_wechat_mp_commerce_draft.py -q
```

Expected: `git diff --check` 无输出；pytest 全部 PASS。

```bash
git add .cursor/skills/wechat-mp-drafts/operations-sop.md .cursor/skills/wechat-mp-drafts/reference.md stock-ai/.env.example
git commit -m "docs: document short drama promotion operations"
```

## Completion Criteria

- `DramaSelect` 可分页读取并安全缓存，当前列表总量和返回字段可验证。
- 候选过滤、同名去重、50/30/20 排序和七天轮换均有单元测试。
- 每篇长文最多一个 `data-adtype="short-play"` 组件，位置在正文约三分之二处。
- 长文没有普通返佣商品、`data-pid` 商品卡或 footer product key；独立 commerce 行为不变。
- 缺少有效归因票据、候选、配置或缓存时在微信 API 前失败关闭。
- 测试草稿写入后回读仍包含正确短剧组件；后台人工预览确认剧目和归因。
- 所有相关测试通过，敏感账号标识、票据和 token 未进入 Git。
