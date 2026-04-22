# 追问智学（SGLD）

面向**初中信息技术课堂**的苏格拉底教学法智能辅学 Web 系统（发布前打磨版 V3）。

## V3 重点收口

- 初始化与运行闭环：新增 `scripts/bootstrap.py`，自动尝试建环境、安装依赖、初始化数据库、写入种子数据。
- 权限与路由安全：API 与 Web 路由统一增加角色校验辅助函数。
- 课堂生命周期：支持开始/暂停/结束，学生端对未开始/进行中/暂停/结束状态有对应页面反馈。
- 发布前可演示性：教师端补课堂结束小结；管理员端/学生端/教师端补空状态与提示语。

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

## 演示路线（按角色）

### 1) 管理员
1. 登录 `admin/123456`。
2. 在系统设置页配置上传大小、允许类型、安全级别、默认温度/max_tokens/超时。
3. 在模型配置区新增或编辑 provider，切换默认模型。

### 2) 教师
1. 登录 `teacher1/123456`。
2. 上传教材并触发解析，观察文件类型/解析状态/提取长度/章节数/最近处理时间。
3. 审核章节、知识点、问题链并发布章节。
4. 开始课堂 -> 暂停课堂 -> 结束课堂，观察看板和分析区变化。
5. 打开学生详情，查看最近回答/AI回复/进度/代码结果并填写评语标签。

### 3) 学生
1. 登录 `student1/123456`。
2. 未开始时显示等待；进行中时可学习；暂停时显示等待；结束时显示本节小结。
3. 在章节页按问题链作答，查看 RAG 命中调试信息。
4. 运行代码练习并查看结果与AI分析。

## 默认账号
- 管理员：`admin / 123456`
- 教师：`teacher1 / 123456`
- 学生：`student1 / 123456`

## 最小回归检查

```bash
python -m py_compile app/main.py app/routers/api.py app/routers/web.py app/services/classroom_service.py app/services/content_service.py app/services/llm_router_service.py
python -m pytest -q tests/test_prompt_service.py tests/test_code_runner_service.py tests/test_permissions_smoke.py
```

## 已知限制
- 当前环境若缺少网络/依赖，`bootstrap.py` 会给出明确提示并退出安装流程。
- `openai_compatible` 仍是配置结构可用，默认演示不发外网请求。
