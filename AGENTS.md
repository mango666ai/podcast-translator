# podcast-translator

英文播客转中文工具（基于 VideoLingo 改造）

**GitHub**: https://github.com/mango666ai/podcast-translator  
**全局工作区总览**: https://github.com/mango666ai/aicoding-notes

## 开始工作前必读（强制）

⚠️ **本仓库是 public**（为了用 GitHub Pages 托 RSS 和音频直链）。内部材料——`决策日志.md`、`PRD.md`、`PROJECT_MAP.md`、`成本拆解.md`、`分享素材.md`——**一律不要提交到本仓库**，它们统一放在私有的工作区笔记仓库 [aicoding-notes](https://github.com/mango666ai/aicoding-notes) 的 `project5_podcast/` 下（2026-08-13 决定：其他项目的决策日志都收归各自私有仓库，project5 因仓库公开而作为例外保留在笔记仓库）。

开工前按顺序读：

1. **必须先完整读取本仓库根目录的 [`PRD_SUMMARY.md`](PRD_SUMMARY.md)**（项目目标、范围、当前完成度、最大阻塞）——脱敏版，随本仓库 git 同步，任何 clone 都能读到。
2. **[`播客工作循环.md`](播客工作循环.md)**（标准流程，唯一真相源）和 [`PROGRESS.md`](PROGRESS.md)（做到哪里）。
3. 完整的内部文档在私有笔记仓库 `aicoding-notes/project5_podcast/`：`PRD.md`、`PROJECT_MAP.md`、`决策日志.md`、`成本拆解.md`。能访问就读，访问不到按 `PRD_SUMMARY.md` 工作即可。

## 决策日志（强制）

产生或确认会影响后续的产品、技术、范围或优先级决策时，收工前写入**私有笔记仓库** `aicoding-notes/project5_podcast/决策日志.md`：日期 + 结论 + why。未定案项标记"待你确认"，不臆造结论。**如果当前环境访问不到那个仓库，必须在收工汇报里明确说"决策未写入决策日志，因为仓库不可达"，不要静默跳过，也不要为了图方便写进本公开仓库。** 若阶段或下一步变化，同步更新 `aicoding-notes/项目总览.md`。收工汇报必须说明"已记录决策"或"本次无决策"。

## 进度文件（强制）

每次收工前必须创建或更新仓库根目录 `PROGRESS.md`，写明日期、当前状态、本次完成、验证结果、下一步与阻塞项。收工汇报必须确认已更新。

## Git 同步规则（强制）

开始工作前：
```bash
git pull
```

结束工作后：
```bash
git add -A && git commit -m "描述" && git push
```

收工必须说明：改了哪些文件 / 是否已 push / 有无未完成工作。
