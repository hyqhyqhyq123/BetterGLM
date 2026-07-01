# Agent Notes

- 用户使用苹果手机，默认按 iOS 设备运行本项目。
- `.env` 中应保持 `PHONE_AGENT_DEVICE_TYPE=ios`。
- 运行前使用 conda 环境：

```bash
conda activate open-autoglm
cd /Users/a1-6/Documents/Open-AutoGLM
python main.py "你的任务描述"
```

- iOS 需要先完成 WebDriverAgent 配置；如需单独指定地址，可在 `.env` 中加入或修改：

```env
PHONE_AGENT_WDA_URL=http://localhost:8100
```

---

# Agent 开发岗面试拷打清单

更新时间：2026-06-29

目标岗位：Agent 开发、Agent 应用开发、LLM 应用工程、GUI Agent、Code Agent、Agent Eval/Infra。

## JD 调研摘要

官方岗位样本：

- 腾讯招聘：微信 GUI Agent、Code Agent、RAG & Agent、Agent Harness、Agent 应用后台、多智能体、Agent 后训练与评测。
  - https://careers.tencent.com/jobdesc.html?postId=2037392063242334208
  - https://careers.tencent.com/jobdesc.html?postId=2037392060885139456
  - https://careers.tencent.com/jobdesc.html?postId=2051971948526878720
  - https://careers.tencent.com/jobdesc.html?postId=2037392065205268480
  - https://careers.tencent.com/jobdesc.html?postId=2042431102441910272
- 百度招聘：AIDU Agent 应用全栈、智能体算法，强调 Planning/Acting/Reflection、Tool/API、Memory、RAG+Agent、Eval、成本和延迟。
  - https://talent.baidu.com/jobs/list?search=agent
- OpenAI Careers：Forward Deployed Software Engineer、AI Deployment Engineer、agentic search，强调把模型能力做成可扩展生产系统。
  - https://jobs.ashbyhq.com/openai/00207abc-49b7-465c-a219-f7c1140f8047
  - https://jobs.ashbyhq.com/openai/04435c05-7a05-4802-894d-c173327fbac8
  - https://jobs.ashbyhq.com/openai/020b2aae-8be0-408c-ab49-20eefa8541af
- Anthropic Careers：Applied AI Architect、Agent Prompts & Evals，强调 eval frameworks、prompt pipeline、regression detection、可靠部署。
  - https://job-boards.greenhouse.io/anthropic/jobs/5159608008
  - https://job-boards.greenhouse.io/anthropic/jobs/5228931008
- Amazon Jobs/AWS：AI Agent Engineer、AWS Agentic AI、agent identity & governance、agent orchestration、agent evaluation、knowledge management。
  - https://www.amazon.jobs/en/jobs/10451070/ai-agent-engineer-arts
  - https://www.amazon.jobs/en/jobs/10443815/sr-software-dev-engineer-ai-agent-identity-governance-aws-applied-ai-solution-core-services
  - https://www.amazon.jobs/en/jobs/3167825/software-development-engineer-aws-agentic-ai
  - https://www.amazon.jobs/en/jobs/10457263/senior-technical-program-manager-customer-experience-and-business-trends

JD 共性：

- Agent 不只是 prompt，而是状态、工具、规划、执行、反思、评测、回放、治理的完整系统。
- GUI Agent 岗重点问长程任务、未见页面泛化、动作空间、坐标映射、真实设备失败恢复。
- Code Agent 岗重点问代码检索、上下文构造、测试闭环、回滚、安全沙箱、PR 质量。
- Agent Eval 岗重点问 trajectory quality、tool-call precision、argument accuracy、success rate、latency、cost、regression detection。
- 应用后台岗重点问高并发、低延迟、任务队列、状态机、trace、权限、成本控制、可观测性。

Boss/牛客补充口径：

