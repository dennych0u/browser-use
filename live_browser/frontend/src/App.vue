<template>
  <div id="app">
    <!-- 顶部导航栏 -->
    <el-header class="header">
      <div class="header-content">
        <div class="logo-section">
          <el-icon class="logo-icon"><Monitor /></el-icon>
          <span class="logo-text">Browser-Use 实时控制台</span>
        </div>
        <div class="nav-section">
          <el-button type="primary" @click="showNewJobDialog = true">
            <el-icon><Plus /></el-icon>
            新建任务
          </el-button>
        </div>
      </div>
    </el-header>

    <!-- 主体内容 -->
    <el-container class="main-container">
      <!-- 左侧边栏 -->
      <el-aside class="sidebar" width="320px">
        <div class="sidebar-content">
          <!-- 连接状态 -->
          <div class="connection-status">
            <h3>连接状态</h3>
            <div class="status-indicator" :class="connectionStatus">
              <el-icon><Connection /></el-icon>
              <span>{{ connectionStatus === 'connected' ? '已连接' : '未连接' }}</span>
            </div>
          </div>

          <!-- 会话控制 -->
          <div class="session-controls">
            <h3>会话控制</h3>
            <div class="control-buttons">
              <el-button 
                type="primary" 
                @click="openBrowserSession"
                :disabled="sessionStatus === 'running'"
                size="small"
                style="width: auto; margin-bottom: 8px; margin-right: 8px;"
              >
                <el-icon><VideoPlay /></el-icon>
                启动浏览器
              </el-button>
              <el-button 
                 type="danger" 
                 @click="stopBrowserSession"
                 :disabled="sessionStatus !== 'running'"
                 size="small"
                 style="width: auto; margin-bottom: 8px; margin-right: 8px;"
               >
                 <el-icon><VideoPause /></el-icon>
                 停止浏览器
               </el-button>
              <el-button 
                @click="refreshSession"
                size="small"
                style="width: auto;"
              >
                <el-icon><Refresh /></el-icon>
                刷新状态
              </el-button>
            </div>
          </div>

          <!-- 实时屏幕状态 -->
          <div class="screen-status" v-if="realtimeScreenEnabled">
            <h3>屏幕状态</h3>
            <div class="status-info">
              <div class="status-item">
                <span>帧率:</span>
                <el-tag size="small">{{ screenStatus.frame_rate }}fps</el-tag>
              </div>
              <div class="status-item">
                <span>质量:</span>
                <el-tag size="small">{{ screenStatus.quality }}%</el-tag>
              </div>
              <div class="status-item">
                <span>分辨率:</span>
                <el-tag size="small">{{ screenStatus.max_width }}x{{ screenStatus.max_height }}</el-tag>
              </div>
            </div>
          </div>

          <!-- 活动日志 -->
          <div class="activity-log">
            <h3>活动日志</h3>
            <div class="log-container" ref="logContainer">
              <div 
                v-for="(log, index) in activityLogs" 
                :key="index" 
                class="log-item" 
                :class="log.type"
              >
                <span class="log-time">{{ formatTime(log.time) }}</span>
                <span class="log-source">[{{ log.source }}]</span>
                <span class="log-message">{{ log.message }}</span>
              </div>
            </div>
          </div>

          <!-- 历史记录选择 -->
          <div class="history-section">
            <h3>历史记录</h3>
            <el-select v-model="selectedHistory" class="history-select" size="small">
              <el-option label="全部记录" value="all"></el-option>
              <el-option label="成功记录" value="success"></el-option>
              <el-option label="错误记录" value="error"></el-option>
            </el-select>
          </div>

          <!-- 用户信息 -->
          <div class="user-section">
            <div class="user-info">
              <el-icon><User /></el-icon>
              <span class="username">{{ userInfo.name }}</span>
            </div>
          </div>
        </div>
      </el-aside>

      <!-- 主内容区域 - 浏览器主窗口 -->
      <el-main class="main-content">
        <!-- 浏览器主窗口 -->
        <div class="browser-main-window">
          <!-- 浏览器工具栏 -->
          <div class="browser-toolbar">
            <div class="browser-controls">
              <div class="control-button close"></div>
              <div class="control-button minimize"></div>
              <div class="control-button maximize"></div>
            </div>
            <div class="address-bar">
              <el-input 
                v-model="currentUrl" 
                placeholder="输入网站地址..."
                size="small"
                @keyup.enter="navigateToUrl"
              >
                <template #prepend>
                  <el-icon><Link /></el-icon>
                </template>
                <template #append>
                  <el-button @click="navigateToUrl" size="small" type="primary">
                    前往
                  </el-button>
                </template>
              </el-input>
            </div>
            <div class="toolbar-actions">
              <el-button 
                @click="takeScreenshot" 
                :disabled="!realtimeScreenEnabled" 
                size="small"
              >
                <el-icon><Camera /></el-icon>
                截图
              </el-button>
            </div>
          </div>

          <!-- 浏览器内容区域 -->
          <div class="browser-content-main">
            <!-- 分割布局：左侧实时屏幕，右侧API数据 -->
            <div class="content-split-layout">
              <!-- 左侧：实时屏幕显示 -->
              <div class="screen-section">
                <div v-if="realtimeScreenEnabled && currentScreenFrame" class="realtime-screen">
                  <img 
                    :src="'data:image/jpeg;base64,' + currentScreenFrame" 
                    alt="实时屏幕"
                    class="screen-image"
                  />
                  <div class="screen-overlay">
                    <div class="recording-indicator">
                      <el-icon class="recording-icon"><VideoCamera /></el-icon>
                      <span>实时录制中</span>
                    </div>
                  </div>
                </div>

                <!-- 默认占位符 -->
                <div v-else class="browser-placeholder">
                  <el-icon class="placeholder-icon"><Monitor /></el-icon>
                  <p>{{ sessionStatus === 'running' ? '等待屏幕数据...' : '点击"启动浏览器"开始会话' }}</p>
                </div>
              </div>

              <!-- 右侧：API数据展示 -->
              <div class="api-section">
                <div class="api-header">
                  <h3>捕获的API请求</h3>
                  <div class="api-stats">
                    <span>总计: {{ capturedApis.length }}</span>
                    <el-button 
                      size="small" 
                      @click="refreshApiData"
                      :loading="apiLoading"
                    >
                      刷新
                    </el-button>
                  </div>
                </div>
                
                <div class="api-list" ref="apiListContainer">
                  <div 
                    v-for="api in capturedApis" 
                    :key="api.id"
                    class="api-item"
                    :class="getApiStatusClass(api.status)"
                  >
                    <div class="api-method">{{ api.method }}</div>
                    <div class="api-url" :title="api.url">{{ api.path || api.url }}</div>
                    <div class="api-status">{{ api.status || 'N/A' }}</div>
                    <div class="api-time">{{ formatApiTime(api.timestamp) }}</div>
                  </div>
                  
                  <div v-if="capturedApis.length === 0" class="api-empty">
                    <el-icon><Document /></el-icon>
                    <p>暂无捕获的API请求</p>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </el-main>
    </el-container>

    <!-- 新建任务对话框 -->
    <el-dialog v-model="showNewJobDialog" title="新建浏览器任务" width="600px">
      <el-form :model="newJobForm" label-width="120px">
        <el-form-item label="网站URL">
          <el-input v-model="newJobForm.websiteUrl" placeholder="https://example.com"></el-input>
        </el-form-item>
        <el-form-item label="任务描述">
          <el-input 
            v-model="newJobForm.taskDescription" 
            type="textarea" 
            :rows="4"
            placeholder="描述要执行的任务..."
          ></el-input>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showNewJobDialog = false">取消</el-button>
        <el-button type="primary" @click="createNewJob">创建任务</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script>
