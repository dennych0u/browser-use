"""
mitmproxy addon for API request/response deduplication and persistent storage
用于API请求/响应去重和持久化存储的mitmproxy插件

Usage:
    mitmproxy -s api_storage_addon.py --set api_db_path=./api_data.db
"""

import hashlib
import json
import logging
import sqlite3
import time
from datetime import datetime
from typing import Optional, Set
from urllib.parse import urlparse, parse_qs

# 新增导入：相似度计算
import difflib

from mitmproxy import ctx, flowfilter, http
from mitmproxy.addonmanager import Loader

logger = logging.getLogger(__name__)


class APIStorageAddon:
    """API数据存储插件"""
    
    def __init__(self):
        self.db_path: Optional[str] = None
        self.filter: Optional[flowfilter.TFilter] = None
        self.conn: Optional[sqlite3.Connection] = None
        
        # 静态资源文件扩展名
        self.static_extensions: Set[str] = {
            # 图片文件
            'jpg', 'jpeg', 'png', 'gif', 'bmp', 'webp', 'svg', 'ico', 'tiff', 'tif',
            # 样式和脚本文件
            'css', 'js', 'jsx', 'ts', 'tsx', 'scss', 'sass', 'less',
            # 字体文件
            'woff', 'woff2', 'ttf', 'eot', 'otf',
            # 音视频文件
            'mp3', 'mp4', 'avi', 'mov', 'wmv', 'flv', 'webm', 'ogg', 'wav',
            # 文档文件
            'pdf', 'doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx',
            # 压缩文件
            'zip', 'rar', '7z', 'tar', 'gz', 'bz2',
            # 其他静态资源
            # 'xml', 'txt', 'csv', 'log', 'map', 'manifest'
        }
        
        # 静态资源Content-Type
        self.static_content_types: Set[str] = {
            # 图片类型
            'image/jpeg', 'image/png', 'image/gif', 'image/bmp', 'image/webp', 
            'image/svg+xml', 'image/x-icon', 'image/tiff',
            # 样式和脚本类型
            'text/css', 'text/javascript', 'application/javascript', 
            'application/x-javascript', 'text/ecmascript', 'application/ecmascript',
            # 字体类型
            'font/woff', 'font/woff2', 'font/ttf', 'font/eot', 'font/otf',
            'application/font-woff', 'application/font-woff2', 'application/x-font-ttf',
            # 音视频类型
            'audio/mpeg', 'audio/wav', 'audio/ogg', 'video/mp4', 'video/avi', 
            'video/quicktime', 'video/x-msvideo', 'video/webm',
            # 文档类型
            'application/pdf', 'application/msword', 'application/vnd.ms-excel',
            'application/vnd.ms-powerpoint', 'application/vnd.openxmlformats-officedocument',
            # 压缩文件类型
            'application/zip', 'application/x-rar-compressed', 'application/x-7z-compressed',
            'application/x-tar', 'application/gzip',
            # 其他静态资源类型
            # 'text/xml', 'application/xml', 'text/plain', 'text/csv'
        }
        
    def load(self, loader: Loader):
        """加载插件配置选项"""
        loader.add_option(
            name="api_db_path",
            typespec=str,
            default="./api_data.db",
            help="API数据存储的数据库文件路径"
        )
        
        loader.add_option(
            name="api_filter",
            typespec=str,
            default="",  # 移除默认的URL过滤，改用自定义过滤逻辑
            help="API请求过滤规则，排除静态资源"
        )
        
        loader.add_option(
            name="enable_deduplication",
            typespec=bool,
            default=True,
            help="是否启用请求去重功能"
        )
        # 新增：相似度去重相关配置
        loader.add_option(
            name="enable_similarity_dedup",
            typespec=bool,
            default=True,
            help="是否启用基于host+path+query_params相似度的去重检查"
        )
        loader.add_option(
            name="similarity_threshold",
            typespec=str,
            default="0.8",
            help="相似度阈值(0-1)，当相似度≥该值时认为是重复API"
        )
        loader.add_option(
            name="similarity_window_seconds",
            typespec=int,
            default=600,
            help="进行相似度去重时的时间窗口(秒)，仅在此窗口内的历史记录参与比较"
        )

    def configure(self, updated):
        """配置更新时的处理"""
        if "api_db_path" in updated:
            self.db_path = ctx.options.api_db_path
            self._init_database()
            
        if "api_filter" in updated:
            filter_expr = ctx.options.api_filter.strip()
            if filter_expr:  # 只有当过滤规则不为空时才解析
                try:
                    self.filter = flowfilter.parse(filter_expr)
                    logger.info(f"API过滤规则已设置: {filter_expr}")
                except Exception as e:
                    logger.error(f"API过滤规则解析失败: {e}")
                    self.filter = None
            else:
                self.filter = None
                logger.info("使用自定义静态资源过滤逻辑")

    def _init_database(self):
        """初始化数据库连接和表结构"""
        try:
            if self.conn:
                self.conn.close()
                
            self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
            self.conn.execute('''
                CREATE TABLE IF NOT EXISTS api_requests (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    request_hash TEXT UNIQUE,
                    timestamp REAL,
                    method TEXT,
                    url TEXT,
                    host TEXT,
                    path TEXT,
                    query_params TEXT,
                    headers TEXT,
                    request_body TEXT,
                    response_status INTEGER,
                    response_headers TEXT,
                    response_body TEXT,
                    response_time REAL,
                    client_ip TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # 创建索引提高查询性能
            self.conn.execute('CREATE INDEX IF NOT EXISTS idx_request_hash ON api_requests(request_hash)')
            self.conn.execute('CREATE INDEX IF NOT EXISTS idx_timestamp ON api_requests(timestamp)')
            self.conn.execute('CREATE INDEX IF NOT EXISTS idx_host ON api_requests(host)')
            
            self.conn.commit()
            logger.info(f"数据库初始化完成: {self.db_path}")
            
        except Exception as e:
            logger.error(f"数据库初始化失败: {e}")

    def _generate_request_hash(self, flow: http.HTTPFlow) -> str:
        """生成请求的唯一哈希值用于去重"""
        # 构建用于哈希的字符串
        hash_components = [
            flow.request.method,
            flow.request.pretty_url,
            # 对查询参数进行排序以确保一致性
            json.dumps(dict(flow.request.query), sort_keys=True),
        ]
        
        # 如果是POST/PUT请求，包含请求体
        if flow.request.method in ['POST', 'PUT', 'PATCH'] and flow.request.content:
            try:
                # 尝试解析JSON并排序
                if flow.request.headers.get('content-type', '').startswith('application/json'):
                    json_data = json.loads(flow.request.content.decode('utf-8', errors='ignore'))
                    hash_components.append(json.dumps(json_data, sort_keys=True))
                else:
                    hash_components.append(flow.request.content.decode('utf-8', errors='ignore'))
            except:
                hash_components.append(flow.request.content.decode('utf-8', errors='ignore'))
        
        hash_string = '|'.join(hash_components)
        return hashlib.md5(hash_string.encode('utf-8')).hexdigest()

    def _is_duplicate(self, request_hash: str) -> bool:
        """检查请求是否重复"""
        if not ctx.options.enable_deduplication or not self.conn:
            return False
            
        try:
            cursor = self.conn.execute(
                'SELECT COUNT(*) FROM api_requests WHERE request_hash = ?',
                (request_hash,)
            )
            count = cursor.fetchone()[0]
            if count > 0:
                # logger.info(f"[重复请求-精确匹配] 哈希: {request_hash[:16]}...")
                return True
            else:
                # logger.info(f"[非重复请求-精确匹配] 哈希: {request_hash[:16]}...")
                return False
        except Exception as e:
            logger.error(f"去重检查失败: {e}")
            return False

    def _store_api_data(self, flow: http.HTTPFlow, request_hash: str):
        """存储API数据到数据库"""
        if not self.conn:
            return
            
        try:
            parsed_url = urlparse(flow.request.pretty_url)
            
            # 准备数据
            data = {
                'request_hash': request_hash,
                'timestamp': flow.timestamp_start,
                'method': flow.request.method,
                'url': flow.request.pretty_url,
                'host': flow.request.pretty_host,
                'path': parsed_url.path,
                'query_params': json.dumps(dict(flow.request.query)),
                'headers': json.dumps(dict(flow.request.headers)),
                'request_body': flow.request.content.decode('utf-8', errors='ignore') if flow.request.content else '',
                'response_status': flow.response.status_code if flow.response else None,
                'response_headers': json.dumps(dict(flow.response.headers)) if flow.response else '',
                'response_body': flow.response.content.decode('utf-8', errors='ignore') if flow.response and flow.response.content else '',
                'response_time': (time.time() - flow.timestamp_start) if flow.response else None,
                'client_ip': flow.client_conn.peername[0] if flow.client_conn.peername else ''
            }
            
            # 插入数据
            self.conn.execute('''
                INSERT OR IGNORE INTO api_requests 
                (request_hash, timestamp, method, url, host, path, query_params, 
                 headers, request_body, response_status, response_headers, 
                 response_body, response_time, client_ip)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                data['request_hash'], data['timestamp'], data['method'], 
                data['url'], data['host'], data['path'], data['query_params'],
                data['headers'], data['request_body'], data['response_status'],
                data['response_headers'], data['response_body'], 
                data['response_time'], data['client_ip']
            ))
            
            self.conn.commit()
            logger.info(f"API数据已存储: {flow.request.method} {flow.request.pretty_url}")
            
        except Exception as e:
            logger.error(f"存储API数据失败: {e}")

    def _is_static_resource(self, flow: http.HTTPFlow) -> bool:
        """
        判断请求是否为静态资源
        
        Args:
            flow: HTTP流对象
            
        Returns:
            bool: 如果是静态资源返回True，否则返回False
        """
        url = flow.request.pretty_url
        method = flow.request.method
        
        # 1. 检查URL路径扩展名
        parsed_url = urlparse(flow.request.pretty_url)
        path = parsed_url.path.lower()
        
        # 提取文件扩展名（忽略查询参数）
        if '.' in path:
            # 获取路径的最后一部分（文件名）
            filename = path.split('/')[-1]
            if '.' in filename:
                extension = filename.split('.')[-1]
                if extension in self.static_extensions:
                    # logger.info(f"[静态资源-扩展名] {method} {url} - 扩展名: {extension}")
                    return True
        
        # 2. 检查响应Content-Type
        if flow.response and flow.response.headers:
            content_type = flow.response.headers.get('content-type', '').lower()
            # 移除charset等参数
            content_type = content_type.split(';')[0].strip()
            
            # 明确排除HTML页面，确保不被误过滤
            if content_type in ['text/html', 'application/xhtml+xml']:
                # logger.info(f"[非静态资源-HTML] {method} {url} - Content-Type: {content_type}")
                return False
            
            if content_type in self.static_content_types:
                # logger.info(f"[静态资源-Content-Type] {method} {url} - Content-Type: {content_type}")
                return True
            
            # 检查是否以静态资源类型开头
            for static_type in self.static_content_types:
                if content_type.startswith(static_type):
                    # logger.info(f"[静态资源-Content-Type前缀] {method} {url} - Content-Type: {content_type} (匹配: {static_type})")
                    return True
        
        # 3. 检查常见的静态资源路径模式
        static_path_patterns = [
            '/static/', '/assets/', '/public/', '/dist/', '/build/',
            '/css/', '/js/', '/img/', '/images/', '/fonts/', '/media/'
        ]
        
        for pattern in static_path_patterns:
            if pattern in path:
                # logger.info(f"[静态资源-路径模式] {method} {url} - 匹配模式: {pattern}")
                return True
        
        # logger.info(f"[非静态资源] {method} {url} - 未匹配任何静态资源规则")
        return False

    def _compose_signature(self, flow: http.HTTPFlow) -> str:
        """组合host+path+query_params形成签名字符串，用于相似度去重计算"""
        parsed_url = urlparse(flow.request.pretty_url)
        host = parsed_url.netloc
        path = parsed_url.path
        
        # 通用的查询参数处理：过滤掉常见的高变化参数以提高相似度
        query_params = dict(flow.request.query)
        filtered_params = {}
        
        # 定义通用的高变化参数模式（不针对特定网站）
        exclude_patterns = {
            # 时间戳相关
            'timestamp', 'ts', 't', '_t', 'time', '_time', 'cache_buster', 'cb', 
            'r', 'rnd', 'random', '_', '__', 'v', 'ver', 'version',
            # 会话和跟踪相关
            'session', 'sid', 'ssid', 'uid', 'user_id', 'token', 'csrf',
            # 缓存和调试相关  
            'debug', 'nocache', 'bust', '_bust', 'reload'
        }
        
        for key, value in query_params.items():
            key_lower = key.lower()
            # 检查是否为高变化参数
            should_exclude = False
            
            # 完全匹配排除列表
            if key_lower in exclude_patterns:
                should_exclude = True
            # 检查是否以时间戳模式开头或结尾
            elif any(pattern in key_lower for pattern in ['timestamp', '_time', 'time_']):
                should_exclude = True
            # 检查是否为纯数字（可能是时间戳）
            elif isinstance(value, str) and value.isdigit() and len(value) >= 10:
                should_exclude = True
            
            if not should_exclude:
                # 对于URL类型的参数，规范化为域名部分以减少路径差异
                if key_lower in ['url', 'page_url', 'ref', 'referer', 'redirect'] and isinstance(value, str):
                    try:
                        if value.startswith(('http://', 'https://')):
                            from urllib.parse import urlparse as parse_param_url
                            parsed_param = parse_param_url(value)
                            filtered_params[key] = f"{parsed_param.scheme}://{parsed_param.netloc}"
                        else:
                            filtered_params[key] = value
                    except:
                        filtered_params[key] = value
                else:
                    filtered_params[key] = value
        
        # 规范化查询参数为排序后的JSON，避免键顺序导致的差异
        try:
            query_json = json.dumps(filtered_params, sort_keys=True)
        except Exception:
            query_json = json.dumps({})
        
        signature = f"{host}|{path}|{query_json}"
        return signature

    def _similarity_ratio(self, a: str, b: str) -> float:
        """计算两个签名字符串的相似度(0-1)，增加路径权重"""
        try:
            # 解析签名字符串：host|path|query_params
            parts_a = a.split('|', 2)
            parts_b = b.split('|', 2)
            
            if len(parts_a) != 3 or len(parts_b) != 3:
                # 如果格式不正确，回退到简单比较
                return difflib.SequenceMatcher(None, a, b).ratio()
            
            host_a, path_a, query_a = parts_a
            host_b, path_b, query_b = parts_b
            
            # 如果路径完全不同，直接返回0（不相似）
            if path_a != path_b:
                return 0.0
            
            # 如果路径相同，计算host和query的相似度
            host_similarity = difflib.SequenceMatcher(None, host_a, host_b).ratio()
            query_similarity = difflib.SequenceMatcher(None, query_a, query_b).ratio()
            
            # 权重分配：路径权重最高，host次之，query最低
            # 由于路径已经相同，主要比较host和query
            # host权重0.3，query权重0.7
            final_similarity = host_similarity * 0.3 + query_similarity * 0.7
            
            return final_similarity
            
        except Exception:
            return 0.0

    def _is_similar_duplicate(self, flow: http.HTTPFlow) -> bool:
        """基于host+path+query_params的相似度去重判断
        当查到最近时间窗口内存在与当前请求签名相似度≥阈值的记录时，认为重复，不进行存储
        """
        # 基本检查
        if not ctx.options.enable_deduplication or not ctx.options.enable_similarity_dedup:
            return False
        if not self.conn:
            return False
        
        # 获取请求信息用于日志
        url = flow.request.pretty_url
        method = flow.request.method
        
        # 计算当前签名与查询范围
        now_ts = flow.timestamp_start or time.time()
        window_seconds = getattr(ctx.options, 'similarity_window_seconds', 600)
        threshold_str = getattr(ctx.options, 'similarity_threshold', '0.8')
        try:
            threshold = float(threshold_str)
        except (ValueError, TypeError):
            threshold = 0.8
        signature = self._compose_signature(flow)
        
        # 仅比较同一host，且限定时间窗口，降低开销
        parsed_url = urlparse(flow.request.pretty_url)
        host = parsed_url.netloc
        window_start = now_ts - window_seconds
        try:
            # 选取时间窗口内同一host的最近若干条记录参与比较
            cursor = self.conn.execute(
                'SELECT host, path, query_params FROM api_requests WHERE host = ? AND timestamp >= ? ORDER BY timestamp DESC LIMIT 200',
                (host, window_start)
            )
            rows = cursor.fetchall()
            for row in rows:
                h, p, q = row
                # 将数据库中的query_params规范化为排序后的JSON，保证一致性
                try:
                    q_dict = json.loads(q) if q else {}
                except Exception:
                    q_dict = {}
                other_sig = f"{h}|{p}|{json.dumps(q_dict, sort_keys=True)}"
                similarity = self._similarity_ratio(signature, other_sig)
                if similarity >= threshold:
                    logger.info(f"[重复请求-相似匹配] {method} {url} - 相似度: {similarity:.3f} (阈值: {threshold})")
                    return True
        except Exception as e:
            logger.error(f"相似度去重检查失败: {e}")
            return False
        
        logger.info(f"[非重复请求-相似匹配] {method} {url} - 未找到相似请求")
        return False

    def response(self, flow: http.HTTPFlow):
        """处理HTTP响应"""
        url = flow.request.pretty_url
        method = flow.request.method
        
        logger.info(f"[API分析] 开始处理请求: {method} {url}")
        
        # 首先检查是否为静态资源
        if self._is_static_resource(flow):
            # logger.info(f"[过滤-静态资源] {method} {url}")
            return
        
        # logger.info(f"[通过-非静态资源] {method} {url}")
        
        # 检查是否匹配过滤规则（如果有自定义规则）
        if self.filter and not flowfilter.match(self.filter, flow):
            logger.info(f"[过滤-自定义规则] {method} {url} - 不匹配过滤规则: {ctx.options.api_filter}")
            return
            
        if self.filter:
            logger.info(f"[通过-自定义规则] {method} {url}")
        else:
            logger.info(f"[通过-无自定义规则] {method} {url}")
            
        # 生成请求哈希
        request_hash = self._generate_request_hash(flow)
        # logger.info(f"[哈希生成] {method} {url} - 哈希: {request_hash[:16]}...")
        
        # 先做严格去重(哈希)
        if self._is_duplicate(request_hash):
            # logger.info(f"[过滤-哈希重复] {method} {url} - 哈希: {request_hash[:16]}...")
            return
        
        # logger.info(f"[通过-哈希唯一] {method} {url}")
        
        # 再做相似度去重(基于host+path+query_params)
        if self._is_similar_duplicate(flow):
            logger.info(f"[过滤-相似度重复] {method} {url}")
            return
            
        logger.info(f"[通过-相似度唯一] {method} {url}")
        
        # 存储API数据
        logger.info(f"[存储API] {method} {url}")
        self._store_api_data(flow, request_hash)

    def done(self):
        """插件卸载时的清理工作"""
        if self.conn:
            self.conn.close()
            logger.info("数据库连接已关闭")


# 注册插件
addons = [APIStorageAddon()]