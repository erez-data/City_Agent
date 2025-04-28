# utils/process_helper.py

import psutil
import platform
import os
from typing import Set, List


def get_all_children_pids(pid: int) -> Set[int]:
    """Find all children recursively for a given parent PID (cross-platform)."""
    try:
        parent = psutil.Process(pid)
        children = parent.children(recursive=True)
        return {child.pid for child in children}
    except Exception as e:
        print(f"⚠️ Failed to get child processes for PID {pid}: {e}")
        return set()


def is_safe_to_kill(proc: psutil.Process, protected_pids: Set[int], active_cmdlines: List[List[str]]) -> bool:
    """Determine if a process is safe to kill based on various criteria."""
    try:
        # Skip protected PIDs
        if proc.pid in protected_pids:
            return False

        # Skip processes with remote debugging port (likely active sessions)
        cmdline = proc.cmdline()
        if any('--remote-debugging-port' in arg for arg in cmdline):
            return False

        # Skip processes matching active command lines
        for active_cmd in active_cmdlines:
            if cmdline == active_cmd:
                return False

        return True
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        return False


def kill_zombie_chrome_processes(active_driver=None):
    """🚑 Hybrid method to kill Chrome zombies without affecting real user Chrome (cross-platform)."""
    try:
        active_pids = set()
        active_cmdlines = []

        if active_driver:
            try:
                # Get driver PID and all its children
                driver_pid = active_driver.service.process.pid
                active_pids.add(driver_pid)
                child_pids = get_all_children_pids(driver_pid)
                active_pids.update(child_pids)
                print(f"🛡️ Active PIDs: {list(active_pids)} (Main + Children)")

                # Store command lines of active processes for additional protection
                try:
                    driver_process = psutil.Process(driver_pid)
                    active_cmdlines.append(driver_process.cmdline())
                    for child in driver_process.children(recursive=True):
                        active_cmdlines.append(child.cmdline())
                except Exception as e:
                    print(f"⚠️ Cannot fetch active driver command lines: {e}")

            except Exception as e:
                print(f"⚠️ Couldn't get active driver PID: {e}")

        # Find all Chrome and ChromeDriver processes
        chrome_procs = []
        driver_procs = []

        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                if not proc.info['name']:
                    continue

                pname = proc.info['name'].lower()
                if 'chrome' in pname and 'chromedriver' not in pname:
                    chrome_procs.append(proc)
                elif 'chromedriver' in pname:
                    driver_procs.append(proc)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        print(f"🔍 Found {len(chrome_procs)} Chrome processes, {len(driver_procs)} ChromeDriver processes.")

        killed = 0
        for proc in chrome_procs + driver_procs:
            if is_safe_to_kill(proc, active_pids, active_cmdlines):
                try:
                    print(f"💀 Killing zombie PID {proc.pid} ({proc.info['name']})")
                    proc.kill()
                    killed += 1
                except Exception as e:
                    print(f"⚠️ Failed to kill PID {proc.pid}: {e}")

        if killed > 0:
            print(f"✅ Killed {killed} zombie Chrome/ChromeDriver processes.")
        else:
            print(f"🛡️ No zombie processes found. Only active session and user sessions kept.")

    except Exception as e:
        print(f"⚠️ Zombie killer error: {e}")


def log_memory_usage(context=""):
    """📊 Log the current memory usage"""
    try:
        process = psutil.Process()
        mem_info = process.memory_info()
        memory_usage_mb = mem_info.rss / 1024 / 1024
        print(f"📊 Memory usage {context}: {memory_usage_mb:.2f} MB")
    except Exception as e:
        print(f"⚠️ Memory log error: {e}")