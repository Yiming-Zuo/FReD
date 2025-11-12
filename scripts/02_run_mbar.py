#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
MBAR计算和诊断脚本

功能：
1. 加载MBAR输入数据
2. 子采样去相关（可选）
3. 运行MBAR计算
4. 计算诊断指标
5. 生成诊断图表
6. 保存MBAR权重和诊断报告

使用方法：
    conda activate femto_test
    python scripts/02_run_mbar.py [--skip-subsample] [--target-state 0]

参数：
    --skip-subsample: 跳过子采样步骤（直接使用原始数据）
    --target-state: 目标状态索引（默认0，对应λ=1, 300K）
"""

import sys
import argparse
from pathlib import Path
import numpy as np
import json
import logging

sys.path.insert(0, str(Path(__file__).parent))
from utils import io, mbar, visualization

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


def print_mbar_summary(mbar_obj, diagnostics: dict, weights: np.ndarray):
    """打印MBAR计算摘要"""
    print(f"\n{BOLD}{'='*60}{RESET}")
    print(f"{BOLD}MBAR计算摘要{RESET}")
    print(f"{BOLD}{'='*60}{RESET}")

    # 基本信息
    print(f"\n{BLUE}[1] 基本信息{RESET}")
    n_states = len(mbar_obj.f_k)
    print(f"  状态数: {n_states}")
    print(f"  总样本数: {weights.shape[0]}")

    # 自由能
    print(f"\n{BLUE}[2] 自由能{RESET}")
    f_k = diagnostics['free_energies']
    df_k = diagnostics['uncertainties']

    if f_k is not None and df_k is not None:
        # 相对于状态0
        f_k_rel = f_k - f_k[0]

        print(f"  {'状态':<8} {'ΔF (kT)':<15} {'不确定度 (kT)':<15}")
        print(f"  {'-'*40}")
        for i in range(min(n_states, 10)):  # 最多显示10个状态
            print(f"  {i:<8} {f_k_rel[i]:>12.4f}   ±{df_k[i]:>10.4f}")
        if n_states > 10:
            print(f"  ... (共{n_states}个状态)")
    else:
        print(f"  {RED}自由能数据不可用{RESET}")

    # Overlap诊断
    print(f"\n{BLUE}[3] Overlap诊断{RESET}")
    if diagnostics['overlap_matrix'] is not None:
        min_overlap = diagnostics['min_overlap']
        if min_overlap >= 0.03:
            status = f"{GREEN}✓{RESET}"
        else:
            status = f"{YELLOW}⚠{RESET}"
        print(f"  {status} 最小相邻overlap: {min_overlap:.4f}")
    else:
        print(f"  {RED}✗ Overlap矩阵计算失败{RESET}")

    # 有效样本数
    print(f"\n{BLUE}[4] 有效样本数{RESET}")
    ess = diagnostics['effective_sample_size']
    if ess >= 50:
        status = f"{GREEN}✓{RESET}"
    else:
        status = f"{YELLOW}⚠{RESET}"
    print(f"  {status} ESS: {ess:.1f}")

    # 权重统计
    print(f"\n{BLUE}[5] 权重统计{RESET}")
    print(f"  均值: {weights.mean():.2e}")
    print(f"  标准差: {weights.std():.2e}")
    print(f"  范围: [{weights.min():.2e}, {weights.max():.2e}]")
    print(f"  最大/最小比: {weights.max()/weights.min():.1f}")

    # 收敛性
    print(f"\n{BLUE}[6] 收敛性{RESET}")
    if diagnostics['is_converged']:
        print(f"  {GREEN}✓ MBAR计算收敛{RESET}")
    else:
        print(f"  {YELLOW}⚠ 存在警告（见下方）{RESET}")


def parse_args():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(
        description='MBAR重加权计算和诊断',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument(
        '--skip-subsample',
        action='store_true',
        help='跳过子采样步骤（直接使用原始数据）'
    )

    parser.add_argument(
        '--target-state',
        type=int,
        default=0,
        help='目标状态索引（默认0，对应λ=1, 300K）'
    )

    parser.add_argument(
        '--subsample-method',
        type=str,
        default='auto',
        choices=['auto', 'manual'],
        help='子采样方法（auto: 自动检测, manual: 手动指定）'
    )

    parser.add_argument(
        '--max-iter',
        type=int,
        default=10000,
        help='MBAR最大迭代次数（默认10000）'
    )

    return parser.parse_args()


def main():
    """主函数"""
    args = parse_args()

    print(f"{BOLD}{'='*60}{RESET}")
    print(f"{BOLD}FReD MBAR计算和诊断工具{RESET}")
    print(f"{BOLD}{'='*60}{RESET}")
    print()

    output_dir = Path('outputs')
    figures_dir = output_dir / 'figures'
    figures_dir.mkdir(parents=True, exist_ok=True)

    # ========== 1. 加载MBAR输入 ==========
    input_path = output_dir / 'mbar_input.npz'
    if not input_path.exists():
        print(f"{RED}错误: 未找到MBAR输入文件: {input_path}{RESET}")
        print(f"{YELLOW}请先运行: python scripts/01_prepare_mbar.py{RESET}")
        return 1

    print(f"{BLUE}[1/5] 加载MBAR输入数据...{RESET}")
    try:
        mbar_input = io.load_mbar_input(input_path)
        print(f"{GREEN}✓ 数据加载成功{RESET}")
    except Exception as e:
        print(f"{RED}错误: 数据加载失败 - {e}{RESET}")
        logger.exception("数据加载失败")
        return 1

    u_kn = mbar_input['u_kn']
    N_k = mbar_input['N_k']
    lambda_values = mbar_input.get('lambda_values', None)

    print(f"  u_kn shape: {u_kn.shape}")
    print(f"  N_k: {N_k}")
    print(f"  总样本数: {u_kn.shape[1]}")

    # ========== 2. 子采样去相关（可选）==========
    if args.skip_subsample:
        print(f"\n{YELLOW}[2/5] 跳过子采样（使用原始数据）{RESET}")
        u_kn_sub = u_kn
        N_k_sub = N_k
        subsample_info = None
    else:
        print(f"\n{BLUE}[2/5] 子采样去相关...{RESET}")
        try:
            subsample_result = mbar.subsample_all_states(
                u_kn, N_k, method=args.subsample_method
            )

            u_kn_sub = subsample_result['u_kn_sub']
            N_k_sub = subsample_result['N_k_sub']
            subsample_info = subsample_result['subsample_info']

            print(f"{GREEN}✓ 子采样完成{RESET}")
            print(f"  样本数: {u_kn.shape[1]} → {u_kn_sub.shape[1]}")
            print(f"  减少比例: {subsample_result['total_reduction']*100:.1f}%")
        except Exception as e:
            print(f"{YELLOW}⚠ 子采样失败，使用原始数据: {e}{RESET}")
            logger.exception("子采样失败")
            u_kn_sub = u_kn
            N_k_sub = N_k
            subsample_info = None

    # ========== 3. 运行MBAR计算 ==========
    print(f"\n{BLUE}[3/5] 运行MBAR计算...{RESET}")
    print(f"  目标状态: {args.target_state}")
    print(f"  最大迭代: {args.max_iter}")

    try:
        mbar_obj, weights = mbar.run_mbar(
            u_kn_sub, N_k_sub,
            target_state=args.target_state,
            maximum_iterations=args.max_iter,
            verbose=True
        )
        print(f"{GREEN}✓ MBAR计算成功{RESET}")
    except Exception as e:
        print(f"{RED}错误: MBAR计算失败 - {e}{RESET}")
        logger.exception("MBAR计算失败")
        return 1

    # ========== 4. 计算诊断指标 ==========
    print(f"\n{BLUE}[4/5] 计算诊断指标...{RESET}")
    try:
        diagnostics = mbar.compute_diagnostics(mbar_obj)
        print(f"{GREEN}✓ 诊断计算完成{RESET}")
    except Exception as e:
        print(f"{RED}错误: 诊断计算失败 - {e}{RESET}")
        logger.exception("诊断计算失败")
        return 1

    # 显示诊断摘要
    print_mbar_summary(mbar_obj, diagnostics, weights)

    # 显示警告
    if diagnostics['warnings']:
        print(f"\n{YELLOW}警告信息:{RESET}")
        for i, warning in enumerate(diagnostics['warnings'], 1):
            print(f"  {YELLOW}⚠ {i}. {warning}{RESET}")

    # ========== 5. 生成诊断图表 ==========
    print(f"\n{BLUE}[5/5] 生成诊断图表...{RESET}")
    try:
        visualization.plot_all_diagnostics(
            mbar_obj, weights, u_kn_sub,
            output_dir=str(figures_dir),
            lambda_values=lambda_values,
            subsample_info=subsample_info
        )
        print(f"{GREEN}✓ 诊断图表已保存到: {figures_dir}{RESET}")
    except Exception as e:
        print(f"{YELLOW}⚠ 图表生成失败: {e}{RESET}")
        logger.exception("图表生成失败")

    # ========== 6. 保存MBAR权重 ==========
    weights_path = output_dir / 'mbar_weights.npz'
    print(f"\n{BLUE}保存MBAR权重到: {weights_path}{RESET}")

    try:
        # 构建sample_indices (如果有subsample_info)
        if subsample_info is not None:
            # TODO: 从subsample_info重建sample_indices
            # 目前使用placeholder
            sample_indices = None
        else:
            sample_indices = None

        io.save_mbar_weights(
            weights_path,
            weights=weights,
            f_k=diagnostics['free_energies'],
            df_k=diagnostics['uncertainties'],
            sample_indices=sample_indices,
            target_state=args.target_state
        )
        print(f"{GREEN}✓ 权重已保存{RESET}")
    except Exception as e:
        print(f"{RED}错误: 权重保存失败 - {e}{RESET}")
        logger.exception("权重保存失败")
        return 1

    # ========== 7. 保存诊断报告JSON ==========
    diagnostics_path = output_dir / 'mbar_diagnostics.json'
    print(f"\n{BLUE}保存诊断报告到: {diagnostics_path}{RESET}")

    try:
        # 构建可JSON序列化的诊断报告
        report = {
            'target_state': args.target_state,
            'n_states': len(mbar_obj.f_k),
            'n_samples_original': int(u_kn.shape[1]),
            'n_samples_subsampled': int(u_kn_sub.shape[1]),
            'skip_subsample': args.skip_subsample,
            'min_overlap': float(diagnostics['min_overlap']) if diagnostics['overlap_matrix'] is not None else None,
            'effective_sample_size': float(diagnostics['effective_sample_size']),
            'is_converged': diagnostics['is_converged'],
            'warnings': diagnostics['warnings'],
            'free_energies': diagnostics['free_energies'].tolist() if diagnostics['free_energies'] is not None else None,
            'uncertainties': diagnostics['uncertainties'].tolist() if diagnostics['uncertainties'] is not None else None,
        }

        with open(diagnostics_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)

        print(f"{GREEN}✓ 诊断报告已保存{RESET}")
    except Exception as e:
        print(f"{YELLOW}⚠ 诊断报告保存失败: {e}{RESET}")
        logger.exception("诊断报告保存失败")

    # ========== 8. 成功完成 ==========
    print(f"\n{GREEN}{'='*60}{RESET}")
    print(f"{GREEN}✓ MBAR计算和诊断完成{RESET}")
    print(f"{GREEN}{'='*60}{RESET}")

    file_size_kb = weights_path.stat().st_size / 1024
    print(f"\n📁 输出文件:")
    print(f"  - 权重文件: {weights_path} ({file_size_kb:.2f} KB)")
    print(f"  - 诊断报告: {diagnostics_path}")
    print(f"  - 图表目录: {figures_dir}")

    print(f"\n➡️  下一步: 运行 python scripts/03_build_training_dataset.py")

    return 0


if __name__ == '__main__':
    sys.exit(main())
