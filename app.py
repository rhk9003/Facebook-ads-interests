import streamlit as st
import google.generativeai as genai
import PyPDF2
import os

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
    
    # 模型選擇
    model_options = ["gemini-1.5-pro", "gemini-1.5-flash", "gemini-2.0-flash-exp"]
    selected_model = st.selectbox("選擇模型版本", model_options, index=0)
    custom_model = st.text_input("或輸入自定義模型名稱 (如 gemini-2.5-pro)", "")
    model_version = custom_model if custom_model else selected_model

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
    1. 請推薦 10 組受眾標籤。
    2. 必須依照資料庫架構分類 (人口統計/興趣/行為)。
    3. **嚴格比對**：若你推薦的標籤存在於「標準受眾資料庫」中，請標記【✅ 資料庫驗證】；若是你根據產品特性推論，但資料庫中沒有明確列出的，請標記【⚠️ 潛在受眾】。
    4. 每一組建議請提供「戰略邏輯」(為什麼選這個？與產品的連結點為何？)。
    5. 請以 Markdown 表格呈現。
    
    表格欄位格式：
    | 優先序 | 類別 | 受眾標籤 (Tag) | 來源驗證 | 戰略邏輯與應用場景 |

    最後，請根據這些標籤提供一個「漏斗策略建議」，例如：冷受眾建議使用 [A] 排除 [B]。
    """

    try:
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"API 呼叫錯誤: {str(e)}"

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
            
            # 顯示結果
            st.markdown("### 📊 AI 戰略分析報告")
            st.markdown(result)