- Boss 直聘搜索页：
  - https://www.zhipin.com/web/geek/job?query=AI%20Agent&city=101010100
  - 前端 bundle 暴露职位接口 `/wapi/zpgeek/search/joblist.json`、`/wapi/zpgeek/job/detail.json`，但直接接口调用触发环境异常，不能稳定抽取岗位详情。
  - 市场侧常见关键词仍集中在：大模型应用开发、RAG、Agent 工作流、Python/FastAPI、LangChain/LangGraph、向量数据库、工具调用、企业知识库、业务自动化。
- 牛客搜索页：
  - https://www.nowcoder.com/search/all?query=%E5%A4%A7%E6%A8%A1%E5%9E%8B%20Agent%20%E9%9D%A2%E8%AF%95
  - https://www.nowcoder.com/search/all?query=LangChain%20RAG%20%E9%9D%A2%E8%AF%95%20%E7%89%9B%E5%AE%A2
  - 高频面试口径不再满足“我用了 LangChain/Milvus/DeepSeek”，而是追问：业务场景、为什么需要 Agent、选型边界、上线稳定性、Benchmark、回滚/沙盒、状态一致性、长上下文和记忆成本。
  - 牛客上贴近题目包括：“如果我关掉你的大模型，你的 Agent 还剩下什么？”、“简历上写了 RAG/Agent 项目，面试官到底想听什么？”、“为什么用 LangChain 而不是直接用官方 API？”。

## 简历命中点

- 手机 GUI Agent：iOS 真机、WebDriverAgent/XCTest、截图理解、Launch/Tap/Type/Swipe/Back/Home 闭环，直接对齐 GUI Agent。
- Agent Eval/Infra：Replay、Evaluation、Dashboard、BetterGLM-Bench、失败归因、坐标审计，对齐腾讯/Anthropic/Amazon 的 Agent eval 和 regression detection。
- Code Agent：LangGraph 14 节点、LlamaIndex+BM25+RRF、AST 切分、Docker 测试、人工审批、路径围栏、命令黑名单，对齐 Code Agent 和 coding automation。
- 生产化味道：FastAPI、PostgreSQL、Redis、Celery、Web Console、Doctor、Token 加密、权限分级，能往应用工程岗讲。

## 简历风险点

- 数据口径要解释清楚：简历写 60 个 iOS 任务模板、400+ 条真实设备回放、4482 步、92% 截图覆盖率、95% 回放完整率；当前仓库样例报告是 19 个模板、12 条回放、124 步、100% 截图覆盖率、88% 坐标审计覆盖率。面试时必须说明完整实验数据在哪里、统计脚本怎么跑、是否因隐私没有提交 runs。
- “通过率由原版约 62% 提升至 74%”要能说清 baseline：任务集、设备、模型版本、max_steps、随机性控制、失败分类、重复实验次数。
- “90% 自动评分覆盖”和“88% 坐标审计覆盖”要能说清分母：是任务模板、回放、步骤，还是触控动作。
- Code Agent 项目不在当前仓库，需要准备可展示证据：README、架构图、实验脚本、SWE-Bench 子集列表、43 个 API/13 张表 schema、190 个测试用例摘要。
- 简历里有科研和两个独立项目，面试官会追问“哪些是你独立写的，哪些是基于开源改造”。回答要坦诚区分 upstream 与二开增强。

## 第一轮：项目总览

1. 用 2 分钟讲清 BetterGLM 的核心贡献。不要复述 README，要说“原 Open-AutoGLM 缺什么、你补了什么、指标如何证明有用”。
2. 你的 Agent loop 是什么状态机？从用户任务、截图、模型响应、动作解析、执行、回放、终止条件逐步讲。
3. 为什么这个项目算 Agent，而不是普通 UI 自动化脚本？请从 perception、planning、tool use、feedback loop、eval 五个角度回答。
4. 你在 fork 中最核心的 3 个改动是什么？每个改动给一个真实失败案例和修复后的指标变化。
5. 如果面试官只给你 5 分钟 demo，你会展示 Doctor、Web Console、Replay、Evaluation 中哪三个？为什么？

