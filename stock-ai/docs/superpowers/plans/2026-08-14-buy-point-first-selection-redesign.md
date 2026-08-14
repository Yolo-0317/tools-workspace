# Buy-Point-First Selection Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a fail-closed, main-board-only selector that emits zero to three executable 3–5-session trade plans only when market, point-in-time risk, sector, setup, price-plan, and portfolio gates all pass.

**Architecture:** Add a pure `stock_ai.buy_point_selection` domain package for point-in-time gates, three setup detectors, structural plans, ranking, conservative execution simulation, and promotion validation. Keep MySQL and Tushare access in adapters, then let `a-share-short-term-trading` persist schema-v1.3 candidates/plans and perform chip, account, and live-release gating. The existing four lanes remain shadow-only inputs and cannot promote a candidate.

**Tech Stack:** Python 3.12, frozen dataclasses, Pydantic v2, pandas, SQLAlchemy/MySQL 8, Tushare Pro, pytest.

## Global Constraints

- Formal universe is Shanghai/Shenzhen main-board A shares only; exclude ST, suspended, held, and fewer-than-60-session symbols.
- Primary objective is positive net expectancy and controlled drawdown over 3–5 sessions, not next-day limit-up recall.
- Formal output is zero to three candidates; `LIMITED` permits at most one and `FREEZE` permits zero.
- Rule version starts at `buy-point-selection-3.0.0`; strategies are `buy_point_v3_shadow` and `buy_point_v3`.
- Signal-day gain above 5%, three-session gain above 8%, five-session gain above 12%, MA5 distance above 5%, or MA20 distance above 12% forbids a formal plan.
- Entry is conditional for two sessions, gap above 3% or trigger-time gain above 5% cancels entry, and every entered trade exits no later than session five.
- Risk is at most 500 yuan and 4,000 yuan ticket value in `ALLOW`; both halve in `LIMITED`; total exposure remains 40,000 yuan.
- AI, news, legacy lanes, three-up, and limit-up-gene results cannot grant formal eligibility.
- Tests use fictional securities and accounts; personal holdings and decision memory never enter Git.
- Do not install a scheduler or automatic order path; the selector remains manually triggered.

---

### Task 1: Point-in-Time Sector, ST, and Announcement-Risk Data

**Files:**
- Create: `stock-mysql/sql/015_buy_point_reference_history.sql`
- Create: `stock-ai/stock_ai/buy_point_selection/__init__.py`
- Create: `stock-ai/stock_ai/buy_point_selection/reference_data.py`
- Create: `stock-ai/scripts/sync/sync_buy_point_reference_data.py`
- Create: `stock-ai/tests/unit/test_buy_point_reference_data.py`
- Create: `stock-ai/tests/unit/test_buy_point_reference_schema.py`

**Interfaces:**
- Produces: `SectorMembership`, `RiskFlag`, `ReferenceCoverage`, `ReferenceRepository.membership_on(date)`, `ReferenceRepository.risk_flags_on(date)`, and `sync_reference_data(pro, repository, trade_dates)`.
- Consumes later: Tasks 2, 4, 6, and 9 query memberships and risk flags strictly by analysis date.

- [ ] **Step 1: Write failing schema and point-in-time tests**

```python
def test_membership_uses_inclusive_in_date_and_exclusive_out_date() -> None:
    rows = (
        SectorMembership("600001", "801010.SI", "农林牧渔", date(2024, 1, 2), date(2025, 6, 30)),
        SectorMembership("600001", "801120.SI", "食品饮料", date(2025, 7, 1), None),
    )
    assert membership_on(rows, date(2025, 6, 30))["600001"].sector_name == "农林牧渔"
    assert membership_on(rows, date(2025, 7, 1))["600001"].sector_name == "食品饮料"


def test_st_and_official_material_risk_are_point_in_time_vetoes() -> None:
    flags = (
        RiskFlag("600002", "ST", "VETO", date(2025, 8, 1), date(2025, 8, 20), "tushare-stock-st"),
        RiskFlag("600003", "REGULATORY_INVESTIGATION", "VETO", date(2025, 8, 5), None, "tushare-anns-d"),
    )
    assert set(risk_flags_on(flags, date(2025, 8, 6))) == {"600002", "600003"}
    assert "600002" not in risk_flags_on(flags, date(2025, 8, 21))
```

The schema test must assert both tables and the sync-run table exist, all have point-in-time indexes, and no SQL contains `DROP TABLE`.

- [ ] **Step 2: Run the tests and verify RED**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=stock-ai \
stock-ai/.venv/bin/pytest -q -p no:cacheprovider \
  stock-ai/tests/unit/test_buy_point_reference_data.py \
  stock-ai/tests/unit/test_buy_point_reference_schema.py
