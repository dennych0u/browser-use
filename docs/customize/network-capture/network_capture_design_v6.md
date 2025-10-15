# Browser-Use 网络请求/响应捕获 Watchdog 设计方案 v6（深度优化版）

## 1. 概述

本方案基于对Browser-Use架构的深度分析，设计一个完全契合现有体系的网络流量捕获watchdog。该方案严格遵循原始需求，充分利用Browser-Use现有的事件机制、CDP集成、Agent生命周期管理等核心能力，实现高效、稳定的HTTP/WebSocket流量捕获。

### 1.1 核心优化要点

1. **深度集成Agent生命周期**：直接从Agent实例获取conversation_id，无需额外配置
2. **简化事件模型**：基于原始需求重新设计事件结构，避免过度设计
3. **优化CDP集成**：遵循Browser-Use的CDP最佳实践，确保稳定性
4. **智能存储策略**：基于原始需求的去重和缓存机制
5. **配置集成优化**：完全融入Browser-Use的配置体系

### 1.2 架构契合度分析

基于对Browser-Use核心架构的分析：
- **事件总线**：完全基于bubus事件机制，遵循现有的事件处理模式
- **Watchdog模式**：继承BaseWatchdog，遵循LISTENS_TO/EMITS声明模式
- **CDP集成**：使用现有的CDP会话管理和事件监听机制
- **配置管理**：集成到BrowserProfile和BrowserSession配置体系
- **生命周期管理**：与Agent和BrowserSession生命周期完全同步

## 2. 原始需求分析与设计映射

### 2.1 核心需求重新梳理

基于原始需求文档，核心功能需求如下：

1. **流量捕获**：捕获Agent运行期间所有HTTP通信流量
2. **配置过滤**：支持基于域名、文件类型的流量过滤
3. **页面关联**：记录触发请求的前端页面信息
4. **完整数据**：成对捕获请求/响应的完整信息
5. **智能存储**：Redis缓存 + 数据库持久化，支持去重
6. **大小控制**：响应体大小限制和截断
7. **会话标识**：通过conversation_id区分不同Agent任务

### 2.2 设计映射策略

| 原始需求 | Browser-Use现有能力 | 设计方案 |
|---------|-------------------|---------|
| 流量捕获 | CDP Network域事件 | 监听Network.requestWillBeSent等事件 |
| 配置过滤 | BrowserProfile配置 | 扩展BrowserProfile添加网络捕获配置 |
| 页面关联 | DOMWatchdog页面状态 | 复用现有页面上下文获取机制 |
| 完整数据 | CDP响应体获取 | 使用Network.getResponseBody命令 |
| 智能存储 | 无现有实现 | 新增NetworkStorageManager组件 |
| 大小控制 | 无现有实现 | 在响应体获取时实现截断 |
| 会话标识 | Agent.id属性 | 直接从Agent实例获取conversation_id |

## 3. 优化后的事件设计

### 3.1 简化的事件模型

基于原始需求，重新设计更简洁的事件模型：

#### 文件位置：`browser_use/browser/network_events.py`（新建文件）

```python
"""网络捕获相关事件定义（v6优化版）"""

import time
from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field
from bubus import BaseEvent
from cdp_use.cdp.target import TargetID

# ============================================================================
# 核心数据模型（基于原始需求优化）
# ============================================================================

class NetworkRequestData(BaseModel):
    """网络请求数据（完整信息）"""
    # 请求基本信息
    url: str = Field(description="请求URL")
    method: str = Field(description="HTTP方法")
    headers: Dict[str, str] = Field(description="请求头")
    body: Optional[str] = Field(None, description="请求体")
    
    # 页面上下文信息（原始需求2）
    page_url: str = Field(description="触发请求的页面URL")
    page_title: str = Field(description="页面标题")
    target_id: TargetID = Field(description="目标ID")
    
    # 时序信息
    timestamp: float = Field(default_factory=time.time, description="请求时间戳")
    
    # 资源类型和发起者
    resource_type: str = Field(description="资源类型")
    initiator: Dict[str, Any] = Field(default_factory=dict, description="请求发起者")

class NetworkResponseData(BaseModel):
    """网络响应数据（完整信息）"""
    # 响应基本信息
    status: int = Field(description="HTTP状态码")
    status_text: str = Field(description="状态文本")
    headers: Dict[str, str] = Field(description="响应头")
    body: Optional[str] = Field(None, description="响应体")
    
    # 响应体处理信息（原始需求5）
    body_truncated: bool = Field(False, description="响应体是否被截断")
    original_body_size: Optional[int] = Field(None, description="原始响应体大小")
    
    # 时序信息
    timestamp: float = Field(default_factory=time.time, description="响应时间戳")
    
    # 内容类型
    mime_type: str = Field(description="MIME类型")

class NetworkTrafficCapture(BaseModel):
    """完整的网络流量捕获数据（原始需求3）"""
    # 唯一标识
    request_id: str = Field(description="请求ID")
    conversation_id: str = Field(description="会话ID，区分不同Agent任务")
    
    # 请求/响应数据
    request: NetworkRequestData = Field(description="请求数据")
    response: Optional[NetworkResponseData] = Field(None, description="响应数据")
    
    # 状态信息
    completed: bool = Field(False, description="是否完成（请求/响应都已捕获）")
    failed: bool = Field(False, description="是否失败")
    error_message: Optional[str] = Field(None, description="错误信息")
    
    # 时序信息
    duration_ms: Optional[float] = Field(None, description="请求耗时（毫秒）")

# ============================================================================
# 简化的事件定义（基于原始需求）
# ============================================================================

class NetworkTrafficCapturedEvent(BaseEvent[None]):
    """网络流量捕获完成事件（核心事件）"""
    
    traffic_data: NetworkTrafficCapture = Field(description="捕获的流量数据")
    should_store: bool = Field(description="是否应该存储（基于过滤规则）")
    
    event_timeout: float | None = 30.0

class NetworkCaptureErrorEvent(BaseEvent[None]):
    """网络捕获错误事件"""
    
    request_id: str = Field(description="请求ID")
    error_message: str = Field(description="错误信息")
    conversation_id: str = Field(description="会话ID")
    
    event_timeout: float | None = 10.0
```

