import pandas as pd
from datetime import datetime
import os

# 保存先フォルダ
folder_path = os.path.expanduser("~/Desktop/AI入居相談")
file_path = os.path.join(folder_path, "相談記録.xlsx")

# 相談データ（テスト用）
data = {
    "日時": [datetime.now().strftime("%Y-%m-%d %H:%M")],
    "希望エリア": ["名古屋市"],
    "性別": ["男性"],
    "年齢": ["30代"],
    "希望入居時期": ["3ヶ月以内"],
    "相談内容": ["グループホームを探しています"],
    "障がい名": [""],
    "障害区分": [""],
    "病院": [""],
    "ケースワーカー": [""],
    "相談員": [""],
    "経済状況": [""]
}

df = pd.DataFrame(data)

# Excelが存在するか確認
if os.path.exists(file_path):
    existing = pd.read_excel(file_path)
    df = pd.concat([existing, df], ignore_index=True)

# Excel保存
df.to_excel(file_path, index=False)

print("相談記録を保存しました")