# 工具映射与参数说明

> 来源：本会话对 mcd-mcp 连接器实际暴露的 schema 逐字段读取，并结合真实调用校准。
> 原则：**工具名、参数名、枚举值以连接器实际暴露为准**；本文档不新增未出现的字段。

## 1. 基础工具（9 个）

> 另有 §6（领券与积分，8 个）和 §7（主题活动，5 个）共 13 个工具，合计22个流程工具；真实会话已调用其中17个，详见仓库根目录 MCP_INTEGRATION.md。

| # | 工具 | 作用 | 必填 | 可选 / 要点 |
|---|---|---|---|---|
| 1 | `now-time-info` | 服务器时间基准 | 无（空对象） | 返回 `data.formatted`、`data.timestamp`、`data.timezone`、`data.dayOfWeek` |
| 2 | `query-my-coupons` | 券包资产 | 无 | `page`（默认 1，最多 5）、`pageSize`（默认 200，最大 200）。**只代表拥有，不代表本店可用** |
| 3 | `query-nearby-stores` | 到店/得来速门店 | `beType`、`searchType` | `city`、`keyword`（`searchType=2` 时二者必填） |
| 4 | `delivery-query-addresses` | 外送地址列表 | 无 | 返回 `data.addresses[]`，可能为空数组 |
| 5 | `delivery-query-stores` | 外送可配送门店 | `beType`、`addressId` | `addressId` 只能来自工具 4 |
| 6 | `query-store-coupons` | 门店 + 订单类型下的可用券 | `orderType`、`beType`、`storeCode` | `beCode`（见规则）、`reservationDate` |
| 7 | `query-meals` | 门店菜单 | `storeCode`、`orderType`、`beType` | `beCode`、`reservationDate` |
| 8 | `query-meal-detail` | 餐品详情/套餐组成/特调 | `storeCode`、`orderType`、`beType`、`code` | `beCode`、`reservationDate` |
| 9 | `calculate-price` | 价格与优惠试算 | `storeCode`、`orderType`、`beType` | `items[]`、`beCode`、`reservationDate`、`needTableware`、`withOrder`、`gmServiceCode` |

连接器另有门店/菜单同族的其它工具（如促销、活动日历、订单、商城、抽奖等），**v0.2.0 按 L0/L1/L2 分级：仅在授权范围内调用领券与积分兑换，其余未接入的写操作不调用**。

## 2. 枚举与传参对照

### beType / orderType

| 就餐方式 | `beType` | `orderType` | `beCode` |
|---|---|---|---|
| 到店自取 | 1 | 1 | **不传**（传了会报错，`query-meal-detail` 的说明里明确写了这一点） |
| 得来速 DT | 5 | 1 | **必传**，来自 `query-nearby-stores` |
| 麦乐送 | 2 | 2 | **必传**，来自 `delivery-query-stores` |
| 企业团餐 | 6 | 2 | **必传**，来自 `delivery-query-stores` |

### searchType（仅 `query-nearby-stores`）

- `1`：搜索收藏餐厅，不需要 `city` / `keyword`（默认值，但 schema 里同时列为 required，需显式传）。
- `2`：按位置搜索，`city` + `keyword` 必填。

### reservationDate

格式 `yyyy-MM-dd HH:mm`。预约场景必传，非预约场景不传。本技能首版默认非预约，只在用户明确说「预约」时才带。

## 3. 调用依赖顺序

```
now-time-info ──────────────────────────────► 时间基准
query-my-coupons ───────────────────────────► 券包 + 有效期

【到店分支】
query-nearby-stores(beType=1/5, searchType) ──► storeCode (+beCode)
        │
【外送分支】
delivery-query-addresses ──► addressId
        └──► delivery-query-stores(beType=2/6, addressId) ──► storeCode + beCode

                     storeCode (+beCode)
                            │
        ┌───────────────────┼────────────────────┐
        ▼                   ▼                    ▼
query-store-coupons     query-meals      query-meal-detail(按需)
        │                   │  (code)            │
        └───────────┬───────┴────────────────────┘
                    ▼
              calculate-price  ← 必须最后调，依赖上面的 code / couponId / couponCode
```

硬依赖：

- `delivery-query-stores.addressId` ← `delivery-query-addresses`
- `query-meal-detail.code` ← `query-meals`
- `calculate-price.items[].productCode` ← `query-meals` 或 `query-store-coupons.products[].productCode`
- `calculate-price.items[].couponId/couponCode` ← `query-store-coupons`（`query-my-coupons` 的券可能在本店不可用）
- 所有下游工具 `storeCode` ← 门店查询结果

