#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
make_pota_parks.py — POTA公式APIから日本の公園一覧を取得し、
HamLogJP の PotaParks.json 形式へ変換して出力する。
あわせて、POTA日本有志会(pota-jp.com)の公園リストから日本語名を取り込み、
コードで突き合わせて nameJa（日本語名）を付与する。

配置先: hamlogjp-data リポジトリ（GitHub Action から実行）
出力:   リポジトリ直下（= GitHub Pages）の pota-parks.json
アプリ側取得URL: https://jpanhamlogapp.github.io/hamlogjp-data/pota-parks.json

使い方:
  python make_pota_parks.py pota-parks.json

取得元:
  英名・座標: https://api.pota.app/program/parks/JP
  日本語名  : https://pota-jp.com/parkslist/  （コード｜日本語名｜英名｜都道府県｜種別 の表）
"""

import json
import re
import sys
from datetime import date

import requests

API_URL = "https://api.pota.app/program/parks/JP"
JA_LIST_URL = "https://pota-jp.com/parkslist/"

# POTA の locationDesc(JP-XX) → 日本語の都道府県名（栃木=TC, 山形=YT, 滋賀=SH）
PREF = {
    "JP-HK": "北海道", "JP-AO": "青森県", "JP-IW": "岩手県", "JP-MG": "宮城県",
    "JP-AK": "秋田県", "JP-YT": "山形県", "JP-FS": "福島県", "JP-IB": "茨城県",
    "JP-TC": "栃木県", "JP-GM": "群馬県", "JP-ST": "埼玉県", "JP-CH": "千葉県",
    "JP-TK": "東京都", "JP-KN": "神奈川県", "JP-NI": "新潟県", "JP-TY": "富山県",
    "JP-IS": "石川県", "JP-FI": "福井県", "JP-YN": "山梨県", "JP-NN": "長野県",
    "JP-GF": "岐阜県", "JP-SZ": "静岡県", "JP-AI": "愛知県", "JP-ME": "三重県",
    "JP-SH": "滋賀県", "JP-KY": "京都府", "JP-OS": "大阪府", "JP-HG": "兵庫県",
    "JP-NR": "奈良県", "JP-WK": "和歌山県", "JP-TT": "鳥取県", "JP-SM": "島根県",
    "JP-OY": "岡山県", "JP-HS": "広島県", "JP-YC": "山口県", "JP-TS": "徳島県",
    "JP-KG": "香川県", "JP-EH": "愛媛県", "JP-KC": "高知県", "JP-FO": "福岡県",
    "JP-SG": "佐賀県", "JP-NS": "長崎県", "JP-KM": "熊本県", "JP-OT": "大分県",
    "JP-MZ": "宮崎県", "JP-KS": "鹿児島県", "JP-ON": "沖縄県",
    "JP-OG": "東京都",  # 小笠原（行政上は東京都）
}

CODE_RE = re.compile(r"^JP-\d{4}$")
HAS_JP = re.compile(r"[぀-ヿ㐀-鿿]")  # ひらがな/カタカナ/漢字を含むか


def load_ja_names() -> dict:
    """pota-jp.com の公園表から {コード: 日本語名} を作る。取得失敗時は空。"""
    ua = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
          "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")
    try:
        html = requests.get(JA_LIST_URL, timeout=60, headers={
            "User-Agent": ua,
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "ja,en;q=0.8",
        }).text
    except Exception as e:  # noqa: BLE001
        print("WARNING: 日本語名ページの取得に失敗:", e)
        return {}

    names = {}
    # 1) pandas で <table> を解釈
    try:
        import pandas as pd
        for df in pd.read_html(html):
            ncol = df.shape[1]
            if ncol < 2:
                continue
            code_col = None
            for ci in range(min(ncol, 3)):
                col = df.iloc[:, ci].astype(str).str.strip()
                if int(col.str.match(r"JP-\d{4}$").sum()) > 30:
                    code_col = ci
                    break
            if code_col is None or code_col + 1 >= ncol:
                continue
            for _, row in df.iterrows():
                code = str(row.iloc[code_col]).strip()
                ja = str(row.iloc[code_col + 1]).strip()
                if CODE_RE.match(code) and ja and ja.lower() != "nan" and HAS_JP.search(ja):
                    names[code] = ja
    except Exception as e:  # noqa: BLE001
        print("WARNING: pandasでの表解釈に失敗（HTML直接パースへ）:", e)

    # 2) 取れなければ HTML を直接パース（<td>JP-0001</td><td>日本語名</td> …）
    if not names:
        for code, ja in re.findall(
                r"(JP-\d{4})\s*</t[dh]>\s*<t[dh][^>]*>\s*([^<]+?)\s*</t[dh]>", html):
            ja = ja.strip()
            if HAS_JP.search(ja):
                names[code] = ja

    print(f"  日本語名ソース: {len(names)}件")
    return names


def main() -> int:
    out = sys.argv[1] if len(sys.argv) > 1 else "pota-parks.json"

    r = requests.get(API_URL, timeout=60,
                     headers={"User-Agent": "HamLogJP-parks/1.0"})
    r.raise_for_status()
    data = r.json()

    ja = load_ja_names()

    entries = []
    unknown = set()
    for p in data:
        ref = (p.get("reference") or "").strip()
        if not ref.startswith("JP-"):
            continue
        loc = (p.get("locationDesc") or "").strip()
        loc0 = loc.split(",")[0].strip() if loc else ""
        pref = PREF.get(loc0)
        if pref is None:
            pref = loc0 or ""
            if loc0:
                unknown.add(loc0)
        try:
            lat = float(p.get("latitude")) if p.get("latitude") is not None else None
            lon = float(p.get("longitude")) if p.get("longitude") is not None else None
        except (TypeError, ValueError):
            lat = lon = None
        entries.append({
            "ref": ref,
            "name": (p.get("name") or "").strip(),
            "nameJa": ja.get(ref, ""),
            "pref": pref,
            "lat": lat,
            "lon": lon,
            "grid": (p.get("grid") or "").strip(),
        })

    entries.sort(key=lambda e: e["ref"])
    ja_hit = sum(1 for e in entries if e["nameJa"])

    doc = {
        "dataVersion": 2,
        "updated": date.today().isoformat(),
        "note": ("POTA公式API(api.pota.app)から自動生成。日本語名(nameJa)は"
                 "POTA日本有志会(pota-jp.com)の公園リストより。未収録は英名にフォールバック。"),
        "entries": entries,
    }
    with open(out, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=1)

    print(f"wrote {out}: {len(entries)} parks (日本語名 {ja_hit}件)")
    if unknown:
        print("WARNING: 未知のlocationDescコード(要PREFマップ追加):", sorted(unknown))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