```

Expected: collection fails because `stock_ai.buy_point_selection.reference_data` and migration `015` do not exist.

- [ ] **Step 3: Add the append-safe reference schema**

Create three idempotent tables:

```sql
CREATE TABLE IF NOT EXISTS buy_point_sector_memberships (
  code CHAR(6) NOT NULL,
  sector_code VARCHAR(24) NOT NULL,
  sector_name VARCHAR(128) NOT NULL,
  valid_from DATE NOT NULL,
  valid_to DATE NULL,
  source VARCHAR(64) NOT NULL,
  captured_at DATETIME(6) NOT NULL,
  PRIMARY KEY (code, sector_code, valid_from),
  KEY idx_sector_validity (sector_code, valid_from, valid_to),
  KEY idx_code_validity (code, valid_from, valid_to)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS buy_point_risk_flags (
  flag_id CHAR(64) NOT NULL,
  code CHAR(6) NOT NULL,
  flag_type VARCHAR(48) NOT NULL,
  severity VARCHAR(16) NOT NULL,
  effective_from DATE NOT NULL,
  effective_to DATE NULL,
  source VARCHAR(64) NOT NULL,
  evidence_ref VARCHAR(1024) NOT NULL,
  captured_at DATETIME(6) NOT NULL,
  PRIMARY KEY (flag_id),
  KEY idx_risk_code_validity (code, effective_from, effective_to),
  KEY idx_risk_severity_validity (severity, effective_from, effective_to)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS buy_point_reference_sync_runs (
  run_id CHAR(36) NOT NULL,
  dataset VARCHAR(32) NOT NULL,
  start_date DATE NOT NULL,
  end_date DATE NOT NULL,
  status VARCHAR(16) NOT NULL,
  row_count INT NOT NULL,
  error_code VARCHAR(64) NULL,
  captured_at DATETIME(6) NOT NULL,
  PRIMARY KEY (run_id),
  KEY idx_dataset_bounds (dataset, start_date, end_date, status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

- [ ] **Step 4: Implement deterministic adapters and sync normalization**

`reference_data.py` must expose exact date semantics and never fall back to current profiles:

```python
@dataclass(frozen=True)
class SectorMembership:
    code: str
    sector_code: str
    sector_name: str
    valid_from: date
    valid_to: date | None


def is_active(start: date, end: date | None, on: date) -> bool:
    return start <= on and (end is None or on <= end)


def classify_announcement_title(title: str) -> tuple[str, str] | None:
    vetoes = {
        "立案调查": "REGULATORY_INVESTIGATION",
        "终止上市": "DELISTING",
        "退市风险警示": "DELISTING_RISK",
        "重大违法": "MAJOR_VIOLATION",
        "债务逾期": "DEBT_DEFAULT",
    }
    for token, flag_type in vetoes.items():
        if token in title:
            return flag_type, "VETO"
    return None


class ReferenceRepository(Protocol):
    def upsert_sector_memberships(self, rows: Sequence[SectorMembership], captured_at: datetime) -> int: ...
    def upsert_risk_flags(self, rows: Sequence[RiskFlag], captured_at: datetime) -> int: ...
    def save_sync_run(self, run: ReferenceSyncRun) -> None: ...
    def membership_on(self, analysis_date: date) -> Mapping[str, SectorMembership]: ...
    def risk_flags_on(self, analysis_date: date) -> Mapping[str, tuple[RiskFlag, ...]]: ...
    def coverage(self, analysis_date: date) -> ReferenceCoverage: ...
```

Use these exact value objects:

```python
@dataclass(frozen=True)
class RiskFlag:
    code: str
    flag_type: str
    severity: Literal["OBSERVE", "VETO"]
    effective_from: date
    effective_to: date | None
    source: str
    evidence_ref: str = ""


@dataclass(frozen=True)
class ReferenceCoverage:
    analysis_date: date
    sector_complete: bool
    st_complete: bool
    announcement_complete: bool

    @property
    def complete(self) -> bool:
        return self.sector_complete and self.st_complete and self.announcement_complete


@dataclass(frozen=True)
class ReferenceSyncRun:
    run_id: str
    dataset: Literal["sector", "st", "announcement"]
    start_date: date
    end_date: date
    status: Literal["COMPLETE", "FAILED"]
    row_count: int
    error_code: str | None
    captured_at: datetime
```

The sync script must obtain all historical SW2021 L1 memberships through `index_classify` plus `index_member_all(..., is_new="N")`, daily historical ST rows through `stock_st(trade_date=...)`, and official announcement titles through `anns_d(ann_date=...)`. Normalize a raw membership `out_date` to the previous confirmed trading day before storing it as inclusive `valid_to`, so adjacent industry records cannot overlap. A dataset failure writes a failed sync run and does not mark coverage complete.

- [ ] **Step 5: Run focused tests and verify GREEN**

Run the Step 2 command. Expected: all reference-data tests pass.

- [ ] **Step 6: Commit Task 1**

```bash
git add stock-mysql/sql/015_buy_point_reference_history.sql \
  stock-ai/stock_ai/buy_point_selection/__init__.py \
  stock-ai/stock_ai/buy_point_selection/reference_data.py \
  stock-ai/scripts/sync/sync_buy_point_reference_data.py \
  stock-ai/tests/unit/test_buy_point_reference_data.py \
  stock-ai/tests/unit/test_buy_point_reference_schema.py
git commit -m "feat(stock-ai): add point-in-time selection references"
```

---

### Task 2: Core Models and Fail-Closed Gates

**Files:**
- Create: `stock-ai/stock_ai/buy_point_selection/models.py`
- Create: `stock-ai/stock_ai/buy_point_selection/gates.py`
- Create: `stock-ai/tests/unit/test_buy_point_gates.py`
- Modify: `stock-ai/stock_ai/buy_point_selection/__init__.py`

**Interfaces:**
- Produces: `BuyPointBar`, `SetupType`, `CandidateTier`, `PlanState`, `SelectionPolicy`, `MarketSnapshot`, `SectorSnapshot`, `GateDecision`, `classify_market`, `base_gate`, `anti_chase_gate`, and `sector_gate`.
- Consumes: Task 1 point-in-time memberships and flags.
- Used by: Tasks 3–9.

- [ ] **Step 1: Write failing tests for exact hard gates**

```python
def test_market_states_follow_frozen_thresholds() -> None:
    assert classify_market(MarketSnapshot(2, 52.0, 0.95, True)).status == "ALLOW"
    assert classify_market(MarketSnapshot(1, 39.0, 0.90, True)).status == "FREEZE"
    assert classify_market(MarketSnapshot(2, 48.0, 0.85, True)).status == "LIMITED"
    assert classify_market(MarketSnapshot(3, 70.0, 1.20, False)).status == "FREEZE"


@pytest.mark.parametrize("three_day,five_day,ma5_dist,ma20_dist", [
    (8.01, 5.0, 2.0, 4.0),
    (3.0, 12.01, 2.0, 4.0),
    (3.0, 8.0, 5.01, 4.0),
    (3.0, 8.0, 2.0, 12.01),
])
def test_anti_chase_rejects_each_overheat_boundary(three_day, five_day, ma5_dist, ma20_dist) -> None:
    decision = anti_chase_gate(4.0, three_day, five_day, ma5_dist, ma20_dist)
    assert not decision.passed


def test_sector_requires_point_in_time_breadth_and_turnover() -> None:
    good = SectorSnapshot("801010.SI", "农林牧渔", 0.72, 6, 2, 0.55, 0.85, True)
    assert sector_gate(good).passed
    assert not sector_gate(replace(good, membership_complete=False)).passed
```

- [ ] **Step 2: Run the focused test and verify RED**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=stock-ai \
stock-ai/.venv/bin/pytest -q -p no:cacheprovider stock-ai/tests/unit/test_buy_point_gates.py
```

Expected: import failure for the new models and gates.

- [ ] **Step 3: Implement immutable models and frozen policy values**

```python
class SetupType(str, Enum):
    PRE_BREAKOUT = "PRE_BREAKOUT"
    TREND_PULLBACK = "TREND_PULLBACK"
    FIRST_LAUNCH_PULLBACK = "FIRST_LAUNCH_PULLBACK"


class CandidateTier(str, Enum):
    FORMAL = "FORMAL"
    OBSERVE = "OBSERVE"
    SHADOW = "SHADOW"


class PlanState(str, Enum):
    PREPARED = "PREPARED"
    TRIGGERED = "TRIGGERED"
    EXPIRED = "EXPIRED"
    INVALIDATED = "INVALIDATED"


@dataclass(frozen=True)
class BuyPointBar:
    trade_date: date
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    pct_chg: Decimal
    amount_qian: Decimal


@dataclass(frozen=True)
class MarketSnapshot:
    indexes_above_ma20: int
    breadth_pct: float
    amount_ratio: float
    complete: bool


@dataclass(frozen=True)
class SectorSnapshot:
    sector_code: str
    sector_name: str
    return_percentile: float
    liquid_member_count: int
    strengthening_member_count: int
    breadth_ratio: float
    amount_ratio: float
    membership_complete: bool


@dataclass(frozen=True)
class GateDecision:
    passed: bool
    status: str
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class SelectionPolicy:
    rule_version: str = "buy-point-selection-3.0.0"
    min_history: int = 60
    min_average_amount5_qian: float = 100_000.0
    max_signal_gain_pct: float = 5.0
    max_return3_pct: float = 8.0
    max_return5_pct: float = 12.0
    max_ma5_distance_pct: float = 5.0
    max_ma20_distance_pct: float = 12.0
    max_gap_pct: float = 3.0
    max_trigger_gain_pct: float = 5.0
    max_formal_candidates: int = 3
    limited_candidates: int = 1
```

`base_gate` must reject non-main-board codes, holdings, active risk flags, short history, non-positive recent amounts, and five-day average amount below `100_000` Tushare thousand-yuan units.

- [ ] **Step 4: Implement exact market, anti-chase, and sector gates**

```python
def classify_market(value: MarketSnapshot) -> GateDecision:
    if not value.complete:
        return GateDecision(False, "FREEZE", ("MARKET_DATA_INCOMPLETE",))
    if value.indexes_above_ma20 <= 1 and value.breadth_pct < 40:
        return GateDecision(False, "FREEZE", ("INDEX_AND_BREADTH_WEAK",))
    if value.amount_ratio < 0.75 and value.breadth_pct < 45:
        return GateDecision(False, "FREEZE", ("AMOUNT_AND_BREADTH_WEAK",))
    if value.indexes_above_ma20 >= 2 and value.breadth_pct >= 50 and value.amount_ratio >= 0.90:
        return GateDecision(True, "ALLOW", ())
    return GateDecision(True, "LIMITED", ("MARKET_LIMITED",))
```

`sector_gate` must require at least five liquid members, return percentile at least `0.70`, two strengthening members, breadth at least `0.50`, amount ratio at least `0.80`, and complete point-in-time membership.

- [ ] **Step 5: Run the test and verify GREEN**

Run the Step 2 command. Expected: all gate tests pass.

- [ ] **Step 6: Commit Task 2**

```bash
git add stock-ai/stock_ai/buy_point_selection/models.py \
  stock-ai/stock_ai/buy_point_selection/gates.py \
  stock-ai/stock_ai/buy_point_selection/__init__.py \
  stock-ai/tests/unit/test_buy_point_gates.py
git commit -m "feat(stock-ai): add buy-point hard gates"
```

---

### Task 3: Three Buy-Point Setup Detectors

**Files:**
- Create: `stock-ai/stock_ai/buy_point_selection/patterns.py`
- Create: `stock-ai/tests/unit/test_buy_point_patterns.py`
- Modify: `stock-ai/stock_ai/buy_point_selection/models.py`

**Interfaces:**
- Produces: `DetectedSetup` and `detect_setups(code, bars, policy) -> tuple[DetectedSetup, ...]`.
- `DetectedSetup` contains `setup_type`, `structure_start`, `structure_high`, `structure_low`, `quality`, `reasons`, and calculated metrics.
- Used by: Task 4 service and Task 5 backtest.

```python
@dataclass(frozen=True)
class DetectedSetup:
    code: str
    setup_type: SetupType
    analysis_date: date
    structure_start: date
    structure_high: Decimal
    structure_low: Decimal
    quality: Decimal
    reasons: tuple[str, ...]
    metrics: Mapping[str, Decimal]
```

- [ ] **Step 1: Write one failing behavior test per setup and explicit rejection tests**

```python
def test_pre_breakout_is_near_contracting_platform_top() -> None:
    setup = only_setup(detect_setups("600001", platform_fixture(), POLICY))
    assert setup.setup_type is SetupType.PRE_BREAKOUT
    assert setup.metrics["distance_to_platform_top"] <= 0.03


def test_trend_pullback_requires_two_to_four_contracting_sessions() -> None:
    setup = only_setup(detect_setups("600002", trend_pullback_fixture(), POLICY))
    assert setup.setup_type is SetupType.TREND_PULLBACK
    assert 2 <= setup.metrics["pullback_sessions"] <= 4


def test_first_launch_requires_launch_then_one_or_two_quiet_bars() -> None:
    setup = only_setup(detect_setups("600003", first_launch_fixture(), POLICY))
    assert setup.setup_type is SetupType.FIRST_LAUNCH_PULLBACK
    assert setup.metrics["launch_gain_pct"] == pytest.approx(0.04)


def test_plain_three_up_has_no_setup() -> None:
    assert detect_setups("600004", three_up_fixture(), POLICY) == ()
```

- [ ] **Step 2: Run and verify RED**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=stock-ai \
stock-ai/.venv/bin/pytest -q -p no:cacheprovider stock-ai/tests/unit/test_buy_point_patterns.py
```

Expected: `patterns.py` is missing.

- [ ] **Step 3: Implement the platform detector**

Use the latest 30 bars, require total width at most 12%, latest-10-bar width no more than 80% of the prior-10-bar width, latest close 0%–3% below the prior platform high, non-negative five-session MA20 slope, and recent-five/prior-five amount ratio at most 0.80.

```python
def detect_pre_breakout(code: str, bars: tuple[BuyPointBar, ...], policy: SelectionPolicy) -> DetectedSetup | None:
    window = bars[-30:]
    platform_high = max(bar.high for bar in window[:-1])
    platform_low = min(bar.low for bar in window)
    width = platform_high / platform_low - 1.0
    distance = (platform_high - window[-1].close) / platform_high
    if width > 0.12 or not 0.0 <= distance <= 0.03:
        return None
    if range_width(window[-10:]) > 0.80 * range_width(window[-20:-10]):
        return None
    if amount_ratio(window[-5:], window[-10:-5]) > 0.80 or ma20_slope5(bars) < 0:
        return None
    return build_setup(code, SetupType.PRE_BREAKOUT, window[0].trade_date, platform_high, platform_low, bars)
```

- [ ] **Step 4: Implement trend-pullback and first-launch detectors**

Trend pullback must have 5%–18% ten-session pre-pullback return, two to four non-accelerating pullback bars, 2%–8% drawdown, pullback amount ratio at most 0.80, and close at or above MA10 and MA20.

First launch must find a launch bar one or two sessions before the signal date with 2%–5% gain, amount ratio 1.30–2.20, close-location at least 0.70, preceding-five return at most 5%, no preceding three-up sequence, and one or two subsequent bars with absolute gain at most 2% and amount at most 80% of launch amount.

- [ ] **Step 5: Run tests and verify GREEN**

Run the Step 2 command. Expected: all detector tests pass, including the plain-three-up rejection.

- [ ] **Step 6: Commit Task 3**

```bash
git add stock-ai/stock_ai/buy_point_selection/models.py \
  stock-ai/stock_ai/buy_point_selection/patterns.py \
  stock-ai/tests/unit/test_buy_point_patterns.py
git commit -m "feat(stock-ai): detect pre-entry buy-point setups"
```

---

### Task 4: Structural Plans, Stable Setup Identity, Ranking, and Three-Tier Output

**Files:**
- Create: `stock-ai/stock_ai/buy_point_selection/planning.py`
- Create: `stock-ai/stock_ai/buy_point_selection/service.py`
- Create: `stock-ai/stock_ai/buy_point_selection/formatting.py`
- Create: `stock-ai/tests/unit/test_buy_point_planning.py`
- Create: `stock-ai/tests/unit/test_buy_point_service.py`

**Interfaces:**
- Produces: `build_price_plan`, `structure_id`, `select_buy_points`, `render_buy_point_report`.
- Consumes: Task 2 gates, Task 3 setups, point-in-time sectors/risks, current holdings, and risk budget.
- Produces for Task 8: `BuyPointSelectionResult(qualified, observe, shadow, rejection_counts)`. `qualified` is an internal technical/sector/account prequalification list; it is not user-visible formal output until Task 8 chip and release gates pass.

```python
@dataclass(frozen=True)
class RiskBudget:
    loss_budget: Decimal
    ticket_limit: Decimal
    remaining_exposure: Decimal


@dataclass(frozen=True)
class PricePlan:
    structure_id: str
    code: str
    setup_type: SetupType
    signal_date: date
    signal_close: Decimal
    trigger_price: Decimal
    invalidation_price: Decimal
    target_2r: Decimal
    risk_distance: Decimal
    risk_reward_ratio: Decimal
    maximum_shares: int
    valid_through_trade_date: date
```

- [ ] **Step 1: Write failing plan-math and deduplication tests**

```python
def test_plan_uses_tick_atr_buffer_two_r_and_risk_sizing() -> None:
    plan = build_price_plan(setup(), bars(), RiskBudget(500, 4000, 40000), "ALLOW", POLICY)
    assert plan.trigger_price == Decimal("10.01")
    assert plan.invalidation_price == Decimal("9.71")
    assert plan.target_2r == Decimal("10.61")
    assert plan.maximum_shares == 300


def test_same_structure_has_same_id_on_next_analysis_day() -> None:
    first = structure_id("600001", setup(), POLICY.rule_version)
    second = structure_id("600001", replace(setup(), analysis_date=date(2026, 8, 15)), POLICY.rule_version)
    assert first == second


def test_freeze_returns_no_formal_candidates_and_never_falls_back_to_shadow() -> None:
    result = select_buy_points(selection_input(market_status="FREEZE", legacy_shadow=(shadow_row(),)))
    assert result.qualified == ()
    assert len(result.shadow) == 1
```

- [ ] **Step 2: Run and verify RED**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=stock-ai \
stock-ai/.venv/bin/pytest -q -p no:cacheprovider \
  stock-ai/tests/unit/test_buy_point_planning.py \
  stock-ai/tests/unit/test_buy_point_service.py
```

Expected: planning and service modules are missing.

- [ ] **Step 3: Implement exact structural plan math**

```python
trigger = ceil_cent(setup.structure_high + Decimal("0.01"))
atr = atr14(bars)
invalidation = floor_cent(setup.structure_low - Decimal("0.2") * atr)
risk = trigger - invalidation
risk_pct = risk / trigger
minimum = max(Decimal("0.015"), Decimal("0.8") * atr / trigger)
if not minimum <= risk_pct <= Decimal("0.05"):
    return PlanDecision(None, ("RISK_DISTANCE_OUT_OF_RANGE",))
target_2r = ceil_cent(trigger + Decimal("2") * risk)
if nearest_resistance_above(trigger, bars[-60:]) < target_2r:
    return PlanDecision(None, ("INSUFFICIENT_TWO_R_SPACE",))
shares = floor_100(min(ticket_limit / trigger, loss_budget / risk, remaining_exposure / trigger))
```

`nearest_resistance_above` returns positive infinity when the prior 60 bars contain no resistance above trigger, so absence of overhead resistance does not reject the plan.

In `LIMITED`, halve `ticket_limit` and `loss_budget`; in `FREEZE`, return no formal plan. Fewer than 100 shares rejects the plan.

- [ ] **Step 4: Implement deterministic ranking and three tiers**

Rank only fully gated plans by `(-quality, -risk_reward_ratio, risk_pct, -sector_percentile, -average_amount5, code)`. Allocate at most three in `ALLOW`, one in `LIMITED`, zero in `FREEZE`, and one per sector. Missing sector, point-in-time risk coverage, or account freshness places the row in `observe` with explicit `missing_fields`; legacy rows always enter `shadow` with zero shares. Chip and release permission are applied in Task 8, after the small `qualified` list exists.

- [ ] **Step 5: Implement stable structure IDs and non-repeating state behavior**

```python
def structure_id(code: str, setup: DetectedSetup, rule_version: str) -> str:
    payload = ":".join((
        code,
        setup.setup_type.value,
        setup.structure_start.isoformat(),
        f"{setup.structure_high:.2f}",
        f"{setup.structure_low:.2f}",
        rule_version,
    ))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:32]
```

Existing `PREPARED`, `TRIGGERED`, `EXPIRED`, or `INVALIDATED` structures are not emitted as new plans. A new structure start or boundary produces a new ID.

- [ ] **Step 6: Implement report separation**

The renderer must produce `正式候选`, `准备中观察`, `影子研究`, and `拒绝统计`. Only formal rows may print `最大股数`; observe and shadow rows must print `无交易资格`.

- [ ] **Step 7: Run tests and verify GREEN**

Run the Step 2 command. Expected: all planning, allocation, deduplication, and formatting tests pass.

- [ ] **Step 8: Commit Task 4**

```bash
git add stock-ai/stock_ai/buy_point_selection/planning.py \
  stock-ai/stock_ai/buy_point_selection/service.py \
  stock-ai/stock_ai/buy_point_selection/formatting.py \
  stock-ai/tests/unit/test_buy_point_planning.py \
  stock-ai/tests/unit/test_buy_point_service.py
git commit -m "feat(stock-ai): build auditable buy-point plans"
```

---

### Task 5: Conservative Two-Session Trigger and Five-Session Execution Simulator

**Files:**
- Create: `stock-ai/stock_ai/buy_point_selection/execution.py`
- Create: `stock-ai/tests/unit/test_buy_point_execution.py`

**Interfaces:**
- Produces: `ExecutionCosts`, `SimulatedTrade`, `simulate_plan`, and `simulate_portfolio`.
- Consumes: Task 4 `PricePlan` plus subsequent daily bars.
- Used by: Task 6 validation.

```python
@dataclass(frozen=True)
class ExecutionCosts:
    commission_rate: Decimal = Decimal("0.001")
    minimum_commission: Decimal = Decimal("5")
    slippage_rate: Decimal = Decimal("0.001")
    sell_tax_rate: Decimal = Decimal("0.001")


@dataclass(frozen=True)
class ExitLeg:
    exit_date: date
    price: Decimal
    quantity: int
    reason: str
    fees: Decimal


@dataclass(frozen=True)
class SimulatedTrade:
    structure_id: str
    code: str
    sector_code: str
    status: str
    entry_date: date | None
    entry_price: Decimal | None
    quantity: int
    exit_legs: tuple[ExitLeg, ...]
    net_pnl: Decimal
    net_return: Decimal | None
```

- [ ] **Step 1: Write failing tests for every conservative ordering rule**

```python
def test_untriggered_first_day_can_trigger_on_second_day() -> None:
    trade = simulate_plan(plan(), two_day_trigger_fixture(), COSTS)
    assert trade.entry_date == date(2026, 8, 12)


def test_gap_above_three_percent_cancels() -> None:
    assert simulate_plan(plan(), gap_fixture(0.031), COSTS).status == "GAP_CANCELLED"


def test_same_bar_stop_and_target_assumes_stop_first() -> None:
    trade = simulate_plan(plan(), same_bar_stop_target_fixture(), COSTS)
    assert trade.exit_reason == "STOP"


def test_two_r_sells_half_and_moves_remainder_to_entry() -> None:
    trade = simulate_plan(plan(quantity=400), two_r_then_breakeven_fixture(), COSTS)
    assert trade.exit_legs[0].quantity == 200
    assert trade.exit_legs[0].reason == "TARGET_2R"
    assert trade.exit_legs[1].reason == "BREAKEVEN_STOP"
```

- [ ] **Step 2: Run and verify RED**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=stock-ai \
stock-ai/.venv/bin/pytest -q -p no:cacheprovider stock-ai/tests/unit/test_buy_point_execution.py
```

Expected: execution module is missing.

- [ ] **Step 3: Implement entry and cancellation ordering**

For each of the first two sessions after the signal: reject a locked one-price limit-up bar; cancel if open gap exceeds 3%; enter at open plus slippage when open is at or above trigger and trigger-time gain is at most 5%; otherwise enter at trigger plus slippage when high reaches trigger and trigger/pre-close gain is at most 5%. After two sessions without entry, return `EXPIRED`.

- [ ] **Step 4: Implement exits, fees, and portfolio constraints**

Use 0.10% slippage and 0.10% commission on both sides, 5-yuan minimum commission per side, and 0.10% sell tax. On ambiguous daily bars, process stop before target. At 2R, sell half rounded down to 100 shares when quantity is at least 200; for 100 shares, exit all. Protect the remainder at entry and close any remainder at session-five close. Portfolio simulation must enforce three open positions, 40,000-yuan exposure, and one open position per sector.

- [ ] **Step 5: Run and verify GREEN**

Run the Step 2 command. Expected: all execution, cost, partial-exit, and ambiguity tests pass.

- [ ] **Step 6: Commit Task 5**

```bash
git add stock-ai/stock_ai/buy_point_selection/execution.py \
  stock-ai/tests/unit/test_buy_point_execution.py
git commit -m "feat(stock-ai): simulate conservative buy-point execution"
```

---

### Task 6: Chronological Backtest, Concentration Metrics, and Fail-Closed Promotion

**Files:**
- Create: `stock-ai/stock_ai/buy_point_selection/validation.py`
- Create: `stock-ai/scripts/analysis/backtest_buy_point_selection.py`
- Create: `stock-ai/tests/unit/test_buy_point_validation.py`
- Create: `stock-ai/tests/unit/test_backtest_buy_point_selection_cli.py`
- Create at explicit research time only: `stock-ai/config/buy_point_selection_validation.json`

**Interfaces:**
- Produces: `chronological_split`, `compute_metrics`, `evaluate_promotion`, `write_artifact`, and `load_historical_release`.
- Artifact schema: `buy-point-selection-validation-v1` with per-setup, rolling-window, aggregate, concentration, costs, point-in-time coverage, and immutable split bounds.
- Used by: Tasks 8–9 release gating.

```python
@dataclass(frozen=True)
class SetupPromotionDecision:
    setup_type: SetupType
    promoted: bool
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class PromotionDecision:
    promoted: bool
    reasons: tuple[str, ...]
    setup_decisions: Mapping[str, SetupPromotionDecision]


@dataclass(frozen=True)
class HistoricalRelease:
    live_eligible: bool
    rule_version: str
    policy_hash: str
    reasons: tuple[str, ...]
```

- [ ] **Step 1: Write failing split and promotion tests**

```python
def test_split_requires_252_126_126_sessions() -> None:
    with pytest.raises(ValidationError, match="630"):
        chronological_split(trading_dates(629))
    split = chronological_split(trading_dates(630))
    assert len(split.train) >= 252
    assert len(split.validation) >= 126
    assert len(split.test) >= 126


def test_negative_single_setup_blocks_only_that_setup() -> None:
    decision = evaluate_promotion(metrics_with(first_launch_expectancy=-0.002))
    assert not decision.setup_decisions["FIRST_LAUNCH_PULLBACK"].promoted
    assert "NEGATIVE_EXPECTANCY" in decision.setup_decisions["FIRST_LAUNCH_PULLBACK"].reasons


def test_profit_concentration_blocks_promotion() -> None:
    decision = evaluate_promotion(metrics_with(top5_profit_share=0.36))
    assert not decision.promoted
    assert "TOP5_PROFIT_CONCENTRATION" in decision.reasons
```

- [ ] **Step 2: Run and verify RED**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=stock-ai \
stock-ai/.venv/bin/pytest -q -p no:cacheprovider \
  stock-ai/tests/unit/test_buy_point_validation.py \
  stock-ai/tests/unit/test_backtest_buy_point_selection_cli.py
```

Expected: validation and CLI modules are missing.

- [ ] **Step 3: Implement chronological research without test-set tuning**

Split ordered unique dates 60%/20%/20%, enforce segment minima 252/126/126, allow parameter selection only from train plus validation, then execute the frozen profile once on test. Compute 63-session rolling windows without randomization. The CLI must require `--freeze-profile` before `--run-test`, store a hash of policy and split bounds, and reject a second test run with a different hash unless the rule version changes.

- [ ] **Step 4: Implement all promotion gates**

Require at least 100 triggered trades overall and 30 per promoted setup, positive net expectancy, at least 60% positive rolling windows, non-negative frozen-test expectancy, average-profit/average-loss at least 1.5, Profit Factor at least 1.3, maximum drawdown at most 8%, top-five winner profit share at most 35%, single-sector trade share at most 35%, single-sector profit share at most 40%, and complete point-in-time coverage for any claimed formal result.

- [ ] **Step 5: Make the CLI emit technical-only and fully-gated metrics separately**

When historical sector/ST/announcement coverage is incomplete, the artifact must set `promoted=false`, include `POINT_IN_TIME_COVERAGE_INCOMPLETE`, and still report technical-core metrics under a separate non-promotable section. No current industry profile may be injected into historical dates.

- [ ] **Step 6: Run tests and verify GREEN**

Run the Step 2 command. Expected: all validation and CLI contract tests pass.

- [ ] **Step 7: Commit Task 6 without generating a passing artifact**

```bash
git add stock-ai/stock_ai/buy_point_selection/validation.py \
  stock-ai/scripts/analysis/backtest_buy_point_selection.py \
  stock-ai/tests/unit/test_buy_point_validation.py \
  stock-ai/tests/unit/test_backtest_buy_point_selection_cli.py
git commit -m "feat(stock-ai): validate buy-point strategy chronologically"
```

Do not add `stock-ai/config/buy_point_selection_validation.json` until the real frozen run has completed and its content has been inspected.

---

### Task 7: Schema-v1.3 Candidate, Plan-State, and Forward-Run Persistence

**Files:**
- Create: `a-share-short-term-trading/sql/006_buy_point_selection_v13.sql`
- Modify: `a-share-short-term-trading/short_term_trading/contracts/market.py:63-96`
- Modify: `a-share-short-term-trading/short_term_trading/contracts/decisions.py:64-114`
- Modify: `a-share-short-term-trading/short_term_trading/contracts/__init__.py:1-45`
- Modify: `a-share-short-term-trading/short_term_trading/repositories/planning.py:57-174`
- Create: `a-share-short-term-trading/tests/test_buy_point_contracts.py`
- Create: `a-share-short-term-trading/tests/test_buy_point_repositories.py`
- Modify: `a-share-short-term-trading/tests/test_migration_files.py`

**Interfaces:**
- Produces: `CandidateV3`, `TradePlanV3`, `PlanEventV1`, `ForwardSelectionRunV1`, `PlanningRepository.save_buy_point_bundle`, `append_plan_event`, and `forward_gate_summary`.
- Consumes: Task 4 result and plan-state IDs.
- Used by: Tasks 8–9.

`PlanEventV1` contains `event_id`, `plan_id`, `structure_id`, `previous_state`, `new_state`, `reason_code`, `evidence_refs`, `observed_at`, and `event_fingerprint`. `ForwardSelectionRunV1` contains `run_id`, `analysis_date`, `rule_version`, formal/observe/shadow/resolved/duplicate counts, `integrity_violations`, and `release_mode`. Both IDs and fingerprints are deterministic for a repeated analysis-date run.

- [ ] **Step 1: Write failing contract, migration, and transaction tests**

```python
def test_shadow_candidate_cannot_be_executable() -> None:
    with pytest.raises(ValueError, match="shadow"):
        CandidateV3(**candidate_payload(tier="SHADOW", executable_status="EXECUTABLE"))


def test_prepared_plan_requires_two_r_and_structure_id() -> None:
    plan = TradePlanV3(**plan_payload())
    assert plan.target_2r == plan.trigger_price + 2 * plan.risk_distance
    assert len(plan.structure_id) == 32


def test_bundle_failure_rolls_back_candidate_plan_and_event(engine) -> None:
    repository = PlanningRepository(engine)
    with pytest.raises(RuntimeError):
        repository.save_buy_point_bundle(bundle_with_forced_event_failure())
    assert repository.get_candidate_v3(CANDIDATE_ID) is None
```

- [ ] **Step 2: Run and verify RED**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=a-share-short-term-trading:stock-ai \
stock-ai/.venv/bin/pytest -q -p no:cacheprovider \
  a-share-short-term-trading/tests/test_buy_point_contracts.py \
  a-share-short-term-trading/tests/test_buy_point_repositories.py \
  a-share-short-term-trading/tests/test_migration_files.py
```

Expected: V3 contracts and migration are absent.

- [ ] **Step 3: Add schema-v1.3 fields and append-only event tables**

Migration `006` adds `structure_id`, `selection_tier`, `plan_state`, `missing_fields_json`, `pattern_quality`, `sector_metrics_json`, `target_2r`, `signal_close`, and `valid_through_trade_date`. It creates `stt_buy_point_plan_events` with a unique event fingerprint and `stt_buy_point_forward_runs` with unique `(analysis_date, rule_version)`. It must not drop or rewrite V1/V2 rows.

- [ ] **Step 4: Add strict V3 Pydantic validation**

`CandidateV3.candidate_type` accepts the three Task 3 types. `SHADOW` and `OBSERVE` cannot be executable. `TradePlanV3` enforces `invalidation < trigger < target_2r`, `target_2r == trigger + 2*risk_distance`, state in `PREPARED/TRIGGERED/EXPIRED/INVALIDATED`, zero or unknown shares for non-formal rows, and a two-session validity date.

- [ ] **Step 5: Persist candidate, plan, initial event, and forward run in one transaction**

`save_buy_point_bundle` must use one `write_connection` block and execute all inserts before returning. Duplicate fingerprints are idempotent. State changes append an event before updating the current plan projection.

- [ ] **Step 6: Run tests and verify GREEN**

Run the Step 2 command. Expected: contracts, migrations, idempotency, and rollback tests pass.

- [ ] **Step 7: Commit Task 7**

```bash
git add a-share-short-term-trading/sql/006_buy_point_selection_v13.sql \
  a-share-short-term-trading/short_term_trading/contracts/market.py \
  a-share-short-term-trading/short_term_trading/contracts/decisions.py \
  a-share-short-term-trading/short_term_trading/contracts/__init__.py \
  a-share-short-term-trading/short_term_trading/repositories/planning.py \
  a-share-short-term-trading/tests/test_buy_point_contracts.py \
  a-share-short-term-trading/tests/test_buy_point_repositories.py \
  a-share-short-term-trading/tests/test_migration_files.py
git commit -m "feat(short-term): persist buy-point plans and states"
```

---

### Task 8: Chip, Account, Release, and Three-Tier Materialization

**Files:**
- Create: `stock-mysql/sql/016_buy_point_advisor_link.sql`
- Create: `a-share-short-term-trading/short_term_trading/buy_point_selection_service.py`
- Create: `a-share-short-term-trading/tests/test_buy_point_selection_service.py`
- Modify: `a-share-short-term-trading/short_term_trading/repositories/planning.py:174-230`
- Modify: `stock-ai/stock_ai/advisor_memory/repository.py:123-181`
- Modify: `stock-ai/stock_ai/advisor_memory/position_sync.py:128-185`
- Modify: `stock-ai/tests/unit/test_advisor_position_sync.py:1-180`
- Modify: `stock-ai/tests/unit/test_buy_point_reference_schema.py`

**Interfaces:**
- Produces: `materialize_buy_point_selection(result, dependencies, request) -> BuyPointRuntimeReport` and `render_buy_point_runtime_report`.
- Produces: `advance_buy_point_plan_states(open_plans, bars_by_code, market_state, risk_flags)` for append-only `TRIGGERED`, `EXPIRED`, and `INVALIDATED` transitions.
- Produces: broker-confirmed `OPENED` linkage from `stt_trade_plans.plan_id` to `advisor_decision_cycles.selection_plan_id`; simulated triggers alone never open an advisor cycle.
- Consumes: Tasks 4, 6, and 7.
- Release is `LIVE` only when historical artifact passes and the DB forward gate has at least 20 distinct analysis dates, 20 resolved plans, and zero integrity violations.

```python
@dataclass(frozen=True)
class BuyPointRuntimeItem:
    code: str
    name: str
    tier: CandidateTier
    setup_type: SetupType
    reason_code: str
    missing_fields: tuple[str, ...]
    plan: TradePlanV3 | None
    maximum_shares: int | None


@dataclass(frozen=True)
class BuyPointRuntimeReport:
    analysis_date: date
    trading_date: date
    rule_version: str
    release_mode: Literal["SHADOW", "LIVE"]
    formal: tuple[BuyPointRuntimeItem, ...]
    observe: tuple[BuyPointRuntimeItem, ...]
    shadow: tuple[BuyPointRuntimeItem, ...]
    rejection_counts: Mapping[str, int]
```

- [ ] **Step 1: Write failing downgrade and no-share-leak tests**

```python
def test_missing_chip_downgrades_formal_to_observe_without_share_count() -> None:
    report = materialize_buy_point_selection(result_with_qualified(), deps(chip=None), request(live=True))
    assert report.formal == ()
    assert report.observe[0].missing_fields == ("CHIP",)
    assert "最大股数" not in render_buy_point_runtime_report(report).split("准备中观察")[1]


def test_unpromoted_release_keeps_every_new_plan_shadow_only() -> None:
    report = materialize_buy_point_selection(result_with_qualified(), deps(), request(live=False))
    assert report.formal == ()
    assert report.shadow[0].maximum_shares == 0


def test_cost_overhang_before_two_r_downgrades_candidate() -> None:
    report = materialize_buy_point_selection(result_with_qualified(), deps(cost_90_high="10.40"), request(live=True))
    assert report.observe[0].reason_code == "CHIP_RESISTANCE_BEFORE_2R"


def test_previous_prepared_plan_expires_after_second_untriggered_session() -> None:
    events = advance_buy_point_plan_states((prepared_plan(),), {"600001": two_untriggered_bars()}, market(), {})
    assert events[0].new_state == "EXPIRED"


def test_structure_break_before_entry_invalidates_plan() -> None:
    events = advance_buy_point_plan_states((prepared_plan(),), {"600001": breakdown_bar()}, market(), {})
    assert events[0].new_state == "INVALIDATED"


def test_broker_open_links_triggered_plan_to_new_decision_cycle() -> None:
    sync_broker_facts_with_memory(
        (opened_position("600001"),),
        broker_account(),
        connection=connection_with_triggered_plan(PLAN_ID),
    )
    cycle = load_latest_cycle("600001")
    assert cycle["selection_source"] == "buy_point_v3"
    assert cycle["selection_plan_id"] == PLAN_ID
    assert json.loads(cycle["trigger_plan_json"])["trigger_price"] == "10.01"
```

- [ ] **Step 2: Run and verify RED**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=a-share-short-term-trading:stock-ai \
stock-ai/.venv/bin/pytest -q -p no:cacheprovider \
  a-share-short-term-trading/tests/test_buy_point_selection_service.py \
  stock-ai/tests/unit/test_advisor_position_sync.py \
  stock-ai/tests/unit/test_buy_point_reference_schema.py
```

Expected: materializer module is missing.

- [ ] **Step 3: Implement evidence and release downgrades without recalculating setups**

The service validates, but does not recreate, Task 4 prices. A chip snapshot must match the analysis date. If `cost_90_high` lies above trigger and below `target_2r`, downgrade with `CHIP_RESISTANCE_BEFORE_2R`. Stale account, insufficient cash, total exposure, same-sector exposure, market `FREEZE`, historical promotion failure, or forward-gate failure produces zero shares and a non-formal tier. Before materializing new setups, advance every prior `PREPARED` plan from completed bars using the same Task 5 conservative trigger ordering; this condition state is not treated as broker-confirmed execution.

- [ ] **Step 4: Persist the full bundle and forward run atomically**

One-symbol evidence failure may downgrade that symbol, but a database transaction failure fails the whole run and prints no success statement. The forward run stores counts for formal, observe, shadow, expired, invalidated, duplicate-suppressed, and integrity violations.

- [ ] **Step 5: Link only broker-confirmed openings to the advisor ledger**

Migration `016` adds nullable `selection_plan_id CHAR(36)` and an index to `advisor_decision_cycles`; it does not alter existing cycles. Extend `AdvisorLedgerRepository.open_cycle` with optional `selection_source` and `selection_plan_id`. When position sync sees `OPENED` without an active cycle, query the latest V3 plan for the same code whose state is `TRIGGERED`; if found, build five confirmed trading dates from `stock_ai.trading_calendar.next_confirmed_a_share_trade_date`, call `resolve_cycle_dates`, and open a cycle with the frozen trigger plan. If the calendar or plan cannot be confirmed, append the position event with `cycle_id=NULL` and do not invent a cycle.

- [ ] **Step 6: Run tests and verify GREEN**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=a-share-short-term-trading:stock-ai \
stock-ai/.venv/bin/pytest -q -p no:cacheprovider \
  a-share-short-term-trading/tests/test_buy_point_selection_service.py \
  stock-ai/tests/unit/test_advisor_position_sync.py
```

Expected: all materialization, state-advance, report-boundary, and broker-linkage tests pass.

- [ ] **Step 7: Commit Task 8**

```bash
git add stock-mysql/sql/016_buy_point_advisor_link.sql \
  stock-ai/stock_ai/advisor_memory/repository.py \
  stock-ai/stock_ai/advisor_memory/position_sync.py \
  stock-ai/tests/unit/test_advisor_position_sync.py \
  stock-ai/tests/unit/test_buy_point_reference_schema.py \
  a-share-short-term-trading/short_term_trading/buy_point_selection_service.py \
  a-share-short-term-trading/short_term_trading/repositories/planning.py \
  a-share-short-term-trading/tests/test_buy_point_selection_service.py
git commit -m "feat(short-term): gate and materialize buy-point selection"
```

---

### Task 9: Manual Full-Universe CLI and Legacy Shadow Isolation

**Files:**
- Modify: `a-share-short-term-trading/scripts/select_short_term_candidates.py:27-232`
- Modify: `a-share-short-term-trading/tests/test_select_short_term_candidates_cli.py`
- Modify: `stock-ai/scripts/selection/short_term_trade_candidates.py:1-29`
- Create: `stock-ai/tests/unit/test_buy_point_full_universe_runtime.py`

**Interfaces:**
- The existing manual command remains the canonical entry.
- Formal selection scans all eligible main-board bars directly, not the union of four legacy lanes.
- Legacy lanes are loaded only after formal selection and passed as shadow rows.

- [ ] **Step 1: Write failing CLI tests for full-universe scanning and fail-closed output**

```python
def test_runtime_scans_full_main_board_not_only_legacy_rows(fake_runtime) -> None:
    fake_runtime.legacy_rows = []
    fake_runtime.full_universe = {"600001": setup_bars()}
    assert main(["--output", "json"], runtime_factory=lambda _: fake_runtime) == 0
    assert fake_runtime.selected_codes == {"600001"}


def test_missing_reference_coverage_returns_observe_and_exit_zero(fake_runtime, capsys) -> None:
    fake_runtime.reference_coverage = "INCOMPLETE"
    assert main(["--output", "text"], runtime_factory=lambda _: fake_runtime) == 0
    output = capsys.readouterr().out
    assert "正式候选：0" in output
    assert "点时参考数据不完整" in output


def test_legacy_three_up_never_enters_formal_section(fake_runtime) -> None:
    fake_runtime.legacy_rows = [{"代码": "600009", "策略标签": "三连阳", "建议动作": "观察买入"}]
    report = fake_runtime.execute()
    assert all(item.code != "600009" for item in report.formal)
    assert report.shadow[0].code == "600009"
```

- [ ] **Step 2: Run and verify RED**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=a-share-short-term-trading:stock-ai \
stock-ai/.venv/bin/pytest -q -p no:cacheprovider \
  a-share-short-term-trading/tests/test_select_short_term_candidates_cli.py \
  stock-ai/tests/unit/test_buy_point_full_universe_runtime.py
```

Expected: current runtime still builds candidates from merged four-lane rows.

- [ ] **Step 3: Replace candidate sourcing with the complete MySQL universe**

Load one bounded MySQL panel query covering the prior 180 calendar days through the analysis date, group by normalized main-board code, and retain the latest 120 completed bars per code; do not execute one SQL query per symbol. Apply Task 2 base prefilters before running Task 3. Load point-in-time memberships, ST rows, announcement flags, market snapshot, account, holdings, existing plan states, and validation release. Do not fetch or use the deprecated Eastmoney eight-dimension framework.

- [ ] **Step 4: Keep legacy research explicitly shadow-only**

The CLI may run or reuse `combined`, `ma5`, `five_factor`, `bottom_breakout`, `limit_up_gene_watch`, and event-watch outputs, but passes them only to the shadow renderer. Remove all legacy simulated share counts from the visible shadow section.

- [ ] **Step 5: Preserve manual-only behavior and compatibility wrapper**

Keep `stock-ai/scripts/selection/short_term_trade_candidates.py` as a thin delegate. Do not modify cron, launchd, Docker scheduler, or automatic notification scripts. Add `--refresh-reference-data` for an explicit Tushare refresh; without it, the CLI reads cached point-in-time data and fails closed when coverage is missing.

- [ ] **Step 6: Run tests and verify GREEN**

Run the Step 2 command. Expected: full-universe, fail-closed, and shadow-isolation tests pass.

- [ ] **Step 7: Commit Task 9**

```bash
git add a-share-short-term-trading/scripts/select_short_term_candidates.py \
  a-share-short-term-trading/tests/test_select_short_term_candidates_cli.py \
  stock-ai/scripts/selection/short_term_trade_candidates.py \
  stock-ai/tests/unit/test_buy_point_full_universe_runtime.py
git commit -m "feat(stock-ai): switch manual selection to buy-point universe"
```

---

### Task 10: Documentation, Frozen Research Run, and End-to-End Verification

**Files:**
- Modify: `stock-ai/docs/CAPABILITIES.md:338-370`
- Modify: `stock-ai/docs/PROJECT_LAYOUT.md:15-36`
- Modify: `a-share-short-term-trading/README.md:31-92`
- Create only after verified research: `stock-ai/config/buy_point_selection_validation.json`
- Modify only after a passing frozen run: runtime release metadata in MySQL through the Task 8 repository; do not store account data in Git.

**Interfaces:**
- Documents exact manual commands, shadow/live status, data prerequisites, and why zero candidates is valid.
- Produces fresh verification evidence for every completion claim.

- [ ] **Step 1: Write documentation assertions before editing docs**

Add a small test to `stock-ai/tests/unit/test_buy_point_full_universe_runtime.py` that reads the three documents and asserts they contain `buy-point-selection-3.0.0`, `0—3`, `影子研究`, `--refresh-reference-data`, and no scheduling installation instruction for this selector.

- [ ] **Step 2: Run the documentation assertion and verify RED**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=stock-ai:a-share-short-term-trading \
stock-ai/.venv/bin/pytest -q -p no:cacheprovider \
  stock-ai/tests/unit/test_buy_point_full_universe_runtime.py
```

Expected: documentation assertion fails before the docs are updated.

- [ ] **Step 3: Document the new system and safe rollout**

Document these commands exactly:

```bash
PYTHONPATH=stock-ai:a-share-short-term-trading stock-ai/.venv/bin/python \
  stock-ai/scripts/sync/sync_buy_point_reference_data.py --start 2024-01-02 --end latest

PYTHONPATH=stock-ai stock-ai/.venv/bin/python \
  stock-ai/scripts/analysis/backtest_buy_point_selection.py --research-train-validation

PYTHONPATH=stock-ai stock-ai/.venv/bin/python \
  stock-ai/scripts/analysis/backtest_buy_point_selection.py --freeze-profile

PYTHONPATH=stock-ai stock-ai/.venv/bin/python \
  stock-ai/scripts/analysis/backtest_buy_point_selection.py --run-test --write-artifact

PYTHONPATH=stock-ai:a-share-short-term-trading stock-ai/.venv/bin/python \
  a-share-short-term-trading/scripts/select_short_term_candidates.py --output text
```

The docs must state that a historical pass is insufficient for `LIVE`: at least 20 distinct manual forward dates and 20 resolved plans are also required.

- [ ] **Step 4: Run all focused unit and integration-free regression tests**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=stock-ai:a-share-short-term-trading \
stock-ai/.venv/bin/pytest -q -p no:cacheprovider \
  stock-ai/tests/unit/test_buy_point_reference_data.py \
  stock-ai/tests/unit/test_buy_point_reference_schema.py \
  stock-ai/tests/unit/test_buy_point_gates.py \
  stock-ai/tests/unit/test_buy_point_patterns.py \
  stock-ai/tests/unit/test_buy_point_planning.py \
  stock-ai/tests/unit/test_buy_point_service.py \
  stock-ai/tests/unit/test_buy_point_execution.py \
  stock-ai/tests/unit/test_buy_point_validation.py \
  stock-ai/tests/unit/test_backtest_buy_point_selection_cli.py \
  stock-ai/tests/unit/test_buy_point_full_universe_runtime.py \
  stock-ai/tests/unit/test_advisor_position_sync.py \
  a-share-short-term-trading/tests/test_buy_point_contracts.py \
  a-share-short-term-trading/tests/test_buy_point_repositories.py \
  a-share-short-term-trading/tests/test_buy_point_selection_service.py \
  a-share-short-term-trading/tests/test_select_short_term_candidates_cli.py \
  a-share-short-term-trading/tests/test_migration_files.py
```

Expected: zero failures.

- [ ] **Step 5: Run existing selection and trading regressions**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=stock-ai:a-share-short-term-trading \
stock-ai/.venv/bin/pytest -q -p no:cacheprovider \
  stock-ai/tests/unit/test_short_term_selection.py \
  stock-ai/tests/unit/test_selection_validation.py \
  stock-ai/tests/unit/test_backtest_short_term_trade.py \
  stock-ai/tests/unit/test_run_parallel_selection.py \
  stock-ai/tests/unit/test_limit_up_gene_watch.py \
  a-share-short-term-trading/tests/test_selection_service.py \
  a-share-short-term-trading/tests/test_intraday.py \
  a-share-short-term-trading/tests/test_diagnosis.py \
  a-share-short-term-trading/tests/test_repositories.py
```

Expected: zero failures and no legacy strategy gains formal eligibility.

- [ ] **Step 6: Apply migrations and sync reference data only with explicit runtime approval**

First run migration dry checks. Database mutation and Tushare network sync are separate runtime actions and require the user's explicit approval at execution time. After approval, apply `stock-mysql/sql/015`, `stock-mysql/sql/016`, and `a-share-short-term-trading/sql/006`, then run the reference sync and inspect coverage counts before any backtest.

- [ ] **Step 7: Run train/validation, freeze, and one-time test in order**

Do not write a promoted artifact if any gate fails. Inspect trade counts, all three setup metrics, rolling-window percentage, concentration, maximum drawdown, cost configuration, and point-in-time coverage. If the frozen test fails, commit the failing artifact/status as shadow evidence only when it contains no personal data; do not modify parameters against the test result.

- [ ] **Step 8: Run one manual shadow selection and inspect all three sections**

Verify that formal is zero before forward promotion, observe has no share count, shadow contains legacy hits without trade qualification, and the forward run is idempotent when repeated for the same analysis date.

- [ ] **Step 9: Review the complete diff and commit documentation/artifact status**

```bash
git diff --check
git status --short
git diff --stat
git add stock-ai/docs/CAPABILITIES.md \
  stock-ai/docs/PROJECT_LAYOUT.md \
  a-share-short-term-trading/README.md \
  stock-ai/config/buy_point_selection_validation.json
git commit -m "docs(stock-ai): document buy-point selector rollout"
```

If no validation artifact was generated, omit it from `git add`. Confirm unrelated user changes remain unstaged.

---

## Final Verification Checklist

- [ ] Every production-code change was preceded by a test that failed for the expected reason.
- [ ] All new focused tests pass in one fresh run.
- [ ] Existing short-term, validation, intraday, and legacy-shadow regressions pass.
- [ ] Migrations contain no destructive table operations and are idempotent.
- [ ] Historical dates use point-in-time membership, ST, and announcement facts only.
- [ ] Plain three-up, limit-up genes, events, and legacy scores cannot enter formal output.
- [ ] Only formal rows show maximum shares; observe and shadow rows show no trade qualification.
- [ ] A repeated manual run does not duplicate a structure, plan event, or forward-run record.
- [ ] A failed historical or forward gate leaves release mode non-live with zero executable shares.
- [ ] No scheduler, automatic order path, account snapshot, holding, or personal decision memory was added to Git.
