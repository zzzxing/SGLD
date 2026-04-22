# 追问智学（SGLD）

面向初中信息技术课堂的苏格拉底式智能辅学 Web 系统（FastAPI + Jinja2 + HTMX）。

## 环境要求

- Python 3.11（Windows / Linux / macOS）
- 建议使用干净虚拟环境

## 三步启动（主流程）

```bash
pip install -r requirements.txt
uvicorn app.main:app --reload
# 浏览器打开 http://127.0.0.1:8000
```

> 首次启动时，系统会自动：
> 1) 建表（`create_all`）
> 2) 检查数据库是否为空
> 3) 若为空，自动写入演示账号与最小示例课程数据

因此主流程**不需要**手动执行 `init_db.py` / `seed_demo_data.py`。

## 演示账号

- 管理员：`admin / 123456`
- 教师：`teacher1 / 123456`
- 学生：`student1 / 123456`

## 登录后演示建议

1. **管理员端**：查看系统设置与模型配置。
2. **教师端**：上传教材、触发解析、发布章节、开始课堂。
3. **学生端**：进入已发布章节，查看课堂状态并开始学习。

## 开发者工具（可选）

仅在需要重置数据时使用：

```bash
python scripts/init_db.py
python scripts/seed_demo_data.py
```

## 常见问题

### 1) 登录页能打开但账号登录失败
- 检查 `uvicorn` 启动日志，确认是否打印了：
  - `[app] database is empty, seeding demo data...`
  - `[app] demo data seeded`
- 若没有，可手动执行一次：
  - `python scripts/seed_demo_data.py`

### 2) `No module named itsdangerous`
- 说明依赖没有安装完整，请重新执行：
  - `pip install -r requirements.txt`

### 3) `sqlite3.OperationalError: unable to open database file`
- 检查项目目录是否可写。
- 检查启动日志中的 `sqlite file path` 指向位置是否存在权限问题。

## 设计原则（当前版本）

- 优先保证启动稳定、登录可用、课堂演示可跑通。
- 优先保证 Windows 局域网部署友好。
- 在不引入重型前端框架前提下，持续优化 UI 可用性。