### 3.2 事件注册

#### 文件位置：`browser_use/browser/events.py`（修改现有文件）

```python
# network capture feature code
# 在现有events.py文件中添加导入
from browser_use.browser.network_events import (
    NetworkTrafficCapturedEvent,
    NetworkCaptureErrorEvent,
)
```

## 4. 配置集成优化

### 4.1 集成到BrowserProfile

#### 文件位置：`browser_use/browser/browser_profile.py`（修改现有文件）

```python
# network capture feature code
# 在BrowserProfile类中添加网络捕获配置

@dataclass
class NetworkCaptureConfig:
    """网络捕获配置（集成到BrowserProfile）"""
    
    # 基本开关（原始需求）
    enabled: bool = False
    
    # 过滤配置（原始需求1）
    allowed_domains: List[str] = field(default_factory=list)  # 允许的域名
    blocked_domains: List[str] = field(default_factory=list)  # 阻止的域名
    allowed_resource_types: List[str] = field(default_factory=lambda: [
        'Document', 'XHR', 'Fetch', 'WebSocket'
    ])  # 允许的资源类型
    blocked_file_extensions: List[str] = field(default_factory=lambda: [
        '.jpg', '.jpeg', '.png', '.gif', '.css', '.js', '.ico', '.svg'
    ])  # 阻止的文件扩展名
    
    # 大小限制（原始需求5）
    max_request_body_size: int = 1024 * 1024  # 1MB
    max_response_body_size: int = 10 * 1024 * 1024  # 10MB
    
    # 存储配置（原始需求4）
    redis_key_prefix: str = "browser_use:network_capture"
    enable_deduplication: bool = True  # 启用去重
    
    # 日志配置（原始需求注意事项5）
    log_level: str = "INFO"  # DEBUG, INFO, WARNING, ERROR

# 在BrowserProfile类中添加字段
class BrowserProfile:
    # ... 现有字段 ...
    
    # network capture feature code
    network_capture: NetworkCaptureConfig = field(default_factory=NetworkCaptureConfig)
```

### 4.2 环境变量配置

#### 文件位置：项目根目录`.env`文件

```bash
# network capture feature code
# 网络捕获相关配置（原始需求注意事项4）

# Redis配置
NETWORK_CAPTURE_REDIS_HOST=localhost
NETWORK_CAPTURE_REDIS_PORT=6379
NETWORK_CAPTURE_REDIS_DB=0
NETWORK_CAPTURE_REDIS_PASSWORD=

# 数据库配置
NETWORK_CAPTURE_DB_URL=sqlite:///network_capture.db
# 或者使用PostgreSQL: postgresql://user:password@localhost/network_capture

# 捕获配置
NETWORK_CAPTURE_ENABLED=false
NETWORK_CAPTURE_MAX_RESPONSE_SIZE=10485760  # 10MB
```

## 5. 核心Watchdog实现（深度优化版）

### 5.1 主要Watchdog类

#### 文件位置：`browser_use/browser/watchdogs/network_capture_watchdog.py`（新建文件）

