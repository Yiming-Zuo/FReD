# -*- coding: utf-8 -*-
"""
MBAR核心计算和诊断模块

功能：
1. 时间序列子采样和去相关
2. MBAR重加权计算
3. 诊断指标计算（overlap矩阵、ESS、收敛性）
4. 观测量重加权

依赖：
- pymbar >= 4.0.0
- numpy
"""

import numpy as np
import logging
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


def subsample_timeseries(u_k: np.ndarray,
                         method: str = 'auto',
                         equilibration: Optional[int] = None,
                         statistical_inefficiency: Optional[float] = None) -> Dict:
    """
    对时间序列去相关并子采样

    使用pymbar时间序列分析：
    - detect_equilibration(): 检测平衡化时间t0
    - statistical_inefficiency(): 计算统计无效性g（相关时间）
    - subsample_correlated_data(): 子采样为独立样本

    Parameters
    ----------
    u_k : np.ndarray
        shape=(n_samples,) 单个状态的能量时间序列
    method : str, optional
        'auto': 自动检测平衡和相关性
        'manual': 使用提供的equilibration和statistical_inefficiency
    equilibration : int, optional
        手动指定的平衡化时间（丢弃前t0个样本）
    statistical_inefficiency : float, optional
        手动指定的统计无效性g

    Returns
    -------
    result : dict
        {
            'subsampled_data': np.ndarray,  # 子采样后的数据
            't0': int,                       # 平衡化时间
            'g': float,                      # 统计无效性
            'indices': np.ndarray,           # 子采样索引（相对于平衡后）
            'n_effective': int,              # 有效样本数
            'original_n': int                # 原始样本数
        }
    """
    from pymbar import timeseries

    original_n = len(u_k)

    if method == 'auto':
        # 自动检测平衡化
        t0, g, n_effective = timeseries.detect_equilibration(u_k)
        logger.info(f"自动检测: 平衡化时间 t0={t0}, 统计无效性 g={g:.2f}, 有效样本数 N_eff={n_effective:.0f}")
    elif method == 'manual':
        if equilibration is None or statistical_inefficiency is None:
            raise ValueError("手动模式需要提供 equilibration 和 statistical_inefficiency")
        t0 = equilibration
        g = statistical_inefficiency
        n_effective = (original_n - t0) / g
        logger.info(f"手动设置: 平衡化时间 t0={t0}, 统计无效性 g={g:.2f}")
    else:
        raise ValueError(f"未知方法: {method}，应为 'auto' 或 'manual'")

    # 子采样去相关
    u_equilibrated = u_k[t0:]
    indices = timeseries.subsample_correlated_data(u_equilibrated, g=g)
    subsampled_data = u_equilibrated[indices]

    logger.info(f"子采样结果: {original_n} → {len(u_equilibrated)} (平衡后) → {len(subsampled_data)} (去相关后)")

    return {
        'subsampled_data': subsampled_data,
        't0': t0,
        'g': g,
        'indices': indices,
        'n_effective': int(n_effective),
        'original_n': original_n
    }