import { ref, reactive, onMounted, onUnmounted, nextTick } from 'vue'
import { io } from 'socket.io-client'
import axios from 'axios'
import { 
  Monitor, Plus, Connection, VideoPlay, VideoPause, Refresh, 
  User, Link, Camera, VideoCamera, Loading, Document 
} from '@element-plus/icons-vue'

export default {
  name: 'App',
  components: {
    Monitor, Plus, Connection, VideoPlay, VideoPause, Refresh,
    User, Link, Camera, VideoCamera, Loading, Document
  },
  setup() {
    // 响应式数据
    const sessionStatus = ref('idle')
    const connectionStatus = ref('disconnected')
    const currentUrl = ref('https://xiaozihealth.com/')
    const isRecording = ref(false)
    const taskProgress = ref(0)
    const progressText = ref('等待开始...')
    const activityLogs = ref([])
    const selectedHistory = ref('all')
    const showNewJobDialog = ref(false)
    const logContainer = ref(null)

    // 实时屏幕相关数据
    const realtimeScreenEnabled = ref(false)
    const currentScreenFrame = ref(null)
    const screenStatus = reactive({
      is_recording: false,
      frame_rate: 0,
      quality: 0,
      max_width: 0,
      max_height: 0,
      active_sessions: 0,
      last_frame_time: 0
    })

    // API数据相关
    const capturedApis = ref([])
    const apiLoading = ref(false)

    // 用户信息
    const userInfo = reactive({
      name: 'Browser User',
      avatar: '/api/placeholder/32/32'
    })

    // 任务列表
    const jobs = ref([
      { id: 1, name: 'Manual Jobs Search', url: 'https://xiaozihealth.com/' },
      { id: 2, name: 'Google Search', url: 'https://google.com' }
    ])

    // 新任务表单
    const newJobForm = reactive({
      websiteUrl: '',
      taskDescription: ''
    })

    // WebSocket连接
    let socket = null
    const API_BASE_URL = 'http://localhost:5000'

    // 初始化WebSocket连接
    const initSocket = () => {
      socket = io(API_BASE_URL)
      
      socket.on('connect', () => {
        connectionStatus.value = 'connected'
        addLog('系统', '已连接到服务器', 'success')
      })
      
      socket.on('disconnect', () => {
        connectionStatus.value = 'disconnected'
        addLog('系统', '与服务器断开连接', 'error')
      })
      
      socket.on('session_started', (data) => {
        sessionStatus.value = 'running'
        isRecording.value = true
        taskProgress.value = 0
        progressText.value = '任务开始执行...'
        realtimeScreenEnabled.value = true
        addLog('Agent', data.message, 'info')
        
        // 获取实时屏幕状态
        fetchScreenStatus()
      })
      
      socket.on('agent_step', (data) => {
        console.log('Agent step received:', JSON.stringify(data, null, 2))
        // 移除硬编码的15步限制，使用动态进度计算
        const maxSteps = data.max_steps || 100  // 使用后端传递的max_steps，默认100
        taskProgress.value = Math.min((data.step / maxSteps) * 100, 100)
        progressText.value = `执行步骤 ${data.step}/${maxSteps}`
        
        // 处理action对象，提取可读的任务描述
        let actionText = '执行中...'
        if (data.action && typeof data.action === 'object') {
          console.log('Action type:', data.action.action_type)
          console.log('Action data:', data.action.action_data)
          
          const actionType = data.action.action_type || 'unknown'
          const actionData = data.action.action_data || {}
          
          // 如果是ActionModel，需要从action_data中提取具体操作
          if (actionType === 'ActionModel' && typeof actionData === 'object') {
            // 检查action_data中的具体操作类型
            if (actionData.click) {
              const clickData = actionData.click
              actionText = `点击元素: ${clickData.coordinate ? `坐标(${clickData.coordinate[0]}, ${clickData.coordinate[1]})` : '未知位置'}`
            } else if (actionData.type) {
              actionText = `输入文本: "${actionData.type.text || '未知内容'}"`
            } else if (actionData.scroll) {
              actionText = `滚动页面: ${actionData.scroll.direction || '未知方向'}`
            } else if (actionData.navigate) {
              actionText = `导航到: ${actionData.navigate.url || '未知地址'}`
            } else if (actionData.wait) {
              actionText = `等待: ${actionData.wait.seconds || '未知时间'}秒`
            } else if (actionData.screenshot) {
              actionText = '截取屏幕截图'
            } else if (actionData.extract) {
              actionText = '提取页面信息'
            } else if (actionData.go_back) {
              actionText = '返回上一页'
            } else if (actionData.refresh) {
              actionText = '刷新页面'
            } else if (actionData.write_file) {
              const writeData = actionData.write_file
              actionText = `写入文件: ${writeData.file_name || '未知文件'}`
            } else if (actionData.read_file) {
              const readData = actionData.read_file
              actionText = `读取文件: ${readData.file_name || '未知文件'}`
            } else {
              // 尝试从第一个键值对中提取操作类型
              const firstKey = Object.keys(actionData)[0]
              if (firstKey) {
                actionText = `执行${firstKey}操作`
              } else {
                actionText = '执行未知操作'
              }
            }
          } else {
            // 处理其他类型的action
            switch (actionType) {
              case 'ClickAction':
                actionText = `点击元素: ${actionData.coordinate ? `坐标(${actionData.coordinate[0]}, ${actionData.coordinate[1]})` : '未知位置'}`
                break
              case 'TypeAction':
                actionText = `输入文本: "${actionData.text || '未知内容'}"`
                break
              case 'ScrollAction':
                actionText = `滚动页面: ${actionData.direction || '未知方向'}`
                break
              case 'NavigateAction':
                actionText = `导航到: ${actionData.url || '未知地址'}`
                break
              case 'WaitAction':
                actionText = `等待: ${actionData.seconds || '未知时间'}秒`
                break
              case 'ScreenshotAction':
                actionText = '截取屏幕截图'
                break
              case 'ExtractAction':
                actionText = '提取页面信息'
                break
              case 'GoBackAction':
                actionText = '返回上一页'
                break
              case 'RefreshAction':
                actionText = '刷新页面'
                break
              default:
                actionText = `执行${actionType}操作`
            }
          }
        } else if (typeof data.action === 'string') {
          actionText = data.action
        }
        
        addLog('Agent', `步骤 ${data.step}: ${actionText}`, 'info')
      })
      
      socket.on('session_completed', (data) => {
        sessionStatus.value = 'completed'
        isRecording.value = false
        taskProgress.value = 100
        progressText.value = '任务执行完成'
        realtimeScreenEnabled.value = false
        currentScreenFrame.value = null
        addLog('Agent', data.message, 'success')
      })
      
      socket.on('session_stopped', (data) => {
        sessionStatus.value = 'idle'
        isRecording.value = false
        taskProgress.value = 0
        progressText.value = '任务已停止'
        realtimeScreenEnabled.value = false
        currentScreenFrame.value = null
        addLog('系统', data.message, 'warning')
      })
      
      // 实时屏幕帧事件
      socket.on('realtime_screen', (data) => {
        if (data.type === 'realtime_frame' && data.data) {
          currentScreenFrame.value = data.data
          // 更新屏幕状态时间戳
          screenStatus.last_frame_time = Date.now()
        }
      })
      
      socket.on('error', (data) => {
        sessionStatus.value = 'error'
        addLog('错误', data.message, 'error')
      })

      // 新增：监听API数据更新事件
      socket.on('new_api_data', (data) => {
        if (data.data && Array.isArray(data.data)) {
          // 将新数据添加到现有数据的前面（最新的在上面）
          const newApis = data.data.filter(newApi => 
            !capturedApis.value.some(existingApi => existingApi.id === newApi.id)
          )
          capturedApis.value = [...newApis, ...capturedApis.value]
          
          // 限制显示的数量，避免内存占用过多
          if (capturedApis.value.length > 200) {
            capturedApis.value = capturedApis.value.slice(0, 200)
          }
          
          // 自动滚动到顶部显示最新数据
          nextTick(() => {
            const apiListContainer = document.querySelector('.api-list')
            if (apiListContainer) {
              apiListContainer.scrollTop = 0
            }
          })
        }
      })
    }

    // 添加日志
    const addLog = (source, message, type = 'info') => {
      const log = {
        time: new Date(),
        source,
        message,
        type
      }
      activityLogs.value.push(log)
      
      // 限制日志数量
      if (activityLogs.value.length > 100) {
        activityLogs.value.shift()
      }
      
      // 自动滚动到底部
      nextTick(() => {
        if (logContainer.value) {
          logContainer.value.scrollTop = logContainer.value.scrollHeight
        }
      })
    }

    // 格式化时间
    const formatTime = (date) => {
      return date.toLocaleTimeString('zh-CN', { 
        hour12: false,
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit'
      })
    }

    // 启动浏览器会话
    const openBrowserSession = async () => {
      try {
        const response = await axios.post(`${API_BASE_URL}/api/start_session`, {
          url: currentUrl.value,
          task: '浏览网站并执行任务'
        })
        
        if (response.data.status === 'success') {
          addLog('系统', '浏览器会话启动成功', 'success')
        }
      } catch (error) {
        addLog('错误', `启动失败: ${error.response?.data?.error || error.message}`, 'error')
      }
    }

    // 停止浏览器会话
    const stopBrowserSession = async () => {
      try {
        const response = await axios.post(`${API_BASE_URL}/api/stop_session`)
        
        if (response.data.status === 'success') {
          addLog('系统', '浏览器会话停止成功', 'warning')
        }
      } catch (error) {
        addLog('错误', `停止失败: ${error.response?.data?.error || error.message}`, 'error')
      }
    }

    // 刷新会话状态
    const refreshSession = async () => {
      try {
        const response = await axios.get(`${API_BASE_URL}/api/session_status`)
        sessionStatus.value = response.data.is_running ? 'running' : 'idle'
        addLog('系统', '状态已刷新', 'info')
      } catch (error) {
        addLog('错误', `刷新失败: ${error.message}`, 'error')
      }
    }

    // 截图功能
    const takeScreenshot = async () => {
      try {
        const response = await axios.post(`${API_BASE_URL}/api/realtime/screen/screenshot`)
        if (response.data.success) {
          addLog('系统', '截图已保存', 'success')
        }
      } catch (error) {
        addLog('错误', `截图失败: ${error.message}`, 'error')
      }
    }

    // 获取实时屏幕状态
      const fetchScreenStatus = async () => {
        try {
          const response = await axios.get(`${API_BASE_URL}/api/realtime/screen/status`)
          if (response.data.success) {
            Object.assign(screenStatus, response.data.status)
          }
        } catch (error) {
          console.error('获取屏幕状态失败:', error)
        }
      }

    // 更新屏幕配置
      const updateScreenConfig = async (config) => {
        try {
          const response = await axios.post(`${API_BASE_URL}/api/realtime/screen/config`, config)
          if (response.data.success) {
            addLog('系统', '屏幕配置已更新', 'success')
            await fetchScreenStatus()
          }
        } catch (error) {
          addLog('错误', `配置更新失败: ${error.message}`, 'error')
        }
      }

    // 选择任务
    const selectJob = (job) => {
      currentUrl.value = job.url
      addLog('系统', `选择了任务: ${job.name}`, 'info')
    }

    // 创建新任务
    const createNewJob = () => {
      if (!newJobForm.websiteUrl) {
        return
      }
      
      currentUrl.value = newJobForm.websiteUrl
      showNewJobDialog.value = false
      addLog('系统', `创建新任务: ${newJobForm.websiteUrl}`, 'info')
      
      // 重置表单
      newJobForm.websiteUrl = ''
      newJobForm.taskDescription = ''
    }

    /**
     * 导航到指定URL
     * 当用户在地址栏输入URL并按回车或点击前往按钮时调用
     */
    const navigateToUrl = async () => {
      if (!currentUrl.value.trim()) {
        addLog('错误', '请输入有效的网站地址', 'error')
        return
      }
    
      // 确保URL格式正确
      let url = currentUrl.value.trim()
      if (!url.startsWith('http://') && !url.startsWith('https://')) {
        url = 'https://' + url
        currentUrl.value = url
      }
    
      addLog('系统', `导航到: ${url}`, 'info')
      
      // 如果当前有会话在运行，先停止
      if (sessionStatus.value === 'running') {
        await stopBrowserSession()
        // 等待一下确保会话完全停止
        await new Promise(resolve => setTimeout(resolve, 1000))
      }
      
      // 启动新的浏览器会话
      await openBrowserSession()
    }

    /**
     * 刷新API数据
     * 从后端获取最新的捕获API数据
     */
    const refreshApiData = async () => {
      apiLoading.value = true
      try {
        const response = await axios.get(`${API_BASE_URL}/api/captured_apis?limit=100`)
        if (response.data.status === 'success') {
          capturedApis.value = response.data.data
          addLog('系统', `已加载 ${response.data.count} 条API记录`, 'info')
        }
      } catch (error) {
        addLog('错误', `获取API数据失败: ${error.message}`, 'error')
      } finally {
        apiLoading.value = false
      }
    }

    /**
     * 格式化API时间戳
     * 将时间戳转换为可读的时间格式
     */
    const formatApiTime = (timestamp) => {
      if (!timestamp) return 'N/A'
      const date = new Date(timestamp * 1000) // 转换为毫秒
      return date.toLocaleTimeString('zh-CN', { 
        hour12: false,
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit'
      })
    }

    /**
     * 获取API状态对应的CSS类
     * 根据HTTP状态码返回不同的样式类
     */
    const getApiStatusClass = (status) => {
      if (!status) return 'status-unknown'
      if (status >= 200 && status < 300) return 'status-success'
      if (status >= 300 && status < 400) return 'status-redirect'
      if (status >= 400 && status < 500) return 'status-client-error'
      if (status >= 500) return 'status-server-error'
      return 'status-unknown'
    }
     // 生命周期钩子
     onMounted(() => {
       initSocket()
       addLog('系统', '应用已启动', 'info')
       // 初始加载API数据
       refreshApiData()
     })
     
     onUnmounted(() => {
       if (socket) {
         socket.disconnect()
       }
     })

     return {
       // 数据
       sessionStatus,
       connectionStatus,
       currentUrl,
       isRecording,
       taskProgress,
       progressText,
       activityLogs,
       selectedHistory,
       showNewJobDialog,
       userInfo,
       jobs,
       newJobForm,
       logContainer,
       
       // 实时屏幕数据
       realtimeScreenEnabled,
       currentScreenFrame,
       screenStatus,
       
       // API数据
       capturedApis,
       apiLoading,
       
       // 方法
       openBrowserSession,
       stopBrowserSession,
       refreshSession,
       takeScreenshot,
       selectJob,
       createNewJob,
       navigateToUrl,
       formatTime,
       addLog,
       
       // API相关方法
       refreshApiData,
       formatApiTime,
       getApiStatusClass,
       
       // 实时屏幕方法
       fetchScreenStatus,
       updateScreenConfig
     }
   }
 }
 </script>

