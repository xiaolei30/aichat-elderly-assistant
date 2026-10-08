# 银龄守望后端服务

面向老年居家语音助手「银龄守望」的 Python 后端，提供语音对话、天气播报、健康监测、紧急呼救、子女号码与每日用药计划等能力，并直接托管前端页面。

## 功能

- **前端托管**：后端直接托管 `index.html`，浏览器访问 `http://localhost:8000` 即可使用（语音识别需要 localhost 安全上下文）。
- **AI 对话**：接入 DeepSeek 大模型，未配置密钥或请求失败时自动降级为本地规则回复。
- **天气播报**：联网自动定位当前位置（IP 定位 + open-meteo），失败回退默认城市 + 季节估算。
- **今日播报**：动态拼装天气 + 健康建议 + 用药情况 + 身体状况。
- **健康监测**：生成血压/心率/血糖并做异常检测（演示用模拟数据，可替换真实设备）。
- **紧急呼救**：识别「救命 / 摔倒了 / 喘不过气」等关键词，返回 `risk_alert` 触发告警。
- **打电话**：识别「打电话给女儿/儿子」等，返回已存联系人的号码供前端唤起拨号。
- **子女号码 / 用药计划**：增删查，持久化到本地 JSON 文件。

## 目录结构

```
backend/
├── main.py          # FastAPI 入口 + 路由 + 前端托管
├── config.py        # 配置读取（环境变量 / .env）
├── llm.py           # DeepSeek 客户端 + 本地兜底
├── intents.py       # 意图识别（呼救 / 打电话 / 用药提醒）
├── weather.py       # 天气获取（IP 定位 + open-meteo）
├── health.py        # 健康数据生成与异常检测
├── store.py         # JSON 文件存储
├── requirements.txt
└── .env.example
```

## 安装与运行

```bash
cd backend
python -m venv venv
# Windows:
venv\Scripts\activate
# macOS / Linux:
# source venv/bin/activate

pip install -r requirements.txt

# 配置密钥（可选，不配也能跑）
# 方式一：复制 .env.example 为 .env 并填入 DEEPSEEK_API_KEY
# 方式二：设置环境变量 set DEEPSEEK_API_KEY=sk-xxx

python main.py
```

启动后**用 Chrome 或 Edge 浏览器**访问：

```
http://localhost:8000
```

> 不要直接双击 `index.html`（`file://`）——语音识别需要 localhost 安全上下文，且后端接口访问更稳定。语音识别仅支持 Chrome / Edge（Firefox 不支持）。

## 接口说明

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/` | 托管前端页面 |
| GET | `/api/health` | 健康检查 |
| POST | `/api/chat` | 对话入口（呼救/打电话/用药提醒/闲聊） |
| GET | `/api/weather` | 当前位置天气 |
| GET | `/api/health-data` | 健康数据与异常标记 |
| GET | `/api/report` | 今日播报文本 |
| GET/POST | `/api/contacts` | 子女号码查询/新增 |
| DELETE | `/api/contacts/{id}` | 删除子女号码 |
| GET/POST | `/api/medplan` | 用药计划查询/整体保存 |
| GET | `/api/medplan/due` | 当前时刻到点用药 |
| GET | `/api/reminders` | 查询用药提醒 |
| POST | `/api/reminders` | 新增用药提醒 |
| DELETE | `/api/reminders/{id}` | 删除用药提醒 |

## 说明

- 运行时数据保存在 `backend/` 下的 `reminders.json`、`contacts.json`、`medplan.json`，重启不丢失。
- 会话记忆为内存态，进程重启清空。
- 健康数据当前为演示用模拟生成，接入真实血压计/手环后替换 `health.py` 的 `get_health()` 即可。
