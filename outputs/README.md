# outputs/

此目录用于存放处理后的中间数据文件。

## 预期文件

- `energy_matrix.npz`: 从 EDR 提取的能量矩阵
- `exchange_record.csv`: 从 LOG 解析的副本交换记录
- `dataset.arrow` (或 `.h5` / `.npz`): 标准化的 MBAR 输入数据集
- `mbar_weights.npz`: MBAR 计算的权重

## 注意

这些文件由脚本自动生成，不应手动编辑。
建议添加到 `.gitignore` 中（文件较大）。