## 第二轮：GUI Agent 执行链路

1. 模型输出的动作 schema 是什么？`do(...)` 和 `finish(...)` 如何解析？解析失败为什么选择重试而不是直接 fail？
2. 当前动作解析失败重试会把上一张图片从 context 里移除，这个设计解决什么问题？会引入什么信息损失？
3. `AgentLoopGuard` 用“连续 3 次完全相同 action JSON”判断重复动作。这个策略有哪些 false positive 和 false negative？
4. App 未安装为什么要快速失败？如果模型在 Spotlight 搜索页反复搜索 App，你怎么区分“仍有希望找到”和“应该停止”？
5. WDA 断连时为什么不能把黑屏或空截图继续交给模型？这类坏输入会怎样污染 Agent 决策？
6. `request_cancel` 为什么只在安全检查点生效？如果模型调用和 WDA action 正在执行，强杀有什么风险？

## 第三轮：坐标映射与真机问题

1. 模型输出 0-1000 坐标，为什么不直接用截图像素？跨设备泛化和执行精度怎么权衡？
2. 解释 `CoordinateMapper` 的链路：model coordinate -> screenshot pixel -> WDA window point -> transport coordinate。
3. iOS 上为什么要读取 WDA `window/size`？截图尺寸和 WDA 坐标系可能在哪些设备、缩放、横竖屏情况下不一致？
4. 当前 `transport_coordinate` 最终 clamp 到 screenshot 宽高范围，这里有没有潜在 bug？如果 WDA target size 和 screenshot size 不同，应该 clamp 到哪个坐标系？
5. 坐标审计里记录 `clamped_points=0` 说明什么？它不能说明什么？
6. 如果用户说“模型总是点偏 50px”，你如何通过 Replay 判断是模型看错、截图缩放错、WDA 坐标换算错，还是页面动画导致时序错？

## 第四轮：Replay、Eval 与指标

1. 为什么不能相信模型最后说“完成了”？你的 deterministic evaluator 用了哪些证据？
2. `_build_text_corpus` 里为什么不能把原始用户任务当成功证据？否则会导致什么分数污染？
3. 当前评分项有 run_completed、no_step_errors、max_steps、target_app、must_contain_text。各自的权重为什么这么设？如果换成电商任务怎么改？
4. `must_contain_text` 只看文本证据，遇到图片型页面、地图点位、视频结果页时会有什么漏判？如何增强？
5. 通过率 45% 或 74% 如何解释才不显得弱？你要强调它是 benchmark 质量指标，而不是单次 demo 成败。
6. 设计一个 Agent regression test：模型版本、prompt、动作解析器、坐标映射任一改动后，如何判断有没有退化？
7. 如果要上线给业务方用，你会新增哪些指标？至少回答 success rate、tool precision、argument accuracy、retry count、latency、cost、safety failure。

## 第五轮：Web Console 与工程化

1. Web Console 如何管理异步任务状态？`WebConsoleState` 里哪些字段必须加锁，为什么？
2. `/api/stop` 请求如何传递到正在运行的 Agent？有哪些 race condition？
3. `_send_replay_file` 如何防路径穿越？`resolve()` 和 `parents` 检查能防住哪些攻击？
4. Web Console 为什么适合面试/作品集？它和命令行相比，体现了哪些产品化能力？
5. 如果多个用户同时提交任务，目前系统会怎样？要扩展成多租户任务队列，你会怎么设计？
6. 真实设备池如何管理？WDA session、设备占用、失败恢复、截图隐私、日志清理分别怎么做？

## 第六轮：Code Agent 项目深挖

