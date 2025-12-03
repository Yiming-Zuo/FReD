# 实施计划：添加 Rerun XVG 文件支持

## 背景

当前 FReD 工具仅支持从 EDR 文件读取多状态能量，但在实际使用中：
- GROMACS REST2 模拟的 EDR 文件不一定包含所有 λ 状态的能量
- 需要使用 `gmx mdrun -rerun` 重新计算，生成 XVG 格式的能量文件
- `data_0` 目录已有 25 个 rerun XVG 文件：`rerun_r{0-4}_l{0-4}_Potential.xvg`

## 目标

修改代码支持从 rerun 生成的 XVG 文件读取多状态能量，实现：
1. 自动检测数据源（EDR 或 XVG）
2. 统一的能量矩阵提取接口
3. 向后兼容现有 EDR 工作流

## XVG 文件格式分析

基于实际文件 `data_0/rerun_r0_l0_Potential.xvg` 的格式：

```
# 注释行（以 # 开头）- 包含元数据
# Created by: gmx energy
# Command line: gmx_mpi energy -f rerun_r0_l0.edr -o rerun_r0_l0_Potential.xvg

# GROMACS 格式标记行（以 @ 开头）
@    title "GROMACS Energies"
@    xaxis  label "Time (ps)"
@    yaxis  label "(kJ/mol)"
@TYPE xy
@ s0 legend "Potential"

# 数据行（空格分隔）
    0.000000  -14380.977539
  100.000000  -14471.011719
  200.000000  -14599.801758
```

**关键特征**：
- 文件命名：`rerun_r{replica_id}_l{lambda_idx}_Potential.xvg`
- 单列能量值（仅 Potential）
- 时间列 + 能量列
- 跳过以 `#` 和 `@` 开头的行

## 实施方案

### 阶段 1：基础设施（I/O 模块）

#### 1.1 在 `scripts/utils/io.py` 中添加 XVG 读取函数

**位置**：`io.py` 第 44 行后（`read_edr_file` 函数之后）

**新增函数**：

```python
def read_xvg_file(xvg_path: Union[str, Path]) -> pd.DataFrame:
    """
    读取 GROMACS XVG 文件

    Parameters
    ----------
    xvg_path : str or Path
        XVG 文件路径

    Returns
    -------
    df : pd.DataFrame
        包含时间和数据列的 DataFrame
        列名：['Time'] + 从 @sN legend 提取的列名

    Notes
    -----
    XVG 文件格式：
    - # 开头：注释行（跳过）
    - @ 开头：格式标记行（解析图例信息）
    - 数据行：空格分隔的数值

    示例：
    >>> df = read_xvg_file('rerun_r0_l0_Potential.xvg')
    >>> df.columns
    ['Time', 'Potential']
    """
```

**实现逻辑**：
1. 打开文件，逐行读取
2. 解析 `@ s<N> legend "<name>"` 提取列名
3. 跳过所有 `#` 和 `@` 开头的行
4. 使用 `pd.read_csv` 读取数据行（空格分隔）
5. 返回 DataFrame，列名为 `['Time'] + legend_names`

#### 1.2 添加工具脚本 `scripts/tools/inspect_xvg.py`

**功能**：
- 显示 XVG 文件基本信息（时间范围、数据列、统计值）
- 验证文件格式
- 检测是否为 rerun 文件（从文件名或注释行）

**参考**：模仿 `inspect_edr.py` 的代码风格

---

### 阶段 2：能量提取（Preprocessing 模块）

#### 2.1 在 `scripts/utils/preprocessing.py` 中添加 XVG 能量提取函数

**位置**：`preprocessing.py` 第 131 行后（`extract_multistate_energies` 函数之后）

**新增函数 1**：

