#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
从 GROMACS LOG 文件解析副本交换信息

功能：
1. 解析 prod.log 中的副本交换记录
2. 提取交换尝试和接受信息
3. 重建 replica_to_state_idx[cycle, replica] 映射
4. 计算交换接受率统计

LOG 文件示例格式：
    Replica exchange at step 1000 time 2.00000
    Repl 0 <-> 1  dE_term = -0.000e+00 (kT)
      dpV =  0.000e+00  d =  0.000e+00
    dplumed =  3.328e-02  dE_Term =  3.328e-02 (kT)
    Repl ex  0 x  1    2 x  3    4
    Repl pr   .97       1.0

使用方法：
    conda activate femto_test
    python scripts/02_parse_exchanges.py
"""

import re
import numpy as np
import pandas as pd
from pathlib import Path

# TODO: 导入工具模块
# from utils.log_parser import parse_exchange_record

def main():
    """主函数"""
    print("="*60)
    print("FReD 副本交换解析工具")
    print("="*60)

    # TODO: 实现以下功能
    # 1. 读取所有 replica 的 LOG 文件
    # 2. 使用正则表达式提取交换信息
    # 3. 重建副本-状态映射矩阵
    # 4. 计算统计信息
    # 5. 保存到 outputs/exchange_record.csv

    print("\nTODO: 实现交换记录解析")
    print("预期输出：")
    print("  - replica_to_state_idx.shape = (n_cycles, n_replicas)")
    print("  - n_proposed_swaps, n_accepted_swaps")
    print("  - 保存路径: FReD/outputs/exchange_record.csv")

    # 示例：读取 rep_0 的 LOG 文件片段
    log_path = Path("FReD/data/rep_0/prod.log")
    if log_path.exists():
        print(f"\n检查 {log_path}...")
        with open(log_path, 'r') as f:
            # 查找副本交换相关的行
            exchange_lines = []
            for line in f:
                if 'Replica exchange' in line or 'Repl ex' in line or 'Repl pr' in line:
                    exchange_lines.append(line.strip())
                    if len(exchange_lines) >= 20:  # 只读前20行作为示例
                        break

        if exchange_lines:
            print(f"找到 {len(exchange_lines)} 行交换信息:")
            for line in exchange_lines[:10]:
                print(f"  {line}")
        else:
            print("未找到副本交换信息")

if __name__ == '__main__':
    main()
