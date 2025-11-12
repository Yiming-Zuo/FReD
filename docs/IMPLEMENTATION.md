# FReD 项目重构实施文档

## 项目概览

**版本**: v0.2.0
**更新时间**: 2025-11-12
**当前阶段**: 第二阶段 - 核心功能实现

---

## 已完成工作（第一阶段）

### ✅ 清理和重组
- 删除空壳模块：`edr_parser.py`, `log_parser.py`, `mbar_utils.py`, `xtc_reader.py`
- 删除重复脚本：`read_edr_example.py`
- 备份旧模块到 `utils_backup/`
- 创建新的utils目录结构

### ✅ Utils模块实现

#### 1. `utils/validation.py` (617行)
**功能**: 完整的数据验证逻辑

**核心函数**:
```python
check_directory_structure(data_dir, expected_replicas) -> Dict
check_file_integrity(rep_dir, data_dir) -> Dict
validate_edr_file(edr_path) -> Dict
validate_xtc_file(xtc_path, gro_path) -> Dict
validate_log_file(log_path) -> Dict
analyze_lambda_parameters(data_dir, replica_dirs) -> Dict
run_full_validation(data_dir, expected_replicas) -> Dict
format_file_size(size_bytes) -> str
```

**关键特性**:
- Lambda参数自动检测（Lamb-SOL, Lamb-UNL, Lambda列）
- 多状态能量列检测（dH/dl, Energy-lambda-*等）
- 完整的REST2模拟判断
- MBAR就绪状态验证

#### 2. `utils/io.py` (约300行)
**功能**: 统一文件读写接口

**核心函数**:
```python
# 读取函数
read_edr_file(edr_path) -> pd.DataFrame
read_log_file(log_path) -> str
load_trajectory(xtc_path, top_path, stride) -> md.Trajectory
load_trajectory_frame(xtc_path, top_path, frame_index) -> md.Trajectory

# MBAR数据保存/加载
save_mbar_input(output_path, u_kn, N_k, replica_to_state, **metadata)
load_mbar_input(input_path) -> Dict

# MBAR权重保存/加载
save_mbar_weights(output_path, weights, f_k, df_k, sample_indices, **kwargs)
load_mbar_weights(input_path) -> Dict

# 训练数据集保存/加载 (NPZ格式)
save_training_dataset_npz(output_path, coordinates, energies, **kwargs)
load_training_dataset_npz(input_path) -> Dict
```

### ✅ 脚本重构

#### `00_data_validation.py` (665行 → 246行)
- 核心逻辑迁移到 `utils/validation.py`
- 保留完整的显示和报告功能
- 使用 `validation.run_full_validation()` 统一调用

---

## 正在进行（第二阶段）

### 🔄 `utils/preprocessing.py` - 能量提取和交换解析

#### 设计目标
1. **能量矩阵提取**: 从EDR文件提取多状态能量，构建u_kn矩阵
2. **交换记录解析**: 从LOG文件解析副本交换历史
3. **状态映射重建**: 重建replica_to_state_idx映射

#### 核心数据结构

##### 1. 能量矩阵 (u_kn)
```python
# 原始形式（从EDR读取）
u_raw[replica_id][cycle_id][state_id] = 势能 (kJ/mol)

# MBAR输入形式（需要转换）
u_kn[state_id, sample_global_id] = 势能 (kJ/mol)
# 其中 sample_global_id = cycle_id * n_replicas + replica_id

# 维度关系
n_cycles = EDR文件的时间步数
n_replicas = 副本数量
n_states = Lambda状态数量（从多状态能量列检测）
n_samples_total = n_cycles * n_replicas
```

##### 2. 副本状态映射 (replica_to_state_idx)
```python
replica_to_state_idx[cycle_id, replica_id] = state_id

# 说明
cycle_id: 交换周期索引 (0, 1, 2, ...)
replica_id: 副本索引 (0, 1, 2, ..., n_replicas-1)
state_id: Lambda状态索引 (0, 1, 2, ..., n_states-1)
```

