# Cross-App Architecture Charter

本文件用于编写跨应用程序开发宪章。所有应用、共享包、基础设施脚本和设计文档都应遵守这里定义的统一规则。

## 1. 宪章目标

在此说明本宪章要解决的问题、适用范围，以及哪些团队或目录必须遵守。
本项目由多个应用系统组成，每一个应用系统都需要遵循本规则。

## 2. 来自作者的宪章要求 - 需要遵守的最高优先级，此段内容禁止AI修改，只能人工修改。
1. 本项目是个POC，不考虑生产应用所必须的非功能性需求。
2. 任何涉及到提供UI的用户操作系统的必要流程：
    a) 首先要求用户登录，登陆后用户的 Entra ID 用户账户 显示在 登录按钮下，登录按钮变为 切换用户按钮（直接弹账号选择）
    b) 登陆后，显示页面内容。    
    c) 页面打开后采用异步加载模式，逐步填充页面中的数字，列表，和图形。（页面打开后，逐个调用API加载数据）。
    d) 系统无管理员后台维护功能。
    e) UI 仅使用英文。
3. 所有应用，不开发缓存/中间存储能力，所有需要调用API接口的需求，直接调用。
4. 任何应用，如果有前端，则前端使用 HTML5，Bootstrap，原生JS。
    如果有后端，则后端使用：FastAPI。
    同一应用程序的 前端后端，包装至同一个 docker image。前端直接托管静态 HTML/CSS/JS。
    后端使用HTTP的无状态的服务，使用Python，FastAPI开发，无需考虑高可靠，和性能要求。    
5. 应用开发调用 API 时，不采用任何重试，或多链路。一旦调用失败，直接终止后续步骤，在界面，API返回，控制台等任何地方，返回错误信息，以供后续分析。
6. 如果涉及到数据库，则系统涉及到的数据库都是 Azure SQL Database，认证方式是 Entra ID Only，认证方式是基于 Entra ID 上的 Enterprise Application 的 Application(client) ID 和 client secret。
7. 应用程序基于 Entra ID 的 Enterprise Application 账户运行，用户使用Entra ID的用户账户登录，登录后，用户的账户不透传到数据层。应用程序使用 Client ID 及 App Secret访问数据层或AI服务。Redirect 要配置测试环境的地址，以及生产环境的地址。
8. 测试直接在开发使用的 Linux 服务器上直接完成，开发服务器上直接安装必要的环境，测试时，应用服务都直接使用 bash 命令在开发机Linux服务器上开启服务，无需发布到部署环境。测试采用 HTTP。
9. 开发代码的时候，对于环境变量的命名，有限参考并使用 .env.local.L4 文件中已有的变量。
10. 每个代码文件顶端提供简单的注释
11. 根据需要开发的脚本文件，也在顶端提供注释
12. 生产环境到 Azure Web App 后通过平台提供的 HTTPS 对外提供服务。使用平台证书，不适用 azure keyvault
13. 环境变量使用 Azure Web App 的配置实现环境变量的注入，帮我生成基于 Linux 的 Azure CLI 脚本来配置 Azure Web App 的环境变量设置。
14. 所有运行期需要的变量使用 环境变量传入。
15. 不开发伪码或者占位符，直接开发完整代码。
16. 在开发的系统中，所有对于 AI 的调用，都必须被日志，AI 调用的所有 input, output 都必须有记录。设计需要设计统一的记录位置。
17. 本项目里所有可以引入 APIM 后端的 API 接口，都被要求接入 APIM， 不能有例外，所有接入 APIM 的 API 接口，必须通过 APIM 来调用，不能有例外。
18. 应用程序对于 blob 的访问，使用 SPN， Entra ID认证。
19. 每一个应用程序，都应该在代码层默认开启与 Azure App Insights 的集成，其使用的 Azure App Insights 链接字，以及 OTEL_SERVICE_NAME 都可以在 .env.local.L4 配置文件找到，这里需要注意的是，每个应用的 OTEL_SERVICE_NAME 名字都是不同的。
20. 每一个使用 LLM 接口的应用，都必须套用 shared-observability 组件，对于每一次的 LLM 接口调用进行log记录，不论调用结果是成功还是失败。
21. 本项目创建的所有资源，都创建到 AIGovernTrustworthyRG 资源组。

