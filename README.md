# 追问智学（SGLD）

面向**初中信息技术课堂**的苏格拉底教学法智能辅学 Web 系统（发布前打磨版 V3）。

## V3 重点收口

- 初始化与运行闭环：`scripts/bootstrap.py` 自动尝试建环境、安装依赖、初始化数据库、写入种子数据；任一步失败会直接停止。
- 稳定数据库路径：SQLite 使用项目内绝对路径，并在启动 engine 前自动创建父目录。
- 权限与路由安全：API 与 Web 路由统一增加角色校验辅助函数。
- 课堂生命周期：支持开始/暂停/结束，学生端对应未开始/进行中/暂停/结束状态。

## 从零启动（最短步骤）

### Windows
1. 安装 Python 3.11。
2. 双击 `start_server.bat`（内部会调用 `scripts/bootstrap.py`）。
3. 浏览器打开 `http://127.0.0.1:8000`。

### Linux/macOS
```bash
python3 scripts/bootstrap.py
./run_server.sh
```

## 数据库重置与重新导入种子数据

> 用于“登录失败/账号不存在/数据库损坏”场景。

```bash
# 1) 重新建表（会清空旧数据）
python scripts/init_db.py

# 2) 写入演示账号与示范课程
python scripts/seed_demo_data.py
```

执行时会打印：
- 配置的 `DATABASE_URL`
- 实际解析后的 `DATABASE_URL`
- SQLite 文件绝对路径

## 演示账号

- 管理员：`admin / 123456`
- 教师：`teacher1 / 123456`
- 学生：`student1 / 123456`

> 密码在数据库中以 bcrypt 哈希保存，登录使用 `verify_password` 校验，不是明文比对。

## 依赖安装失败时的 fallback

如果网络环境导致 `pip install -r requirements.txt` 失败，可设置镜像后重试：

```bash
export PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple
python3 scripts/bootstrap.py
```

Windows:
```bat
set PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple
python scripts\bootstrap.py
```

## 最小回归检查

```bash
python -m py_compile app/main.py app/core/config.py app/core/db.py scripts/init_db.py scripts/seed_demo_data.py scripts/bootstrap.py
python -m pytest -q tests/test_prompt_service.py tests/test_code_runner_service.py tests/test_permissions_smoke.py
```

## 已知限制

- 当前环境若缺少网络/依赖，`bootstrap.py` 会报错并停止，不会继续启动服务。
- `openai_compatible` 默认仅保留配置结构，演示环境可不发外网请求。
