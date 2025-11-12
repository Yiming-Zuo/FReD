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

# 导入验证工具
sys.path.insert(0, str(Path(__file__).parent))
from utils import validation

# 颜色代码（简单的ANSI终端颜色）
GREEN = '\033[92m'
YELLOW = '\033[93m'
RED = '\033[91m'
BLUE = '\033[94m'
RESET = '\033[0m'
BOLD = '\033[1m'


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

    # 运行完整验证
    print(f"{BLUE}运行完整数据验证...{RESET}\n")
    report = validation.run_full_validation(data_dir=data_dir)

    dir_check = report['directory_check']
    file_checks = report['file_checks']
    format_validations = report['format_validations']
    lambda_analysis = report['lambda_analysis']

    # ===== 步骤 1: 显示目录结构检查结果 =====
    print(f"{BLUE}[1/3] 副本目录结构{RESET}")
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

    # ===== 步骤 2: 显示文件完整性检查结果 =====
    print(f"{BLUE}[2/3] 文件完整性{RESET}")

    for rep_dir in dir_check['found']:
        integrity = file_checks[rep_dir]
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

    # ===== 步骤 3: 显示文件格式验证结果 =====
    print(f"{BLUE}[3/3] 文件格式验证{RESET}")

    for rep_dir in dir_check['found']:
        validations = format_validations[rep_dir]

        # 显示EDR验证结果
        edr_result = validations['edr']
        if edr_result['readable']:
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

        # 显示XTC验证结果
        xtc_result = validations['xtc']
        if xtc_result['readable']:
            print(f"  [{rep_dir}/prod.xtc] {print_status_symbol(xtc_result['status'])} "
                  f"可读取, {xtc_result['n_frames']} 帧, {xtc_result['n_atoms']} 原子")
        else:
            print(f"  [{rep_dir}/prod.xtc] {print_status_symbol('error')} "
                  f"{RED}无法读取: {xtc_result['error']}{RESET}")

        # 显示LOG验证结果
        log_result = validations['log']
        if log_result['readable']:
            exchange_status = "检测到副本交换" if log_result['has_replica_exchange'] else "未检测到副本交换"
            exchange_color = GREEN if log_result['has_replica_exchange'] else YELLOW
            print(f"  [{rep_dir}/prod.log] {print_status_symbol(log_result['status'])} "
                  f"{exchange_color}{exchange_status}{RESET}")
        else:
            print(f"  [{rep_dir}/prod.log] {print_status_symbol('error')} "
                  f"{RED}无法读取: {log_result['error']}{RESET}")

    print()

    # ===== Lambda 参数验证 =====
    print(f"{BOLD}Lambda 参数验证:{RESET}")

    # 1. 副本Lambda标签
    print(f"\n{BOLD}(1) 副本Lambda标签:{RESET}")
    if lambda_analysis['has_replica_lambda_all'] and lambda_analysis['replica_lambda_values']:
        if lambda_analysis['n_unique_lambdas'] == 1:
            lambda_val = lambda_analysis['unique_lambdas'][0]
            print(f"{YELLOW}  ⚠️  所有副本的 Lambda 值都相同: {lambda_val:.3f}{RESET}")
            print(f"{YELLOW}     可能的问题: REST2 设置不正确或数据有问题{RESET}")
        else:
            print(f"{GREEN}  ✓ 检测到 {lambda_analysis['n_unique_lambdas']} 个不同的 Lambda 值{RESET}")
            for rep, lam_val in sorted(lambda_analysis['replica_lambda_values'].items()):
                print(f"    {rep}: λ = {lam_val:.3f}")
    else:
        print(f"{YELLOW}  ⚠️  部分或全部副本缺少 Lambda 标签{RESET}")

    # 2. 多状态能量列
    print(f"\n{BOLD}(2) 多状态能量列（MBAR必需）:{RESET}")
    if lambda_analysis['has_multistate_energy_all']:
        n_states = lambda_analysis['n_multistate_cols']
        print(f"{GREEN}  ✓ 所有副本都包含 {n_states} 个状态的能量列{RESET}")
        print(f"{GREEN}    可以进行 MBAR 分析{RESET}")
    else:
        print(f"{RED}  ✗ 缺少多状态能量列{RESET}")
        print(f"{RED}    无法进行 MBAR 分析{RESET}")
        print(f"{YELLOW}    建议: 使用 gmx mdrun -rerun 重新计算多状态能量矩阵{RESET}")

    # 3. 模拟类型判断
    print(f"\n{BOLD}(3) 模拟类型判断:{RESET}")
    if lambda_analysis['is_rest2']:
        if lambda_analysis['is_mbar_ready']:
            print(f"{GREEN}  ✓ 确认为 REST2 模拟，数据完整{RESET}")
        else:
            print(f"{YELLOW}  ⚠️  疑似 REST2 模拟，但缺少多状态能量{RESET}")
    else:
        if lambda_analysis['has_multistate_energy_all']:
            print(f"{YELLOW}  ⚠️  有多状态能量，但副本Lambda标签异常{RESET}")
        else:
            print(f"{YELLOW}  ⚠️  可能不是标准的 REST2 模拟{RESET}")

    # ===== 保存JSON报告 =====
    report_dir = Path('outputs')
    report_dir.mkdir(exist_ok=True)

    # 简化报告（只显示问题项）
    report_data = {
        'summary': report['summary'],
        'issues': report['issues'],
        'lambda_analysis': {
            'replica_lambda_values': lambda_analysis['replica_lambda_values'],
            'n_unique_lambdas': lambda_analysis['n_unique_lambdas'],
            'has_multistate_energy': lambda_analysis['has_multistate_energy_all'],
            'n_multistate_cols': lambda_analysis['n_multistate_cols']
        }
    }

    report_path = report_dir / 'validation_report.json'
    with open(report_path, 'w', encoding='utf-8') as f:
        json.dump(report_data, f, indent=2, ensure_ascii=False)

    # ===== 打印最终验证摘要 =====
    print()
    print(f"{BOLD}{'='*60}{RESET}")
    print(f"{BOLD}验证摘要{RESET}")
    print(f"{BOLD}{'='*60}{RESET}")

    overall_status = report['summary']['overall_status']
    print(f"状态: {print_status_symbol(overall_status)} ", end='')
    if overall_status == 'ok':
        print(f"{GREEN}通过{RESET}")
    elif overall_status == 'warning':
        print(f"{YELLOW}通过（有警告）{RESET}")
    else:
        print(f"{RED}失败{RESET}")

    print(f"副本数: {report['summary']['n_replicas']}")
    print(f"问题数: {report['summary']['n_issues']}")
    print()
    print(f"详细报告已保存至: {report_path}")

    # 返回状态码：error返回1，warning和ok返回0
    if overall_status == 'error':
        return 1
    else:
        return 0


if __name__ == '__main__':
    sys.exit(main())