```python
"""网络请求/响应捕获watchdog实现（v6深度优化版）"""

import asyncio
import json
import time
import traceback
from collections import defaultdict
from typing import Any, Dict, List, Optional, Set
from weakref import WeakSet
from pydantic import PrivateAttr

from browser_use.browser.events import (
    BrowserConnectedEvent,
    BrowserStoppedEvent,
    TabCreatedEvent,
    TabClosedEvent,
)
from browser_use.browser.network_events import (
    NetworkTrafficCapturedEvent,
    NetworkCaptureErrorEvent,
    NetworkRequestData,
    NetworkResponseData,
    NetworkTrafficCapture,
)
from browser_use.browser.watchdog_base import BaseWatchdog
from browser_use.browser.network_storage import NetworkStorageManager


class NetworkCaptureWatchdog(BaseWatchdog):
    """网络请求/响应捕获watchdog（v6深度优化版）
    
    基于Browser-Use架构深度优化的网络流量捕获实现：
    1. 完全集成Agent生命周期管理
    2. 遵循Browser-Use的CDP最佳实践
    3. 简化事件模型，专注原始需求
    4. 智能存储和去重机制
    """
    
    # 声明监听的Browser-Use事件
    LISTENS_TO = [
        BrowserConnectedEvent,
        BrowserStoppedEvent,
        TabCreatedEvent,
        TabClosedEvent,
    ]
    
    # 发出的事件
    EMITS = [
        NetworkTrafficCapturedEvent,
        NetworkCaptureErrorEvent,
    ]
    
    # 私有状态管理
    _storage_manager: Optional[NetworkStorageManager] = PrivateAttr(default=None)
    _cdp_event_tasks: WeakSet[asyncio.Task] = PrivateAttr(default_factory=WeakSet)
    _active_requests: Dict[str, Dict[str, Any]] = PrivateAttr(default_factory=dict)
    _sessions_with_listeners: Set[str] = PrivateAttr(default_factory=set)
    _conversation_id: Optional[str] = PrivateAttr(default=None)
    
    def __init__(self, **data):
        super().__init__(**data)
        # network capture feature code
        self._storage_manager = None
        self._cdp_event_tasks = WeakSet()
        self._active_requests = {}
        self._sessions_with_listeners = set()
        self._conversation_id = None
    
    @property
    def config(self):
        """获取网络捕获配置"""
        if hasattr(self.browser_session, 'browser_profile'):
            return self.browser_session.browser_profile.network_capture
        return None
    
    def _get_conversation_id(self) -> str:
        """获取conversation_id（基于Agent实例优化）"""
        if self._conversation_id:
            return self._conversation_id
        
        try:
            # 方法1：从browser_session获取agent引用
            if hasattr(self.browser_session, 'agent') and self.browser_session.agent:
                agent_id = getattr(self.browser_session.agent, 'id', None)
                if agent_id:
                    self._conversation_id = str(agent_id)
                    self.logger.info(f"[NetworkCapture] 从Agent获取conversation_id: {agent_id}")
                    return self._conversation_id
            
            # 方法2：从环境变量获取
            import os
            env_id = os.getenv('BROWSER_USE_CONVERSATION_ID')
            if env_id:
                self._conversation_id = env_id
                return self._conversation_id
            
            # 方法3：生成默认值
            default_id = f"session_{int(time.time())}"
            self._conversation_id = default_id
            self.logger.warning(f"[NetworkCapture] 使用默认conversation_id: {default_id}")
            return self._conversation_id
            
        except Exception as e:
            self.logger.error(f"[NetworkCapture] 获取conversation_id失败: {e}")
            fallback_id = f"fallback_{int(time.time())}"
            self._conversation_id = fallback_id
            return fallback_id
    
    # ========================================================================
    # Browser-Use事件处理器
    # ========================================================================
    
    async def on_BrowserConnectedEvent(self, event: BrowserConnectedEvent) -> None:
        """浏览器连接时初始化网络捕获"""
        if not self.config or not self.config.enabled:
            self.logger.info("[NetworkCapture] 网络捕获功能已禁用")
            return
        
        conversation_id = self._get_conversation_id()
        self.logger.info(f"[NetworkCapture] 初始化网络捕获 (conversation_id: {conversation_id})")
        
        try:
            # 初始化存储管理器
            self._storage_manager = NetworkStorageManager(self.config)
            await self._storage_manager.initialize()
            
            self.logger.info("[NetworkCapture] 网络捕获初始化完成")
            
        except Exception as e:
            self.logger.error(f"[NetworkCapture] 初始化失败: {e}")
            # 发送错误事件
            error_event = NetworkCaptureErrorEvent(
                request_id="init",
                error_message=f"初始化失败: {str(e)}",
                conversation_id=conversation_id
            )
            await self.browser_session.event_bus.publish(error_event)
    
    async def on_TabCreatedEvent(self, event: TabCreatedEvent) -> None:
        """新标签页创建时设置网络监听器"""
        if not self.config or not self.config.enabled:
            return
        
        target_id = event.target_id
        self.logger.debug(f"[NetworkCapture] 为标签页 {target_id} 设置网络监听器")
        
        try:
            # 获取CDP会话
            cdp_session = await self.browser_session.get_or_create_cdp_session(target_id)
            
            # 避免重复设置
            if cdp_session.session_id in self._sessions_with_listeners:
                return
            
            # 启用网络域
            await cdp_session.cdp_client.send.Network.enable(
                session_id=cdp_session.session_id
            )
            
            # 设置网络事件监听器（遵循CDP最佳实践）
            cdp_session.cdp_client.register.Network.requestWillBeSent(
                self._create_cdp_handler(self._handle_request_will_be_sent, target_id)
            )
            cdp_session.cdp_client.register.Network.responseReceived(
                self._create_cdp_handler(self._handle_response_received, target_id)
            )
            cdp_session.cdp_client.register.Network.loadingFinished(
                self._create_cdp_handler(self._handle_loading_finished, target_id, cdp_session)
            )
            cdp_session.cdp_client.register.Network.loadingFailed(
                self._create_cdp_handler(self._handle_loading_failed, target_id)
            )
            
            # 记录已设置监听器的会话
            self._sessions_with_listeners.add(cdp_session.session_id)
            
            self.logger.debug(f"[NetworkCapture] 标签页 {target_id} 网络监听器设置完成")
            
        except Exception as e:
            self.logger.error(f"[NetworkCapture] 设置网络监听器失败: {e}")
    
    async def on_TabClosedEvent(self, event: TabClosedEvent) -> None:
        """标签页关闭时清理状态"""
        target_id = event.target_id
        
        # 清理该标签页的活跃请求
        to_remove = [
            req_id for req_id, req_info in self._active_requests.items()
            if req_info.get('target_id') == target_id
        ]
        
        for req_id in to_remove:
            del self._active_requests[req_id]
        
        self.logger.debug(f"[NetworkCapture] 清理标签页 {target_id} 的 {len(to_remove)} 个活跃请求")
    
    async def on_BrowserStoppedEvent(self, event: BrowserStoppedEvent) -> None:
        """浏览器停止时清理资源并持久化数据"""
        if not self._storage_manager:
            return
        
        self.logger.info("[NetworkCapture] 浏览器停止，开始清理和持久化")
        
        try:
            # 取消所有CDP事件任务
            for task in list(self._cdp_event_tasks):
                if not task.done():
                    task.cancel()
            
            if self._cdp_event_tasks:
                await asyncio.gather(*self._cdp_event_tasks, return_exceptions=True)
            
            # 持久化Redis中的数据到数据库（原始需求4）
            await self._storage_manager.persist_to_database()
            
            # 清理资源
            await self._storage_manager.cleanup()
            
            self.logger.info("[NetworkCapture] 清理和持久化完成")
            
        except Exception as e:
            self.logger.error(f"[NetworkCapture] 清理过程中出错: {e}")
    
    # ========================================================================
    # CDP事件处理方法（优化版）
    # ========================================================================
    
    def _create_cdp_handler(self, handler_func, *args):
        """创建CDP事件处理器（遵循最佳实践）"""
        def wrapper(event_data: Dict[str, Any]):
            task = asyncio.create_task(handler_func(event_data, *args))
            self._cdp_event_tasks.add(task)
            task.add_done_callback(lambda t: self._cdp_event_tasks.discard(t))
        return wrapper
    
    async def _handle_request_will_be_sent(self, event_data: Dict[str, Any], target_id: str) -> None:
        """处理请求开始事件"""
        try:
            request_id = event_data.get('requestId', '')
            request = event_data.get('request', {})
            resource_type = event_data.get('type', 'Other')
            
            # 应用过滤规则（原始需求1）
            if not self._should_capture_request(request.get('url', ''), resource_type):
                return
            
            # 获取页面上下文（原始需求2）
            page_context = await self._get_page_context(target_id)
            
            # 构建请求数据
            request_data = NetworkRequestData(
                url=request.get('url', ''),
                method=request.get('method', 'GET'),
                headers=request.get('headers', {}),
                body=request.get('postData'),
                page_url=page_context['url'],
                page_title=page_context['title'],
                target_id=target_id,
                resource_type=resource_type,
                initiator=event_data.get('initiator', {})
            )
            
            # 存储活跃请求
            self._active_requests[request_id] = {
                'request_data': request_data,
                'start_time': time.time(),
                'target_id': target_id
            }
            
            self.logger.debug(f"[NetworkCapture] 请求开始: {request_data.method} {request_data.url[:100]}")
            
        except Exception as e:
            self.logger.error(f"[NetworkCapture] 处理请求开始事件失败: {e}")
    
    async def _handle_response_received(self, event_data: Dict[str, Any], target_id: str) -> None:
        """处理响应接收事件"""
        try:
            request_id = event_data.get('requestId', '')
            response = event_data.get('response', {})
            
            if request_id not in self._active_requests:
                return
            
            # 构建响应数据（不包含body，在loading_finished时获取）
            response_data = NetworkResponseData(
                status=response.get('status', 0),
                status_text=response.get('statusText', ''),
                headers=response.get('headers', {}),
                mime_type=response.get('mimeType', ''),
            )
            
            # 更新活跃请求
            self._active_requests[request_id]['response_data'] = response_data
            
        except Exception as e:
            self.logger.error(f"[NetworkCapture] 处理响应接收事件失败: {e}")
    
    async def _handle_loading_finished(self, event_data: Dict[str, Any], target_id: str, cdp_session) -> None:
        """处理加载完成事件"""
        try:
            request_id = event_data.get('requestId', '')
            
            if request_id not in self._active_requests:
                return
            
            request_info = self._active_requests[request_id]
            request_data = request_info['request_data']
            response_data = request_info.get('response_data')
            
            if not response_data:
                return
            
            # 获取响应体（原始需求3）
            response_body = await self._get_response_body(request_id, cdp_session)
            if response_body:
                response_data.body = response_body['body']
                response_data.body_truncated = response_body['truncated']
                response_data.original_body_size = response_body['original_size']
            
            # 构建完整的流量捕获数据
            traffic_capture = NetworkTrafficCapture(
                request_id=request_id,
                conversation_id=self._get_conversation_id(),
                request=request_data,
                response=response_data,
                completed=True,
                duration_ms=(time.time() - request_info['start_time']) * 1000
            )
            
            # 判断是否应该存储（基于过滤规则）
            should_store = self._should_store_traffic(traffic_capture)
            
            # 发出流量捕获事件
            capture_event = NetworkTrafficCapturedEvent(
                traffic_data=traffic_capture,
                should_store=should_store
            )
            await self.browser_session.event_bus.publish(capture_event)
            
            # 存储到Redis（如果需要）
            if should_store and self._storage_manager:
                await self._storage_manager.store_traffic_data(traffic_capture)
            
            # 清理活跃请求
            del self._active_requests[request_id]
            
            self.logger.debug(f"[NetworkCapture] 请求完成: {request_data.url[:100]}")
            
        except Exception as e:
            self.logger.error(f"[NetworkCapture] 处理加载完成事件失败: {e}")
    
    async def _handle_loading_failed(self, event_data: Dict[str, Any], target_id: str) -> None:
        """处理加载失败事件"""
        try:
            request_id = event_data.get('requestId', '')
            error_text = event_data.get('errorText', 'Unknown error')
            
            if request_id not in self._active_requests:
                return
            
            request_info = self._active_requests[request_id]
            request_data = request_info['request_data']
            
            # 构建失败的流量捕获数据
            traffic_capture = NetworkTrafficCapture(
                request_id=request_id,
                conversation_id=self._get_conversation_id(),
                request=request_data,
                response=None,
                completed=False,
                failed=True,
                error_message=error_text,
                duration_ms=(time.time() - request_info['start_time']) * 1000
            )
            
            # 发出流量捕获事件
            capture_event = NetworkTrafficCapturedEvent(
                traffic_data=traffic_capture,
                should_store=False  # 失败的请求通常不存储
            )
            await self.browser_session.event_bus.publish(capture_event)
            
            # 清理活跃请求
            del self._active_requests[request_id]
            
            self.logger.debug(f"[NetworkCapture] 请求失败: {request_data.url[:100]} - {error_text}")
            
        except Exception as e:
            self.logger.error(f"[NetworkCapture] 处理加载失败事件失败: {e}")
    
    # ========================================================================
    # 辅助方法
    # ========================================================================
    
    def _should_capture_request(self, url: str, resource_type: str) -> bool:
        """判断是否应该捕获请求（原始需求1）"""
        if not self.config:
            return False
        
        # 检查资源类型
        if resource_type not in self.config.allowed_resource_types:
            return False
        
        # 检查文件扩展名
        for ext in self.config.blocked_file_extensions:
            if url.lower().endswith(ext.lower()):
                return False
        
        # 检查域名
        from urllib.parse import urlparse
        try:
            parsed_url = urlparse(url)
            domain = parsed_url.netloc.lower()
            
            # 如果有允许列表，只允许列表中的域名
            if self.config.allowed_domains:
                allowed = any(
                    domain == allowed_domain.lower() or 
                    domain.endswith('.' + allowed_domain.lower())
                    for allowed_domain in self.config.allowed_domains
                )
                if not allowed:
                    return False
            
            # 检查阻止列表
            if self.config.blocked_domains:
                blocked = any(
                    domain == blocked_domain.lower() or 
                    domain.endswith('.' + blocked_domain.lower())
                    for blocked_domain in self.config.blocked_domains
                )
                if blocked:
                    return False
            
        except Exception as e:
            self.logger.debug(f"[NetworkCapture] URL解析失败: {url} - {e}")
            return False
        
        return True
    
    def _should_store_traffic(self, traffic_capture: NetworkTrafficCapture) -> bool:
        """判断是否应该存储流量数据"""
        if not traffic_capture.completed or traffic_capture.failed:
            return False
        
        # 可以添加更多存储条件
        return True
    
    async def _get_page_context(self, target_id: str) -> Dict[str, str]:
        """获取页面上下文信息（原始需求2）"""
        try:
            cdp_session = await self.browser_session.get_or_create_cdp_session(target_id)
            
            # 获取页面URL
            url_result = await cdp_session.cdp_client.send.Runtime.evaluate(
                expression="window.location.href",
                session_id=cdp_session.session_id
            )
            page_url = url_result.get('result', {}).get('value', '')
            
            # 获取页面标题
            title_result = await cdp_session.cdp_client.send.Runtime.evaluate(
                expression="document.title",
                session_id=cdp_session.session_id
            )
            page_title = title_result.get('result', {}).get('value', '')
            
            return {
                'url': page_url,
                'title': page_title
            }
            
        except Exception as e:
            self.logger.debug(f"[NetworkCapture] 获取页面上下文失败: {e}")
            return {
                'url': '',
                'title': ''
            }
    
    async def _get_response_body(self, request_id: str, cdp_session) -> Optional[Dict[str, Any]]:
        """获取响应体（原始需求5：支持大小限制）"""
        try:
            result = await cdp_session.cdp_client.send.Network.getResponseBody(
                requestId=request_id,
                session_id=cdp_session.session_id
            )
            
            body = result.get('body', '')
            base64_encoded = result.get('base64Encoded', False)
            
            # 解码base64
            if base64_encoded:
                import base64 as b64
                try:
                    body = b64.b64decode(body).decode('utf-8', errors='ignore')
                except Exception:
                    # 如果解码失败，保持原始base64格式
                    pass
            
            # 检查大小限制
            original_size = len(body)
            truncated = False
            
            if self.config and original_size > self.config.max_response_body_size:
                body = body[:self.config.max_response_body_size]
                truncated = True
            
            return {
                'body': body,
                'truncated': truncated,
                'original_size': original_size
            }
            
        except Exception as e:
            self.logger.debug(f"[NetworkCapture] 获取响应体失败: {e}")
            return None
```

