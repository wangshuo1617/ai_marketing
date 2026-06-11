# utils/file_saver.py

import pandas as pd

def save_dataframe(df: pd.DataFrame, path: str):
    """
    将Pandas DataFrame保存为CSV文件。
    """
    try:
        df.to_csv(path, index=False, encoding='utf-8-sig')
    except Exception as e:
        print(f"Error saving DataFrame to {path}: {e}")

def save_text(content: str, path: str):
    """
    将文本内容保存为TXT文件。
    """
    try:
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)
    except Exception as e:
        print(f"Error saving text to {path}: {e}") 