##### 3. 交换记录 (exchange_records)
```python
exchange_records = {
    'cycle': [交换周期列表],
    'replica_pairs': [每个周期的交换对列表],
    'accepted': [每个交换是否接受],
    'probabilities': [接受概率]
}
```

#### 模块函数设计

##### 1. 能量提取模块

```python
def detect_lambda_states(edr_df: pd.DataFrame) -> List[float]:
    """
    从EDR DataFrame检测Lambda状态

    检测策略:
    1. 查找多状态能量列（dH/dl-lambda-*或Energy-lambda-*）
    2. 从列名提取Lambda值
    3. 排序并返回唯一值

    Returns:
        sorted list of lambda values
    """
    pass


def extract_multistate_energies(edr_df: pd.DataFrame,
                                 lambda_values: List[float]) -> np.ndarray:
    """
    从EDR DataFrame提取多状态能量

    Parameters:
        edr_df: panedr读取的DataFrame
        lambda_values: Lambda状态列表

    Returns:
        u_matrix: shape=(n_cycles, n_states), 单个副本的能量矩阵

    实现细节:
    - 匹配列名模式：'dH/dl-lambda-{i}' 或 'Energy-lambda-{i}'
    - 如果缺少某些Lambda列，返回错误提示用户rerun
    """
    pass


def extract_energy_matrix(data_dir: str = 'data',
                          replica_dirs: Optional[List[str]] = None,
                          lambda_values: Optional[List[float]] = None) -> Dict:
    """
    从所有副本的EDR文件提取完整能量矩阵

    工作流程:
    1. 如果lambda_values未提供，从validation报告或第一个EDR检测
    2. 遍历所有副本，提取多状态能量
    3. 验证所有副本的时间步数一致
    4. 构建完整u_kn矩阵: (n_states, n_samples_total)

    Returns:
        {
            'u_kn': np.ndarray,  # (n_states, n_samples_total)
            'N_k': np.ndarray,   # (n_states,) 每个状态的样本数
            'lambda_values': List[float],
            'n_cycles': int,
            'n_replicas': int,
            'n_states': int,
            'cycle_indices': np.ndarray,  # 每个样本对应的cycle_id
            'replica_indices': np.ndarray,  # 每个样本对应的replica_id
            'status': str,
            'warnings': List[str]
        }
    """
    pass


def validate_energy_matrix(u_kn: np.ndarray,
                           N_k: np.ndarray) -> Dict:
    """
    验证能量矩阵的物理合理性

    检查项:
    1. 是否有NaN或Inf
    2. 能量范围是否合理（-1e6 ~ 1e6 kJ/mol）
    3. 不同状态的能量分布是否重叠（overlap检查）
    4. 每个状态的样本数是否足够（建议>100）

    Returns:
        {
            'is_valid': bool,
            'has_nan': bool,
            'has_inf': bool,
            'energy_range': Tuple[float, float],
            'issues': List[str],
            'warnings': List[str]
        }
    """
    pass
```

##### 2. 交换记录解析模块

