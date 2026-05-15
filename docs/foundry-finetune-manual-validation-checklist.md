# Domain 4 · Foundry Fine-tune 手工验证题单（20 题）

本题单用于在 **Azure AI Foundry Playground** 中手工验证 `AIGovernTrustworthyDemoFineTuneModel` 是否体现了训练集中的 AI Governance 内容。

> 题目选择原则：优先选择**业务意义简单、表述清晰、非领域专家也容易判断对错**的例子。  
> 题面均直接取自训练集归档：`docs/finetune-qa-archive/aigoverntrustworthydemo-qa-5000.jsonl`

> 如果当前 Markdown 渲染器禁用了脚本，下面的“复制到剪切板”按钮可能不可用；此时可以直接复制题目代码块中的文本。

<script>
async function copyBlock(id, button) {
  const block = document.getElementById(id);
  if (!block) {
    return;
  }

  const text = block.textContent.trim();
  try {
    await navigator.clipboard.writeText(text);
  } catch (error) {
    const range = document.createRange();
    range.selectNodeContents(block);
    const selection = window.getSelection();
    selection.removeAllRanges();
    selection.addRange(range);
    document.execCommand("copy");
    selection.removeAllRanges();
  }

  if (button) {
    const original = button.textContent;
    button.textContent = "已复制";
    setTimeout(() => {
      button.textContent = original;
    }, 1200);
  }
}
</script>

## 推荐测试方式

1. 在 Foundry Playground 中选择 deployment：`AIGovernTrustworthyDemoFineTuneModel`
2. 将 `temperature` 设为 `0`
3. 先使用下面这条固定 system prompt
4. 每次只问 1 个题目，便于人工对比
5. 回答时优先看**关键词是否命中**，不要要求一字不差

### 固定 system prompt

<button type="button" onclick="copyBlock('system-prompt', this)">复制 system prompt</button>

<pre id="system-prompt">You are an AI governance expert specializing in AI governance frameworks and controls.</pre>

### 一次复制全部 20 题

<button type="button" onclick="copyBlock('all-prompts', this)">复制全部 20 题</button>

<details>
<summary>展开全部 20 题</summary>

<pre id="all-prompts">1. What is the full document title as shown on the page?
2. What framework name is included in the document title?
3. What version of the AI risk management framework is indicated in the source text?
4. What does “AI RMF” stand for in the provided page text?
5. What does MS-2.7-009 require regarding security measures?
6. What types of content provenance-related methods are mentioned in MS-2.7-005?
7. What does Action ID MS-2.8-001 ask an organization to compile?
8. What does Action ID MS-2.8-002 require to be documented?
9. What does Action ID MS-2.8-003 recommend using to enable content documentation?
10. What is the purpose of the tamper-proof history described in MS-2.8-003?
11. What additional control does MS-2.8-003 mention for tracking changes?
12. What is TEVV MEASURE 2.8 focused on?
13. What are examples of security threats listed under MS-2.7-001?
14. What are examples of input/output modalities mentioned in Annex XIII?
15. What is one example of how computation used for training may be indicated besides floating point operations?
16. Under what condition does Annex XIII presume high impact on the internal market?
17. What is the document title shown on the page?
18. What version information is shown for the OWASP PDF on this page?
19. Under what license is the document released?
20. What does the license allow you to do with the document?</pre>

</details>

---

## 01. NIST AI RMF 文档全名

<button type="button" onclick="copyBlock('prompt-01', this)">复制题目 01</button>

<pre id="prompt-01">What is the full document title as shown on the page?</pre>

- **为什么容易判断**：答案就是一个清晰的文档标题。
- **期望答案**：`NIST AI 100-1 Artificial Intelligence Risk Management Framework (AI RMF 1.0).`
- **人工通过标准**：回答里应同时出现 `NIST AI 100-1` 和 `AI RMF 1.0`。
- **训练集位置**：第 9 行

## 02. AI RMF 框架名称

<button type="button" onclick="copyBlock('prompt-02', this)">复制题目 02</button>

<pre id="prompt-02">What framework name is included in the document title?</pre>

- **为什么容易判断**：答案是标题中的框架名，不需要专业背景。
- **期望答案**：`Artificial Intelligence Risk Management Framework (AI RMF 1.0).`
- **人工通过标准**：回答里应出现 `Artificial Intelligence Risk Management Framework`。
- **训练集位置**：第 2 行

## 03. AI RMF 版本号

<button type="button" onclick="copyBlock('prompt-03', this)">复制题目 03</button>

<pre id="prompt-03">What version of the AI risk management framework is indicated in the source text?</pre>

- **为什么容易判断**：答案只有一个简单版本号。
- **期望答案**：`1.0.`
- **人工通过标准**：回答里应出现 `1.0`。
- **训练集位置**：第 3 行

## 04. AI RMF 缩写含义