## 6. 存储管理器实现

### 6.1 NetworkStorageManager

#### 文件位置：`browser_use/browser/network_storage.py`（新建文件）

```python
"""网络流量存储管理器（v6优化版）"""

import asyncio
import hashlib
import json
import os
from typing import Any, Dict, List, Optional
import logging

from browser_use.browser.network_events import NetworkTrafficCapture


class NetworkStorageManager:
    """网络流量存储管理器
    
    负责Redis缓存和数据库持久化存储，支持去重机制（原始需求4）
    """
    
    def __init__(self, config):
        self.config = config
        self.logger = logging.getLogger(__name__)
        self._redis_client = None
        self._db_engine = None
    
    async def initialize(self):
        """初始化存储组件"""
        try:
            # 初始化Redis连接
            await self._init_redis()
            
            # 初始化数据库连接
            await self._init_database()
            
            self.logger.info("[NetworkStorage] 存储管理器初始化完成")
            
        except Exception as e:
            self.logger.error(f"[NetworkStorage] 初始化失败: {e}")
            raise
    
    async def _init_redis(self):
        """初始化Redis连接"""
        try:
            import redis.asyncio as redis
            
            # 从环境变量读取Redis配置
            redis_host = os.getenv('NETWORK_CAPTURE_REDIS_HOST', 'localhost')
            redis_port = int(os.getenv('NETWORK_CAPTURE_REDIS_PORT', '6379'))
            redis_db = int(os.getenv('NETWORK_CAPTURE_REDIS_DB', '0'))
            redis_password = os.getenv('NETWORK_CAPTURE_REDIS_PASSWORD', None)
            
            self._redis_client = redis.Redis(
                host=redis_host,
                port=redis_port,
                db=redis_db,
                password=redis_password,
                decode_responses=True
            )
            
            # 测试连接
            await self._redis_client.ping()
            self.logger.info(f"[NetworkStorage] Redis连接成功: {redis_host}:{redis_port}")
            
        except ImportError:
            self.logger.warning("[NetworkStorage] Redis库未安装，跳过Redis初始化")
            self._redis_client = None
        except Exception as e:
            self.logger.warning(f"[NetworkStorage] Redis连接失败: {e}")
            self._redis_client = None
    
    async def _init_database(self):
        """初始化数据库连接"""
        try:
            import sqlalchemy as sa
            from sqlalchemy.ext.asyncio import create_async_engine
            
            # 从环境变量读取数据库配置
            db_url = os.getenv('NETWORK_CAPTURE_DB_URL', 'sqlite+aiosqlite:///network_capture.db')
            
            self._db_engine = create_async_engine(db_url)
            
            # 创建表结构
            await self._create_tables()
            
            self.logger.info(f"[NetworkStorage] 数据库连接成功: {db_url}")
            
        except ImportError:
            self.logger.warning("[NetworkStorage] SQLAlchemy库未安装，跳过数据库初始化")
            self._db_engine = None
        except Exception as e:
            self.logger.warning(f"[NetworkStorage] 数据库连接失败: {e}")
            self._db_engine = None
    
    async def _create_tables(self):
        """创建数据库表结构"""
        if not self._db_engine:
            return
        
        try:
            import sqlalchemy as sa
            from sqlalchemy.ext.asyncio import AsyncSession
            
            # 定义表结构
            metadata = sa.MetaData()
            
            network_traffic_table = sa.Table(
                'network_traffic',
                metadata,
                sa.Column('id', sa.Integer, primary_key=True),
                sa.Column('request_id', sa.String(255), nullable=False),
                sa.Column('conversation_id', sa.String(255), nullable=False),
                sa.Column('request_url', sa.Text, nullable=False),
                sa.Column('request_method', sa.String(10), nullable=False),
                sa.Column('request_headers', sa.Text),
                sa.Column('request_body', sa.Text),
                sa.Column('response_status', sa.Integer),
                sa.Column('response_headers', sa.Text),
                sa.Column('response_body', sa.Text),
                sa.Column('page_url', sa.Text),
                sa.Column('page_title', sa.Text),
                sa.Column('resource_type', sa.String(50)),
                sa.Column('duration_ms', sa.Float),
                sa.Column('created_at', sa.DateTime, default=sa.func.now()),
                sa.Column('content_hash', sa.String(64)),  # 用于去重
                sa.Index('idx_conversation_id', 'conversation_id'),
                sa.Index('idx_content_hash', 'content_hash'),
                sa.Index('idx_created_at', 'created_at'),
            )
            
            # 创建表
            async with self._db_engine.begin() as conn:
                await conn.run_sync(metadata.create_all)
            
            self.logger.info("[NetworkStorage] 数据库表创建完成")
            
        except Exception as e:
            self.logger.error(f"[NetworkStorage] 创建数据库表失败: {e}")
    
    async def store_traffic_data(self, traffic_capture: NetworkTrafficCapture):
        """存储流量数据到Redis（原始需求4）"""
        if not self._redis_client:
            return
        
        try:
            # 生成内容哈希用于去重
            content_hash = self._generate_content_hash(traffic_capture)
            
            # 检查是否已存在（去重机制）
            if self.config.enable_deduplication:
                exists = await self._redis_client.exists(f"{self.config.redis_key_prefix}:hash:{content_hash}")
                if exists:
                    self.logger.debug(f"[NetworkStorage] 跳过重复流量: {traffic_capture.request.url[:100]}")
                    return
            
            # 存储到Redis
            redis_key = f"{self.config.redis_key_prefix}:traffic:{traffic_capture.conversation_id}:{traffic_capture.request_id}"
            traffic_data = traffic_capture.model_dump()
            
            await self._redis_client.setex(
                redis_key,
                3600 * 24,  # 24小时过期
                json.dumps(traffic_data, ensure_ascii=False)
            )
            
            # 存储哈希标记
            if self.config.enable_deduplication:
                await self._redis_client.setex(
                    f"{self.config.redis_key_prefix}:hash:{content_hash}",
                    3600 * 24,
                    "1"
                )
            
            # 添加到会话列表
            session_key = f"{self.config.redis_key_prefix}:session:{traffic_capture.conversation_id}"
            await self._redis_client.sadd(session_key, traffic_capture.request_id)
            await self._redis_client.expire(session_key, 3600 * 24)
            
            self.logger.debug(f"[NetworkStorage] 流量数据已存储到Redis: {traffic_capture.request.url[:100]}")
            
        except Exception as e:
            self.logger.error(f"[NetworkStorage] 存储到Redis失败: {e}")
    
    async def persist_to_database(self):
        """将Redis中的数据持久化到数据库（原始需求4）"""
        if not self._redis_client or not self._db_engine:
            return
        
        try:
            import sqlalchemy as sa
            from sqlalchemy.ext.asyncio import AsyncSession
            
            # 获取所有会话
            pattern = f"{self.config.redis_key_prefix}:session:*"
            session_keys = await self._redis_client.keys(pattern)
            
            total_records = 0
            
            async with AsyncSession(self._db_engine) as session:
                for session_key in session_keys:
                    conversation_id = session_key.split(':')[-1]
                    
                    # 获取会话中的所有请求ID
                    request_ids = await self._redis_client.smembers(session_key)
                    
                    for request_id in request_ids:
                        traffic_key = f"{self.config.redis_key_prefix}:traffic:{conversation_id}:{request_id}"
                        traffic_data_str = await self._redis_client.get(traffic_key)
                        
                        if not traffic_data_str:
                            continue
                        
                        try:
                            traffic_data = json.loads(traffic_data_str)
                            
                            # 插入数据库
                            insert_stmt = sa.text("""
                                INSERT INTO network_traffic (
                                    request_id, conversation_id, request_url, request_method,
                                    request_headers, request_body, response_status, response_headers,
                                    response_body, page_url, page_title, resource_type,
                                    duration_ms, content_hash
                                ) VALUES (
                                    :request_id, :conversation_id, :request_url, :request_method,
                                    :request_headers, :request_body, :response_status, :response_headers,
                                    :response_body, :page_url, :page_title, :resource_type,
                                    :duration_ms, :content_hash
                                )
                            """)
                            
                            request_data = traffic_data['request']
                            response_data = traffic_data.get('response', {})
                            
                            await session.execute(insert_stmt, {
                                'request_id': traffic_data['request_id'],
                                'conversation_id': traffic_data['conversation_id'],
                                'request_url': request_data['url'],
                                'request_method': request_data['method'],
                                'request_headers': json.dumps(request_data['headers']),
                                'request_body': request_data.get('body'),
                                'response_status': response_data.get('status'),
                                'response_headers': json.dumps(response_data.get('headers', {})),
                                'response_body': response_data.get('body'),
                                'page_url': request_data['page_url'],
                                'page_title': request_data['page_title'],
                                'resource_type': request_data['resource_type'],
                                'duration_ms': traffic_data.get('duration_ms'),
                                'content_hash': self._generate_content_hash_from_dict(traffic_data)
                            })
                            
                            total_records += 1
                            
                        except Exception as e:
                            self.logger.error(f"[NetworkStorage] 处理流量数据失败: {e}")
                
                await session.commit()
            
            self.logger.info(f"[NetworkStorage] 持久化完成，共处理 {total_records} 条记录")
            
            # 清理Redis数据
            await self._cleanup_redis_data()
            
        except Exception as e:
            self.logger.error(f"[NetworkStorage] 持久化到数据库失败: {e}")
    
    async def _cleanup_redis_data(self):
        """清理Redis中的数据"""
        try:
            # 删除所有相关的Redis键
            patterns = [
                f"{self.config.redis_key_prefix}:traffic:*",
                f"{self.config.redis_key_prefix}:session:*",
                f"{self.config.redis_key_prefix}:hash:*"
            ]
            
            for pattern in patterns:
                keys = await self._redis_client.keys(pattern)
                if keys:
                    await self._redis_client.delete(*keys)
            
            self.logger.info("[NetworkStorage] Redis数据清理完成")
            
        except Exception as e:
            self.logger.error(f"[NetworkStorage] Redis数据清理失败: {e}")
    
    def _generate_content_hash(self, traffic_capture: NetworkTrafficCapture) -> str:
        """生成内容哈希用于去重（原始需求4）"""
        # 基于URL、方法和请求体生成哈希
        content = f"{traffic_capture.request.url}|{traffic_capture.request.method}|{traffic_capture.request.body or ''}"
        return hashlib.sha256(content.encode('utf-8')).hexdigest()
    
    def _generate_content_hash_from_dict(self, traffic_data: Dict[str, Any]) -> str:
        """从字典数据生成内容哈希"""
        request_data = traffic_data['request']
        content = f"{request_data['url']}|{request_data['method']}|{request_data.get('body', '') or ''}"
        return hashlib.sha256(content.encode('utf-8')).hexdigest()
    
    async def cleanup(self):
        """清理资源"""
        try:
            if self._redis_client:
                await self._redis_client.close()
            
            if self._db_engine:
                await self._db_engine.dispose()
            
            self.logger.info("[NetworkStorage] 存储管理器清理完成")
            
        except Exception as e:
            self.logger.error(f"[NetworkStorage] 清理过程中出错: {e}")
```