```python
def parse_exchange_line(line: str) -> Optional[Dict]:
    """
    解析单行副本交换记录

    LOG格式示例:
    "Repl ex  0    1 x  2    3 x"
    "Repl ex  1 x  0    2 x  3"

    解析规则:
    - "Repl ex" 后面跟副本索引
    - "x" 表示该副本参与交换
    - 连续的两个带"x"的副本索引表示一个交换对

    Returns:
        {
            'replica_pairs': [(0, 1), (2, 3)],  # 交换对
            'step': int  # 时间步（如果能解析）
        }
        或 None（如果不是交换记录行）
    """
    pass


def parse_gromacs_log(log_path: str) -> Dict:
    """
    解析GROMACS LOG文件中的副本交换记录

    工作流程:
    1. 读取LOG文件
    2. 查找 "Repl ex" 或 "Replica exchange" 行
    3. 逐行解析交换记录
    4. 提取时间步和接受概率（如果有）

    Returns:
        {
            'exchanges': List[Dict],  # 每次交换的记录
            'n_exchanges': int,
            'total_steps': int,
            'exchange_interval': int,  # 交换间隔（步数）
            'status': str
        }
    """
    pass


def build_replica_state_mapping(exchange_records: Dict,
                                 n_replicas: int,
                                 n_cycles: int,
                                 initial_state_assignment: Optional[np.ndarray] = None) -> np.ndarray:
    """
    从交换记录重建replica_to_state_idx映射

    算法:
    1. 初始化: replica_to_state_idx[0, :] = initial_state_assignment
       （如果未提供，假设replica_id == state_id）
    2. 遍历每次交换:
       - 对于交换对(r1, r2)，交换它们的state_id
       - 更新replica_to_state_idx[cycle+1, :]
    3. 填充未交换周期（线性插值或前向填充）

    Parameters:
        exchange_records: parse_gromacs_log()的输出
        n_replicas: 副本数量
        n_cycles: 总周期数（通常 = EDR时间步数）
        initial_state_assignment: 初始状态分配，shape=(n_replicas,)

    Returns:
        replica_to_state_idx: shape=(n_cycles, n_replicas)
    """
    pass


def calculate_exchange_statistics(exchange_records: Dict) -> Dict:
    """
    计算交换统计信息

    Returns:
        {
            'total_exchanges': int,
            'total_attempts': int,
            'global_acceptance_rate': float,
            'pairwise_acceptance_rates': Dict[Tuple[int, int], float],
            'replica_mobility': np.ndarray,  # 每个副本访问的状态数
            'state_coverage': np.ndarray  # 每个状态被访问的次数
        }
    """
    pass
```

##### 3. 数据整合模块

```python
def prepare_mbar_input(data_dir: str = 'data',
                       validation_report_path: Optional[str] = None) -> Dict:
    """
    准备MBAR输入数据（整合01的完整流程）

    工作流程:
    1. 加载validation报告（如果提供）
    2. 提取能量矩阵
    3. 解析交换记录
    4. 构建状态映射
    5. 验证数据一致性
    6. 返回完整MBAR输入

    Returns:
        {
            'u_kn': np.ndarray,
            'N_k': np.ndarray,
            'replica_to_state': np.ndarray,
            'temperatures': np.ndarray,
            'lambda_values': List[float],
            'n_cycles': int,
            'n_replicas': int,
            'n_states': int,
            'exchange_statistics': Dict,
            'validation': Dict,
            'status': str
        }
    """
    pass


def verify_data_consistency(u_kn: np.ndarray,
                            replica_to_state: np.ndarray,
                            N_k: np.ndarray) -> Dict:
    """
    验证u_kn和replica_to_state的维度一致性

    检查项:
    1. u_kn.shape[1] == replica_to_state的总样本数
    2. N_k的总和 == u_kn.shape[1]
    3. replica_to_state的状态索引范围 == [0, n_states-1]
    4. 时间步数一致

    Returns:
        {
            'is_consistent': bool,
            'issues': List[str]
        }
    """
    pass
```

#### 关键实现细节

##### EDR多状态能量列检测

```python
# 常见列名模式（按优先级）
MULTISTATE_PATTERNS = [
    r'dH/dl-lambda-(\d+)',           # GROMACS expanded ensemble
    r'Energy-lambda-(\d+)',          # 自定义能量列
    r'U-lambda-(\d+)',               # 替代命名
    r'dE/dl-lambda-(\d+)',           # 能量导数
]

# 检测示例
import re
for col in edr_df.columns:
    for pattern in MULTISTATE_PATTERNS:
        match = re.search(pattern, col)
        if match:
            lambda_index = int(match.group(1))
            # 记录该列对应的Lambda索引
```