<style scoped>
/* 全局样式 */
#app {
  font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
  height: 100vh;
  display: flex;
  flex-direction: column;
  background-color: #f5f5f5;
}

/* 顶部导航栏 */
.header {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  padding: 0 20px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
  z-index: 1000;
}

.header-content {
  display: flex;
  justify-content: space-between;
  align-items: center;
  height: 100%;
}

.logo-section {
  display: flex;
  align-items: center;
  gap: 12px;
}

.logo-icon {
  font-size: 24px;
  color: #fff;
}

.logo-text {
  font-size: 18px;
  font-weight: 600;
  color: #fff;
}

.nav-section {
  display: flex;
  align-items: center;
}

/* 主容器 */
.main-container {
  flex: 1;
  height: calc(100vh - 60px);
}

/* 左侧边栏 */
.sidebar {
  background: #ffffff;
  border-right: 1px solid #e0e0e0;
  box-shadow: 2px 0 8px rgba(0, 0, 0, 0.05);
}

.sidebar-content {
  padding: 20px;
  height: 100%;
  overflow-y: auto;
}

.sidebar-content h3 {
  margin: 0 0 15px 0;
  font-size: 16px;
  font-weight: 600;
  color: #333;
  border-bottom: 2px solid #667eea;
  padding-bottom: 8px;
}

