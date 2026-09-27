# 自托管加密货币研究工作台

本 fork 的 Docker 默认入口是加密货币 Agent 聊天工作台。React UI、FastAPI、SQLite 在一个容器内运行；行情由开源 CCXT 适配 OKX、Binance、Bybit 的免费公开接口。不需要 TickFlow、Tushare、Supabase、Cloudflare、会员账户或交易所 API Key。

CCXT 是开源软件；行情由交易所提供，属于免费公开 API，并不意味着行情数据本身采用开源许可证。接口有地区限制、速率限制和维护窗口，失败时切换界面中的交易所。系统不会悄悄替换交易所、混合不同市场的成交量或回退到收费平台。

## 一键部署

要求 Docker Engine/Desktop、Compose **v2.24+**（使用可选 env_file）、可访问镜像仓库及交易所的网络。首次构建需下载 Python/Node 依赖，建议预留数 GB 磁盘；本地大模型另需相应内存/显存。

```bash
git clone https://github.com/GloveBear666/WyckoffTradingAgent.git
cd WyckoffTradingAgent
bash scripts/deploy-selfhost.sh
```

打开 <http://localhost:8000>。首次启动自动生成访问口令，读取后填到登录页：

```bash
docker compose exec wyckoff cat /data/access-token
```

也可以直接运行 `docker compose up --build -d --wait`，无需任何配置即可使用结构分析、K 线图和历史研究。`scripts/deploy-selfhost.sh` 会从示例创建 `.env.selfhost`，已有配置不会被覆盖。

UI 的研究工具集中在同一个聊天工作台：选择交易所、现货/线性永续、交易对、周期，点击“运行结构分析”。未配置模型时也能工作。免费行情不包含模型 API 费用；模型可以接入你自己的服务，或使用本地 Ollama。

## 模型配置

编辑 `.env.selfhost`（不要提交到 GitHub）：

```dotenv
LLM_BASE_URL=https://your-provider.example/v1
LLM_MODEL=your-tool-capable-model
LLM_API_KEY=your-provider-key
```

服务需支持 OpenAI Chat Completions 和 function/tool calling。服务端保存密钥，浏览器无法读取。配置仅接受服务器环境变量；用户对话不能指定模型代理地址。API Key 和模型名必须匹配服务商；本仓库不捆绑任何付费订阅。

更改配置后：

```bash
docker compose up -d
```

AI 对话会先读取当前选择的行情，再通过只读 `analyze_crypto` 工具按问题补充其他交易对。每次最多 4 轮、每轮最多 3 个工具请求，单次模型超时 90 秒。没有任意代码执行、文件工具、交易密钥或下单工具。对话文本保留在当前浏览器页面内存；**研究报告**保存在服务器。刷新页面后可从近期研究恢复报告。

### 本地 Ollama

在宿主机安装并运行 Ollama，先下载支持工具调用的模型，例如 `ollama pull qwen3:8b`。然后配置：

```dotenv
LLM_BASE_URL=http://host.docker.internal:11434/v1
LLM_MODEL=qwen3:8b
LLM_API_KEY=ollama
```

Compose 已配置 host-gateway，Linux 也能解析 `host.docker.internal`。Ollama 必须监听容器可到达的宿主机地址；若只监听 127.0.0.1，可按 Ollama 文档设置 `OLLAMA_HOST=0.0.0.0:11434`，并用主机防火墙限制该端口只允许本机/Docker 网络访问。模型名称是示例，按实际硬件选择；不会在部署时自动下载模型。

## 市场和计算口径

| 功能 | 当前支持 |
| --- | --- |
| 交易所 | OKX（默认）、Binance、Bybit |
| 现货 | `BTC/USDT`、`ETH/USDT` 等，具体以所选交易所为准 |
| 永续 | 线性永续，如 `BTC/USDT:USDT`；选永续后输入 `BTC/USDT` 会自动补齐结算币 |
| 暂不支持 | 币本位反向合约、交割合约、期权、账户与订单 |
| K 线 | 15m、1h、4h、1d；UI 可选 120/320/500 根，API 为 100–500 |
| 结构 | 复用 `core/wyckoff_structure.py` 的交易区间、Spring/SOS/LPS/EVR 与阶段识别 |
| 指标 | MA20/50/200、ATR14，窗口单位为所选周期的 **K 线根数** |
| 永续补充 | 当前资金费率、结算周期（交易所提供时）、未平仓量及时间戳 |

所有 K 线时间为 UTC **开盘时间**。正在形成的 K 线不参与计算。排序去重后检查 OHLC 合理性、非有限数字、连续性和新鲜度；不足 100 根、缺口或过期时返回明确错误。不会填造缺失 K 线；MA200 在不足 200 根时为 null。近期上市/不活跃交易对可能因此无法分析。

