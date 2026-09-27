# 加密市场自托管改造：代码审阅记录

审阅基线：`08b93dc2`。对仓库目录、入口、依赖和工作流进行了全仓盘点，对与本次迁移有关的数据、算法、Agent、Web、持久化及部署链路做了代码追踪。这是迁移审阅，不是对全部历史代码逐行无缺陷的保证，也不构成策略收益验证。

## 主要发现与处理

| 范围 | 现有代码事实 | 本次处理 |
| --- | --- | --- |
| Python 行情 | `integrations/data_source.py` 依次尝试 TickFlow / Tushare / AKShare / BaoStock / EFinance；并非所有入口只支持收费源 | 加密链路使用独立 CCXT 公开 API，不经过股票供应商回退 |
| Web 行情 | `web/packages/shared/src/agent-market.ts` 只接受 CN/HK/US 股票代码，部分财务能力直接要求 TickFlow Key | 自托管入口明确传递交易所、spot/swap 和 CCXT 交易对，不把 BTC 误识别成美股 |
| 云端 Web | React 主入口有 Supabase 登录，Worker 包含会员、模型、工具、远程控制、队列等云服务契约 | 专用自托管构建入口；FastAPI 同源提供静态 UI 和 API，SQLite 本地历史，单用户口令 |
| 原本地 Dashboard | `cli/dashboard.py` 是管理面板，Host/Origin 限定本机；不是可直接发布到服务器的完整聊天后端 | 保留原边界；自托管服务具有自己的认证和有限研究 API |
| 威科夫引擎 | `core/wyckoff_engine.py` 混合股票板块、市值、交易日/价格制度和通用量价识别 | 仅复用 `wyckoff_structure.detect_structure_triggers`、`price_targets.calc_atr` 等纯量价计算，不调用 A 股筛选/订单逻辑 |
| 时间与价格 | 股票代码有交易日、两位价格及整数成交量的显示假设 | UTC 连续 K 线，保留小数价格/成交量，剔除未收盘 K 线，不伪造缺口 |
| 衍生品 | 原股票诊断没有永续结算币、资金费率、OI 概念 | 明确线性永续格式；展示原生 OI、资金费率周期及时间；反向合约明确拒绝 |
| Agent | CLI、MCP、Web 已有不同 runtime 和股票工具协议 | 自托管聊天使用有限 OpenAI-compatible 工具循环，仅暴露加密研究工具，支持 Ollama |
| 存储与密钥 | 原项目既有本地 SQLite，也有云端多用户配置 | 自托管独立目录/数据库；服务器环境保存模型 Key，前端只持有会话访问口令 |
| 部署 | 原主链路针对 CF Pages/Workers 和桌面发布，缺少独立 Docker 交付 | 锁文件构建、非 root 容器、Compose、启动脚本、健康检查、持久化及独立 Docker CI |
| 定时任务 | 上游有面向股票的 GitHub Actions 漏斗与推送流程 | Docker 不运行这些任务；本次未改股票策略、订单门槛或外部推送目标 |

## 保留的边界

- 自托管 Crypto 是此 fork 新的 Docker 产品入口；旧 CLI/MCP/桌面端和云股票 UI 仍是原来的股票产品，尚未全面迁移成加密界面。
- 仅支持现货与线性永续的研究；不交易，不提供账户余额/仓位同步，不支持币本位反向合约、交割合约和期权。
- 资金费率/OI 是当前公开快照。历史资金费率、OI 曲线、全市场扫描和加密市场回测不在当前交付内。
- 模型层复用了已存在的 OpenAI SDK 依赖；真实外部模型需要部署者提供配置。无 Key 的结构分析与模型工具循环分别验证。
- 原结构引擎不是经加密回测验证的盈利策略。没有调参以制造结果，也没有把股票回测结果当作加密结论。
- 上游源码含 AGPL 文件和部分版权头的额外文字；本次保留原文与来源，没有重新授权或删除署名。
- 仓库没有 `wiki_repo_new/` 独立 checkout；当前部署契约更新到 README、GLOSSARY、架构文档和本文。未声称已同步不存在的 wiki checkout。

## 验证方式

`tests/selfhost/` 覆盖 OHLCV 校验、时间/收盘语义、分页、缓存、swap 校验、衍生品缺失值、生产结构函数复用、认证、输入大小、工具白名单、模型工具循环和历史持久化。全仓回归与 CI 状态随 PR 提供；排队中的 CI 不等同通过。

生产入口用 Docker Compose 实际构建启动；人工网络 smoke 读取 OKX BTC 现货/永续公开行情，浏览器验收桌面与移动布局。真实行情测试不放入 pytest，以遵守仓库无网络测试契约。
