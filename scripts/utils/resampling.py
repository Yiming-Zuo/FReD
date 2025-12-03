# -*- coding: utf-8 -*-
"""
重采样和训练数据集构建模块

功能：
1. 根据MBAR权重重采样
2. 从XTC轨迹提取构象坐标
3. 从EDR提取还原势能（λ=1状态）
4. 计算辅助特征（二面角、距离等）

依赖：
- mdtraj >= 1.9.0
- numpy
"""

import numpy as np
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


def resample_by_weights(weights: np.ndarray,
                        n_samples: int,
                        method: str = 'multinomial',
                        random_seed: Optional[int] = None) -> np.ndarray:
    """
    根据MBAR权重重采样

    Parameters
    ----------
    weights : np.ndarray
        shape=(n_samples_original,) MBAR权重
    n_samples : int
        目标样本数
    method : str, optional
        重采样方法:
        - 'multinomial': 多项式抽样（有放回，默认）
        - 'systematic': 系统重采样（更均匀，但稍慢）
    random_seed : int, optional
        随机种子（用于可重复性）

    Returns
    -------
    indices : np.ndarray
        shape=(n_samples,) 重采样后的索引
    """
    if random_seed is not None:
        np.random.seed(random_seed)

    # 归一化权重
    weights_normalized = weights / weights.sum()

    logger.info(f"重采样: {len(weights)} → {n_samples} 个样本 (方法: {method})")

    if method == 'multinomial':
        # 多项式抽样（有放回）
        indices = np.random.choice(
            len(weights),
            size=n_samples,
            p=weights_normalized,
            replace=True
        )

    elif method == 'systematic':
        # 系统重采样（更均匀，减少方差）
        cumsum = np.cumsum(weights_normalized)
        u = np.random.rand() / n_samples
        indices = []

        for i in range(n_samples):
            threshold = u + i / n_samples
            idx = np.searchsorted(cumsum, threshold)
            # 确保索引不越界
            idx = min(idx, len(weights) - 1)
            indices.append(idx)

        indices = np.array(indices, dtype=int)

    else:
        raise ValueError(f"未知方法: {method}，应为 'multinomial' 或 'systematic'")

    # 统计重采样效果
    unique_indices = len(np.unique(indices))
    logger.info(f"  唯一样本数: {unique_indices}/{n_samples} ({unique_indices/n_samples*100:.1f}%)")

    return indices


