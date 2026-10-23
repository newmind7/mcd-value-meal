"""Export only public conversation text and an MCP call index from a local session.

Usage: python scripts/export_workbuddy.py <session.jsonl> --output workbuddy.md
Raw reasoning, provider metadata, full tool responses and private paths are omitted.
The source log is never modified. Inspect the generated document before publishing.
"""

import argparse
import hashlib
import json
import re
from collections import Counter
from datetime import datetime, timezone, timedelta
from pathlib import Path


PROJECT = Path(__file__).resolve().parent.parent
TZ = timezone(timedelta(hours=8))


def redact(text):
    text = re.sub(r"(?i)Bearer\s+(?!\$\{)[A-Za-z0-9._~+/=-]+", "Bearer [凭据已移除]", text)
    text = re.sub(r"\bMCD[A-Z0-9]{8,}\b", "MOCK_COUPON_A", text)
    text = re.sub(r"(?<!\d)1[3-9]\d{9}(?!\d)", "[手机号已移除]", text)
    text = re.sub(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", "[邮箱已移除]", text)
    text = re.sub(r"(?i)(?:D:[/\\]2Develop_Code[/\\]26[/\\]McDonald)", "[项目目录]", text)
    text = re.sub(r"(?i)C:[/\\]Users[/\\][^/\\\s`]+", "[本地用户目录]", text)
    return text


def time_text(timestamp):
    return datetime.fromtimestamp(timestamp / 1000, TZ).strftime("%Y-%m-%d %H:%M:%S +08:00")


def response_summary(row):
    """Keep allowlisted business status fields; no coupon/account/address objects."""
    if not row:
        return "未找到对应返回记录"
    output = row.get("output")
    text = output.get("text", "") if isinstance(output, dict) else ""
    tail = text.split("## Original Response")[-1]
    decoder = json.JSONDecoder()
    data = None
    for match in re.finditer(r"\{", tail):
        try:
            item, _ = decoder.raw_decode(tail[match.start():])
        except json.JSONDecodeError:
            continue
        if isinstance(item, dict) and isinstance(item.get("success"), bool):
            data = item
            break
    if data is None:
        return "有返回记录；业务结果见验收记录"
    parts = ["success=" + str(data["success"]).lower()]
    if "code" in data:
        parts.append("code=" + str(data["code"]))
    payload = data.get("data")
    if isinstance(payload, list):
        parts.append("返回列表条数=" + str(len(payload)))
    elif isinstance(payload, dict):
        for key in ("price", "originalPrice", "discount"):
            if key in payload and isinstance(payload[key], (int, float)):
                parts.append(key + "=" + str(payload[key]))
        if isinstance(payload.get("addresses"), list):
            parts.append("地址数量=" + str(len(payload["addresses"])))
    return "; ".join(parts)


def export(source, target):
    source = source.resolve()
    target = target.resolve()
    if source == target:
        raise ValueError("输出路径不能覆盖原始会话日志")
    raw = source.read_bytes()
    rows = [json.loads(line) for line in raw.decode("utf-8-sig").splitlines() if line.strip()]
    messages = [r for r in rows if r.get("type") == "message" and r.get("role") in ("user", "assistant")]
    calls = []
    for row in rows:
        if row.get("type") != "function_call" or row.get("name") != "DeferExecuteTool":
            continue
        args = json.loads(row["arguments"])
        name = args.get("toolName", "")
        if name.startswith("mcp__mcd-mcp__"):
            calls.append((row, name.removeprefix("mcp__mcd-mcp__")))
    results = {r.get("callId"): r for r in rows if r.get("type") == "function_call_result"}
    counts = Counter(name for _, name in calls)
    blocks = [
        "# WorkBuddy 开发上下文（真实记录，脱敏导出）",
        "",
        "项目：麦麦不白花 · https://github.com/newmind7/mcd-value-meal",
        "",
        "来源是本项目的本地 WorkBuddy 会话日志。下文保留真实用户请求和助手可见答复；"
        "剔除了注入的系统上下文、内部推理、账号/追踪元数据、完整工具响应及本机路径。"
        "券码用 MOCK_COUPON_A 代替；其他凭据和联系方式按规则移除。",
        "",
        "这是开发过程的历史记录，早期答复中的只读限制、功能数量和绝对表述不代表最终状态；"
        "最终功能与验证边界以 README.md、MCP_INTEGRATION.md 为准。"
        "历史开发者记录不等于本轮重新调用接口；本轮仅整理文件和复跑本地检查。",
        "",
        "- 原始日志 SHA-256：`" + hashlib.sha256(raw).hexdigest() + "`",
        "- 导出范围：" + time_text(messages[0]["timestamp"]) + " 至 " + time_text(messages[-1]["timestamp"]),
        "- 可见消息数：" + str(len(messages)),
        "- 麦当劳 MCP 调用记录：" + str(len(calls)) + " 次，涉及 " + str(len(counts)) + " 个不同工具。",
        "",
        "## 真实对话",
        "",
    ]
    for index, row in enumerate(messages, 1):
        texts = [c["text"] for c in row.get("content", []) if isinstance(c.get("text"), str)]
        content = "\n".join(texts)
        if row["role"] == "user":
            query = re.search(r"<user_query>([\s\S]*?)</user_query>", content)
            if query:
                content = query.group(1)
            else:
                content = re.sub(r"<system-reminder\b[^>]*>[\s\S]*?</system-reminder>", "", content)
        content = redact(content.strip())
        role = "用户" if row["role"] == "user" else "WorkBuddy 助手"
        blocks += ["### " + str(index) + ". " + role + " · " + time_text(row["timestamp"]), ""]
        blocks += ["> " + line if line else ">" for line in content.splitlines()]
        blocks.append("")
    blocks += ["## MCP 调用记录索引", "", "仅保留真实调用的时间、工具名、参数字段名及白名单结果摘要。业务失败的调用也保留；不把执行返回等同于业务成功。", "", "| 时间（北京时间） | 工具 | 参数字段（不含值） | 返回摘要 |", "|---|---|---|---|"]
    for row, name in calls:
        args = json.loads(row["arguments"])
        params = args.get("params") or {}
        keys = ", ".join(sorted(params)) if isinstance(params, dict) else "结构见原日志"
        summary = response_summary(results.get(row.get("callId")))
        blocks.append("| " + time_text(row["timestamp"]) + " | `" + name + "` | " + (keys or "无") + " | " + summary + " |")
    mutations = sorted(set(counts) & {
        "auto-bind-coupons", "mall-create-order", "create-order", "party-order-create",
        "cancel-order", "delivery-create-address", "draw-lottery",
    })
    if mutations:
        note = "日志中记录了以下账户操作调用：" + ", ".join(mutations) + "。调用记录本身不证明交易成功，实际结果须核对业务返回和账户状态。"
    else:
        note = "本日志未记录 auto-bind-coupons 实际领券、mall-create-order 积分兑换、create-order 点餐或 party-order-create 活动下单。相应能力只能按流程实现或尚未验证标注，不能写成交易成功。"
    blocks += ["", "## 账户操作记录范围", "", note, ""]
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("\n".join(blocks), encoding="utf-8")
    return {"messages": len(messages), "mcp_calls": len(calls), "distinct_tools": len(counts)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("session", type=Path)
    parser.add_argument("--output", type=Path, default=PROJECT / "workbuddy.md")
    args = parser.parse_args()
    print(json.dumps(export(args.session, args.output), ensure_ascii=False))


if __name__ == "__main__":
    main()
