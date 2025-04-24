def focus_driver(driver):
    """Ensure the correct window is active and focused for the driver."""
    try:
        driver.switch_to.window(driver.current_window_handle)
        driver.execute_script("window.focus();")
        print("🪟 Focused on driver window:", driver.current_window_handle)
    except Exception as e:
        print(f"⚠️ Could not focus driver: {e}")
