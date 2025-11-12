# -*- coding: utf-8 -*-
"""
数据验证工具模块

完整提取自00_data_validation.py的验证逻辑
包含目录检查、文件完整性验证、格式验证和Lambda参数分析
"""

import os
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union
import logging

logger = logging.getLogger(__name__)

# 文件大小阈值（字节）
FILE_SIZE_LIMITS = {
    'prod.edr': 100 * 1024,      # 100 KB
    'prod.xtc': 1 * 1024 * 1024,  # 1 MB
    'prod.log': 1 * 1024 * 1024,  # 1 MB
    'prod.tpr': 10 * 1024,        # 10 KB
    'prod.gro': 10 * 1024,        # 10 KB
}

REQUIRED_FILES = list(FILE_SIZE_LIMITS.keys())


def check_directory_structure(data_dir: Union[str, Path] = 'data',
                               expected_replicas: Optional[int] = None) -> Dict:
    """
    检查副本目录结构（支持自动发现）

    Parameters
    ----------
    data_dir : str or Path
        数据目录路径
    expected_replicas : int, optional
        期望的副本数量，None表示自动适应实际数量

    Returns
    -------
    result : dict
        {
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


def check_file_integrity(rep_dir: str, data_dir: Union[str, Path] = 'data') -> Dict:
    """
    检查单个副本目录的文件完整性

    Parameters
    ----------
    rep_dir : str
        副本目录名（如'rep_0'）
    data_dir : str or Path
        数据目录路径

    Returns
    -------
    result : dict
        {
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


def validate_edr_file(edr_path: Union[str, Path]) -> Dict:
    """
    验证EDR文件格式

    Parameters
    ----------
    edr_path : str or Path
        EDR文件路径

    Returns
    -------
    result : dict
        {
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


def validate_xtc_file(xtc_path: Union[str, Path],
                      gro_path: Union[str, Path]) -> Dict:
    """
    验证XTC文件格式（轻量级：只读取头信息）

    Parameters
    ----------
    xtc_path : str or Path
        XTC文件路径
    gro_path : str or Path
        GRO拓扑文件路径

    Returns
    -------
    result : dict
        {
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


def validate_log_file(log_path: Union[str, Path]) -> Dict:
    """
    验证LOG文件格式

    Parameters
    ----------
    log_path : str or Path
        LOG文件路径

    Returns
    -------
    result : dict
        {
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


def analyze_lambda_parameters(data_dir: Union[str, Path] = 'data',
                               replica_dirs: Optional[List[str]] = None) -> Dict:
    """
    分析所有副本的Lambda参数

    Parameters
    ----------
    data_dir : str or Path
        数据目录路径
    replica_dirs : list of str, optional
        副本目录列表，如果为None则自动发现

    Returns
    -------
    result : dict
        {
            'replica_lambda_values': dict,  # {rep_dir: lambda_value}
            'unique_lambdas': list,  # 唯一的Lambda值（排序）
            'n_unique_lambdas': int,
            'has_replica_lambda_all': bool,  # 所有副本都有Lambda标签
            'has_multistate_energy_all': bool,  # 所有副本都有多状态能量
            'n_multistate_cols': int,  # 多状态能量列数
            'is_rest2': bool,  # 是否确认为REST2模拟
            'is_mbar_ready': bool,  # 是否可以进行MBAR分析
            'status': str,
            'issues': list
        }
    """
    data_path = Path(data_dir)

    # 如果未提供副本列表，自动发现
    if replica_dirs is None:
        dir_check = check_directory_structure(data_dir)
        replica_dirs = dir_check['found']

    if not replica_dirs:
        return {
            'replica_lambda_values': {},
            'unique_lambdas': [],
            'n_unique_lambdas': 0,
            'has_replica_lambda_all': False,
            'has_multistate_energy_all': False,
            'n_multistate_cols': 0,
            'is_rest2': False,
            'is_mbar_ready': False,
            'status': 'error',
            'issues': [{'type': 'no_replicas', 'message': '未找到副本目录'}]
        }

    replica_lambda_values = {}
    has_replica_lambda_all = True
    has_multistate_energy_all = True
    n_states_list = []
    issues = []

    for rep_dir in replica_dirs:
        edr_path = data_path / rep_dir / 'prod.edr'
        if edr_path.exists():
            edr_info = validate_edr_file(edr_path)

            # 检查Lambda标签
            if edr_info.get('has_replica_lambda'):
                replica_lambda_values[rep_dir] = edr_info.get('replica_lambda_value')
            else:
                has_replica_lambda_all = False

            # 检查多状态能量
            if edr_info.get('has_multistate_energy'):
                n_states_list.append(edr_info.get('n_multistate_cols', 0))
            else:
                has_multistate_energy_all = False
        else:
            issues.append({
                'type': 'missing_edr',
                'replica': rep_dir,
                'message': f'{rep_dir}/prod.edr 不存在'
            })

    # 分析Lambda值
    unique_lambdas = sorted(set(replica_lambda_values.values())) if replica_lambda_values else []
    n_unique_lambdas = len(unique_lambdas)

    # 检查Lambda值是否全部相同
    if has_replica_lambda_all and n_unique_lambdas == 1:
        issues.append({
            'type': 'lambda',
            'severity': 'warning',
            'message': f'所有副本的Lambda值都相同: {unique_lambdas[0]:.3f}',
            'suggestion': 'REST2设置可能不正确'
        })

    # 检查多状态能量列数是否一致
    if has_multistate_energy_all and len(set(n_states_list)) > 1:
        issues.append({
            'type': 'multistate_energy',
            'severity': 'warning',
            'message': '不同副本的多状态能量列数量不一致',
            'details': {rep: n for rep, n in zip(replica_dirs, n_states_list)}
        })

    # 确定多状态能量列数（取最常见值或第一个）
    n_multistate_cols = n_states_list[0] if n_states_list else 0

    # 判断是否为REST2模拟
    is_rest2 = has_replica_lambda_all and n_unique_lambdas > 1

    # 判断是否可以进行MBAR分析
    is_mbar_ready = has_multistate_energy_all and is_rest2

    # 确定整体状态
    if not has_multistate_energy_all:
        status = 'error'
        issues.append({
            'type': 'multistate_energy',
            'severity': 'error',
            'message': '缺少MBAR所需的多状态能量列',
            'solution': '使用 gmx mdrun -rerun 重新计算'
        })
    elif not is_rest2:
        status = 'warning'
        issues.append({
            'type': 'rest2',
            'severity': 'warning',
            'message': '可能不是标准的REST2模拟'
        })
    else:
        status = 'ok'

    return {
        'replica_lambda_values': replica_lambda_values,
        'unique_lambdas': unique_lambdas,
        'n_unique_lambdas': n_unique_lambdas,
        'has_replica_lambda_all': has_replica_lambda_all,
        'has_multistate_energy_all': has_multistate_energy_all,
        'n_multistate_cols': n_multistate_cols,
        'is_rest2': is_rest2,
        'is_mbar_ready': is_mbar_ready,
        'status': status,
        'issues': issues
    }


def run_full_validation(data_dir: Union[str, Path] = 'data',
                        expected_replicas: Optional[int] = None) -> Dict:
    """
    运行完整的数据验证流程

    Parameters
    ----------
    data_dir : str or Path
        数据目录路径
    expected_replicas : int, optional
        期望的副本数量

    Returns
    -------
    report : dict
        完整的验证报告，包含所有检查结果和问题列表
    """
    data_path = Path(data_dir)

    # 1. 检查目录结构
    dir_check = check_directory_structure(data_dir, expected_replicas)

    if dir_check['status'] == 'error':
        return {
            'summary': {
                'overall_status': 'error',
                'n_replicas': 0,
                'n_issues': 1,
                'is_rest2': False,
                'is_mbar_ready': False
            },
            'directory_check': dir_check,
            'issues': [{
                'type': 'directory',
                'severity': 'error',
                'message': dir_check.get('message', '未找到副本目录')
            }]
        }

    # 2. 检查文件完整性
    file_checks = {}
    for rep_dir in dir_check['found']:
        file_checks[rep_dir] = check_file_integrity(rep_dir, data_dir)

    # 3. 验证文件格式
    format_validations = {}
    for rep_dir in dir_check['found']:
        rep_path = data_path / rep_dir
        validations = {}

        # 验证EDR
        validations['edr'] = validate_edr_file(rep_path / 'prod.edr')
        # 验证XTC
        validations['xtc'] = validate_xtc_file(rep_path / 'prod.xtc', rep_path / 'prod.gro')
        # 验证LOG
        validations['log'] = validate_log_file(rep_path / 'prod.log')

        format_validations[rep_dir] = validations

    # 4. Lambda参数分析
    lambda_analysis = analyze_lambda_parameters(data_dir, dir_check['found'])

    # 5. 收集所有问题
    issues = []

    # 目录问题
    if dir_check['missing']:
        issues.append({
            'type': 'directory',
            'severity': 'error',
            'message': f"缺失副本目录: {', '.join(dir_check['missing'])}"
        })

    # 文件完整性问题
    for rep, check in file_checks.items():
        if check['status'] != 'ok':
            problem_files = [f for f, info in check['files'].items() if info['status'] != 'ok']
            issues.append({
                'type': 'file_integrity',
                'replica': rep,
                'severity': check['status'],
                'message': f"文件问题: {', '.join(problem_files)}"
            })

    # 格式验证问题
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

    # Lambda分析问题
    issues.extend(lambda_analysis['issues'])

    # 6. 确定整体状态
    has_errors = any(issue['severity'] == 'error' for issue in issues)
    has_warnings = any(issue.get('severity') == 'warning' for issue in issues)

    if has_errors:
        overall_status = 'error'
    elif has_warnings:
        overall_status = 'warning'
    else:
        overall_status = 'ok'

    # 7. 构建完整报告
    report = {
        'summary': {
            'overall_status': overall_status,
            'n_replicas': dir_check['actual'],
            'n_issues': len(issues),
            'is_rest2': lambda_analysis['is_rest2'],
            'is_mbar_ready': lambda_analysis['is_mbar_ready']
        },
        'directory_check': dir_check,
        'file_checks': file_checks,
        'format_validations': format_validations,
        'lambda_analysis': lambda_analysis,
        'issues': issues
    }

    return report


def format_file_size(size_bytes: int) -> str:
    """格式化文件大小"""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.1f} TB"
