# FReD

FReD（Free-energy Reweighting and Dataset Builder） 是一个 Replica-Exchange Structured Track 数据构建与重加权的工具集，用于将 REST2-GROMACS 采样结果转换为无偏平衡系综，以支持基于生成模型的自由能估计。

## 数据流动

```
   原始数据                验证报告              MBAR输入             MBAR输出            训练数据集
(GROMACS REST2)          (完整性检查)          (能量+映射)          (权重+诊断)        (坐标+能量)
      ↓                      ↓                    ↓                   ↓                  ↓
┌──────────────┐      ┌──────────────┐     ┌──────────────┐    ┌──────────────┐   ┌──────────────┐
│  prod.edr    │      │ Lambda检测    │     │  u_kn矩阵    │    │  MBAR权重     │   │ coordinates  │
│  prod.log    │  →   │ 文件完整性     │  →  │  N_k数组     │ →  │  自由能曲线    │ → │  energies    │
│  prod.xtc    │      │ MBAR就绪      │     │  状态映射     │    │  overlap矩阵  │   │  box向量     │
└──────────────┘      └──────────────┘     └──────────────┘    └──────────────┘   └──────────────┘
    data/rep_*              00                     01                 02                  03
                    data_validation         prepare_mbar          run_mbar      build_training_dataset
```

## 项目结构

```
FReD/
├── README.md
├── requirements.txt
├── data/
│   └── rep_*/                   # 各副本的采样输出
│       ├── prod.edr             # 能量文件
│       ├── prod.log             # 日志文件(含交换记录)
│       ├── prod.xtc             # 轨迹文件
│       ├── prod.tpr             # 拓扑文件
│       └── prod.gro             # 结构文件
├── scripts/
│   ├── 00_data_validation.py        # 数据完整性验证
│   ├── 01_prepare_mbar.py           # MBAR输入准备
│   ├── 02_run_mbar.py               # MBAR计算和诊断
│   ├── 03_build_training_dataset.py # 训练数据集构建
│   ├── utils/
│   │   ├── validation.py            # 数据验证
│   │   ├── io.py                    # 统一I/O接口
│   │   ├── preprocessing.py         # 能量提取和交换解析
│   │   ├── mbar.py                  # MBAR核心计算
│   │   ├── visualization.py         # 诊断可视化
│   │   └── resampling.py            # 重采样和构象提取
│   └── tools/
│       ├── inspect_edr.py           # EDR文件检查
│       ├── inspect_log.py           # LOG文件分析
│       └── analyze_trajectory.py    # 轨迹分析
├── outputs/
│   ├── validation_report.json   # 验证报告
│   ├── mbar_input.npz           # MBAR输入数据
│   ├── mbar_weights.npz         # MBAR权重
│   ├── mbar_diagnostics.json    # 诊断报告
│   ├── training_dataset.npz     # 训练数据集
│   └── figures/
├── docs/
└── tests/
```

## 快速开始

### 1. 安装依赖

```bash
conda activate fred
pip install -r requirements.txt
```

### 2. 完整工作流

```bash
# 步骤0: 数据验证
python scripts/00_data_validation.py
# 输出: outputs/validation_report.json

# 步骤1: 准备MBAR输入
python scripts/01_prepare_mbar.py
# 输出: outputs/mbar_input.npz

# 步骤2: MBAR计算
python scripts/02_run_mbar.py --target-state 0
# 输出: outputs/mbar_weights.npz, mbar_diagnostics.json, figures/*.png

# 步骤3: 构建训练集
python scripts/03_build_training_dataset.py --n-samples 10000
# 输出: outputs/training_dataset.npz
```

### 3. 辅助工具

```bash
# EDR文件快速检查
python scripts/tools/inspect_edr.py data/rep_0/prod.edr

# LOG文件交换分析
python scripts/tools/inspect_log.py data/rep_0/prod.log --n-replicas 5

# 轨迹分析(RMSD/回旋半径)
python scripts/tools/analyze_trajectory.py data/rep_0/prod.xtc data/rep_0/prod.gro --rmsd --rg
```

### 4. 交互式教程

```bash
cd notebooks/
jupyter notebook 01_quick_start.ipynb
```

## 5. 数据格式

### mbar_input.npz
```python
u_kn: (n_states, n_samples_total)  # 能量矩阵 [kJ/mol]
N_k: (n_states,)                    # 每状态样本数
replica_to_state: (n_cycles, n_replicas)  # 状态映射
lambda_values: (n_states,)          # Lambda参数
```

### training_dataset.npz
```python
coordinates: (n_samples, n_atoms, 3)  # 坐标 [nm]
energies: (n_samples,)                # 能量 [kJ/mol]
box: (n_samples, 3, 3)                # 盒子向量 [nm]
original_indices: (n_samples, 2)      # 数据来源追溯
```

## 参考文献

- **MBAR理论**: Shirts & Chodera, *J. Chem. Phys.* 129, 124105 (2008)
- **GROMACS REST2**: [官方手册](https://manual.gromacs.org/documentation/current/reference-manual/algorithms/replica-exchange.html)
- **pymbar文档**: [pymbar.readthedocs.io](https://pymbar.readthedocs.io/)

## 许可

MIT License - Use this however you want. Make it your own.

随意使用，让他成为你自己的。
