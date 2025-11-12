# -*- coding: utf-8 -*-
"""
MBAR诊断可视化模块

功能：
1. Overlap矩阵热图
2. 自由能曲线（带误差棒）
3. MBAR权重分布
4. 能量时间序列
5. 完整诊断图表集

依赖：
- matplotlib >= 3.0
- seaborn (可选，用于更美观的热图)
- numpy
"""

import numpy as np
import matplotlib.pyplot as plt
import logging
from pathlib import Path
from typing import List, Optional

logger = logging.getLogger(__name__)

# 设置matplotlib中文支持（可选）
try:
    plt.rcParams['font.sans-serif'] = ['Arial Unicode MS', 'SimHei', 'DejaVu Sans']
    plt.rcParams['axes.unicode_minus'] = False
except:
    pass


def plot_overlap_matrix(overlap: np.ndarray,
                        output_path: str,
                        lambda_values: Optional[List] = None,
                        title: str = 'MBAR Overlap Matrix',
                        vmin: float = 0.0,
                        vmax: float = 1.0):
    """
    绘制overlap矩阵热图

    Parameters
    ----------
    overlap : np.ndarray
        shape=(n_states, n_states) overlap矩阵
    output_path : str
        输出路径
    lambda_values : list, optional
        Lambda值列表（用于标签）
    title : str, optional
        图表标题
    vmin, vmax : float, optional
        颜色映射范围
    """
    try:
        import seaborn as sns
        use_seaborn = True
    except ImportError:
        use_seaborn = False
        logger.warning("未安装seaborn，使用基础matplotlib绘图")

    n_states = overlap.shape[0]

    # 准备标签
    if lambda_values is None:
        labels = [f'State {i}' for i in range(n_states)]
    else:
        if len(lambda_values) == n_states and all(isinstance(v, (int, float)) for v in lambda_values):
            labels = [f'λ={v:.3f}' for v in lambda_values]
        else:
            labels = [str(v) for v in lambda_values]

    fig, ax = plt.subplots(figsize=(10, 8))

    if use_seaborn:
        # 使用seaborn绘制更美观的热图
        sns.heatmap(overlap, annot=True, fmt='.3f', cmap='YlOrRd',
                    xticklabels=labels, yticklabels=labels,
                    vmin=vmin, vmax=vmax, ax=ax,
                    cbar_kws={'label': 'Overlap'})
    else:
        # 使用matplotlib基础功能
        im = ax.imshow(overlap, cmap='YlOrRd', vmin=vmin, vmax=vmax,
                      aspect='auto', origin='lower')

        # 添加颜色条
        cbar = plt.colorbar(im, ax=ax)
        cbar.set_label('Overlap', rotation=270, labelpad=20)

        # 添加数值标注
        for i in range(n_states):
            for j in range(n_states):
                text = ax.text(j, i, f'{overlap[i, j]:.3f}',
                             ha='center', va='center',
                             color='black' if overlap[i, j] > 0.5 else 'white',
                             fontsize=8)

        # 设置刻度
        ax.set_xticks(range(n_states))
        ax.set_yticks(range(n_states))
        ax.set_xticklabels(labels, rotation=45, ha='right')
        ax.set_yticklabels(labels)

    ax.set_title(title, fontsize=14, fontweight='bold')
    ax.set_xlabel('State', fontsize=12)
    ax.set_ylabel('State', fontsize=12)

    plt.tight_layout()
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    plt.close()

    logger.info(f"✓ Overlap矩阵图已保存: {output_path}")


