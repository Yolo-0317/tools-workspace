#!/usr/bin/env python3
"""微信公众号内容分析页（daily_v2）OpenCLI：流量 picker + highcharts 柱图（页面真源，不用 API）。"""

from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo

TZ = ZoneInfo("Asia/Shanghai")

# 与 get_article_stat_tendency_and_source 返回的 scene 一致（2026 后台实测）
SCENE_CHANNEL: dict[int, str] = {
    0: "公众号消息",
    1: "聊天会话",
    2: "朋友圈",
    4: "推荐",
    5: "公众号主页",
    6: "其它",
    7: "搜一搜",
}

CLICK_PERIOD_TAG_JS = r"""
(periodText) => JSON.stringify((() => {
  let clicked = false;
  for (const el of document.querySelectorAll(".weui-desktop-tag")) {
    const t = (el.innerText || "").trim();
    if (t === periodText) { el.click(); clicked = true; break; }
  }
  return { clicked, periodText };
})())
"""

SET_FLOW_DATE_RANGE_JS = r"""
(start, end) => new Promise((resolve) => {
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
  const parse = (s) => {
    const [y, m, d] = s.split("-").map(Number);
    return { y, m, d };
  };

  (async () => {
    const startD = parse(start);
    const endD = parse(end);

    const inFlow = (el) => {
      let p = el;
      for (let i = 0; i < 20 && p; i++) {
        const t = p.innerText || "";
        if (t.includes("流量分析") && t.includes("传播渠道")) return true;
        p = p.parentElement;
      }
      return false;
    };

    const picker = [...document.querySelectorAll(".weui-desktop-picker__date-range")].find(inFlow);
    if (!picker) {
      resolve(JSON.stringify({ ok: false, err: "未找到流量分析内的 .weui-desktop-picker__date-range" }));
      return;
    }

    const inputs = picker.querySelectorAll("input.weui-desktop-form__input");
    const startInp = inputs[0];
    const endInp = inputs[1];
    if (!startInp || !endInp) {
      resolve(JSON.stringify({ ok: false, err: "日期输入框缺失" }));
      return;
    }

    const panelFor = () =>
      document.querySelector(".weui-desktop-picker__panel_day") ||
      document.querySelector(".weui-desktop-picker__panel");

    const headerYm = (panel) => {
      const labels = [...panel.querySelectorAll(".weui-desktop-picker__panel__label")].map((x) =>
        (x.innerText || "").trim()
      );
      const y = parseInt((labels.find((l) => l.includes("年")) || "").replace(/\D/g, ""), 10);
      const m = parseInt((labels.find((l) => l.includes("月")) || "").replace(/\D/g, ""), 10);
      return { y, m, labels };
    };

    const navToMonth = async (panel, y, m) => {
      for (let i = 0; i < 48; i++) {
        const cur = headerYm(panel);
        if (cur.y === y && cur.m === m) return { ok: true, ...cur };
        // 该 picker 头栏常只有左箭头；改月用点击「MM月」标签选月
        const monthLabel = [...panel.querySelectorAll(".weui-desktop-picker__panel__label")].find((x) =>
          (x.innerText || "").includes("月")
        );
        if (monthLabel && cur.m !== m) {
          monthLabel.click();
          await sleep(350);
          const monthPanel = document.querySelector(".weui-desktop-picker__panel_day, .weui-desktop-picker__panel");
          const monthLink = [...(monthPanel?.querySelectorAll("a, td, span, button") || [])].find(
            (el) => (el.textContent || "").trim() === m + "月"
          );
          if (monthLink) {
            monthLink.click();
            await sleep(350);
            continue;
          }
        }
        if (!cur.y || !cur.m) return { err: "header parse fail", ...cur };
        const curIdx = cur.y * 12 + cur.m;
        const tgtIdx = y * 12 + m;
        const left = panel.querySelector(".weui-desktop-btn__icon__left");
        const right =
          panel.querySelector(".weui-desktop-btn__icon__right") ||
          panel.querySelector(".weui-desktop-btn__icon__right__out");
        if (curIdx > tgtIdx) left?.click();
        else if (right) right.click();
        else return { err: "no nav control", ...cur };
        await sleep(260);
      }
      return { err: "month nav timeout", ...headerYm(panel) };
    };

    const pickDay = async (inp, y, m, d) => {
      inp.focus();
      inp.click();
      await sleep(550);
      const panel = panelFor();
      if (!panel) return { err: "calendar panel missing" };
      const nav = await navToMonth(panel, y, m);
      if (nav.err) return nav;
      const links = [...panel.querySelectorAll("a")].filter((a) => !(a.className || "").includes("faded"));
      const link = links.find((a) => (a.textContent || "").trim() === String(d));
      if (!link) {
        return {
          err: "day not found",
          d,
          m,
          y,
          days: links.map((a) => a.textContent.trim()).slice(0, 15),
        };
      }
      link.click();
      await sleep(450);
      return { ok: true, value: inp.value, picked: d };
    };

    const r1 = await pickDay(startInp, startD.y, startD.m, startD.d);
    const r2 = await pickDay(endInp, endD.y, endD.m, endD.d);
    await sleep(4000);

    const dates = [...picker.querySelectorAll("input")].map((i) => i.value);
    resolve(
      JSON.stringify({
        ok: dates[0] === start && dates[1] === end,
        start,
        end,
        r1,
        r2,
        dates,
      })
    );
  })().catch((e) => resolve(JSON.stringify({ ok: false, err: String(e) })));
})
"""

