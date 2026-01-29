# Gemini Enterprise API 逆向文档

本文档记录了通过抓包分析 Gemini Enterprise (business.gemini.google) 得到的 API 结构。

## 基础信息

### API 基础 URL

```
https://biz-discoveryengine.googleapis.com/v1alpha/locations/global/
```

### 认证方式

使用 JWT Bearer Token 认证：

```
Authorization: Bearer <JWT_TOKEN>
```

Token 通过 `https://business.gemini.google/auth/getoxsrf?csesidx=<SESSION_ID>` 获取。

---

## 核心 API 端点

| 端点 | 方法 | 用途 |
|------|------|------|
| `widgetStreamAssist` | POST | 流式对话（普通/搜索/图片/视频） |
| `widgetCreateSession` | POST | 创建会话 |
| `widgetListSessions` | POST | 列出会话 |
| `widgetGetSession` | POST | 获取会话详情 |
| `widgetListTools` | POST | 获取可用工具列表 |
| `widgetRecommendQuestions` | POST | 获取推荐问题 |
| `widgetListAvailableAgentViews` | POST | 获取可用 Agent 视图 |

---

## 对话请求结构

### 1. 普通对话 / 工具调用（流式）

**端点**: `POST /widgetStreamAssist`

**请求体**:

```json
{
  "configId": "<企业配置ID>",
  "additionalParams": {"token": "-"},
  "streamAssistRequest": {
    "session": "collections/default_collection/engines/agentspace-engine/sessions/<SESSION_ID>",
    "query": {
      "parts": [{"text": "用户消息内容"}]
    },
    "filter": "",
    "fileIds": [],
    "answerGenerationMode": "NORMAL",
    "toolsSpec": {
      // 工具配置，见下方详细说明
    },
    "languageCode": "zh-CN",
    "userMetadata": {"timeZone": "Asia/Shanghai"},
    "assistSkippingMode": "REQUEST_ASSIST",
    "assistGenerationConfig": {
      "modelId": "<模型ID>"
    }
  }
}
```

### 2. Deep Research（异步）

**端点**: `POST /widgetStreamAssist`

**请求体**:

```json
{
  "configId": "<企业配置ID>",
  "additionalParams": {"token": "-"},
  "asyncAssistRequest": {
    "session": "collections/default_collection/engines/agentspace-engine/sessions/<SESSION_ID>",
    "query": {
      "parts": [{"text": "研究主题"}]
    },
    "filter": "",
    "fileIds": [],
    "answerGenerationMode": "AGENT",
    "agentsConfig": {
      "agent": "deep_research"
    },
    "agentsSpec": {
      "agentSpecs": [
        {"agentId": "deep_research"}
      ]
    },
    "toolsSpec": {
      "webGroundingSpec": {}
    },
    "languageCode": "zh-CN",
    "userMetadata": {"timeZone": "Asia/Shanghai"},
    "assistSkippingMode": "REQUEST_ASSIST",
    "assistGenerationConfig": {
      "modelId": "<模型ID>"
    }
  }
}
```

---

## 工具配置 (toolsSpec)

### 工具字段映射表

| 工具 | toolsSpec 配置 |
|------|---------------|
| **无工具（默认）** | `{"toolRegistry":"default_tool_registry"}` |
| **Google 搜索** | `{"toolRegistry":"default_tool_registry","webGroundingSpec":{}}` |
| **图片生成** | `{"toolRegistry":"default_tool_registry","imageGenerationSpec":{}}` |
| **视频生成** | `{"toolRegistry":"default_tool_registry","videoGenerationSpec":{}}` |

> **注意**：`toolRegistry` 是必需字段，所有请求都应包含。工具配置是**叠加**而非互斥的。

### 示例

#### 默认（无特定工具）

```json
"toolsSpec": {
  "toolRegistry": "default_tool_registry"
}
```

#### 开启 Google 搜索

```json
"toolsSpec": {
  "toolRegistry": "default_tool_registry",
  "webGroundingSpec": {}
}
```

#### 图片生成

```json
"toolsSpec": {
  "toolRegistry": "default_tool_registry",
  "imageGenerationSpec": {}
}
```

#### 视频生成

```json
"toolsSpec": {
  "toolRegistry": "default_tool_registry",
  "videoGenerationSpec": {}
}
```

---

## 模型 ID 映射

### 原生模型 ID

