#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
EDR 文件解析器

功能：
1. 读取 GROMACS EDR 文件
2. 提取能量时间序列
3. 构建能量矩阵（如果 EDR 包含多状态能量）
4. 验证数据完整性

依赖：
- panedr: EDR 文件读取
"""

import numpy as np
import pandas as pd
import panedr
from pathlib import Path
from typing import Dict, List, Tuple, Optional

def read_edr_file(edr_path: str) -> pd.DataFrame:
    """
    读取 EDR 文件并返回 DataFrame

    Args:
        edr_path: EDR 文件路径

    Returns:
        包含所有能量项的 DataFrame

    TODO: 实现
    """
    pass


def validate_edr_file(edr_path: str) -> bool:
    """
    验证 EDR 文件是否可读且完整

    Args:
        edr_path: EDR 文件路径

    Returns:
        True 如果文件有效

    TODO: 实现
    """
    pass


def extract_u_kn_matrix(edr_files: List[str], n_states: int) -> np.ndarray:
    """
    从多个 EDR 文件提取能量矩阵

    Args:
        edr_files: EDR 文件路径列表（每个 replica 一个）
        n_states: REST2 状态数

    Returns:
        u_kn: shape (n_cycles, n_replicas, n_states) 的能量矩阵

    核心问题：
    - GROMACS EDR 是否包含所有 λ 状态的能量？
    - 如果是：直接读取对应列
    - 如果否：需要重新运行 gmx mdrun -rerun

    TODO: 实现
    - 检查 EDR 中的能量项
    - 判断是否包含多状态能量
    - 如果包含，提取并重塑为 u_kn 格式
    - 如果不包含，提示用户需要 -rerun
    """
    pass


def get_lambda_columns(df: pd.DataFrame) -> List[str]:
    """
    从 DataFrame 中查找 Lambda 相关的列

    Args:
        df: EDR 数据的 DataFrame

    Returns:
        Lambda 列名列表

    TODO: 实现
    """
    pass