##### LOG交换记录正则表达式

```python
# GROMACS LOG格式
# "Repl ex  0    1 x  2    3 x"
# "Repl ex  1 x  0    2 x  3"

import re

EXCHANGE_LINE_PATTERN = r'Repl\s+ex\s+((?:\d+\s*x?\s*)+)'

def parse_exchange_line(line):
    match = re.search(EXCHANGE_LINE_PATTERN, line)
    if not match:
        return None

    # 提取所有副本索引和标记
    tokens = match.group(1).split()
    replicas_with_x = []

    i = 0
    while i < len(tokens):
        if tokens[i].isdigit():
            replica_id = int(tokens[i])
            has_x = (i+1 < len(tokens) and tokens[i+1] == 'x')
            if has_x:
                replicas_with_x.append(replica_id)
                i += 2
            else:
                i += 1

    # 构建交换对（连续的两个有x的副本）
    pairs = [(replicas_with_x[i], replicas_with_x[i+1])
             for i in range(0, len(replicas_with_x)-1, 2)]

    return {'replica_pairs': pairs}
```

##### 状态映射重建算法

```python
def build_replica_state_mapping(exchanges, n_replicas, n_cycles):
    # 初始化：假设replica_id == state_id
    mapping = np.zeros((n_cycles, n_replicas), dtype=int)
    mapping[0, :] = np.arange(n_replicas)

    # 遍历交换记录
    for cycle_id, exchange in enumerate(exchanges, start=1):
        # 复制上一周期的映射
        mapping[cycle_id, :] = mapping[cycle_id - 1, :]

        # 应用交换
        for r1, r2 in exchange['replica_pairs']:
            # 交换两个副本的状态
            mapping[cycle_id, r1], mapping[cycle_id, r2] = \
                mapping[cycle_id, r2], mapping[cycle_id, r1]

    return mapping
```

#### 错误处理和边界情况

1. **EDR缺少多状态能量列**
   ```python
   if not has_multistate_energy:
       raise ValueError(
           "EDR文件缺少多状态能量列。\n"
           "请使用以下命令重新计算:\n"
           "  gmx mdrun -s prod.tpr -rerun prod.xtc -dhdl dhdl.xvg"
       )
   ```

2. **LOG缺少交换记录**
   ```python
   if len(exchanges) == 0:
       warnings.warn("LOG文件中未找到副本交换记录，假设无交换")
       # 使用静态映射：replica_id == state_id
   ```

3. **时间步数不一致**
   ```python
   if len(set(n_steps_list)) > 1:
       raise ValueError(
           f"不同副本的时间步数不一致: {dict(zip(replica_dirs, n_steps_list))}\n"
           "请检查模拟是否完整"
       )
   ```

4. **能量矩阵包含NaN**
   ```python
   if np.isnan(u_kn).any():
       nan_positions = np.argwhere(np.isnan(u_kn))
       raise ValueError(
           f"能量矩阵包含{len(nan_positions)}个NaN值\n"
           f"位置: state={nan_positions[0][0]}, sample={nan_positions[0][1]}"
       )
   ```

---

## 待实现（第三阶段）

### `utils/mbar.py` - MBAR核心计算

#### 核心函数设计

