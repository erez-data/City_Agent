import psutil
import time

def clean_zombies():
    zombie_names = ['cat', 'nacl_helper', 'chrome', 'chromedriver']

    for proc in psutil.process_iter(['pid', 'name', 'status']):
        try:
            name = proc.info['name'].lower() if proc.info['name'] else ''
            if any(z in name for z in zombie_names):
                if proc.status() == psutil.STATUS_ZOMBIE:
                    print(f"💀 Killing zombie PID {proc.pid} - {proc.info['name']}")
                    proc.kill()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

if __name__ == "__main__":
    while True:
        print("🔎 Checking for zombie processes...")
        clean_zombies()
        print("⏳ Sleeping for 60 seconds...\n")
        time.sleep(60)
