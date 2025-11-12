# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目简介

FReD（Free-energy Reweighting and Dataset Builder）是一个用于将 REST2-GROMACS 采样结果转换为无偏平衡系综的工具集，支持基于生成模型的自由能估计。

**项目状态**: ✅ **生产就绪** - 核心功能 100% 完成（~5570行代码）

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

# 步骤0: 数据验证
python scripts/00_data_validation.py

# 步骤1: 准备MBAR输入
python scripts/01_prepare_mbar.py

# 步骤2: MBAR计算
python scripts/02_run_mbar.py [--skip-subsample] [--target-state 0]

# 步骤3: 构建训练集
python scripts/03_build_training_dataset.py [--n-samples 10000]
```

### 辅助工具
```bash
# 激活环境
source /opt/anaconda3/bin/activate femto_test

# EDR文件检查
python scripts/tools/inspect_edr.py data/rep_0/prod.edr

# LOG文件分析
python scripts/tools/inspect_log.py data/rep_0/prod.log --n-replicas 5

# 轨迹分析
python scripts/tools/analyze_trajectory.py data/rep_0/prod.xtc data/rep_0/prod.gro --rmsd --rg
```

### 测试
```bash
# 激活环境
source /opt/anaconda3/bin/activate femto_test

# 运行所有测试
pytest tests/ -v

# 运行单个测试
pytest tests/test_validation.py -v
pytest tests/test_preprocessing.py -v
pytest tests/test_mbar.py -v
```

## 代码架构

### 数据流向
```
data/rep_* → 00_验证 → 01_准备 → 02_MBAR → 03_数据集 → 生成模型
  (REST2)    (检查)    (u_kn)    (权重)    (坐标)
```

详细流程：
```
   原始数据                验证报告              MBAR输入             MBAR输出            训练数据集
(GROMACS REST2)          (完整性检查)          (能量+映射)          (权重+诊断)        (坐标+能量)
      ↓                      ↓                    ↓                   ↓                  ↓
┌──────────────┐      ┌──────────────┐     ┌──────────────┐    ┌──────────────┐   ┌──────────────┐
│  prod.edr    │      │ Lambda检测   │     │  u_kn矩阵    │    │  MBAR权重    │   │ coordinates  │
│  prod.log    │  →   │ 文件完整性   │  →  │  N_k数组     │ →  │  自由能曲线  │ → │  energies    │
│  prod.xtc    │      │ MBAR就绪     │     │  状态映射    │    │  overlap矩阵 │   │  box向量     │
└──────────────┘      └──────────────┘     └──────────────┘    └──────────────┘   └──────────────┘
```

### 核心概念

#### 能量矩阵 u_kn
- **维度**: `(n_states, n_samples_total)`
- **含义**: `u_kn[k, n]` 表示第 n 个样本在第 k 个温度状态下的势能
- **单位**: kJ/mol
- **关键问题**: GROMACS EDR 文件不一定包含所有状态的能量，可能需要使用 `gmx mdrun -rerun` 重新计算

#### 副本到状态的映射 replica_to_state
- **维度**: `(n_cycles, n_replicas)`
- **含义**: `replica_to_state[i, j] = k` 表示第 i 个周期，第 j 个副本处于第 k 个温度状态
- **用途**: MBAR 需要知道每个样本来自哪个状态

#### MBAR 工作流
1. **子采样**: 使用 `pymbar.timeseries.detect_equilibration()` 和 `subsample_correlated_data()` 去除相关性
2. **MBAR 初始化**: `MBAR(u_kn, N_k)` 其中 N_k 是每个状态的样本数
3. **权重计算**: 获取目标状态（通常是状态 0）的权重用于重加权
4. **诊断**: 检查 overlap 矩阵和有效样本数（ESS）

### 工具模块 (scripts/utils/)

**已完成模块**:

- **validation.py** (617行): 数据完整性验证
  - `discover_replica_dirs()`: 自动发现副本目录
  - `check_file_exists()`: 文件存在性检查
  - `validate_edr_format()`: EDR格式验证
  - `detect_lambda_params()`: Lambda参数检测
  - `check_mbar_ready()`: MBAR就绪检查

- **io.py** (300行): 统一文件I/O接口
  - `read_edr_file()`: 读取EDR文件（基于panedr）
  - `load_trajectory()`: 加载XTC轨迹（基于mdtraj）
  - `save_npz()`: 保存NPZ文件
  - `load_npz()`: 加载NPZ文件

- **preprocessing.py** (600行): 能量提取和交换解析
  - `extract_multistate_energies()`: 从EDR提取能量矩阵
  - `parse_gromacs_log()`: 解析LOG交换记录
  - `build_replica_state_mapping()`: 重建replica→state映射
  - `calculate_exchange_statistics()`: 交换统计

- **mbar.py** (450行): MBAR核心计算
  - `subsample_timeseries()`: 时间序列去相关
  - `run_mbar()`: MBAR计算（基于pymbar 4.x）
  - `compute_diagnostics()`: 诊断分析（overlap、ESS、自由能）

- **visualization.py** (480行): 诊断可视化
  - `plot_overlap_matrix()`: Overlap热图
  - `plot_free_energy_profile()`: 自由能曲线
  - `plot_weights_distribution()`: 权重分布
  - `plot_energy_timeseries()`: 能量时间序列
  - `plot_all_diagnostics()`: 完整诊断套件

- **resampling.py** (420行): 重采样和构象提取
  - `resample_by_weights()`: MBAR权重重采样
  - `extract_configurations()`: 从XTC提取构象
  - `extract_unscaled_energies()`: 提取目标状态能量
  - `compute_dihedrals()`: 计算二面角特征

### 辅助工具 (scripts/tools/)

- **inspect_edr.py** (252行): EDR文件快速检查
  - 显示基本信息、热力学量、能量组成
  - 检测Lambda参数和多状态能量列
  - MBAR就绪检测

- **inspect_log.py** (244行): LOG文件交换分析
  - 交换摘要统计（轮次、尝试次数）
  - 副本迁移详情
  - 交换记录展示

- **analyze_trajectory.py** (276行): 轨迹分析工具
  - 显示轨迹基本信息（帧数、原子数、时间范围）
  - 计算RMSD（相对参考结构）
  - 计算回旋半径

## 项目状态

**当前阶段**: ✅ 生产就绪（100%完成）

**已完成模块** (~5570行代码):
- ✅ 数据验证系统 (validation.py, 617行)
- ✅ 统一I/O接口 (io.py, 300行)
- ✅ 预处理模块 (preprocessing.py, 600行)
- ✅ MBAR核心 (mbar.py, 450行)
- ✅ 可视化套件 (visualization.py, 480行)
- ✅ 重采样模块 (resampling.py, 420行)
- ✅ 4个主脚本 (00-03, 共933行)
- ✅ 3个工具脚本 (tools/, 共772行)

**下一步**: 真实数据测试和性能优化

## 编码规范

### 字符编码
- 所有 Python 文件使用 UTF-8 编码
- 直接使用中文注释和字符串，不要使用 Unicode 转义序列（如 `\u4e2d\u6587`）
- 文件头使用 `# -*- coding: utf-8 -*-`

