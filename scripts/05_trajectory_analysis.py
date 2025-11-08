#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
轨迹分析

功能：
1. 读取 XTC 轨迹文件
2. 计算二面角（φ/ψ for 丙氨酸二肽）
3. 使用 MBAR 权重重加权
4. 生成 Ramachandran 图、自由能曲面等

注意：
- 当前系统是甲烷（CH₄），无二面角
- 如果后续更换为丙氨酸二肽，需要修改分析代码

使用方法：
    conda activate femto_test
    python scripts/05_trajectory_analysis.py
"""

import numpy as np
import mdtraj as md
import matplotlib.pyplot as plt
from pathlib import Path

# TODO: 导入工具模块
# from utils.xtc_reader import load_trajectories
# from utils.mbar_utils import reweight_histogram

def main():
    """主函数"""
    print("="*60)
    print("FReD 轨迹分析工具")
    print("="*60)

    # TODO: 实现以下功能
    # 1. 加载所有 replica 的 XTC 轨迹
    # 2. 计算结构性质（二面角、距离、RMSD 等）
    # 3. 加载 MBAR 权重
    # 4. 重加权计算目标状态的分布
    # 5. 生成图表

    print("\nTODO: 实现轨迹分析")
    print("预期分析：")
    print("  - Ramachandran 图（φ/ψ）")
    print("  - 自由能曲面")
    print("  - 构象占比统计")

    # 检查轨迹文件
    data_dir = Path("FReD/data")
    xtc_files = list(data_dir.glob("rep_*/prod.xtc"))
    print(f"\n找到 {len(xtc_files)} 个 XTC 文件")

    if xtc_files:
        # 示例：读取第一个轨迹
        xtc_path = xtc_files[0]
        gro_path = xtc_path.parent / "prod.gro"

        if gro_path.exists():
            print(f"\n加载轨迹: {xtc_path}")
            traj = md.load(str(xtc_path), top=str(gro_path))
            print(f"  帧数: {traj.n_frames}")
            print(f"  原子数: {traj.n_atoms}")
            print(f"  时间范围: {traj.time[0]:.2f} - {traj.time[-1]:.2f} ps")

            # 检查拓扑
            print(f"\n拓扑信息:")
            print(f"  残基数: {traj.n_residues}")
            print(f"  残基列表: {[res.name for res in traj.top.residues[:5]]}...")

            # 如果是丙氨酸二肽，计算二面角
            # phi, psi = md.compute_phi(traj), md.compute_psi(traj)
        else:
            print(f"警告: 未找到拓扑文件 {gro_path}")

if __name__ == '__main__':
    main()