成交量保留 CCXT 返回的交易所原生数量，只用于同一个交易对内部比较；合约大小记录在元数据中，不能把现货数量、合约张数或不同交易所的量直接相加。OI 数量/名义价值按 CCXT 字段返回，不把“没有数据”写成 0。资金费率展示为每结算周期百分比，不自动年化、不假定每个市场都为 8 小时；资金费率时间可能是即将结算的时间。OI 是抓取时点的快照，不是历史时间序列。

结构引擎参数沿用上游，**尚未经过加密市场回测**。这是价格结构观察，不继承股票回测收益、A 股市值/ST/涨跌停门槛、交易日历、仓位与买卖闸门。没有识别出区间时会明确显示，不硬判为吸筹或派发。

实例内 CCXT 连接复用、限流开启；相同请求缓存 30 秒，最多 64 项。不会在数据源故障时返回过期缓存。每次最多 8 页取数，避免无限分页。市场列表加载后在进程内复用，新上市交易对必要时重启服务刷新。

## 服务部署和数据

默认只向宿主机 127.0.0.1:8000 发布端口。远程服务器可用 SSH 隧道直接访问：

```bash
ssh -L 8000:127.0.0.1:8000 user@your-server
```

然后在自己的电脑打开 <http://localhost:8000>。若需域名访问，在主机使用 Nginx/Caddy 将 HTTPS 反向代理至 `127.0.0.1:8000`，代理读取超时建议 600 秒。需要局域网直接访问时：

```bash
BIND_ADDRESS=0.0.0.0 WEB_PORT=8000 docker compose up -d
```

`BIND_ADDRESS` / `WEB_PORT` 是 Compose 插值变量，放在命令环境或 Compose 的 `.env`，不是 `.env.selfhost`；后者用于容器应用配置。公网访问应通过 HTTPS，避免口令和报告明文传输。

这是**个人单用户**部署：同一个访问口令共享报告历史，不是多租户服务。口令默认持久化到命名卷 `/data/access-token`；自定义 `WEB_TOKEN` 至少 32 字符。换口令时设置该变量并重建容器。浏览器口令仅放在当前标签页的 sessionStorage，退出时清除；容器不把口令或模型 Key 写入日志。

SQLite 数据在命名卷 `/data/reports.sqlite3`；保留最近 100 份报告，界面读取最近 30 份。应用默认无股票调度任务、飞书推送或云同步。原仓库的 CLI/桌面端/云端股票工作流继续保留，**不会因启动 Docker 自动运行**。

```bash
# 查看服务、日志，升级，停止（保留卷）
docker compose ps
docker compose logs --tail 100
git pull --ff-only
docker compose up --build -d --wait
docker compose down
```

备份可在停止服务后复制 SQLite 文件；也可使用 SQLite 在线 backup API。不要把数据库或口令提交进 Git。`docker compose down -v` 会删除数据和自动生成的口令，只应在确认清空时使用。

容器以 UID 10001 运行、只读根文件系统、独立可写数据卷、去除 Linux capabilities，带健康检查、日志轮转、请求体上限与并发限制。Python 依赖读取 `uv.lock`，前端依赖读取 `web/pnpm-lock.yaml`；新依赖锁定在 `selfhost` extra。

## 开发和验证

```bash
uv sync --extra dev --extra mcp --extra selfhost
.venv/bin/python -m pytest tests/selfhost -q
.venv/bin/ruff check .
.venv/bin/python scripts/quality_gate.py --ci
cd web
pnpm install --frozen-lockfile
pnpm -r exec tsc --noEmit
pnpm --filter @wyckoff/web exec vite build --config vite.selfhost.config.ts
cd ..
.venv/bin/uvicorn selfhost.server:app --host 127.0.0.1 --port 8000
```

本地自动口令位于 `.wyckoff/selfhost/access-token`。开发时可分别运行 API 与 `pnpm --filter @wyckoff/web exec vite --config vite.selfhost.config.ts`，后者将 `/api` 代理到本机 8000 端口。

GitHub `CI` 覆盖新旧 Python 测试和 Web 检查；`Self-hosted Docker` 构建镜像、实际启动、验证未登录拒绝访问、认证配置读取、重启持久化，并上传容器日志。测试使用假行情，不依赖交易所网络。手动离线容器 smoke：

```bash
docker compose exec wyckoff python scripts/smoke_selfhost.py
```

协议参考：[CCXT Manual](https://docs.ccxt.com/docs/manual)、[FastAPI Docker](https://fastapi.tiangolo.com/deployment/docker/)、[Ollama OpenAI compatibility](https://docs.ollama.com/api/openai-compatibility)。
