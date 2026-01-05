import tkinter as tk
from tkinter import scrolledtext, messagebox, Toplevel
import threading
import pyautogui
import base64
import json
import io
import time
import re
import traceback
from PIL import Image, ImageDraw, ImageFont, ImageTk
from openai import OpenAI, OpenAIError

# ================= 配置区域 =================
# 根据你提供的文档更新了默认值
DEFAULT_API_KEY = "sk-..." 
# SiliconFlow (硅基流动) 的常见 API 地址，如果不同请在界面修改
DEFAULT_BASE_URL = "https://api.siliconflow.cn/v1" 
# 文档中有效的模型名称 (Qwen2.5-VL 72B 是目前很强的开源视觉模型)
DEFAULT_MODEL_NAME = "Qwen/Qwen2.5-VL-72B-Instruct" 
# ===========================================

class OSCopilotAgent:
    """逻辑核心类：负责视觉处理和 LLM 通信"""
    def __init__(self, api_key, base_url):
        self.client = OpenAI(api_key=api_key, base_url=base_url)
        self.last_grid_image = None  # 带网格的图（用于预览）
        self.last_clean_image = None # 原始干净图（用于裁剪）

    def update_settings(self, api_key, base_url):
        """动态更新 API 配置"""
        self.client.api_key = api_key
        self.client.base_url = base_url

    def _image_to_base64(self, image):
        """辅助函数：PIL Image 转 Base64"""
        buffered = io.BytesIO()
        image.save(buffered, format="JPEG", quality=85) # 稍微提高质量
        return base64.b64encode(buffered.getvalue()).decode("utf-8")

    def _draw_grid(self, image, step_count=10, color=(255, 0, 0), width=2):
        """辅助函数：在图片上画网格"""
        draw = ImageDraw.Draw(image)
        w, h = image.size
        step_x = w // step_count
        step_y = h // step_count
        
        for x in range(0, w, step_x):
            draw.line([(x, 0), (x, h)], fill=color, width=width)
            # 简单的坐标标注
            draw.text((x + 5, 5), str(x), fill=color)
            
        for y in range(0, h, step_y):
            draw.line([(0, y), (w, y)], fill=color, width=width)
            draw.text((5, y + 5), str(y), fill=color)
        return image

    def _draw_box(self, image, box, color=(0, 255, 0), width=5):
        """辅助函数：在图片上画预测框"""
        if not box or len(box) != 4:
            return image
        draw = ImageDraw.Draw(image)
        xmin, ymin, xmax, ymax = box
        draw.rectangle([xmin, ymin, xmax, ymax], outline=color, width=width)
        return image

    def capture_screen(self):
        """截取全屏"""
        screenshot = pyautogui.screenshot()
        self.last_clean_image = screenshot.copy() # 备份一份干净的
        
        # 在副本上画网格
        grid_img = screenshot.copy()
        self.last_grid_image = self._draw_grid(grid_img, step_count=10)
        
        return self._image_to_base64(self.last_grid_image), screenshot.size

    def think(self, instruction, img_base64, screen_size, model_name, is_refine=False, crop_offset=(0,0)):
        """
        调用大模型进行思考
        model_name: 动态传入的模型名称
        """
        width, height = screen_size
        
        if not is_refine:
            # === 第一阶段：粗定位 (Bounding Box 模式) ===
            system_prompt = f"""
            你是一个桌面智能助手。当前屏幕分辨率: {width}x{height}。
            图片已覆盖红色网格。
            任务：根据指令分析 UI，返回目标元素的【检测框】(Bounding Box)。
            
            【返回格式】：
            {{
                "thought": "简述判断依据",
                "box_2d": [ymin, xmin, ymax, xmax] 
            }}
            
            注意：
            1. 请返回目标的左上角和右下角坐标。
            2. 坐标必须在 [0, 0] 到 [{height}, {width}] 范围内。
            3. 如果无法确定范围，请尽量估计一个合理的中心区域。
            """
        else:
            # === 第二阶段：精细定位 ===
            # ... (精修逻辑保持不变，但为了兼容性，也建议用 box)
            pass 
            # 暂时保持精修逻辑不变，集中火力改第一阶段
            off_x, off_y = crop_offset
            system_prompt = f"""
            这是目标区域的【局部放大图】。
            此局部图的左上角对应屏幕绝对坐标: ({off_x}, {off_y})。
            当前局部图分辨率: {width}x{height}。
            
            任务：在局部图中找到目标精确中心。
            请返回相对于【局部图左上角】的坐标 (local_x, local_y)。
            
            【返回格式】：
            {{
                "thought": "在放大图中，我看到...",
                "x": 50, 
                "y": 50
            }}
            """

        try:
            print(f"DEBUG: 发送请求 ({'精修模式' if is_refine else '全局模式'}) -> {model_name}...")
            response = self.client.chat.completions.create(
                model=model_name,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": [
                        {"type": "text", "text": f"指令：{instruction}"},
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img_base64}"}}
                    ]}
                ],
                max_tokens=300,
                temperature=0.0 # 精确模式需要0温
            )
            content = response.choices[0].message.content
            print(f"DEBUG: 模型响应: {content}")
            
            # 提取 JSON
            start_idx = content.find('{')
            end_idx = content.rfind('}')
            if start_idx != -1 and end_idx != -1:
                data = json.loads(content[start_idx : end_idx + 1])
                
                # 处理 Bounding Box 转换
                if "box_2d" in data:
                    ymin, xmin, ymax, xmax = data["box_2d"]
                    # 计算中心点
                    center_x = (xmin + xmax) // 2
                    center_y = (ymin + ymax) // 2
                    data["x"] = center_x
                    data["y"] = center_y
                    data["box"] = [xmin, ymin, xmax, ymax] # 保存框用于 debug
                
                return data
            
            # 正则兜底 (同时支持 Box 和 Point)
            # 匹配 [ymin, xmin, ymax, xmax]
            box_match = re.search(r'\[(\d+),\s*(\d+),\s*(\d+),\s*(\d+)\]', content)
            if box_match:
                 ymin, xmin, ymax, xmax = map(int, box_match.groups())
                 return {
                     "x": (xmin + xmax) // 2,
                     "y": (ymin + ymax) // 2,
                     "thought": "Regex Box Fallback",
                     "box": [xmin, ymin, xmax, ymax]
                 }

            # 匹配 (x, y)
            match = re.search(r'\((\d+),\s*(\d+)\)', content)
            if match:
                return {"x": int(match.group(1)), "y": int(match.group(2)), "thought": "Regex Point Fallback"}
            
            return {"error": f"解析失败: {content}"}

        except Exception as e:
            traceback.print_exc()
            return {"error": str(e)}

    def refine_coordinates(self, instruction, approx_x, approx_y, screen_w, screen_h, model_name):
        """第二阶段：裁剪出局部图，进行精细定位"""
        if not self.last_clean_image:
            return {"error": "无原始截图"}

        # 动态计算裁剪框大小
        crop_size = int(screen_w / 3) 
        crop_size = max(600, min(crop_size, 1200))
        
        half_crop = crop_size // 2
        
        # 计算裁剪区域，防止越界
        left = max(0, approx_x - half_crop)
        top = max(0, approx_y - half_crop)
        right = min(screen_w, left + crop_size)
        bottom = min(screen_h, top + crop_size)
        
        # 实际裁剪
        crop_img = self.last_clean_image.crop((left, top, right, bottom))
        
        # 在局部图上画更细的网格
        grid_crop = crop_img.copy()
        grid_crop = self._draw_grid(grid_crop, step_count=8, color=(0, 255, 0)) # 用绿色网格区分
        
        # 保存精修图用于调试查看
        self.last_grid_image = grid_crop 
        
        img_base64 = self._image_to_base64(grid_crop)
        
        # 调用大模型
        result = self.think(instruction, img_base64, crop_img.size, model_name, is_refine=True, crop_offset=(left, top))
        
        if "error" in result:
            return result
            
        # 将局部坐标转换为全局坐标
        local_x = result.get("x", 0)
        local_y = result.get("y", 0)
        
        global_x = left + local_x
        global_y = top + local_y
        
        return {
            "thought": f"精修修正: {result.get('thought')}",
            "x": global_x,
            "y": global_y
        }

class CopilotGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("OS Copilot Pro (Configurable)")
        self.root.geometry("450x750") # 稍微加高一点以容纳新选项
        self.root.attributes('-topmost', True)
        self.bg_color = "#1e1e1e"
        self.fg_color = "#00ff00"
        self.root.configure(bg=self.bg_color)
        
        self.agent = OSCopilotAgent(DEFAULT_API_KEY, DEFAULT_BASE_URL)
        self.setup_ui()
        
    def setup_ui(self):
        # 1. 标题
        tk.Label(self.root, text="OS COPILOT V2.2", bg=self.bg_color, fg=self.fg_color, font=("Consolas", 16, "bold")).pack(pady=10)
        
        # === 配置区域容器 ===
        config_frame = tk.Frame(self.root, bg=self.bg_color)
        config_frame.pack(fill="x", padx=10)

        # 2.1 API Key
        tk.Label(config_frame, text="API Key:", bg=self.bg_color, fg="white", anchor="w").pack(fill="x")
        self.api_entry = tk.Entry(config_frame, bg="#333", fg="white", show="*")
        self.api_entry.insert(0, DEFAULT_API_KEY)
        self.api_entry.pack(fill="x", pady=(0, 5))

        # 2.2 Base URL (新增)
        tk.Label(config_frame, text="Base URL (API Endpoint):", bg=self.bg_color, fg="white", anchor="w").pack(fill="x")
        self.base_url_entry = tk.Entry(config_frame, bg="#333", fg="white")
        self.base_url_entry.insert(0, DEFAULT_BASE_URL)
        self.base_url_entry.pack(fill="x", pady=(0, 5))

        # 2.3 Model Name (新增)
        tk.Label(config_frame, text="Model Name (e.g. gpt-4o, qwen...):", bg=self.bg_color, fg="white", anchor="w").pack(fill="x")
        self.model_entry = tk.Entry(config_frame, bg="#333", fg="white")
        self.model_entry.insert(0, DEFAULT_MODEL_NAME)
        self.model_entry.pack(fill="x", pady=(0, 10))

        # 3. 指令
        tk.Label(self.root, text="指令 (Command):", bg=self.bg_color, fg="white", anchor="w").pack(fill="x", padx=10, pady=(5, 0))
        self.cmd_entry = tk.Entry(self.root, bg="#333", fg="white", font=("Microsoft YaHei", 12))
        self.cmd_entry.pack(fill="x", padx=10, pady=5)
        self.cmd_entry.bind("<Return>", lambda e: self.start_task_thread())

        # 4. 按钮
        btn_frame = tk.Frame(self.root, bg=self.bg_color)
        btn_frame.pack(pady=10)
        self.run_btn = tk.Button(btn_frame, text="执行 (EXECUTE)", command=self.start_task_thread, bg="#006400", fg="white", width=12)
        self.run_btn.pack(side="left", padx=5)
        self.preview_btn = tk.Button(btn_frame, text="视觉调试 (VIEW)", command=self.show_debug_image, bg="#00008b", fg="white", width=12)
        self.preview_btn.pack(side="left", padx=5)

        # 5. 选项开关
        opt_frame = tk.Frame(self.root, bg=self.bg_color)
        opt_frame.pack(pady=5)
        
        self.safe_mode = tk.BooleanVar(value=True)
        tk.Checkbutton(opt_frame, text="安全模式(不点击)", variable=self.safe_mode, bg=self.bg_color, fg="orange", selectcolor="#333").pack(side="left", padx=5)
        
        self.precision_mode = tk.BooleanVar(value=True) # 默认开启精准模式
        tk.Checkbutton(opt_frame, text="精准定位(双重确认)", variable=self.precision_mode, bg=self.bg_color, fg="#00ffff", selectcolor="#333").pack(side="left", padx=5)

        # 6. 日志
        tk.Label(self.root, text="SYSTEM LOG:", bg=self.bg_color, fg="gray", anchor="w").pack(fill="x", padx=10)
        self.log_area = scrolledtext.ScrolledText(self.root, bg="black", fg=self.fg_color, font=("Consolas", 10), height=18)
        self.log_area.pack(fill="both", expand=True, padx=10, pady=10)
        self.log("System Ready. Please check Base URL & Model Name.")

    def log(self, text):
        current_time = time.strftime("%H:%M:%S")
        self.log_area.insert(tk.END, f"[{current_time}] {text}\n")
        self.log_area.see(tk.END)

    def start_task_thread(self):
        instruction = self.cmd_entry.get()
        if not instruction: return
        
        # === 动态获取配置 ===
        api_key = self.api_entry.get().strip()
        base_url = self.base_url_entry.get().strip()
        model_name = self.model_entry.get().strip()
        
        # 更新 Agent 配置
        self.agent.update_settings(api_key, base_url)
        
        self.run_btn.config(state="disabled", text="Running...")
        threading.Thread(target=self.run_task, args=(instruction, model_name)).start()

    def run_task(self, instruction, model_name):
        try:
            self.log("隐藏窗口截屏...")
            self.root.attributes('-alpha', 0.0)
            time.sleep(0.5)
            
            # === 第一步：粗定位 ===
            img_base64, screen_size = self.agent.capture_screen()
            phys_w, phys_h = screen_size
            
            # === 自动计算 DPI 缩放 ===
            logic_w, logic_h = pyautogui.size()
            scale_x = phys_w / logic_w
            scale_y = phys_h / logic_h
            
            self.log(f"Res: {phys_w}x{phys_h} | Scale: {scale_x:.2f}")
            self.root.attributes('-alpha', 1.0) # 恢复显示
            
            self.log(f"Thinking with {model_name}...")
            res1 = self.agent.think(instruction, img_base64, screen_size, model_name)
            
            if "error" in res1:
                self.log(f"Error: {res1['error']}")
                return

            x1, y1 = res1.get("x", 0), res1.get("y", 0)
            self.log(f"粗定位: ({x1}, {y1}) | {res1.get('thought', '')}")
            
            # === 在 debug 图上画出模型预测的框 ===
            if "box" in res1 and self.agent.last_grid_image:
                 self.agent.last_grid_image = self.agent._draw_box(self.agent.last_grid_image, res1["box"])
                 self.log(f"预测框: {res1['box']}")

            final_x, final_y = x1, y1
            
            # === 第二步：精细定位 (如果开启) ===
            if self.precision_mode.get():
                self.log(">>> Refine (Zoom-in)...")
                pyautogui.moveTo(x1 / scale_x, y1 / scale_y, duration=0.5)
                
                res2 = self.agent.refine_coordinates(instruction, x1, y1, phys_w, phys_h, model_name)
                
                if "error" not in res2:
                    final_x = res2.get("x")
                    final_y = res2.get("y")
                    self.log(f"精定位修正: -> ({final_x}, {final_y})")
                else:
                    self.log(f"Refine Failed: {res2['error']}")

            # === 执行动作 ===
            # 安全边界检查：防止坐标越界
            final_x = max(0, min(final_x, phys_w - 1))
            final_y = max(0, min(final_y, phys_h - 1))
            
            target_x = final_x / scale_x
            target_y = final_y / scale_y
            
            self.log(f"Action -> ({target_x:.1f}, {target_y:.1f}) [Phys: {final_x},{final_y}]")
            pyautogui.moveTo(target_x, target_y, duration=0.8)
            
            if not self.safe_mode.get():
                self.log("CLICK!")
                pyautogui.click()
            else:
                self.log("Safe Mode: Skipped Click")
                
        except Exception as e:
            self.log(f"Critical Error: {e}")
            traceback.print_exc()
            self.root.attributes('-alpha', 1.0)
        finally:
            self.run_btn.config(state="normal", text="执行 (EXECUTE)")

    def show_debug_image(self):
        if self.agent.last_grid_image is None:
            messagebox.showinfo("提示", "无记录")
            return
        top = Toplevel(self.root)
        top.title("Vision Debug (Last Processed Frame)")
        top.geometry("800x600")
        img = self.agent.last_grid_image.copy()
        img.thumbnail((780, 580))
        photo = ImageTk.PhotoImage(img)
        lbl = tk.Label(top, image=photo)
        lbl.image = photo
        lbl.pack(expand=True, fill="both")

if __name__ == "__main__":
    root = tk.Tk()
    app = CopilotGUI(root)
    root.mainloop()