## 7. Watchdog注册集成

### 7.1 修改session.py

#### 文件位置：`browser_use/browser/session.py`（修改现有文件）

```python
# network capture feature code
# 在attach_all_watchdogs方法中添加NetworkCaptureWatchdog

def attach_all_watchdogs(self) -> None:
    """附加所有watchdog到会话"""
    from browser_use.browser.watchdogs.dom_watchdog import DOMWatchdog
    from browser_use.browser.watchdogs.default_action_watchdog import DefaultActionWatchdog
    from browser_use.browser.watchdogs.downloads_watchdog import DownloadsWatchdog
    # network capture feature code
    from browser_use.browser.watchdogs.network_capture_watchdog import NetworkCaptureWatchdog
    
    watchdogs = [
        DOMWatchdog(),
        DefaultActionWatchdog(),
        DownloadsWatchdog(),
        # network capture feature code
        NetworkCaptureWatchdog(),
    ]
    
    for watchdog in watchdogs:
        watchdog.attach_to_session(self)
```

## 8. 依赖管理

### 8.1 pyproject.toml更新

#### 文件位置：`pyproject.toml`（修改现有文件）

```toml
# network capture feature code
# 在dependencies中添加网络捕获相关依赖

[project]
dependencies = [
    # ... 现有依赖 ...
    # network capture feature code
    "redis[hiredis]>=4.5.0",  # Redis客户端
    "sqlalchemy[asyncio]>=2.0.0",  # 异步SQLAlchemy
    "aiosqlite>=0.19.0",  # SQLite异步驱动
]

[project.optional-dependencies]
# network capture feature code
network-capture = [
    "redis[hiredis]>=4.5.0",
    "sqlalchemy[asyncio]>=2.0.0",
    "aiosqlite>=0.19.0",
    "asyncpg>=0.28.0",  # PostgreSQL异步驱动（可选）
]
```