```python
def extract_multistate_energies_from_xvg(
    data_dir: Union[str, Path],
    replica_dirs: List[str],
    n_states: int
) -> np.ndarray:
    """
    从 rerun 生成的 XVG 文件提取多状态能量矩阵

    Parameters
    ----------
    data_dir : str or Path
        数据目录路径（包含 rerun_r*_l*.xvg 文件）
    replica_dirs : list of str
        副本目录列表（用于确定副本数量）
    n_states : int
        Lambda 状态数量

    Returns
    -------
    u_replicas : list of np.ndarray
        每个副本的能量矩阵列表
        每个矩阵形状：(n_cycles, n_states)

    文件命名约定
    -----------
    rerun_r{replica_id}_l{lambda_idx}_Potential.xvg

    示例：
    - rerun_r0_l0_Potential.xvg  # 副本0在状态0的能量
    - rerun_r0_l1_Potential.xvg  # 副本0在状态1的能量
    """
```

**实现逻辑**：
1. 对每个副本：
   - 初始化 `u_matrix` 为 `(n_cycles, n_states)`
   - 对每个状态：
     - 构建文件名：`f"rerun_r{rep_idx}_l{state_idx}_Potential.xvg"`
     - 使用 `io.read_xvg_file()` 读取
     - 提取 Potential 列：`u_matrix[:, state_idx] = df['Potential'].values`
   - 验证所有状态的周期数一致
2. 返回 `u_replicas` 列表

**新增函数 2**：

```python
def detect_xvg_file_pattern(data_dir: Union[str, Path]) -> Dict:
    """
    检测数据目录中是否存在 rerun XVG 文件

    Parameters
    ----------
    data_dir : str or Path
        数据目录路径

    Returns
    -------
    result : dict
        {
            'has_xvg': bool,  # 是否存在 XVG 文件
            'n_replicas': int,  # 副本数
            'n_states': int,  # 状态数
            'xvg_files': list[Path]  # 所有 XVG 文件路径
        }

    检测逻辑
    -------
    查找匹配 rerun_r*_l*_Potential.xvg 的文件
    从文件名提取最大副本ID和状态ID
    """
```

#### 2.2 修改 `extract_energy_matrix` 函数添加数据源选择逻辑

**位置**：`preprocessing.py` 第 133 行（函数签名）

**修改内容**：

1. **添加参数**：
```python
def extract_energy_matrix(
    data_dir: Union[str, Path] = 'data',
    replica_dirs: Optional[List[str]] = None,
    n_states: Optional[int] = None,
    energy_source: str = 'auto'  # ← 新参数
) -> Dict:
    """
    ...

    Parameters
    ----------
    ...
    energy_source : str, default='auto'
        能量数据源选择：
        - 'auto': 自动选择（优先 EDR，无则尝试 XVG）
        - 'edr': 仅从 EDR 文件读取
        - 'xvg': 仅从 rerun XVG 文件读取

    ...
    """
```

2. **在函数开头添加数据源选择逻辑**（第 179 行前）：

```python
# 2. 确定能量数据源
if energy_source == 'auto':
    # 尝试从 EDR 检测多状态能量
    first_edr = data_path / replica_dirs[0] / 'prod.edr'
    if first_edr.exists():
        edr_df = io.read_edr_file(first_edr)
        lambda_values_edr = detect_lambda_states(edr_df)
        if lambda_values_edr:
            energy_source = 'edr'
            logger.info("检测到 EDR 中包含多状态能量，使用 EDR 数据源")
        else:
            # EDR 无多状态能量，检查 XVG
            xvg_info = detect_xvg_file_pattern(data_path)
            if xvg_info['has_xvg']:
                energy_source = 'xvg'
                logger.info("EDR 不包含多状态能量，使用 rerun XVG 数据源")
            else:
                raise ValueError(
                    "未找到可用的能量数据源。\n"
                    "EDR 文件不包含多状态能量，且未找到 rerun XVG 文件。\n"
                    "请使用 gmx mdrun -rerun 生成 XVG 文件。"
                )
    else:
        # EDR 不存在，尝试 XVG
        xvg_info = detect_xvg_file_pattern(data_path)
        if xvg_info['has_xvg']:
            energy_source = 'xvg'
            logger.info("未找到 EDR 文件，使用 rerun XVG 数据源")
        else:
            raise ValueError("未找到 EDR 或 XVG 能量文件")

logger.info(f"使用能量数据源: {energy_source.upper()}")
```

3. **修改能量提取部分**（替换第 199-217 行）：

