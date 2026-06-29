# BetterGLM 指标报告

生成时间：`2026-06-29T16:43:57`
回放目录：`runs`
已排除运行中任务：`1`

## 核心指标

| 指标 | 数值 | 证明什么 |
| --- | ---: | --- |
| iOS 模板数 | 19 | 可复现 demo 和回归场景覆盖。 |
| 带评分标准模板数 | 19 | 任务有确定性成功条件，不靠模型自述。 |
| 低风险模板数 | 17 | Prompt 内显式约束不支付、不下单、不互动。 |
| 回放任务数 | 9 | 可用于调试、复盘和演示的证据样本。 |
| 已评分任务数 | 8 | 有 passed/failed 和分数的任务样本。 |
| 评分通过率 | 62% | 基于回放证据的质量指标。 |
| 平均分 | 81.1 | 任务完成质量的聚合分。 |
| 平均步数 | 8.8 | 任务效率和收敛速度信号。 |
| 完整回放率 | 100% | metadata、steps、HTML replay 的可观测性覆盖。 |
| 步骤截图覆盖率 | 100% | 每一步是否有视觉证据可复盘。 |
| 坐标审计覆盖率 | 84% | 触控动作是否记录了坐标映射证据。 |

## 质量指标

```json
{
  "total_runs": 9,
  "evaluated_runs": 8,
  "passed_runs": 5,
  "failed_or_classified_runs": 3,
  "scored_pass_rate": 62,
  "avg_score": 81.1,
  "avg_steps": 8.8,
  "avg_duration_seconds": 97,
  "status_counts": {
    "passed": 5,
    "failed": 3,
    "completed": 1
  },
  "failure_counts": {
    "max_steps": 3
  }
}
```

## 回放证据指标

```json
{
  "complete_replay_runs": 9,
  "complete_replay_rate": 100,
  "runs_with_evaluation": 8,
  "evaluation_coverage": 89,
  "total_steps": 79,
  "screenshot_steps": 79,
  "screenshot_file_coverage": 100,
  "step_screenshot_coverage": 100
}
```

## 坐标执行指标

```json
{
  "touch_actions": 43,
  "audited_touch_actions": 36,
  "coordinate_audit_coverage": 84,
  "coordinate_points": 37,
  "clamped_points": 0,
  "strategy_counts": {
    "wda_window_calibrated": 37
  },
  "action_counts": {
    "Tap": 42,
    "Launch": 10,
    "Type": 7,
    "Back": 6,
    "Home": 4,
    "Swipe": 1
  }
}
```

## 模板库指标

```json
{
  "ios_templates": 19,
  "scored_templates": 19,
  "guarded_templates": 17,
  "app_or_scene_segments": 24,
  "top_tags": {
    "safe": 17,
    "portfolio": 16,
    "ios": 3,
    "alibaba": 3,
    "ecommerce": 3,
    "content": 3,
    "smoke": 2,
    "meituan": 2,
    "video": 2,
    "browser": 1,
    "settings": 1,
    "demo": 1
  }
}
```

## 最近任务样本

| 状态 | 分数 | 步数 | 耗时秒 | 失败类型 | 任务 | 回放目录 |
| --- | ---: | ---: | ---: | --- | --- | --- |
| passed | 100 | 7 | 62 | - | 打开大众点评，搜索火锅，停留在商户或笔记搜索结果页，不要下单、不要写评价 | `runs/web/20260629-163927-打开大众点评-搜索火锅-停留在商户或笔记搜索结果页-不要下单-不要写评价` |
| failed | 61 | 16 | 259 | max_steps | 打开哔哩哔哩，搜索Python 教程，停留在视频搜索结果页，不要点赞、不要投币、不要评论 | `runs/benchmark-20260629-151604/20260629-152227-打开哔哩哔哩-搜索Python-教程-停留在视频搜索结果页-不要点赞-不要投币-不要评论` |
| passed | 100 | 7 | 69 | - | 打开高德地图，搜索北京南站，停留在地点搜索结果页，不要发起打车、不要导航 | `runs/benchmark-20260629-151604/20260629-152117-打开高德地图-搜索北京南站-停留在地点搜索结果页-不要发起打车-不要导航` |
| passed | 100 | 6 | 72 | - | 打开支付宝，搜索汇率，停留在搜索结果页，不要转账、不要付款、不要打开收付款码 | `runs/benchmark-20260629-151604/20260629-152004-打开支付宝-搜索汇率-停留在搜索结果页-不要转账-不要付款-不要打开收付款码` |
| failed | 44 | 10 | 105 | max_steps | 打开设置，查看当前 Wi-Fi 页面，不要修改任何设置 | `runs/benchmark-20260629-151604/20260629-151818-打开设置-查看当前-Wi-Fi-页面-不要修改任何设置` |
| failed | 44 | 14 | 133 | max_steps | 打开 Safari 搜索上海天气 | `runs/benchmark-20260629-151604/20260629-151604-打开-Safari-搜索上海天气` |
| passed | 100 | 5 | 51 | - | 打开支付宝，搜索汇率，停留在搜索结果页，不要转账、不要付款、不要打开收付款码 | `runs/web/20260629-150026-打开支付宝-搜索汇率-停留在搜索结果页-不要转账-不要付款-不要打开收付款码` |
| completed | - | 7 | 64 | - | 打开抖音，评论一句你好 | `runs/web/20260629-143757-打开抖音-评论一句你好` |
| passed | 100 | 7 | 58 | - | 打开 Safari 搜索北京天气 | `runs/smoke-test/20260629-143116-打开-Safari-搜索北京天气` |

## 这些数据怎么证明优化

- 不是只录一次成功 demo，而是把每次任务沉淀为 metadata、steps、screenshots、HTML replay 和 evaluation report。
- 评分通过率、平均分、平均步数能证明 Agent 质量和效率，而不是只相信模型说“完成了”。
- 失败类型能区分 max_steps、目标 App 不匹配、目标文本缺失、WDA/坐标/解析异常，方便继续优化。
- 坐标审计覆盖率能证明点击链路被观测：模型坐标、截图像素、WDA/设备坐标都有记录。
- 模板数量和低风险模板数量能证明你做了场景库和安全边界，而不是零散手写 prompt。

## 简历可写

- 构建手机 Agent 回放评测体系，累计生成多条真实 iOS 任务回放，统计评分通过率、平均步数、失败类型和坐标审计覆盖率。
- 将单次手机自动化 demo 产品化为可复现模板库和质量 Dashboard，支持任务级 replay、deterministic evaluation 和失败归因。
- 优化多模态点击执行链路，记录模型归一化坐标、截图像素和 WDA 触控坐标，用数据定位点击偏移问题。
