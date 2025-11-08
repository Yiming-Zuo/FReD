# results/

此目录用于存放最终的分析结果。

## 结构

```
results/
├── figures/        # 图表（PNG, PDF）
└── reports/        # 文本报告（TXT, MD）
```

## figures/

预期图表包括：

- `energy_evolution.png`: 能量时间序列
- `acceptance_rates.png`: 副本交换接受率矩阵
- `replica_walk.png`: 副本游走轨迹
- `ramachandran_*.png`: Ramachandran 图（如适用）
- `mbar_diagnostics.png`: MBAR 诊断图
- `free_energy_surface.png`: 自由能曲面

## reports/

预期报告包括：

- `data_summary.txt`: 数据完整性报告
- `exchange_stats.txt`: 副本交换统计
- `mbar_report.txt`: MBAR 分析报告
- `trajectory_analysis.txt`: 轨迹分析摘要

## 注意

建议添加到 `.gitignore` 中，仅保留最终版本的图表和报告到版本控制。