EXTRACT_HIGHCHARTS_TRAFFIC_JS = r"""
JSON.stringify((() => {
  const CHANNELS = ["朋友圈", "搜一搜", "聊天会话", "公众号主页", "其它", "公众号消息", "推荐"];
  const container = [...document.querySelectorAll(".highcharts-container")].find((c) => {
    const t = c.innerText || "";
    return t.includes("搜一搜") && t.includes("推荐") && t.includes("聊天会话");
  });
  if (!container) return { ok: false, err: "未找到流量来源 .highcharts-container" };

  const nodes = [];
  for (const t of container.querySelectorAll("text,tspan")) {
    const txt = (t.textContent || "").trim();
    if (!CHANNELS.includes(txt) && !/^[\d.]+%$/.test(txt)) continue;
    if (/^[\d.]+%$/.test(txt) && parseFloat(txt) > 100) continue;
    const bb = t.getBoundingClientRect();
    nodes.push({ txt, cx: bb.x + bb.width / 2 });
  }
  const labels = nodes.filter((n) => CHANNELS.includes(n.txt));
  const pcts = nodes.filter((n) => /^[\d.]+%$/.test(n.txt));
  const paired = labels
    .map((lb) => {
      let best = null;
      let bestDx = 9999;
      for (const pc of pcts) {
        const dx = Math.abs(pc.cx - lb.cx);
        if (dx < bestDx) {
          bestDx = dx;
          best = pc;
        }
      }
      return { channel: lb.txt, pct: best?.txt, dx: bestDx };
    })
    .filter((x) => x.pct && x.dx < 40)
    .sort((a, b) => parseFloat(b.pct) - parseFloat(a.pct));

  const traffic = {};
  for (const row of paired) traffic[row.channel] = row.pct;

  return {
    ok: true,
    container_id: container.id,
    container_class: container.className,
    traffic_sources_pct: traffic,
    paired,
  };
})())
"""

FETCH_SOURCE_API_JS = r"""
(beginTs, endTs, token) => new Promise((resolve) => {
  const fp =
    (performance.getEntriesByType("resource").find((e) => e.name.includes("fingerprint="))?.name || "").match(
      /fingerprint=([^&]+)/
    )?.[1] || "";
  const url =
    "https://mp.weixin.qq.com/misc/appmsganalysis?begin_timestamp=" +
    beginTs +
    "&end_timestamp=" +
    endTs +
    "&action=get_article_stat_tendency_and_source&token=" +
    token +
    "&lang=zh_CN&f=json&ajax=1" +
    (fp ? "&fingerprint=" + fp : "");
  fetch(url, { credentials: "include" })
    .then((r) => r.json())
    .then((data) => {
      const list = data.all_article_stat_source?.list || [];
      const total = list.reduce((s, r) => s + (r.read_uv || 0), 0);
      const ranked = list
        .map((r) => ({
          scene: r.scene,
          channel: ({0:"公众号消息",1:"聊天会话",2:"朋友圈",4:"推荐",5:"公众号主页",6:"其它",7:"搜一搜"}[r.scene] ||
            "scene_" + r.scene),
          read_uv: r.read_uv || 0,
          share_uv: r.share_uv || 0,
          pct: total ? +(((r.read_uv || 0) / total) * 100).toFixed(1) : 0,
        }))
        .sort((a, b) => b.read_uv - a.read_uv);
      const traffic_sources_pct = {};
      for (const row of ranked) {
        if (row.channel.startsWith("scene_")) continue;
        traffic_sources_pct[row.channel] = row.pct.toFixed(1) + "%";
      }
      resolve(
        JSON.stringify({
          ok: data.base_resp?.ret === 0,
          url,
          total_read_uv: total,
          traffic_sources_pct,
          source_breakdown: ranked,
          base_resp: data.base_resp,
        })
      );
    })
    .catch((e) => resolve(JSON.stringify({ ok: false, err: String(e) })));
})
"""


def date_to_timestamp(d: date, *, end_of_day: bool = False) -> int:
    if end_of_day:
        dt = datetime(d.year, d.month, d.day, 23, 59, 59, tzinfo=TZ)
    else:
        dt = datetime(d.year, d.month, d.day, 0, 0, 0, tzinfo=TZ)
    return int(dt.timestamp())


def parse_ymd(text: str) -> date:
    return datetime.strptime(text.strip(), "%Y-%m-%d").date()
