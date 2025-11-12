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


def check_directory_structure(data_dir='data', expected_replicas=5):
    """
    检查副本目录结构

    Returns:
        dict: {
            'found': list of found replica dirs,
            'missing': list of missing replica dirs,
            'status': 'ok' or 'error'
        }
    """
    expected_dirs = [f'rep_{i}' for i in range(expected_replicas)]
    found_dirs = []
    missing_dirs = []

    for rep_dir in expected_dirs:
        rep_path = Path(data_dir) / rep_dir
        if rep_path.is_dir():
            found_dirs.append(rep_dir)
        else:
            missing_dirs.append(rep_dir)

    status = 'ok' if len(missing_dirs) == 0 else 'error'

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
            'has_lambda': bool,
            'columns': list,
            'status': str,
            'error': str (if any)
        }
    """
    try:
        import panedr
        df = panedr.edr_to_df(str(edr_path))

        # 检查关键列
        required_cols = ['Time', 'Potential']
        has_required = all(col in df.columns for col in required_cols)

        # 检查是否有Lambda相关列
        lambda_cols = [col for col in df.columns if 'Lambda' in col or 'lambda' in col or 'dH' in col]
        has_lambda = len(lambda_cols) > 0

        return {
            'readable': True,
            'n_steps': len(df),
            'has_lambda': has_lambda,
            'lambda_columns': lambda_cols if has_lambda else [],
            'columns': list(df.columns),
            'status': 'ok' if has_required else 'warning',
            'error': None if has_required else 'Missing required columns'
        }
    except Exception as e:
        return {
            'readable': False,
            'n_steps': 0,
            'has_lambda': False,
            'lambda_columns': [],
            'columns': [],
            'status': 'error',
            'error': str(e)
        }


def validate_xtc_file(xtc_path, gro_path):
    """
    验证 XTC 文件格式

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
        # mdtraj需要GRO文件作为拓扑，不支持TPR
        traj = md.load(str(xtc_path), top=str(gro_path))

        return {
            'readable': True,
            'n_frames': traj.n_frames,
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
        print(f"  {RED}缺失: {', '.join(dir_check['missing'])}{RESET}")
    print()

    if dir_check['status'] == 'error':
        print(f"{RED}致命错误: 副本目录不完整，无法继续验证{RESET}")
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
            lambda_status = f"包含 Lambda 列" if edr_result['has_lambda'] else "无 Lambda 列"
            lambda_color = GREEN if edr_result['has_lambda'] else YELLOW
            print(f"  [{rep_dir}/prod.edr] {print_status_symbol(edr_result['status'])} "
                  f"可读取, {edr_result['n_steps']} 步, {lambda_color}{lambda_status}{RESET}")
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

    # ===== 生成摘要 =====
    print(f"{BOLD}{'='*60}{RESET}")
    print(f"{BOLD}验证摘要{RESET}")
    print(f"{BOLD}{'='*60}{RESET}")

    # 统计状态
    n_ok = sum(1 for v in file_checks.values() if v['status'] == 'ok')
    n_warning = sum(1 for v in file_checks.values() if v['status'] == 'warning')
    n_error = sum(1 for v in file_checks.values() if v['status'] == 'error')

    overall_status = 'error' if n_error > 0 else ('warning' if n_warning > 0 else 'ok')

    print(f"状态: {print_status_symbol(overall_status)} ", end='')
    if overall_status == 'ok':
        print(f"{GREEN}通过{RESET}")
    elif overall_status == 'warning':
        print(f"{YELLOW}通过（有警告）{RESET}")
    else:
        print(f"{RED}失败{RESET}")

    print(f"副本数: {dir_check['actual']}/{dir_check['expected']}")
    print(f"警告: {n_warning} 个")
    print(f"错误: {n_error} 个")

    # Lambda 能量列检查
    has_lambda_all = all(format_validations[rep]['edr'].get('has_lambda', False)
                         for rep in dir_check['found']
                         if rep in format_validations)

    if not has_lambda_all:
        print()
        print(f"{YELLOW}⚠️  重要提示:{RESET}")
        print(f"{YELLOW}  EDR 文件不包含 Lambda 能量列{RESET}")
        print(f"{YELLOW}  MBAR 分析需要所有 lambda 状态的能量{RESET}")
        print(f"{YELLOW}  建议: 使用 gmx mdrun -rerun 重新计算能量矩阵{RESET}")

    # 保存JSON报告
    report_dir = Path('outputs')
    report_dir.mkdir(exist_ok=True)

    report_data = {
        'directory_check': dir_check,
        'file_integrity': file_checks,
        'format_validation': format_validations,
        'summary': {
            'overall_status': overall_status,
            'n_ok': n_ok,
            'n_warning': n_warning,
            'n_error': n_error,
            'has_lambda_energy': has_lambda_all
        }
    }

    report_path = report_dir / 'validation_report.json'
    with open(report_path, 'w', encoding='utf-8') as f:
        json.dump(report_data, f, indent=2, ensure_ascii=False)

    print()
    print(f"详细报告已保存至: {report_path}")

    # 返回状态码
    return 0 if overall_status in ['ok', 'warning'] else 1


if __name__ == '__main__':
    sys.exit(main())
