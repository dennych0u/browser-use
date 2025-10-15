# 实时浏览器操作 Demo

这是一个基于 browser-use 的实时浏览器操作演示项目，包含前后端完整实现。

## 项目结构

```
live_browser/
├── backend/                 # Flask 后端
│   ├── app.py              # 主应用文件
│   ├── requirements.txt    # Python 依赖
│   └── recordings/         # 录制文件存储目录
├── frontend/               # Vue 前端
│   ├── src/
│   │   ├── App.vue        # 主应用组件
│   │   └── main.js        # 应用入口
│   ├── index.html         # HTML 模板
│   ├── package.json       # 前端依赖
│   └── vite.config.js     # Vite 配置
└── README.md              # 项目说明
```

## 功能特性

### 后端功能
- ✅ Flask + WebSocket 实时通信
- ✅ 集成 browser-use 屏幕录制功能
- ✅ 无头浏览器模式
- ✅ 实时任务状态监控
- ✅ 录制文件管理
- ✅ RESTful API 接口

### 前端功能
- ✅ Vue 3 + Element Plus UI 框架
- ✅ 参照 Stapply 界面设计
- ✅ 实时 WebSocket 连接
- ✅ 浏览器会话控制
- ✅ 实时日志显示
- ✅ 任务进度监控
- ✅ 响应式设计

## 安装和运行

### 环境要求
- Python 3.12+
- Node.js 16+
- Chrome/Chromium 浏览器

### 后端设置

1. 进入后端目录：
```bash
cd live_browser/backend
```

2. 创建虚拟环境：
```bash
python -m venv venv
venv\Scripts\activate  # Windows
```

3. 安装依赖：
```bash
pip install -r requirements.txt
```

4. 配置环境变量（创建 .env 文件）：
```
GOOGLE_API_KEY=your_google_api_key_here
```

5. 启动后端服务：
```bash
python app.py
```

后端服务将在 http://localhost:5000 启动

### 前端设置

1. 进入前端目录：
```bash
cd live_browser/frontend
```

2. 安装依赖：
```bash
npm install
```

3. 启动开发服务器：
```bash
npm run dev
```

前端应用将在 http://localhost:3000 启动

## 使用说明

### 基本操作

1. **启动服务**：
   - 先启动后端服务（端口 5000）
   - 再启动前端服务（端口 3000）
   - 在浏览器中访问 http://localhost:3000

2. **创建新任务**：
   - 点击 "New Job Search" 按钮
   - 输入目标网站 URL
   - 可选择添加自定义任务描述
   - 点击 "创建任务"

3. **开始浏览器会话**：
   - 点击 "Open" 按钮启动浏览器会话
   - 系统将使用无头模式启动 Chrome
   - 实时日志会显示 agent 的执行步骤

4. **监控执行过程**：
   - 查看实时活动日志
   - 监控任务进度条
   - 观察连接状态指示器

5. **停止会话**：
   - 点击 "Stop Task" 按钮
   - 或等待任务自动完成

### API 接口

#### 健康检查
```
GET /api/health
```

#### 启动浏览器会话
```
POST /api/start_session
Content-Type: application/json

{
  "website_url": "https://example.com",
  "task": "自定义任务描述（可选）"
}
```

#### 停止浏览器会话
```
POST /api/stop_session
```

#### 获取会话状态
```
GET /api/session_status
```

#### 获取录制文件列表
```
GET /api/recordings
```

### WebSocket 事件

#### 客户端发送
- `connect`: 连接到服务器
- `ping`: 心跳检测

#### 服务器发送
- `connected`: 连接确认
- `session_started`: 会话开始
- `agent_step`: Agent 执行步骤
- `session_completed`: 会话完成
- `session_stopped`: 会话停止
- `error`: 错误信息
- `pong`: 心跳响应

## 技术架构

### 后端技术栈
- **Flask**: Web 框架
- **Flask-SocketIO**: WebSocket 支持
- **browser-use**: 浏览器自动化
- **Google Gemini**: LLM 模型
- **asyncio**: 异步编程

### 前端技术栈
- **Vue 3**: 前端框架
- **Element Plus**: UI 组件库
- **Socket.IO Client**: WebSocket 客户端
- **Axios**: HTTP 客户端
- **Vite**: 构建工具

### 核心特性

1. **实时通信**：
   - WebSocket 双向通信
   - 实时状态同步
   - 心跳检测机制

2. **屏幕录制**：
   - 使用 browser-use 内置录制功能
   - 自动保存 MP4 格式视频
   - 录制文件管理

3. **无头浏览器**：
   - Chrome 无头模式
   - 减少资源占用
   - 适合服务器部署

4. **任务监控**：
   - 实时日志显示
   - 进度条指示
   - 错误处理

## 故障排除

### 常见问题

1. **GOOGLE_API_KEY 未设置**：
   - 在后端目录创建 .env 文件
   - 添加有效的 Google API Key

2. **Chrome 浏览器未找到**：
   - 确保系统已安装 Chrome 或 Chromium
   - 检查 PATH 环境变量

3. **端口冲突**：
   - 后端默认端口 5000
   - 前端默认端口 3000
   - 可在配置文件中修改

4. **WebSocket 连接失败**：
   - 检查后端服务是否正常运行
   - 确认防火墙设置
   - 检查 CORS 配置

### 调试模式

启动后端时使用调试模式：
```bash
python app.py
```

查看详细日志输出，便于问题定位。

## 扩展功能

### 可扩展的功能点

1. **多浏览器支持**：
   - Firefox、Safari 等
   - 移动端浏览器模拟

2. **录制增强**：
   - 截图功能
   - 录制质量设置
   - 录制文件压缩

3. **任务管理**：
   - 任务队列
   - 定时任务
   - 任务模板

4. **用户系统**：
   - 用户认证
   - 权限管理
   - 多租户支持

## 许可证

本项目基于 MIT 许可证开源。