/* 连接状态 */
.connection-status {
  margin-bottom: 25px;
}

.status-indicator {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 15px;
  border-radius: 8px;
  font-weight: 500;
  transition: all 0.3s ease;
}

.status-indicator.connected {
  background-color: #e8f5e8;
  color: #2e7d32;
  border: 1px solid #4caf50;
}

.status-indicator.disconnected {
  background-color: #ffebee;
  color: #c62828;
  border: 1px solid #f44336;
}

/* 会话控制 */
.session-controls {
  margin-bottom: 25px;
}

.control-buttons {
  display: flex;
  flex-direction: row;
  flex-wrap: wrap;
  justify-content: flex-start;
  align-items: center;
  gap: 0;
}

/* 屏幕状态 */
.screen-status {
  margin-bottom: 25px;
}

.status-info {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.status-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 12px;
  background-color: #f8f9fa;
  border-radius: 6px;
  font-size: 14px;
}

/* 活动日志 */
.activity-log {
  margin-bottom: 25px;
}

.log-container {
  max-height: 300px;
  overflow-y: auto;
  border: 1px solid #e0e0e0;
  border-radius: 4px;
  background-color: #f8f9fa;
  padding: 8px;
  font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
}

.log-item {
  display: flex;
  align-items: baseline;
  margin-bottom: 2px;
  padding: 2px 4px;
  font-size: 12px;
  line-height: 1.3;
  border-radius: 2px;
}

