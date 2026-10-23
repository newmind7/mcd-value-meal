# 麦麦不白花 · mcd-value-meal v0.2.0

本目录是完整的 WorkBuddy Skill，保留入口、参考流程、计算脚本与示例。

## 安装与使用

完整的项目介绍、安装、目标用户和示例统一维护在[仓库根目录 README](../../../README.md)。复用用户自己的 `mcd-mcp` 连接器，远程地址为 `https://mcp.mcd.cn`，协议为 Streamable HTTP；不自行启动本地 MCP 服务。

若只收到这个技能目录：将整个目录放入 WorkBuddy 项目技能位置，或使用当前版本的自定义技能导入入口。配置并启用连接器后，新建任务测试 `now-time-info`。本目录的 [mcp-config.example.json](mcp-config.example.json) 只含环境变量凭据占位符，使用说明见根目录 README。

## 能力与验证边界

- 预算搭餐、账户券查询、菜单和价格试算：有历史真实调用记录。
- 自动领券：流程已编写，真实领取尚未验证。
- 多人分餐：本地校验与排序已通过模拟检查，六人完整订单未真实试算。
- 积分适配：账户和商城查询有记录；积分商品券查询、兑换和到账使用链路尚未完整验证。
- 周末活动：有城市、门店、日期、场次查询记录；不创建活动订单。

现金与积分独立展示，先满足人数、份数和忌口再筛预算；不承诺全局最优。模拟样例的辣度不是官方证明，券码均为不可兑换的测试标识。

## 本地验证

从本技能目录执行：

```powershell
python scripts/selfcheck.py
python scripts/plan_math.py rank --input examples/group-6p-150.mock.json --limit 1
```

第一条为10项本地回归，第二条展示模拟分餐。均不调用接口、不改变账户。详细状态见 [references/acceptance-tests.md](references/acceptance-tests.md)。

## 提交材料

参赛所需 README、官方声明、MCP_INTEGRATION、脱敏配置和真实 WorkBuddy 开发上下文放在仓库根目录，参见 [SUBMISSION.md](../../../SUBMISSION.md)。不要只上传本目录或压缩包而漏掉根目录材料。
