# Development（开发与调试指南）— Hacker News Daily Scraper

## 为什么没有 `tests/` 目录

这是一组围绕数据的小脚本（HN API → JSON → 渲染成 Markdown），不是一个有纯函数、适合写单元测试的 library。大部分价值体现在端到端 pipeline 本身，以及它和两个外部 API（HN API、OpenAI API）的交互上。所以验证方式是手动/结构化检查，而不是一整套 test suite：

- **`main.py rebuild`**：完全基于已有的 JSON backup 重新渲染所有历史 `.md` 页面，不发起任何 HN/LLM/网络请求。改动了 template/CSS/渲染逻辑之后，这是在 push 之前确认没有把历史全部页面搞坏的标准做法。
- 排查渲染差异时，可以对比新生成 JSON 里的 `meta.count_written` 和对应 `.md` 里实际渲染出的卡片数量是否一致。
- 改了去重（dedup）逻辑之后，看 pipeline 打印出的 `[STEP 3/6] Dedup result:` 里 same-day/cross-day/cross-mode/new 四个计数，跟你根据当天已有 JSON 内容预期的结果对不对得上。

## 环境准备

```bash
pip install -r requirements.txt
export OPENAI_API_KEY=sk-...        # best/top/all/resummarize 需要；rebuild 不需要
```

不需要其他环境变量。`GITHUB_EVENT_NAME` 只是 `main.py` 用来在 `logs/scrape_run_log.md` 里标注这次运行是 `schedule`/`workflow_dispatch`/`local`（本地运行时这个变量不存在，会自动 fallback 成 `local`，不影响功能）。

## 本地运行

所有命令都要在仓库根目录下执行（`news_config.yml` 是用相对路径加载的）：

```bash
# 完整 pipeline，会真实调用 HN API 和 OpenAI API
python news_scraper/main.py best
python news_scraper/main.py top
python news_scraper/main.py all        # best 然后 top

# 仅根据已有 JSON 重新渲染所有历史页面 — 不发起任何网络请求
python news_scraper/main.py rebuild

# 只重新跑 LLM 摘要（比如改了 prompt 之后）
python news_scraper/resummarize.py                       # 处理所有 JSON 文件
python news_scraper/resummarize.py hackernews/2026/09/11/top_stories_09112026.json

# 周报（正常情况下由 cron 在每周一自动跑）
python news_scraper/weekly_digest.py                      # 上一个完整的自然周
python news_scraper/weekly_digest.py 2026-W08              # 指定 ISO 周
```

本地跑 `best`/`top`/`all` 会真实写入 `hackernews/` 下的生产数据文件，也会往 `logs/scrape_run_log.md` / `logs/openai_token_usage_log.md` 追加内容 —— 跟 GitHub Actions 上跑的效果完全一样，**没有单独的 dry-run 或 staging 输出目录**。所以本地跑这几个 mode 之前想清楚，提交前记得 `git diff` 检查一遍。

## 调试流程（Debugging workflow）

1. 本地复现问题（`python news_scraper/main.py <mode>`），看 `[STEP N/6]` 的进度日志 — pipeline 每一步都会打印当前阶段、计数和耗时。
2. 如果问题看起来跟 LLM 有关（返回的 JSON 格式不对、字段缺失），`llm_batch.py` 已经内置了一次 fallback model 重试（对应 `news_config.yml` 里的 `llm.fallback_model`）— 先确认是两个模型都失败了，还是只有主模型失败。
3. 如果问题看起来跟渲染有关（HTML 不对、tags/图片缺失）但 JSON 本身看起来是对的，用 `main.py rebuild` 把 `md_writer.py` 单独隔离出来测试，排除掉抓取/LLM 这些步骤的干扰。
4. 只在 GitHub Actions 上才出现的问题，去对应 workflow 的 Job Summary 标签页看 — `hn_top.yml` 会把 pipeline 的指标表格，加上两个日志文件的 tail 内容都写在那里（见 `.github/workflows/hn_top.yml`）。

## 项目约定（Project conventions）

- 每天的 JSON 是唯一的 source of truth（详见 `docs/ARCHITECTURE.md`）— **永远不要手动编辑生成好的 `.md` 页面**，要改就改 JSON 再重新渲染，否则下一次 scrape/rebuild 会直接把你的手改覆盖掉。
- 模型名称等可调参数都放在 `news_config.yml` 里，不要硬编码进脚本 — 以后新增的可调参数也遵循同样的模式。
- `logs/scrape_run_log.md` 和 `logs/openai_token_usage_log.md` 是被 CI workflow 硬编码引用的路径 — 改名或挪位置之前，必须同步改 `run_logger.py`、`token_logger.py` 和 `hn_top.yml`。
- 新的一次性开发笔记/实验记录写进 `logs/YYYY-MM-DD.md`（当天没有就新建一个），不要作为零散文件散落在 `news_scraper/` 或 `logs/` 目录下。