.log-item:hover {
  background-color: #f0f0f0;
}

.log-item.info {
  color: #333;
}

.log-item.success {
  color: #28a745;
}

.log-item.error {
  color: #dc3545;
}

.log-item.warning {
  color: #ffc107;
}

.log-time {
  font-weight: normal;
  color: #6c757d;
  margin-right: 8px;
  font-size: 11px;
  min-width: 60px;
}

.log-source {
  font-weight: 500;
  margin-right: 8px;
  min-width: 50px;
}

.log-message {
  flex: 1;
  word-break: break-word;
}

/* 历史记录 */
.history-section {
  margin-bottom: 25px;
}

.history-select {
  width: 100%;
}

/* 用户信息 */
.user-section {
  margin-top: auto;
  padding-top: 20px;
  border-top: 1px solid #e0e0e0;
}

.user-info {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px;
  background-color: #f8f9fa;
  border-radius: 8px;
}

.username {
  font-weight: 500;
  color: #333;
}

/* 主内容区域 */
.main-content {
  background-color: #f5f5f5;
  padding: 20px;
}

/* 浏览器主窗口 */
.browser-main-window {
  background: #ffffff;
  border-radius: 12px;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.1);
  overflow: hidden;
  height: calc(100vh - 140px);
  display: flex;
  flex-direction: column;
}

