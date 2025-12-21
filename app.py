import streamlit as st
import google.generativeai as genai
import PyPDF2
import os
import pandas as pd
import io
import json
import docx  # 處理 .docx
from openpyxl import load_workbook

# --- 頁面設定 ---
st.set_page_config(
    page_title="Meta 廣告受眾戰略顧問 (Multi-Format)",
    page_icon="📂",
    layout="wide"
)

# --- 側邊欄：設定 ---
with st.sidebar:
    st.header("⚙️ 系統設定")
    
    api_key = st.text_input("Gemini API Key", type="password", help="請輸入 Google AI Studio API Key")
    
    st.markdown("### 🤖 模型版本")
    st.info("已鎖定使用：**gemini-2.5-pro**")
    model_version = "gemini-2.5-pro"

    st.markdown("---")
    st.info("💡 系統模式：本地讀取\n\n自動讀取 `meta_ads_targeting_database.md`。")

# --- 核心邏輯函式：多格式提取 ---

def extract_text_from_files(files):
    """根據副檔名自動選擇解析方式並合併文字"""
    combined_text = ""
    for file in files:
        try:
            file_extension = file.name.split('.')[-1].lower()
            combined_text += f"\n--- 檔案內容: {file.name} ---\n"
            
            # 1. PDF 處理
            if file_extension == 'pdf':
                pdf_reader = PyPDF2.PdfReader(file)
                for page in pdf_reader.pages:
                    text = page.extract_text()
                    if text: combined_text += text + "\n"
            
            # 2. Word 處理 (.docx)
            elif file_extension == 'docx':
                doc = docx.Document(file)
                for para in doc.paragraphs:
                    combined_text += para.text + "\n"
            
            # 3. Excel 處理 (.xlsx, .xls)
            elif file_extension in ['xlsx', 'xls']:
                df = pd.read_excel(file)
                # 將 Excel 轉換為 CSV 格式字串，保留結構感以便 AI 理解
                combined_text += df.to_csv(index=False) + "\n"
            
            # 4. JSON 處理
            elif file_extension == 'json':
                json_data = json.load(file)
                combined_text += json.dumps(json_data, indent=2, ensure_ascii=False) + "\n"
            
            # 5. TXT 處理
            elif file_extension == 'txt':
                stringio = io.StringIO(file.getvalue().decode("utf-8"))
                combined_text += stringio.read() + "\n"

        except Exception as e:
            st.error(f"讀取檔案 {file.name} 時發生錯誤: {e}")
            
    return combined_text

# --- 核心邏輯：Gemini API ---

def get_gemini_response(api_key, model_name, db_context, user_input, user_files_content):
    """呼叫 Gemini API 進行 RAG 分析"""
    genai.configure(api_key=api_key)
    
    generation_config = {
        "temperature": 0.2, 
        "top_p": 0.95,
        "max_output_tokens": 8192,
    }

    model = genai.GenerativeModel(
        model_name=model_name,
        generation_config=generation_config,
    )

    prompt = f"""
    角色設定：你是一位精通 Meta 廣告系統的資深投手與數據策略師。
    任務目標：請根據提供的「產品與策略資訊」，從「標準受眾資料庫」中篩選出最適合的 10-20 組廣告受眾興趣標籤。

    📚 標準受眾資料庫：
    {db_context}

    📝 補充文件與輸入內容：
    {user_input}
    {user_files_content}

    輸出要求：
    1. 提供 20 組受眾標籤。
    2. 分類明確（人口/興趣/行為）。
    3. 標記【✅ 資料庫驗證】或【⚠️ 潛在受眾】。
    4. 輸出 Markdown 表格，欄位：| 優先序 | 類別 | 受眾標籤 (Tag) | 來源驗證 | 戰略邏輯與應用場景 |
    """

    try:
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"API 呼叫錯誤: {str(e)}"

# --- 輔助函式：Markdown 表格轉 DF ---
def parse_markdown_table_to_df(markdown_text):
    try:
        lines = markdown_text.split('\n')
        table_lines = [line.strip() for line in lines if line.strip().startswith('|') and line.strip().endswith('|')]
        if len(table_lines) < 3: return None
        
        headers = [h.strip() for h in table_lines[0].strip('|').split('|')]
        data = []
        for line in table_lines[2:]:
            if '---' in line: continue
            values = [v.strip() for v in line.strip('|').split('|')]
            if len(values) == len(headers): data.append(values)
            elif len(values) > len(headers): data.append(values[:len(headers)])
            else: data.append(values + [''] * (len(headers) - len(values)))
        
        return pd.DataFrame(data, columns=headers) if data else None
    except:
        return None

def convert_df_to_excel(df):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='受眾標籤建議')
    return output.getvalue()

# --- 主畫面 UI ---
st.title("📂 Meta 廣告受眾戰略顧問 (全格式支援)")

# 讀取資料庫
def get_local_database(filename="meta_ads_targeting_database.md"):
    if not os.path.exists(filename): return None, f"❌ 找不到檔案：{filename}"
    with open(filename, "r", encoding="utf-8") as f: return f.read(), None

db_content, error_msg = get_local_database()

if error_msg:
    st.error(error_msg)
else:
    st.success(f"✅ 已載入受眾資料庫")

    col1, col2 = st.columns([1, 1])

    with col1:
        st.subheader("1. 輸入產品資訊")
        user_strategy_text = st.text_area("直接描述", height=200, placeholder="描述您的產品...")

    with col2:
        st.subheader("2. 上傳策略文件")
        uploaded_files = st.file_uploader(
            "支援 PDF, DOCX, XLSX, JSON, TXT", 
            type=['pdf', 'docx', 'xlsx', 'xls', 'json', 'txt'], 
            accept_multiple_files=True
        )

    if st.button("🚀 啟動 AI 戰略分析", type="primary"):
        if not api_key: st.stop()
        
        with st.spinner("🧠 正在跨格式提取數據並分析中..."):
            # 調用新的多格式提取函式
            user_files_content = extract_text_from_files(uploaded_files) if uploaded_files else ""
            
            result = get_gemini_response(api_key, model_version, db_content, user_strategy_text, user_files_content)
            
            st.markdown("### 📊 AI 戰略分析報告")
            st.markdown(result)
            
            df = parse_markdown_table_to_df(result)
            if df is not None:
                excel_data = convert_df_to_excel(df)
                st.download_button("📥 下載 Excel 清單", data=excel_data, file_name='meta_audience_suggestions.xlsx', type="primary")
