#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""麦麦不白花 — 一键回归自检

只跑本地示例（不调接口、不改账户），对 plan_math.py 的校验能力做红绿判定。
用法：python scripts/selfcheck.py
退出码 0 = 全部通过；1 = 有失败。
"""

import re
import subprocess
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

ROOT = Path(__file__).resolve().parent.parent
PLAN = ROOT / "scripts" / "plan_math.py"
EX_GROUP = ROOT / "examples" / "group-6p-150.mock.json"
EX_SINGLE = ROOT / "examples" / "verified-2026-10-23.json"

CASES = [
    {
        "id": "S1",
        "desc": "6人150元2人不吃辣：P1 通过且排第一",
        "args": ["rank", "--input", str(EX_GROUP), "--limit", "1"],
        "must": ["方案 1｜全单·1 张券", "校验：通过", "现金 ¥123.10", "D1（不吃辣）", "薯条×1，6 人共享"],
        "must_not": ["SPICY_VIOLATION"],
    },
    {
        "id": "S2",
        "desc": "总价够但少餐的方案被拒",
        "args": ["validate", "--input", str(EX_GROUP), "--plan-id", "P2", "--people", "6"],
        "must": ["DINER_NO_FOOD", "校验：不通过"],
        "must_not": [],
    },
    {
        "id": "S3",
        "desc": "接口数量压缩后淘汰",
        "args": ["validate", "--input", str(EX_GROUP), "--plan-id", "P3", "--people", "2"],
        "must": ["ACTUAL_QTY_SHORT", "接口实际只返回 1 份"],
        "must_not": [],
    },
    {
        "id": "S4",
        "desc": "辣度未知不能判为符合",
        "args": ["validate", "--input", str(EX_GROUP), "--plan-id", "P4", "--people", "2"],
        "must": ["SPICY_UNKNOWN", "辣度未知"],
        "must_not": [],
    },
    {
        "id": "S5",
        "desc": "同一券实例不得跨订单复用",
        "args": ["validate", "--input", str(EX_GROUP), "--plan-id", "P6", "--people", "2"],
        "must": ["COUPON_REUSED"],
        "must_not": [],
    },
    {
        "id": "S6",
        "desc": "单人搭餐正常，超预算被剔除",
        "args": ["rank", "--input", str(EX_SINGLE)],
        "must": ["单人·用券单堡", "现金 ¥11.90", "另有 1 套需求达标但超预算"],
        "must_not": ["校验：不通过"],
    },
    {
        "id": "S7",
        "desc": "全部超预算时的兜底话术",
        "args": ["rank", "--input", str(EX_SINGLE), "--budget", "8", "--people", "1"],
        "must": ["没有通过校验且未超预算的方案", "不因为券临期或凑单而建议提高预算"],
        "must_not": [],
    },
    {
        "id": "S8",
        "desc": "小数积分不被截断",
        "args": ["rank", "--input", str(EX_GROUP), "--limit", "2"],
        "must": ["积分 49.6"],
        "must_not": ["积分 49｜"],
    },
    {
        "id": "S9",
        "desc": "临期判定",
        "args": ["expiry", "--now", "2026-10-23 17:20:59",
                 "--range", "2026-10-19 10:30:00-2026-10-23 23:59:59"],
        "must": ['"status": "NEAR_EXPIRY"', "6小时39分"],
        "must_not": [],
    },
    {
        "id": "S10",
        "desc": "有效期缺失降级为未知",
        "args": ["expiry", "--now", "2026-10-23 17:20:59", "--end", ""],
        "must": ['"status": "UNKNOWN"', "有效期未知"],
        "must_not": [],
    },
]


def run(case):
    proc = subprocess.run([sys.executable, str(PLAN)] + case["args"],
                          capture_output=True, text=True, encoding="utf-8")
    out = (proc.stdout or "") + (proc.stderr or "")
    missing = [m for m in case["must"] if m not in out]
    leaked = [m for m in case["must_not"] if m in out]
    return (not missing and not leaked), missing, leaked, out


def main():
    print(f"自检目录：{ROOT}\n")
    failed = 0
    for case in CASES:
        ok, missing, leaked, out = run(case)
        if ok:
            print(f"✅ {case['id']}  {case['desc']}")
        else:
            failed += 1
            print(f"❌ {case['id']}  {case['desc']}")
            for m in missing:
                print(f"     缺少预期输出：{m!r}")
            for m in leaked:
                print(f"     出现禁止输出：{m!r}")
            if not (missing or leaked):
                print(re.sub(r"\s+", " ", out)[:200])

    print(f"\n{len(CASES) - failed}/{len(CASES)} 通过")
    print("注意：本自检只覆盖本地模拟用例，不代表接口真实行为。")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
