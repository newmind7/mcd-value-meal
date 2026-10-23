# 麦麦不白花 · mcd-value-meal

把「几个人、多少钱、谁不吃辣」变成可核对的麦当劳点餐清单，并结合优惠券、积分和周末主题活动提供建议。

这是基于麦当劳中国 `mcd-mcp` 的 WorkBuddy Skill，当前版本 **0.2.0**。技能复用用户自己的连接器；本地 Python 脚本负责数量、分配、预算和排序，不自行提供 MCP 服务。

- 项目仓库：https://github.com/newmind7/mcd-value-meal
- 作者：GitHub 用户 [newmind7](https://github.com/newmind7)
- 技能入口：[SKILL.md](.workbuddy/skills/mcd-value-meal/SKILL.md)

## 目标用户与功能

| 功能 | 解决的问题 | 当前验证范围 |
|---|---|---|
| 预算搭餐、临期券提醒 | 从门店菜单和账户券中选出预算内候选，再核对试算金额 | 已有真实查询和价格试算记录 |
| 自动领券 | 用户要求或命中已授权偏好时，一键领取后刷新券包 | 流程已编写；真实领取尚未验证 |
| 多人分餐 | 逐人核对主食份数、忌口、共享餐品和接口实际数量 | 本地模拟验证通过；六人完整订单尚未真实试算 |
| 积分适配 | 比较不兑换与兑换后的现金支出、积分消耗 | 积分查询已留有记录；商品券兑换与扣积分尚未验证 |
| 周末主题活动 | 区分营销日历与可预约活动，查询城市、门店、日期、场次 | 已有查询记录；不创建活动订单 |

适合个人午餐、同事拼餐、家庭用餐，以及希望利用现有权益、查询周末活动的人。首版不代下餐饮订单、不支付、不抽奖。

## 安装与连接

1. 安装 WorkBuddy；本地脚本需要 Python 3.9 或更高版本，仅使用标准库。
2. 克隆本仓库，或下载并解压源码：

   ```powershell
   git clone https://github.com/newmind7/mcd-value-meal.git
   ```

3. 在 WorkBuddy 中打开仓库根目录。技能位于 `.workbuddy/skills/mcd-value-meal/`，保持该目录及其 `references`、`scripts`、`examples` 完整。新建任务后检查技能是否加载；如果当前版本未识别项目级目录，可从「专家·技能·连接器 → 技能」的自定义技能入口导入完整技能包，以实际界面为准。
4. 前往 [麦当劳 MCP 平台](https://open.mcd.cn/mcp) 申请自己的 Token。在 WorkBuddy 的「专家·技能·连接器 → 连接器 → 自定义连接器 → 配置 MCP」中，参考 [mcp-config.example.json](mcp-config.example.json) 配置并启用 `mcd-mcp`。
5. 示例使用 `Bearer ${MCD_MCP_TOKEN}` 表示凭据。**不要假设 WorkBuddy 自动展开环境变量**；若客户端不支持插值，在本地连接器编辑框中替换为自己的 Token。不要把替换后的配置保存进本仓库。
6. 在新任务中启用连接器，输入「调用 now-time-info 检查麦当劳 MCP 连接」，成功后再使用技能。

技能以任务中能否调用工具为连接依据。仅有技能文件、未启用连接器时，无法获得实时菜单和账户权益。

## 使用示例

### 多人搭餐

> 使用麦麦不白花：6个人，总预算150元，其中2个人不吃辣，每人至少一份主食，饮料可选。上海人民广场附近到店取餐。先比较现有券与积分方案，兑换前列清单给我确认。

预期输出：逐人餐品、共享小食、采购总表、使用的券、现金与积分、需求校验结果。缺少门店或口味依据时，技能会补问或标为未知，不能用少餐或未知辣度凑低价。

### 领券与积分

> 帮我领取当前麦麦省可领券，刷新后再搭配30元以内的一人餐。

> 查查我的积分能换哪些本次用得上的商品券，同时保留不花积分的方案。先不要兑换。

一键领券工具领取全部当前可领券，不能指定单张。实际扣积分前需要具体清单的授权；尚未到账的券只能作为条件方案，不能编造券码试算。

### 周末活动

> 查桂林本周末的麦当劳主题活动，列出城市、门店、具体日期、场次和接口返回的价格与余量，只查询。

只有日期在可预约列表中、且场次条件满足时，才标为可预约。营销日历中的活动标题不能替代门店预约结果。

## 本地运行与验证

在仓库根目录执行：

```powershell
python .workbuddy/skills/mcd-value-meal/scripts/selfcheck.py
python .workbuddy/skills/mcd-value-meal/scripts/plan_math.py rank --input .workbuddy/skills/mcd-value-meal/examples/group-6p-150.mock.json --limit 1
```

第一条运行现有的10项本地回归检查；第二条展示六人分餐的**模拟**方案。样例中的餐品组合、辣度和分配是测试夹具，券码已替换为不可兑换的模拟标识；即使部分单价源于历史查询，也不代表六人购物车已真实试算或当前门店仍有同价商品。

真实开发记录、历史查询结果与尚未验证项分别见：

- [workbuddy.md](workbuddy.md)：从真实本地会话日志提取的脱敏对话与 MCP 调用索引。
- [MCP_INTEGRATION.md](MCP_INTEGRATION.md)：Server、工具、调用流程、业务价值与验证边界。
- [详细验收记录](.workbuddy/skills/mcd-value-meal/references/acceptance-tests.md)：历史 WorkBuddy 记录；本轮未重新调用麦当劳接口。

## 规则和限制

- 先满足人数、份数、忌口，再筛预算；现金与积分独立展示。
- 只称「本次已试算候选中最低」，不保证全局最优；最多试算5套候选。
- 历史调用不支持单次多券，且曾出现带券后数量减少；以后端实际返回与当前工具定义为准。
- 没有明确辣度依据时标为未知；本地模拟中的 `not-spicy` 不能当作官方不辣证明。
- 领券、真实兑换和异常恢复仍有未验证部分；积分商品券链路尚未完成端到端验证。
- 不调用餐饮下单、取消订单、添加配送地址、活动预约或抽奖工具。账户操作只使用本人授权范围。
- 不提交真实 Token、券码、地址、手机号和原始日志；`.workbuddy/memory/` 等本地数据已加入忽略规则。

## 项目结构

```text
README.md                         项目介绍、安装、示例、目标用户
CONTEST_DECLARATION.md             官方参赛声明原文
MCP_INTEGRATION.md                 MCP 集成说明
mcp-config.example.json           远程 MCP 脱敏配置
workbuddy.md                      真实 WorkBuddy 脱敏开发上下文
SUBMISSION.md                     提交清单与报名 Issue 正文
scripts/export_workbuddy.py       本地日志脱敏导出工具
.workbuddy/skills/mcd-value-meal/  技能入口、参考流程、计算脚本与样例
```

## 声明与许可

本项目为独立开发的参赛作品，非麦当劳官方产品；价格、供应、权益和活动以官方实时结果为准。参见 [参赛声明](CONTEST_DECLARATION.md)。项目源代码遵循仓库 [LICENSE](LICENSE)；麦当劳服务、品牌和官方声明不因项目许可证而获得额外授权。

官方规则：[比赛仓库](https://github.com/M-China/mcd-developer-innovation-challenge)、[完整活动规则](https://github.com/M-China/mcd-developer-innovation-challenge/blob/main/activityGuidelines.md)。
