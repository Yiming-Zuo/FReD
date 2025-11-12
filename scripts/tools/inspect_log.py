#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
LOG文件交换统计分析工具

功能：
1. 解析副本交换记录
2. 计算交换统计（轮次、尝试次数）
3. 显示副本迁移率
4. 显示前N次交换记录

使用方法：
    conda activate femto_test
    python scripts/tools/inspect_log.py <log_file> [options]

参数：
    --summary: 仅显示摘要统计
    --mobility: 显示副本迁移详情
    --exchanges N: 显示前N次交换记录
"""

import sys
import argparse
from pathlib import Path
import numpy as np

# 添加utils路径
sys.path.insert(0, str(Path(__file__).parent.parent))
from utils import io, preprocessing

# 颜色代码
GREEN = '\033[92m'
YELLOW = '\033[93m'
RED = '\033[91m'
BLUE = '\033[94m'
RESET = '\033[0m'
BOLD = '\033[1m'


def show_summary(exchange_records, replica_to_state=None):
    """显示交换摘要统计"""
    print(f"\n{BOLD}{'='*60}{RESET}")
    print(f"{BOLD}交换摘要统计{RESET}")
    print(f"{BOLD}{'='*60}{RESET}")

    exchanges = exchange_records['exchanges']

    # 基本统计
    total_rounds = len(exchanges)
    total_attempts = sum(len(ex['replica_pairs']) for ex in exchanges)

    print(f"总交换轮次: {total_rounds}")
    print(f"总交换尝试: {total_attempts}")

    if total_rounds > 0:
        print(f"平均每轮尝试数: {total_attempts/total_rounds:.2f}")

    # 如果有replica_to_state，计算迁移率
    if replica_to_state is not None:
        n_cycles, n_replicas = replica_to_state.shape

        mobility = np.array([
            len(np.unique(replica_to_state[:, r])) for r in range(n_replicas)
        ])

        mean_mobility = mobility.mean()

        print(f"\n{BLUE}副本迁移统计:{RESET}")
        print(f"  平均迁移率: {mean_mobility:.2f} 个状态")
        print(f"  最大迁移率: {mobility.max()} 个状态")
        print(f"  最小迁移率: {mobility.min()} 个状态")


def show_mobility_details(replica_to_state):
    """显示副本迁移详情"""
    n_cycles, n_replicas = replica_to_state.shape

    print(f"\n{BOLD}{'='*60}{RESET}")
    print(f"{BOLD}副本迁移详情{RESET}")
    print(f"{BOLD}{'='*60}{RESET}")

    for rep_idx in range(n_replicas):
        states_visited = np.unique(replica_to_state[:, rep_idx])
        n_visited = len(states_visited)

        print(f"副本{rep_idx}: 访问了 {n_visited} 个不同状态", end='')

        if n_visited <= 10:
            print(f"  {sorted(states_visited)}")
        else:
            print(f"  ({states_visited.min()} ~ {states_visited.max()})")


def show_exchange_records(exchange_records, n_show=10):
    """显示前N次交换记录"""
    exchanges = exchange_records['exchanges']

    print(f"\n{BOLD}{'='*60}{RESET}")
    print(f"{BOLD}前{min(n_show, len(exchanges))}次交换记录{RESET}")
    print(f"{BOLD}{'='*60}{RESET}")

    for i, exchange in enumerate(exchanges[:n_show], 1):
        pairs = exchange['replica_pairs']
        pairs_str = ', '.join([f"({r1}↔{r2})" for r1, r2 in pairs])
        print(f"{i:3d}. {pairs_str}")

    if len(exchanges) > n_show:
        print(f"... (共{len(exchanges)}次交换，仅显示前{n_show}次)")


def show_exchange_matrix(replica_to_state, max_display=20):
    """显示交换矩阵（简化版）"""
    n_cycles, n_replicas = replica_to_state.shape

    print(f"\n{BOLD}{'='*60}{RESET}")
    print(f"{BOLD}副本-状态映射（前{min(max_display, n_cycles)}个周期）{RESET}")
    print(f"{BOLD}{'='*60}{RESET}")

    # 表头
    print(f"{'周期':>6s}", end='')
    for rep in range(n_replicas):
        print(f" Rep{rep:1d}", end='')
    print()
    print('-' * (6 + 5 * n_replicas))

    # 显示前N个周期
    for cycle in range(min(max_display, n_cycles)):
        print(f"{cycle:6d}", end='')
        for rep in range(n_replicas):
            state = replica_to_state[cycle, rep]
            print(f"  {state:2d} ", end='')
        print()

    if n_cycles > max_display:
        print(f"... (共{n_cycles}个周期，仅显示前{max_display}个)")


def parse_args():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(
        description='LOG文件交换统计分析工具',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument(
        'log_file',
        type=str,
        nargs='?',
        default=None,
        help='LOG文件路径'
    )

    parser.add_argument(
        '--summary',
        action='store_true',
        help='仅显示摘要统计'
    )

    parser.add_argument(
        '--mobility',
        action='store_true',
        help='显示副本迁移详情'
    )

    parser.add_argument(
        '--exchanges',
        type=int,
        default=0,
        metavar='N',
        help='显示前N次交换记录'
    )

    parser.add_argument(
        '--matrix',
        type=int,
        default=0,
        metavar='N',
        help='显示前N个周期的副本-状态矩阵'
    )

    parser.add_argument(
        '--n-replicas',
        type=int,
        default=None,
        help='副本数量（用于重建状态映射）'
    )

    return parser.parse_args()


def main():
    """主函数"""
    args = parse_args()

    # 确定LOG文件路径
    if args.log_file is None:
        print(f"{YELLOW}未指定LOG文件{RESET}")
        print(f"使用方法: python {Path(__file__).name} <log_file> [options]")
        return 1

    log_file = Path(args.log_file)

    if not log_file.exists():
        print(f"{RED}错误: 文件不存在 - {log_file}{RESET}")
        return 1

    # 读取并解析LOG文件
    print(f"{BLUE}读取: {log_file}{RESET}")

    try:
        exchange_records = preprocessing.parse_gromacs_log(log_file)
    except Exception as e:
        print(f"{RED}错误: 解析失败 - {e}{RESET}")
        return 1

    if not exchange_records['exchanges']:
        print(f"{YELLOW}警告: 未找到交换记录{RESET}")
        return 0

    # 尝试重建replica_to_state映射
    replica_to_state = None

    if args.n_replicas is not None:
        n_replicas = args.n_replicas
        n_cycles = len(exchange_records['exchanges']) + 1

        try:
            replica_to_state = preprocessing.build_replica_state_mapping(
                exchange_records,
                n_replicas=n_replicas,
                n_cycles=n_cycles
            )
        except Exception as e:
            print(f"{YELLOW}警告: 状态映射重建失败 - {e}{RESET}")

    # 根据参数选择显示内容
    if args.summary:
        # 仅显示摘要
        show_summary(exchange_records, replica_to_state)

    elif args.mobility and replica_to_state is not None:
        # 显示迁移详情
        show_mobility_details(replica_to_state)

    elif args.exchanges > 0:
        # 显示交换记录
        show_exchange_records(exchange_records, args.exchanges)

    elif args.matrix > 0 and replica_to_state is not None:
        # 显示状态矩阵
        show_exchange_matrix(replica_to_state, args.matrix)

    else:
        # 完整显示
        show_summary(exchange_records, replica_to_state)

        if args.n_replicas is not None and replica_to_state is not None:
            show_mobility_details(replica_to_state)
            show_exchange_matrix(replica_to_state, max_display=20)

        # 默认显示前10次交换
        show_exchange_records(exchange_records, n_show=10)

    return 0


if __name__ == '__main__':
    sys.exit(main())