def subsample_all_states(u_kn: np.ndarray,
                          N_k: np.ndarray,
                          method: str = 'auto') -> Dict:
    """
    对所有状态的能量时间序列进行子采样

    Parameters
    ----------
    u_kn : np.ndarray
        shape=(n_states, n_samples_total) 能量矩阵
    N_k : np.ndarray
        shape=(n_states,) 每个状态的样本数
    method : str, optional
        子采样方法 ('auto' 或 'manual')

    Returns
    -------
    result : dict
        {
            'u_kn_sub': np.ndarray,       # 子采样后的能量矩阵
            'N_k_sub': np.ndarray,        # 子采样后的样本数
            'subsample_info': List[Dict], # 每个状态的子采样信息
            'total_reduction': float      # 总样本数减少比例
        }
    """
    n_states = u_kn.shape[0]

    # 分割每个状态的能量序列
    u_k_list = []
    start_idx = 0
    for k, n_samples in enumerate(N_k):
        u_k_list.append(u_kn[:, start_idx:start_idx + n_samples])
        start_idx += n_samples

    # 对每个状态进行子采样
    u_k_subsampled = []
    N_k_sub = []
    subsample_info = []

    for k in range(n_states):
        # 使用状态k在自身状态下的能量序列进行平衡和相关性检测
        u_k_self = u_k_list[k][k, :]  # shape=(N_k[k],)

        result = subsample_timeseries(u_k_self, method=method)

        # 获取子采样索引（相对于平衡后）
        t0 = result['t0']
        indices_rel = result['indices']

        # 将相对索引转换为绝对索引
        indices_abs = indices_rel + t0

        # 应用子采样到该状态的所有能量列
        u_k_sub = u_k_list[k][:, indices_abs]  # shape=(n_states, n_subsampled)

        u_k_subsampled.append(u_k_sub)
        N_k_sub.append(len(indices_abs))
        subsample_info.append({
            'state': k,
            't0': t0,
            'g': result['g'],
            'n_original': result['original_n'],
            'n_effective': result['n_effective'],
            'n_subsampled': len(indices_abs)
        })

        logger.info(f"状态{k}: {result['original_n']} → {result['n_effective']} (有效) → {len(indices_abs)} (子采样)")

    # 合并所有状态的子采样数据
    u_kn_sub = np.hstack(u_k_subsampled)
    N_k_sub = np.array(N_k_sub, dtype=int)

    total_original = N_k.sum()
    total_subsampled = N_k_sub.sum()
    reduction = 1.0 - (total_subsampled / total_original)

    logger.info(f"总体子采样: {total_original} → {total_subsampled} (减少 {reduction*100:.1f}%)")

    return {
        'u_kn_sub': u_kn_sub,
        'N_k_sub': N_k_sub,
        'subsample_info': subsample_info,
        'total_reduction': reduction
    }


def run_mbar(u_kn: np.ndarray,
             N_k: np.ndarray,
             target_state: int = 0,
             **mbar_kwargs) -> Tuple:
    """
    运行MBAR计算

    Parameters
    ----------
    u_kn : np.ndarray
        shape=(n_states, n_samples_total) 能量矩阵
    N_k : np.ndarray
        shape=(n_states,) 每个状态的样本数
    target_state : int, optional
        目标状态索引（通常0对应λ=1, 300K）
    **mbar_kwargs : dict
        传递给pymbar.MBAR的参数，如：
        - maximum_iterations: 最大迭代次数（默认10000）
        - relative_tolerance: 相对收敛容限（默认1e-7）
        - verbose: 是否显示详细信息（默认False）

    Returns
    -------
    mbar : pymbar.MBAR
        MBAR对象实例
    weights : np.ndarray
        目标状态的MBAR权重 shape=(n_samples_total,)
    """
    from pymbar import MBAR

    n_states, n_samples_total = u_kn.shape

    logger.info(f"初始化MBAR: {n_states} 个状态, {n_samples_total} 个样本")
    logger.info(f"N_k分布: {N_k}")

    # 设置默认参数
    default_kwargs = {
        'maximum_iterations': 10000,
        'relative_tolerance': 1e-7,
        'verbose': False
    }
    default_kwargs.update(mbar_kwargs)

    # 初始化MBAR
    try:
        mbar = MBAR(u_kn, N_k, **default_kwargs)
        logger.info("✓ MBAR初始化成功")
    except Exception as e:
        logger.error(f"MBAR初始化失败: {e}")
        raise

    # 计算目标状态的权重
    # pymbar 4.x: weights() 返回 shape=(n_states, n_samples_total)
    try:
        all_weights = mbar.W_nk  # shape=(n_samples_total, n_states)
        weights = all_weights[:, target_state]  # shape=(n_samples_total,)
        logger.info(f"✓ 计算目标状态{target_state}的权重")
        logger.info(f"  权重范围: [{weights.min():.2e}, {weights.max():.2e}]")
        logger.info(f"  权重总和: {weights.sum():.6f}")
    except Exception as e:
        logger.error(f"权重计算失败: {e}")
        raise

    return mbar, weights


