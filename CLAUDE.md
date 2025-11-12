# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目简介

FReD（Free-energy Reweighting and Dataset Builder）是一个用于将 REST2-GROMACS 采样结果转换为无偏平衡系综的工具集，支持基于生成模型的自由能估计。

## 开发环境

### 环境配置
```bash
conda activate femto_test
pip install -r requirements.txt
```

### 在 Claude Code 中使用 Conda 环境

**重要**: 本项目必须使用 `femto_test` conda 环境运行所有 Python 代码和测试。

由于 Claude Code 的 shell 环境未自动初始化 conda，需要先激活 conda 后再执行命令：

```bash
# 方式 1: 使用 conda run（需要先初始化）
source /opt/anaconda3/bin/activate && conda run -n femto_test python scripts/00_data_validation.py

# 方式 2: 直接激活环境（推荐，更简洁）
source /opt/anaconda3/bin/activate femto_test && python scripts/00_data_validation.py

# 运行测试
source /opt/anaconda3/bin/activate femto_test && pytest tests/ -v

# 运行单个测试文件
source /opt/anaconda3/bin/activate femto_test && pytest tests/test_edr_parser.py -v

# 安装新依赖
source /opt/anaconda3/bin/activate femto_test && pip install <package_name>
```

**不要使用**:
- ❌ `python scripts/xxx.py` (会使用系统 Python)
- ❌ `pytest tests/` (会使用错误的环境)
- ❌ `conda run -n femto_test python scripts/xxx.py` (conda 未初始化，会报错)

**正确使用**:
- ✅ `source /opt/anaconda3/bin/activate femto_test && python scripts/xxx.py`
- ✅ `source /opt/anaconda3/bin/activate femto_test && pytest tests/`

### 核心依赖
- **panedr** (>=0.7.0): 读取 GROMACS EDR 文件
- **mdtraj** (>=1.9.0): XTC 轨迹分析
- **pymbar** (>=4.0.0): MBAR 重加权计算
- numpy, pandas, matplotlib, seaborn

## 常用命令

### 完整工作流
```bash
# 激活环境（所有命令前都需要）
source /opt/anaconda3/bin/activate femto_test

# 1. 数据验证
python scripts/00_data_validation.py

# 2. 提取能量矩阵
python scripts/01_extract_energies.py

# 3. 解析副本交换（如果需要）
python scripts/02_parse_exchanges.py

# 4. 构建 MBAR 数据集
python scripts/03_build_dataset.py

# 5. MBAR 重加权分析
python scripts/04_mbar_analysis.py

# 6. 轨迹分析
python scripts/05_trajectory_analysis.py
```

### 测试
```bash
# 激活环境
source /opt/anaconda3/bin/activate femto_test

# 运行所有测试
pytest tests/ -v

# 运行单个测试
pytest tests/test_edr_parser.py -v
pytest tests/test_log_parser.py -v
pytest tests/test_mbar.py -v
```

## 代码架构

### 数据流向
```
GROMACS 输出 (data/rep_*)
    ├── EDR 文件 → 01_extract_energies.py → u_kn 能量矩阵
    ├── LOG 文件 → 02_parse_exchanges.py → replica_to_state_idx 映射
    └── XTC 文件 → 05_trajectory_analysis.py → 构象分析
                ↓
        03_build_dataset.py
                ↓
        outputs/dataset.arrow (或 .h5/.npz)
                ↓
        04_mbar_analysis.py
                ↓
        outputs/mbar_weights.npz
```

### 核心概念

#### 能量矩阵 u_kn
- **维度**: `(n_cycles, n_replicas, n_states)` 或重塑为 `(n_samples_total, n_states)`
- **含义**: `u_kn[i, j, k]` 表示第 i 个采样周期，第 j 个副本在第 k 个温度状态下的势能
- **关键问题**: GROMACS EDR 文件不一定包含所有状态的能量，可能需要使用 `gmx mdrun -rerun` 重新计算

#### 副本到状态的映射 replica_to_state_idx
- **维度**: `(n_cycles, n_replicas)`
- **含义**: `replica_to_state_idx[i, j] = k` 表示第 i 个周期，第 j 个副本处于第 k 个温度状态
- **用途**: MBAR 需要知道每个样本来自哪个状态

#### MBAR 工作流
1. **子采样**: 使用 `pymbar.timeseries.detect_equilibration()` 和 `subsample_correlated_data()` 去除相关性
2. **MBAR 初始化**: `MBAR(u_kn, N_k)` 其中 N_k 是每个状态的样本数
3. **权重计算**: 获取目标状态（通常是状态 0）的权重用于重加权
4. **诊断**: 检查 overlap 矩阵和有效样本数（ESS）

### 工具模块 (scripts/utils/)

- **edr_parser.py**: EDR 文件读取和能量矩阵提取
  - `read_edr_file()`: 读取单个 EDR 文件
  - `extract_u_kn_matrix()`: 从多个 EDR 提取能量矩阵
  - `get_lambda_columns()`: 检测是否包含多状态能量

- **log_parser.py**: LOG 文件解析和副本交换跟踪
  - `parse_gromacs_log()`: 解析交换记录
  - `build_replica_state_mapping()`: 重建 replica_to_state_idx
  - `calculate_exchange_statistics()`: 计算交换接受率

- **mbar_utils.py**: MBAR 分析和诊断
  - `run_mbar_analysis()`: 运行 MBAR 计算
  - `subsample_data()`: 子采样去相关
  - `compute_mbar_diagnostics()`: 计算诊断指标
  - `reweight_histogram()`: 重加权直方图

- **xtc_reader.py**: XTC 轨迹读取和分析

## 项目状态

**当前阶段**: 早期开发，核心功能框架已建立但大部分函数仍为 `pass` 占位符

**开发优先级**:
1. 实现 EDR 能量矩阵提取（`scripts/utils/edr_parser.py`）
2. 实现 LOG 交换历史解析（`scripts/utils/log_parser.py`）
3. 实现 MBAR 数据集构建（`scripts/03_build_dataset.py`）
4. 实现 MBAR 分析流程（`scripts/04_mbar_analysis.py`）
5. 添加单元测试和验证

## 编码规范

### 字符编码
- 所有 Python 文件使用 UTF-8 编码
- 直接使用中文注释和字符串，不要使用 Unicode 转义序列（如 `\u4e2d\u6587`）
- 文件头使用 `# -*- coding: utf-8 -*-`

### Git 提交
遵循 Conventional Commits 规范:
- `feat:` 新功能
- `fix:` 错误修复
- `refact:` 重构
- `docs:` 文档更新
- `test:` 测试相关

### 依赖管理原则
- 如果依赖安装失败（网络问题、权限问题等），**不要自动降级到备选方案**
- 明确告知用户需要安装哪些依赖，让用户手动处理
- 等待用户确认依赖安装成功后，再继续实现功能

## 重要注意事项

1. **能量矩阵提取的挑战**: GROMACS REST2 模拟的 EDR 文件不一定包含所有 λ 状态的能量。需要先检查 EDR 中是否有 Lambda 相关列，如果没有，需要提示用户使用 `gmx mdrun -rerun` 重新计算。

2. **数据一致性**: 确保 u_kn 矩阵和 replica_to_state_idx 映射的维度一致，尤其是时间步数和副本数。

3. **MBAR 诊断**: 始终检查 overlap 矩阵，如果相邻状态的 overlap < 0.03，说明温度间距设置不当。

4. **文档同步**: 完成关键功能或修正错误后，自动更新 README.md 和此文件。
