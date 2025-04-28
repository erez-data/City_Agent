# process_helperv2.py - FINAL memory based cleaning
import psutil
import os
from typing import Set

class ChromeCleaner:
    def __init__(self, active_driver=None):
        self.active_driver = active_driver

    def get_driver_pid(self):
        if not self.active_driver or not hasattr(self.active_driver.service, 'process'):
            return None
        try:
            return self.active_driver.service.process.pid
        except Exception as e:
            print(f"⚠️ Driver PID alınamadı: {e}")
            return None

    def kill_chrome_processes(self, force_full_clean=False):
        try:
            chrome_procs = []

            for proc in psutil.process_iter(['pid', 'name', 'cmdline', 'memory_info']):
                try:
                    name = proc.info['name'].lower() if proc.info['name'] else ''
                    if 'chrome' in name or 'chromedriver' in name:
                        chrome_procs.append(proc)
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue

            driver_pid = self.get_driver_pid()

            # Hafıza kullanımına göre sırala
            chrome_procs.sort(
                key=lambda p: p.info['memory_info'].rss if p.info['memory_info'] else 0,
                reverse=True
            )

            # Light clean: Sadece en yüksek 2 RAM kullanan PID + driver PID korunsun
            if not force_full_clean:
                memory_protected = {p.pid for p in chrome_procs[:7]}
                if driver_pid:
                    memory_protected.add(driver_pid)
            else:
                memory_protected = set()

            killed = 0
            alive_processes = []

            for proc in chrome_procs:
                pid = proc.pid
                mem_mb = (proc.info['memory_info'].rss / 1024 / 1024) if proc.info['memory_info'] else 0

                if pid in memory_protected:
                    alive_processes.append((pid, proc.info['name'], mem_mb))
                    continue

                try:
                    proc.kill()
                    try:
                        proc.wait(timeout=1)
                    except psutil.TimeoutExpired:
                        print(f"⚠️ PID {pid} düzgün kapanmadı.")
                    killed += 1
                except Exception as e:
                    print(f"⚠️ PID {pid} öldürülemedi: {e}")

            if force_full_clean:
                print(f"💥 FULL CLEAN: Killed {killed} Chrome processes")
            elif killed > 0:
                print(f"🧹 Light clean: Killed {killed} Chrome processes")

            if alive_processes:
                print("\n🟢 Active Chrome Processes (After Cleaning):")
                for pid, name, mem in alive_processes:
                    print(f"  PID {pid} - {name} - {mem:.1f} MB")

        except Exception as e:
            print(f"⚠️ Cleaner error: {e}")

    def manual_clean(self, force_full_clean=False):
        self.kill_chrome_processes(force_full_clean=force_full_clean)