## 4. 关键返回字段（只记录实际出现过的）

### `query-my-coupons`
`title`、优惠价（用券价格）、`tradeDateTime` 风格的有效期文案、领取时间、标签（如「今日到期」「到店专用」「外送专用」）。
原始结构未见结构化 `couponId`，**要拿 `couponId`/`couponCode` 必须走 `query-store-coupons`**。

### `query-store-coupons`
`data[].title`、`data[].couponId`、`data[].couponCode`、`data[].tradeDateTime`、`data[].promotionId`、`data[].products[].productCode`、`data[].products[].productName`。
同一 `couponId` 可对应多个 `couponCode`，展示时按 `couponId` 分组。

### `query-nearby-stores`
`data[].storeCode`、`storeName`、`address`、`distance`、`reservation`、`reservationTimeOptions[]`（`date`/`today`/`reservationOptionText`）、`latitude`/`longitude`。
`beType=1` 时返回里没有 `beCode`（与「到店自取不传 beCode」一致）；`beType=5` 才有 `beCode`。

### `query-meals`
`data.categories[].name`、`data.categories[].meals[].code`/`tags[]`；
`data.meals.{code}`：`name`、`image`、`currentPrice`（字符串，元）、`originalPrice`（字符串，元）、`discountType`、`canWithOrder`、`withOrder{membershipCode, specId}`、`cardId`/`cardType`（随机型出现）。
`data.frequent`：常点餐品。

### `calculate-price`（单位全部为**分**）
`productOriginalPrice`、`productPrice`、`deliveryOriginalPrice`、`deliveryPrice`、`packingOriginalPrice`、`packingPrice`、`tablewarePrice`、`originalPrice`、`discount`、`price`、
`productList[]`（`productCode`/`productName`/`quantity`/`originalSubtotal`/`subtotal`）、
`takeWayList[]`（`code`/`title`/`subtitle`，下单用，本技能只读）、
`mealAssistanceList[]`（团餐助餐服务）、
`enjoyed` / `enjoyable`（`amountType` 1 特价 2 折扣 3 立减、`realDiscount` 单位元、`balance` 单位分）。

## 5. 已实测的错误码与畸形行为

| 现象 | 触发 | 处理 |
|---|---|---|
| `code: 600022`，`message: 暂不支持多张券使用` | 一次 `calculate-price` 传了 2 张不同券 | 一套方案只放 1 张券。**2026-10-23 17:21 与 17:44 两次复核均复现，未支持叠加** |
| 请求 `quantity=2` 带 1 张券，返回 `productList[].quantity=1` | 券覆盖份数小于请求份数 | 以返回 `quantity` 为准；需要多份就拆成多行商品条目 |
| `data.addresses` 为 `[]` | 账户无外送地址 | 属「查询成功但无数据」，不是失败；需引导用户先添加地址（本技能不代建） |
| 券适用商品编码不在 `query-meals` 菜单映射中 | 券指向组合商品（实测 `9900016534`） | 仍可用该编码试算并成功减免，不要据菜单缺失否决 |
| `query-party-store-session` 对未开放日期仍返回场次 | 传入的 `dateStr` 不在 `query-party-store-date` 列表里（实测 2026-10-24） | **以 date 列表为准**；date 列表没有的日期，session 返回也不算可预约 |
| `query-party-city` 一次返回全国城市（约 300 条），无分页参数 | 任意调用 | 提示模型不要整段复述，按名称精确匹配 |

## 6. 领券与积分工具（v2 新增）

