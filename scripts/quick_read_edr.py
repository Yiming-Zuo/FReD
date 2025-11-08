#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
快速读取 .edr 文件的简化脚本

使用方法:
    conda activate femto_test
    python quick_read_edr.py <edr_file_path>
"""

import sys
import panedr
import pandas as pd

def quick_read(edr_path):
    """快速读取并显示 .edr 文件的关键信息"""

    # 读取文件
    print(f"读取: {edr_path}")
    df = panedr.edr_to_df(edr_path)

    # 基本信息
    print(f"\n{'='*60}")
    print("基本信息")
    print(f"{'='*60}")
    print(f"总帧数: {len(df)}")
    print(f"时间范围: {df['Time'].min():.0f} - {df['Time'].max():.0f} ps ({(df['Time'].max()-df['Time'].min())/1000:.1f} ns)")

    # 关键热力学量
    print(f"\n{'='*60}")
    print("关键热力学量（平均值 ± 标准差）")
    print(f"{'='*60}")
    print(f"温度:     {df['Temperature'].mean():8.2f} ± {df['Temperature'].std():6.2f} K")
    print(f"压力:     {df['Pressure'].mean():8.2f} ± {df['Pressure'].std():6.2f} bar")
    print(f"势能:     {df['Potential'].mean():8.2f} ± {df['Potential'].std():6.2f} kJ/mol")
    print(f"动能:     {df['Kinetic En.'].mean():8.2f} ± {df['Kinetic En.'].std():6.2f} kJ/mol")
    print(f"总能量:   {df['Total Energy'].mean():8.2f} ± {df['Total Energy'].std():6.2f} kJ/mol")
    print(f"体积:     {df['Volume'].mean():8.4f} ± {df['Volume'].std():6.4f} nm³")
    print(f"密度:     {df['Density'].mean():8.2f} ± {df['Density'].std():6.2f} kg/m³")

    # 能量组成
    if 'Angle' in df.columns:
        print(f"\n{'='*60}")
        print("能量组成（平均值）")
        print(f"{'='*60}")
        print(f"键角能:           {df['Angle'].mean():10.2f} kJ/mol")
        print(f"LJ短程相互作用:   {df['LJ (SR)'].mean():10.2f} kJ/mol")
        print(f"色散校正:         {df['Disper. corr.'].mean():10.2f} kJ/mol")
        print(f"库伦短程:         {df['Coulomb (SR)'].mean():10.2f} kJ/mol")
        print(f"库伦倒空间:       {df['Coul. recip.'].mean():10.2f} kJ/mol")

    # 温度组分（如果有）
    if 'T-UNL' in df.columns and 'T-SOL' in df.columns:
        print(f"\n{'='*60}")
        print("各组分温度")
        print(f"{'='*60}")
        print(f"UNL (溶质):  {df['T-UNL'].mean():8.2f} ± {df['T-UNL'].std():6.2f} K")
        print(f"SOL (溶剂):  {df['T-SOL'].mean():8.2f} ± {df['T-SOL'].std():6.2f} K")

    # Lambda值（REST2相关）
    if 'Lamb-UNL' in df.columns:
        print(f"\n{'='*60}")
        print("REST2 Lambda 值")
        print(f"{'='*60}")
        print(f"Lamb-UNL:  {df['Lamb-UNL'].mean():.4f}")
        print(f"Lamb-SOL:  {df['Lamb-SOL'].mean():.4f}")

    return df

if __name__ == '__main__':
    if len(sys.argv) < 2:
        edr_file = '/Users/yiming/projects/rest2/data/rep_0/prod.edr'
        print("未指定文件，使用默认路径")
    else:
        edr_file = sys.argv[1]

    df = quick_read(edr_file)

    print(f"\n{'='*60}")
    print("返回的 DataFrame 包含以下列:")
    print(f"{'='*60}")
    for i, col in enumerate(df.columns, 1):
        print(f"{i:3d}. {col}")

    print(f"\n{'='*60}")
    print("可以通过 df[列名] 访问特定数据")
    print("例如: df['Temperature'] 获取所有温度数据")
    print(f"{'='*60}")
