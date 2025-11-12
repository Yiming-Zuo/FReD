# FReD

FReD（Free-energy Reweighting and Dataset Builder） 是一个 Replica-Exchange Structured Track 数据构建与重加权的工具集，用于将 REST2-GROMACS 采样结果转换为无偏平衡系综，以支持基于生成模型的自由能估计。

## 项目结构

```
FReD/
├── README.md
├── requirements.txt
├── data/
│   └── rep_*/                 # 各副本的采样输出
├── scripts/
│   ├── 00_data_validation.py   # 数据完整性检查
│   ├── 01_extract_energies.py  # 从 EDR 提取能量矩阵
│   ├── 02_parse_exchanges.py   # 从 LOG 解析副本交换
│   ├── 03_build_dataset.py     # 构建 MBAR 数据集
│   ├── 04_mbar_analysis.py     # MBAR 重加权分析
│   ├── 05_trajectory_analysis.py # 轨迹分析
│   └── utils/
├── notebooks/
├── outputs/
├── results/
│   ├── figures/
│   └── reports/
└── tests/
```

## 快速开始

### 1. 安装依赖

```bash
conda activate femto_test  # 或你的环境名
pip install -r requirements.txt
```

### 2. 数据验证

```bash
python scripts/00_data_validation.py
```

### 3. 提取能量矩阵

```bash
python scripts/01_extract_energies.py
```

### 4. MBAR 分析

```bash
python scripts/04_mbar_analysis.py
```

## 工作流程

1. **数据准备**：GROMACS REST2 模拟输出（EDR, XTC, LOG 文件）
2. **能量提取**：从 EDR 文件提取所有副本在所有温度状态下的势能
3. **交换解析**：从 LOG 文件解析副本交换历史
4. **数据集构建**：构建标准化的 MBAR 输入数据集
5. **MBAR 计算**：使用 pymbar 进行重加权
6. **结果分析**：生成图表和报告

## 关键特性

- ✅ 支持 GROMACS REST2 数据格式（EDR, XTC, LOG）
- ✅ 自动提取能量矩阵和交换历史
- ✅ MBAR 重加权分析（基于 pymbar）
- ✅ 轨迹分析（二面角、构象等）
- ✅ 详细的诊断和可视化

## 依赖

- Python >= 3.8
- panedr - EDR 文件读取
- mdtraj - XTC 轨迹分析
- pymbar - MBAR 计算
- numpy, pandas, matplotlib

## 参考

- MBAR 理论：Shirts & Chodera, J. Chem. Phys. 2008
- GROMACS REST2：https://manual.gromacs.org/documentation/current/reference-manual/algorithms/replica-exchange.html
- pymbar 文档：https://pymbar.readthedocs.io/

## TODO

- [ ] 实现 EDR 能量矩阵提取
- [ ] 实现 LOG 交换历史解析
- [ ] 实现 MBAR 数据集构建
- [ ] 实现 MBAR 分析流程
- [ ] 实现轨迹分析
- [ ] 添加单元测试
- [ ] 编写使用教程

## 许可

MIT License - Use this however you want. Make it your own.

随意使用，让他成为你自己的。
