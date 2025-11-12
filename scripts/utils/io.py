# -*- coding: utf-8 -*-
"""
文件读写工具模块

统一封装panedr、mdtraj等文件读取操作
"""

import numpy as np
import pandas as pd
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Union
import logging

logger = logging.getLogger(__name__)

def read_edr_file(edr_path: Union[str, Path]) -> pd.DataFrame:
    """
    读取GROMACS EDR文件

    Parameters
    ----------
    edr_path : str or Path
        EDR文件路径

    Returns
    -------
    df : pd.DataFrame
        包含所有能量项的DataFrame，索引为时间步
    """
    try:
        import panedr
    except ImportError:
        raise ImportError("需要安装panedr: pip install panedr")

    edr_path = Path(edr_path)
    if not edr_path.exists():
        raise FileNotFoundError(f"EDR文件不存在: {edr_path}")

    logger.info(f"读取EDR文件: {edr_path}")
    df = panedr.edr_to_df(str(edr_path))
    logger.info(f"读取完成，包含 {len(df)} 个时间步，{len(df.columns)} 列")

    return df


def read_log_file(log_path: Union[str, Path]) -> str:
    """
    读取GROMACS LOG文件

    Parameters
    ----------
    log_path : str or Path
        LOG文件路径

    Returns
    -------
    content : str
        LOG文件全部内容
    """
    log_path = Path(log_path)
    if not log_path.exists():
        raise FileNotFoundError(f"LOG文件不存在: {log_path}")

    logger.info(f"读取LOG文件: {log_path}")
    with open(log_path, 'r') as f:
        content = f.read()

    return content


def load_trajectory(xtc_path: Union[str, Path],
                    top_path: Union[str, Path],
                    stride: int = 1) -> 'mdtraj.Trajectory':
    """
    加载GROMACS轨迹文件

    Parameters
    ----------
    xtc_path : str or Path
        XTC轨迹文件路径
    top_path : str or Path
        拓扑文件路径（GRO/PDB）
    stride : int, default=1
        采样间隔，1表示读取所有帧

    Returns
    -------
    traj : mdtraj.Trajectory
        轨迹对象
    """
    try:
        import mdtraj as md
    except ImportError:
        raise ImportError("需要安装mdtraj: conda install -c conda-forge mdtraj")

    xtc_path = Path(xtc_path)
    top_path = Path(top_path)

    if not xtc_path.exists():
        raise FileNotFoundError(f"XTC文件不存在: {xtc_path}")
    if not top_path.exists():
        raise FileNotFoundError(f"拓扑文件不存在: {top_path}")

    logger.info(f"加载轨迹: {xtc_path}, 拓扑: {top_path}, stride={stride}")
    traj = md.load(str(xtc_path), top=str(top_path), stride=stride)
    logger.info(f"加载完成，包含 {traj.n_frames} 帧，{traj.n_atoms} 个原子")

    return traj


def load_trajectory_frame(xtc_path: Union[str, Path],
                          top_path: Union[str, Path],
                          frame_index: int) -> 'mdtraj.Trajectory':
    """
    加载轨迹的单个帧

    Parameters
    ----------
    xtc_path : str or Path
        XTC轨迹文件路径
    top_path : str or Path
        拓扑文件路径
    frame_index : int
        帧索引（从0开始）

    Returns
    -------
    traj : mdtraj.Trajectory
        包含单帧的轨迹对象
    """
    try:
        import mdtraj as md
    except ImportError:
        raise ImportError("需要安装mdtraj: conda install -c conda-forge mdtraj")

    traj = md.load_frame(str(xtc_path), index=frame_index, top=str(top_path))
    return traj


