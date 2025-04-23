import os

def get_data_path(filename):
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    full_path = os.path.join(base_dir, "data-python", filename)
    os.makedirs(os.path.dirname(full_path), exist_ok=True)
    return full_path