1. LangGraph 14 个节点分别是什么？每个节点输入输出是什么？失败如何路由？
2. 为什么用 LlamaIndex + BM25 + RRF，而不是只用向量检索？RRF 的融合公式和 TopK 调参怎么做？
3. AST 代码切分解决了什么问题？和按固定 token chunk 切相比，召回率和上下文污染有什么差异？
4. Recall@5 从 0.42 到 0.67 的评测集怎么构建？“相关文件”的标注从哪里来？
5. token 消耗降低 35% 是怎么算的？是 prompt tokens、context tokens、总 tokens，还是成功样本上的平均？
6. Docker 测试失败后，诊断 Agent 如何定位原因？如何避免模型乱改无关文件？
7. 路径围栏、命令黑名单、权限分级、Token 加密分别防什么风险？给一个 prompt injection 例子。
8. SWE-Bench 子集成功率 23.3% -> 35.7%，子集大小、题目难度、pass@1/多次重试口径是什么？

## 第七轮：科研经历深挖

1. CSAS 里的“上下文完整性”和“噪声抑制”矛盾在哪里？为什么跨过程漏洞检测尤其明显？
2. 风险引导自适应切片怎么定义风险？风险来自静态规则、模型分数、调用图，还是数据流？
3. LLM 审计报告增强是训练时增强、推理时解释，还是后处理特征？它如何提升检测器 F1？
4. FFmpeg+QEMU 和 PrimeVul 数据集怎么划分训练/测试？如何避免函数或项目级泄漏？
5. 相对提升 71.1% 和 20.7% 的原始 F1 分别是多少？为什么两个数据集提升差距这么大？

## 场景题

1. 让你做微信里的 GUI Agent，要求未见页面泛化和长程任务成功率，你会怎么做训练数据、环境、动作空间和评测？
2. 让你做企业知识库 RAG+Agent，用户会让 Agent 查资料、写报告、调用内部系统。如何设计工具权限、引用、记忆、审计和回滚？
3. 让你把手机 Agent 上线到 100 台真机并发跑巡检，设备调度、WDA 保活、任务队列、日志存储、成本怎么设计？
4. 业务说“成功率要从 74% 到 90%”，你会先投模型、prompt、动作空间、任务模板、坐标链路、还是评测体系？给优先级。
5. Agent 在支付 App 里误触“付款”，你如何从产品、工程、模型、评测四层降低风险？
6. 用户在 App 里登录/验证码/隐私页面卡住，Take_over 机制应该怎样设计，才能兼顾自动化效率和安全？

## 反问候选人必备口径

- 我做的不是重新训练手机模型，而是把手机 Agent 的工程闭环补齐：诊断、执行、失败快停、回放、评测、Dashboard。
- 我最想继续补的是更强的 trajectory-level evaluator：不仅看最终结果，还看每一步工具选择、参数正确性、重复动作、恢复能力、成本和延迟。
- 我能讲清楚 upstream 和我二开的边界：原项目提供手机 Agent 基础链路，我增强了 iOS 工程化、可观测性、评测和演示体验。

## 今天先练的 8 个问题

1. 你用 90 秒讲一下 BetterGLM，相比原 Open-AutoGLM 你的核心贡献是什么？
2. 简历里 60 个模板、400+ 回放、4482 步的数据，和当前仓库报告的 19 个模板、12 条回放是什么关系？完整数据怎么复现？
3. `CoordinateMapper` 里如果 WDA target size 和 screenshot size 不一致，最终 clamp 到 screenshot 范围是否合理？你会怎么修？
4. 为什么 action parse failed 后要继续跑，而不是直接失败？如何避免模型连续输出坏格式导致浪费步骤？
5. 你的 evaluator 如何避免“prompt 里有关键词，所以评分通过”的污染？代码里具体哪一段体现？
6. AgentLoopGuard 连续 3 次完全相同 action 才停。如果模型在同一个输入框里连续 Type 三次不同文本，或者连续 Tap 三个相邻点，怎么检测循环？
7. Code Agent 的 Recall@5 提升和 SWE-Bench 成功率提升分别怎么测？有没有统计显著性和样本泄漏问题？
8. 如果腾讯微信 GUI Agent 面试官问“你怎么提升未见场景泛化”，你会从数据、模型、工具、评测四层怎么答？