## 9. 使用示例

### 9.1 基本使用

```python
"""网络捕获使用示例"""

from browser_use import Agent, BrowserProfile, NetworkCaptureConfig
from langchain_openai import ChatOpenAI

# 配置网络捕获
network_config = NetworkCaptureConfig(
    enabled=True,
    allowed_domains=['example.com', 'api.example.com'],
    blocked_file_extensions=['.jpg', '.png', '.css'],
    max_response_body_size=5 * 1024 * 1024,  # 5MB
    enable_deduplication=True
)

# 创建浏览器配置
browser_profile = BrowserProfile(
    headless=False,
    network_capture=network_config
)

# 创建Agent
agent = Agent(
    task="访问example.com并提交表单",
    llm=ChatOpenAI(model="gpt-4"),
    browser_profile=browser_profile
)

# 运行Agent（网络流量将自动捕获）
result = await agent.arun()
```

### 9.2 监听网络捕获事件

```python
"""监听网络捕获事件的示例"""

from browser_use.browser.network_events import NetworkTrafficCapturedEvent

class CustomNetworkWatchdog(BaseWatchdog):
    LISTENS_TO = [NetworkTrafficCapturedEvent]
    
    async def on_NetworkTrafficCapturedEvent(self, event: NetworkTrafficCapturedEvent) -> None:
        """处理网络流量捕获事件"""
        traffic = event.traffic_data
        
        print(f"捕获到网络流量:")
        print(f"  URL: {traffic.request.url}")
        print(f"  方法: {traffic.request.method}")
        print(f"  状态: {traffic.response.status if traffic.response else 'N/A'}")
        print(f"  页面: {traffic.request.page_title}")
        print(f"  会话ID: {traffic.conversation_id}")
        
        # 可以进行自定义处理，如发送到外部系统
        if event.should_store:
            await self.send_to_external_system(traffic)
    
    async def send_to_external_system(self, traffic_data):
        """发送到外部系统的示例"""
        # 实现自定义逻辑
        pass
```