/* 浏览器工具栏 */
.browser-toolbar {
  display: flex;
  align-items: center;
  padding: 12px 16px;
  background: linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%);
  border-bottom: 1px solid #dee2e6;
  gap: 16px;
}

.browser-controls {
  display: flex;
  gap: 8px;
  align-items: center;
}

.control-button {
  width: 12px;
  height: 12px;
  border-radius: 50%;
  cursor: pointer;
  transition: opacity 0.2s ease;
}

.control-button:hover {
  opacity: 0.8;
}

.control-button.close {
  background-color: #ff5f57;
}

.control-button.minimize {
  background-color: #ffbd2e;
}

.control-button.maximize {
  background-color: #28ca42;
}

.address-bar {
  flex: 1;
  max-width: 600px;
}

.toolbar-actions {
  display: flex;
  gap: 8px;
}

/* 浏览器内容区域 */
.browser-content-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  position: relative;
  background-color: #ffffff;
}

/* 分割布局 */
.content-split-layout {
  display: flex;
  height: 100%;
  gap: 1px;
}

/* 左侧屏幕区域 */
.screen-section {
  flex: 1;
  background: #000;
  position: relative;
  min-width: 0;
}

/* 右侧API区域 */
.api-section {
  width: 400px;
  background: #ffffff;
  border-left: 1px solid #e0e0e0;
  display: flex;
  flex-direction: column;
}

