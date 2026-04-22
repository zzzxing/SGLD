# 追问智学（SGLD）

面向**初中信息技术课堂**的苏格拉底教学法智能辅学 Web 系统。

## 先看这里：Windows 从零启动（推荐）

> 目标：在全新 Windows 环境中稳定启动，避免 `.venv` 损坏、`pip` 缺失、数据库初始化失败。

1. 打开项目根目录终端（PowerShell / CMD）。
2. **如果之前启动失败，先清理旧虚拟环境**：
   ```bat
   rmdir /s /q .venv
   ```
3. 运行一键脚本：
   ```bat
   start_server.bat
   ```
4. 首次启动会自动执行：
   - `python -m venv .venv`
   - `.venv\Scripts\python.exe -m ensurepip --upgrade`
   - `.venv\Scripts\python.exe -m pip install --upgrade pip`
   - `.venv\Scripts\python.exe -m pip install -r requirements.txt`
   - `.venv\Scripts\python.exe scripts/init_db.py`
   - `.venv\Scripts\python.exe scripts/seed_demo_data.py`
5. 浏览器打开：`http://127.0.0.1:8000`

## 手动启动（排障模式）

### Windows
```bat
python -m venv .venv
.venv\Scripts\python.exe -m ensurepip --upgrade
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe scripts/init_db.py
.venv\Scripts\python.exe scripts/seed_demo_data.py
.venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### Linux/macOS
```bash
python3 -m venv .venv
.venv/bin/python -m ensurepip --upgrade
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python scripts/init_db.py
.venv/bin/python scripts/seed_demo_data.py
.venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## pip 缺失怎么办（`No module named pip`）

这通常是因为**复制了别处的 `.venv`** 或 `.venv` 已损坏。处理顺序：

1. 删除旧 `.venv`。
2. 重新 `python -m venv .venv`。
3. 强制 `ensurepip --upgrade`。
4. 再执行 `pip install -r requirements.txt`。

如果仍失败，请确认 Python 安装包含 `ensurepip`，建议重装 Python 3.11。

## 数据库初始化说明

项目会自动把 SQLite 路径解析为项目内绝对路径，并在创建 engine 前自动创建数据库父目录。
初始化脚本会打印：
- configured DATABASE_URL
- resolved DATABASE_URL
- sqlite file path

如需重置数据库：
```bash
python scripts/init_db.py
python scripts/seed_demo_data.py
```

## 演示账号

- 管理员：`admin / 123456`
- 教师：`teacher1 / 123456`
- 学生：`student1 / 123456`

> 密码使用 bcrypt 哈希保存，登录时做哈希校验。

## 常见问题

1. `No module named itsdangerous`：
   - 说明依赖不完整，重新执行 `pip install -r requirements.txt`（本仓库已将 `itsdangerous` 加入依赖）。
2. `sqlite3.OperationalError: unable to open database file`：
   - 检查 `scripts/init_db.py` 打印的 sqlite 路径是否可写。
   - 确认项目目录有写权限。

## 最小检查命令

```bash
python -m py_compile app/main.py app/core/config.py app/core/db.py scripts/bootstrap.py scripts/init_db.py scripts/seed_demo_data.py
```
