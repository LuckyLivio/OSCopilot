# config.py

# SiliconFlow API Key
# 警告：不要将真实的 API Key 提交到代码仓库中！
OPENAI_API_KEY = "sk-..." 

# SiliconFlow API Base URL
API_BASE_URL = "https://api.siliconflow.cn/v1"

# 模型选择
# 使用 SiliconFlow 支持的 Qwen2-VL 模型，具备强大的视觉定位能力
MODEL_NAME = "Qwen/Qwen2-VL-72B-Instruct"

# 屏幕缩放比例 (DPI Scaling)
# 如果您的屏幕设置了 125% 或 150% 缩放，请相应修改此值 (例如 1.25 或 1.5)
# Windows 系统通常需要手动设置此值以确保坐标准确
SCREEN_SCALING = 1.0

# 请求超时时间 (秒)
API_TIMEOUT = 60
