import streamlit as st
import google.generativeai as genai
import PyPDF2
import os
import pandas as pd
import io
import re

# --- 頁面設定 ---
st.set_page_config(
    page_title="Meta 廣告受眾戰略顧問 (Local DB)",
    page_icon="📂",
    layout="wide"
)

# --- 側邊欄：設定 ---
with st.sidebar:
    st.header("⚙️ 系統設定")
    
    # API Key 設定
    api_key = st.text_input("Gemini API Key", type="password", help="請輸入 Google AI Studio API Key")
    
    # 模型設定 (已鎖定)
    st.markdown("### 🤖 模型版本")
    st.info("已鎖定使用：**gemini-2.5-pro**")
    model_version = "gemini-2.5-pro"

    st.markdown("---")
    st.info("💡 系統模式：本地讀取\n\n程式會直接讀取同目錄下的 `meta_ads_targeting_database.md` 作為知識庫。")

# --- 核心邏輯函式 ---

def get_local_database(filename="meta_ads_targeting_database.md"):
    """直接讀取同目錄下的受眾資料庫文字檔"""
    if not os.path.exists(filename):
        return None, f"❌ 找不到檔案：{filename}。請確保該檔案與 app.py 位於同一資料夾內。"
    
    try:
        with open(filename, "r", encoding="utf-8") as f:
            return f.read(), None
    except Exception as e:
        return None, f"❌ 讀取檔案時發生錯誤：{str(e)}"

def extract_text_from_pdfs(files):
    """讀取使用者上傳的策略 PDF"""
    combined_text = ""
    for file in files:
        try:
            pdf_reader = PyPDF2.PdfReader(file)
            for page in pdf_reader.pages:
                text = page.extract_text()
                if text:
                    combined_text += text + "\n"
        except Exception as e:
            st.error(f"讀取檔案 {file.name} 時發生錯誤: {e}")
    return combined_text

def get_gemini_response(api_key, model_name, db_context, user_input, user_files_content):
    """呼叫 Gemini API 進行 RAG 分析"""
    genai.configure(api_key=api_key)
    
    generation_config = {
        "temperature": 0.2, 
        "top_p": 0.95,
        "top_k": 64,
        "max_output_tokens": 8192,
    }

    model = genai.GenerativeModel(
        model_name=model_name,
        generation_config=generation_config,
    )

    # 組合 Prompt
    prompt = f"""
    角色設定：
    你是一位精通 Meta (Facebook/Instagram) 廣告系統的資深投手與數據策略師。

    任務目標：
    請根據使用者提供的「產品與策略資訊」，從「標準受眾資料庫」中篩選出最適合的 10 組廣告受眾興趣標籤。

    📚 標準受眾資料庫 (這是 Meta 後台真實存在的標籤，請優先由此選取)：
    {db_context}

    📝 使用者產品與策略資訊：
    ---
    {user_input}
    
    {user_files_content}
    ---

    輸出要求：
    1. 請推薦 20 組受眾標籤。
    2. 必須依照資料庫架構分類 (人口統計/興趣/行為)。
    3. **嚴格比對**：若你推薦的標籤存在於「標準受眾資料庫」中，請標記【✅ 資料庫驗證】；若標籤屬於資料中待驗證區域的請標記【⚠️ 潛在受眾】。
    4. 每一組建議請提供「戰略邏輯」(為什麼選這個？與產品的連結點為何？)。
    5. 請以 Markdown 表格呈現。
    
    表格欄位格式：
    | 優先序 | 類別 | 受眾標籤 (Tag) | 來源驗證 | 戰略邏輯與應用場景 |
    """

    try:
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"API 呼叫錯誤: {str(e)}"

