#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
数据完整性验证脚本

功能：
1. 检查所有 replica 目录是否存在
2. 检查必需文件（EDR, XTC, LOG, TPR, GRO）是否完整
3. 验证文件大小和基本格式
4. 生成数据摘要报告

使用方法：
    conda activate femto_test
    python scripts/00_data_validation.py
"""

import os
import sys
from pathlib import Path
import json

# 颜色代码（简单的ANSI终端颜色）
GREEN = '\033[92m'
YELLOW = '\033[93m'
RED = '\033[91m'
BLUE = '\033[94m'
RESET = '\033[0m'
BOLD = '\033[1m'

# 文件大小阈值（字节）
FILE_SIZE_LIMITS = {
    'prod.edr': 100 * 1024,      # 100 KB
    'prod.xtc': 1 * 1024 * 1024,  # 1 MB
    'prod.log': 1 * 1024 * 1024,  # 1 MB
    'prod.tpr': 10 * 1024,        # 10 KB
    'prod.gro': 10 * 1024,        # 10 KB
}

REQUIRED_FILES = list(FILE_SIZE_LIMITS.keys())


def check_directory_structure(data_dir='data', expected_replicas=None):
    """
    检查副本目录结构（支持自动发现）

    Args:
        data_dir: 数据目录路径
        expected_replicas: 期望的副本数量，None表示自动适应实际数量

    Returns:
        dict: {
            'found': list of found replica dirs,
            'missing': list of missing replica dirs,
            'status': 'ok', 'warning', or 'error'
            'expected': int,
            'actual': int
        }
    """
    data_path = Path(data_dir)

    # 自动发现所有rep_*目录
    found_dirs = sorted([d.name for d in data_path.iterdir()
                        if d.is_dir() and d.name.startswith('rep_')
                        and d.name.split('_')[1].isdigit()])

    if not found_dirs:
        return {
            'found': [],
            'missing': [],
            'status': 'error',
            'expected': expected_replicas or 0,
            'actual': 0,
            'message': '未找到任何rep_*目录'
        }

    # 如果未指定期望数量，从找到的目录推断（假设rep_0到rep_N连续）
    if expected_replicas is None:
        indices = [int(d.split('_')[1]) for d in found_dirs]
        max_idx = max(indices)
        expected_replicas = max_idx + 1

    expected_dirs = [f'rep_{i}' for i in range(expected_replicas)]
    missing_dirs = [d for d in expected_dirs if d not in found_dirs]

    # 缺失副本降级为warning，允许继续验证剩余副本
    if missing_dirs:
        status = 'warning'
    else:
        status = 'ok'

    return {
        'found': found_dirs,
        'missing': missing_dirs,
        'status': status,
        'expected': expected_replicas,
        'actual': len(found_dirs)
    }


def check_file_integrity(rep_dir, data_dir='data'):
    """
    检查单个副本目录的文件完整性

    Returns:
        dict: {
            'replica': str,
            'files': {filename: {'exists': bool, 'size': int, 'readable': bool, 'status': str}},
            'status': 'ok', 'warning', or 'error'
        }
    """
    rep_path = Path(data_dir) / rep_dir
    file_checks = {}
    overall_status = 'ok'

    for filename in REQUIRED_FILES:
        file_path = rep_path / filename

        file_info = {
            'exists': file_path.exists(),
            'size': 0,
            'readable': False,
            'status': 'missing'
        }

        if file_info['exists']:
            try:
                file_info['size'] = file_path.stat().st_size
                file_info['readable'] = os.access(file_path, os.R_OK)

                # 检查文件大小
                min_size = FILE_SIZE_LIMITS[filename]
                if file_info['size'] < min_size:
                    file_info['status'] = 'warning'
                    overall_status = 'warning' if overall_status == 'ok' else overall_status
                elif file_info['readable']:
                    file_info['status'] = 'ok'
                else:
                    file_info['status'] = 'error'
                    overall_status = 'error'
            except Exception as e:
                file_info['status'] = 'error'
                file_info['error'] = str(e)
                overall_status = 'error'
        else:
            overall_status = 'error'

        file_checks[filename] = file_info

    return {
        'replica': rep_dir,
        'files': file_checks,
        'status': overall_status
    }


def validate_edr_file(edr_path):
    """
    验证 EDR 文件格式

    Returns:
        dict: {
            'readable': bool,
            'n_steps': int,
            'has_replica_lambda': bool,  # 副本的Lambda标签
            'replica_lambda_value': float or None,
            'has_multistate_energy': bool,  # 多状态能量列（MBAR需要）
            'multistate_energy_columns': list,
            'columns': list,
            'status': str,
            'error': str (if any)
        }
    """
    try:
        import panedr
        import numpy as np
        df = panedr.edr_to_df(str(edr_path))

        # 检查关键列
        required_cols = ['Time', 'Potential']
        has_required = all(col in df.columns for col in required_cols)

        # 1. 检查副本Lambda标签（Lamb-SOL, Lamb-UNL等）
        replica_lambda_col = None
        replica_lambda_value = None

        if 'Lamb-SOL' in df.columns:
            replica_lambda_col = 'Lamb-SOL'
        elif 'Lamb-UNL' in df.columns:
            replica_lambda_col = 'Lamb-UNL'
        elif 'Lambda' in df.columns:
            replica_lambda_col = 'Lambda'

        if replica_lambda_col:
            replica_lambda_value = float(df[replica_lambda_col].iloc[0])

        has_replica_lambda = replica_lambda_col is not None

        # 2. 检查多状态能量列（MBAR需要的）
        # 这些列通常命名为: dH/dl, Energy-lambda-0, Energy-lambda-1 等
        multistate_cols = []

        # 搜索可能的多状态能量列模式
        for col in df.columns:
            # 常见模式：dH/dl, dE/dl, Energy-lambda, U-lambda等
            if any(pattern in col for pattern in ['dH/dl', 'dE/dl', 'Energy-lambda', 'U-lambda', 'Energy-Lambda']):
                multistate_cols.append(col)

        has_multistate_energy = len(multistate_cols) > 0

        return {
            'readable': True,
            'n_steps': len(df),
            'has_replica_lambda': has_replica_lambda,
            'replica_lambda_column': replica_lambda_col,
            'replica_lambda_value': replica_lambda_value,
            'has_multistate_energy': has_multistate_energy,
            'multistate_energy_columns': multistate_cols,
            'n_multistate_cols': len(multistate_cols),
            'columns': list(df.columns),
            'status': 'ok' if has_required else 'warning',
            'error': None if has_required else 'Missing required columns'
        }
    except Exception as e:
        return {
            'readable': False,
            'n_steps': 0,
            'has_replica_lambda': False,
            'replica_lambda_column': None,
            'replica_lambda_value': None,
            'has_multistate_energy': False,
            'multistate_energy_columns': [],
            'n_multistate_cols': 0,
            'columns': [],
            'status': 'error',
            'error': str(e)
        }


def validate_xtc_file(xtc_path, gro_path):
    """
    验证 XTC 文件格式（轻量级：只读取头信息）

    Returns:
        dict: {
            'readable': bool,
            'n_frames': int,
            'n_atoms': int,
            'status': str,
            'error': str (if any)
        }
    """
    try:
        import mdtraj as md
        from mdtraj.formats import XTCTrajectoryFile

        # 只加载第一帧验证格式和原子数（避免加载整个轨迹）
        traj = md.load(str(xtc_path), top=str(gro_path), frame=0)

        # 使用XTCTrajectoryFile获取总帧数（不加载数据）
        with XTCTrajectoryFile(str(xtc_path)) as f:
            n_frames = len(f)

        return {
            'readable': True,
            'n_frames': n_frames,
            'n_atoms': traj.n_atoms,
            'status': 'ok',
            'error': None
        }
    except Exception as e:
        return {
            'readable': False,
            'n_frames': 0,
            'n_atoms': 0,
            'status': 'error',
            'error': str(e)
        }


def validate_log_file(log_path):
    """
    验证 LOG 文件格式

    Returns:
        dict: {
            'readable': bool,
            'has_replica_exchange': bool,
            'status': str,
            'error': str (if any)
        }
    """
    try:
        with open(log_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read(50000)  # 读前50KB，确保能读到交换信息

        has_replica_exchange = 'Replica exchange' in content or 'Repl ex' in content

        return {
            'readable': True,
            'has_replica_exchange': has_replica_exchange,
            'status': 'ok' if has_replica_exchange else 'warning',
            'error': None if has_replica_exchange else 'No replica exchange info found'
        }
    except Exception as e:
        return {
            'readable': False,
            'has_replica_exchange': False,
            'status': 'error',
            'error': str(e)
        }


def format_file_size(size_bytes):
    """格式化文件大小"""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.1f} TB"


def print_status_symbol(status):
    """打印状态符号"""
    if status == 'ok':
        return f"{GREEN}✓{RESET}"
    elif status == 'warning':
        return f"{YELLOW}⚠{RESET}"
    elif status == 'error' or status == 'missing':
        return f"{RED}✗{RESET}"
    else:
        return "?"


def main():
    """主函数"""
    print(f"{BOLD}{'='*60}{RESET}")
    print(f"{BOLD}FReD 数据验证工具{RESET}")
    print(f"{BOLD}{'='*60}{RESET}")
    print()

    data_dir = Path('data')
    if not data_dir.exists():
        print(f"{RED}错误: data/ 目录不存在{RESET}")
        return 1

    # ===== 步骤 1: 检查目录结构 =====
    print(f"{BLUE}[1/3] 检查副本目录结构...{RESET}")
    dir_check = check_directory_structure()

    print(f"  {print_status_symbol(dir_check['status'])} 发现 {dir_check['actual']}/{dir_check['expected']} 个副本目录", end='')
    if dir_check['found']:
        print(f" ({', '.join(dir_check['found'])})")
    else:
        print()

    if dir_check['missing']:
        print(f"  {YELLOW}缺失: {', '.join(dir_check['missing'])}{RESET}")
    print()

    # 只有完全没有副本才终止
    if dir_check['status'] == 'error':
        print(f"{RED}致命错误: {dir_check.get('message', '未找到任何副本目录')}{RESET}")
        return 1

    # ===== 步骤 2: 检查文件完整性 =====
    print(f"{BLUE}[2/3] 检查文件完整性...{RESET}")
    file_checks = {}

    for rep_dir in dir_check['found']:
        integrity = check_file_integrity(rep_dir)
        file_checks[rep_dir] = integrity

        status_symbol = print_status_symbol(integrity['status'])
        print(f"  [{rep_dir}] {status_symbol} ", end='')

        if integrity['status'] == 'ok':
            print("所有文件完整")
        else:
            missing_files = [f for f, info in integrity['files'].items() if info['status'] == 'missing']
            warning_files = [f for f, info in integrity['files'].items() if info['status'] == 'warning']

            if missing_files:
                print(f"{RED}缺失: {', '.join(missing_files)}{RESET}")
            elif warning_files:
                print(f"{YELLOW}警告: {', '.join(warning_files)} 文件过小{RESET}")
    print()

    # ===== 步骤 3: 验证文件格式 =====
    print(f"{BLUE}[3/3] 验证文件格式...{RESET}")

    format_validations = {}

    for rep_dir in dir_check['found']:
        rep_path = data_dir / rep_dir
        validations = {}

        # 验证 EDR
        edr_result = validate_edr_file(rep_path / 'prod.edr')
        validations['edr'] = edr_result

        if edr_result['readable']:
            # 显示副本Lambda和多状态能量信息
            info_parts = []

            if edr_result['has_replica_lambda']:
                lambda_val = edr_result['replica_lambda_value']
                info_parts.append(f"λ={lambda_val:.3f}")

            if edr_result['has_multistate_energy']:
                n_states = edr_result['n_multistate_cols']
                info_parts.append(f"{GREEN}{n_states}状态能量{RESET}")
            else:
                info_parts.append(f"{YELLOW}无多状态能量{RESET}")

            info_str = ", ".join(info_parts)

            print(f"  [{rep_dir}/prod.edr] {print_status_symbol(edr_result['status'])} "
                  f"可读取, {edr_result['n_steps']} 步, {info_str}")
        else:
            print(f"  [{rep_dir}/prod.edr] {print_status_symbol('error')} "
                  f"{RED}无法读取: {edr_result['error']}{RESET}")

        # 验证 XTC
        xtc_result = validate_xtc_file(rep_path / 'prod.xtc', rep_path / 'prod.gro')
        validations['xtc'] = xtc_result

        if xtc_result['readable']:
            print(f"  [{rep_dir}/prod.xtc] {print_status_symbol(xtc_result['status'])} "
                  f"可读取, {xtc_result['n_frames']} 帧, {xtc_result['n_atoms']} 原子")
        else:
            print(f"  [{rep_dir}/prod.xtc] {print_status_symbol('error')} "
                  f"{RED}无法读取: {xtc_result['error']}{RESET}")

        # 验证 LOG
        log_result = validate_log_file(rep_path / 'prod.log')
        validations['log'] = log_result

        if log_result['readable']:
            exchange_status = "检测到副本交换" if log_result['has_replica_exchange'] else "未检测到副本交换"
            exchange_color = GREEN if log_result['has_replica_exchange'] else YELLOW
            print(f"  [{rep_dir}/prod.log] {print_status_symbol(log_result['status'])} "
                  f"{exchange_color}{exchange_status}{RESET}")
        else:
            print(f"  [{rep_dir}/prod.log] {print_status_symbol('error')} "
                  f"{RED}无法读取: {log_result['error']}{RESET}")

        format_validations[rep_dir] = validations

    print()

    # ===== 统计文件完整性和格式验证问题 =====
    # 统计状态
    n_ok = sum(1 for v in file_checks.values() if v['status'] == 'ok')
    n_warning = sum(1 for v in file_checks.values() if v['status'] == 'warning')
    n_error = sum(1 for v in file_checks.values() if v['status'] == 'error')

    # 统计格式验证问题
    format_errors = 0
    format_warnings = 0
    for rep, validations in format_validations.items():
        for file_type, result in validations.items():
            if result['status'] == 'error':
                format_errors += 1
            elif result['status'] == 'warning':
                format_warnings += 1

    # 初步计算状态（仅基于文件完整性和格式验证）
    # 注意: 最终状态将在 Lambda 和多状态能量验证后确定
    if n_error > 0 or format_errors > 0:
        overall_status = 'error'
    elif n_warning > 0 or format_warnings > 0:
        overall_status = 'warning'
    else:
        overall_status = 'ok'

    # Lambda 参数验证
    print()
    print(f"{BOLD}Lambda 参数验证:{RESET}")

    replica_lambda_values = {}
    has_replica_lambda_all = True
    has_multistate_energy_all = True

    for rep in dir_check['found']:
        if rep in format_validations and 'edr' in format_validations[rep]:
            edr_info = format_validations[rep]['edr']
            if edr_info.get('has_replica_lambda'):
                replica_lambda_values[rep] = edr_info.get('replica_lambda_value')
            else:
                has_replica_lambda_all = False

            if not edr_info.get('has_multistate_energy'):
                has_multistate_energy_all = False

    # 1. 检查副本Lambda标签
    print(f"\n{BOLD}(1) 副本Lambda标签:{RESET}")
    if has_replica_lambda_all and replica_lambda_values:
        unique_lambdas = set(replica_lambda_values.values())

        if len(unique_lambdas) == 1:
            lambda_val = list(unique_lambdas)[0]
            print(f"{YELLOW}  ⚠️  所有副本的 Lambda 值都相同: {lambda_val:.3f}{RESET}")
            print(f"{YELLOW}     可能的问题: REST2 设置不正确或数据有问题{RESET}")
        else:
            print(f"{GREEN}  ✓ 检测到 {len(unique_lambdas)} 个不同的 Lambda 值{RESET}")
            for rep, lam_val in sorted(replica_lambda_values.items()):
                print(f"    {rep}: λ = {lam_val:.3f}")
    else:
        print(f"{YELLOW}  ⚠️  部分或全部副本缺少 Lambda 标签{RESET}")

    # 2. 检查多状态能量列（MBAR关键）
    print(f"\n{BOLD}(2) 多状态能量列（MBAR必需）:{RESET}")
    if has_multistate_energy_all:
        # 检查每个副本的多状态能量列数量
        n_states_list = []
        for rep in dir_check['found']:
            if rep in format_validations and 'edr' in format_validations[rep]:
                n_states = format_validations[rep]['edr'].get('n_multistate_cols', 0)
                n_states_list.append(n_states)

        if len(set(n_states_list)) == 1:
            n_states = n_states_list[0]
            print(f"{GREEN}  ✓ 所有副本都包含 {n_states} 个状态的能量列{RESET}")
            print(f"{GREEN}    可以进行 MBAR 分析{RESET}")
        else:
            print(f"{YELLOW}  ⚠️  不同副本的多状态能量列数量不一致{RESET}")
            for rep in dir_check['found']:
                if rep in format_validations:
                    n = format_validations[rep]['edr'].get('n_multistate_cols', 0)
                    print(f"    {rep}: {n} 列")
    else:
        print(f"{RED}  ✗ 缺少多状态能量列{RESET}")
        print(f"{RED}    无法进行 MBAR 分析{RESET}")
        print(f"{YELLOW}    建议: 使用 gmx mdrun -rerun 重新计算多状态能量矩阵{RESET}")
        overall_status = 'warning' if overall_status == 'ok' else overall_status

    # 3. 综合判断
    print(f"\n{BOLD}(3) 模拟类型判断:{RESET}")
    if has_replica_lambda_all and len(set(replica_lambda_values.values())) > 1:
        if has_multistate_energy_all:
            print(f"{GREEN}  ✓ 确认为 REST2 模拟，数据完整{RESET}")
        else:
            print(f"{YELLOW}  ⚠️  疑似 REST2 模拟，但缺少多状态能量{RESET}")
    else:
        if has_multistate_energy_all:
            print(f"{YELLOW}  ⚠️  有多状态能量，但副本Lambda标签异常{RESET}")
        else:
            print(f"{YELLOW}  ⚠️  可能不是标准的 REST2 模拟{RESET}")

    # 保存JSON报告（简化版：只显示问题项）
    report_dir = Path('outputs')
    report_dir.mkdir(exist_ok=True)

    # 收集问题项
    issues = []

    # 检查目录问题
    if dir_check['missing']:
        issues.append({
            'type': 'directory',
            'severity': 'error',
            'message': f"缺失副本目录: {', '.join(dir_check['missing'])}"
        })

    # 检查文件完整性问题
    for rep, check in file_checks.items():
        if check['status'] != 'ok':
            problem_files = [f for f, info in check['files'].items() if info['status'] != 'ok']
            issues.append({
                'type': 'file_integrity',
                'replica': rep,
                'severity': check['status'],
                'message': f"文件问题: {', '.join(problem_files)}"
            })

    # 检查格式验证问题
    for rep, validations in format_validations.items():
        for file_type, result in validations.items():
            if result['status'] == 'error':
                issues.append({
                    'type': 'format_validation',
                    'replica': rep,
                    'file': file_type,
                    'severity': 'error',
                    'message': f"{file_type.upper()}无法读取: {result.get('error', 'Unknown error')}"
                })

    # 检查Lambda问题
    if has_replica_lambda_all:
        if len(set(replica_lambda_values.values())) == 1:
            issues.append({
                'type': 'lambda',
                'severity': 'warning',
                'message': f"所有副本Lambda值相同: {list(replica_lambda_values.values())[0]}"
            })
    else:
        issues.append({
            'type': 'lambda',
            'severity': 'warning',
            'message': "部分副本缺少Lambda标签"
        })

    # 检查多状态能量问题
    if not has_multistate_energy_all:
        issues.append({
            'type': 'multistate_energy',
            'severity': 'error',
            'message': "缺少MBAR所需的多状态能量列",
            'solution': "使用 gmx mdrun -rerun 重新计算"
        })
        # 多状态能量缺失是致命问题，设为error
        overall_status = 'error'

    # ===== 打印最终验证摘要 =====
    print()
    print(f"{BOLD}{'='*60}{RESET}")
    print(f"{BOLD}验证摘要{RESET}")
    print(f"{BOLD}{'='*60}{RESET}")

    print(f"状态: {print_status_symbol(overall_status)} ", end='')
    if overall_status == 'ok':
        print(f"{GREEN}通过{RESET}")
    elif overall_status == 'warning':
        print(f"{YELLOW}通过（有警告）{RESET}")
    else:
        print(f"{RED}失败{RESET}")

    print(f"副本数: {dir_check['actual']}/{dir_check['expected']}")
    print(f"问题数: {len(issues)}")

    # 构建简化报告
    report_data = {
        'summary': {
            'overall_status': overall_status,
            'n_replicas': dir_check['actual'],
            'n_issues': len(issues),
            'is_rest2': has_replica_lambda_all and len(set(replica_lambda_values.values())) > 1 if replica_lambda_values else False,
            'is_mbar_ready': has_multistate_energy_all
        },
        'issues': issues,
        'lambda_analysis': {
            'replica_lambda_values': replica_lambda_values if replica_lambda_values else {},
            'n_unique_lambdas': len(set(replica_lambda_values.values())) if replica_lambda_values else 0,
            'has_multistate_energy': has_multistate_energy_all,
            'n_multistate_cols': n_states_list[0] if has_multistate_energy_all and n_states_list else 0
        }
    }

    report_path = report_dir / 'validation_report.json'
    with open(report_path, 'w', encoding='utf-8') as f:
        json.dump(report_data, f, indent=2, ensure_ascii=False)

    print()
    print(f"详细报告已保存至: {report_path}")

    # 返回状态码：error返回1，warning和ok返回0
    if overall_status == 'error':
        return 1
    else:
        return 0


if __name__ == '__main__':
    sys.exit(main())