| 界面显示名称 | modelId |
|-------------|---------|
| Gemini 2.5 Flash | `gemini-2.5-flash` |
| Gemini 2.5 Pro | `gemini-2.5-pro` |
| Gemini 3 Flash (preview) | `gemini-3-flash-preview` |
| Gemini 3 Pro (预览) | `gemini-3-pro-preview` |

### 本项目扩展模型

本项目在原生模型基础上扩展了以下虚拟模型，通过后缀控制工具启用：

| 扩展模型名称 | 映射到原生 modelId | 工具配置 |
|-------------|-------------------|---------|
| `gemini-2.5-flash` | `gemini-2.5-flash` | 无工具 |
| `gemini-2.5-pro` | `gemini-2.5-pro` | 无工具 |
| `gemini-3-flash-preview` | `gemini-3-flash-preview` | 无工具 |
| `gemini-3-pro-preview` | `gemini-3-pro-preview` | 无工具 |
| `gemini-2.5-flash-search` | `gemini-2.5-flash` | Google 搜索 |
| `gemini-2.5-pro-search` | `gemini-2.5-pro` | Google 搜索 |
| `gemini-3-flash-preview-search` | `gemini-3-flash-preview` | Google 搜索 |
| `gemini-3-pro-preview-search` | `gemini-3-pro-preview` | Google 搜索 |
| `gemini-3-pro-image` | `gemini-3-pro-preview` | 图片生成 |
| `gemini-imagen` | 无（虚拟） | 图片生成 |
| `gemini-veo` | 无（虚拟） | 视频生成 |
| `gemini-auto` | 无（由服务端决定） | 无工具 |

> **使用说明**：
> - 基础模型（无后缀）：纯文本对话，不启用任何工具
> - `-search` 后缀：启用 Google 搜索（webGroundingSpec）
> - `gemini-3-pro-image`：专用图片生成模型
> - `gemini-imagen` / `gemini-veo`：纯图片/视频生成虚拟模型

---

## 请求类型对比

| 特性 | 普通对话 | Deep Research |
|------|---------|---------------|
| 请求字段 | `streamAssistRequest` | `asyncAssistRequest` |
| 生成模式 | `answerGenerationMode: "NORMAL"` | `answerGenerationMode: "AGENT"` |
| Agent 配置 | 无 | `agentsConfig`, `agentsSpec` |
| 响应类型 | 流式 JSON 数组 | 返回异步操作 ID |

---

## 响应格式

### 流式响应（普通对话）

响应为 JSON 数组，每个元素包含增量内容：

```json
[
  {
    "uToken": "<token>",
    "streamAssistResponse": {
      "answer": {
        "state": "IN_PROGRESS",
        "replies": [
          {
            "groundedContent": {
              "content": {
                "role": "model",
                "text": "思考中...",
                "thought": true
              }
            }
          }
        ],
        "adkAuthor": "root_agent"
      },
      "sessionInfo": {},
      "assistToken": "<assist_token>"
    }
  },
  {
    "streamAssistResponse": {
      "answer": {
        "state": "SUCCEEDED",
        "replies": [...]
      },
      "sessionInfo": {
        "session": "<session_path>",
        "queryId": "<query_id>",
        "turnId": "<turn_id>"
      }
    }
  }
]
```

### 响应字段说明

| 字段 | 说明 |
|------|------|
| `state` | 状态：`IN_PROGRESS`（进行中）、`SUCCEEDED`（完成） |
| `thought: true` | 表示这是模型的思考过程，非最终回复 |
| `role: "model"` | 表示这是模型的回复 |
| `text` | 回复文本内容 |

### 异步响应（Deep Research）

```json
[
  {
    "asyncAssistOperation": "projects/<PROJECT_ID>/locations/global/collections/default_collection/engines/agentspace-engine/sessions/<SESSION_ID>/operations/<OPERATION_ID>"
  }
]
```

需要通过操作 ID 轮询获取结果。

---

## 关于非流式请求

### 结论：目前未发现官方非流式端点

通过抓包分析，Gemini Enterprise 的所有对话请求都使用 `widgetStreamAssist` 端点，返回流式 JSON 数组。

### 可能的替代方案

1. **客户端缓冲**：接收完整流式响应后，拼接所有 `text` 字段
2. **等待 `state: "SUCCEEDED"`**：当响应状态变为 `SUCCEEDED` 时，表示回复完成
3. **使用 `asyncAssistRequest`**：Deep Research 模式返回操作 ID，可轮询获取完整结果

