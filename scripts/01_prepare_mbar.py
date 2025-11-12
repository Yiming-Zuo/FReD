#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
MBAR输入数据准备脚本

功能：
1. 运行数据验证
2. 提取能量矩阵
3. 解析副本交换记录
4. 构建replica→state映射
5. 保存MBAR输入数据

使用方法：
    conda activate fred
    python scripts/01_prepare_mbar.py
"""

import sys
from pathlib import Path
import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
from utils import validation, preprocessing, io

# 颜色代码
GREEN = '\033[92m'
YELLOW = '\033[93m'
RED = '\033[91m'
BLUE = '\033[94m'
RESET = '\033[0m'
BOLD = '\033[1m'


def print_statistics(mbar_input: dict):
    """打印MBAR输入数据统计"""
    print(f"\n{BOLD}{'='*60}{RESET}")
    print(f"{BOLD}MBAR输入数据统计{RESET}")
    print(f"{BOLD}{'='*60}{RESET}")

    # 基本信息
    print(f"\n{BLUE}[1] 基本信息{RESET}")
    print(f"  副本数: {mbar_input['n_replicas']}")
    print(f"  状态数: {mbar_input['n_states']}")
    print(f"  周期数: {mbar_input['n_cycles']}")
    print(f"  总样本数: {mbar_input['u_kn'].shape[1]}")

    # Lambda值
    print(f"\n{BLUE}[2] Lambda状态{RESET}")
    for i, lam in enumerate(mbar_input['lambda_values']):
        print(f"  状态{i}: λ = {lam}")

    # 能量统计
    u_kn = mbar_input['u_kn']
    print(f"\n{BLUE}[3] 能量矩阵统计{RESET}")
    print(f"  形状: {u_kn.shape}")
    print(f"  范围: [{np.min(u_kn):.2e}, {np.max(u_kn):.2e}] kJ/mol")
    print(f"  平均: {np.mean(u_kn):.2e} kJ/mol")

    for state_idx in range(min(3, u_kn.shape[0])):  # 显示前3个状态
        state_mean = np.mean(u_kn[state_idx, :])
        state_std = np.std(u_kn[state_idx, :])
        print(f"    状态{state_idx}: 均值={state_mean:.2e}, 标准差={state_std:.2e}")

    # 交换统计
    exchange_stats = mbar_input['exchange_statistics']
    print(f"\n{BLUE}[4] 交换统计{RESET}")
    print(f"  总交换轮次: {exchange_stats['total_exchange_rounds']}")
    print(f"  总交换尝试: {exchange_stats['total_exchange_attempts']}")
    print(f"  平均副本迁移率: {exchange_stats['mean_mobility']:.2f} 个状态")

    # 副本迁移详情
    mobility = exchange_stats['replica_mobility']
    print(f"\n{BLUE}[5] 副本迁移详情{RESET}")
    for rep_idx, mob in enumerate(mobility):
        print(f"  副本{rep_idx}: 访问了 {mob} 个不同状态")


def main():
    """主函数"""
    print(f"{BOLD}{'='*60}{RESET}")
    print(f"{BOLD}FReD MBAR输入数据准备工具{RESET}")
    print(f"{BOLD}{'='*60}{RESET}")
    print()

    data_dir = Path('data')
    output_dir = Path('outputs')
    output_dir.mkdir(exist_ok=True)

    # 1. 检查验证报告
    validation_report_path = output_dir / 'validation_report.json'

    if not validation_report_path.exists():
        print(f"{YELLOW}未找到验证报告，运行数据验证...{RESET}\n")
        report = validation.run_full_validation(data_dir)

        if report['summary']['overall_status'] == 'error':
            print(f"\n{RED}{'='*60}{RESET}")
            print(f"{RED}数据验证失败，请先修复错误{RESET}")
            print(f"{RED}{'='*60}{RESET}")
            return 1

        print(f"\n{GREEN}✓ 数据验证通过{RESET}")
    else:
        print(f"{GREEN}✓ 发现验证报告: {validation_report_path}{RESET}")

    # 2. 准备MBAR输入
    print(f"\n{BOLD}准备MBAR输入数据...{RESET}\n")

    try:
        mbar_input = preprocessing.prepare_mbar_input(
            data_dir=data_dir,
            validation_report_path=str(validation_report_path) if validation_report_path.exists() else None
        )
    except Exception as e:
        print(f"\n{RED}{'='*60}{RESET}")
        print(f"{RED}错误: {e}{RESET}")
        print(f"{RED}{'='*60}{RESET}")
        import traceback
        traceback.print_exc()
        return 1

    # 3. 保存MBAR输入
    output_path = output_dir / 'mbar_input.npz'
    print(f"\n{BLUE}保存MBAR输入数据到: {output_path}{RESET}")

    io.save_mbar_input(
        output_path,
        u_kn=mbar_input['u_kn'],
        N_k=mbar_input['N_k'],
        replica_to_state=mbar_input['replica_to_state'],
        lambda_values=mbar_input['lambda_values'],
        n_cycles=mbar_input['n_cycles'],
        n_replicas=mbar_input['n_replicas'],
        n_states=mbar_input['n_states']
    )

    print(f"{GREEN}✓ 数据已保存{RESET}")

    # 4. 显示统计
    print_statistics(mbar_input)

    # 5. 警告信息
    if mbar_input.get('warnings'):
        print(f"\n{YELLOW}警告信息:{RESET}")
        for warning in mbar_input['warnings']:
            print(f"  {YELLOW}⚠  {warning}{RESET}")

    # 6. 成功完成
    print(f"\n{GREEN}{'='*60}{RESET}")
    print(f"{GREEN}✓ MBAR输入数据准备完成{RESET}")
    print(f"{GREEN}{'='*60}{RESET}")
    print(f"\n📁 输出文件: {output_path}")
    print(f"📊 数据大小: {output_path.stat().st_size / 1024:.2f} KB")
    print(f"\n➡️  下一步: 运行 python scripts/02_run_mbar.py")

    return 0


if __name__ == '__main__':
    sys.exit(main())
