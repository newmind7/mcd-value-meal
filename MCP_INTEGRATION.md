# 麦麦不白花 · MCP 集成说明

## Server 与运行方式

| 项目 | 配置 |
|---|---|
| MCP Server | 麦当劳中国 MCP，连接器名 `mcd-mcp` |
| 远程地址 | `https://mcp.mcd.cn` |
| 协议 | Streamable HTTP，WorkBuddy 配置中 `type: streamablehttp` |
| 身份认证 | `Authorization: Bearer ${MCD_MCP_TOKEN}`，由使用者本地提供 |
| 客户端 | WorkBuddy；任务中启用技能和连接器 |
| 技能入口 | `.workbuddy/skills/mcd-value-meal/SKILL.md`，版本0.2.0 |
| 本地计算 | `scripts/plan_math.py`，只做数量、需求、预算校验和排序，不请求接口 |

配置示例见根目录 [mcp-config.example.json](mcp-config.example.json)。占位符是否能自动展开取决于客户端；不支持时只在本地连接器编辑框替换。项目不保存真实 Token，不依赖本地 MCP 启动命令或 OAuth 客户端密钥。

官方能力说明：https://github.com/M-China/mcd-mcp-server 。具体参数以使用者当前连接器的工具定义为准。

## 实际工具与证据边界

技能流程涉及22个不同工具。现有 WorkBuddy 原始会话中可对应到 **23次 MCP 调用、17个不同工具**，包括预期失败的双券试算；不能把22个工具都写成已实测通过。

下表的“有记录”来自本地真实 WorkBuddy 会话的工具调用/返回事件，本轮整理没有重新访问麦当劳账户。原始凭据、券码和完整个人数据未进入导出。调用索引见 [workbuddy.md](workbuddy.md)，业务结果及条件见 [验收记录](.workbuddy/skills/mcd-value-meal/references/acceptance-tests.md)。

| 工具 | 用途 | 历史记录状态 |
|---|---|---|
| `now-time-info` | 当前时间、临期与周末日期基准 | 有记录 |
| `query-my-coupons` | 查询账户券包 | 有记录 |
| `query-nearby-stores` | 到店/得来速门店 | 到店收藏分支有记录；得来速和位置搜索未验证 |
| `delivery-query-addresses` | 外送已存地址 | 有记录，空列表 |
| `delivery-query-stores` | 可配送门店 | 流程接入，未实际调用 |
| `query-store-coupons` | 当前门店、渠道可用券 | 有记录 |
| `query-meals` | 当前门店菜单 | 有记录 |
| `query-meal-detail` | 套餐组成、口味与特调核验 | 流程接入，未实际调用 |
| `calculate-price` | 商品、费用和优惠试算 | 有记录，包括成功和双券拒绝 |
| `available-coupons` | 查询当前可领券 | 有记录 |
| `auto-bind-coupons` | 一键领券 | 流程接入，真实领取未验证 |
| `query-my-account` | 可用、冻结、临期积分 | 有记录 |
| `mall-points-products` | 积分商品和活动商品标识 | 派对类目有记录；商品券类目未验证 |
| `mall-product-detail` | SKU、积分/现金、规则 | 派对商品有记录；积分商品券详情未验证 |
| `mall-create-order` | 按清单授权后兑换 | 流程接入，真实兑换未验证 |
| `mall-order-list` | 商城订单、异常核查入口 | 有记录，空列表 |
| `mall-order-detail` | 单笔商城订单状态 | 流程接入，未实际调用 |
| `campaign-calendar` | 营销活动日历 | 有记录 |
| `query-party-city` | 活动可参与城市 | 有记录 |
| `query-party-store` | 活动可参与门店 | 有记录 |
| `query-party-store-date` | 可预约日期 | 有记录 |
| `query-party-store-session` | 预约场次、价格和余量 | 有记录，含日期不开放但仍返回场次的案例 |

工具细节见 [tool-map.md](.workbuddy/skills/mcd-value-meal/references/tool-map.md)。历史工具名为 `query-party-store-date` / `query-party-store-session`；不要根据其他版本文档拼写直接替换，需核对实际定义。

## 调用流程

### 1. 预算搭餐与多人分餐

