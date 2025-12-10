#!/bin/bash

echo "🚀 Starting Meta Audience AI Strategy Tool..."

# 1. 檢查是否已安裝 pip
if ! command -v pip &> /dev/null; then
    echo "❌ Error: pip is not installed. Please install Python first."
    exit 1
fi

# 2. 安裝必要套件
echo "📦 Installing dependencies from requirements.txt..."
pip install -r requirements.txt

# 3. 檢查資料庫檔案是否存在
if [ ! -f "meta_ads_targeting_database.md" ]; then
    echo "⚠️  Warning: 'meta_ads_targeting_database.md' not found in current directory."
    echo "   Please ensure you have uploaded the audience database file."
fi

# 4. 啟動 Streamlit
echo "🌟 Launching Streamlit App..."
streamlit run app.py