def compute_diagnostics(mbar) -> Dict:
    """
    计算MBAR诊断指标

    Parameters
    ----------
    mbar : pymbar.MBAR
        MBAR对象实例

    Returns
    -------
    diagnostics : dict
        {
            'overlap_matrix': np.ndarray,    # (n_states, n_states)
            'min_overlap': float,            # 最小相邻overlap
            'effective_sample_size': float,  # 有效样本数
            'free_energies': np.ndarray,     # f_k (无量纲自由能)
            'uncertainties': np.ndarray,     # df_k (不确定度)
            'is_converged': bool,            # 是否收敛
            'warnings': List[str]            # 警告信息
        }
    """
    diagnostics = {}
    warnings = []

    # 1. Overlap矩阵
    logger.info("计算overlap矩阵...")
    try:
        overlap_dict = mbar.compute_overlap()
        overlap_matrix = overlap_dict['matrix']
        diagnostics['overlap_matrix'] = overlap_matrix

        # 检查相邻状态overlap
        n_states = overlap_matrix.shape[0]
        adjacent_overlaps = [overlap_matrix[i, i+1] for i in range(n_states-1)]
        min_overlap = min(adjacent_overlaps) if adjacent_overlaps else 0.0
        diagnostics['min_overlap'] = min_overlap

        logger.info(f"  最小相邻overlap: {min_overlap:.4f}")

        if min_overlap < 0.03:
            warning_msg = (
                f"相邻状态overlap过低: {min_overlap:.4f} < 0.03\n"
                "建议调整温度/Lambda间距以增加状态重叠"
            )
            warnings.append(warning_msg)
            logger.warning(warning_msg)
    except Exception as e:
        logger.error(f"Overlap矩阵计算失败: {e}")
        warnings.append(f"Overlap矩阵计算失败: {e}")
        diagnostics['overlap_matrix'] = None
        diagnostics['min_overlap'] = 0.0

    # 2. 有效样本数
    logger.info("计算有效样本数...")
    try:
        # pymbar 4.x: compute_effective_sample_number()
        ess = mbar.compute_effective_sample_number()
        diagnostics['effective_sample_size'] = float(ess)

        logger.info(f"  有效样本数: {ess:.1f}")

        if ess < 50:
            warning_msg = (
                f"有效样本数过低: {ess:.1f} < 50\n"
                "建议增加采样时间或减少状态数"
            )
            warnings.append(warning_msg)
            logger.warning(warning_msg)
    except Exception as e:
        logger.error(f"有效样本数计算失败: {e}")
        warnings.append(f"有效样本数计算失败: {e}")
        diagnostics['effective_sample_size'] = 0.0

    # 3. 自由能
    logger.info("提取自由能和不确定度...")
    try:
        # pymbar 4.x: f_k 是无量纲自由能
        diagnostics['free_energies'] = mbar.f_k

        # 计算不确定度（标准误）
        # compute_covariance() 返回协方差矩阵，对角线的平方根是标准误
        try:
            cov_matrix = mbar.compute_covariance()
            uncertainties = np.sqrt(np.diag(cov_matrix))
            diagnostics['uncertainties'] = uncertainties
        except:
            # 如果协方差计算失败，使用零数组
            logger.warning("协方差矩阵计算失败，使用零不确定度")
            diagnostics['uncertainties'] = np.zeros_like(mbar.f_k)

        logger.info(f"  自由能范围: [{mbar.f_k.min():.2f}, {mbar.f_k.max():.2f}] kT")
    except Exception as e:
        logger.error(f"自由能提取失败: {e}")
        warnings.append(f"自由能提取失败: {e}")
        diagnostics['free_energies'] = None
        diagnostics['uncertainties'] = None

    # 4. 收敛性判断
    is_converged = len(warnings) == 0
    diagnostics['is_converged'] = is_converged
    diagnostics['warnings'] = warnings

    if is_converged:
        logger.info("✓ MBAR计算收敛，无警告")
    else:
        logger.warning(f"⚠ MBAR计算完成，但有 {len(warnings)} 个警告")

    return diagnostics