### 流式响应处理示例

```python
import json

def parse_stream_response(response_text: str) -> str:
    """解析流式响应，提取完整回复"""
    chunks = json.loads(response_text)

    full_text = ""
    for chunk in chunks:
        resp = chunk.get("streamAssistResponse", {})
        answer = resp.get("answer", {})

        for reply in answer.get("replies", []):
            content = reply.get("groundedContent", {}).get("content", {})
            # 跳过思考过程
            if content.get("thought"):
                continue
            text = content.get("text", "")
            if text:
                full_text += text

    return full_text
```

---

## 必要的请求头

```http
POST /v1alpha/locations/global/widgetStreamAssist HTTP/2
Host: biz-discoveryengine.googleapis.com
Authorization: Bearer <JWT_TOKEN>
Content-Type: application/json
Origin: https://business.gemini.google
Referer: https://business.gemini.google/
X-Server-Timeout: 1800
```

---

## 会话管理

### 创建会话

**端点**: `POST /widgetCreateSession`

```json
{
  "configId": "<企业配置ID>",
  "additionalParams": {"token": "-"},
  "createSessionRequest": {}
}
```

### 列出会话

**端点**: `POST /widgetListSessions`

```json
{
  "configId": "<企业配置ID>",
  "additionalParams": {"token": "-"},
  "listSessionsRequest": {}
}
```

---

## 错误处理

### 429 限流错误

```json
{
  "error": {
    "code": 429,
    "message": "Resource has been exhausted (e.g. check quota).",
    "status": "RESOURCE_EXHAUSTED",
    "details": [
      {
        "@type": "type.googleapis.com/google.rpc.ErrorInfo",
        "reason": "LLM_OVERLOADED",
        "domain": "discoveryengine.googleapis.com"
      }
    ]
  }
}
```

---

## 完整请求示例

### 普通对话（无工具）

```bash
curl -X POST 'https://biz-discoveryengine.googleapis.com/v1alpha/locations/global/widgetStreamAssist' \
  -H 'Authorization: Bearer <JWT_TOKEN>' \
  -H 'Content-Type: application/json' \
  -H 'Origin: https://business.gemini.google' \
  -H 'Referer: https://business.gemini.google/' \
  -d '{
    "configId": "<CONFIG_ID>",
    "additionalParams": {"token": "-"},
    "streamAssistRequest": {
      "session": "collections/default_collection/engines/agentspace-engine/sessions/<SESSION_ID>",
      "query": {
        "parts": [{"text": "你好"}]
      },
      "filter": "",
      "fileIds": [],
      "answerGenerationMode": "NORMAL",
      "toolsSpec": {
        "toolRegistry": "default_tool_registry"
      },
      "languageCode": "zh-CN",
      "userMetadata": {"timeZone": "Asia/Shanghai"},
      "assistSkippingMode": "REQUEST_ASSIST",
      "assistGenerationConfig": {
        "modelId": "gemini-2.5-pro"
      }
    }
  }'
```

### 普通对话（带 Google 搜索）

```bash
curl -X POST 'https://biz-discoveryengine.googleapis.com/v1alpha/locations/global/widgetStreamAssist' \
  -H 'Authorization: Bearer <JWT_TOKEN>' \
  -H 'Content-Type: application/json' \
  -H 'Origin: https://business.gemini.google' \
  -H 'Referer: https://business.gemini.google/' \
  -d '{
    "configId": "<CONFIG_ID>",
    "additionalParams": {"token": "-"},
    "streamAssistRequest": {
      "session": "collections/default_collection/engines/agentspace-engine/sessions/<SESSION_ID>",
      "query": {
        "parts": [{"text": "今天的新闻"}]
      },
      "filter": "",
      "fileIds": [],
      "answerGenerationMode": "NORMAL",
      "toolsSpec": {
        "toolRegistry": "default_tool_registry",
        "webGroundingSpec": {}
      },
      "languageCode": "zh-CN",
      "userMetadata": {"timeZone": "Asia/Shanghai"},
      "assistSkippingMode": "REQUEST_ASSIST",
      "assistGenerationConfig": {
        "modelId": "gemini-3-flash-preview"
      }
    }
  }'
```

### 图片生成