```python
# 3. 根据数据源提取能量矩阵
if energy_source == 'edr':
    # 原有 EDR 提取逻辑（保持不变）
    if n_states is None:
        first_edr = data_path / replica_dirs[0] / 'prod.edr'
        edr_df = io.read_edr_file(first_edr)
        lambda_values = detect_lambda_states(edr_df)
        n_states = len(lambda_values)
    else:
        lambda_values = list(range(n_states))

    u_replicas = []
    n_cycles_list = []

    for rep_dir in replica_dirs:
        edr_path = data_path / rep_dir / 'prod.edr'
        edr_df = io.read_edr_file(edr_path)
        u_matrix = extract_multistate_energies(edr_df, n_states)
        u_replicas.append(u_matrix)
        n_cycles_list.append(len(edr_df))

elif energy_source == 'xvg':
    # 新增 XVG 提取逻辑
    if n_states is None:
        xvg_info = detect_xvg_file_pattern(data_path)
        n_states = xvg_info['n_states']
        lambda_values = list(range(n_states))
    else:
        lambda_values = list(range(n_states))

    u_replicas = extract_multistate_energies_from_xvg(
        data_path, replica_dirs, n_states
    )
    n_cycles_list = [u.shape[0] for u in u_replicas]

# 后续逻辑保持不变...
```

#### 2.3 修改 `prepare_mbar_input` 传递参数

**位置**：`preprocessing.py` 第 550 行（`prepare_mbar_input` 函数）

**修改内容**：

1. 添加 `energy_source` 参数到函数签名
2. 传递给 `extract_energy_matrix`：
```python
energy_data = extract_energy_matrix(
    data_dir=data_dir,
    replica_dirs=replica_dirs,
    n_states=n_states,
    energy_source=energy_source  # ← 传递参数
)
```

---

### 阶段 3：脚本集成

#### 3.1 修改 `scripts/01_prepare_mbar.py` 添加命令行参数

**位置**：第 78 行（`main` 函数）

**修改内容**：

1. 添加 argparse 解析：
```python
import argparse

def main():
    parser = argparse.ArgumentParser(
        description='准备 MBAR 输入数据'
    )
    parser.add_argument(
        '--energy-source',
        choices=['auto', 'edr', 'xvg'],
        default='auto',
        help='能量数据源：auto（自动检测）、edr（仅EDR）、xvg（仅XVG）'
    )
    args = parser.parse_args()

    # ... 原有代码 ...
```

2. 传递参数给 `prepare_mbar_input`：
```python
mbar_input = preprocessing.prepare_mbar_input(
    data_dir=data_dir,
    validation_report_path=str(validation_report_path) if validation_report_path.exists() else None,
    energy_source=args.energy_source  # ← 传递参数
)
```

3. 在输出中显示数据源：
```python
print(f"{BLUE}[INFO] 能量数据源: {args.energy_source.upper()}{RESET}")
```

---

### 阶段 4：测试

#### 4.1 单元测试

**创建新文件**：`tests/test_xvg_reader.py`

**测试用例**：
1. `test_read_xvg_file()` - 读取单个 XVG 文件
2. `test_detect_xvg_pattern()` - 检测 XVG 文件模式
3. `test_extract_from_xvg()` - 从 XVG 提取能量矩阵
4. `test_extract_energy_matrix_with_xvg()` - 端到端测试

**测试数据**：使用 `data_0/rerun_r*_l*_Potential.xvg` 实际文件

#### 4.2 集成测试

**修改**：`tests/test_mbar.py`

**新增测试**：
- 测试使用 XVG 数据源运行完整 MBAR 工作流
- 验证 EDR 和 XVG 提取的能量矩阵一致性（如果两者都可用）

---

### 阶段 5：验证

#### 5.1 在 `data_0` 上验证新功能

**验证步骤**：

1. **自动模式**（应选择 XVG）：
```bash
source /opt/anaconda3/bin/activate femto_test && \
python scripts/01_prepare_mbar.py
```

2. **显式 XVG 模式**：
```bash
source /opt/anaconda3/bin/activate femto_test && \
python scripts/01_prepare_mbar.py --energy-source xvg
```