/* API头部 */
.api-header {
  padding: 16px;
  border-bottom: 1px solid #e0e0e0;
  background: #f8f9fa;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.api-header h3 {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
  color: #333;
}

.api-stats {
  display: flex;
  align-items: center;
  gap: 12px;
  font-size: 14px;
  color: #666;
}

/* API列表 */
.api-list {
  flex: 1;
  overflow-y: auto;
  padding: 8px;
}

.api-item {
  display: grid;
  grid-template-columns: 60px 1fr 60px 80px;
  gap: 8px;
  padding: 8px 12px;
  margin-bottom: 4px;
  background: #ffffff;
  border: 1px solid #e0e0e0;
  border-radius: 6px;
  font-size: 12px;
  align-items: center;
  transition: all 0.2s ease;
}

.api-item:hover {
  background: #f8f9fa;
  border-color: #667eea;
  transform: translateY(-1px);
  box-shadow: 0 2px 8px rgba(102, 126, 234, 0.1);
}

.api-method {
  font-weight: 600;
  text-align: center;
  padding: 2px 6px;
  border-radius: 4px;
  color: #fff;
  background: #666;
}

.api-method:contains("GET") { background: #28a745; }
.api-method:contains("POST") { background: #007bff; }
.api-method:contains("PUT") { background: #ffc107; color: #333; }
.api-method:contains("DELETE") { background: #dc3545; }
.api-method:contains("PATCH") { background: #6f42c1; }

.api-url {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: #333;
  font-family: 'Consolas', 'Monaco', monospace;
}

.api-status {
  text-align: center;
  font-weight: 600;
  padding: 2px 6px;
  border-radius: 4px;
}

.status-success { color: #28a745; background: #d4edda; }
.status-redirect { color: #ffc107; background: #fff3cd; }
.status-client-error { color: #dc3545; background: #f8d7da; }
.status-server-error { color: #dc3545; background: #f8d7da; }
.status-unknown { color: #6c757d; background: #e2e3e5; }

.api-time {
  text-align: center;
  color: #666;
  font-family: 'Consolas', 'Monaco', monospace;
}

/* API空状态 */
.api-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 200px;
  color: #999;
}

.api-empty .el-icon {
  font-size: 48px;
  margin-bottom: 16px;
}

.api-empty p {
  margin: 0;
  font-size: 14px;
}

/* 实时屏幕显示 */
.realtime-screen {
  flex: 1;
  position: relative;
  display: flex;
  justify-content: center;
  align-items: center;
  background-color: #000;
  overflow: hidden;
}

.screen-image {
  max-width: 100%;
  max-height: 100%;
  object-fit: contain;
  border-radius: 4px;
}

.screen-overlay {
  position: absolute;
  top: 16px;
  right: 16px;
  z-index: 10;
}

.recording-indicator {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 16px;
  background: rgba(244, 67, 54, 0.9);
  color: white;
  border-radius: 20px;
  font-size: 14px;
  font-weight: 500;
  backdrop-filter: blur(10px);
}

.recording-icon {
  font-size: 16px;
  animation: pulse 2s infinite;
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}

/* 默认占位符 */
.browser-placeholder {
  flex: 1;
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  color: #666;
  background: linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%);
}

.placeholder-icon {
  font-size: 64px;
  color: #ccc;
  margin-bottom: 16px;
}

.browser-placeholder p {
  font-size: 16px;
  color: #666;
  margin: 0;
}

/* 响应式设计 */
@media (max-width: 1200px) {
  .sidebar {
    width: 280px !important;
  }
}

@media (max-width: 768px) {
  .header-content {
    padding: 0 16px;
  }
  
  .logo-text {
    display: none;
  }
  
  .sidebar {
    width: 260px !important;
  }
  
  .main-content {
    padding: 16px;
  }
  
  .browser-main-window {
    height: calc(100vh - 120px);
  }
}

/* 滚动条样式 */
.log-container::-webkit-scrollbar,
.sidebar-content::-webkit-scrollbar {
  width: 6px;
}

.log-container::-webkit-scrollbar-track,
.sidebar-content::-webkit-scrollbar-track {
  background: #f1f1f1;
  border-radius: 3px;
}

.log-container::-webkit-scrollbar-thumb,
.sidebar-content::-webkit-scrollbar-thumb {
  background: #c1c1c1;
  border-radius: 3px;
}

.log-container::-webkit-scrollbar-thumb:hover,
.sidebar-content::-webkit-scrollbar-thumb:hover {
  background: #a8a8a8;
}

/* Element Plus 组件样式覆盖 */
.el-button {
  border-radius: 6px;
  font-weight: 500;
}

.el-input {
  border-radius: 6px;
}

.el-progress {
  margin-bottom: 8px;
}

.el-tag {
  border-radius: 4px;
  font-weight: 500;
}

.el-dialog {
  border-radius: 12px;
}

.el-form-item__label {
  font-weight: 500;
  color: #333;
}
</style>