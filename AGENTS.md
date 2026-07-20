# podcast-translator

英文播客转中文工具（基于 VideoLingo 改造）

**GitHub**: https://github.com/mango666ai/podcast-translator  
**全局工作区总览**: https://github.com/mango666ai/aicoding-notes

## 开始工作前必读（强制）

本仓库可能被 clone 到不同机器/不同目录深度（工作区磁盘 vs 其他本地路径），相对路径不一定能解析到同一份文件。因此：

1. **必须先完整读取本仓库根目录的 [`PRD_SUMMARY.md`](PRD_SUMMARY.md)**（项目目标、范围、当前完成度、最大阻塞）——这份文件随 git 同步，保证任何 clone 都能读到。
2. 如果你的环境能访问 `/Volumes/SANDISK ELE/AICoding`，优先读完整版：`/Volumes/SANDISK ELE/AICoding/project5_podcast/PRD.md`、`PROJECT_MAP.md`、`决策日志.md`。访问不到也不用勉强，按 `PRD_SUMMARY.md` 的信息工作即可。

## 决策日志（强制）

产生或确认会影响后续的产品、技术、范围或优先级决策时，收工前写入 `/Volumes/SANDISK ELE/AICoding/project5_podcast/决策日志.md`（绝对路径，不要用 `../`，不同 clone 的目录深度不同会解析错）：日期 + 结论 + why。未定案项标记"待你确认"，不臆造结论。**如果当前环境访问不到这个绝对路径，必须在收工汇报里明确说"决策未写入决策日志，因为路径不可达"，不要静默跳过。** 若阶段或下一步变化，同步更新 `/Volumes/SANDISK ELE/AICoding/项目总览.md`。收工汇报必须说明"已记录决策"或"本次无决策"。

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
