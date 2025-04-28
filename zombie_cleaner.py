import psutil

def find_active_chromedriver_pids():
    active_pids = set()

    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            name = proc.info['name'].lower() if proc.info['name'] else ''
            cmdline = " ".join(proc.info['cmdline']).lower() if proc.info['cmdline'] else ''

            if 'chromedriver' in name or 'chrome' in name:
                active_pids.add(proc.pid)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    return active_pids

def clean_zombie_parents(exclude_pids):
    zombies = []

    # Zombie'leri bul
    for proc in psutil.process_iter(['pid', 'ppid', 'name', 'status']):
        try:
            if proc.info['status'] == psutil.STATUS_ZOMBIE:
                zombies.append((proc.info['pid'], proc.info['ppid'], proc.info['name']))
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    if not zombies:
        print("✅ No zombie processes found.")
        return

    print(f"⚠️ Found {len(zombies)} zombies.")

    parent_pids = set(ppid for _, ppid, _ in zombies)

    # Parent PID'lerden aktif olanları koru
    for ppid in parent_pids:
        if ppid in exclude_pids:
            print(f"🔒 Skipping active parent PID {ppid}")
            continue

        try:
            parent = psutil.Process(ppid)
            print(f"💀 Killing parent PID {ppid} ({parent.name()}) to cleanup zombies...")
            parent.terminate()
            parent.wait(timeout=5)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            print(f"⚠️ Cannot access or already dead: PID {ppid}")
        except psutil.TimeoutExpired:
            print(f"⏳ Timeout. Force killing PID {ppid}")
            try:
                parent.kill()
            except Exception as e:
                print(f"❌ Force kill failed: {e}")

if __name__ == "__main__":
    active_pids = find_active_chromedriver_pids()
    clean_zombie_parents(exclude_pids=active_pids)
