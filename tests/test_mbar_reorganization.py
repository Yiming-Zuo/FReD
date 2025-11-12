#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
测试u_kn矩阵重组功能

验证reorganize_u_kn_by_state函数的正确性
"""

import sys
from pathlib import Path
import numpy as np
import pytest

# 添加scripts目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent / 'scripts'))

from utils.preprocessing import reorganize_u_kn_by_state


class TestReorganizeUknByState:
    """测试u_kn重组功能"""

    def test_simple_case(self):
        """
        测试简单案例：2个副本，3个状态，4个周期

        场景：
        - 2个副本（rep0, rep1）
        - 3个热力学状态（state0, state1, state2）
        - 4个周期（cycle 0-3）
        - 总共8个样本（2副本 × 4周期）
        """
        n_replicas = 2
        n_states = 3
        n_cycles = 4
        n_samples_total = n_replicas * n_cycles  # 8

        # 1. 构建按副本组织的u_kn矩阵
        # 列顺序：[rep0_cyc0, rep0_cyc1, rep0_cyc2, rep0_cyc3,
        #          rep1_cyc0, rep1_cyc1, rep1_cyc2, rep1_cyc3]
        u_kn_by_replica = np.arange(n_states * n_samples_total).reshape(n_states, n_samples_total).astype(float)
        # shape: (3, 8)
        # [[0,  1,  2,  3,  4,  5,  6,  7],
        #  [8,  9, 10, 11, 12, 13, 14, 15],
        #  [16, 17, 18, 19, 20, 21, 22, 23]]

        # 2. 构建副本到状态的映射
        replica_to_state = np.array([
            [0, 2],  # cycle 0: rep0在state0, rep1在state2
            [1, 2],  # cycle 1: rep0在state1, rep1在state2
            [1, 0],  # cycle 2: rep0在state1, rep1在state0
            [2, 0]   # cycle 3: rep0在state2, rep1在state0
        ])

        # 3. 构建索引数组
        cycle_indices = np.array([0, 1, 2, 3, 0, 1, 2, 3])
        replica_indices = np.array([0, 0, 0, 0, 1, 1, 1, 1])

        # 4. 调用重组函数
        result = reorganize_u_kn_by_state(
            u_kn_by_replica,
            replica_to_state,
            cycle_indices,
            replica_indices
        )

        # 5. 验证N_k
        # 根据replica_to_state，统计每个状态的样本数：
        # state0: (rep0,cyc0), (rep1,cyc2), (rep1,cyc3) = 3个
        # state1: (rep0,cyc1), (rep0,cyc2) = 2个
        # state2: (rep1,cyc0), (rep1,cyc1), (rep0,cyc3) = 3个
        expected_N_k = np.array([3, 2, 3])
        np.testing.assert_array_equal(result['N_k'], expected_N_k)

        # 6. 验证总样本数
        assert result['N_k'].sum() == n_samples_total

        # 7. 验证u_kn shape
        assert result['u_kn'].shape == (n_states, n_samples_total)

        # 8. 验证state_sample_indices
        # state0应该包含：(rep0,cyc0), (rep1,cyc2), (rep1,cyc3)
        # 在原始索引中是：0, 6, 7
        state0_indices = result['state_sample_indices'][0]
        assert len(state0_indices) == 3
        expected_state0_original_indices = {0, 6, 7}
        assert set(state0_indices) == expected_state0_original_indices

        # state1应该包含：(rep0,cyc1), (rep0,cyc2)
        # 在原始索引中是：1, 2
        state1_indices = result['state_sample_indices'][1]
        assert len(state1_indices) == 2
        expected_state1_original_indices = {1, 2}
        assert set(state1_indices) == expected_state1_original_indices

        # state2应该包含：(rep1,cyc0), (rep1,cyc1), (rep0,cyc3)
        # 在原始索引中是：4, 5, 3
        state2_indices = result['state_sample_indices'][2]
        assert len(state2_indices) == 3
        expected_state2_original_indices = {3, 4, 5}
        assert set(state2_indices) == expected_state2_original_indices

    def test_equal_distribution(self):
        """
        测试均匀分布的情况

        所有状态的样本数应该相等（理想的REST2交换）
        """
        n_replicas = 5
        n_states = 5
        n_cycles = 100

        # 构建理想的交换：每个副本在每个状态停留相同时间
        replica_to_state = np.zeros((n_cycles, n_replicas), dtype=int)
        for cycle in range(n_cycles):
            # 每20个周期交换一次
            shift = (cycle // 20) % n_states
            for rep in range(n_replicas):
                replica_to_state[cycle, rep] = (rep + shift) % n_states

        # 构建u_kn和索引
        n_samples_total = n_replicas * n_cycles
        u_kn_by_replica = np.random.randn(n_states, n_samples_total)

        cycle_indices = np.repeat(np.arange(n_cycles), n_replicas)
        replica_indices = np.tile(np.arange(n_replicas), n_cycles)

        # 重组
        result = reorganize_u_kn_by_state(
            u_kn_by_replica,
            replica_to_state,
            cycle_indices,
            replica_indices
        )

        # 验证每个状态的样本数应该相等
        expected_samples_per_state = n_samples_total // n_states
        np.testing.assert_array_equal(result['N_k'], np.full(n_states, expected_samples_per_state))

    def test_unequal_distribution(self):
        """
        测试不均匀分布的情况

        某些状态可能有更多样本（非理想交换）
        """
        n_replicas = 3
        n_states = 3
        n_cycles = 10

        # 构建非理想交换：state0被访问更多
        replica_to_state = np.array([
            [0, 0, 1],
            [0, 0, 1],
            [0, 0, 1],
            [0, 1, 2],
            [0, 1, 2],
            [1, 1, 2],
            [1, 2, 2],
            [1, 2, 2],
            [2, 2, 2],
            [2, 2, 2]
        ])

        n_samples_total = n_replicas * n_cycles
        u_kn_by_replica = np.random.randn(n_states, n_samples_total)

        cycle_indices = np.repeat(np.arange(n_cycles), n_replicas)
        replica_indices = np.tile(np.arange(n_replicas), n_cycles)

        # 重组
        result = reorganize_u_kn_by_state(
            u_kn_by_replica,
            replica_to_state,
            cycle_indices,
            replica_indices
        )

        # 手动统计每个状态的出现次数
        expected_N_k = np.bincount(replica_to_state.flatten(), minlength=n_states)

        # 验证
        np.testing.assert_array_equal(result['N_k'], expected_N_k)
        assert result['N_k'].sum() == n_samples_total

    def test_energy_values_preserved(self):
        """
        测试能量值是否正确保留

        验证重组后的u_kn矩阵中的能量值与原始值对应
        """
        n_replicas = 2
        n_states = 2
        n_cycles = 3
        n_samples_total = n_replicas * n_cycles

        # 使用容易辨识的能量值
        u_kn_by_replica = np.array([
            [10, 11, 12, 20, 21, 22],  # state0的能量
            [30, 31, 32, 40, 41, 42]   # state1的能量
        ], dtype=float)

        replica_to_state = np.array([
            [0, 1],  # cycle 0: rep0→state0, rep1→state1
            [1, 0],  # cycle 1: rep0→state1, rep1→state0
            [0, 1]   # cycle 2: rep0→state0, rep1→state1
        ])

        cycle_indices = np.array([0, 1, 2, 0, 1, 2])
        replica_indices = np.array([0, 0, 0, 1, 1, 1])

        result = reorganize_u_kn_by_state(
            u_kn_by_replica,
            replica_to_state,
            cycle_indices,
            replica_indices
        )

        # state0应该包含：(rep0,cyc0), (rep0,cyc2), (rep1,cyc1)
        # 原始索引：0, 2, 4
        # state1应该包含：(rep0,cyc1), (rep1,cyc0), (rep1,cyc2)
        # 原始索引：1, 3, 5

        N_k = result['N_k']
        u_kn_reorg = result['u_kn']

        # 验证N_k
        assert N_k[0] == 3
        assert N_k[1] == 3

        # 验证state0的样本
        state0_samples = u_kn_reorg[:, :N_k[0]]  # 前3列
        state0_original_indices = result['state_sample_indices'][0]

        for i, orig_idx in enumerate(state0_original_indices):
            # 验证能量值被正确复制
            np.testing.assert_array_equal(
                state0_samples[:, i],
                u_kn_by_replica[:, orig_idx]
            )


def test_consistency_with_verify_data_consistency():
    """
    集成测试：验证重组后的数据通过verify_data_consistency检查
    """
    from utils.preprocessing import verify_data_consistency

    n_replicas = 4
    n_states = 4
    n_cycles = 50
    n_samples_total = n_replicas * n_cycles

    # 生成随机replica_to_state
    replica_to_state = np.random.randint(0, n_states, size=(n_cycles, n_replicas))

    # 生成随机能量
    u_kn_by_replica = np.random.randn(n_states, n_samples_total) * 1000 + 5000

    cycle_indices = np.repeat(np.arange(n_cycles), n_replicas)
    replica_indices = np.tile(np.arange(n_replicas), n_cycles)

    # 重组
    result = reorganize_u_kn_by_state(
        u_kn_by_replica,
        replica_to_state,
        cycle_indices,
        replica_indices
    )

    # 验证一致性
    consistency = verify_data_consistency(
        result['u_kn'],
        replica_to_state,
        result['N_k']
    )

    assert consistency['is_consistent'], f"一致性检查失败: {consistency['issues']}"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
