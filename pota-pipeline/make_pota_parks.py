#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
make_pota_parks.py — POTA公式APIから日本の公園一覧を取得し、
HamLogJP の PotaParks.json 形式へ変換して出力する。

配置先: hamlogjp-data リポジトリ（GitHub Action から実行）
出力:   リポジトリ直下（= GitHub Pages）の pota-parks.json
アプリ側取得URL: https://jpanhamlogapp.github.io/hamlogjp-data/pota-parks.json

使い方:
  python make_pota_parks.py pota-parks.json

取得元: https://api.pota.app/program/parks/JP
  各要素の主なキー: reference, name, latitude, longitude, grid, locationDesc(JP-XX)
  ※ name はPOTA登録の英語名。locationDesc は都道府県コード(POTA独自の2文字)。

出力仕様（アプリが読む）:
{
  "dataVersion": 1,
  "updated": "2026-09-14",
  "note": "...",
  "entries": [
    {"ref":"JP-0001","name":"...","pref":"北海道","lat":45.1942,"lon":141.239,"grid":"QN05oe"},
    ...
  ]
}
"""

import json
import sys
from datetime import date

import requests

API_URL = "https://api.pota.app/program/parks/JP"

# POTA の locationDesc(JP-XX) → 日本語の都道府県名
# ※ 実データに現れた確実なコードに加え、POTA標準の2文字コードを網羅。
#   未知コードはそのまま(JP-XX)を残し、CIログで警告する。
PREF = {
    "JP-HK": "北海道", "JP-AO": "青森県", "JP-IW": "岩手県", "JP-MG": "宮城県",
    "JP-AK": "秋田県", "JP-YM": "山形県", "JP-FS": "福島県", "JP-IB": "茨城県",
    "JP-TG": "栃木県", "JP-GM": "群馬県", "JP-ST": "埼玉県", "JP-CH": "千葉県",
    "JP-TK": "東京都", "JP-KN": "神奈川県", "JP-NI": "新潟県", "JP-TY": "富山県",
    "JP-IS": "石川県", "JP-FI": "福井県", "JP-YN": "山梨県", "JP-NN": "長野県",
    "JP-GF": "岐阜県", "JP-SZ": "静岡県", "JP-AI": "愛知県", "JP-ME": "三重県",
    "JP-SI": "滋賀県", "JP-KY": "京都府", "JP-OS": "大阪府", "JP-HG": "兵庫県",
    "JP-NR": "奈良県", "JP-WK": "和歌山県", "JP-TT": "鳥取県", "JP-SM": "島根県",
    "JP-OY": "岡山県", "JP-HS": "広島県", "JP-YC": "山口県", "JP-TS": "徳島県",
    "JP-KG": "香川県", "JP-EH": "愛媛県", "JP-KC": "高知県", "JP-FO": "福岡県",
    "JP-SG": "佐賀県", "JP-NS": "長崎県", "JP-KM": "熊本県", "JP-OT": "大分県",
    "JP-MZ": "宮崎県", "JP-KS": "鹿児島県", "JP-ON": "沖縄県",
    "JP-OG": "東京都",  # 小笠原（行政上は東京都）
}


def main() -> int:
    out = sys.argv[1] if len(sys.argv) > 1 else "pota-parks.json"

    r = requests.get(API_URL, timeout=60,
                     headers={"User-Agent": "HamLogJP-parks/1.0"})
    r.raise_for_status()
    data = r.json()

    entries = []
    unknown = set()
    for p in data:
        ref = (p.get("reference") or "").strip()
        if not ref.startswith("JP-"):
            continue
        loc = (p.get("locationDesc") or "").strip()
        # locationDesc は稀に "JP-TK,JP-KN" のように複数入るので先頭を採用
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
            "pref": pref,
            "lat": lat,
            "lon": lon,
            "grid": (p.get("grid") or "").strip(),
        })

    entries.sort(key=lambda e: e["ref"])

    doc = {
        "dataVersion": 1,
        "updated": date.today().isoformat(),
        "note": "POTA公式API(api.pota.app/program/parks/JP)から自動生成。nameはPOTA登録の英語名。",
        "entries": entries,
    }
    with open(out, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=1)

    print(f"wrote {out}: {len(entries)} parks")
    if unknown:
        print("WARNING: 未知のlocationDescコード(要PREFマップ追加):", sorted(unknown))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