| 工具 | 参数 | 关键事实 |
|---|---|---|
| `available-coupons` | 无 | 返回券标题、状态（`已领取` / `可领取`）、图片。**不返回面额、有效期、积分价或费用字段**——无法据此判断券是否免费 |
| `auto-bind-coupons` | **无参数** | 一次领取当前全部可领券。**没有按 couponId 选择单张的参数**，不得编造；调用后必须刷新 `query-my-coupons` 与 `query-store-coupons` |
| `query-my-account` | 无 | `availablePoint`（**字符串且含小数**，实测 `"49.6"`）、`currentMouthExpirePoint`、`nextMouthExpirePoint`、`expiredPoint`、`frozenPoint`、`usedPoint`、`accumulativePoint` |
| `mall-points-products` | `catRuleIds`（可选，逗号分隔） | 类目：`1>4` 商品券、`2` 实物、`2>8` 周边、`1>6>20` 生日派对、`1>6>21` 主题派对、`1>6>22` 麦麦体验营、`1>6>25` 品鉴会、`1>6>34` 读书会、`1>6>40` 积分兑换活动。返回 `spuId`/`point`/`price`/`upTime`/`downTime`/`status`/`shopId` |
| `mall-product-detail` | `spuId`（必填） | 返回 `skuId`/`points`/`price`/`extTradePrice`/`spuCategory`/`shopId`/`note`/`partyType`/`spuLimit`。**`skuId` 才是兑换入参，`spuId` 不是** |
| `mall-create-order` | `skuId`、`spuCategory`；`addressId`（实体必填）；`count` | 仅支持 `shopId=2`；一商品一订单，多商品须串行排队。返回 `status`：1 全成功 / 2 部分成功 / 0 失败 |
| `mall-order-list` | `size`（默认 10，>10 按 10）、`lastId` | 实测账户无订单：`list: []`、`hasNext:false`。用于兑换超时后核查，而非重试 |
| `mall-order-detail` | `orderId`（必填） | 查单笔商城订单状态与券码 |

实测要点：

- `mall-points-products(1>6>21)` 返回 13 个主题派对 SPU，`point` 全为 `"0"`、`price` 为 `45~198`（元）。**主题派对是现金付费产品，不是积分兑换**，不要按"积分免费"表述。
- `mall-product-detail(6370)` → `skuId 6912`、`points "0"`、`price "55"`、`shopId 5`、`spuCategory "1"`。`shopId=5` 说明它走 `party-order-create`，不走 `mall-create-order`（后者仅 `shopId=2`）。
- `mall-product-detail.data.note` 是**纯展示文案**，接口说明明确禁止从中提取数值做校验；本技能只原文展示或概述，不解析。

## 7. 主题活动工具链（v2 新增）

| 工具 | 必填 | 上游来源 | 说明 |
|---|---|---|---|
| `campaign-calendar` | 无（`specifiedDate` 可选，`yyyy-MM-dd`） | — | 营销日历。传入日期则返回该日及前后最近的两个有活动的日子；不传返回当月。**只有标题和文案，没有门店/场次/余量** |
| `query-party-city` | `spuId` | `mall-points-products` 或 `mall-product-detail` | 返回 `code`/`name`/`latitude`/`longitude` |
| `query-party-store` | `code`（描述要求同时给 `latitude`/`longitude`/`spuId`） | `query-party-city` + `spuId` | 返回门店 `code`、名称、地址、`distance`、`businessStatus` |
| `query-party-store-date` | `spuId`、`storeCode` | `query-party-store` | 返回可预约 `date` 列表，可能是空数组 |
| `query-party-store-session` | `spuId`、`storeCode`、`dateStr` | `query-party-store-date` | 返回 `id`、`timeStart`/`timeEnd`、`partyMin`/`partyMax`、`price`（**分**）、`leftNum`、以及 `cookEmpNo`/`opEmpNo`/`rgmEmpNo` 员工编号（**不对外展示**） |

硬依赖链：

```
mall-points-products(catRuleIds=1>6>21) ──► spuId
        └──► mall-product-detail(spuId) ──► skuId / shopId / partyType / note

spuId ──► query-party-city ──► code + latitude + longitude
              └──► query-party-store(code, lat, lng, spuId) ──► storeCode
                        └──► query-party-store-date(spuId, storeCode) ──► dateStr
                                  └──► query-party-store-session(spuId, storeCode, dateStr) ──► 场次
```

**没有 spuId 就无法进入这条链**。不能只凭城市名硬调 `query-party-store`。

## 8. 未验证项

| 项 | 原因 |
|---|---|
| `auto-bind-coupons` 实调用 | 会真实改变账户券包，未获授权，本轮不执行 |
| `mall-create-order` 兑换 | 会扣积分，未获兑换授权 |
| `party-order-create` | 首版明确不接入自动预约 |
| 得来速（`beType=5`）的 `beCode` 全链路 | 收藏门店中无得来速门店 |
| 麦乐送 / 团餐（`beType=2/6`） | 账户无外送地址，`delivery-query-stores` 未进入 |
| `query-meal-detail` 的套餐组成与特调 | 本轮未构造套餐场景 |
| 预约下单 `reservationDate` | 未验证 |
| `mall-points-products(1>4)` 商品券兑换品 | 未查询该具体类目 |