def extract_configurations(xtc_paths: List[str],
                          top_path: str,
                          sample_indices: np.ndarray,
                          replica_indices: np.ndarray,
                          cycle_indices: np.ndarray,
                          extract_box: bool = True,
                          atom_selection: str = None) -> Dict:
    """
    从XTC文件提取构象坐标

    性能优化：使用轨迹缓存，每个副本只加载一次完整轨迹

    Parameters
    ----------
    xtc_paths : list of str
        XTC文件路径列表（每个副本一个）
    top_path : str
        拓扑文件路径（GRO或PDB）
    sample_indices : np.ndarray
        重采样后的全局样本索引
    replica_indices : np.ndarray
        每个全局样本对应的replica_id
    cycle_indices : np.ndarray
        每个全局样本对应的cycle_id
    extract_box : bool, optional
        是否提取盒子向量
    atom_selection : str, optional
        原子选择语法（mdtraj风格，例如: "not water and not resname SOL"）
        如果为None，则保存所有原子

    Returns
    -------
    result : dict
        {
            'coordinates': np.ndarray,  # (n_samples, n_atoms, 3) [nm]
            'box': np.ndarray,          # (n_samples, 3, 3) [nm] (如果extract_box=True)
            'n_atoms': int,
            'topology': mdtraj.Topology
        }
    """
    from . import io

    n_samples = len(sample_indices)

    coordinates = []
    boxes = [] if extract_box else None

    logger.info(f"从XTC提取 {n_samples} 个构象...")

    # 预加载所有副本的完整轨迹（性能优化）
    traj_cache = {}
    n_replicas = len(xtc_paths)

    logger.info(f"预加载 {n_replicas} 个副本的完整轨迹...")
    original_n_atoms = None
    for rep_id, xtc_path in enumerate(xtc_paths):
        logger.info(f"  加载副本{rep_id}: {xtc_path}")
        traj = io.load_trajectory(xtc_path, top_path)

        # 记录原始原子数
        if original_n_atoms is None:
            original_n_atoms = traj.n_atoms

        # 如果指定了原子选择，则在缓存前先过滤
        if atom_selection is not None:
            atom_indices = traj.topology.select(atom_selection)
            traj = traj.atom_slice(atom_indices)
            if rep_id == 0:
                logger.info(f"  原子选择: '{atom_selection}'")
                logger.info(f"  选中原子数: {traj.n_atoms}/{original_n_atoms}")

        traj_cache[rep_id] = traj

    logger.info(f"[OK] 所有轨迹已加载到内存")

    # 提取构象
    for i, sample_idx in enumerate(sample_indices):
        replica_id = replica_indices[sample_idx]
        cycle_id = cycle_indices[sample_idx]

        # 从缓存中获取轨迹
        traj = traj_cache[replica_id]

        # 提取指定帧
        coordinates.append(traj.xyz[cycle_id])  # shape=(n_atoms, 3)

        if extract_box:
            boxes.append(traj.unitcell_vectors[cycle_id])  # shape=(3, 3)

        # 进度日志
        if (i + 1) % 1000 == 0 or (i + 1) == n_samples:
            logger.info(f"  已提取: {i + 1}/{n_samples} ({(i+1)/n_samples*100:.1f}%)")

    coordinates = np.array(coordinates, dtype=np.float32)  # (n_samples, n_atoms, 3)

    # 使用最后一个轨迹的拓扑
    result = {
        'coordinates': coordinates,
        'n_atoms': coordinates.shape[1],
        'topology': traj.topology
    }

    if extract_box:
        result['box'] = np.array(boxes, dtype=np.float32)  # (n_samples, 3, 3)

    logger.info(f"[OK] 构象提取完成: shape={coordinates.shape}")

    return result


def extract_unscaled_energies(edr_paths: List[str],
                               sample_indices: np.ndarray,
                               replica_indices: np.ndarray,
                               cycle_indices: np.ndarray,
                               target_state: int = 0) -> np.ndarray:
    """
    提取还原后的势能（λ=1, 300K状态）

    Parameters
    ----------
    edr_paths : list of str
        EDR文件路径列表
    sample_indices : np.ndarray
        重采样后的全局样本索引
    replica_indices : np.ndarray
        replica_id映射
    cycle_indices : np.ndarray
        cycle_id映射
    target_state : int, optional
        目标Lambda状态索引（通常0对应λ=1）

    Returns
    -------
    energies : np.ndarray
        shape=(n_samples,) [kJ/mol]
    """
    from . import io

    n_samples = len(sample_indices)
    energies = []

    logger.info(f"从EDR提取 {n_samples} 个势能（目标状态{target_state}）...")

    # 缓存EDR数据（避免重复读取）
    edr_cache = {}

    for i, sample_idx in enumerate(sample_indices):
        replica_id = replica_indices[sample_idx]
        cycle_id = cycle_indices[sample_idx]

        # 读取EDR（使用缓存）
        if replica_id not in edr_cache:
            edr_path = edr_paths[replica_id]
            edr_cache[replica_id] = io.read_edr_file(edr_path)

        edr_df = edr_cache[replica_id]

        # 提取目标状态的能量
        # 优先使用多状态能量列，如果没有则使用Potential
        target_col = None

        # 尝试多种列名模式
        patterns = [
            f'dH/dl-lambda-{target_state}',
            f'Energy-lambda-{target_state}',
            f'U-lambda-{target_state}',
            f'dE/dl-lambda-{target_state}',
        ]

        for pattern in patterns:
            matching = [col for col in edr_df.columns if pattern in col]
            if matching:
                target_col = matching[0]
                break

        if target_col is None:
            # 如果没有多状态能量列，使用'Potential'
            if 'Potential' in edr_df.columns:
                target_col = 'Potential'
            else:
                raise ValueError(
                    f"EDR文件中未找到目标状态{target_state}的能量列，"
                    f"也没有'Potential'列"
                )

        # 提取该周期的能量
        try:
            energy = edr_df.iloc[cycle_id][target_col]
            energies.append(energy)
        except IndexError:
            raise ValueError(
                f"cycle_id={cycle_id} 超出EDR数据范围（共{len(edr_df)}个周期）"
            )

        # 进度日志
        if (i + 1) % 1000 == 0 or (i + 1) == n_samples:
            logger.info(f"  已提取: {i + 1}/{n_samples} ({(i+1)/n_samples*100:.1f}%)")

    energies = np.array(energies, dtype=np.float32)

    logger.info(f"[OK] 势能提取完成: shape={energies.shape}")
    logger.info(f"  能量范围: [{energies.min():.2e}, {energies.max():.2e}] kJ/mol")

    return energies


