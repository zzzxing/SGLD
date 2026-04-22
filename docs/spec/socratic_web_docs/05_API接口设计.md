# API 接口设计（第一版）

## 1. 说明

虽然本项目采用“单体 Web + 服务端模板”的路线，但仍建议把核心业务做成内部 API 化接口，方便：
- 页面调用
- 后续拆前后端
- WebSocket 外的异步请求
- 测试与维护

接口统一前缀建议：
- `/api/auth`
- `/api/student`
- `/api/teacher`
- `/api/admin`
- `/api/classroom`
- `/api/llm`

返回格式统一建议：

```json
{
  "code": 0,
  "message": "ok",
  "data": {}
}
```

## 2. 认证接口

### 2.1 登录
`POST /api/auth/login`

请求体：
```json
{
  "username": "student001",
  "password": "123456"
}
```

返回：
```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "token": "jwt_or_session",
    "role": "student",
    "redirect_url": "/student/home"
  }
}
```

### 2.2 退出
`POST /api/auth/logout`

### 2.3 修改密码
`POST /api/auth/change-password`

## 3. 管理员接口

### 3.1 创建教师
`POST /api/admin/teachers`

### 3.2 创建班级
`POST /api/admin/classes`

### 3.3 批量导入学生
`POST /api/admin/classes/{class_id}/students/import`

### 3.4 获取模型配置列表
`GET /api/admin/model-providers`

### 3.5 新增模型配置
`POST /api/admin/model-providers`

示例请求：
```json
{
  "provider_name": "deepseek",
  "base_url": "https://example.com",
  "api_key": "xxx",
  "default_chat_model": "xxx",
  "default_embed_model": "xxx",
  "enabled": true,
  "priority_no": 1
}
```

### 3.6 更新系统配置
`PUT /api/admin/system-configs/{key}`

## 4. 教师接口

### 4.1 上传教材
`POST /api/teacher/resources/upload`

表单字段：
- file
- course_id
- parse_mode

返回：
```json
{
  "code": 0,
  "message": "uploaded",
  "data": {
    "resource_id": 101,
    "parse_status": "pending"
  }
}
```

### 4.2 获取解析结果
`GET /api/teacher/resources/{resource_id}/parse-result`

### 4.3 保存自动生成的章节树
`POST /api/teacher/courses/{course_id}/chapters/import`

### 4.4 获取课程章节树
`GET /api/teacher/courses/{course_id}/chapters`

### 4.5 更新章节
`PUT /api/teacher/chapters/{chapter_id}`

### 4.6 获取知识点列表
`GET /api/teacher/chapters/{chapter_id}/knowledge-points`

### 4.7 生成知识讲解初稿
`POST /api/teacher/knowledge-points/{kp_id}/generate-explanation`

### 4.8 保存知识讲解
`PUT /api/teacher/knowledge-points/{kp_id}`

### 4.9 生成问题链初稿
`POST /api/teacher/knowledge-points/{kp_id}/generate-question-chain`

### 4.10 获取问题链
`GET /api/teacher/question-chains/{chain_id}`

### 4.11 更新问题链
`PUT /api/teacher/question-chains/{chain_id}`

### 4.12 创建任务
`POST /api/teacher/chapters/{chapter_id}/tasks`

### 4.13 发布任务
`POST /api/teacher/tasks/{task_id}/publish`

### 4.14 开始课堂
`POST /api/teacher/classroom/start`

请求体：
```json
{
  "class_id": 1,
  "chapter_id": 12,
  "task_id": 3
}
```

### 4.15 暂停课堂
`POST /api/teacher/classroom/{session_id}/pause`

### 4.16 结束课堂
`POST /api/teacher/classroom/{session_id}/end`

### 4.17 获取课堂实时统计
`GET /api/teacher/classroom/{session_id}/dashboard`

返回建议包含：
- 在线人数
- 已开始人数
- 完成人数
- 平均进度
- 卡点分布
- 高频错误关键词

### 4.18 获取学生详情
`GET /api/teacher/students/{student_id}/detail?session_id=xx`

### 4.19 教师点评/打标/评分
`POST /api/teacher/feedbacks`

## 5. 学生接口

### 5.1 获取当前课堂信息
`GET /api/student/current-session`

### 5.2 获取当前章节内容
`GET /api/student/chapters/{chapter_id}/learn`

返回包含：
- 章节标题
- 当前知识点
- 讲解内容
- 当前问题链进度
- 当前任务

### 5.3 开始学习
`POST /api/student/study-records/start`

### 5.4 提交文字回答
`POST /api/student/dialogue/answer`

请求体：
```json
{
  "study_record_id": 1001,
  "step_no": 2,
  "answer_text": "我认为变量就是..."
}
```

返回：
```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "next_action": "next_question",
    "assistant_message": "...",
    "current_step_no": 3,
    "progress_percent": 45
  }
}
```

### 5.5 提交代码并运行
`POST /api/student/code/run`

请求体：
```json
{
  "study_record_id": 1001,
  "task_id": 3,
  "language": "python",
  "source_code": "print('hello')"
}
```

返回：
```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "run_status": "success",
    "stdout": "hello\n",
    "stderr": "",
    "runtime_ms": 33,
    "assistant_feedback": "..."
  }
}
```

### 5.6 提交任务
`POST /api/student/tasks/{task_id}/submit`

### 5.7 获取学习记录
`GET /api/student/study-records`

## 6. WebSocket 设计

## 6.1 学生端频道
`/ws/student/{user_id}`

用途：
- 接收教师一键推送课堂
- 接收课堂状态变化
- 接收系统实时提醒

消息示例：
```json
{
  "type": "class_started",
  "session_id": 10,
  "chapter_id": 12,
  "task_id": 3,
  "message": "请开始本节学习"
}
```

## 6.2 教师端频道
`/ws/teacher/{user_id}`

用途：
- 接收学生进度更新
- 接收在线状态更新
- 接收任务提交提醒

消息示例：
```json
{
  "type": "student_progress",
  "session_id": 10,
  "student_id": 23,
  "progress_percent": 60,
  "current_step_no": 4,
  "status": "in_progress"
}
```

## 7. 文件上传接口

### 7.1 通用文件上传
`POST /api/files/upload`

限制建议：
- pdf/docx/pptx/txt/md/png/jpg/jpeg
- 默认单文件 20MB 内
- 白名单校验
- 自动重命名

## 8. 后台任务接口（可选）

### 8.1 查询解析任务状态
`GET /api/teacher/jobs/{job_id}`

### 8.2 重建向量索引
`POST /api/admin/vector/rebuild`

## 9. 错误码建议

| code | 含义 |
|---|---|
| 0 | 成功 |
| 4001 | 参数错误 |
| 4002 | 未登录 |
| 4003 | 权限不足 |
| 4004 | 资源不存在 |
| 4005 | 文件类型不支持 |
| 5001 | 模型调用失败 |
| 5002 | 向量检索失败 |
| 5003 | 代码运行失败 |
| 5004 | 系统内部异常 |

## 10. 接口开发顺序建议

### 第一批
- 登录
- 获取当前课堂
- 获取章节内容
- 提交文字回答
- 提交代码运行
- 开始课堂
- 获取课堂统计

### 第二批
- 教材上传解析
- 章节编辑
- 问题链编辑
- 任务提交
- 教师点评

### 第三批
- 模型配置
- 系统配置
- 日志与资源管理