def parse_markdown_table_to_df(markdown_text):
    """
    從 Markdown 文本中解析出表格並轉換為 Pandas DataFrame。
    """
    try:
        # 使用正規表達式尋找 Markdown 表格結構
        # 尋找以 | 開頭和結尾的行
        lines = markdown_text.split('\n')
        table_lines = [line.strip() for line in lines if line.strip().startswith('|') and line.strip().endswith('|')]
        
        if len(table_lines) < 3:
            return None # 沒有找到有效的表格

        # 1. 處理標題列 (第一行)
        header_line = table_lines[0]
        # 移除前後的 | 並以 | 分割，去除空白
        headers = [h.strip() for h in header_line.strip('|').split('|')]

        # 2. 略過分隔列 (第二行，通常是 |---|---|)
        
        # 3. 處理數據列 (從第三行開始)
        data = []
        for line in table_lines[2:]:
            # 簡單檢查這行是不是分隔線 (有些 Markdown 會有多個分隔線或錯置)
            if '---' in line:
                continue
                
            values = [v.strip() for v in line.strip('|').split('|')]
            
            # 確保欄位數量與標題一致 (處理可能有的空欄位)
            if len(values) == len(headers):
                data.append(values)
            elif len(values) > len(headers):
                 # 如果數據列比標題多，截斷
                 data.append(values[:len(headers)])
            else:
                # 如果數據列比標題少，補空值
                values += [''] * (len(headers) - len(values))
                data.append(values)

        if not data:
            return None

        df = pd.DataFrame(data, columns=headers)
        return df
    except Exception as e:
        print(f"解析表格時發生錯誤: {e}")
        return None

def convert_df_to_excel(df):
    """將 DataFrame 轉換為 Excel 的 Bytes"""
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='受眾標籤建議')
    processed_data = output.getvalue()
    return processed_data

# --- 主畫面 UI ---
st.title("📂 Meta 廣告受眾戰略顧問 (Direct Read)")
st.markdown("""
本系統會自動載入同目錄下的 **`meta_ads_targeting_database.md`**。
您只需輸入本次行銷活動的產品資訊與策略文件即可。
""")

# 1. 自動讀取資料庫
db_content, error_msg = get_local_database()

if error_msg:
    st.error(error_msg)
    st.warning("請將我們之前整理好的受眾清單存為 `meta_ads_targeting_database.md` 並上傳至同一個 GitHub 資料夾。")
else:
    st.success(f"✅ 已載入受眾資料庫 (長度: {len(db_content)} 字元)")

    col1, col2 = st.columns([1, 1])

    with col1:
        st.subheader("1. 輸入產品/策略資訊")
        user_strategy_text = st.text_area(
            "直接輸入產品描述、目標客群或行銷痛點", 
            height=200,
            placeholder="例如：我們是一款針對 25-35 歲上班族的舒壓精油，主要競品是無印良品，希望強調『睡前儀式感』..."
        )

    with col2:
        st.subheader("2. 補充策略文件 (選填)")
        uploaded_files = st.file_uploader(
            "上傳產品簡報、Persona 分析或過往投報 (PDF)", 
            type=['pdf'], 
            accept_multiple_files=True
        )

    # --- 執行區 ---
    st.markdown("---")

    if st.button("🚀 啟動 AI 戰略分析", type="primary"):
        # 檢查必要條件
        if not api_key:
            st.warning("⚠️ 請在側邊欄輸入 Gemini API Key")
            st.stop()
        
        if not user_strategy_text and not uploaded_files:
            st.warning("⚠️ 請至少輸入文字描述或上傳一份文件")
            st.stop()

        # 執行分析
        with st.spinner("🧠 正在比對資料庫並分析您的策略文件..."):
            # 讀取使用者上傳的 PDF
            user_files_content = ""
            if uploaded_files:
                user_files_content = extract_text_from_pdfs(uploaded_files)
                
            # 呼叫 Gemini
            result = get_gemini_response(
                api_key, 
                model_version, 
                db_content, 
                user_strategy_text, 
                user_files_content
            )
            
            # 顯示 Markdown 結果
            st.markdown("### 📊 AI 戰略分析報告")
            st.markdown(result)
            
            # --- 嘗試解析表格並提供下載 ---
            df = parse_markdown_table_to_df(result)
            
            if df is not None:
                st.markdown("---")
                st.success("🎉 已成功提取受眾標籤表格！")
                
                excel_data = convert_df_to_excel(df)
                
                st.download_button(
                    label="📥 下載受眾標籤 Excel 清單",
                    data=excel_data,
                    file_name='meta_audience_suggestions.xlsx',
                    mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                    type="primary"
                )
            else:
                st.info("💡 提示：本次回應中未偵測到標準表格，故無法提供 Excel 下載。")