def save_mbar_input(output_path: Union[str, Path],
                    u_kn: np.ndarray,
                    N_k: np.ndarray,
                    replica_to_state: Optional[np.ndarray] = None,
                    **metadata) -> None:
    """
    保存MBAR输入数据

    Parameters
    ----------
    output_path : str or Path
        输出文件路径（.npz格式）
    u_kn : np.ndarray, shape=(n_states, n_samples_total)
        能量矩阵
    N_k : np.ndarray, shape=(n_states,)
        每个状态的样本数
    replica_to_state : np.ndarray, optional, shape=(n_cycles, n_replicas)
        副本到状态的映射
    **metadata : dict
        其他元数据（temperatures, lambda_values等）
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    save_dict = {
        'u_kn': u_kn,
        'N_k': N_k,
    }

    if replica_to_state is not None:
        save_dict['replica_to_state'] = replica_to_state

    # 添加元数据
    save_dict.update(metadata)

    logger.info(f"保存MBAR输入数据到: {output_path}")
    logger.info(f"  u_kn shape: {u_kn.shape}")
    logger.info(f"  N_k shape: {N_k.shape}")
    if replica_to_state is not None:
        logger.info(f"  replica_to_state shape: {replica_to_state.shape}")

    np.savez_compressed(output_path, **save_dict)
    logger.info("保存完成")


def load_mbar_input(input_path: Union[str, Path]) -> Dict:
    """
    加载MBAR输入数据

    Parameters
    ----------
    input_path : str or Path
        MBAR输入文件路径（.npz格式）

    Returns
    -------
    data : dict
        包含u_kn, N_k及其他元数据的字典
    """
    input_path = Path(input_path)
    if not input_path.exists():
        raise FileNotFoundError(f"MBAR输入文件不存在: {input_path}")

    logger.info(f"加载MBAR输入数据: {input_path}")
    data = dict(np.load(input_path, allow_pickle=True))

    logger.info(f"  u_kn shape: {data['u_kn'].shape}")
    logger.info(f"  N_k shape: {data['N_k'].shape}")
    if 'replica_to_state' in data:
        logger.info(f"  replica_to_state shape: {data['replica_to_state'].shape}")

    return data


def save_mbar_weights(output_path: Union[str, Path],
                      weights: np.ndarray,
                      f_k: np.ndarray,
                      df_k: np.ndarray,
                      sample_indices: Optional[np.ndarray] = None,
                      **kwargs) -> None:
    """
    保存MBAR权重

    Parameters
    ----------
    output_path : str or Path
        输出文件路径（.npz格式）
    weights : np.ndarray
        MBAR权重
    f_k : np.ndarray
        各状态的自由能
    df_k : np.ndarray
        自由能不确定度
    sample_indices : np.ndarray, optional
        样本索引 (replica_id, cycle_id)
    **kwargs : dict
        其他元数据
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    save_dict = {
        'weights': weights,
        'f_k': f_k,
        'df_k': df_k,
    }

    if sample_indices is not None:
        save_dict['sample_indices'] = sample_indices

    save_dict.update(kwargs)

    logger.info(f"保存MBAR权重到: {output_path}")
    logger.info(f"  weights shape: {weights.shape}")
    logger.info(f"  f_k shape: {f_k.shape}")

    np.savez_compressed(output_path, **save_dict)
    logger.info("保存完成")


def load_mbar_weights(input_path: Union[str, Path]) -> Dict:
    """
    加载MBAR权重

    Parameters
    ----------
    input_path : str or Path
        MBAR权重文件路径（.npz格式）

    Returns
    -------
    data : dict
        包含weights, f_k, df_k等的字典
    """
    input_path = Path(input_path)
    if not input_path.exists():
        raise FileNotFoundError(f"MBAR权重文件不存在: {input_path}")

    logger.info(f"加载MBAR权重: {input_path}")
    data = dict(np.load(input_path, allow_pickle=True))

    logger.info(f"  weights shape: {data['weights'].shape}")
    logger.info(f"  f_k shape: {data['f_k'].shape}")

    return data


def save_training_dataset_npz(output_path: Union[str, Path],
                               coordinates: np.ndarray,
                               energies: np.ndarray,
                               **kwargs) -> None:
    """
    保存训练数据集（NPZ格式）

    Parameters
    ----------
    output_path : str or Path
        输出文件路径（.npz格式）
    coordinates : np.ndarray, shape=(n_samples, n_atoms, 3)
        构象坐标 [nm]
    energies : np.ndarray, shape=(n_samples,)
        还原后的势能 [kJ/mol]
    **kwargs : dict
        其他数据（box, phi, psi, original_indices等）
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    save_dict = {
        'coordinates': coordinates,
        'energies': energies,
        'n_atoms': coordinates.shape[1],
    }

    save_dict.update(kwargs)

    logger.info(f"保存训练数据集到: {output_path}")
    logger.info(f"  coordinates shape: {coordinates.shape}")
    logger.info(f"  energies shape: {energies.shape}")
    logger.info(f"  其他字段: {list(kwargs.keys())}")

    np.savez_compressed(output_path, **save_dict)

    file_size_mb = output_path.stat().st_size / 1024 / 1024
    logger.info(f"保存完成，文件大小: {file_size_mb:.2f} MB")


def load_training_dataset_npz(input_path: Union[str, Path]) -> Dict:
    """
    加载训练数据集（NPZ格式）

    Parameters
    ----------
    input_path : str or Path
        训练数据集文件路径（.npz格式）

    Returns
    -------
    data : dict
        包含coordinates, energies等的字典
    """
    input_path = Path(input_path)
    if not input_path.exists():
        raise FileNotFoundError(f"训练数据集文件不存在: {input_path}")

    logger.info(f"加载训练数据集: {input_path}")
    data = dict(np.load(input_path, allow_pickle=True))

    logger.info(f"  coordinates shape: {data['coordinates'].shape}")
    logger.info(f"  energies shape: {data['energies'].shape}")
    logger.info(f"  所有字段: {list(data.keys())}")

    return data
