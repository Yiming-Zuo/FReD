#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
轨迹快速分析工具

功能：
1. 显示轨迹基本信息（帧数、原子数、时间范围）
2. 计算RMSD（可选参考结构）
3. 计算回旋半径
4. 显示盒子大小统计

使用方法：
    conda activate fred
    python scripts/tools/analyze_trajectory.py <xtc_file> <topology> [options]

参数：
    --info: 仅显示基本信息
    --rmsd: 计算RMSD
    --ref: 参考结构（用于RMSD计算）
    --rg: 计算回旋半径
    --selection: 原子选择表达式（默认protein）
"""

import sys
import argparse
from pathlib import Path
import numpy as np

# 添加utils路径
sys.path.insert(0, str(Path(__file__).parent.parent))
from utils import io

# 颜色代码
GREEN = '\033[92m'
YELLOW = '\033[93m'
RED = '\033[91m'
BLUE = '\033[94m'
RESET = '\033[0m'
BOLD = '\033[1m'


def show_basic_info(traj):
    """显示轨迹基本信息"""
    print(f"\n{BOLD}{'='*60}{RESET}")
    print(f"{BOLD}轨迹基本信息{RESET}")
    print(f"{BOLD}{'='*60}{RESET}")

    print(f"帧数: {traj.n_frames}")
    print(f"原子数: {traj.n_atoms}")
    print(f"残基数: {traj.n_residues}")

    # 时间范围
    if traj.time is not None:
        time_min = traj.time.min()
        time_max = traj.time.max()
        time_range = time_max - time_min
        print(f"时间范围: {time_min:.1f} - {time_max:.1f} ps ({time_range/1000:.2f} ns)")
        print(f"时间步长: {(time_range/(traj.n_frames-1)):.2f} ps/frame")

    # 盒子信息
    if traj.unitcell_vectors is not None:
        box_lengths = traj.unitcell_lengths  # shape=(n_frames, 3)
        mean_box = box_lengths.mean(axis=0)
        print(f"\n{BLUE}盒子大小（平均）:{RESET}")
        print(f"  X: {mean_box[0]:.3f} nm")
        print(f"  Y: {mean_box[1]:.3f} nm")
        print(f"  Z: {mean_box[2]:.3f} nm")

    # 拓扑信息
    print(f"\n{BLUE}拓扑信息:{RESET}")
    print(f"  链数: {traj.n_chains}")

    # 残基类型统计
    residue_names = [r.name for r in traj.topology.residues]
    unique_residues = set(residue_names)
    print(f"  残基类型数: {len(unique_residues)}")


def compute_and_show_rmsd(traj, reference=None, selection='protein'):
    """计算并显示RMSD"""
    import mdtraj as md

    print(f"\n{BOLD}{'='*60}{RESET}")
    print(f"{BOLD}RMSD 分析{RESET}")
    print(f"{BOLD}{'='*60}{RESET}")

    # 选择原子
    try:
        atom_indices = traj.topology.select(selection)
        print(f"选择: {selection}")
        print(f"原子数: {len(atom_indices)}")
    except Exception as e:
        print(f"{RED}错误: 原子选择失败 - {e}{RESET}")
        return

    if len(atom_indices) == 0:
        print(f"{YELLOW}警告: 选择的原子数为0{RESET}")
        return

    # 确定参考结构
    if reference is None:
        reference = traj[0]
        ref_frame = 0
        print(f"参考结构: 第0帧")
    else:
        ref_frame = 'external'
        print(f"参考结构: 外部文件")

    # 计算RMSD
    try:
        rmsd = md.rmsd(traj, reference, atom_indices=atom_indices) * 10  # 转换为Å
        print(f"\n{BLUE}RMSD统计:{RESET}")
        print(f"  均值: {rmsd.mean():.3f} ± {rmsd.std():.3f} Å")
        print(f"  范围: [{rmsd.min():.3f}, {rmsd.max():.3f}] Å")
        print(f"  中位数: {np.median(rmsd):.3f} Å")
    except Exception as e:
        print(f"{RED}错误: RMSD计算失败 - {e}{RESET}")


def compute_and_show_rg(traj, selection='protein'):
    """计算并显示回旋半径"""
    import mdtraj as md

    print(f"\n{BOLD}{'='*60}{RESET}")
    print(f"{BOLD}回旋半径分析{RESET}")
    print(f"{BOLD}{'='*60}{RESET}")

    # 选择原子
    try:
        atom_indices = traj.topology.select(selection)
        print(f"选择: {selection}")
        print(f"原子数: {len(atom_indices)}")
    except Exception as e:
        print(f"{RED}错误: 原子选择失败 - {e}{RESET}")
        return

    if len(atom_indices) == 0:
        print(f"{YELLOW}警告: 选择的原子数为0{RESET}")
        return

    # 计算回旋半径
    try:
        # 创建选择后的子轨迹
        traj_subset = traj.atom_slice(atom_indices)
        rg = md.compute_rg(traj_subset) * 10  # 转换为Å

        print(f"\n{BLUE}回旋半径统计:{RESET}")
        print(f"  均值: {rg.mean():.3f} ± {rg.std():.3f} Å")
        print(f"  范围: [{rg.min():.3f}, {rg.max():.3f}] Å")
        print(f"  中位数: {np.median(rg):.3f} Å")
    except Exception as e:
        print(f"{RED}错误: 回旋半径计算失败 - {e}{RESET}")


def parse_args():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(
        description='轨迹快速分析工具',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument(
        'xtc_file',
        type=str,
        nargs='?',
        default=None,
        help='XTC轨迹文件路径'
    )

    parser.add_argument(
        'topology',
        type=str,
        nargs='?',
        default=None,
        help='拓扑文件路径（GRO或PDB）'
    )

    parser.add_argument(
        '--info',
        action='store_true',
        help='仅显示基本信息'
    )

    parser.add_argument(
        '--rmsd',
        action='store_true',
        help='计算RMSD'
    )

    parser.add_argument(
        '--ref',
        type=str,
        default=None,
        help='参考结构文件（用于RMSD计算）'
    )

    parser.add_argument(
        '--rg',
        action='store_true',
        help='计算回旋半径'
    )

    parser.add_argument(
        '--selection',
        type=str,
        default='protein',
        help='原子选择表达式（默认protein）'
    )

    parser.add_argument(
        '--stride',
        type=int,
        default=1,
        help='采样间隔（默认1，读取所有帧）'
    )

    return parser.parse_args()


def main():
    """主函数"""
    args = parse_args()

    # 检查参数
    if args.xtc_file is None or args.topology is None:
        print(f"{YELLOW}使用方法: python {Path(__file__).name} <xtc_file> <topology> [options]{RESET}")
        print(f"\n示例:")
        print(f"  python {Path(__file__).name} prod.xtc prod.gro --info")
        print(f"  python {Path(__file__).name} prod.xtc prod.gro --rmsd --rg")
        print(f"  python {Path(__file__).name} prod.xtc prod.gro --rmsd --ref=ref.pdb")
        return 1

    xtc_file = Path(args.xtc_file)
    topology = Path(args.topology)

    if not xtc_file.exists():
        print(f"{RED}错误: XTC文件不存在 - {xtc_file}{RESET}")
        return 1

    if not topology.exists():
        print(f"{RED}错误: 拓扑文件不存在 - {topology}{RESET}")
        return 1

    # 读取轨迹
    print(f"{BLUE}读取轨迹...{RESET}")
    print(f"  XTC: {xtc_file}")
    print(f"  拓扑: {topology}")
    print(f"  采样间隔: {args.stride}")

    try:
        traj = io.load_trajectory(str(xtc_file), str(topology), stride=args.stride)
        print(f"{GREEN}[OK] 轨迹加载成功{RESET}")
    except Exception as e:
        print(f"{RED}错误: 轨迹加载失败 - {e}{RESET}")
        return 1

    # 根据参数选择分析内容
    if args.info:
        # 仅显示基本信息
        show_basic_info(traj)

    elif args.rmsd or args.rg:
        # 显示基本信息
        show_basic_info(traj)

        # RMSD分析
        if args.rmsd:
            reference = None
            if args.ref is not None:
                ref_path = Path(args.ref)
                if ref_path.exists():
                    import mdtraj as md
                    try:
                        reference = md.load(str(ref_path))
                        print(f"\n{GREEN}[OK] 参考结构加载成功: {ref_path}{RESET}")
                    except Exception as e:
                        print(f"{YELLOW}警告: 参考结构加载失败 - {e}{RESET}")
                        print(f"{YELLOW}使用第0帧作为参考{RESET}")
                else:
                    print(f"{YELLOW}警告: 参考结构不存在 - {ref_path}{RESET}")
                    print(f"{YELLOW}使用第0帧作为参考{RESET}")

            compute_and_show_rmsd(traj, reference=reference, selection=args.selection)

        # 回旋半径分析
        if args.rg:
            compute_and_show_rg(traj, selection=args.selection)

    else:
        # 默认：完整分析
        show_basic_info(traj)
        compute_and_show_rmsd(traj, reference=None, selection=args.selection)
        compute_and_show_rg(traj, selection=args.selection)

    return 0


if __name__ == '__main__':
    sys.exit(main())