<button type="button" onclick="copyBlock('prompt-04', this)">复制题目 04</button>

<pre id="prompt-04">What does “AI RMF” stand for in the provided page text?</pre>

- **为什么容易判断**：这是缩写释义题，答案很短。
- **期望答案**：`Artificial Intelligence Risk Management Framework.`
- **人工通过标准**：回答里应出现完整短语 `Artificial Intelligence Risk Management Framework`。
- **训练集位置**：第 4 行

## 05. 安全措施需要做到什么

<button type="button" onclick="copyBlock('prompt-05', this)">复制题目 05</button>

<pre id="prompt-05">What does MS-2.7-009 require regarding security measures?</pre>

- **为什么容易判断**：核心含义很直白，就是“定期检查安全措施是否仍然有效”。
- **期望答案**：`Regularly assess and verify that security measures remain effective and have not been compromised.`
- **人工通过标准**：回答里应覆盖 `regularly assess`、`verify`、`remain effective`。
- **训练集位置**：第 1200 行

## 06. 内容来源证明方法

<button type="button" onclick="copyBlock('prompt-06', this)">复制题目 06</button>

<pre id="prompt-06">What types of content provenance-related methods are mentioned in MS-2.7-005?</pre>

- **为什么容易判断**：答案是 3 个具体方法名。
- **期望答案**：`Watermarking, cryptographic signatures, and digital fingerprints.`
- **人工通过标准**：回答里至少应出现 `watermarking`、`cryptographic signatures`、`digital fingerprints`。
- **训练集位置**：第 1199 行

## 07. 组织需要汇总什么统计信息

<button type="button" onclick="copyBlock('prompt-07', this)">复制题目 07</button>

<pre id="prompt-07">What does Action ID MS-2.8-001 ask an organization to compile?</pre>

- **为什么容易判断**：答案是几类需要统计的事项。
- **期望答案**：`Statistics on actual policy violations, take-down requests, and intellectual property infringement for organizational GAI systems.`
- **人工通过标准**：回答里应出现 `policy violations`、`take-down requests`、`intellectual property infringement`。
- **训练集位置**：第 1203 行

## 08. 需要记录什么说明文档

<button type="button" onclick="copyBlock('prompt-08', this)">复制题目 08</button>

<pre id="prompt-08">What does Action ID MS-2.8-002 require to be documented?</pre>

- **为什么容易判断**：答案非常具体，就是“给标注员或红队员的说明”。
- **期望答案**：`The instructions given to data annotators or AI red-teamers.`
- **人工通过标准**：回答里应出现 `instructions` 以及 `annotators` 或 `red-teamers`。
- **训练集位置**：第 1206 行

## 09. 用什么来支持内容留痕

<button type="button" onclick="copyBlock('prompt-09', this)">复制题目 09</button>

<pre id="prompt-09">What does Action ID MS-2.8-003 recommend using to enable content documentation?</pre>

- **为什么容易判断**：答案是一个明确的方案名称。
- **期望答案**：`Digital content transparency solutions to document each instance where content is generated, modified, or shared.`
- **人工通过标准**：回答里应出现 `digital content transparency solutions` 和 `generated, modified, or shared`。
- **训练集位置**：第 1208 行

## 10. 为什么需要防篡改历史

<button type="button" onclick="copyBlock('prompt-10', this)">复制题目 10</button>

<pre id="prompt-10">What is the purpose of the tamper-proof history described in MS-2.8-003?</pre>

- **为什么容易判断**：这题直接问“目的”，很适合人工判断。
- **期望答案**：`To provide a tamper-proof history of the content, promote transparency, and enable traceability.`
- **人工通过标准**：回答里应覆盖 `tamper-proof history`、`transparency`、`traceability`。
- **训练集位置**：第 1209 行

## 11. 跟踪变更的额外控制

<button type="button" onclick="copyBlock('prompt-11', this)">复制题目 11</button>

<pre id="prompt-11">What additional control does MS-2.8-003 mention for tracking changes?</pre>

- **为什么容易判断**：答案是常见的工程概念“版本控制”。
- **期望答案**：`Robust version control systems can be applied to track changes across the AI lifecycle over time.`
- **人工通过标准**：回答里应出现 `version control systems`。
- **训练集位置**：第 1210 行

## 12. TEVV 2.8 在关注什么

<button type="button" onclick="copyBlock('prompt-12', this)">复制题目 12</button>

<pre id="prompt-12">What is TEVV MEASURE 2.8 focused on?</pre>

- **为什么容易判断**：虽然带编号，但核心含义是“透明度和问责风险”。
- **期望答案**：`Risks associated with transparency and accountability—identified in the MAP function—are examined and documented.`
- **人工通过标准**：回答里应出现 `transparency` 和 `accountability`。
- **训练集位置**：第 1202 行

## 13. 常见安全威胁有哪些

