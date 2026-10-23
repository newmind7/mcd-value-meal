# 验收用例与验证状态

历史验证环境：WorkBuddy 开发会话，`mcd-mcp` 连接器，服务器时间 `2026-10-23 17:19 ~ 17:44`（GMT+8）。

状态标记：

- **真实调用** — 本次真的调了接口并记录返回。
- **模拟验证** — 用真实返回数据驱动本地脚本或走查规则，不产生新接口调用。**数据源已标注，方案组合为本地构造。**
- **尚未验证** — 未覆盖，不得写成通过。

> 模拟数据统一带 `"_mock": true`。任何由人手工填写的示例必须显式声明，禁止伪装成接口结果。

## 一、v2 新增：真实调用（12 例）

| ID | 用例 | 调用 | 实际结果 | 结论 |
|---|---|---|---|---|
| R12 | 可领券列表 | `available-coupons` | 5 条：2 条「已领取」(11.9 麦辣鸡腿堡、19.9 王牌炸鸡任选2)、3 条「可领取」(免费脆薯饼、11.9 麦辣鸡腿堡、19.9 王牌炸鸡任选2)。**无面额/积分/费用字段** | ✅ |
| R13 | 积分账户 | `query-my-account` | `availablePoint "49.6"`、`currentMouthExpirePoint "0"`、`nextMouthExpirePoint "0"`、`expiredPoint "170.9"`、`frozenPoint "0"` | ✅ |
| R14 | 营销日历 | `campaign-calendar`（无参） | 返回 10 月整月；`2026-10-24` 有「韩式风味蘸酱上新」「预约麦金喜抽奖」，`2026-10-25` 有「麦当劳联动 G-DRAGON」。**只有标题文案，无门店/场次/余量** | ✅ |
| R15 | 派对 SPU 列表 | `mall-points-products(catRuleIds=1>6>21)` | 13 个主题派对 SPU，`point` 全为 `"0"`、`price` 为 `45~198`、`shopId` 全为 `5`、`status` 全为 `2` | ✅ |
| R16 | 活动城市 | `query-party-city(spuId=6370)` | 全国城市列表（约 300 条），字段 `code`/`name`/`latitude`/`longitude`/`initial`/`sortNo`；桂林市 = `450300`, `25.235615`, `110.179752` | ✅ |
| R17 | 城市门店 | `query-party-store(450300, lat, lng, spuId=6370)` | 10 家桂林门店，含 `code`/`name`/`address`/`distance`/`businessStatus`；如 `3570109 桂林花生唐餐厅` | ✅ |
| R18 | 可约日期 | `query-party-store-date(6370, 3570109)` | `2026-10-26 ~ 2026-11-01`，**不含本周末 10-24/10-25** | ✅ |
| R19 | 未开放日期查场次 | `query-party-store-session(6370, 3570109, "2026-10-24")` | **仍返回 2 个场次**（15:30-17:00、17:00-18:30） | ✅ 发现陷阱 |
| R20 | 已开放日期查场次 | `query-party-store-session(6370, 3570109, "2026-10-26")` | 2 场次：`partyMin 5`、`partyMax 12`、`price 5500`（分=¥55）、`leftNum 12` | ✅ |
| R21 | 商城订单 | `mall-order-list(size=3)` | `data[0].list = []`、`hasNext=false`（账户无兑换订单） | ✅ |
| R22 | 兑换品详情 | `mall-product-detail(spuId=6370)` | `skuId 6912`、`points "0"`、`price "55"`、`shopId 5`、`spuCategory "1"`、`partyType -1`、`note` 含「请提前 3 天预订」 | ✅ |
| R23 | 多券叠加复测 | `calculate-price` 2 张不同券 | `success:false`、`code:600022`、`暂不支持多张券使用`（17:44:27，与 17:21 首次复现一致） | ✅ 仍不支持 |

## 二、v1 保留：真实调用（11 例）

