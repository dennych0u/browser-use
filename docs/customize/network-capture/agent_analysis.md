# Browser-Use Agent 参数与函数详细分析

本文档基于 [Browser-Use 官方文档](https://docs.browser-use.com/customize/browser/all-parameters)、examples 目录中的实例以及源码分析，详细介绍 Agent 类的可设置参数、主要函数及其适用场景。

## 目录

1. [Agent 核心参数](#agent-核心参数)
2. [Agent 主要方法](#agent-主要方法)
3. [浏览器相关参数](#浏览器相关参数)
4. [典型使用案例](#典型使用案例)
5. [最佳实践](#最佳实践)

## Agent 核心参数

### 必需参数

#### `task: str`
- **作用**: 定义 Agent 要执行的任务描述
- **适用场景**: 所有 Agent 实例都必须提供
- **典型代码**:
```python
agent = Agent(
    task="Go to Google and search for 'browser automation'",
    llm=llm
)
```

#### `llm: BaseChatModel`
- **作用**: 指定用于决策的大语言模型
- **适用场景**: 提供 Agent 的"大脑"，处理页面理解和动作决策
- **典型代码**:
```python
from browser_use import ChatOpenAI, ChatGoogle, ChatAnthropic

# OpenAI GPT 模型
llm = ChatOpenAI(model='gpt-4.1-mini')

# Google Gemini 模型
llm = ChatGoogle(model='gemini-2.5-flash')

# Anthropic Claude 模型
llm = ChatAnthropic(model='claude-3-sonnet-20240229')
```

### 浏览器配置参数

#### `browser_session: BrowserSession`
- **作用**: 指定浏览器会话实例
- **适用场景**: 需要自定义浏览器配置或复用浏览器会话
- **典型代码**:
```python
from browser_use import BrowserSession, BrowserProfile

# 基本配置
browser_session = BrowserSession(headless=False)

# 高级配置
profile = BrowserProfile(
    headless=False,
    user_data_dir='./browser_profile',
    keep_alive=True
)
browser_session = BrowserSession(browser_profile=profile)

agent = Agent(
    task="Navigate to example.com",
    llm=llm,
    browser_session=browser_session
)
```

#### `browser_profile: BrowserProfile`
- **作用**: 定义浏览器启动配置
- **适用场景**: 需要特定浏览器设置但不需要复用会话
- **典型代码**:
```python
from browser_use import BrowserProfile

profile = BrowserProfile(
    headless=True,
    user_data_dir='~/.browser-use/profiles/default',
    proxy=ProxySettings(server='http://proxy:8080'),
    allowed_domains=['*.example.com']
)

agent = Agent(
    task="Visit example.com",
    llm=llm,
    browser_profile=profile
)
```

### 工具和扩展参数

#### `tools: Tools`
- **作用**: 注册自定义工具和动作
- **适用场景**: 需要扩展 Agent 功能，如文件操作、API 调用、2FA 处理
- **典型代码**:
```python
from browser_use import Tools, ActionResult

tools = Tools()

@tools.action(description='Get 2FA code from authenticator')
def get_2fa_code(secret_key: str) -> ActionResult:
    import pyotp
    totp = pyotp.TOTP(secret_key)
    code = totp.now()
    return f"Generated 2FA code: {code}"

agent = Agent(
    task="Login with 2FA",
    llm=llm,
    tools=tools
)
```

#### `sensitive_data: dict`
- **作用**: 安全地传递敏感信息（如密码、API 密钥）
- **适用场景**: 需要在表单中填写敏感信息，但不希望暴露给 LLM
- **典型代码**:
```python
# 简单模式
sensitive_data = {
    'username': 'john_doe',
    'password': 'secret123'
}

# 域名特定模式
sensitive_data = {
    'https://example.com': {
        'email': 'user@example.com',
        'password': 'password123'
    },
    'https://admin.example.com': {
        'admin_key': 'admin_secret'
    }
}

agent = Agent(
    task="Login to the website",
    llm=llm,
    sensitive_data=sensitive_data
)
```

### 视觉和处理参数

#### `use_vision: bool` (默认: True)
- **作用**: 启用/禁用视觉能力处理截图
- **适用场景**: 控制是否使用截图进行页面理解
- **典型代码**:
```python
# 禁用视觉能力（仅使用 DOM）
agent = Agent(
    task="Extract text content",
    llm=llm,
    use_vision=False
)
```

#### `vision_detail_level: str` (默认: 'auto')
- **作用**: 控制截图详细程度 ('low', 'high', 'auto')
- **适用场景**: 平衡性能和准确性
- **典型代码**:
```python
agent = Agent(
    task="Analyze complex UI",
    llm=llm,
    vision_detail_level='high'  # 高质量截图
)
```

#### `page_extraction_llm: BaseChatModel`
- **作用**: 用于页面内容提取的独立 LLM
- **适用场景**: 使用快速小模型进行文本提取，主 LLM 处理决策
- **典型代码**:
```python
main_llm = ChatOpenAI(model='gpt-4.1')
extraction_llm = ChatOpenAI(model='gpt-4.1-mini')  # 更快的模型

agent = Agent(
    task="Extract and analyze data",
    llm=main_llm,
    page_extraction_llm=extraction_llm
)
```

### 行为控制参数

#### `max_actions_per_step: int` (默认: 4)
- **作用**: 每步最大动作数量
- **适用场景**: 控制表单填写等批量操作的效率
- **典型代码**:
```python
# 表单填写场景，允许一次填写多个字段
agent = Agent(
    task="Fill out registration form",
    llm=llm,
    max_actions_per_step=10
)
```

#### `initial_actions: list`
- **作用**: 在主任务前执行的预定义动作
- **适用场景**: 预先导航到特定页面或设置初始状态
- **典型代码**:
```python
initial_actions = [
    {'go_to_url': {'url': 'https://example.com', 'new_tab': True}},
    {'go_to_url': {'url': 'https://admin.example.com', 'new_tab': True}}
]

agent = Agent(
    task="Compare data between two pages",
    llm=llm,
    initial_actions=initial_actions
)
```

#### `max_failures: int` (默认: 3)
- **作用**: 最大失败重试次数
- **适用场景**: 控制错误恢复策略
- **典型代码**:
```python
agent = Agent(
    task="Robust web scraping",
    llm=llm,
    max_failures=5  # 允许更多重试
)
```

### 输出和结构化参数

#### `output_model_schema: type`
- **作用**: 定义结构化输出模式
- **适用场景**: 需要特定格式的数据提取
- **典型代码**:
```python
from pydantic import BaseModel

class ProductInfo(BaseModel):
    name: str
    price: float
    rating: float
    reviews_count: int

agent = Agent(
    task="Extract product information",
    llm=llm,
    output_model_schema=ProductInfo
)
```

### 性能优化参数

#### `flash_mode: bool` (默认: False)
- **作用**: 启用快速模式，禁用思考过程
- **适用场景**: 需要最大化执行速度
- **典型代码**:
```python
agent = Agent(
    task="Quick data extraction",
    llm=llm,
    flash_mode=True,
    extend_system_message="Focus on speed and efficiency"
)
```

#### `use_thinking: bool` (默认: True)
- **作用**: 启用/禁用 LLM 思考过程
- **适用场景**: 控制输出详细程度和性能
- **典型代码**:
```python
agent = Agent(
    task="Simple navigation",
    llm=llm,
    use_thinking=False  # 跳过思考过程
)
```

### 调试和监控参数

#### `save_conversation_path: str | Path`
- **作用**: 保存对话历史到文件
- **适用场景**: 调试、审计或分析 Agent 行为
- **典型代码**:
```python
agent = Agent(
    task="Complex workflow",
    llm=llm,
    save_conversation_path="./logs/conversation.json"
)
```

#### `generate_gif: bool | str` (默认: False)
- **作用**: 生成 Agent 操作的 GIF 动画
- **适用场景**: 演示、调试或文档制作
- **典型代码**:
```python
agent = Agent(
    task="Demo workflow",
    llm=llm,
    generate_gif="./demo.gif"
)
```

#### `calculate_cost: bool` (默认: False)
- **作用**: 计算和跟踪 API 成本
- **适用场景**: 成本监控和优化
- **典型代码**:
```python
agent = Agent(
    task="Cost-monitored task",
    llm=llm,
    calculate_cost=True
)
```

### 超时控制参数

#### `llm_timeout: int` (默认: 60)
- **作用**: LLM 调用超时时间（秒）
- **适用场景**: 控制响应时间和避免长时间等待
- **典型代码**:
```python
agent = Agent(
    task="Time-sensitive task",
    llm=llm,
    llm_timeout=30  # 30秒超时
)
```

#### `step_timeout: int` (默认: 180)
- **作用**: 每步执行超时时间（秒）
- **适用场景**: 控制整体执行时间
- **典型代码**:
```python
agent = Agent(
    task="Quick operations",
    llm=llm,
    step_timeout=60  # 每步最多60秒
)
```

## Agent 主要方法

### 核心执行方法

#### `async def run(max_steps: int = 100, on_step_start=None, on_step_end=None)`
- **作用**: 执行主任务，Agent 的核心方法
- **适用场景**: 启动 Agent 执行任务
- **参数说明**:
  - `max_steps`: 最大执行步数
  - `on_step_start`: 步骤开始回调
  - `on_step_end`: 步骤结束回调
- **典型代码**:
```python
async def step_callback(agent):
    print(f"Step {agent.state.n_steps} completed")

history = await agent.run(
    max_steps=50,
    on_step_end=step_callback
)
```

#### `def run_sync(max_steps: int = 100, on_step_start=None, on_step_end=None)`
- **作用**: 同步版本的 run 方法
- **适用场景**: 在非异步环境中使用
- **典型代码**:
```python
# 同步执行
history = agent.run_sync(max_steps=20)
```

### 历史管理方法

#### `def save_history(file_path: str | Path)`
- **作用**: 保存执行历史到文件
- **适用场景**: 调试、重放或分析
- **典型代码**:
```python
await agent.run()
agent.save_history("./history/task_history.json")
```

#### `async def load_and_rerun(history_file: str | Path, **kwargs)`
- **作用**: 加载并重放历史记录
- **适用场景**: 调试、测试或重现问题
- **典型代码**:
```python
# 重放历史
results = await agent.load_and_rerun(
    "./history/task_history.json",
    max_retries=3,
    skip_failures=True
)
```

#### `async def rerun_history(history, max_retries=3, skip_failures=True, delay_between_actions=2.0)`
- **作用**: 重放指定的历史记录
- **适用场景**: 精确控制重放过程
- **典型代码**:
```python
history = AgentHistoryList.load_from_file("history.json")
results = await agent.rerun_history(
    history,
    max_retries=5,
    delay_between_actions=1.0
)
```

### 控制方法

#### `def pause()`
- **作用**: 暂停 Agent 执行
- **适用场景**: 交互式控制或调试
- **典型代码**:
```python
# 在另一个线程或回调中
agent.pause()
```

#### `def resume()`
- **作用**: 恢复 Agent 执行
- **适用场景**: 从暂停状态继续
- **典型代码**:
```python
agent.resume()
```

#### `def stop()`
- **作用**: 停止 Agent 执行
- **适用场景**: 提前终止任务
- **典型代码**:
```python
agent.stop()
```

#### `async def close()`
- **作用**: 清理资源并关闭 Agent
- **适用场景**: 任务完成后的清理
- **典型代码**:
```python
try:
    await agent.run()
finally:
    await agent.close()
```

### 动作执行方法

#### `async def multi_act(actions: list)`
- **作用**: 执行多个动作
- **适用场景**: 批量操作或复杂工作流
- **典型代码**:
```python
actions = [
    {'click': {'element_id': 'button1'}},
    {'type': {'text': 'Hello World', 'element_id': 'input1'}}
]
results = await agent.multi_act(actions)
```

### 云同步方法

#### `async def authenticate_cloud_sync()`
- **作用**: 认证云同步服务
- **适用场景**: 使用云浏览器或同步功能
- **典型代码**:
```python
await agent.authenticate_cloud_sync()
```

## 浏览器相关参数

### BrowserProfile 核心参数

#### 基础配置

##### `headless: bool` (默认: True)
- **作用**: 控制浏览器是否显示界面
- **适用场景**: 
  - `True`: 服务器环境、自动化脚本
  - `False`: 调试、演示、交互式操作
- **典型代码**:
```python
# 显示浏览器界面
profile = BrowserProfile(headless=False)

# 无界面模式（服务器环境）
profile = BrowserProfile(headless=True)
```

##### `user_data_dir: str | Path`
- **作用**: 指定浏览器用户数据目录
- **适用场景**: 
  - 持久化登录状态
  - 保存 cookies 和会话
  - 多环境隔离
- **典型代码**:
```python
# 持久化配置
profile = BrowserProfile(
    user_data_dir='~/.browser-use/profiles/production'
)

# 临时配置
profile = BrowserProfile(user_data_dir=None)  # 使用临时目录
```

##### `keep_alive: bool` (默认: False)
- **作用**: Agent 完成后是否保持浏览器运行
- **适用场景**:
  - `True`: 多个 Agent 复用同一浏览器
  - `False`: 单次任务后自动清理
- **典型代码**:
```python
# 保持浏览器运行，供后续使用
profile = BrowserProfile(keep_alive=True)

# 任务完成后自动关闭
profile = BrowserProfile(keep_alive=False)
```

#### 安全和访问控制

##### `allowed_domains: list[str]`
- **作用**: 限制 Agent 可访问的域名
- **适用场景**: 安全控制、防止意外访问
- **典型代码**:
```python
profile = BrowserProfile(
    allowed_domains=[
        '*.example.com',
        'api.service.com',
        'https://trusted-site.org'
    ]
)
```

##### `disable_security: bool` (默认: False)
- **作用**: 禁用浏览器安全特性
- **适用场景**: 测试环境、特殊网站兼容性
- **典型代码**:
```python
# 仅在测试环境使用
profile = BrowserProfile(
    disable_security=True,  # 禁用 CORS、证书检查等
)
```

##### `proxy: ProxySettings`
- **作用**: 配置代理服务器
- **适用场景**: 网络代理、地理位置模拟
- **典型代码**:
```python
from browser_use.browser.profile import ProxySettings

proxy = ProxySettings(
    server='http://proxy.example.com:8080',
    username='user',
    password='pass',
    bypass='localhost,127.0.0.1'
)

profile = BrowserProfile(proxy=proxy)
```

#### 性能和行为配置

##### `minimum_wait_page_load_time: float` (默认: 1.0)
- **作用**: 页面加载最小等待时间
- **适用场景**: 确保页面完全加载
- **典型代码**:
```python
# 快速操作
profile = BrowserProfile(minimum_wait_page_load_time=0.5)

# 慢速网络或复杂页面
profile = BrowserProfile(minimum_wait_page_load_time=3.0)
```

##### `wait_between_actions: float` (默认: 1.0)
- **作用**: 动作间等待时间
- **适用场景**: 控制操作速度，避免过快操作
- **典型代码**:
```python
# 快速执行
profile = BrowserProfile(wait_between_actions=0.1)

# 模拟人类操作
profile = BrowserProfile(wait_between_actions=2.0)
```

##### `window_size: dict`
- **作用**: 设置浏览器窗口大小
- **适用场景**: 响应式测试、截图一致性
- **典型代码**:
```python
profile = BrowserProfile(
    window_size={'width': 1920, 'height': 1080}
)
```

#### 存储和会话管理

##### `storage_state: str | Path | dict`
- **作用**: 加载或保存浏览器存储状态
- **适用场景**: 会话复用、登录状态保持
- **典型代码**:
```python
# 从文件加载状态
profile = BrowserProfile(
    storage_state='./auth_state.json'
)

# 直接传入状态字典
profile = BrowserProfile(
    storage_state={
        'cookies': [...],
        'localStorage': {...}
    }
)
```

#### 录制和调试

##### `record_video_dir: str | Path`
- **作用**: 录制操作视频
- **适用场景**: 调试、演示、审计
- **典型代码**:
```python
profile = BrowserProfile(
    record_video_dir='./recordings',
    record_video_framerate=30
)
```

##### `downloads_path: str | Path`
- **作用**: 设置下载目录
- **适用场景**: 文件下载任务
- **典型代码**:
```python
profile = BrowserProfile(
    downloads_path='./downloads',
    auto_download_pdfs=True
)
```

### BrowserSession 参数

#### 会话标识

##### `id: str`
- **作用**: 会话唯一标识符
- **适用场景**: 会话跟踪、日志关联
- **典型代码**:
```python
session = BrowserSession(
    id='task-001',
    browser_profile=profile
)
```

#### 云浏览器配置

##### `use_cloud: bool`
- **作用**: 使用云浏览器服务
- **适用场景**: 远程执行、资源节约
- **典型代码**:
```python
session = BrowserSession(
    use_cloud=True,
    browser_profile=profile
)
```

## 典型使用案例

### 1. 基础网页自动化

```python
from browser_use import Agent, ChatOpenAI

async def basic_automation():
    llm = ChatOpenAI(model='gpt-4.1-mini')
    
    agent = Agent(
        task="Go to Google and search for 'browser automation'",
        llm=llm,
        use_vision=True,
        max_actions_per_step=3
    )
    
    history = await agent.run(max_steps=10)
    return history
```

### 2. 表单填写和数据提取

```python
from pydantic import BaseModel
from browser_use import Agent, ChatOpenAI

class ContactInfo(BaseModel):
    name: str
    email: str
    phone: str

async def form_filling_extraction():
    llm = ChatOpenAI(model='gpt-4.1-mini')
    
    sensitive_data = {
        'https://example.com': {
            'name': 'John Doe',
            'email': 'john@example.com',
            'phone': '+1234567890'
        }
    }
    
    agent = Agent(
        task="Fill the contact form and extract confirmation details",
        llm=llm,
        sensitive_data=sensitive_data,
        output_model_schema=ContactInfo,
        max_actions_per_step=5
    )
    
    return await agent.run()
```

### 3. 多步骤工作流

```python
async def multi_step_workflow():
    llm = ChatOpenAI(model='gpt-4.1-mini')
    
    initial_actions = [
        {'go_to_url': {'url': 'https://admin.example.com'}},
    ]
    
    agent = Agent(
        task="""
        1. Login to the admin panel
        2. Navigate to user management
        3. Export user list
        4. Download the exported file
        """,
        llm=llm,
        initial_actions=initial_actions,
        max_failures=5,
        save_conversation_path='./logs/workflow.json'
    )
    
    return await agent.run(max_steps=20)
```

### 4. 2FA 认证处理

```python
from browser_use import Tools, ActionResult
import pyotp

async def two_factor_auth():
    tools = Tools()
    
    @tools.action(description='Generate 2FA code from secret')
    def generate_2fa_code(secret: str) -> ActionResult:
        totp = pyotp.TOTP(secret)
        code = totp.now()
        return f"2FA code: {code}"
    
    sensitive_data = {
        'username': 'user@example.com',
        'password': 'secret123',
        '2fa_secret': 'JBSWY3DPEHPK3PXP'
    }
    
    agent = Agent(
        task="Login with 2FA authentication",
        llm=ChatOpenAI(model='gpt-4.1-mini'),
        tools=tools,
        sensitive_data=sensitive_data
    )
    
    return await agent.run()
```

### 5. 高性能数据抓取

```python
async def high_performance_scraping():
    # 使用快速模型和优化配置
    fast_llm = ChatOpenAI(model='gpt-4.1-mini')
    
    profile = BrowserProfile(
        headless=True,
        minimum_wait_page_load_time=0.5,
        wait_between_actions=0.1,
        deterministic_rendering=False  # 提高性能
    )
    
    agent = Agent(
        task="Scrape product data from multiple pages",
        llm=fast_llm,
        browser_profile=profile,
        flash_mode=True,  # 最大化速度
        use_thinking=False,
        max_actions_per_step=8
    )
    
    return await agent.run(max_steps=50)
```

### 6. 会话复用和状态管理

```python
async def session_reuse():
    # 第一个 Agent：登录并保存状态
    profile = BrowserProfile(
        headless=False,
        user_data_dir='./browser_profile',
        keep_alive=True
    )
    
    session = BrowserSession(browser_profile=profile)
    
    login_agent = Agent(
        task="Login to the website and navigate to dashboard",
        llm=ChatOpenAI(model='gpt-4.1-mini'),
        browser_session=session
    )
    
    await login_agent.run()
    
    # 第二个 Agent：复用已登录的会话
    data_agent = Agent(
        task="Extract user data from dashboard",
        llm=ChatOpenAI(model='gpt-4.1-mini'),
        browser_session=session  # 复用同一会话
    )
    
    return await data_agent.run()
```

### 7. 并行多任务处理

```python
import asyncio

async def parallel_tasks():
    tasks = [
        "Search Google for 'AI news'",
        "Check weather on weather.com",
        "Get latest Bitcoin price"
    ]
    
    # 创建多个独立的浏览器会话
    agents = []
    for i, task in enumerate(tasks):
        profile = BrowserProfile(
            headless=True,
            user_data_dir=f'./temp_profile_{i}'
        )
        
        agent = Agent(
            task=task,
            llm=ChatOpenAI(model='gpt-4.1-mini'),
            browser_profile=profile
        )
        agents.append(agent)
    
    # 并行执行
    results = await asyncio.gather(*[agent.run() for agent in agents])
    return results
```

### 8. 调试和监控

```python
async def debugging_workflow():
    async def step_monitor(agent):
        print(f"Step {agent.state.n_steps}: {agent.state.last_model_output}")
    
    agent = Agent(
        task="Complex multi-step task",
        llm=ChatOpenAI(model='gpt-4.1-mini'),
        save_conversation_path='./debug/conversation.json',
        generate_gif='./debug/workflow.gif',
        calculate_cost=True,
        use_vision=True,
        vision_detail_level='high'
    )
    
    history = await agent.run(
        max_steps=30,
        on_step_end=step_monitor
    )
    
    # 保存历史记录
    agent.save_history('./debug/history.json')
    
    return history
```

## 最佳实践

### 1. 性能优化

```python
# 快速执行配置
fast_config = {
    'flash_mode': True,
    'use_thinking': False,
    'max_actions_per_step': 8,
    'llm_timeout': 30,
    'browser_profile': BrowserProfile(
        headless=True,
        minimum_wait_page_load_time=0.3,
        wait_between_actions=0.1
    )
}

agent = Agent(task="Quick task", llm=fast_llm, **fast_config)
```

### 2. 错误处理和重试

```python
async def robust_execution():
    agent = Agent(
        task="Potentially unstable task",
        llm=llm,
        max_failures=5,
        step_timeout=300,
        save_conversation_path='./logs/errors.json'
    )
    
    try:
        return await agent.run()
    except Exception as e:
        # 保存失败状态用于调试
        agent.save_history(f'./logs/failed_{int(time.time())}.json')
        raise
```

### 3. 安全配置

```python
# 生产环境安全配置
secure_profile = BrowserProfile(
    allowed_domains=['*.trusted-domain.com'],
    disable_security=False,
    user_data_dir='./secure_profile',
    proxy=ProxySettings(server='http://secure-proxy:8080')
)

agent = Agent(
    task="Production task",
    llm=llm,
    browser_profile=secure_profile,
    sensitive_data=encrypted_credentials
)
```

### 4. 资源管理

```python
async def proper_cleanup():
    session = None
    try:
        session = BrowserSession(browser_profile=profile)
        agent = Agent(task="Task", llm=llm, browser_session=session)
        return await agent.run()
    finally:
        if session:
            await session.kill()  # 确保清理资源
```

### 5. 监控和日志

```python
import logging

# 设置详细日志
logging.basicConfig(level=logging.DEBUG)

async def monitored_execution():
    def cost_monitor(agent):
        if hasattr(agent, 'cost_tracker'):
            print(f"Current cost: ${agent.cost_tracker.total_cost:.4f}")
    
    agent = Agent(
        task="Monitored task",
        llm=llm,
        calculate_cost=True,
        save_conversation_path='./logs/detailed.json'
    )
    
    return await agent.run(on_step_end=cost_monitor)
```

---

本文档涵盖了 Browser-Use Agent 的主要参数和方法。更多详细信息请参考 [官方文档](https://docs.browser-use.com/) 和 [GitHub 仓库](https://github.com/browser-use/browser-use)。