# 模块：周末主题活动查询

## 1. 两类"活动"不能混

| 类型 | 工具 | 返回什么 | 不能回答什么 |
|---|---|---|---|
| **营销活动**（新品、联名、限时优惠） | `campaign-calendar` | 活动标题 + 文案 + 图片，按日期归组 | 没有门店、场次、余量、可预约状态 |
| **主题活动预约**（派对/体验营/品鉴会） | `query-party-city` → `query-party-store` → `query-party-store-date` → `query-party-store-session` | 城市 → 门店 → 日期 → 场次，含价格、人数、余量 | 不覆盖普通营销活动 |

**营销日历不能替代预约场次**。用户问"这周末有什么活动"→ 先判断是"有什么新品/优惠"还是"有什么派对可以约"。

## 2. 「本周末」的时间锚点

先 `now-time-info` 拿北京时间，再显式换算成具体日期，不要用相对词糊过去。

以 `2026-10-23（周五）` 为例：

- 本周六 = **2026-10-24**
- 本周日 = **2026-10-25**

输出时必须写全"2026-10-24（周六）""2026-10-25（周日）"，不写"这周六"。

如果当前是周日，"本周末"指**今天**；如果当前已过周六，说明"本周只剩周日 2026-10-25"。

## 3. 主题活动链路（有硬上游）

```
mall-points-products(catRuleIds=1>6>21)   → spuId
        │  （也可用 1>6>20 生日 / 1>6>22 体验营 / 1>6>25 品鉴会 / 1>6>34 读书会 / 1>6>40 积分兑换活动）
        ▼
mall-product-detail(spuId)                → skuId / shopId / partyType / partyPeople / note
        ▼
query-party-city(spuId)                   → code + latitude + longitude
        ▼
query-party-store(code, lat, lng, spuId)  → storeCode
        ▼
query-party-store-date(spuId, storeCode)  → date 列表
        ▼
query-party-store-session(spuId, storeCode, dateStr) → 场次
```

**没有 `spuId` 就进不去这条链。** 只凭城市名硬调 `query-party-store` 是错的做法——缺 `spuId` 时应当明确报告"缺少活动标识来源"，而不是猜一个。

`spuId` 的合法来源只有两个：`mall-points-products` 或 `mall-product-detail` 的返回。不要编造。

## 4. 各步的必填参数（实际 schema）

| 工具 | 必填 | 说明 |
|---|---|---|
| `mall-points-products` | 无（`catRuleIds` 可选） | 不传返回全部类目，量大；按需传类目 |
| `mall-product-detail` | `spuId` | 必传 |
| `query-party-city` | `spuId` | 必传，返回全国城市列表（约 300 条，无分页） |
| `query-party-store` | `code`；描述要求同时给 `latitude`/`longitude`/`spuId` | 坐标必须来自 `query-party-city` 对应城市 |
| `query-party-store-date` | `spuId`、`storeCode` | 返回 `date` 列表，可能为空 |
| `query-party-store-session` | `spuId`、`storeCode`、`dateStr` | `dateStr` 必须来自上一步 |

## 5. 三个实测坑

1. **`date` 列表为空 ≠ 查询失败**。空数组表示该店该活动当前没有可约日期。
2. **`query-party-store-session` 对未开放日期仍会返回场次**。实测传 `2026-10-24`（不在 date 列表里）依然返回 2 个场次。**必须以 `date` 列表为准**，date 列表没有的日期不能说"可预约"。
3. **提前预订期会砍掉近几天**。实测门店 date 列表从 `2026-10-26` 起，而 `note` 写明"请提前 3 天预订"。所以"本周末没有场次"往往不是活动停办，而是没到可约窗口——要如实解释，不要断言"活动取消"。

## 6. 输出字段

| 字段 | 来源 | 缺失时 |
|---|---|---|
| 活动名称 | `spuName` | 必填，缺失则报错 |
| 城市 | `query-party-city.name` | 必填 |
| 门店 | `query-party-store.name` + `code` | 必填 |
| 日期 | `query-party-store-date.date` | 无 → 写"无可预约日期" |
| 场次 | `timeStart`-`timeEnd` | 无 → 写"该日无场次" |
| 价格 | `session.price`（**分**，除以 100） | 未返回 → **未知** |
| 人数限制 | `partyMin` / `partyMax` | 未返回 → **未知** |
| 余量 | `leftNum` | 未返回 → **未知** |
| 可预约状态 | 由 date 列表 + 场次 + `leftNum>0` 综合判断 | 任一缺失 → 标"部分未知" |

`cookEmpNo` / `opEmpNo` / `rgmEmpNo` 是内部员工编号，**不展示给用户**。

## 7. 场景参数

用户可能指定：城市、门店、日期、场次类型。处理顺序：

1. 有 `spuId` 来源即可开始；用户只说"主题派对"→ `catRuleIds=1>6>21`。
2. 用户指定城市 → 在 `query-party-city` 结果里按名称精确匹配，拿 `code`+坐标。
3. 用户指定门店 → 在 `query-party-store` 结果里匹配名称或 `code`。
4. 用户指定日期 → 先校验该日期在 `date` 列表里，再查场次。
5. 用户指定场次时间 → 在 `session` 列表里按 `timeStart` 匹配。

## 8. 只查活动时不要牵连个人数据

如果用户只是问"周末有什么活动/派对"，**不要**顺手查 `query-my-coupons`、`query-my-account`、`delivery-query-addresses`。

只有用户接着说"我积分够不够""我有券能用吗"再查对应账户。

## 9. 不做自动预约

本技能**不调用 `party-order-create`**。查到场次后，把信息给用户，让用户在官方渠道预约。

理由：预约涉及付费占位、人数和场次锁定，属于高副作用操作。

## 10. 两种"没有"要分开说

| 情况 | 判定 | 话术 |
|---|---|---|
| 周末无场次 | 链路全通，`date` 列表不含周末，或 `session` 返回空 | 「该门店本周末（10-24/10-25）无可预约场次；最近可约日期为 10-26」 |
| 活动查询失败 | 任一接口 `success:false` / 超时 / 缺少 `spuId` 来源 | 「活动查询失败：<原因>；无法确认本周末是否有场次」 |

绝不能把"没查到"写成"没有活动"，也不能把"没有场次"写成"查询失败"。