| ID | 用例 | 结果 |
|---|---|---|
| R1 | `now-time-info` | `2026-10-23 17:19:16`，GMT+08:00 |
| R2 | `query-my-coupons` | 2 张，均至 `2026-10-23 23:59:59`，标签含「今日到期」 |
| R3 | `query-nearby-stores(beType=1, searchType=1)` | 2 家收藏门店，均无 `beCode`（到店自取符合预期） |
| R4 | `query-store-coupons(3570022)` | 2 张本店可用，带 `couponId`/`couponCode`/`products[]` |
| R5 | `query-meals(3570022)` | 完整菜单；`1440 麦辣鸡腿汉堡 ¥22.50` 等 |
| R6 | `calculate-price` 无券 ×2 | `4500` 分 |
| R7 | `calculate-price` 带券 ×2 | **返回只有 `quantity:1`**，`price:1190`、`discount:1060` |
| R8 | `calculate-price` 拆行 1 券 + 1 原价 | `3440` 分，`discount:1060` |
| R9 | `calculate-price` 券指向组合商品 `9900016534` | `2380 → 1990`，该编码不在 `query-meals` 映射里 |
| R10 | 双券叠加 | `600022` |
| R11 | `delivery-query-addresses` | `addresses: []` |

## 三、v2 新增：模拟验证（脚本，10 例）

数据文件：`examples/group-6p-150.mock.json`（**模拟**方案组合，部分单品行价格取自历史接口查询；完整购物车未真实试算，辣度为测试设定，券码为模拟标识）、`examples/verified-2026-10-23.json`（**真实**价格）。
一键复跑：`python scripts/selfcheck.py`（10/10 通过）。

| ID | 验收点 | 命令 | 实际输出 | 结论 |
|---|---|---|---|---|
| S1 | 6 人 150 元、2 人不吃辣，逐人分配满足 | `rank --input examples/group-6p-150.mock.json` | P1 通过：6 人各 1 份主食，D1/D2 为麦香鸡（not-spicy），现金 ¥123.10 ≤ ¥150；P7 现金相同但积分 49.6，排在其后 | ✅ |
| S2 | 总价够但少餐的方案被拒 | `validate --plan-id P2 --people 6` | `DINER_NO_FOOD: D5 / D6 没有任何餐品分配`，方案淘汰（其现金 ¥62.80 远低于预算） | ✅ |
| S3 | 试算返回数量减少后重新分配或淘汰 | `validate --plan-id P3 --people 2` | `ACTUAL_QTY_SHORT: 请求 2 份，接口实际只返回 1 份` + `SPICY_VIOLATION` | ✅ |
| S4 | 辣度未知不能判为符合 | `validate --plan-id P4 --people 2` | `SPICY_UNKNOWN: D1 不吃辣，「人气经典随心配」辣度未知，不能判为符合` | ✅ |
| S5 | 同一券实例不得跨订单复用 | `validate --plan-id P6 --people 2` | `COUPON_REUSED: 券码 MOCK_COUPON_A 在同一方案内被使用了 2 次` | ✅ |
| S6 | 积分消耗不参与现金比较 | 同 S1 的 P1 vs P7 | 现金同为 ¥123.10，P1 积分 0 排第一，P7 积分 49.6 排第二；积分未折算成钱 | ✅ |
| S7 | 单人预算搭餐仍正常 | `rank --input examples/verified-2026-10-23.json` | 3 套通过，¥11.90 / ¥19.90 / ¥34.40；¥45.00 超预算被剔除 | ✅ |
| S8 | 全部超预算的兜底 | 同上 `--budget 8 --people 1` | 「没有通过校验且未超预算的方案」+ 逐条差额 + 「不因为券临期或凑单而建议提高预算」 | ✅ |
| S9 | 小数积分不截断 | 同 S1 | 脚本显示 `积分 49.6`（未截断为 49） | ✅ |
| S10 | 临期判定与未知降级 | `expiry --range ...` / `expiry --end ""` | 前者 `NEAR_EXPIRY`、剩余 `6小时39分`；后者 `UNKNOWN` / `有效期未知` | ✅ |

