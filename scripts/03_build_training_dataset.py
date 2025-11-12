#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
训练数据集构建脚本

功能：
1. 加载MBAR权重
2. 按权重重采样
3. 提取构象坐标（从XTC）
4. 提取还原势能（从EDR）
5. 计算辅助特征（可选）
6. 保存训练数据集（NPZ格式）

使用方法：
    conda activate femto_test
    python scripts/03_build_training_dataset.py [--n-samples 10000] [--compute-dihedrals]

参数：
    --n-samples: 目标样本数（默认10000）
    --compute-dihedrals: 计算二面角特征
    --target-state: 目标状态索引（默认0）
    --resample-method: 重采样方法（multinomial或systematic，默认multinomial）
    --random-seed: 随机种子（用于可重复性）
"""

import sys
import argparse
from pathlib import Path
import numpy as np
import logging

sys.path.insert(0, str(Path(__file__).parent))
from utils import io, resampling, validation

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# 颜色代码
GREEN = '\033[92m'
YELLOW = '\033[93m'
RED = '\033[91m'
BLUE = '\033[94m'
RESET = '\033[0m'
BOLD = '\033[1m'


def print_dataset_summary(dataset: dict):
    """打印数据集摘要"""
    print(f"\n{BOLD}{'='*60}{RESET}")
    print(f"{BOLD}训练数据集摘要{RESET}")
    print(f"{BOLD}{'='*60}{RESET}")

    # 基本信息
    print(f"\n{BLUE}[1] 基本信息{RESET}")
    print(f"  样本数: {dataset['n_samples']}")
    print(f"  原子数: {dataset['n_atoms']}")

    # 数据形状
    print(f"\n{BLUE}[2] 数据维度{RESET}")
    print(f"  坐标: {dataset['coordinates'].shape}  ({dataset['coordinates'].dtype})")
    print(f"  能量: {dataset['energies'].shape}  ({dataset['energies'].dtype})")

    if 'box' in dataset:
        print(f"  盒子: {dataset['box'].shape}  ({dataset['box'].dtype})")

    # 辅助特征
    if 'phi' in dataset or 'psi' in dataset or 'chi1' in dataset:
        print(f"\n{BLUE}[3] 辅助特征{RESET}")
        if 'phi' in dataset:
            print(f"  φ二面角: {dataset['phi'].shape}")
        if 'psi' in dataset:
            print(f"  ψ二面角: {dataset['psi'].shape}")
        if 'chi1' in dataset:
            print(f"  χ1二面角: {dataset['chi1'].shape}")

    # 能量统计
    energies = dataset['energies']
    print(f"\n{BLUE}[4] 能量统计{RESET}")
    print(f"  范围: [{energies.min():.2e}, {energies.max():.2e}] kJ/mol")
    print(f"  均值: {energies.mean():.2e} kJ/mol")
    print(f"  标准差: {energies.std():.2e} kJ/mol")

    # 内存占用估算
    coords_size = dataset['coordinates'].nbytes / (1024**2)
    energies_size = dataset['energies'].nbytes / (1024**2)
    total_size = coords_size + energies_size

    if 'box' in dataset:
        box_size = dataset['box'].nbytes / (1024**2)
        total_size += box_size
    else:
        box_size = 0

    print(f"\n{BLUE}[5] 内存占用（估算）{RESET}")
    print(f"  坐标: {coords_size:.2f} MB")
    print(f"  能量: {energies_size:.2f} MB")
    if 'box' in dataset:
        print(f"  盒子: {box_size:.2f} MB")
    print(f"  总计: {total_size:.2f} MB")


def parse_args():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(
        description='训练数据集构建',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument(
        '--n-samples',
        type=int,
        default=10000,
        help='目标样本数（默认10000）'
    )

    parser.add_argument(
        '--compute-dihedrals',
        action='store_true',
        help='计算二面角特征（φ, ψ）'
    )

    parser.add_argument(
        '--target-state',
        type=int,
        default=0,
        help='目标状态索引（默认0，对应λ=1, 300K）'
    )

    parser.add_argument(
        '--resample-method',
        type=str,
        default='multinomial',
        choices=['multinomial', 'systematic'],
        help='重采样方法（默认multinomial）'
    )

    parser.add_argument(
        '--random-seed',
        type=int,
        default=None,
        help='随机种子（用于可重复性）'
    )

    return parser.parse_args()


def main():
    """主函数"""
    args = parse_args()

    print(f"{BOLD}{'='*60}{RESET}")
    print(f"{BOLD}FReD 训练数据集构建工具{RESET}")
    print(f"{BOLD}{'='*60}{RESET}")
    print()

    data_dir = Path('data')
    output_dir = Path('outputs')

    # ========== 1. 加载MBAR权重 ==========
    weights_path = output_dir / 'mbar_weights.npz'
    if not weights_path.exists():
        print(f"{RED}错误: 未找到MBAR权重文件: {weights_path}{RESET}")
        print(f"{YELLOW}请先运行: python scripts/02_run_mbar.py{RESET}")
        return 1

    print(f"{BLUE}[1/5] 加载MBAR权重...{RESET}")
    try:
        mbar_weights_data = io.load_mbar_weights(weights_path)
        weights = mbar_weights_data['weights']
        print(f"{GREEN}✓ 权重加载成功{RESET}")
        print(f"  权重形状: {weights.shape}")
    except Exception as e:
        print(f"{RED}错误: 权重加载失败 - {e}{RESET}")
        logger.exception("权重加载失败")
        return 1

    # 加载MBAR输入（获取sample_indices）
    mbar_input_path = output_dir / 'mbar_input.npz'
    if not mbar_input_path.exists():
        print(f"{RED}错误: 未找到MBAR输入文件: {mbar_input_path}{RESET}")
        return 1

    try:
        mbar_input = io.load_mbar_input(mbar_input_path)
        replica_indices = mbar_input['replica_indices']
        cycle_indices = mbar_input['cycle_indices']
        n_replicas = mbar_input['n_replicas']
        print(f"{GREEN}✓ MBAR输入加载成功{RESET}")
        print(f"  副本数: {n_replicas}")
    except Exception as e:
        print(f"{RED}错误: MBAR输入加载失败 - {e}{RESET}")
        logger.exception("MBAR输入加载失败")
        return 1

    # ========== 2. 准备文件路径 ==========
    print(f"\n{BLUE}[2/5] 准备文件路径...{RESET}")
    try:
        dir_check = validation.check_directory_structure(data_dir)
        replica_dirs = dir_check['found']

        if not replica_dirs:
            print(f"{RED}错误: 未找到副本目录{RESET}")
            return 1

        xtc_paths = [str(data_dir / rep / 'prod.xtc') for rep in replica_dirs]
        edr_paths = [str(data_dir / rep / 'prod.edr') for rep in replica_dirs]
        top_path = str(data_dir / replica_dirs[0] / 'prod.gro')

        print(f"{GREEN}✓ 文件路径准备完成{RESET}")
        print(f"  副本目录: {', '.join(replica_dirs)}")
        print(f"  拓扑文件: {top_path}")
    except Exception as e:
        print(f"{RED}错误: 文件路径准备失败 - {e}{RESET}")
        logger.exception("文件路径准备失败")
        return 1

    # ========== 3. 构建训练数据集 ==========
    print(f"\n{BLUE}[3/5] 构建训练数据集...{RESET}")
    print(f"  目标样本数: {args.n_samples}")
    print(f"  重采样方法: {args.resample_method}")
    print(f"  计算二面角: {'是' if args.compute_dihedrals else '否'}")
    if args.random_seed is not None:
        print(f"  随机种子: {args.random_seed}")

    try:
        dataset = resampling.build_training_dataset(
            xtc_paths=xtc_paths,
            edr_paths=edr_paths,
            top_path=top_path,
            mbar_weights=weights,
            replica_indices=replica_indices,
            cycle_indices=cycle_indices,
            n_target_samples=args.n_samples,
            target_state=args.target_state,
            resample_method=args.resample_method,
            compute_dihedrals=args.compute_dihedrals,
            random_seed=args.random_seed
        )
        print(f"\n{GREEN}✓ 数据集构建完成{RESET}")
    except Exception as e:
        print(f"\n{RED}错误: 数据集构建失败 - {e}{RESET}")
        logger.exception("数据集构建失败")
        return 1

    # ========== 4. 显示数据集摘要 ==========
    print_dataset_summary(dataset)

    # ========== 5. 保存训练数据集 ==========
    output_path = output_dir / 'training_dataset.npz'
    print(f"\n{BLUE}[4/5] 保存训练数据集到: {output_path}{RESET}")

    try:
        # 准备保存的数据
        save_data = {
            'coordinates': dataset['coordinates'],
            'energies': dataset['energies'],
            'n_atoms': dataset['n_atoms'],
            'original_indices': dataset['original_indices']
        }

        # 添加可选字段
        if 'box' in dataset:
            save_data['box'] = dataset['box']
        if 'phi' in dataset:
            save_data['phi'] = dataset['phi']
        if 'psi' in dataset:
            save_data['psi'] = dataset['psi']
        if 'chi1' in dataset:
            save_data['chi1'] = dataset['chi1']

        io.save_training_dataset_npz(output_path, **save_data)

        print(f"{GREEN}✓ 数据集已保存{RESET}")
    except Exception as e:
        print(f"{RED}错误: 数据集保存失败 - {e}{RESET}")
        logger.exception("数据集保存失败")
        return 1

    # ========== 6. 重采样效率分析 ==========
    print(f"\n{BLUE}[5/5] 重采样效率分析...{RESET}")
    try:
        # 需要重新生成resampled_indices用于分析
        resampled_indices = resampling.resample_by_weights(
            weights,
            args.n_samples,
            method=args.resample_method,
            random_seed=args.random_seed
        )

        analysis = resampling.analyze_resampling_efficiency(
            weights, resampled_indices
        )
        print(f"{GREEN}✓ 效率分析完成{RESET}")
    except Exception as e:
        print(f"{YELLOW}⚠ 效率分析失败: {e}{RESET}")
        logger.exception("效率分析失败")

    # ========== 7. 成功完成 ==========
    print(f"\n{GREEN}{'='*60}{RESET}")
    print(f"{GREEN}✓ 训练数据集构建完成{RESET}")
    print(f"{GREEN}{'='*60}{RESET}")

    file_size_mb = output_path.stat().st_size / (1024**2)
    print(f"\n📁 输出文件:")
    print(f"  - 数据集文件: {output_path} ({file_size_mb:.2f} MB)")
    print(f"  - 数据格式: NPZ (NumPy压缩格式)")

    print(f"\n📊 数据集内容:")
    print(f"  - 样本数: {dataset['n_samples']}")
    print(f"  - 原子数: {dataset['n_atoms']}")
    print(f"  - 坐标: {dataset['coordinates'].shape}")
    print(f"  - 能量: {dataset['energies'].shape}")

    print(f"\n✨ 数据集可用于生成模型（如FreeFlow）训练")

    return 0


if __name__ == '__main__':
    sys.exit(main())
