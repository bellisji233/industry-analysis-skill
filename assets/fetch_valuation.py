#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
估值分位取数辅助脚本（行业分析 skill · methodology 第七节配套）
==============================================================
用途：把报告里最易幻觉的"历史估值分位"从"定性猜"升级为"一手数据"。
数据源：akshare 的 stock_value_em（东方财富个股估值，约 5–6 年日频，
        含 PE(TTM) / 市净率 / PEG / 市销率）。免费、无需 token。

用法：
    pip install akshare pandas
    python fetch_valuation.py 688017 002050 601689 300124
    python fetch_valuation.py 688017 --years 3        # 改分位回看年数
    python fetch_valuation.py 688017 --md             # 直接输出 markdown 表

设计原则（对齐 methodology 防编造硬约束）：
- 历史 PE/PB/PS 分位 = 可靠输出（真实日频序列算出来的），可直接写进报告。
- PEG = 东财口径，净利下滑/微利时会出现负值或极端值 → 脚本自动打 ⚠️ 失真标记，
  不可盲信；报告里 PEG 仍按"能指到来源才写、失真则降级定性"处理。
- 取不到数据时明确报错，不猜数——宁可留白让用户用 Wind 补。
"""
import sys
import argparse
import datetime as dt

def _die(msg):
    print(f"[fetch_valuation] {msg}", file=sys.stderr)
    sys.exit(1)

_HINT = ("缺少可选依赖：pip install -r assets/requirements.txt （akshare+pandas，免费无 token）。"
         "这是可选增强，非必需——未安装时请勿擅自 pip install，改回退为定性估值判断即可。")

try:
    import pandas as pd
except ImportError:
    _die("缺少 pandas。" + _HINT)

try:
    import akshare as ak
except ImportError:
    _die("缺少 akshare。" + _HINT)


def pct_rank(series, value):
    """value 在 series 中的历史分位（%），0=最低、100=最高。"""
    s = series.dropna()
    if len(s) == 0 or pd.isna(value):
        return None
    return round((s < value).mean() * 100)


def fetch_one(code, years=5):
    """取单只股票的当前估值 + 历史分位。返回 dict 或抛异常。"""
    df = ak.stock_value_em(symbol=code)
    if df is None or df.empty:
        raise ValueError(f"{code} 无估值数据")
    df["数据日期"] = pd.to_datetime(df["数据日期"])
    cutoff = dt.datetime.now() - pd.Timedelta(days=365 * years)
    win = df[df["数据日期"] >= cutoff]
    if win.empty:
        win = df
    cur = win.iloc[-1]
    pe, pb, ps, peg = cur["PE(TTM)"], cur["市净率"], cur["市销率"], cur["PEG值"]
    # PEG 失真判定：负值（净利下滑/亏损）或极端大值时不可用
    peg_flag = ""
    try:
        peg_v = float(peg)
        if peg_v <= 0 or peg_v > 5:
            peg_flag = " ⚠️失真(净利下滑/微利)"
    except (TypeError, ValueError):
        peg_v, peg_flag = None, " ❓"
    return {
        "code": code,
        "date": cur["数据日期"].date(),
        "pe": pe, "pe_pct": pct_rank(win["PE(TTM)"], pe),
        "pb": pb, "pb_pct": pct_rank(win["市净率"], pb),
        "ps": ps, "ps_pct": pct_rank(win["市销率"], ps),
        "peg": peg, "peg_flag": peg_flag,
        "n": len(win), "years": years,
    }


def fmt(v, nd=1):
    try:
        return f"{float(v):.{nd}f}"
    except (TypeError, ValueError):
        return "—"


def main():
    ap = argparse.ArgumentParser(description="取 A 股历史估值分位（akshare/东财）")
    ap.add_argument("codes", nargs="+", help="6 位股票代码，如 688017 002050")
    ap.add_argument("--years", type=int, default=5, help="分位回看年数，默认 5")
    ap.add_argument("--md", action="store_true", help="输出 markdown 表格")
    args = ap.parse_args()

    rows = []
    for code in args.codes:
        try:
            rows.append(fetch_one(code, args.years))
        except Exception as e:  # noqa: BLE001
            print(f"[skip] {code}: {type(e).__name__}: {e}", file=sys.stderr)

    if not rows:
        _die("全部取数失败")

    if args.md:
        print(f"| 标的 | 截至 | PE(TTM) | PE分位({args.years}Y) | PB | PB分位 | PS | PS分位 | PEG(东财) |")
        print("|---|---|---|---|---|---|---|---|---|")
        for r in rows:
            print(f"| {r['code']} | {r['date']} | {fmt(r['pe'])} | {r['pe_pct']}% | "
                  f"{fmt(r['pb'],2)} | {r['pb_pct']}% | {fmt(r['ps'])} | {r['ps_pct']}% | "
                  f"{fmt(r['peg'],2)}{r['peg_flag']} |")
    else:
        for r in rows:
            print(f"{r['code']} 截至{r['date']} (近{r['years']}年,{r['n']}日): "
                  f"PE(TTM)={fmt(r['pe'])}[分位{r['pe_pct']}%] "
                  f"PB={fmt(r['pb'],2)}[分位{r['pb_pct']}%] "
                  f"PS={fmt(r['ps'])}[分位{r['ps_pct']}%] "
                  f"PEG={fmt(r['peg'],2)}{r['peg_flag']}")

    print("\n注：PE/PB/PS 历史分位为真实日频序列算出，可直接引用；"
          "PEG 为东财口径，标 ⚠️失真/❓ 者不可盲信，应降级为定性判断。", file=sys.stderr)


if __name__ == "__main__":
    main()
