import shutil
import platform

def get_chrome_binary_path():
    system = platform.system()
    if system == "Linux":
        return shutil.which("google-chrome") or shutil.which("chromium")
    elif system == "Darwin":  # macOS
        return "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
    elif system == "Windows":
        return shutil.which("chrome.exe")
    return None

def get_chromedriver_path():
    return shutil.which("chromedriver")