<button type="button" onclick="copyBlock('prompt-13', this)">复制题目 13</button>

<pre id="prompt-13">What are examples of security threats listed under MS-2.7-001?</pre>

- **为什么容易判断**：答案是一串容易识别的安全威胁名词。
- **期望答案**：`Backdoors, compromised dependencies, data breaches, eavesdropping, man-in-the-middle attacks, reverse engineering, autonomous agents, model theft or exposure of model weights, AI inference, bypass, and extraction.`
- **人工通过标准**：回答里至少应命中 3 个以上典型威胁，如 `backdoors`、`data breaches`、`man-in-the-middle`。
- **训练集位置**：第 1198 行

## 14. 模型输入输出模态例子

<button type="button" onclick="copyBlock('prompt-14', this)">复制题目 14</button>

<pre id="prompt-14">What are examples of input/output modalities mentioned in Annex XIII?</pre>

- **为什么容易判断**：答案是几个常见模型类型例子。
- **期望答案**：`Text-to-text (large language models), text-to-image, and multi-modality (criterion (d)).`
- **人工通过标准**：回答里应出现 `text-to-text`、`text-to-image`、`multi-modality`。
- **训练集位置**：第 3600 行

## 15. 除 FLOPs 外还能怎么表示训练计算量

<button type="button" onclick="copyBlock('prompt-15', this)">复制题目 15</button>

<pre id="prompt-15">What is one example of how computation used for training may be indicated besides floating point operations?</pre>

- **为什么容易判断**：答案是几个日常容易理解的指标：成本、时间、能耗。
- **期望答案**：`By a combination of other variables such as estimated cost of training, estimated time required for training, or estimated energy consumption for training (criterion (c)).`
- **人工通过标准**：回答里应出现 `cost`、`time` 或 `energy consumption`。
- **训练集位置**：第 3602 行

## 16. 什么时候会被视为对内部市场有高影响

<button type="button" onclick="copyBlock('prompt-16', this)">复制题目 16</button>

<pre id="prompt-16">Under what condition does Annex XIII presume high impact on the internal market?</pre>

- **为什么容易判断**：核心是一个明确阈值。
- **期望答案**：`When the model has been made available to at least 10,000 registered business users established in the Union (criterion (f)).`
- **人工通过标准**：回答里应出现 `10,000 registered business users`。
- **训练集位置**：第 3603 行

## 17. OWASP 文档标题

<button type="button" onclick="copyBlock('prompt-17', this)">复制题目 17</button>

<pre id="prompt-17">What is the document title shown on the page?</pre>

- **为什么容易判断**：答案就是标题本身。
- **期望答案**：`OWASP Top 10 for LLM Applications 2025 Version 2025.`
- **人工通过标准**：回答里应出现 `OWASP Top 10 for LLM Applications 2025`。
- **训练集位置**：第 3604 行

## 18. OWASP PDF 版本信息

<button type="button" onclick="copyBlock('prompt-18', this)">复制题目 18</button>

<pre id="prompt-18">What version information is shown for the OWASP PDF on this page?</pre>

- **为什么容易判断**：答案是一个明确版本串。
- **期望答案**：`OWASP PDF v4.2.0a 20241114-202703.`
- **人工通过标准**：回答里应出现 `v4.2.0a`。
- **训练集位置**：第 3605 行

## 19. 文档使用什么许可证

<button type="button" onclick="copyBlock('prompt-19', this)">复制题目 19</button>

<pre id="prompt-19">Under what license is the document released?</pre>

- **为什么容易判断**：答案是通用许可证名。
- **期望答案**：`It is licensed under Creative Commons, CC BY-SA 4.0.`
- **人工通过标准**：回答里应出现 `CC BY-SA 4.0`。
- **训练集位置**：第 3608 行

## 20. 许可证允许你做什么

<button type="button" onclick="copyBlock('prompt-20', this)">复制题目 20</button>

<pre id="prompt-20">What does the license allow you to do with the document?</pre>

- **为什么容易判断**：答案是日常可理解的“可分享、可改编”。
- **期望答案**：`You are free to Share (copy and redistribute), and Adapt (remix, transform, and build upon) the material in any medium or format for any purpose, even commercially.`
- **人工通过标准**：回答里应出现 `Share` 和 `Adapt`，或对应含义 `copy and redistribute` / `remix, transform, and build upon`。
- **训练集位置**：第 3609 行

---

## 建议的人工判定方式

1. **优先看关键词是否命中**，不要要求逐字逐句完全一致。
2. 如果模型回答更长，只要包含题目对应的核心信息，也可以算通过。
3. 如果同一题在连续 2 到 3 次提问中都能稳定命中预期关键词，说明 fine-tune 数据已被较稳定地学到。
4. 建议再拿同一题对比 `AIGovernTrustworthyDemoNativeModel`，观察 fine-tuned model 是否更稳定、更贴近训练集表达。
