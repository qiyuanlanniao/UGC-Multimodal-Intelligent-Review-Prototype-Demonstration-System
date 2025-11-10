# backend/web_ocr.py
"""
使用Selenium和PearOCR的Web OCR处理器
"""
import time
import os
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.options import Options
from threading import Lock


class BrowserManager:
    """
    管理Selenium WebDriver实例的单例。
    确保整个应用程序生命周期中只有一个浏览器实例被创建和复用。
    """
    _instance = None
    _lock = Lock()  # 线程锁，用于处理并发请求

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance.driver = None
                    cls._instance.wait = None
        return cls._instance

    def initialize(self):
        """
        初始化WebDriver。这个方法应该在应用启动时被调用。
        """
        if self.driver is None:
            print("🧠 首次初始化Selenium WebDriver (启动后台Chrome)...")
            try:
                chrome_options = Options()
                chrome_options.add_argument("--headless=new")
                chrome_options.add_argument("--disable-gpu")
                chrome_options.add_argument("--no-sandbox")
                chrome_options.add_argument("--window-size=1920,1080")
                chrome_options.add_argument(
                    "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")
                chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])

                self.driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)

                url = "https://pearocr.com/#/"
                self.driver.get(url)
                self.wait = WebDriverWait(self.driver, 20)  # 通用等待器
                print(f"✅ 后台Chrome启动成功，并已打开: {url}")
            except Exception as e:
                print(f"❌ Selenium WebDriver初始化失败: {e}")
                self.driver = None

    def recognize_text(self, image_path: str) -> str:
        """
        使用已打开的浏览器实例识别单张图片的文本。
        该方法是线程安全的。
        """
        if self.driver is None:
            print("⚠️ WebDriver未初始化，无法执行Web OCR")
            return ""

        # 使用线程锁确保同一时间只有一个请求在使用浏览器
        with self._lock:
            try:
                print(f"🚀 [Web OCR] 开始处理图片: {os.path.basename(image_path)}")
                # 每次识别前刷新页面，确保处于一个干净的状态
                self.driver.refresh()

                # 1. 定位文件上传框并上传
                file_input = self.wait.until(EC.presence_of_element_located((By.XPATH, "//input[@type='file']")))
                file_input.send_keys(image_path)
                print("...图片上传成功，等待识别...")

                # 2. 等待识别完成的信号（复制按钮可点击）
                copy_button_wait = WebDriverWait(self.driver, 60)  # OCR可能很慢，给足等待时间
                copy_button_wait.until(EC.element_to_be_clickable((By.ID, "copyText")))
                print("...OCR识别完成！")

                # 3. 提取结果
                result_textarea = self.driver.find_element(By.CSS_SELECTOR, "textarea.textItem")
                recognized_text = result_textarea.get_attribute('value')

                print(f"✅ [Web OCR] 识别成功")
                return recognized_text.strip() if recognized_text else ""

            except Exception as e:
                print(f"❌ [Web OCR] 自动化识别过程中发生错误: {e}")
                return ""

    def shutdown(self):
        """
        关闭WebDriver。这个方法应该在应用关闭时被调用。
        """
        if self.driver:
            print("🔌 关闭后台Chrome...")
            self.driver.quit()
            self._instance = None  # 重置实例


# 创建全局单例
browser_manager = BrowserManager()