# -*- coding: utf-8 -*-
"""
数据预处理模块

功能：
1. 能量矩阵提取：从EDR文件提取多状态能量，构建u_kn矩阵
2. 交换记录解析：从LOG文件解析副本交换历史
3. 状态映射重建：重建replica_to_state_idx映射

核心数据结构说明：
- u_kn: (n_states, n_samples_total) MBAR输入能量矩阵
- N_k: (n_states,) 每个状态的样本数
- replica_to_state: (n_cycles, n_replicas) 副本到状态的映射
"""

import re
import numpy as np
import pandas as pd
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union
import logging

logger = logging.getLogger(__name__)

# 多状态能量列名模式（按优先级）
MULTISTATE_PATTERNS = [
    r'dH/dl-lambda-(\d+)',      # GROMACS expanded ensemble
    r'Energy-lambda-(\d+)',     # 自定义能量列
    r'U-lambda-(\d+)',          # 替代命名
    r'dE/dl-lambda-(\d+)',      # 能量导数
]

# LOG交换记录正则表达式
EXCHANGE_LINE_PATTERN = r'Repl\s+ex\s+((?:\d+\s*x?\s*)+)'


# ==================== 能量提取模块 ====================

def detect_lambda_states(edr_df: pd.DataFrame) -> List[float]:
    """
    从EDR DataFrame检测Lambda状态索引

    ⚠️  重要：此函数返回Lambda状态的索引（0, 1, 2, ...），而不是真实的λ值。
    要获取真实的λ值或温度，需要从tpr文件或mdp文件中读取。

    Parameters
    ----------
    edr_df : pd.DataFrame
        panedr读取的EDR数据

    Returns
    -------
    lambda_indices : list of int
        Lambda状态索引列表 [0, 1, 2, ...]（不是真实的λ值）
    """
    lambda_indices = []

    for col in edr_df.columns:
        for pattern in MULTISTATE_PATTERNS:
            match = re.search(pattern, col)
            if match:
                lambda_idx = int(match.group(1))
                lambda_indices.append(lambda_idx)
                break  # 找到一个模式就跳过其他模式

    if not lambda_indices:
        return []

    # 假设Lambda索引连续，从0开始
    n_states = max(lambda_indices) + 1
    lambda_values = list(range(n_states))

    logger.info(f"检测到 {n_states} 个Lambda状态（返回索引，非真实λ值）")
    logger.warning(
        "⚠️ 返回的是Lambda状态索引 [0, 1, 2, ...]，不是真实的λ值或温度。"
    )

    return lambda_values


def extract_multistate_energies(edr_df: pd.DataFrame,
                                 n_states: int) -> np.ndarray:
    """
    从EDR DataFrame提取多状态能量

    Parameters
    ----------
    edr_df : pd.DataFrame
        panedr读取的EDR数据
    n_states : int
        Lambda状态数量

    Returns
    -------
    u_matrix : np.ndarray
        shape=(n_cycles, n_states), 单个副本的能量矩阵

    Raises
    ------
    ValueError
        如果缺少必需的多状态能量列
    """
    n_cycles = len(edr_df)
    u_matrix = np.zeros((n_cycles, n_states))

    # 尝试每个模式，找到对应的列
    for state_idx in range(n_states):
        col_found = False

        for pattern_template in MULTISTATE_PATTERNS:
            # 构建该状态的列名模式（替换(\d+)为具体索引）
            pattern = pattern_template.replace(r'(\d+)', str(state_idx))

            # 查找匹配的列
            matching_cols = [col for col in edr_df.columns if re.search(pattern, col)]

            if matching_cols:
                col_name = matching_cols[0]
                u_matrix[:, state_idx] = edr_df[col_name].values
                col_found = True
                logger.debug(f"状态{state_idx}: 使用列 '{col_name}'")
                break

        if not col_found:
            raise ValueError(
                f"未找到Lambda状态{state_idx}的能量列。\n"
                f"请检查EDR文件是否包含多状态能量，或使用 gmx mdrun -rerun 重新计算。"
            )

    return u_matrix