## 3. shared-observability 使用要求

本节是对第 2 章第 20 条的补充说明，所有使用 LLM 接口的应用必须遵守。

### 3.1 强制要求

- 应用程序对每一次实际 LLM 调用（无论成功还是失败）都必须调用 `log_llm_call()`。
- 不得跳过调用，不得只在成功时记录。
- `log_llm_call()` 必须在 LLM 调用返回之后、应用程序继续后续逻辑之前立即调用。
- 如果 `log_llm_call()` 抛出 `BlobWriteError` 或 `TelemetryEmitError`，应用程序应按第 2 章第 5 条处理（直接终止后续步骤并返回错误）。

### 3.2 调用方式

**安装**：应用程序将 `shared-observability` 作为本地包依赖引入。

**初始化**：应用程序启动时从环境变量加载配置，并使用自己的运行时 SPN 构造 credential：

```python
from azure.identity import ClientSecretCredential
from shared_observability import load_settings_from_env

observability_settings = load_settings_from_env()
observability_credential = ClientSecretCredential(
    tenant_id=os.environ["AZ_RUNTIME_TENANT_ID"],
    client_id=os.environ["AZ_RUNTIME_CLIENT_ID"],
    client_secret=os.environ["AZ_RUNTIME_CLIENT_SECRET"],
)
```

**每次 LLM 调用**：

```python
from shared_observability import log_llm_call, TargetType

# 调用前固定完整输入
llm_input = { ... }

# 发起实际 LLM 调用
try:
    llm_output = call_llm(llm_input)
    log_llm_call(
        settings=observability_settings,
        credential=observability_credential,
        service_name="<应用名>",
        target_type=TargetType.<目标类型>,
        target_id="<模型或Agent ID>",
        target_endpoint="<调用端点URL>",
        llm_input=llm_input,
        llm_output=llm_output,
        response_id=llm_output.get("id"),
        model_name="<模型名>",
        model_version="<版本>",
    )
except Exception as e:
    log_llm_call(
        settings=observability_settings,
        credential=observability_credential,
        service_name="<应用名>",
        target_type=TargetType.<目标类型>,
        target_id="<模型或Agent ID>",
        target_endpoint="<调用端点URL>",
        llm_input=llm_input,
        error={"type": type(e).__name__, "message": str(e)},
    )
    raise
```

### 3.3 Credential 来源

- shared-observability 组件本身不拥有 Azure 身份，不从环境变量自行读取 SPN。
- Credential 必须由调用方应用程序创建并传入。
- 每个应用程序使用自己专属的运行时 SPN，不得使用 deploy SPN（`AZ_DEPLOY_*`）。
- 运行时 SPN 需具备对 Blob 容器 `ai-invocation-archive` 的 `Storage Blob Data Contributor` 权限，以及对 App Insights 的 `Monitoring Metrics Publisher` 权限（可通过 `aigoverndemogroup` 继承）。

### 3.4 所需环境变量

调用方应用程序需在 `.env.local.L4` 及 Azure Web App 配置中提供以下变量：

| 变量 | 用途 |
|---|---|
| `L4_OBSERVABILITY_BLOB_STORAGE_ACCOUNT_NAME` | Blob 存储账户名 |
| `L4_OBSERVABILITY_BLOB_CONTAINER` | Blob 容器名 |
| `L4_OBSERVABILITY_BLOB_PREFIX` | Blob 路径前缀 |
| `APPLICATIONINSIGHTS_CONNECTION_STRING` | App Insights 连接字符串 |
| `AZ_RUNTIME_TENANT_ID` / `AZ_RUNTIME_CLIENT_ID` / `AZ_RUNTIME_CLIENT_SECRET` | 应用运行时 SPN 凭据 |