def plot_free_energy_profile(f_k: np.ndarray,
                             df_k: np.ndarray,
                             output_path: str,
                             lambda_values: Optional[List] = None,
                             title: str = 'Free Energy Profile',
                             xlabel: str = 'λ',
                             ylabel: str = 'ΔF (kT)'):
    """
    绘制自由能曲线（带误差棒）

    Parameters
    ----------
    f_k : np.ndarray
        shape=(n_states,) 自由能
    df_k : np.ndarray
        shape=(n_states,) 自由能不确定度
    output_path : str
        输出路径
    lambda_values : list, optional
        Lambda值列表（用于x轴）
    title : str, optional
        图表标题
    xlabel, ylabel : str, optional
        坐标轴标签
    """
    n_states = len(f_k)

    if lambda_values is None:
        lambda_values = np.arange(n_states)

    fig, ax = plt.subplots(figsize=(10, 6))

    # 自由能相对于第一个状态
    f_k_relative = f_k - f_k[0]

    # 绘制误差棒
    ax.errorbar(lambda_values, f_k_relative, yerr=df_k,
                marker='o', linestyle='-', linewidth=2,
                markersize=8, capsize=5, capthick=2,
                color='steelblue', ecolor='gray',
                label='MBAR Free Energy')

    ax.set_xlabel(xlabel, fontsize=12)
    ax.set_ylabel(ylabel, fontsize=12)
    ax.set_title(title, fontsize=14, fontweight='bold')
    ax.grid(True, alpha=0.3, linestyle='--')
    ax.legend(fontsize=10)

    # 添加零线
    ax.axhline(y=0, color='black', linestyle='--', linewidth=1, alpha=0.5)

    plt.tight_layout()
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    plt.close()

    logger.info(f"✓ 自由能曲线图已保存: {output_path}")


def plot_weights_distribution(weights: np.ndarray,
                               output_path: str,
                               bins: int = 100,
                               title: str = 'MBAR Weights Distribution',
                               log_scale: bool = True):
    """
    绘制MBAR权重分布直方图

    Parameters
    ----------
    weights : np.ndarray
        shape=(n_samples,) MBAR权重
    output_path : str
        输出路径
    bins : int, optional
        直方图bins数
    title : str, optional
        图表标题
    log_scale : bool, optional
        是否使用对数坐标（y轴）
    """
    fig, ax = plt.subplots(figsize=(10, 6))

    # 绘制直方图
    ax.hist(weights, bins=bins, density=True, alpha=0.7,
            edgecolor='black', linewidth=0.5, color='steelblue')

    ax.set_xlabel('MBAR Weight', fontsize=12)
    ax.set_ylabel('Probability Density', fontsize=12)
    ax.set_title(title, fontsize=14, fontweight='bold')

    if log_scale:
        ax.set_yscale('log')

    ax.grid(True, alpha=0.3, linestyle='--')

    # 添加统计信息文本框
    stats_text = (
        f"Mean: {weights.mean():.2e}\n"
        f"Std: {weights.std():.2e}\n"
        f"Min: {weights.min():.2e}\n"
        f"Max: {weights.max():.2e}\n"
        f"Max/Min: {weights.max()/weights.min():.1f}"
    )

    ax.text(0.95, 0.95, stats_text,
            transform=ax.transAxes,
            verticalalignment='top',
            horizontalalignment='right',
            bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5),
            fontsize=10,
            family='monospace')

    plt.tight_layout()
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    plt.close()

    logger.info(f"✓ 权重分布图已保存: {output_path}")