### Git 提交
遵循 Conventional Commits 规范:
- `feat:` 新功能
- `fix:` 错误修复
- `refactor:` 重构
- `docs:` 文档更新
- `test:` 测试相关

### 依赖管理原则
- 如果依赖安装失败（网络问题、权限问题等），**不要自动降级到备选方案**
- 明确告知用户需要安装哪些依赖，让用户手动处理
- 等待用户确认依赖安装成功后，再继续实现功能

## 重要注意事项

1. **能量矩阵提取的挑战**: GROMACS REST2 模拟的 EDR 文件不一定包含所有 λ 状态的能量。需要先检查 EDR 中是否有 Lambda 相关列，如果没有，需要提示用户使用 `gmx mdrun -rerun` 重新计算。

2. **数据一致性**: 确保 u_kn 矩阵和 replica_to_state 映射的维度一致，尤其是时间步数和副本数。

3. **MBAR 诊断**: 始终检查 overlap 矩阵，如果相邻状态的 overlap < 0.03，说明温度间距设置不当。

4. **NPZ 格式**: 所有中间数据和最终数据集均使用 NPZ 格式存储，确保跨平台兼容性和高效加载。

5. **文档同步**: 完成关键功能或修正错误后，自动更新 README.md 和此文件。

## 数据格式规范

### mbar_input.npz
```python
{
    'u_kn': (n_states, n_samples_total) float64,  # 能量矩阵 [kJ/mol]
    'N_k': (n_states,) int,                       # 每状态样本数
    'replica_to_state': (n_cycles, n_replicas) int,  # 状态映射
    'lambda_values': (n_states,) float,           # Lambda值
    'n_cycles': int,
    'n_replicas': int,
    'n_states': int
}
```

### mbar_weights.npz
```python
{
    'weights': (n_samples_total,) float64,  # MBAR权重（归一化）
    'f_k': (n_states,) float64,             # 无量纲自由能 [kT]
    'df_k': (n_states,) float64,            # 自由能不确定度 [kT]
    'target_state': int
}
```

### training_dataset.npz
```python
{
    'coordinates': (n_samples, n_atoms, 3) float32,  # [nm]
    'energies': (n_samples,) float32,                # [kJ/mol]
    'box': (n_samples, 3, 3) float32,                # [nm]
    'n_atoms': int,
    'original_indices': (n_samples, 2) int,          # [replica_id, cycle_id]

    # 可选特征
    'phi': (n_samples, n_phi) float64,               # [弧度]
    'psi': (n_samples, n_psi) float64,               # [弧度]
    'chi1': (n_samples, n_chi1) float64              # [弧度]
}
```

## 参考资源

详细的技术文档请参考：
- [IMPLEMENTATION.md](docs/IMPLEMENTATION.md) - 完整技术文档（1790行）
- [PROGRESS.md](docs/PROGRESS.md) - 项目进度报告