def compute_auxiliary_features(traj,
                               compute_phi: bool = True,
                               compute_psi: bool = True,
                               compute_chi1: bool = False) -> Dict:
    """
    计算辅助特征（二面角等）

    Parameters
    ----------
    traj : mdtraj.Trajectory
        轨迹对象
    compute_phi : bool, optional
        是否计算φ二面角
    compute_psi : bool, optional
        是否计算ψ二面角
    compute_chi1 : bool, optional
        是否计算χ1侧链二面角

    Returns
    -------
    features : dict
        {
            'phi': (n_frames, n_phi),      # [弧度]
            'psi': (n_frames, n_psi),      # [弧度]
            'chi1': (n_frames, n_chi1),    # [弧度] (可选)
        }
    """
    import mdtraj as md

    features = {}

    logger.info("计算辅助特征...")

    # φ二面角（主链）
    if compute_phi:
        try:
            phi_indices, phi_angles = md.compute_phi(traj)
            if len(phi_angles) > 0:
                features['phi'] = phi_angles
                logger.info(f"  [OK] φ二面角: {phi_angles.shape}")
        except Exception as e:
            logger.warning(f"  [WARN] φ二面角计算失败: {e}")

    # ψ二面角（主链）
    if compute_psi:
        try:
            psi_indices, psi_angles = md.compute_psi(traj)
            if len(psi_angles) > 0:
                features['psi'] = psi_angles
                logger.info(f"  [OK] ψ二面角: {psi_angles.shape}")
        except Exception as e:
            logger.warning(f"  [WARN] ψ二面角计算失败: {e}")

    # χ1侧链二面角
    if compute_chi1:
        try:
            chi1_indices, chi1_angles = md.compute_chi1(traj)
            if len(chi1_angles) > 0:
                features['chi1'] = chi1_angles
                logger.info(f"  [OK] χ1二面角: {chi1_angles.shape}")
        except Exception as e:
            logger.warning(f"  [WARN] χ1二面角计算失败（可能不适用于此系统）: {e}")

    return features


