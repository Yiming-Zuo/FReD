# tests/

此目录包含单元测试。

## 测试文件

- `test_edr_parser.py`: EDR 解析器测试
- `test_log_parser.py`: LOG 解析器测试
- `test_mbar.py`: MBAR 工具测试

## 运行测试

```bash
conda activate femto_test

# 运行所有测试
python -m pytest tests/

# 运行特定测试
python -m pytest tests/test_edr_parser.py

# 带覆盖率报告
python -m pytest --cov=scripts/utils tests/
```

## TODO

- [ ] 实现所有测试用例
- [ ] 添加测试数据
- [ ] 设置 CI/CD 自动测试