```python
def subsample_timeseries(u_k: np.ndarray,
                        method: str = 'auto') -> Tuple[np.ndarray, int, int]:
    """
    对时间序列去相关并子采样

    使用pymbar的时间序列分析:
    - detect_equilibration(): 检测平衡化时间
    - statistical_inefficiency(): 计算统计无效性（相关时间）
    - subsample_correlated_data(): 子采样为独立样本

    Returns:
        (subsampled_data, t0, g)
        t0: 平衡化时间
        g: 统计无效性（相关时间）
    """
    pass


def run_mbar(u_kn: np.ndarray,
             N_k: np.ndarray,
             target_state: int = 0,
             **mbar_kwargs) -> Tuple['MBAR', np.ndarray]:
    """
    运行MBAR计算

    Parameters:
        u_kn: shape=(n_states, n_samples_total)
        N_k: shape=(n_states,)
        target_state: 目标状态索引（通常是0，对应λ=1, 300K）

    Returns:
        (mbar_object, weights)
        weights: 目标状态的MBAR权重
    """
    pass


def compute_diagnostics(mbar: 'MBAR') -> Dict:
    """
    计算MBAR诊断指标

    Returns:
        {
            'overlap_matrix': np.ndarray,
            'min_overlap': float,
            'effective_sample_size': float,
            'free_energies': np.ndarray,
            'uncertainties': np.ndarray,
            'is_converged': bool,
            'warnings': List[str]
        }
    """
    pass
```

### `utils/visualization.py` - 诊断可视化

```python
def plot_overlap_matrix(overlap: np.ndarray, output_path: str)
def plot_free_energy_profile(f_k: np.ndarray, df_k: np.ndarray, output_path: str)
def plot_weights_distribution(weights: np.ndarray, output_path: str)
def plot_energy_timeseries(u_kn: np.ndarray, output_path: str)
```

### `utils/resampling.py` - 重采样和数据集构建

```python
def resample_by_weights(weights: np.ndarray, n_samples: int) -> np.ndarray
def extract_configurations(xtc_paths: List[str], indices: np.ndarray) -> np.ndarray
def compute_auxiliary_features(traj: md.Trajectory) -> Dict
```

---

## 主脚本实现顺序

### 1. `01_prepare_mbar.py`
- 调用 `validation.run_full_validation()`
- 调用 `preprocessing.prepare_mbar_input()`
- 调用 `io.save_mbar_input()`
- 显示能量矩阵统计和交换统计

### 2. `02_run_mbar.py`
- 调用 `io.load_mbar_input()`
- 调用 `mbar.subsample_timeseries()`
- 调用 `mbar.run_mbar()`
- 调用 `mbar.compute_diagnostics()`
- 调用 `visualization.plot_*()` 生成诊断图
- 调用 `io.save_mbar_weights()`

### 3. `03_build_training_dataset.py`
- 调用 `io.load_mbar_weights()`
- 调用 `resampling.resample_by_weights()`
- 调用 `resampling.extract_configurations()`
- 调用 `resampling.compute_auxiliary_features()`
- 调用 `io.save_training_dataset_npz()`

---

## 数据流图

```
data/rep_*/
├── prod.edr ──┐
├── prod.log ──┼──> 01_prepare_mbar.py
├── prod.xtc  │         ↓
└── prod.gro ─┘   outputs/mbar_input.npz
                        ↓
                  02_run_mbar.py
                        ↓
                  outputs/mbar_weights.npz
                  outputs/mbar_diagnostics.json
                  outputs/figures/*.png
                        ↓
                  03_build_training_dataset.py
                        ↓
                  outputs/training_dataset.npz
```

---

## 下一轮对话要点

1. **继续实现preprocessing.py的核心函数**
2. **创建01_prepare_mbar.py主脚本**
3. **实现mbar.py和visualization.py**
4. **创建02_run_mbar.py主脚本**
5. **测试完整流程**

---

## 参考资料

### pymbar官方文档
- MBAR基本用法: https://pymbar.readthedocs.io/en/master/mbar.html
- 时间序列分析: https://pymbar.readthedocs.io/en/master/timeseries.html

### GROMACS文档
- EDR文件格式: https://manual.gromacs.org/current/reference-manual/file-formats.html#edr
- REST2模拟: https://manual.gromacs.org/current/reference-manual/algorithms/replica-exchange.html

### 相关论文
- MBAR: Shirts & Chodera, JCP 2008
- REST2: Wang et al., JACS 2011