def extract_energy_matrix(data_dir: Union[str, Path] = 'data',
                          replica_dirs: Optional[List[str]] = None,
                          n_states: Optional[int] = None) -> Dict:
    """
    从所有副本的EDR文件提取完整能量矩阵

    Parameters
    ----------
    data_dir : str or Path
        数据目录路径
    replica_dirs : list of str, optional
        副本目录列表，如果为None则自动发现
    n_states : int, optional
        Lambda状态数量，如果为None则自动检测

    Returns
    -------
    result : dict
        {
            'u_kn': np.ndarray,  # (n_states, n_samples_total)
            'N_k': np.ndarray,   # (n_states,)
            'lambda_values': List[float],
            'n_cycles': int,
            'n_replicas': int,
            'n_states': int,
            'cycle_indices': np.ndarray,
            'replica_indices': np.ndarray,
            'status': str,
            'warnings': List[str]
        }
    """
    from . import io, validation

    data_path = Path(data_dir)
    warnings_list = []

    # 1. 发现副本目录
    if replica_dirs is None:
        dir_check = validation.check_directory_structure(data_dir)
        replica_dirs = dir_check['found']
        if not replica_dirs:
            raise ValueError("未找到任何副本目录")

    n_replicas = len(replica_dirs)
    logger.info(f"发现 {n_replicas} 个副本目录: {replica_dirs}")

    # 2. 检测Lambda状态（从第一个EDR）
    if n_states is None:
        first_edr = data_path / replica_dirs[0] / 'prod.edr'
        edr_df = io.read_edr_file(first_edr)
        lambda_values = detect_lambda_states(edr_df)

        if not lambda_values:
            raise ValueError(
                f"EDR文件 {first_edr} 中未检测到多状态能量列。\n"
                "可能的原因：\n"
                "1. 不是REST2模拟\n"
                "2. EDR文件不包含多状态能量（需要rerun）"
            )

        n_states = len(lambda_values)
    else:
        lambda_values = list(range(n_states))

    logger.info(f"Lambda状态数: {n_states}")

    # 3. 提取所有副本的能量矩阵
    u_replicas = []  # 存储每个副本的能量矩阵
    n_cycles_list = []

    for rep_dir in replica_dirs:
        edr_path = data_path / rep_dir / 'prod.edr'

        if not edr_path.exists():
            raise FileNotFoundError(f"EDR文件不存在: {edr_path}")

        logger.info(f"读取 {rep_dir}/prod.edr ...")
        edr_df = io.read_edr_file(edr_path)
        n_cycles = len(edr_df)
        n_cycles_list.append(n_cycles)

        # 提取该副本的多状态能量
        u_matrix = extract_multistate_energies(edr_df, n_states)  # (n_cycles, n_states)
        u_replicas.append(u_matrix)

        logger.info(f"  {rep_dir}: {n_cycles} 个周期, {n_states} 个状态")

    # 4. 验证所有副本的时间步数一致
    if len(set(n_cycles_list)) > 1:
        raise ValueError(
            f"不同副本的时间步数不一致:\n" +
            '\n'.join([f"  {rep}: {n}" for rep, n in zip(replica_dirs, n_cycles_list)]) +
            "\n请检查模拟是否完整"
        )

    n_cycles = n_cycles_list[0]
    n_samples_total = n_cycles * n_replicas

    logger.info(f"总周期数: {n_cycles}, 总样本数: {n_samples_total}")

    # 5. 构建初始的按副本组织的能量矩阵
    # 从 List[(n_cycles, n_states)] 转换为 (n_states, n_samples_total)
    # 此时按"副本→时间"展开

    u_kn_by_replica = np.zeros((n_states, n_samples_total))
    cycle_indices_by_replica = np.zeros(n_samples_total, dtype=int)
    replica_indices_by_replica = np.zeros(n_samples_total, dtype=int)

    sample_idx = 0
    for rep_idx, u_matrix in enumerate(u_replicas):
        for cycle_idx in range(n_cycles):
            for state_idx in range(n_states):
                u_kn_by_replica[state_idx, sample_idx] = u_matrix[cycle_idx, state_idx]

            cycle_indices_by_replica[sample_idx] = cycle_idx
            replica_indices_by_replica[sample_idx] = rep_idx
            sample_idx += 1

    logger.info("构建了按副本组织的能量矩阵")
    logger.info(f"  u_kn_by_replica shape: {u_kn_by_replica.shape}")
    logger.info(f"  样本顺序: [rep0_cyc0, rep0_cyc1, ..., rep{n_replicas-1}_cyc{n_cycles-1}]")

    # 6. 需要重新组织为按状态分组（需要replica_to_state映射）
    # 暂时返回按副本组织的数据，并标记需要重组
    # 注意：这里的u_kn和N_k是错误的，必须使用reorganize_u_kn_by_state重组
    u_kn = u_kn_by_replica
    cycle_indices = cycle_indices_by_replica
    replica_indices = replica_indices_by_replica

    # 警告：N_k是占位符，需要使用真实的replica_to_state映射计算
    N_k = np.full(n_states, n_samples_total // n_states, dtype=int)

    warnings_list.append(
        "⚠️ 能量矩阵当前按副本组织，N_k为占位符。"
        "必须调用reorganize_u_kn_by_state()重新组织为按状态分组。"
    )

    # 7. 验证能量矩阵
    validation_result = validate_energy_matrix(u_kn, N_k)
    if not validation_result['is_valid']:
        warnings_list.extend(validation_result['warnings'])

    logger.info("能量矩阵提取完成")
    logger.info(f"  u_kn shape: {u_kn.shape}")
    logger.info(f"  N_k shape: {N_k.shape}")

    return {
        'u_kn': u_kn,
        'N_k': N_k,
        'lambda_values': lambda_values,
        'n_cycles': n_cycles,
        'n_replicas': n_replicas,
        'n_states': n_states,
        'cycle_indices': cycle_indices,
        'replica_indices': replica_indices,
        'status': 'ok' if not validation_result['issues'] else 'warning',
        'warnings': warnings_list
    }


def validate_energy_matrix(u_kn: np.ndarray,
                           N_k: np.ndarray) -> Dict:
    """
    验证能量矩阵的物理合理性

    Parameters
    ----------
    u_kn : np.ndarray
        能量矩阵 shape=(n_states, n_samples_total)
    N_k : np.ndarray
        每个状态的样本数 shape=(n_states,)

    Returns
    -------
    result : dict
        验证结果
    """
    issues = []
    warnings_list = []

    # 1. 检查NaN
    if np.isnan(u_kn).any():
        nan_count = np.isnan(u_kn).sum()
        nan_positions = np.argwhere(np.isnan(u_kn))
        issues.append(f"能量矩阵包含 {nan_count} 个NaN值")
        logger.error(f"NaN位置示例: state={nan_positions[0][0]}, sample={nan_positions[0][1]}")

    # 2. 检查Inf
    if np.isinf(u_kn).any():
        inf_count = np.isinf(u_kn).sum()
        issues.append(f"能量矩阵包含 {inf_count} 个Inf值")

    # 3. 检查能量范围
    energy_min = np.nanmin(u_kn)
    energy_max = np.nanmax(u_kn)
    energy_range = (energy_min, energy_max)

    if energy_min < -1e6 or energy_max > 1e6:
        warnings_list.append(
            f"能量范围异常: [{energy_min:.2e}, {energy_max:.2e}] kJ/mol"
        )

    # 4. 检查样本数
    if np.any(N_k < 100):
        warnings_list.append(
            f"部分状态的样本数较少（<100）: {N_k.tolist()}"
        )

    is_valid = len(issues) == 0

    return {
        'is_valid': is_valid,
        'has_nan': np.isnan(u_kn).any(),
        'has_inf': np.isinf(u_kn).any(),
        'energy_range': energy_range,
        'issues': issues,
        'warnings': warnings_list
    }


# ==================== 交换记录解析模块 ====================

def parse_exchange_line(line: str) -> Optional[Dict]:
    """
    解析单行副本交换记录

    Parameters
    ----------
    line : str
        LOG文件的一行

    Returns
    -------
    result : dict or None
        {'replica_pairs': [(r1, r2), ...]}
        如果不是交换记录行，返回None
    """
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
            # 检查下一个token是否是'x'
            has_x = (i + 1 < len(tokens) and tokens[i + 1] == 'x')

            if has_x:
                replicas_with_x.append(replica_id)
                i += 2  # 跳过 'x'
            else:
                i += 1
        else:
            i += 1

    # 构建交换对（连续的两个有x的副本）
    pairs = []
    for i in range(0, len(replicas_with_x) - 1, 2):
        pairs.append((replicas_with_x[i], replicas_with_x[i + 1]))

    return {'replica_pairs': pairs}


def parse_gromacs_log(log_path: Union[str, Path]) -> Dict:
    """
    解析GROMACS LOG文件中的副本交换记录

    Parameters
    ----------
    log_path : str or Path
        LOG文件路径

    Returns
    -------
    result : dict
        {
            'exchanges': List[Dict],  # 每次交换的记录
            'n_exchanges': int,
            'status': str
        }
    """
    from . import io

    log_content = io.read_log_file(log_path)
    lines = log_content.split('\n')

    exchanges = []

    for line in lines:
        if 'Repl ex' in line or 'Repl  ex' in line:
            parsed = parse_exchange_line(line)
            if parsed:
                exchanges.append(parsed)

    logger.info(f"从 {log_path} 解析到 {len(exchanges)} 次交换记录")

    return {
        'exchanges': exchanges,
        'n_exchanges': len(exchanges),
        'status': 'ok' if exchanges else 'warning'
    }


def build_replica_state_mapping(exchange_records: Dict,
                                 n_replicas: int,
                                 n_cycles: int,
                                 initial_state_assignment: Optional[np.ndarray] = None) -> np.ndarray:
    """
    从交换记录重建replica_to_state_idx映射

    Parameters
    ----------
    exchange_records : dict
        parse_gromacs_log()的输出
    n_replicas : int
        副本数量
    n_cycles : int
        总周期数
    initial_state_assignment : np.ndarray, optional
        初始状态分配 shape=(n_replicas,)
        如果为None，假设 replica_id == state_id

    Returns
    -------
    replica_to_state : np.ndarray
        shape=(n_cycles, n_replicas)
    """
    # 初始化映射
    mapping = np.zeros((n_cycles, n_replicas), dtype=int)

    if initial_state_assignment is None:
        # 默认假设：初始时replica_id == state_id
        mapping[0, :] = np.arange(n_replicas)
    else:
        mapping[0, :] = initial_state_assignment

    exchanges = exchange_records['exchanges']

    if not exchanges:
        logger.warning("未找到交换记录，使用静态映射（replica_id == state_id）")
        for cycle in range(1, n_cycles):
            mapping[cycle, :] = mapping[0, :]
        return mapping

    # 遍历交换记录，逐周期更新映射
    exchange_idx = 0
    for cycle in range(1, n_cycles):
        # 复制上一周期的映射
        mapping[cycle, :] = mapping[cycle - 1, :]

        # 如果有对应的交换记录，应用交换
        if exchange_idx < len(exchanges):
            exchange = exchanges[exchange_idx]

            for r1, r2 in exchange['replica_pairs']:
                if r1 < n_replicas and r2 < n_replicas:
                    # 交换两个副本的状态
                    mapping[cycle, r1], mapping[cycle, r2] = \
                        mapping[cycle, r2], mapping[cycle, r1]

            exchange_idx += 1

    logger.info(f"重建了 {n_cycles} 个周期的replica→state映射")

    return mapping


def calculate_exchange_statistics(exchange_records: Dict,
                                   replica_to_state: np.ndarray) -> Dict:
    """
    计算交换统计信息

    Parameters
    ----------
    exchange_records : dict
        parse_gromacs_log()的输出
    replica_to_state : np.ndarray
        shape=(n_cycles, n_replicas)

    Returns
    -------
    stats : dict
        交换统计信息
    """
    exchanges = exchange_records['exchanges']

    total_attempts = sum(len(ex['replica_pairs']) for ex in exchanges)
    total_exchanges = len(exchanges)

    # 简化统计（详细统计需要知道哪些交换被接受）
    stats = {
        'total_exchange_attempts': total_attempts,
        'total_exchange_rounds': total_exchanges,
        'status': 'ok'
    }

    # 计算副本迁移率（每个副本访问的状态数）
    n_cycles, n_replicas = replica_to_state.shape
    replica_mobility = np.array([
        len(np.unique(replica_to_state[:, r])) for r in range(n_replicas)
    ])

    stats['replica_mobility'] = replica_mobility
    stats['mean_mobility'] = replica_mobility.mean()

    logger.info(f"交换统计: {total_attempts} 次尝试, 平均迁移率={stats['mean_mobility']:.2f}")

    return stats


# ==================== 数据整合模块 ====================

def prepare_mbar_input(data_dir: Union[str, Path] = 'data',
                       validation_report_path: Optional[str] = None) -> Dict:
    """
    准备MBAR输入数据（01_prepare_mbar.py的核心逻辑）

    Parameters
    ----------
    data_dir : str or Path
        数据目录路径
    validation_report_path : str, optional
        验证报告路径（JSON）

    Returns
    -------
    mbar_input : dict
        完整的MBAR输入数据
    """
    from . import validation, io
    import json

    logger.info("开始准备MBAR输入数据...")

    # 1. 加载或运行验证
    if validation_report_path and Path(validation_report_path).exists():
        logger.info(f"加载验证报告: {validation_report_path}")
        with open(validation_report_path, 'r') as f:
            validation_report = json.load(f)
    else:
        logger.info("运行数据验证...")
        full_report = validation.run_full_validation(data_dir)
        validation_report = {
            'summary': full_report['summary'],
            'lambda_analysis': full_report['lambda_analysis']
        }

    if not validation_report['summary']['is_mbar_ready']:
        raise ValueError(
            "数据未通过验证，无法进行MBAR分析。\n"
            f"问题: {validation_report['summary']}"
        )

    # 2. 提取能量矩阵
    logger.info("提取能量矩阵...")
    energy_data = extract_energy_matrix(data_dir)

    # 3. 解析交换记录并验证LOG一致性
    logger.info("解析副本交换记录...")
    data_path = Path(data_dir)
    dir_check = validation.check_directory_structure(data_dir)
    replica_dirs = dir_check['found']

    # 从第一个副本读取交换记录
    first_log = data_path / replica_dirs[0] / 'prod.log'
    exchange_records = parse_gromacs_log(first_log)

    # 验证LOG一致性（检查前3个副本）
    if len(replica_dirs) > 1:
        logger.info("验证LOG文件一致性...")
        n_to_check = min(3, len(replica_dirs))

        for i in range(1, n_to_check):
            other_log = data_path / replica_dirs[i] / 'prod.log'
            if not other_log.exists():
                logger.warning(f"副本{i}的LOG文件不存在: {other_log}")
                continue

            other_exchange_records = parse_gromacs_log(other_log)

            # 检查交换轮次数是否一致
            if exchange_records['n_exchanges'] != other_exchange_records['n_exchanges']:
                logger.error(
                    f"LOG文件不一致: {replica_dirs[0]}有{exchange_records['n_exchanges']}次交换, "
                    f"{replica_dirs[i]}有{other_exchange_records['n_exchanges']}次交换"
                )
                raise ValueError("不同副本的LOG文件包含不同数量的交换记录")

        logger.info(f"✓ LOG文件一致性验证通过（检查了{n_to_check}个副本）")
    else:
        logger.warning("只有一个副本，跳过LOG一致性验证")

    # 4. 构建状态映射
    logger.info("构建replica→state映射...")
    replica_to_state = build_replica_state_mapping(
        exchange_records,
        n_replicas=energy_data['n_replicas'],
        n_cycles=energy_data['n_cycles']
    )

    # 5. 重新组织u_kn矩阵（关键修复：从副本分组→状态分组）
    logger.info("重新组织u_kn矩阵（按状态分组）...")
    reorganized = reorganize_u_kn_by_state(
        u_kn_by_replica=energy_data['u_kn'],
        replica_to_state=replica_to_state,
        cycle_indices=energy_data['cycle_indices'],
        replica_indices=energy_data['replica_indices']
    )

    # 更新能量矩阵和N_k为正确的值
    u_kn_correct = reorganized['u_kn']
    N_k_correct = reorganized['N_k']

    logger.info(f"✓ u_kn重组完成")
    logger.info(f"  原N_k (错误): {energy_data['N_k']}")
    logger.info(f"  新N_k (正确): {N_k_correct}")

    # 6. 计算交换统计
    exchange_stats = calculate_exchange_statistics(exchange_records, replica_to_state)

    # 7. 验证数据一致性
    logger.info("验证数据一致性...")
    consistency = verify_data_consistency(
        u_kn_correct,
        replica_to_state,
        N_k_correct
    )

    if not consistency['is_consistent']:
        raise ValueError(
            "数据一致性检查失败:\n" +
            '\n'.join(consistency['issues'])
        )

    # 8. 组装完整输出
    mbar_input = {
        'u_kn': u_kn_correct,
        'N_k': N_k_correct,
        'replica_to_state': replica_to_state,
        'lambda_values': energy_data['lambda_values'],
        'n_cycles': energy_data['n_cycles'],
        'n_replicas': energy_data['n_replicas'],
        'n_states': energy_data['n_states'],
        'exchange_statistics': exchange_stats,
        'validation_summary': validation_report['summary'],
        'state_sample_indices': reorganized['state_sample_indices'],
        'state_cycle_indices': reorganized['state_cycle_indices'],
        'state_replica_indices': reorganized['state_replica_indices'],
        'status': 'ok',
        'warnings': energy_data.get('warnings', [])
    }

    logger.info("MBAR输入数据准备完成")
    logger.info(f"  u_kn shape: {mbar_input['u_kn'].shape}")
    logger.info(f"  replica_to_state shape: {mbar_input['replica_to_state'].shape}")

    return mbar_input


def verify_data_consistency(u_kn: np.ndarray,
                            replica_to_state: np.ndarray,
                            N_k: np.ndarray) -> Dict:
    """
    验证u_kn和replica_to_state的维度一致性

    这是MBAR输入数据的关键验证函数，确保：
    1. u_kn的列数等于总样本数
    2. N_k的总和等于总样本数
    3. replica_to_state中的状态索引在有效范围内
    4. u_kn已按状态正确分组

    Parameters
    ----------
    u_kn : np.ndarray
        shape=(n_states, n_samples_total) 按状态分组的能量矩阵
    replica_to_state : np.ndarray
        shape=(n_cycles, n_replicas)
    N_k : np.ndarray
        shape=(n_states,) 每个状态的真实样本数

    Returns
    -------
    result : dict
        {'is_consistent': bool, 'issues': List[str]}
    """
    issues = []

    n_states, n_samples_total = u_kn.shape
    n_cycles, n_replicas = replica_to_state.shape

    logger.info(f"验证数据一致性...")
    logger.info(f"  u_kn shape: {u_kn.shape}")
    logger.info(f"  replica_to_state shape: {replica_to_state.shape}")
    logger.info(f"  N_k: {N_k}")

    # 1. 检查总样本数
    expected_samples = n_cycles * n_replicas
    if n_samples_total != expected_samples:
        issues.append(
            f"样本数不一致: u_kn有{n_samples_total}个样本, "
            f"但replica_to_state有{n_cycles}×{n_replicas}={expected_samples}个"
        )

    # 2. 检查N_k总和
    if N_k.sum() != n_samples_total:
        issues.append(
            f"N_k总和({N_k.sum()})与样本总数({n_samples_total})不一致"
        )

    # 3. 检查状态索引范围
    max_state = replica_to_state.max()
    min_state = replica_to_state.min()

    if min_state < 0 or max_state >= n_states:
        issues.append(
            f"状态索引超出范围: [{min_state}, {max_state}], 应在[0, {n_states-1}]内"
        )

    # 4. 验证N_k与replica_to_state是否一致
    # 统计replica_to_state中每个状态的实际出现次数
    state_counts_from_mapping = np.bincount(replica_to_state.flatten(), minlength=n_states)

    if not np.array_equal(N_k, state_counts_from_mapping):
        issues.append(
            f"N_k与replica_to_state不一致:\n"
            f"  N_k: {N_k}\n"
            f"  实际统计: {state_counts_from_mapping}"
        )

    # 5. 检查能量矩阵是否包含NaN或Inf
    if np.any(np.isnan(u_kn)):
        issues.append("u_kn包含NaN值")

    if np.any(np.isinf(u_kn)):
        issues.append("u_kn包含Inf值")

    is_consistent = len(issues) == 0

    if is_consistent:
        logger.info("✓ 数据一致性检查通过")
    else:
        logger.error("✗ 数据一致性检查失败")
        for issue in issues:
            logger.error(f"  - {issue}")

    return {
        'is_consistent': is_consistent,
        'issues': issues
    }


def reorganize_u_kn_by_state(u_kn_by_replica: np.ndarray,
                              replica_to_state: np.ndarray,
                              cycle_indices: np.ndarray,
                              replica_indices: np.ndarray) -> Dict:
    """
    将按副本组织的u_kn矩阵重新组织为按状态分组

    这是修复MBAR输入数据的核心函数。原始数据按"副本→时间"展开，
    但MBAR要求按"状态"分组，且N_k必须反映每个状态的真实样本数。

    Parameters
    ----------
    u_kn_by_replica : np.ndarray
        按副本组织的能量矩阵，shape=(n_states, n_samples_total)
        列顺序：[rep0_cyc0, rep0_cyc1, ..., rep0_cycN, rep1_cyc0, ...]
    replica_to_state : np.ndarray
        副本到状态的映射，shape=(n_cycles, n_replicas)
        mapping[cycle, replica] = state
    cycle_indices : np.ndarray
        每个样本的周期索引，shape=(n_samples_total,)
    replica_indices : np.ndarray
        每个样本的副本索引，shape=(n_samples_total,)

    Returns
    -------
    result : dict
        {
            'u_kn': np.ndarray,  # shape=(n_states, n_samples_total)
                                 # 按状态重新组织：[state0的样本 | state1的样本 | ...]
            'N_k': np.ndarray,   # shape=(n_states,), 每个状态的真实样本数
            'state_sample_indices': List[np.ndarray],  # 每个状态的样本索引列表
            'state_cycle_indices': List[np.ndarray],   # 每个状态的周期索引
            'state_replica_indices': List[np.ndarray]  # 每个状态的副本索引
        }

    Example
    -------
    >>> # 假设2个副本，3个状态，4个周期
    >>> u_kn_by_replica.shape  # (3, 8)  # 8 = 2副本 × 4周期
    >>> # 列顺序：[rep0_cyc0, rep0_cyc1, rep0_cyc2, rep0_cyc3,
    ...            rep1_cyc0, rep1_cyc1, rep1_cyc2, rep1_cyc3]
    >>>
    >>> replica_to_state = np.array([
    ...     [0, 2],  # cycle 0: rep0在state0, rep1在state2
    ...     [1, 2],  # cycle 1: rep0在state1, rep1在state2
    ...     [1, 0],  # cycle 2: rep0在state1, rep1在state0
    ...     [2, 0]   # cycle 3: rep0在state2, rep1在state0
    ... ])
    >>>
    >>> result = reorganize_u_kn_by_state(u_kn_by_replica, ...)
    >>> result['N_k']  # array([3, 2, 3])  # state0有3个，state1有2个，state2有3个
    """
    n_states, n_samples_total = u_kn_by_replica.shape
    n_cycles, n_replicas = replica_to_state.shape

    logger.info("开始重新组织u_kn矩阵（从副本分组→状态分组）")

    # 1. 为每个状态收集样本索引
    state_sample_indices = [[] for _ in range(n_states)]
    state_cycle_indices = [[] for _ in range(n_states)]
    state_replica_indices = [[] for _ in range(n_states)]

    for sample_idx in range(n_samples_total):
        rep_id = replica_indices[sample_idx]
        cycle_id = cycle_indices[sample_idx]

        # 查询该样本属于哪个状态
        state_id = replica_to_state[cycle_id, rep_id]

        # 将该样本归类到对应状态
        state_sample_indices[state_id].append(sample_idx)
        state_cycle_indices[state_id].append(cycle_id)
        state_replica_indices[state_id].append(rep_id)

    # 2. 计算每个状态的真实样本数
    N_k = np.array([len(indices) for indices in state_sample_indices], dtype=int)

    logger.info(f"每个状态的样本数 N_k: {N_k}")
    logger.info(f"  总样本数: {N_k.sum()} (应该等于{n_samples_total})")

    # 验证
    if N_k.sum() != n_samples_total:
        raise ValueError(
            f"重组后的样本数不一致: N_k.sum()={N_k.sum()} != {n_samples_total}"
        )

    # 3. 重新组装u_kn矩阵（按状态分组）
    u_kn_by_state = np.zeros((n_states, n_samples_total))

    current_col = 0
    for state_id in range(n_states):
        sample_indices_for_state = state_sample_indices[state_id]
        n_samples_in_state = len(sample_indices_for_state)

        if n_samples_in_state > 0:
            # 提取该状态的所有样本列
            u_kn_by_state[:, current_col:current_col + n_samples_in_state] = \
                u_kn_by_replica[:, sample_indices_for_state]

            current_col += n_samples_in_state

    logger.info("✓ u_kn矩阵重组完成")
    logger.info(f"  新u_kn shape: {u_kn_by_state.shape}")
    logger.info(f"  列顺序: [state0的{N_k[0]}个样本 | state1的{N_k[1]}个样本 | ...]")

    # 转换为numpy数组
    state_sample_indices_arrays = [np.array(idx, dtype=int) for idx in state_sample_indices]
    state_cycle_indices_arrays = [np.array(idx, dtype=int) for idx in state_cycle_indices]
    state_replica_indices_arrays = [np.array(idx, dtype=int) for idx in state_replica_indices]

    return {
        'u_kn': u_kn_by_state,
        'N_k': N_k,
        'state_sample_indices': state_sample_indices_arrays,
        'state_cycle_indices': state_cycle_indices_arrays,
        'state_replica_indices': state_replica_indices_arrays
    }
