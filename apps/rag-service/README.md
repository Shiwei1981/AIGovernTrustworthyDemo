# rag-service

Domain 4 RAG Governance Service — 当前批准方案为 **Azure Web App + 轻量级代码式 RAG**。

## 架构

```text
APIM /rag
    -> Azure Web App (AIGovernTrustworthyRAGApp)
    -> in-process chunking / lexical retrieval
    -> model call (AIGovernTrustworthyDemoNativeModelGPT5.4mini)
    -> shared_observability.log_llm_call() -> Blob archive
```

- 运行形态：**Azure Web App**，部署到现有 App Service Plan `AIGovernDemoASP`
- 运行身份：`L4_RAG_SERVICE_CLIENT_ID`
- 检索层：默认采用**代码切块 + 进程内轻量级检索**，不依赖额外检索云资源或平台侧托管检索能力
- 知识库主题：AI Governance 行业标准 PDF
- 日志：LLM input / output / error -> `aigoverntrustworthysa/ai-invocation-archive`

## 当前设计原则

1. 优先减少依赖项，不默认引入 embedding、外部 vector DB 或额外检索云资源
2. PDF 文件放在 `knowledge-base/`，由应用启动时加载并构建内存索引
3. APIM `/rag` 仍是统一入口，后端改为 RAG Web App `/responses`
4. 如后续需要 embedding、Azure AI Search 或其他新增资源，先暂停并征得用户同意

## 目录说明

```text
apps/rag-service/
  app.py                # Azure Web App 主服务与 /responses API
  knowledge-base/       # PDF 知识库（*.pdf 已 gitignore）
  scripts/              # Web App 部署/配置辅助文件
```

`apps/rag-service` 目录只保留当前批准的 **Azure Web App** 运行路径；已废弃实现不应继续出现在此目录。