```bash
curl -X POST 'https://biz-discoveryengine.googleapis.com/v1alpha/locations/global/widgetStreamAssist' \
  -H 'Authorization: Bearer <JWT_TOKEN>' \
  -H 'Content-Type: application/json' \
  -H 'Origin: https://business.gemini.google' \
  -H 'Referer: https://business.gemini.google/' \
  -d '{
    "configId": "<CONFIG_ID>",
    "additionalParams": {"token": "-"},
    "streamAssistRequest": {
      "session": "collections/default_collection/engines/agentspace-engine/sessions/<SESSION_ID>",
      "query": {
        "parts": [{"text": "画一只可爱的猫咪"}]
      },
      "filter": "",
      "fileIds": [],
      "answerGenerationMode": "NORMAL",
      "toolsSpec": {
        "toolRegistry": "default_tool_registry",
        "imageGenerationSpec": {}
      },
      "languageCode": "zh-CN",
      "userMetadata": {"timeZone": "Asia/Shanghai"},
      "assistSkippingMode": "REQUEST_ASSIST",
      "assistGenerationConfig": {
        "modelId": "gemini-3-pro-preview"
      }
    }
  }'
```

### 视频生成

```bash
curl -X POST 'https://biz-discoveryengine.googleapis.com/v1alpha/locations/global/widgetStreamAssist' \
  -H 'Authorization: Bearer <JWT_TOKEN>' \
  -H 'Content-Type: application/json' \
  -H 'Origin: https://business.gemini.google' \
  -H 'Referer: https://business.gemini.google/' \
  -d '{
    "configId": "<CONFIG_ID>",
    "additionalParams": {"token": "-"},
    "streamAssistRequest": {
      "session": "collections/default_collection/engines/agentspace-engine/sessions/<SESSION_ID>",
      "query": {
        "parts": [{"text": "生成一段日落的视频"}]
      },
      "filter": "",
      "fileIds": [],
      "answerGenerationMode": "NORMAL",
      "toolsSpec": {
        "toolRegistry": "default_tool_registry",
        "videoGenerationSpec": {}
      },
      "languageCode": "zh-CN",
      "userMetadata": {"timeZone": "Asia/Shanghai"},
      "assistSkippingMode": "REQUEST_ASSIST",
      "assistGenerationConfig": {
        "modelId": "gemini-3-pro-preview"
      }
    }
  }'
```

### Deep Research

```bash
curl -X POST 'https://biz-discoveryengine.googleapis.com/v1alpha/locations/global/widgetStreamAssist' \
  -H 'Authorization: Bearer <JWT_TOKEN>' \
  -H 'Content-Type: application/json' \
  -H 'Origin: https://business.gemini.google' \
  -H 'Referer: https://business.gemini.google/' \
  -d '{
    "configId": "<CONFIG_ID>",
    "additionalParams": {"token": "-"},
    "asyncAssistRequest": {
      "session": "collections/default_collection/engines/agentspace-engine/sessions/<SESSION_ID>",
      "query": {
        "parts": [{"text": "研究 Gemini 的起源"}]
      },
      "filter": "",
      "fileIds": [],
      "answerGenerationMode": "AGENT",
      "agentsConfig": {
        "agent": "deep_research"
      },
      "agentsSpec": {
        "agentSpecs": [{"agentId": "deep_research"}]
      },
      "toolsSpec": {
        "webGroundingSpec": {}
      },
      "languageCode": "zh-CN",
      "userMetadata": {"timeZone": "Asia/Shanghai"},
      "assistSkippingMode": "REQUEST_ASSIST",
      "assistGenerationConfig": {
        "modelId": "gemini-3-pro-preview"
      }
    }
  }'
```

---

## 注意事项

1. **Token 有效期**：JWT Token 有效期约 5 分钟，需要定期刷新
2. **会话管理**：每次对话需要先创建或获取有效的 session ID
3. **工具配置**：`toolRegistry` 是必需字段；工具配置是叠加的，可同时启用多个
4. **流式处理**：所有对话响应都是流式的，需要正确处理 JSON 数组格式
5. **限流**：频繁请求可能触发 429 错误，需要实现重试机制
6. **模型后缀**：本项目使用 `-search` 后缀控制搜索工具的启用

---

## 更新日志

- **2026-01-29**: 更新模型映射，新增 `-search` 后缀模型和 `gemini-3-pro-image`；修正工具配置说明
- **2026-01-29**: 初始版本，通过抓包分析完成
