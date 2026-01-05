import base64
import json
import time
import io
import pyautogui
from openai import OpenAI
import config
from PIL import Image

# 初始化 OpenAI 客户端
# 注意：在实际运行前，请确保在 config.py 中填入了有效的 API Key
client = OpenAI(api_key=config.OPENAI_API_KEY)

def capture_screen_base64():
    """
    截取当前屏幕，转换为 JPEG 格式的 Base64 字符串。
    
    Returns:
        str: Base64 编码的图像数据
        tuple: (width, height) 屏幕原始分辨率
    """
    print("正在截取屏幕...")
    # 截取全屏
    screenshot = pyautogui.screenshot()
    
    # 获取屏幕分辨率
    width, height = screenshot.size
    print(f"屏幕分辨率: {width}x{height}")
    
    # 将图像保存为内存中的 JPEG
    buffered = io.BytesIO()
    screenshot.save(buffered, format="JPEG")
    
    # 转为 Base64
    img_str = base64.b64encode(buffered.getvalue()).decode("utf-8")
    
    return img_str, (width, height)

def ask_vlm_for_action(instruction, image_base64, screen_size):
    """
    将截图和指令发送给 GPT-4o，获取目标坐标。
    
    Args:
        instruction (str): 用户的自然语言指令
        image_base64 (str): Base64 编码的屏幕截图
        screen_size (tuple): (width, height) 屏幕分辨率
        
    Returns:
        dict: 包含 x, y 坐标和推理理由的字典，例如 {"x": 100, "y": 200, "reason": "..."}
    """
    width, height = screen_size
    
    # 构建 Prompt
    system_prompt = f"""
    你是一个 GUI 自动化专家。你的任务是分析用户的屏幕截图，根据用户的指令找到对应的 UI 元素，并返回该元素中心的精确像素坐标。
    
    屏幕分辨率为: {width}x{height}
    
    请严格按照以下 JSON 格式返回结果，不要包含 markdown 代码块或其他文本：
    {{
        "x": int, // 目标元素中心的 X 坐标
        "y": int, // 目标元素中心的 Y 坐标
        "reason": "str" // 选择该坐标的理由
    }}
    """
    
    user_message = [
        {
            "type": "text",
            "text": f"用户指令: {instruction}"
        },
        {
            "type": "image_url",
            "image_url": {
                "url": f"data:image/jpeg;base64,{image_base64}",
                "detail": "high" # 使用高分辨率模式以获得更好的细节识别
            }
        }
    ]
    
    print(f"正在向 {config.MODEL_NAME} 发送请求...")
    
    try:
        response = client.chat.completions.create(
            model=config.MODEL_NAME,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message}
            ],
            temperature=0.0, # 降低随机性
            max_tokens=300,
            response_format={"type": "json_object"} # 强制 JSON 输出
        )
        
        result_text = response.choices[0].message.content
        print(f"模型响应: {result_text}")
        
        # 解析 JSON
        result_json = json.loads(result_text)
        return result_json
        
    except Exception as e:
        print(f"API 请求或解析失败: {e}")
        return None

def main():
    print("=== OS Copilot MVP 启动 ===")
    
    # 1. 检查 API Key
    if config.OPENAI_API_KEY.startswith("sk-..."):
        print("错误: 请先在 config.py 中配置有效的 OpenAI API Key！")
        return

    # 模拟用户指令
    instruction = "点击左下角的开始菜单按钮"
    # instruction = "点击任务栏上的微信图标" # 你可以修改这里测试其他指令
    
    print(f"当前任务: {instruction}")
    
    # 2. Observe (观察)
    img_base64, screen_size = capture_screen_base64()
    
    # 3. Think (思考)
    action_data = ask_vlm_for_action(instruction, img_base64, screen_size)
    
    if action_data:
        target_x = action_data.get("x")
        target_y = action_data.get("y")
        reason = action_data.get("reason")
        
        print(f"定位成功! 坐标: ({target_x}, {target_y})")
        print(f"理由: {reason}")
        
        # 4. Act (行动)
        # 考虑 DPI 缩放
        # 注意：pyautogui 在某些高 DPI 设置下可能需要调整坐标，或者截图本身已经是缩放后的
        # 这里我们假设截图分辨率与 pyautogui 坐标系一致，或者通过 SCREEN_SCALING 进行修正
        
        final_x = target_x / config.SCREEN_SCALING
        final_y = target_y / config.SCREEN_SCALING
        
        print(f"正在移动鼠标到 ({final_x}, {final_y}) ...")
        
        # 移动鼠标，持续 2 秒，方便观察
        try:
            pyautogui.moveTo(final_x, final_y, duration=2.0)
            print("移动完成。 (MVP 阶段暂不执行点击，以策安全)")
            # pyautogui.click() 
        except Exception as e:
            print(f"执行动作失败: {e}")
            
    else:
        print("未能获取有效的动作指令。")

if __name__ == "__main__":
    main()
