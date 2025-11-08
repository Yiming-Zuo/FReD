#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
读取和分析 GROMACS .edr 能量文件的示例脚本

使用方法:
    conda activate femto_test
    python read_edr_example.py
"""

import panedr
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

def read_edr_file(edr_path):
    """
    读取 .edr 文件并返回 DataFrame

    参数:
        edr_path: .edr 文件的路径

    返回:
        pandas.DataFrame: 包含所有能量项的数据框
    """
    print(f"正在读取 {edr_path}...")
    df = panedr.edr_to_df(edr_path)
    print(f"✓ 成功读取 {len(df)} 帧数据")
    return df

def show_basic_info(df):
    """显示能量文件的基本信息"""
    print("\n" + "="*60)
    print("基本信息")
    print("="*60)
    print(f"总帧数: {len(df)}")
    print(f"时间范围: {df['Time'].min():.2f} - {df['Time'].max():.2f} ps")
    print(f"时间步长: {(df['Time'].iloc[1] - df['Time'].iloc[0]):.2f} ps")
    print(f"可用能量项数量: {len(df.columns)}")

def show_available_terms(df):
    """显示所有可用的能量项"""
    print("\n" + "="*60)
    print("可用的能量项")
    print("="*60)
    for i, col in enumerate(df.columns, 1):
        print(f"{i:3d}. {col}")

def show_statistics(df, terms=['Potential', 'Kinetic En.', 'Total Energy', 'Temperature', 'Pressure']):
    """显示关键能量项的统计信息"""
    print("\n" + "="*60)
    print("关键能量项统计")
    print("="*60)

    stats = df[terms].describe()
    print(stats.to_string())

def plot_energy_evolution(df, output_dir='.'):
    """绘制能量演化图"""
    fig, axes = plt.subplots(3, 2, figsize=(14, 12))
    fig.suptitle('能量演化分析', fontsize=16, fontweight='bold')

    # 1. 势能
    ax = axes[0, 0]
    ax.plot(df['Time'], df['Potential'], 'b-', alpha=0.7, linewidth=0.5)
    ax.set_xlabel('时间 (ps)')
    ax.set_ylabel('势能 (kJ/mol)')
    ax.set_title('势能演化')
    ax.grid(True, alpha=0.3)

    # 2. 动能
    ax = axes[0, 1]
    ax.plot(df['Time'], df['Kinetic En.'], 'r-', alpha=0.7, linewidth=0.5)
    ax.set_xlabel('时间 (ps)')
    ax.set_ylabel('动能 (kJ/mol)')
    ax.set_title('动能演化')
    ax.grid(True, alpha=0.3)

    # 3. 总能量
    ax = axes[1, 0]
    ax.plot(df['Time'], df['Total Energy'], 'g-', alpha=0.7, linewidth=0.5)
    ax.set_xlabel('时间 (ps)')
    ax.set_ylabel('总能量 (kJ/mol)')
    ax.set_title('总能量演化')
    ax.grid(True, alpha=0.3)

    # 4. 温度
    ax = axes[1, 1]
    ax.plot(df['Time'], df['Temperature'], 'm-', alpha=0.7, linewidth=0.5)
    ax.axhline(y=df['Temperature'].mean(), color='k', linestyle='--',
               label=f'平均: {df["Temperature"].mean():.2f} K')
    ax.set_xlabel('时间 (ps)')
    ax.set_ylabel('温度 (K)')
    ax.set_title('温度演化')
    ax.legend()
    ax.grid(True, alpha=0.3)

    # 5. 压力
    ax = axes[2, 0]
    ax.plot(df['Time'], df['Pressure'], 'c-', alpha=0.7, linewidth=0.5)
    ax.axhline(y=df['Pressure'].mean(), color='k', linestyle='--',
               label=f'平均: {df["Pressure"].mean():.2f} bar')
    ax.set_xlabel('时间 (ps)')
    ax.set_ylabel('压力 (bar)')
    ax.set_title('压力演化')
    ax.legend()
    ax.grid(True, alpha=0.3)

    # 6. 能量守恒
    ax = axes[2, 1]
    ax.plot(df['Time'], df['Conserved En.'], 'orange', alpha=0.7, linewidth=0.5)
    ax.set_xlabel('时间 (ps)')
    ax.set_ylabel('守恒能量 (kJ/mol)')
    ax.set_title('能量守恒检查')
    ax.grid(True, alpha=0.3)

    plt.tight_layout()
    output_file = f'{output_dir}/energy_evolution.png'
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    print(f"\n✓ 能量演化图已保存到: {output_file}")
    plt.close()

def export_to_csv(df, output_path):
    """导出数据到 CSV 文件"""
    df.to_csv(output_path, index=False)
    print(f"✓ 数据已导出到: {output_path}")

def main():
    # 设置文件路径
    edr_file = '/Users/yiming/projects/rest2/data/rep_0/prod.edr'
    output_dir = '/Users/yiming/projects/rest2/test_alanine_dipeptide'

    # 读取 .edr 文件
    df = read_edr_file(edr_file)

    # 显示基本信息
    show_basic_info(df)

    # 显示可用的能量项
    show_available_terms(df)

    # 显示统计信息
    show_statistics(df)

    # 绘制能量演化图
    plot_energy_evolution(df, output_dir)

    # 导出到 CSV（可选）
    # export_to_csv(df, f'{output_dir}/energy_data.csv')

    # 示例：获取特定时间范围的数据
    print("\n" + "="*60)
    print("示例：获取特定数据")
    print("="*60)

    # 获取最后 10 ns 的平均温度
    last_10ns = df[df['Time'] >= (df['Time'].max() - 10000)]
    avg_temp = last_10ns['Temperature'].mean()
    print(f"最后 10 ns 的平均温度: {avg_temp:.2f} K")

    # 获取特定能量项的最大值和最小值
    pot_min = df['Potential'].min()
    pot_max = df['Potential'].max()
    print(f"势能范围: {pot_min:.2f} ~ {pot_max:.2f} kJ/mol")

    print("\n" + "="*60)
    print("完成！")
    print("="*60)

if __name__ == '__main__':
    main()
