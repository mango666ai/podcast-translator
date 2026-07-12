# podcast-translator

英文播客转中文工具（基于 VideoLingo 改造）

**GitHub**: https://github.com/mango666ai/podcast-translator  
**全局工作区总览**: https://github.com/mango666ai/aicoding-notes

## 决策日志（强制）

产生或确认会影响后续的产品、技术、范围或优先级决策时，收工前写入 `../决策日志.md`：日期 + 结论 + why。未定案项标记“待你确认”，不臆造结论。若阶段或下一步变化，同步更新 `../../项目总览.md`。收工汇报必须说明“已记录决策”或“本次无决策”。

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