```text
now-time-info → query-my-coupons
用户预算、人数、忌口、每人最低需求、位置与就餐方式
  ├─ 到店/得来速：query-nearby-stores → storeCode（必要时 beCode）
  └─ 外送：delivery-query-addresses → delivery-query-stores
门店 → query-store-coupons + query-meals
     → query-meal-detail（套餐组成/口味核验时）
     → 构造候选与逐人分配 → calculate-price
     → 按实际返回数量复核 → 本地预算过滤与排序 → 最多3套建议
```

`addressId`、`storeCode`、`productCode`、`couponId` 和具体券实例均取自上游真实返回。人数多不自动切换成企业团餐。预算按实际应付现金核算，费用使用整数分；积分独立比较。

### 2. 领券

```text
available-coupons → 核对用户请求/已授权偏好范围
→ auto-bind-coupons（无参数、全量领取）
→ query-my-coupons + query-store-coupons 刷新 → 回到搭餐
```

工具不支持按单张券领取。费用字段缺失时不能声称已证明免费；实际执行依赖用户授权和当前工具说明。失败时保留已有券方案；超时先查券包，避免盲目重复执行。当前没有真实领券记录。

### 3. 积分适配

```text
query-my-account → mall-points-products（商品券类）
→ mall-product-detail → 比较不兑换/兑换后降现金/临期积分方案
→ 展示商品、SKU、数量、积分、现金、有效期与条件 → 明确授权
→ mall-create-order → 刷新积分和券 → 核对本店可用 → 重新试算
异常：先 mall-order-list → mall-order-detail，不盲目重复兑换
```

未持有的券不编造券码；兑换前无法试算时标为条件方案。可兑换窗口与兑换后券有效期需分别核对，商品上下架时间不直接当作券有效期。现有真实记录只验证积分账户和派对商品查询，尚未完成积分商品券从查询到兑换、到账、使用的完整链路。

### 4. 周末活动

```text
now-time-info → 本周末具体日期
mall-points-products → 活动 spuId → mall-product-detail
→ query-party-city → query-party-store → query-party-store-date
→ 仅对可预约日期调用 query-party-store-session → 展示结果
```

`campaign-calendar` 独立提供营销文案，不代表可预约场次。日期必须先出现在日期列表中，不能仅凭 session 返回判断开放。不创建活动订单，不展示员工编号；单独查活动时不读取券包和积分账户。

## 业务价值

- 用户直接给出预算、人数与忌口，得到逐人清单与总采购表，减少手工比价和分餐负担。
- 优惠券经过拥有、本店可用、价格试算三层核对，减少权益适用条件的误读。
- 对比现金与积分消耗，保留不兑换方案，帮助用户判断本次是否需要兑换。
- 结合可预约日期与场次，减少将营销文案误当可预约活动的情况。

以上是设计目标与可观察的功能价值，尚无上线用户规模、转化率或节省金额的统计结论。

## 验证状态与限制

- 历史开发记录：23次真实 MCP 调用，涉及17个不同工具；返回空列表和预期失败也如实保留。
- 本地回归：运行现有 `selfcheck.py`，10项通过；只验证本地夹具与规则，不证明线上完整订单成立。
- 六人150元案例为模拟组合，辣度和分配包含测试设定。部分历史单价不能证明完整购物车已由接口试算，不以该案例保证真实门店价格或不辣。
- 真实领券、积分商品券兑换、扣积分、超时后查单、外送、得来速、预约点餐、套餐详情与部分错误分支仍未验证。
- 不接入 `create-order`、`cancel-order`、`party-order-create`、`delivery-create-address`、`draw-lottery`。
- 历史发现单次多券拒绝、带券数量压缩、未开放日期仍返回场次。保留防护规则，但不把某次历史结果保证为所有门店与未来版本的永久行为。

## 信息安全与凭据处理

配置仅发布环境变量占位符；个人 Token 由用户在本地 WorkBuddy 管理。原始 JSONL、记忆和账户配置不提交，公开开发记录只提取可见对话及调用索引。样例券码改成 `MOCK_COUPON_A` 等不可兑换标识；真实门店/商品编号作为公开业务标识保留。官方声明见 [CONTEST_DECLARATION.md](CONTEST_DECLARATION.md)。