def build_training_dataset(xtc_paths: List[str],
                           edr_paths: List[str],
                           top_path: str,
                           mbar_weights: np.ndarray,
                           replica_indices: np.ndarray,
                           cycle_indices: np.ndarray,
                           n_target_samples: int = 10000,
                           target_state: int = 0,
                           resample_method: str = 'multinomial',
                           compute_dihedrals: bool = False,
                           random_seed: Optional[int] = None,
                           atom_selection: str = None) -> Dict:
    """
    构建完整训练数据集

    Parameters
    ----------
    xtc_paths : list of str
        XTC文件路径列表
    edr_paths : list of str
        EDR文件路径列表
    top_path : str
        拓扑文件路径
    mbar_weights : np.ndarray
        MBAR权重
    replica_indices : np.ndarray
        replica_id映射
    cycle_indices : np.ndarray
        cycle_id映射
    n_target_samples : int, optional
        目标样本数
    target_state : int, optional
        目标状态索引
    resample_method : str, optional
        重采样方法
    compute_dihedrals : bool, optional
        是否计算二面角特征
    random_seed : int, optional
        随机种子
    atom_selection : str, optional
        原子选择语法（mdtraj风格，例如: "not water and not resname SOL"）
        如果为None，则保存所有原子

    Returns
    -------
    dataset : dict
        完整训练数据集
    """
    logger.info("="*60)
    logger.info("构建训练数据集")
    logger.info("="*60)

    # 1. 重采样
    logger.info(f"\n[1/4] 重采样（目标: {n_target_samples} 个样本）...")
    resampled_indices = resample_by_weights(
        mbar_weights,
        n_target_samples,
        method=resample_method,
        random_seed=random_seed
    )

    # 2. 提取构象坐标
    logger.info(f"\n[2/4] 提取构象坐标...")
    config_result = extract_configurations(
        xtc_paths, top_path,
        resampled_indices,
        replica_indices,
        cycle_indices,
        extract_box=True,
        atom_selection=atom_selection
    )

    coordinates = config_result['coordinates']
    box = config_result.get('box', None)
    n_atoms = config_result['n_atoms']
    topology = config_result['topology']

    # 3. 提取还原势能
    logger.info(f"\n[3/4] 提取还原势能...")
    energies = extract_unscaled_energies(
        edr_paths,
        resampled_indices,
        replica_indices,
        cycle_indices,
        target_state=target_state
    )

    # 4. 计算辅助特征（可选）
    dihedrals = {}
    if compute_dihedrals:
        logger.info(f"\n[4/4] 计算辅助特征...")
        import mdtraj as md

        # 构建临时轨迹对象用于计算二面角
        temp_traj = md.Trajectory(coordinates, topology)
        dihedrals = compute_auxiliary_features(temp_traj)
    else:
        logger.info(f"\n[4/4] 跳过辅助特征计算")

    # 组装数据集
    dataset = {
        'coordinates': coordinates,
        'energies': energies,
        'n_atoms': n_atoms,
        'n_samples': len(coordinates),
        'original_indices': np.column_stack([
            replica_indices[resampled_indices],
            cycle_indices[resampled_indices]
        ])
    }

    if box is not None:
        dataset['box'] = box

    # 添加二面角（如果有）
    if 'phi' in dihedrals:
        dataset['phi'] = dihedrals['phi']
    if 'psi' in dihedrals:
        dataset['psi'] = dihedrals['psi']
    if 'chi1' in dihedrals:
        dataset['chi1'] = dihedrals['chi1']

    logger.info("\n" + "="*60)
    logger.info("训练数据集构建完成")
    logger.info("="*60)
    logger.info(f"样本数: {dataset['n_samples']}")
    logger.info(f"原子数: {dataset['n_atoms']}")
    logger.info(f"坐标形状: {dataset['coordinates'].shape}")
    logger.info(f"能量形状: {dataset['energies'].shape}")
    if 'box' in dataset:
        logger.info(f"盒子形状: {dataset['box'].shape}")
    if 'phi' in dataset:
        logger.info(f"φ二面角形状: {dataset['phi'].shape}")
    if 'psi' in dataset:
        logger.info(f"ψ二面角形状: {dataset['psi'].shape}")

    return dataset


def analyze_resampling_efficiency(original_weights: np.ndarray,
                                  resampled_indices: np.ndarray) -> Dict:
    """
    分析重采样效率

    Parameters
    ----------
    original_weights : np.ndarray
        原始MBAR权重
    resampled_indices : np.ndarray
        重采样后的索引

    Returns
    -------
    analysis : dict
        重采样效率分析结果
    """
    n_original = len(original_weights)
    n_resampled = len(resampled_indices)

    # 唯一样本数
    unique_indices = np.unique(resampled_indices)
    n_unique = len(unique_indices)

    # 计算每个原始样本被采样的次数
    counts = np.bincount(resampled_indices, minlength=n_original)

    # 计算有效样本数（ESS）
    weights_normalized = original_weights / original_weights.sum()
    ess = 1.0 / np.sum(weights_normalized**2)

    analysis = {
        'n_original': n_original,
        'n_resampled': n_resampled,
        'n_unique': n_unique,
        'unique_ratio': n_unique / n_resampled,
        'effective_sample_size': ess,
        'max_count': counts.max(),
        'mean_count': counts[counts > 0].mean(),
    }

    logger.info("重采样效率分析:")
    logger.info(f"  原始样本数: {n_original}")
    logger.info(f"  重采样数: {n_resampled}")
    logger.info(f"  唯一样本数: {n_unique} ({analysis['unique_ratio']*100:.1f}%)")
    logger.info(f"  有效样本数(ESS): {ess:.1f}")
    logger.info(f"  最大重复次数: {counts.max()}")

    return analysis