def plot_energy_timeseries(u_kn: np.ndarray,
                           output_path: str,
                           state_indices: Optional[List[int]] = None,
                           max_samples: int = 10000,
                           title_prefix: str = 'Energy Timeseries'):
    """
    绘制能量时间序列（多个状态）

    Parameters
    ----------
    u_kn : np.ndarray
        shape=(n_states, n_samples) 能量矩阵
    output_path : str
        输出路径
    state_indices : list of int, optional
        要显示的状态索引列表（如果为None，显示首、中、尾三个）
    max_samples : int, optional
        最大显示样本数（如果样本太多，会降采样显示）
    title_prefix : str, optional
        图表标题前缀
    """
    n_states, n_samples = u_kn.shape

    if state_indices is None:
        # 默认显示首、中、尾三个状态
        state_indices = [0, n_states//2, n_states-1]

    # 如果样本太多，降采样显示
    if n_samples > max_samples:
        indices = np.linspace(0, n_samples-1, max_samples, dtype=int)
    else:
        indices = np.arange(n_samples)

    n_plots = len(state_indices)
    fig, axes = plt.subplots(n_plots, 1,
                            figsize=(12, 4*n_plots),
                            sharex=True)

    if n_plots == 1:
        axes = [axes]

    for ax, state_idx in zip(axes, state_indices):
        ax.plot(indices, u_kn[state_idx, indices],
               alpha=0.7, linewidth=0.5, color='steelblue')

        ax.set_ylabel(f'U (State {state_idx}) [kJ/mol]', fontsize=11)
        ax.set_title(f'{title_prefix} - State {state_idx}', fontsize=12, fontweight='bold')
        ax.grid(True, alpha=0.3, linestyle='--')

        # 添加统计信息
        u_state = u_kn[state_idx, indices]
        stats_text = f"Mean: {u_state.mean():.2e}\nStd: {u_state.std():.2e}"
        ax.text(0.02, 0.98, stats_text,
               transform=ax.transAxes,
               verticalalignment='top',
               bbox=dict(boxstyle='round', facecolor='white', alpha=0.7),
               fontsize=9,
               family='monospace')

    axes[-1].set_xlabel('Sample Index', fontsize=12)

    plt.tight_layout()
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    plt.close()

    logger.info(f"✓ 能量时间序列图已保存: {output_path}")


def plot_subsample_diagnostics(subsample_info: List[dict],
                               output_path: str,
                               title: str = 'Subsampling Diagnostics'):
    """
    绘制子采样诊断图

    Parameters
    ----------
    subsample_info : list of dict
        每个状态的子采样信息列表
    output_path : str
        输出路径
    title : str, optional
        图表标题
    """
    n_states = len(subsample_info)
    states = [info['state'] for info in subsample_info]

    # 提取数据
    t0_values = [info['t0'] for info in subsample_info]
    g_values = [info['g'] for info in subsample_info]
    n_original = [info['n_original'] for info in subsample_info]
    n_subsampled = [info['n_subsampled'] for info in subsample_info]
    reduction = [1 - (sub/orig) for sub, orig in zip(n_subsampled, n_original)]

    fig, axes = plt.subplots(2, 2, figsize=(14, 10))

    # 1. 平衡化时间
    ax = axes[0, 0]
    ax.bar(states, t0_values, color='steelblue', alpha=0.7, edgecolor='black')
    ax.set_xlabel('State', fontsize=11)
    ax.set_ylabel('Equilibration Time (t0)', fontsize=11)
    ax.set_title('Equilibration Time by State', fontsize=12, fontweight='bold')
    ax.grid(True, alpha=0.3, axis='y')

    # 2. 统计无效性
    ax = axes[0, 1]
    ax.bar(states, g_values, color='coral', alpha=0.7, edgecolor='black')
    ax.set_xlabel('State', fontsize=11)
    ax.set_ylabel('Statistical Inefficiency (g)', fontsize=11)
    ax.set_title('Statistical Inefficiency by State', fontsize=12, fontweight='bold')
    ax.grid(True, alpha=0.3, axis='y')

    # 3. 样本数变化
    ax = axes[1, 0]
    x = np.arange(n_states)
    width = 0.35
    ax.bar(x - width/2, n_original, width, label='Original', color='lightblue', edgecolor='black')
    ax.bar(x + width/2, n_subsampled, width, label='Subsampled', color='lightcoral', edgecolor='black')
    ax.set_xlabel('State', fontsize=11)
    ax.set_ylabel('Number of Samples', fontsize=11)
    ax.set_title('Sample Count: Original vs Subsampled', fontsize=12, fontweight='bold')
    ax.set_xticks(x)
    ax.set_xticklabels(states)
    ax.legend(fontsize=10)
    ax.grid(True, alpha=0.3, axis='y')

    # 4. 减少比例
    ax = axes[1, 1]
    ax.bar(states, [r*100 for r in reduction], color='seagreen', alpha=0.7, edgecolor='black')
    ax.set_xlabel('State', fontsize=11)
    ax.set_ylabel('Reduction (%)', fontsize=11)
    ax.set_title('Data Reduction by State', fontsize=12, fontweight='bold')
    ax.grid(True, alpha=0.3, axis='y')

    plt.suptitle(title, fontsize=14, fontweight='bold', y=0.995)
    plt.tight_layout()
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    plt.close()

    logger.info(f"✓ 子采样诊断图已保存: {output_path}")


def plot_all_diagnostics(mbar,
                        weights: np.ndarray,
                        u_kn: np.ndarray,
                        output_dir: str,
                        lambda_values: Optional[List] = None,
                        subsample_info: Optional[List[dict]] = None):
    """
    生成所有诊断图表

    Parameters
    ----------
    mbar : pymbar.MBAR
        MBAR对象实例
    weights : np.ndarray
        MBAR权重
    u_kn : np.ndarray
        能量矩阵
    output_dir : str
        输出目录路径
    lambda_values : list, optional
        Lambda值列表
    subsample_info : list of dict, optional
        子采样信息（如果有）
    """
    from . import mbar as mbar_module

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    logger.info(f"生成诊断图表到目录: {output_dir}")

    # 计算诊断指标
    diagnostics = mbar_module.compute_diagnostics(mbar)

    # 1. Overlap矩阵
    if diagnostics['overlap_matrix'] is not None:
        plot_overlap_matrix(
            diagnostics['overlap_matrix'],
            str(output_path / 'overlap_matrix.png'),
            lambda_values=lambda_values
        )

    # 2. 自由能曲线
    if diagnostics['free_energies'] is not None and diagnostics['uncertainties'] is not None:
        plot_free_energy_profile(
            diagnostics['free_energies'],
            diagnostics['uncertainties'],
            str(output_path / 'free_energy_profile.png'),
            lambda_values=lambda_values
        )

    # 3. 权重分布
    plot_weights_distribution(
        weights,
        str(output_path / 'weights_distribution.png')
    )

    # 4. 能量时间序列
    plot_energy_timeseries(
        u_kn,
        str(output_path / 'energy_timeseries.png')
    )

    # 5. 子采样诊断（如果提供）
    if subsample_info is not None:
        plot_subsample_diagnostics(
            subsample_info,
            str(output_path / 'subsample_diagnostics.png')
        )

    logger.info("✓ 所有诊断图表生成完成")


def plot_convergence_timeseries(f_k_history: List[np.ndarray],
                                output_path: str,
                                lambda_values: Optional[List] = None,
                                title: str = 'MBAR Convergence'):
    """
    绘制MBAR收敛曲线（自由能随迭代的变化）

    Parameters
    ----------
    f_k_history : list of np.ndarray
        每次迭代的自由能数组列表
    output_path : str
        输出路径
    lambda_values : list, optional
        Lambda值列表
    title : str, optional
        图表标题
    """
    if not f_k_history:
        logger.warning("无收敛历史数据，跳过绘图")
        return

    n_iterations = len(f_k_history)
    n_states = len(f_k_history[0])

    fig, ax = plt.subplots(figsize=(10, 6))

    # 绘制每个状态的收敛曲线
    for state_idx in range(n_states):
        f_values = [f_k[state_idx] for f_k in f_k_history]

        if lambda_values is not None and state_idx < len(lambda_values):
            label = f'λ={lambda_values[state_idx]:.3f}'
        else:
            label = f'State {state_idx}'

        ax.plot(range(n_iterations), f_values,
               marker='o', markersize=4, alpha=0.7,
               label=label)

    ax.set_xlabel('Iteration', fontsize=12)
    ax.set_ylabel('Free Energy (kT)', fontsize=12)
    ax.set_title(title, fontsize=14, fontweight='bold')
    ax.legend(fontsize=9, ncol=2)
    ax.grid(True, alpha=0.3, linestyle='--')

    plt.tight_layout()
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    plt.close()

    logger.info(f"✓ 收敛曲线图已保存: {output_path}")