## 四、v2 新增：尚未验证（5 项）

| ID | 未验证内容 | 原因 | 补齐方式 |
|---|---|---|---|
| N1 | `auto-bind-coupons` 真实领券，及「领券失败仍用已有券」 | 会真实改变账户券包，本轮未获授权 | 用户说「帮我领券」后执行一次，核对 `query-my-coupons` 前后差异 |
| N2 | `mall-create-order` 真实兑换扣积分 | 会扣积分，未获兑换授权 | 用户给出具体兑换清单并授权后执行，核对积分与券到账 |
| N3 | 兑换超时后 `mall-order-list` → `mall-order-detail` 的实际状态字段 | 无兑换订单可查（R21 为空） | 有一次真实兑换后验证 |
| N4 | 积分不足 / 兑换券不适用当前门店的真实拦截表现 | 未发起兑换 | 选一个积分不够的 SPU 试一次，记录返回 |
| N5 | 活动查询失败分支（`success:false` / 超时）与 `spuId` 缺失时的报错形态 | 本轮所有活动调用均成功 | 传不存在的 `spuId` 观察返回 |

`party-order-create`（活动预约）首版不接入，无需验证。

## 五、九项指定验收的对照

| 序号 | 要求 | 状态 |
|---|---|---|
| 1 | 6 人 150 元、2 人不吃辣，逐人分配满足 | ✅ S1（模拟） |
| 2 | 总价够但少餐的方案被拒绝 | ✅ S2（模拟） |
| 3 | 试算返回数量减少后，重新分配或淘汰 | ✅ S3（模拟） |
| 4 | 积分不足、兑换券不能用于当前店 | ⚠️ N4 尚未验证（过滤表已实现） |
| 5 | 不兑换积分也能生成方案 | ✅ S1 的 P1（方案 A 兜底，积分 0） |
| 6 | 领券失败时继续使用已有券 | ⚠️ N1 尚未验证（流程已实现） |
| 7 | 兑换超时不重复扣积分 | ⚠️ N3 尚未验证（查单工具已验证可达） |
| 8 | 周末无场次与活动查询失败分别说明 | ✅ 无场次已用真实数据验证（R18/R19）；⚠️ 失败分支 N5 未验证 |
| 9 | 单人预算搭餐仍正常工作 | ✅ S7（真实价格） |

## 六、回归清单（每次改动后跑）

```bash
python scripts/selfcheck.py        # 10 项一键自检，期望 10/10 通过
```

逐条等价命令：

```bash
S="scripts/plan_math.py"
python $S rank   --input examples/group-6p-150.mock.json            # 期望：P1 第一，P2/P3/P4/P6 淘汰
python $S rank   --input examples/verified-2026-10-23.json          # 期望：3 套通过
python $S rank   --input examples/verified-2026-10-23.json --budget 8 --people 1
python $S validate --input examples/group-6p-150.mock.json --plan-id P3 --people 2
python $S expiry --now "2026-10-23 17:20:59" --range "2026-10-19 10:30:00-2026-10-23 23:59:59"
```

人工核对：

1. `SKILL.md` 的操作分级仍为 L0/L1/L2，且 `party-order-create` 仍在禁入清单。
2. 输出模板中标题、表内、页脚金额三处一致。
3. 全文无「最优 / 最划算 / 全网最低」。
4. 模拟数据文件仍带 `"_mock": true`。

## 参赛材料整理说明（2026-10-23）

上述 R/S/N 条目保留历史开发记录的业务结论，不代表材料整理时重新调用接口。真实会话的可见对话与23次MCP调用索引已脱敏导出到根目录 workbuddy.md；流程共涉及22个工具，其中17个有实际调用记录。六人场景仅为本地模拟验证，不证明官方辣度或真实整单价格。公开样例已移除真实券码；本轮另行复跑10项本地自检。
