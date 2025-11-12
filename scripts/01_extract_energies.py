#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
从 GROMACS EDR 文件提取能量矩阵

功能：
1. 读取所有 replica 的 EDR 文件
2. 提取每个 replica 在所有温度状态下的势能
3. 构建 u_kn[cycle, replica, state] 能量矩阵
4. 保存为 NPZ 格式

使用方法：
    conda activate femto_test
    python scripts/01_extract_energies.py
"""

import numpy as np
import panedr
from pathlib import Path

# TODO: 导入工具模块
# from utils.edr_parser import extract_u_kn_matrix

def main():
    """主函数"""
    print("="*60)
    print("FReD 能量矩阵提取工具")
    print("="*60)

    # TODO: 实现以下功能
    # 1. 检查 EDR 文件中的能量项
    # 2. 判断是否包含多状态能量
    # 3. 提取或计算 u_kn 矩阵
    # 4. 保存到 outputs/energy_matrix.npz

    print("\nTODO: 实现能量矩阵提取")
    print("预期输出：")
    print("  - u_kn.shape = (n_cycles, n_replicas, n_states)")
    print("  - 保存路径: FReD/outputs/energy_matrix.npz")

    # 示例：读取 rep_0 的 EDR
    edr_path = Path("FReD/data/rep_0/prod.edr")
    if edr_path.exists():
        print(f"\n检查 {edr_path}...")
        df = panedr.edr_to_df(str(edr_path))
        print(f"可用能量项: {list(df.columns)}")
        print(f"数据帧数: {len(df)}")

        # 检查是否有 Lambda 相关的列
        lamb_cols = [col for col in df.columns if 'Lamb' in col or 'lambda' in col]
        if lamb_cols:
            print(f"\n找到 Lambda 相关列: {lamb_cols}")
            print("可能包含多状态能量信息")
        else:
            print("\n未找到 Lambda 相关列")
            print("可能需要使用 gmx mdrun -rerun 重新计算")

if __name__ == '__main__':
    main()
