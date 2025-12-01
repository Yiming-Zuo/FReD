#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
EDR文件快速检查工具

功能：
1. 显示基本信息（帧数、时间范围）
2. 显示热力学量统计
3. 检测Lambda参数（REST2）
4. 检测多状态能量列（MBAR就绪）
5. 列出所有能量列

使用方法：
    conda activate fred
    python scripts/tools/inspect_edr.py <edr_file> [options]

参数：
    --columns: 仅列出所有列名
    --lambda-check: 仅检查Lambda信息
    --mbar-ready: 检查MBAR就绪状态
"""

import sys
import argparse
from pathlib import Path
import re

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


def detect_multistate_energy(df):
    """检测多状态能量列"""
    patterns = [
        r'dH/dl-lambda-(\d+)',
        r'Energy-lambda-(\d+)',
        r'U-lambda-(\d+)',
        r'dE/dl-lambda-(\d+)',
    ]

    lambda_columns = []
    lambda_indices = set()

    for col in df.columns:
        for pattern in patterns:
            match = re.search(pattern, col)
            if match:
                lambda_idx = int(match.group(1))
                lambda_columns.append(col)
                lambda_indices.add(lambda_idx)
                break

    return {
        'has_multistate': len(lambda_columns) > 0,
        'n_states': len(lambda_indices),
        'columns': sorted(lambda_columns),
        'lambda_indices': sorted(lambda_indices)
    }


def detect_lambda_params(df):
    """检测Lambda参数"""
    lambda_cols = ['Lamb-UNL', 'Lamb-SOL', 'Lambda']

    detected = {}
    for col in lambda_cols:
        if col in df.columns:
            detected[col] = df[col].mean()

    return detected


def show_basic_info(df):
    """显示基本信息"""
    print(f"\n{BOLD}{'='*60}{RESET}")
    print(f"{BOLD}基本信息{RESET}")
    print(f"{BOLD}{'='*60}{RESET}")
    print(f"总帧数: {len(df)}")
    print(f"时间范围: {df['Time'].min():.0f} - {df['Time'].max():.0f} ps ({(df['Time'].max()-df['Time'].min())/1000:.1f} ns)")


def show_thermodynamics(df):
    """显示热力学量"""
    print(f"\n{BOLD}{'='*60}{RESET}")
    print(f"{BOLD}关键热力学量（平均值 ± 标准差）{RESET}")
    print(f"{BOLD}{'='*60}{RESET}")

    # 标准热力学量
    thermo_cols = {
        'Temperature': 'K',
        'Pressure': 'bar',
        'Potential': 'kJ/mol',
        'Kinetic En.': 'kJ/mol',
        'Total Energy': 'kJ/mol',
        'Volume': 'nm³',
        'Density': 'kg/m³'
    }

    for col, unit in thermo_cols.items():
        if col in df.columns:
            mean = df[col].mean()
            std = df[col].std()
            print(f"{col:15s}: {mean:8.2f} ± {std:6.2f} {unit}")


def show_energy_components(df):
    """显示能量组成"""
    energy_cols = ['Angle', 'LJ (SR)', 'Disper. corr.', 'Coulomb (SR)', 'Coul. recip.']

    if any(col in df.columns for col in energy_cols):
        print(f"\n{BOLD}{'='*60}{RESET}")
        print(f"{BOLD}能量组成（平均值）{RESET}")
        print(f"{BOLD}{'='*60}{RESET}")

        energy_map = {
            'Angle': '键角能',
            'LJ (SR)': 'LJ短程相互作用',
            'Disper. corr.': '色散校正',
            'Coulomb (SR)': '库伦短程',
            'Coul. recip.': '库伦倒空间'
        }

        for col, name in energy_map.items():
            if col in df.columns:
                print(f"{name:20s}: {df[col].mean():10.2f} kJ/mol")


def show_temperature_groups(df):
    """显示各组分温度（REST2）"""
    if 'T-UNL' in df.columns and 'T-SOL' in df.columns:
        print(f"\n{BOLD}{'='*60}{RESET}")
        print(f"{BOLD}各组分温度{RESET}")
        print(f"{BOLD}{'='*60}{RESET}")
        print(f"UNL (溶质):  {df['T-UNL'].mean():8.2f} ± {df['T-UNL'].std():6.2f} K")
        print(f"SOL (溶剂):  {df['T-SOL'].mean():8.2f} ± {df['T-SOL'].std():6.2f} K")


def show_lambda_info(df, show_multistate=True):
    """显示Lambda信息"""
    # 副本Lambda值
    lambda_params = detect_lambda_params(df)

    if lambda_params:
        print(f"\n{BOLD}{'='*60}{RESET}")
        print(f"{BOLD}REST2 Lambda 参数{RESET}")
        print(f"{BOLD}{'='*60}{RESET}")
        for param, value in lambda_params.items():
            print(f"{param}: {value:.4f}")

    # 多状态能量列
    if show_multistate:
        multistate = detect_multistate_energy(df)

        print(f"\n{BOLD}{'='*60}{RESET}")
        print(f"{BOLD}多状态能量检测（MBAR）{RESET}")
        print(f"{BOLD}{'='*60}{RESET}")

        if multistate['has_multistate']:
            print(f"{GREEN}[OK] 检测到 {multistate['n_states']} 个Lambda状态{RESET}")
            print(f"{GREEN}[OK] Lambda索引: {multistate['lambda_indices']}{RESET}")
            print(f"{GREEN}[OK] MBAR就绪: 是{RESET}")

            if len(multistate['columns']) <= 10:
                print(f"\n  多状态能量列:")
                for col in multistate['columns']:
                    print(f"    - {col}")
            else:
                print(f"\n  多状态能量列: {len(multistate['columns'])} 个")
                print(f"    前5个: {', '.join(multistate['columns'][:5])}")
                print(f"    后5个: {', '.join(multistate['columns'][-5:])}")
        else:
            print(f"{RED}[FAIL] 未检测到多状态能量列{RESET}")
            print(f"{RED}[FAIL] MBAR就绪: 否{RESET}")
            print(f"{YELLOW}提示: 需要使用 gmx mdrun -rerun 重新计算多状态能量{RESET}")


def show_all_columns(df):
    """列出所有列名"""
    print(f"\n{BOLD}{'='*60}{RESET}")
    print(f"{BOLD}所有能量列 (共{len(df.columns)}列){RESET}")
    print(f"{BOLD}{'='*60}{RESET}")

    for i, col in enumerate(df.columns, 1):
        print(f"{i:3d}. {col}")


def parse_args():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(
        description='EDR文件快速检查工具',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument(
        'edr_file',
        type=str,
        nargs='?',
        default=None,
        help='EDR文件路径'
    )

    parser.add_argument(
        '--columns',
        action='store_true',
        help='仅列出所有列名'
    )

    parser.add_argument(
        '--lambda-check',
        action='store_true',
        help='仅检查Lambda信息'
    )

    parser.add_argument(
        '--mbar-ready',
        action='store_true',
        help='仅检查MBAR就绪状态'
    )

    return parser.parse_args()


def main():
    """主函数"""
    args = parse_args()

    # 确定EDR文件路径
    if args.edr_file is None:
        print(f"{YELLOW}未指定EDR文件{RESET}")
        print(f"使用方法: python {Path(__file__).name} <edr_file> [options]")
        return 1

    edr_file = Path(args.edr_file)

    if not edr_file.exists():
        print(f"{RED}错误: 文件不存在 - {edr_file}{RESET}")
        return 1

    # 读取EDR文件
    print(f"{BLUE}读取: {edr_file}{RESET}")
    try:
        df = io.read_edr_file(edr_file)
    except Exception as e:
        print(f"{RED}错误: 读取失败 - {e}{RESET}")
        return 1

    # 根据参数选择显示内容
    if args.columns:
        # 仅列出列名
        show_all_columns(df)

    elif args.lambda_check:
        # 仅检查Lambda信息
        show_lambda_info(df, show_multistate=True)

    elif args.mbar_ready:
        # 仅检查MBAR就绪
        multistate = detect_multistate_energy(df)
        lambda_params = detect_lambda_params(df)

        print(f"\n{BOLD}MBAR就绪检查{RESET}")
        print(f"{'='*60}")

        if lambda_params:
            print(f"{GREEN}[OK] 检测到Lambda参数{RESET}")
        else:
            print(f"{YELLOW}[WARN] 未检测到Lambda参数{RESET}")

        if multistate['has_multistate']:
            print(f"{GREEN}[OK] 检测到多状态能量 ({multistate['n_states']} 个状态){RESET}")
            print(f"{GREEN}[OK] MBAR就绪: 是{RESET}")
        else:
            print(f"{RED}[FAIL] 未检测到多状态能量{RESET}")
            print(f"{RED}[FAIL] MBAR就绪: 否{RESET}")

    else:
        # 完整显示
        show_basic_info(df)
        show_thermodynamics(df)
        show_energy_components(df)
        show_temperature_groups(df)
        show_lambda_info(df, show_multistate=True)

    return 0


if __name__ == '__main__':
    sys.exit(main())