3. **检查输出**：
```bash
source /opt/anaconda3/bin/activate femto_test && \
python -c "
import numpy as np
data = np.load('outputs/mbar_input.npz')
print('u_kn shape:', data['u_kn'].shape)
print('N_k:', data['N_k'])
print('n_states:', data['n_states'])
print('n_replicas:', data['n_replicas'])
print('n_cycles:', data['n_cycles'])
"
```

4. **运行后续步骤**：
```bash
source /opt/anaconda3/bin/activate femto_test && \
python scripts/02_run_mbar.py
```

#### 5.2 验证诊断输出

**检查项**：
- 能量矩阵形状正确
- 没有 NaN 或 Inf 值
- Overlap 矩阵合理
- 有效样本数（ESS）充足

---

## 关键文件修改清单

| 文件 | 修改类型 | 关键改动 |
|------|---------|---------|
| `scripts/utils/io.py` | 新增函数 | `read_xvg_file()` |
| `scripts/utils/preprocessing.py` | 新增函数 | `extract_multistate_energies_from_xvg()`, `detect_xvg_file_pattern()` |
| `scripts/utils/preprocessing.py` | 修改函数 | `extract_energy_matrix()` 添加数据源选择逻辑 |
| `scripts/utils/preprocessing.py` | 修改函数 | `prepare_mbar_input()` 添加 `energy_source` 参数 |
| `scripts/01_prepare_mbar.py` | 添加参数 | 命令行参数 `--energy-source` |
| `scripts/tools/inspect_xvg.py` | 新增文件 | XVG 文件检查工具 |
| `tests/test_xvg_reader.py` | 新增文件 | XVG 读取功能单元测试 |

---

## 向后兼容性

**保证**：
- 现有 EDR 工作流完全不受影响
- `energy_source='auto'` 默认优先使用 EDR
- 仅当 EDR 缺少多状态能量时才自动切换到 XVG
- 所有现有测试用例继续通过

---

## 风险和注意事项

### 风险 1：XVG 文件命名不一致
**缓解**：
- 在 `detect_xvg_file_pattern()` 中使用正则表达式灵活匹配
- 如果检测失败，提供清晰的错误提示和命名规范

### 风险 2：XVG 时间步数与 LOG 交换记录不匹配
**缓解**：
- 在 `extract_multistate_energies_from_xvg()` 中验证周期数
- 与 LOG 文件中的交换轮次对比，如果不匹配则警告

### 风险 3：XVG 文件损坏或格式异常
**缓解**：
- 在 `read_xvg_file()` 中添加健壮的错误处理
- 捕获并报告具体的解析错误（行号、内容）

---

## 实施顺序建议

**推荐顺序**（按依赖关系）：

1. **阶段 1.1**：`io.read_xvg_file()` - 基础 I/O 功能
2. **阶段 2.2**：`preprocessing.detect_xvg_file_pattern()` - 文件检测
3. **阶段 2.1**：`preprocessing.extract_multistate_energies_from_xvg()` - 能量提取
4. **阶段 4.1**：单元测试（验证前三步）
5. **阶段 2.2**：修改 `extract_energy_matrix()` - 集成数据源选择
6. **阶段 2.3**：修改 `prepare_mbar_input()` - 参数传递
7. **阶段 3.1**：修改 `01_prepare_mbar.py` - 脚本集成
8. **阶段 5**：在 `data_0` 上完整验证
9. **阶段 1.2**：`tools/inspect_xvg.py` - 辅助工具（可选）

---

## 预期成果

完成后，工具将支持：

1. **自动数据源检测**：
   - EDR 包含多状态能量 → 使用 EDR
   - EDR 不包含多状态能量 → 自动切换到 XVG

2. **手动指定数据源**：
   - `--energy-source edr` 强制使用 EDR（如果失败则报错）
   - `--energy-source xvg` 强制使用 XVG（适用于 rerun 数据）

3. **统一接口**：
   - 无论数据源如何，输出的 `mbar_input.npz` 格式完全一致
   - 下游步骤（02, 03 脚本）无需任何修改

4. **用户友好**：
   - 清晰的日志输出，显示使用的数据源
   - 详细的错误提示，指导用户如何生成缺失的数据
