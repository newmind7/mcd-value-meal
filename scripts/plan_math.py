#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""麦麦不白花 v2 — 确定性校验与计算引擎

职责边界（不要越界）：
  - 不查接口、不猜价格、不估算积分折现比例。
  - 只对 mcd-mcp 已返回的数值做确定性加工：校验 → 预算过滤 → 排序。
  - 金额一律用「分」的整数运算；积分单独记账，绝不换算成现金。

命令：
  expiry    判断券/积分/活动窗口的临期状态
  validate  校验单套方案（人数、份数、忌口、分配、实际数量、费用一致性）
  rank      校验全部候选 → 淘汰不合规 → 预算过滤 → 排序 → 输出

设计要点：
  1. 先校验需求满足，再做预算过滤和排序。顺序不可颠倒。
  2. 辣度 unknown 不算通过「不吃辣」硬约束。
  3. 共享餐品只记一次采购，不按人头重复计数。
  4. calculate-price 返回的 actualQty 是唯一成交数量依据。
"""

import argparse
import json
import sys
from datetime import datetime

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

DT_FORMATS = ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d")
NEAR_EXPIRY_HOURS = 24

# 辣度取值：spicy / not-spicy / unknown。缺失或非法值一律归为 unknown。
SPICY_VALUES = ("spicy", "not-spicy", "unknown")
# 餐品角色：main(主食) / side(小食) / drink(饮品) / dessert(甜品) / other
ROLES = ("main", "side", "drink", "dessert", "other")


# ---------------------------------------------------------------- 时间与临期
def parse_dt(text):
    if not text or not isinstance(text, str):
        return None
    text = text.strip().replace("/", "-")
    for fmt in DT_FORMATS:
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return None


def split_range(text):
    """'2026-10-19 10:30:00-2026-10-23 23:59:59' → (start, end)"""
    if not text:
        return None, None
    s = text.strip().replace("/", "-")
    for i in range(1, len(s)):
        if s[i] != "-":
            continue
        a, b = parse_dt(s[:i].strip()), parse_dt(s[i + 1:].strip())
        if a and b:
            return a, b
    single = parse_dt(s)
    return single, single


def classify(now, end):
    if now is None or end is None:
        return "UNKNOWN", None
    delta = (end - now).total_seconds()
    if delta < 0:
        return "EXPIRED", delta
    if delta <= NEAR_EXPIRY_HOURS * 3600:
        return "NEAR_EXPIRY", delta
    return "NORMAL", delta


LABEL = {"EXPIRED": "已过期", "NEAR_EXPIRY": "临期", "NORMAL": "正常", "UNKNOWN": "有效期未知"}


def fmt_remaining(seconds):
    if seconds is None:
        return "—"
    seconds = int(seconds)
    sign = "-" if seconds < 0 else ""
    h, rem = divmod(abs(seconds), 3600)
    return f"{sign}{h}小时{rem // 60}分"


def cmd_expiry(args):
    now = parse_dt(args.now)
    if now is None:
        print("错误：--now 无法解析，请用 yyyy-MM-dd HH:mm:ss", file=sys.stderr)
        return 2
    if args.range:
        start, end = split_range(args.range)
    else:
        start = parse_dt(args.start) if args.start else None
        end = parse_dt(args.end) if args.end else None
    status, delta = classify(now, end)
    print(json.dumps({
        "now": now.strftime("%Y-%m-%d %H:%M:%S"),
        "start": start.strftime("%Y-%m-%d %H:%M:%S") if start else None,
        "end": end.strftime("%Y-%m-%d %H:%M:%S") if end else None,
        "status": status,
        "statusLabel": LABEL[status],
        "remaining": fmt_remaining(delta) if delta is not None else None,
        "useToday": status in ("NEAR_EXPIRY", "NORMAL"),
    }, ensure_ascii=False, indent=2))
    return 0


# ---------------------------------------------------------------- 结构读取
def as_int(v, default=0):
    if isinstance(v, bool):
        return default
    if isinstance(v, int):
        return v
    if isinstance(v, float):
        return int(round(v))
    return default


def as_points(v, default=0.0):
    """积分可能是小数（实测 availablePoint = "49.6"），不能用 as_int 截断。"""
    if isinstance(v, bool):
        return default
    if isinstance(v, (int, float)):
        return round(float(v), 2)
    return default


def fmt_points(x):
    text = f"{float(x):.2f}".rstrip("0").rstrip(".")
    return text if text not in ("", "-0") else "0"


def get_orders(plan):
    """方案可能是单订单，也可能由多个订单组成（拆单）。统一返回订单列表。"""
    orders = plan.get("orders")
    if isinstance(orders, list) and orders:
        return orders
    return [plan]


def order_items(order):
    items = order.get("items")
    return items if isinstance(items, list) else []


# ---------------------------------------------------------------- 校验核心
def validate_plan(plan, expect_people=None):
    """返回 {errors, warnings, derived}。errors 非空即淘汰该方案。"""
    errors, warnings = [], []

    def err(code, msg):
        errors.append({"code": code, "msg": msg})

    def warn(code, msg):
        warnings.append({"code": code, "msg": msg})

    diners = plan.get("diners")
    if not isinstance(diners, list) or not diners:
        err("NO_DINERS", "方案未声明用餐人（diners 为空）")
        return {"errors": errors, "warnings": warnings, "derived": {}}

    # 1. 每人唯一编号
    ids = [d.get("dinerId") for d in diners]
    if any(not i for i in ids):
        err("DINER_ID_MISSING", "存在未编号的用餐人（dinerId 为空）")
    if len(set(ids)) != len(ids):
        dup = sorted({i for i in ids if ids.count(i) > 1 and i})
        err("DINER_ID_DUP", f"用餐人编号重复：{dup}")

    if expect_people is not None and len(diners) != expect_people:
        err("PEOPLE_MISMATCH", f"方案用餐人 {len(diners)} 人，与需求 {expect_people} 人不符")

    # 2. 汇总采购行 + 券实例使用次数
    orders = get_orders(plan)
    purchased = {}
    allocated = {}
    allocation_by_diner = {i: [] for i in ids if i}
    coupon_usage = {}

    for oi, order in enumerate(orders):
        for raw in order_items(order):
            line_id = raw.get("lineId") or f"O{oi + 1}-{raw.get('productCode')}"
            qty = as_int(raw.get("qty"), 0)
            if qty < 1:
                err("ITEM_QTY_INVALID", f"{line_id} 采购数量非法：{raw.get('qty')}")
                continue
            rec = purchased.setdefault(line_id, {
                "qty": 0, "actualQty": None,
                "name": raw.get("name") or line_id,
                "spicy": (raw.get("spicy") or "unknown").lower(),
                "role": (raw.get("role") or "other").lower(),
                "couponCode": raw.get("couponCode"),
                "componentsVerified": raw.get("componentsVerified", True),
            })
            rec["qty"] += qty
            if raw.get("actualQty") is not None:
                rec["actualQty"] = as_int(raw.get("actualQty"), 0)
            if rec["spicy"] not in SPICY_VALUES:
                rec["spicy"] = "unknown"
            if rec["couponCode"]:
                coupon_usage[rec["couponCode"]] = coupon_usage.get(rec["couponCode"], 0) + 1

    # 3. 分配记录（含共享）
    def take_alloc(entry, is_shared):
        line_id = entry.get("lineId")
        qty = as_int(entry.get("qty"), 0)
        if line_id not in purchased:
            err("ALLOC_UNKNOWN_LINE", f"分配引用了不存在的采购行：{line_id}")
            return
        allocated[line_id] = allocated.get(line_id, 0) + qty
        if is_shared:
            for did in entry.get("dinerIds") or []:
                if did not in allocation_by_diner:
                    err("ALLOC_UNKNOWN_DINER", f"共享餐品指向未知用餐人：{did}")
                else:
                    allocation_by_diner[did].append((line_id, qty, "side", True))
        else:
            did = entry.get("dinerId")
            if did not in allocation_by_diner:
                err("ALLOC_UNKNOWN_DINER", f"分配指向未知用餐人：{did}")
            else:
                allocation_by_diner[did].append((line_id, qty, purchased[line_id]["role"], False))

    for order in orders:
        for entry in order.get("allocation") or []:
            take_alloc(entry, False)
        for entry in order.get("shared") or []:
            take_alloc(entry, True)

    # 4. 不得超分配
    for line_id, rec in purchased.items():
        used = allocated.get(line_id, 0)
        if used > rec["qty"]:
            err("OVER_ALLOC", f"{rec['name']} 采购 {rec['qty']} 份，却分配了 {used} 份")

    # 5. 接口实际成交数量复核
    for line_id, rec in purchased.items():
        if rec["actualQty"] is None:
            warn("QTY_UNVERIFIED", f"{rec['name']} 未提供 actualQty，无法复核接口实际数量")
            continue
        if rec["actualQty"] < rec["qty"]:
            err("ACTUAL_QTY_SHORT",
                f"{rec['name']} 请求 {rec['qty']} 份，接口实际只返回 {rec['actualQty']} 份，"
                f"需重新分配或淘汰该方案")

    # 6. 每人有餐 + 最低需求 + 忌口
    diner_report = {}
    for d in diners:
        did = d.get("dinerId")
        if did not in allocation_by_diner:
            continue
        rows = allocation_by_diner[did]
        if not rows:
            err("DINER_NO_FOOD", f"{did} 没有任何餐品分配")
            continue

        min_req = d.get("minReq") or {"main": 1}
        got = {}
        for line_id, qty, role, is_shared in rows:
            got[role] = got.get(role, 0) + qty
        for role, need in min_req.items():
            need = as_int(need, 0)
            if got.get(role, 0) < need:
                err("MIN_REQ_NOT_MET",
                    f"{did} 最低需求 {role}×{need}，实际只有 {got.get(role, 0)} 份")

        if d.get("spicyAllowed") is False:
            for line_id, qty, role, is_shared in rows:
                rec = purchased[line_id]
                if rec["spicy"] == "spicy":
                    err("SPICY_VIOLATION",
                        f"{did} 不吃辣，却被分配了辣味餐品「{rec['name']}」")
                elif rec["spicy"] == "unknown":
                    err("SPICY_UNKNOWN",
                        f"{did} 不吃辣，「{rec['name']}」辣度未知，不能判为符合")

        diner_report[did] = {
            "rows": [{"lineId": l, "name": purchased[l]["name"], "qty": q,
                      "role": r, "shared": s, "spicy": purchased[l]["spicy"]}
                     for l, q, r, s in rows],
            "spicyAllowed": d.get("spicyAllowed", True),
        }

    # 7. 套餐组成是否核验
    for line_id, rec in purchased.items():
        if rec["componentsVerified"] is False:
            warn("COMPONENTS_UNVERIFIED",
                 f"「{rec['name']}」是套餐但未用 query-meal-detail 核验组成，标为条件方案")

    # 8. 同一张券实例不得跨订单重复使用
    for code, times in coupon_usage.items():
        if times > 1:
            err("COUPON_REUSED", f"券码 {code[:8]}… 在同一方案内被使用了 {times} 次")

    # 9. 费用一致性（现金整数分；积分独立记账）
    cash_total, points_total = 0, 0
    for oi, order in enumerate(orders):
        line_sum = sum(as_int(it.get("unitCashCent"), 0) *
                       as_int(it.get("actualQty", it.get("qty")), 0)
                       for it in order_items(order))
        fees = order.get("feesCent") or {}
        fee_sum = sum(as_int(v, 0) for v in fees.values())
        order_cash = order.get("cashCent")
        if order_cash is None:
            warn("CASH_UNVERIFIED", f"订单 {oi + 1} 未提供接口现金总额 cashCent")
            cash_total += line_sum + fee_sum
        else:
            order_cash = as_int(order_cash, 0)
            if line_sum and abs(line_sum + fee_sum - order_cash) > 1:
                warn("CASH_INCONSISTENT",
                     f"订单 {oi + 1} 逐项相加 {line_sum + fee_sum} 分，与接口总额 "
                     f"{order_cash} 分不一致，以接口总额为准")
            cash_total += order_cash
        points_total += as_points(order.get("pointsCost"), 0.0)

    # 10. 积分不得混入现金
    if plan.get("pointsInCash"):
        err("POINTS_AS_CASH", "方案把积分折算进了现金（不允许，积分必须独立记账）")

    n = len(diners)
    derived = {
        "people": n,
        "cashCent": cash_total,
        "pointsCost": points_total,
        "avgCashCent": (cash_total // n) if n else 0,
        "orders": len(orders),
        "couponCount": len(coupon_usage),
        "purchased": purchased,
        "dinerReport": diner_report,
    }
    return {"errors": errors, "warnings": warnings, "derived": derived}


def plan_ok(result):
    return not result["errors"]


# ---------------------------------------------------------------- 输出
def yuan(cent):
    return f"¥{cent / 100:.2f}"


def emit_plan(idx, plan, result):
    d = result["derived"]
    name = plan.get("label") or plan.get("planId") or f"方案{idx}"
    print(f"\n### 方案 {idx}｜{name}｜现金 {yuan(d['cashCent'])}"
          f"｜积分 {fmt_points(d['pointsCost'])}｜人均现金 {yuan(d['avgCashCent'])}")

    # 共享行按人头重复展示会误导（看起来像每人各得 2 杯可乐），因此单独成段，
    # 逐人清单里只标「共享」，不带份数。
    shared_lines = {}
    for line_id in d["purchased"]:
        diners_of_line = [did for did, info in d["dinerReport"].items()
                          if any(r["shared"] and r["lineId"] == line_id for r in info["rows"])]
        if diners_of_line:
            shared_lines[line_id] = diners_of_line

    print("\n**逐人分配**")
    for did, info in d["dinerReport"].items():
        tag = "" if info["spicyAllowed"] else "（不吃辣）"
        own = [f"{r['name']}×{r['qty']}" for r in info["rows"] if not r["shared"]]
        sh = [f"{r['name']}[共享]" for r in info["rows"] if r["shared"]]
        parts = own + sh
        print(f"- {did}{tag}：{'、'.join(parts) if parts else '无'}")

    if shared_lines:
        print("\n**共享餐品**（只计一次采购，不按人头重复计份）")
        for line_id, diners_of_line in shared_lines.items():
            rec = d["purchased"][line_id]
            print(f"- {rec['name']}×{rec['qty']}，{len(diners_of_line)} 人共享")

    print("\n**采购总清单**")
    for line_id, rec in d["purchased"].items():
        cpn = f"｜券 {rec['couponCode'][:8]}…" if rec["couponCode"] else ""
        act = "" if rec["actualQty"] is None else f"｜接口实际 {rec['actualQty']} 份"
        print(f"- {rec['name']}×{rec['qty']}{act}{cpn}")

    hot = sorted({r["name"] for info in d["dinerReport"].values()
                  for r in info["rows"] if r["spicy"] == "spicy"})
    if hot:
        print(f"\n**含辣餐品**：{'、'.join(hot)}（未分配给不吃辣的人）")

    if result["errors"]:
        print("\n**校验：不通过**")
        for e in result["errors"]:
            print(f"- ❌ [{e['code']}] {e['msg']}")
    else:
        print("\n**校验：通过**")
        print(f"- 用餐人 {d['people']} 人（编号唯一，均已分配餐品并满足最低需求）")
        abstain = [did for did, info in d["dinerReport"].items() if info["spicyAllowed"] is False]
        if abstain:
            print(f"- 忌口约束满足：{'、'.join(abstain)} 未分配到辣味或辣度未知餐品")
        else:
            print("- 本方案无人提出忌口限制")
        print("- 采购份数与分配份数一致，接口实际数量已复核")
    for w in result["warnings"]:
        print(f"- ⚠️ [{w['code']}] {w['msg']}")


def cmd_validate(args):
    with open(args.input, "r", encoding="utf-8") as f:
        payload = json.load(f)
    plan = payload.get("plan")
    if plan is None and isinstance(payload.get("plans"), list):
        target = args.plan_id
        for i, cand in enumerate(payload["plans"], 1):
            if target is not None and (cand.get("planId") == target or str(i) == str(target)):
                plan = cand
                break
        if plan is None and target is None and len(payload["plans"]) == 1:
            plan = payload["plans"][0]
    plan = plan or payload
    result = validate_plan(plan, args.people)
    emit_plan(1, plan, result)
    print("\n--- JSON ---")
    print(json.dumps({"errors": result["errors"], "warnings": result["warnings"]},
                     ensure_ascii=False, indent=2))
    return 0 if plan_ok(result) else 1


def cmd_rank(args):
    with open(args.input, "r", encoding="utf-8") as f:
        payload = json.load(f)
    plans = payload.get("plans") or []
    budget = args.budget if args.budget is not None else payload.get("budget")
    people = args.people if args.people is not None else payload.get("people")
    if budget is None or people is None:
        print("错误：需要预算与人数（命令行或文件内）", file=sys.stderr)
        return 2
    budget_cent = int(round(float(budget) * 100))

    print(f"预算 {yuan(budget_cent)} / {people} 人（人均上限 {yuan(budget_cent // people)}）")
    print(f"候选 {len(plans)} 套。顺序：先校验需求满足 → 再预算过滤 → 再排序。\n")

    passed, rejected, overspend = [], [], []
    for i, plan in enumerate(plans, 1):
        result = validate_plan(plan, people)
        if not plan_ok(result):
            rejected.append((i, plan, result))
            continue
        if result["derived"]["cashCent"] > budget_cent:
            overspend.append((i, plan, result))
            continue
        passed.append((i, plan, result))

    passed.sort(key=lambda x: (x[2]["derived"]["cashCent"], x[2]["derived"]["pointsCost"]))

    if not passed:
        print("❌ 当前预算与人数条件下，没有通过校验且未超预算的方案。")
        for i, plan, result in rejected:
            print(f"\n- 方案{i}「{plan.get('label', '')}」被淘汰：")
            for e in result["errors"][:3]:
                print(f"    [{e['code']}] {e['msg']}")
        for i, plan, result in overspend:
            gap = result["derived"]["cashCent"] - budget_cent
            print(f"\n- 方案{i}「{plan.get('label', '')}」需求达标但超预算 {yuan(gap)}")
        print("\n（不因为券临期或凑单而建议提高预算。）")
        return 0

    for n, (i, plan, result) in enumerate(passed[: args.limit], 1):
        emit_plan(n, plan, result)

    print("\n---")
    print("以上为本次已试算候选中最低的组合，非全局最优。")
    if rejected:
        print(f"\n另有 {len(rejected)} 套未通过需求校验，已淘汰：")
        for i, plan, result in rejected[:5]:
            first = result["errors"][0]
            more = f"（共 {len(result['errors'])} 项问题）" if len(result["errors"]) > 1 else ""
            print(f"- 原序号{i}「{plan.get('label', '')}」：{first['msg']}{more}")
    if overspend:
        print(f"另有 {len(overspend)} 套需求达标但超预算，未纳入。")
    return 0


def build_parser():
    p = argparse.ArgumentParser(description="麦麦不白花确定性校验与计算")
    sub = p.add_subparsers(dest="command", required=True)

    e = sub.add_parser("expiry", help="判断券/积分/活动窗口的临期状态")
    e.add_argument("--now", required=True)
    e.add_argument("--start")
    e.add_argument("--end")
    e.add_argument("--range")
    e.set_defaults(func=cmd_expiry)

    v = sub.add_parser("validate", help="校验单套方案")
    v.add_argument("--input", required=True)
    v.add_argument("--people", type=int)
    v.add_argument("--plan-id", help="从 plans 数组里挑一个 planId（或 1 起的序号）")
    v.set_defaults(func=cmd_validate)

    r = sub.add_parser("rank", help="校验+过滤+排序所有候选")
    r.add_argument("--input", required=True)
    r.add_argument("--budget", type=float)
    r.add_argument("--people", type=int)
    r.add_argument("--limit", type=int, default=3)
    r.set_defaults(func=cmd_rank)
    return p


def main():
    args = build_parser().parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
