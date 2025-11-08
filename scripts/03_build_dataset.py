#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
构建 MBAR 数据集

功能：
1. 整合能量矩阵和交换记录
2. 构建类似 OpenMM samples.arrow 的数据结构
3. 保存为标准化格式（Arrow/HDF5/NPZ）

数据集包含：
- u_kn[cycle, replica, state]: 能量矩阵
- replica_to_state_idx[cycle, replica]: 副本-状态映射
- n_proposed_swaps[cycle]: 提议的交换数
- n_accepted_swaps[cycle]: 接受的交换数
- step[cycle]: 对应的 GROMACS 步数

使用方法：
    conda activate femto_test
    python scripts/03_build_dataset.py
"""

import numpy as np
import pandas as pd
from pathlib import Path

# TODO: 可选择导入
# import pyarrow as pa
# import h5py

def main():
    """主函数"""
    print("="*60)
    print("FReD 数据集构建工具")
    print("="*60)

    # TODO: 实现以下功能
    # 1. 加载 outputs/energy_matrix.npz
    # 2. 加载 outputs/exchange_record.csv
    # 3. 验证数据一致性
    # 4. 构建统一数据集
    # 5. 保存为 outputs/dataset.arrow (或 .h5 / .npz)

    print("\nTODO: 实现数据集构建")
    print("预期输入：")
    print("  - FReD/outputs/energy_matrix.npz")
    print("  - FReD/outputs/exchange_record.csv")
    print("\n预期输出：")
    print("  - FReD/outputs/dataset.arrow")
    print("    或 FReD/outputs/dataset.h5")
    print("    或 FReD/outputs/dataset.npz")

    print("\n数据格式参考:")
    print("  类似于 test_alanine_dipeptide/outputs_v2_gpu/samples.arrow")
    print("  可以复用 MBAR 分析代码")

if __name__ == '__main__':
    main()