def reweight_observable(data: np.ndarray,
                        weights: np.ndarray,
                        bins: int = 50) -> Tuple[np.ndarray, np.ndarray]:
    """
    使用MBAR权重重加权任意观测量

    Parameters
    ----------
    data : np.ndarray
        shape=(n_samples,) 或 (n_samples, n_dims) 观测量数据
    weights : np.ndarray
        shape=(n_samples,) MBAR权重
    bins : int, optional
        直方图bins数

    Returns
    -------
    bin_centers : np.ndarray
        直方图bin中心
    reweighted_prob : np.ndarray
        重加权后的概率密度
    """
    # 归一化权重
    weights_normalized = weights / weights.sum()

    # 处理多维数据（只取第一维）
    if data.ndim > 1:
        data = data[:, 0]
        logger.warning("多维观测量，仅使用第一维进行直方图计算")

    # 计算重加权直方图
    hist, bin_edges = np.histogram(
        data,
        bins=bins,
        weights=weights_normalized,
        density=True
    )

    bin_centers = 0.5 * (bin_edges[1:] + bin_edges[:-1])

    logger.info(f"重加权观测量: bins={bins}, 数据范围=[{data.min():.2e}, {data.max():.2e}]")

    return bin_centers, hist


def compute_free_energy_difference(mbar,
                                    state_i: int,
                                    state_j: int) -> Tuple[float, float]:
    """
    计算两个状态之间的自由能差

    Parameters
    ----------
    mbar : pymbar.MBAR
        MBAR对象实例
    state_i : int
        初始状态索引
    state_j : int
        最终状态索引

    Returns
    -------
    delta_f : float
        自由能差 ΔF_{i→j} (kT单位)
    delta_f_err : float
        自由能差的不确定度 (kT单位)
    """
    try:
        # pymbar 4.x: compute_free_energy_differences()
        # 返回 (delta_f_ij, d_delta_f_ij) 其中delta_f_ij[i,j] = f_j - f_i
        delta_f_ij, d_delta_f_ij = mbar.compute_free_energy_differences()

        delta_f = delta_f_ij[state_i, state_j]
        delta_f_err = d_delta_f_ij[state_i, state_j]

        logger.info(f"ΔF({state_i}→{state_j}) = {delta_f:.3f} ± {delta_f_err:.3f} kT")

        return float(delta_f), float(delta_f_err)
    except Exception as e:
        logger.error(f"自由能差计算失败: {e}")
        raise


def compute_expectations(mbar,
                         observable: np.ndarray,
                         target_state: int = 0) -> Tuple[float, float]:
    """
    计算观测量在目标状态下的期望值

    Parameters
    ----------
    mbar : pymbar.MBAR
        MBAR对象实例
    observable : np.ndarray
        shape=(n_samples_total,) 观测量数据
    target_state : int, optional
        目标状态索引

    Returns
    -------
    expectation : float
        期望值
    uncertainty : float
        不确定度
    """
    try:
        # pymbar 4.x: compute_expectations()
        # 需要将观测量reshape为 (n_samples_total, 1)
        A = observable.reshape(-1, 1)

        # 计算期望值 <A>_i 对所有状态i
        expectations, uncertainties = mbar.compute_expectations(A)

        expectation = expectations[target_state, 0]
        uncertainty = uncertainties[target_state, 0]

        logger.info(f"<A>_{target_state} = {expectation:.3e} ± {uncertainty:.3e}")

        return float(expectation), float(uncertainty)
    except Exception as e:
        logger.error(f"期望值计算失败: {e}")
        raise
