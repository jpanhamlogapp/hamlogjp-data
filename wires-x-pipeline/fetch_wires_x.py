#!/usr/bin/env python3
"""
WiRES-X アクティブノード取得スクリプト（HamLogJP 用）

Yaesu の active_node.php はページ内に JavaScript の
  dataList[0] = {dtmf_id:"...", call_sign:"...", ana_dig:"...", city:"...",
                 state:"...", country:"...", freq:"...", sql:"...",
                 lat:"...", lon:"...", comment:"..."};
という形で全ノードを埋め込んでいる。
これを正規表現で抽出し、緯度経度(DMS)を10進へ変換、デジタル/アナログを判定し、
座標を持つノードだけを wires_x_nodes.json として出力する。

出力仕様（アプリが読む）:
{
  "generated_at": "2026-08-04T12:00:00Z",
  "count": 1234,
  "nodes": [
    {
      "id": "12345",            # DTMF ノードID
      "call": "JA1ABC",
      "mode": "digital",        # "digital" | "analog" | "unknown"
      "ana_dig_raw": "Digital", # 元の値（判定調整用）
      "city": "Tokyo",
      "state": "",
      "country": "Japan",
      "freq": "439.000",
      "sql": "",
      "lat": 35.681236,         # 10進度（南は負）
      "lon": 139.767125,        # 10進度（西は負）
      "comment": "..."
    }, ...
  ]
}
座標のないノードは出力しない（地図に出せないため）。
"""

import json
import re
import sys
from datetime import datetime, timezone

import requests

YAESU_URL = "https://www.yaesu.com/jp/en/wires-x/id/active_node.php"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Connection": "close",
}


def fetch_html(url: str, timeout: int = 20) -> str:
    resp = requests.get(url, headers=HEADERS, timeout=timeout)
    resp.raise_for_status()
    return resp.text


def dms_to_decimal(dms: str):
    """'N:35 39' 42\"' のような DMS 文字列を 10進度に変換。空なら None。"""
    if not dms:
        return None
    dms = dms.replace("&quot;", '"').strip()
    try:
        direction, rest = dms.split(":", 1)
        direction = direction.strip().upper()
        # 度・分・秒を数値だけ抜き出す
        nums = re.findall(r"[\d.]+", rest)
        if len(nums) < 1:
            return None
        deg = float(nums[0])
        minutes = float(nums[1]) if len(nums) > 1 else 0.0
        seconds = float(nums[2]) if len(nums) > 2 else 0.0
        decimal = deg + minutes / 60.0 + seconds / 3600.0
        if direction in ("S", "W"):
            decimal = -decimal
        return round(decimal, 6)
    except Exception:
        return None


def classify_mode(ana_dig: str) -> str:
    """ana_dig の値からデジタル/アナログを判定。値の実態は実データで要確認。"""
    if not ana_dig:
        return "unknown"
    v = ana_dig.strip().lower()
    # デジタル系のキーワード
    if any(k in v for k in ("dig", "c4fm", "fusion", "dn", "vw")):
        return "digital"
    # アナログ系
    if any(k in v for k in ("ana", "fm")):
        return "analog"
    # 1桁コードのパターン（環境により "1"=analog / "2"=digital 等の可能性）
    if v in ("d", "2"):
        return "digital"
    if v in ("a", "1"):
        return "analog"
    return "unknown"


def parse_nodes(html: str):
    """dataList[N] = {...}; の行から辞書配列を作る。"""
    pattern = re.compile(r"dataList\[\d+\]\s*=")
    nodes = []
    for line in html.splitlines():
        if not pattern.match(line.strip()):
            continue
        pairs = re.findall(r'(\w+)\s*:\s*"([^"]*)"', line)
        item = {k: v for k, v in pairs}
        lat = dms_to_decimal(item.get("lat", ""))
        lon = dms_to_decimal(item.get("lon", ""))
        if lat is None or lon is None:
            continue  # 座標なしは地図に出せないので除外
        ana_dig = item.get("ana_dig", "")
        nodes.append({
            "id": item.get("dtmf_id", ""),
            "call": item.get("call_sign", ""),
            "mode": classify_mode(ana_dig),
            "ana_dig_raw": ana_dig,
            "city": item.get("city", ""),
            "state": item.get("state", ""),
            "country": item.get("country", ""),
            "freq": item.get("freq", ""),
            "sql": item.get("sql", ""),
            "lat": lat,
            "lon": lon,
            "comment": item.get("comment", ""),
        })
    return nodes


def main():
    out_path = sys.argv[1] if len(sys.argv) > 1 else "wires_x_nodes.json"
    html = fetch_html(YAESU_URL)
    nodes = parse_nodes(html)
    payload = {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "count": len(nodes),
        "nodes": nodes,
    }
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, separators=(",", ":"))
    # 判定確認用に mode 別件数と ana_dig の実値を stderr に出す
    modes = {}
    raw_vals = {}
    for n in nodes:
        modes[n["mode"]] = modes.get(n["mode"], 0) + 1
        raw_vals[n["ana_dig_raw"]] = raw_vals.get(n["ana_dig_raw"], 0) + 1
    print(f"nodes with coordinates: {len(nodes)}", file=sys.stderr)
    print(f"mode counts: {modes}", file=sys.stderr)
    print(f"ana_dig raw values: {raw_vals}", file=sys.stderr)


if __name__ == "__main__":
    main()
