#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
gmaps_live_tracker.py
Google Maps のライブ位置情報共有（公開リンク）から、共有者の
「時刻・緯度・経度・精度・住所」などを取得し CSV に追記する。

使い方:
    # 1回だけ取得
    python3 gmaps_live_tracker.py "https://maps.app.goo.gl/XXXX" --once

    # 15秒間隔でポーリングし続け track.csv に追記（Ctrl+C で終了）
    python3 gmaps_live_tracker.py "https://maps.app.goo.gl/XXXX" -o track.csv -i 15

仕組み:
    共有リンクを展開して user_id(1s) と share_token(2s) を取り出し、
    Google Maps 内部 RPC  batchexecute(rpcids=Qt4aBe)  を叩く。
    認証クッキーは不要（公開共有のため誰でも読める）。
依存: 標準ライブラリのみ（requests があれば使うがなくても動く）。
"""
import argparse, csv, json, os, re, sys, time, urllib.parse, urllib.request, urllib.error
from datetime import datetime, timezone, timedelta

RPC_URL = "https://www.google.com/maps/_/MapsWizUi/data/batchexecute?rpcids=Qt4aBe&hl=ja&rt=c"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"


def resolve_share(url: str):
    """短縮URL/共有URLから user_id と share_token を抽出"""
    loc = url
    # maps.app.goo.gl 等の短縮URLは1回リダイレクトされる
    if "maps.app.goo.gl" in url or "goo.gl" in url:
        class NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, *a, **k):
                return None
        op = urllib.request.build_opener(NoRedirect)
        req = urllib.request.Request(url, method="HEAD", headers={"User-Agent": UA})
        try:
            op.open(req, timeout=20)
        except urllib.error.HTTPError as e:
            loc = e.headers.get("location", url)
    m = re.search(r"!1s(\d+)!2s([^!?&]+)", loc)
    if not m:
        raise ValueError(f"共有トークンを抽出できませんでした。展開先: {loc}")
    uid = m.group(1)
    tok = urllib.parse.unquote(m.group(2))
    return uid, tok


def fetch_raw(uid: str, tok: str) -> str:
    inner = json.dumps([None, None, [[uid, tok]]])
    freq = json.dumps([[["Qt4aBe", inner, None, "generic"]]])
    data = urllib.parse.urlencode({"f.req": freq}).encode()
    req = urllib.request.Request(
        RPC_URL, data=data,
        headers={"User-Agent": UA,
                 "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8"})
    with urllib.request.urlopen(req, timeout=25) as r:
        return r.read().decode("utf-8", "replace")


def parse(raw: str):
    """batchexecute 応答から位置情報 dict を返す。共有停止中は None。"""
    # 先頭の )]}'  とチャンク長を除去して wrb.fr 行を探す
    payload = None
    for line in raw.splitlines():
        line = line.strip()
        if line.startswith("[[") and "wrb.fr" in line:
            arr = json.loads(line)
            for entry in arr:
                if entry and entry[0] == "wrb.fr" and entry[1] == "Qt4aBe":
                    payload = json.loads(entry[2])
                    break
    if payload is None:
        return None
    try:
        people = payload[0]
        if not people:
            return None
        person = people[0]
        acct = person[0]
        locv = person[1]
        uid = acct[0]
        name = acct[3] if len(acct) > 3 else None
        lng = locv[1][1]
        lat = locv[1][2]
        ts_ms = locv[2]
        acc = locv[3] if len(locv) > 3 else None
        addr = locv[4] if len(locv) > 4 else None
        tz_off_ms = locv[7] if len(locv) > 7 else 0
    except (IndexError, TypeError):
        return None
    tz = timezone(timedelta(milliseconds=tz_off_ms or 0))
    dt = datetime.fromtimestamp(ts_ms / 1000, tz)
    return {
        "timestamp_local": dt.isoformat(),
        "timestamp_unix_ms": ts_ms,
        "latitude": lat,
        "longitude": lng,
        "accuracy_m": acc,
        "address": addr,
        "name": name,
        "user_id": uid,
    }


FIELDS = ["timestamp_local", "timestamp_unix_ms", "latitude", "longitude",
          "accuracy_m", "address", "name", "user_id", "fetched_at"]


def write_row(path: str, row: dict):
    new = not os.path.exists(path) or os.path.getsize(path) == 0
    with open(path, "a", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        if new:
            w.writeheader()
        w.writerow(row)


def main():
    ap = argparse.ArgumentParser(description="Google Maps ライブ位置情報 → CSV")
    ap.add_argument("url", help="共有URL (https://maps.app.goo.gl/... など)")
    ap.add_argument("-o", "--output", default="track.csv", help="出力CSVパス")
    ap.add_argument("-i", "--interval", type=int, default=15, help="ポーリング間隔(秒)")
    ap.add_argument("--once", action="store_true", help="1回だけ取得して終了")
    args = ap.parse_args()

    uid, tok = resolve_share(args.url)
    print(f"[info] user_id={uid}", file=sys.stderr)
    print(f"[info] share_token={tok}", file=sys.stderr)

    last_ts = None
    while True:
        try:
            rec = parse(fetch_raw(uid, tok))
        except Exception as e:
            print(f"[warn] 取得失敗: {e}", file=sys.stderr)
            rec = None
        if rec is None:
            print("[warn] 位置情報なし（共有停止中か未更新）", file=sys.stderr)
        elif rec["timestamp_unix_ms"] != last_ts:
            rec["fetched_at"] = datetime.now(timezone(timedelta(hours=9))).isoformat()
            write_row(args.output, rec)
            last_ts = rec["timestamp_unix_ms"]
            print(f"[ok] {rec['timestamp_local']}  "
                  f"{rec['latitude']:.6f},{rec['longitude']:.6f}  "
                  f"±{rec['accuracy_m']}m  {rec['address']}")
        else:
            print(f"[skip] 更新なし ({rec['timestamp_local']})", file=sys.stderr)
        if args.once:
            break
        time.sleep(args.interval)


if __name__ == "__main__":
    main()