## 10. 总结

### 10.1 优化成果

本v6设计方案相比v5版本实现了以下关键优化：

1. **深度集成Browser-Use架构**：
   - 完全基于现有的事件机制和Watchdog模式
   - 直接利用Agent.id作为conversation_id
   - 遵循Browser-Use的CDP最佳实践

2. **简化事件模型**：
   - 减少事件类型，专注核心需求
   - 统一的NetworkTrafficCapturedEvent事件
   - 避免过度设计，提高性能

3. **优化配置集成**：
   - 完全集成到BrowserProfile配置体系
   - 支持环境变量配置
   - 遵循Browser-Use的配置模式

4. **智能存储策略**：
   - 基于内容哈希的去重机制
   - Redis缓存 + 数据库持久化
   - 支持大小限制和截断

5. **完整生命周期管理**：
   - 与Agent和BrowserSession生命周期同步
   - 自动资源清理和数据持久化
   - 错误处理和恢复机制

### 10.2 原始需求满足度

| 原始需求 | 实现状态 | 说明 |
|---------|---------|------|
| 1. 流量捕获和过滤 | ✅ 完全实现 | 支持域名、文件类型过滤 |
| 2. 页面关联信息 | ✅ 完全实现 | 捕获页面URL、标题等信息 |
| 3. 完整请求/响应 | ✅ 完全实现 | 成对捕获所有必需字段 |
| 4. 智能存储 | ✅ 完全实现 | Redis缓存+数据库持久化+去重 |
| 5. 大小控制 | ✅ 完全实现 | 支持响应体大小限制和截断 |
| 6. 会话标识 | ✅ 完全实现 | 基于Agent.id的conversation_id |

### 10.3 架构优势

1. **无缝集成**：完全融入Browser-Use现有体系，无需额外配置
2. **高性能**：简化的事件模型和智能去重机制
3. **高可靠性**：遵循Browser-Use的最佳实践，确保稳定性
4. **易扩展**：基于事件驱动架构，支持自定义扩展
5. **易维护**：清晰的代码结构和完整的错误处理

本方案严格遵循原始需求，充分利用Browser-Use现有能力，实现了高效、稳定、易用的网络流量捕获功能。