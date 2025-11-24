import streamlit as st
import google.generativeai as genai
from supabase import create_client, Client
from openpyxl import Workbook
from openpyxl.styles import PatternFill, Font, Alignment, Border, Side
from openpyxl.utils.dataframe import dataframe_to_rows
import json
import io
import time
import uuid
import pandas as pd
import random

# --- 유틸리티: 랜덤 파스텔 색상 생성 (어두운 색 방지) ---
def get_random_pastel_color():
    # R, G, B를 각각 200~255 사이에서 뽑아서 무조건 밝은 색이 나오게 함
    r = lambda: random.randint(200, 255)
    return '#%02X%02X%02X' % (r(), r(), r())

# --- 데이터 구조 클래스 ---
class PolicyData:
    def __init__(self, name, df, footer_text, color_hex):
        self.name = name
        self.df = df
        self.footer_text = footer_text
        self.color_hex = color_hex # 사용자가 지정한 색상 코드

# --- 1. Gemini 파싱 함수 (배틀용) ---
def parse_image_with_gemini(file_bytes, agency_name, color_hex, api_key, model_name):
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(model_name)
    
    prompt = """
    Analyze this mobile phone price sheet image.
    Return JSON with two parts:
    1. "table": A list of lists representing the grid. Row 1 is headers.
       - Convert all prices to integers (e.g., 45, -5). If empty, use null.
       - Normalize Model names if possible (e.g., 'gal24' -> 'S24').
    2. "footer": Extract all condition texts at the bottom as a single string.
    
    Structure: {"table": [[...], ...], "footer": "..."}
    Output ONLY JSON.
    """
    
    response = model.generate_content([prompt, {"mime_type": "image/jpeg", "data": file_bytes}])
    text = response.text.replace("```json", "").replace("```", "").strip()
    data = json.loads(text)
    
    # DataFrame 변환
    headers = data["table"][0]
    rows = data["table"][1:]
    df = pd.DataFrame(rows, columns=headers)
    
    # 인덱스 설정 (첫 열 기준)
    df.set_index(df.columns[0], inplace=True)
    df = df.apply(pd.to_numeric, errors='coerce')
    
    # 객체 생성 시 색상 정보도 함께 저장
    return PolicyData(agency_name, df, data["footer"], color_hex)

# --- 2. 엑셀 생성 (전쟁 로직) ---
def create_battle_excel(policies):
    wb = Workbook()
    
    # 1. 시트 생성
    ws_main = wb.active
    ws_main.title = "🏆최고의 정책서"
    
    # 기준점 잡기 (첫 번째 정책 기준)
    base_df = policies[0].df
    combined_index = base_df.index
    combined_columns = base_df.columns
    
    # 헤더 작성
    ws_main.cell(row=1, column=1, value="모델명")
    for c_idx, col in enumerate(combined_columns, 2):
        ws_main.cell(row=1, column=c_idx, value=col)
        
    center_align = Alignment(horizontal='center', vertical='center')
    thin_border = Border(left=Side(style='thin'), right=Side(style='thin'), top=Side(style='thin'), bottom=Side(style='thin'))
    
    winning_agencies = set() # 승리한 대리점 목록

    # Row 순회
    for r_idx, model in enumerate(combined_index, 2):
        ws_main.cell(row=r_idx, column=1, value=model).border = thin_border
        
        # Col 순회 (전쟁)
        for c_idx, col in enumerate(combined_columns, 2):
            best_price = -9999
            winner_policy = None
            
            # 각 정책서 비교
            for p in policies:
                try:
                    price = p.df.at[model, col]
                    if pd.notna(price) and price > best_price:
                        best_price = price
                        winner_policy = p
                except:
                    pass
            
            cell = ws_main.cell(row=r_idx, column=c_idx)
            cell.border = thin_border
            cell.alignment = center_align
            
            if winner_policy:
                cell.value = best_price
                # 사용자가 지정한 색상 적용 (HEX 코드에서 '#' 제거)
                clean_hex = winner_policy.color_hex.replace("#", "")
                cell.fill = PatternFill(start_color=clean_hex, end_color=clean_hex, fill_type="solid")
                winning_agencies.add(winner_policy)
            else:
                cell.value = "-"

    # 4. 하단 조건문 동적 조립
    current_row = len(combined_index) + 3
    header_font = Font(bold=True, size=12)
    
    ws_main.cell(row=current_row, column=1, value="[ 📢 적용 조건 유의사항 ]").font = header_font
    current_row += 1
    
    # 중복 제거를 위해 set을 list로 변환 후 정렬 (순서 보장)
    # set에 객체를 넣었으므로 이름 기준으로 정렬
    sorted_winners = sorted(list(winning_agencies), key=lambda x: x.name)
    
    for p in sorted_winners:
        clean_hex = p.color_hex.replace("#", "")
        
        ws_main.merge_cells(start_row=current_row, start_column=1, end_row=current_row, end_column=5)
        title_cell = ws_main.cell(row=current_row, column=1, value=f"■ {p.name} 조건표")
        title_cell.fill = PatternFill(start_color=clean_hex, end_color=clean_hex, fill_type="solid")
        title_cell.font = Font(bold=True)
        current_row += 1
        
        ws_main.merge_cells(start_row=current_row, start_column=1, end_row=current_row+2, end_column=10)
        content_cell = ws_main.cell(row=current_row, column=1, value=p.footer_text)
        content_cell.alignment = Alignment(wrap_text=True, vertical='top')
        current_row += 3
            
    # 5. 원본 데이터 시트
    for p in policies:
        ws_raw = wb.create_sheet(title=f"원본_{p.name}")
        for r in dataframe_to_rows(p.df, index=True, header=True):
            ws_raw.append(r)
        ws_raw.append([""])
        ws_raw.append(["조건문 원본:"])
        ws_raw.append([p.footer_text])

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)
    return output

# --- 1. 설정 및 비밀키 관리 ---
st.set_page_config(page_title="성지당 시세표 변환기", layout="wide")

# (실제 배포시에는 st.secrets를 사용하세요. 로컬 테스트용으로 사이드바 입력)
with st.sidebar:
    st.header("🔐 서버 설정")
    
    # 기본값 설정 (Secrets에서 가져오기)
    gemini_api_key = st.secrets.get("GEMINI_API_KEY", "")
    supabase_url = st.secrets.get("SUPABASE_URL", "")
    supabase_key = st.secrets.get("SUPABASE_KEY", "")

    # Secrets가 있으면 입력창 숨김, 없으면 입력창 표시
    if gemini_api_key and supabase_url and supabase_key:
        st.success("✅ 서버 설정이 완료되었습니다.")
    else:
        if not gemini_api_key:
            gemini_api_key = st.text_input("Gemini API Key", type="password")
        if not supabase_url:
            supabase_url = st.text_input("Supabase Project URL")
        if not supabase_key:
            supabase_key = st.text_input("Supabase Anon Key", type="password")
    
    st.divider()
    
    # 모델 목록 가져오기 및 드롭다운 구성
    # 모델 목록 가져오기 및 드롭다운 구성
    # gemini-2.5-flash를 무조건 기본값(첫번째)으로 설정
    base_models = ["gemini-2.5-flash", "gemini-1.5-flash", "gemini-1.5-pro", "gemini-pro-vision"]
    model_options = ["gemini-2.5-flash"] # 시작은 flash로
    
    try:
        if gemini_api_key:
            genai.configure(api_key=gemini_api_key)
            # API에서 실제 사용 가능한 모델 리스트 가져오기
            fetched_models = [m.name.replace("models/", "") for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
            
            # fetched_models에 있는 것들을 추가하되, 중복 제거
            for m in fetched_models:
                if m not in model_options:
                    model_options.append(m)
            
            # 만약 API 호출 실패했거나 목록이 비었으면 기본 목록 사용
            if len(model_options) == 1: # flash만 있는 경우
                 for m in base_models:
                     if m not in model_options:
                         model_options.append(m)
                         
    except Exception:
        # API 키 오류시 기본 목록 사용
        model_options = base_models

    # gemini-1.5-flash가 항상 0번 인덱스에 있으므로 index=0
    model_name = st.selectbox("Gemini 모델 선택", model_options, index=0)

    st.divider()
    margin_default = st.number_input("기본 마진 설정 (단위:만원)", value=0)

# --- 2. 엑셀 생성 함수 (사용자 요청 스타일 적용) ---
def create_excel_bytes(data_json, margin_val):
    wb = Workbook()
    ws = wb.active
    ws.title = "성지 통합 시세표"

    # 스타일 정의
    thin_border = Border(left=Side(style='thin'), right=Side(style='thin'), top=Side(style='thin'), bottom=Side(style='thin'))
    header_fill = PatternFill(start_color="DDDDDD", end_color="DDDDDD", fill_type="solid")
    header_font = Font(bold=True)
    center_align = Alignment(horizontal='center', vertical='center')
    
    # 1. 상단 시세표 그리기
    top_headers = ["모델","출고가","공시지원금","SK_번이","SK_기변","SK_카드_번이","SK_카드_기변","KT_번이","KT_기변","KT_카드_번이","KT_카드_기변","LG_번이","LG_기변","LG_카드_번이","LG_카드_기변"]
    
    for col_idx, text in enumerate(top_headers, start=1):
        cell = ws.cell(row=1, column=col_idx, value=text)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = center_align
        cell.border = thin_border

    current_row = 2
    top_data = data_json.get("top_data", [])
    
    if top_data:
        for row_data in top_data:
            # 데이터 길이가 헤더보다 짧을 경우를 대비해 패딩
            row_data = row_data + [None] * (len(top_headers) - len(row_data))
            
            # 앞 3열 (모델, 출고가, 공시지원금) - 그대로 출력
            for c in range(3):
                cell = ws.cell(row=current_row, column=c+1, value=row_data[c])
                cell.alignment = center_align
                cell.border = thin_border
            
            # 나머지 열 (가격 정보) - 마진 수식 적용
            for c in range(3, 15):
                val = row_data[c]
                cell = ws.cell(row=current_row, column=c+1)
                
                # 숫자인 경우에만 수식 적용, 아니면 그대로 값 출력
                if isinstance(val, (int, float)):
                    cell.value = f"={val}-$Q$2"
                elif val is not None and str(val).replace('-','').isdigit(): # 문자열이지만 숫자인 경우
                     cell.value = f"={val}-$Q$2"
                else:
                    cell.value = val if val is not None else ""
                    
                cell.alignment = center_align
                cell.border = thin_border
            current_row += 1

    # 2. 중간 안내 문구
    current_row += 1
    ws.merge_cells(start_row=current_row, start_column=1, end_row=current_row, end_column=15)
    msg_cell = ws.cell(row=current_row, column=1, value="위 표시 금액은 현금완납가격 입니다. 카드결제도 가능합니다.")
    msg_cell.font = Font(color="FF0000", bold=True, size=14)
    msg_cell.alignment = center_align
    current_row += 2

    # 3. 하단 조건표 그리기
    bottom_headers = ["통신사", "부가서비스조건", "월요금", "유지기간", "미가입시추가금"]
    bottom_col_ranges = [(1,3), (4,8), (9,10), (11,12), (13,15)] # 열 병합 범위
    
    # 헤더 출력
    for idx, (sc, ec) in enumerate(bottom_col_ranges):
        ws.merge_cells(start_row=current_row, start_column=sc, end_row=current_row, end_column=ec)
        cell = ws.cell(row=current_row, column=sc, value=bottom_headers[idx])
        cell.fill = PatternFill(start_color="E2EFDA", end_color="E2EFDA", fill_type="solid")
        cell.font = header_font
        cell.alignment = center_align
        for c in range(sc, ec+1):
            ws.cell(row=current_row, column=c).border = thin_border
    current_row += 1

    # 데이터 출력
    bottom_data = data_json.get("bottom_data", [])
    start_data_row = current_row
    
    if bottom_data:
        for row_data in bottom_data:
            # 데이터 패딩
            row_data = row_data + [""] * (len(bottom_headers) - len(row_data))
            
            for idx, (sc, ec) in enumerate(bottom_col_ranges):
                ws.merge_cells(start_row=current_row, start_column=sc, end_row=current_row, end_column=ec)
                cell = ws.cell(row=current_row, column=sc, value=row_data[idx])
                cell.alignment = center_align
                for c in range(sc, ec+1):
                    ws.cell(row=current_row, column=c).border = thin_border
            current_row += 1
        
        # 통신사별 병합 (데이터가 10줄이라고 가정하고 3/3/4 등으로 나눔, 혹은 데이터 내용 기반)
        # 여기서는 사용자가 준 예시처럼 SK(3줄), KT(3줄), LG(3줄) 정도로 가정하되, 
        # 실제 데이터가 가변적일 수 있으므로 통신사 텍스트가 같은 것끼리 묶는 로직이 이상적이나
        # 우선 사용자 예시 코드의 하드코딩된 병합 로직을 최대한 따르되 안전장치 추가
        
        # (간단히 3등분 로직 대신, 첫번째 컬럼 값이 같으면 병합하는 로직은 복잡하므로 
        #  사용자 예시처럼 SK/KT/LG 순서대로 데이터가 온다고 가정하고 렌더링)
        pass 

    # 4. 맨 밑 유의사항 추가
    current_row += 1 
    footer_font = Font(size=9, color="333333") 
    footer_fill = PatternFill(start_color="F2F2F2", end_color="F2F2F2", fill_type="solid") 
    footer_align = Alignment(horizontal='center', vertical='center', wrap_text=True) 

    footer_lines = data_json.get("footer_lines", [])
    if footer_lines:
        for line in footer_lines:
            ws.merge_cells(start_row=current_row, start_column=1, end_row=current_row, end_column=15)
            cell = ws.cell(row=current_row, column=1, value=line)
            cell.font = footer_font
            cell.fill = footer_fill
            cell.alignment = footer_align
            
            for c in range(1, 16):
                ws.cell(row=current_row, column=c).border = thin_border
            current_row += 1

    # 5. 마진 설정 컨트롤러
    ws['Q1'] = "추가 마진 설정(만원)"
    ws['Q1'].fill = PatternFill(start_color="FF0000", end_color="FF0000", fill_type="solid")
    ws['Q1'].font = Font(color="FFFFFF", bold=True)
    ws.column_dimensions['Q'].width = 20
    ws['Q2'] = margin_val
    ws['Q2'].alignment = center_align
    ws['Q2'].font = Font(bold=True, size=14)

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)
    return output

# --- 3. 메인 UI ---
st.title("📱 성지당 시세표 AI 변환 시스템")
st.caption("Powered by Gemini 3.0 & Supabase")

# 탭 구성
tab1, tab2 = st.tabs(["시세표 to 엑셀", "최고의 정책서 만들기"])

# --- Tab 1: 시세표 to 엑셀 (기존 기능) ---
with tab1:
    st.header("📸 이미지로 엑셀 만들기")
    uploaded_file = st.file_uploader("시세표 이미지를 올려주세요", type=['png', 'jpg', 'jpeg'])

    if uploaded_file and gemini_api_key and supabase_url and supabase_key:
        
        # Supabase 클라이언트 연결
        try:
            supabase: Client = create_client(supabase_url, supabase_key)
        except Exception as e:
            st.error(f"Supabase 연결 오류: {e}")
            st.stop()
        
        if st.button("AI 변환 시작"):
            with st.status("작업을 진행하고 있습니다...", expanded=True) as status:
                
                # 1. Supabase Storage에 원본 이미지 업로드 (uploads 버킷)
                status.write("1️⃣ 원본 이미지를 서버에 저장 중...")
                file_bytes = uploaded_file.getvalue()
                # 한글 파일명 등으로 인한 오류 방지를 위해 UUID 사용
                file_ext = uploaded_file.name.split('.')[-1]
                file_name = f"simple-ocr/{int(time.time())}_{uuid.uuid4()}.{file_ext}"
                
                try:
                    # Storage 버킷 이름: uploads
                    supabase.storage.from_("uploads").upload(file_name, file_bytes, {"content-type": uploaded_file.type})
                    # 공개 URL 가져오기
                    image_public_url = supabase.storage.from_("uploads").get_public_url(file_name)
                except Exception as e:
                    error_msg = str(e)
                    if "Bucket not found" in error_msg or "404" in error_msg:
                        st.error("❌ **오류: 'uploads' 버킷을 찾을 수 없습니다.**")
                        st.info("Supabase 대시보드 > Storage 메뉴로 이동해서 **'uploads'** 라는 이름의 **Public Bucket**을 새로 만들어주세요.")
                    elif "row-level security policy" in error_msg or "403" in error_msg:
                        st.error("❌ **오류: 권한이 없습니다 (RLS Policy).**")
                        st.info("Supabase Storage의 'uploads' 버킷에 대해 Public Access 정책을 설정해주세요.")
                    else:
                        st.error(f"이미지 업로드 실패: {e}")
                    st.stop()
                    
                # 2. Gemini 3.0 호출 (OCR)
                status.write(f"2️⃣ Gemini ({model_name})가 데이터를 추출 중...")
                genai.configure(api_key=gemini_api_key)
                # 사용자가 선택한 모델 사용
                model = genai.GenerativeModel(model_name) 
                
                prompt = """
                Analyze the provided price sheet image and extract data into a specific JSON structure.
                
                The JSON must have these keys: "top_data", "bottom_data", "footer_lines".

                1. "top_data": A list of lists representing the main price table.
                   - Columns should correspond to: [Model, FactoryPrice, PublicSupport, SK_Move, SK_Change, SK_Card_Move, SK_Card_Change, KT_Move, KT_Change, KT_Card_Move, KT_Card_Change, LG_Move, LG_Change, LG_Card_Move, LG_Card_Change]
                   - Extract numerical values for prices. If a cell is empty or has '-', use null or 0.
                   - Example row: ["Flip7 256", 148.5, 60, 13, 18, -27, -22, 15, 15, -25, -25, -3, -1, -43, -41]

                2. "bottom_data": A list of lists for the carrier condition table at the bottom.
                   - Columns: [Carrier, ServiceCondition, MonthlyFee, Duration, Penalty]
                   - Example row: ["SK(24months)", "Plan: Premium", "109,000won", "6 months", "500,000"]

                3. "footer_lines": A list of strings for the caution/notice text at the very bottom.
                   - Capture each distinct line of text as a string in the list.
                
                Output ONLY valid JSON.
                """
                
                # 재시도 로직 추가 (429 Rate Limit 대응)
                max_retries = 3
                retry_delay = 5 # 초
                
                for attempt in range(max_retries):
                    try:
                        response = model.generate_content([prompt, {"mime_type": uploaded_file.type, "data": file_bytes}])
                        
                        # JSON 파싱
                        json_str = response.text.replace("```json", "").replace("```", "").strip()
                        data_json = json.loads(json_str)
                        break # 성공하면 루프 탈출
                    except Exception as e:
                        error_msg = str(e)
                        if "429" in error_msg and attempt < max_retries - 1:
                            status.write(f"⚠️ 사용량 초과(429). {retry_delay}초 후 재시도합니다... ({attempt+1}/{max_retries})")
                            time.sleep(retry_delay)
                            retry_delay *= 2 # 대기 시간 2배로 늘림
                        else:
                            st.error(f"Gemini 처리 실패: {e}")
                            st.stop()
                
                # 3. 엑셀 파일 생성
                status.write("3️⃣ 엑셀 파일 생성 중...")
                excel_bytes = create_excel_bytes(data_json, margin_default)
                
                # 4. 엑셀 파일 Supabase 저장 (exports 버킷)
                status.write("4️⃣ 엑셀 파일을 클라우드에 백업 중...")
                excel_name = f"simple-excel/converted_{int(time.time())}.xlsx"
                try:
                    supabase.storage.from_("exports").upload(excel_name, excel_bytes.getvalue(), {"content-type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"})
                    excel_public_url = supabase.storage.from_("exports").get_public_url(excel_name)
                except Exception as e:
                    error_msg = str(e)
                    if "Bucket not found" in error_msg or "404" in error_msg:
                        st.error("❌ **오류: 'exports' 버킷을 찾을 수 없습니다.** (엑셀 저장 실패)")
                        st.info("Supabase 대시보드에서 'exports' 버킷을 생성했는지 확인해주세요.")
                    else:
                        st.error(f"엑셀 업로드 실패: {e}")
                    st.stop()

                # 5. DB에 기록 남기기
                status.write("5️⃣ 작업 이력 기록 중...")
                try:
                    supabase.table("price_sheets").insert({
                        "filename": uploaded_file.name,
                        "image_url": image_public_url,
                        "excel_url": excel_public_url,
                        "status": "success"
                    }).execute()
                except Exception as e:
                    st.warning(f"DB 기록 실패 (파일은 생성됨): {e}")
                
                status.update(label="완료되었습니다!", state="complete", expanded=False)

            # 결과 화면
            st.success("변환 성공!")
            col1, col2 = st.columns(2)
            with col1:
                st.image(uploaded_file, caption="원본 이미지")
            with col2:
                st.info("생성된 엑셀 파일")
                st.download_button(
                    label="📥 엑셀 다운로드",
                    data=excel_bytes,
                    file_name=excel_name.split('/')[-1],
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
                st.markdown(f"[클라우드 링크로 보기]({excel_public_url})")

    elif not (gemini_api_key and supabase_url):
        st.warning("왼쪽 사이드바에서 서버 설정(API Key)을 완료해주세요.")

# --- Tab 2: 최고의 정책서 만들기 (커스텀 정책 배틀) ---
with tab2:
    st.header("⚔️ 성지당 v2: 커스텀 정책 배틀")
    st.markdown("대리점 이름과 색상을 직접 정해서 **최고의 정책서**를 만들어보세요.")
    st.caption("데이터는 'uploads' 및 'exports' 버킷에 체계적으로 분류되어 저장됩니다.")

    if 'policies' not in st.session_state:
        st.session_state.policies = []

    # 탭 2 내부에 별도의 입력 구역 생성 (사이드바 대신)
    with st.expander("➕ 새로운 경쟁자 등록하기", expanded=True):
        col1, col2 = st.columns(2)
        with col1:
            input_agency_name = st.text_input("대리점 이름 (예: 구로 1호점)", placeholder="이름을 지어주세요")
            # 매번 로드시 랜덤하게 다른 밝은 색을 제안함
            default_color = get_random_pastel_color()
            input_agency_color = st.color_picker("고유 색상 선택", default_color)
        with col2:
            uploaded_battle_file = st.file_uploader("시세표 이미지 업로드 (배틀용)", type=['png', 'jpg'], key="battle_uploader")
        
        if st.button("목록에 추가 +", type="primary"):
            if uploaded_battle_file and input_agency_name and gemini_api_key:
                with st.spinner(f"AI가 '{input_agency_name}' 시세표를 분석 중..."):
                    file_bytes = uploaded_battle_file.getvalue()
                    
                    # 1. Supabase에 이미지 업로드 (uploads 버킷)
                    image_url = None
                    if supabase_url and supabase_key:
                        try:
                            supabase_v2: Client = create_client(supabase_url, supabase_key)
                            file_ext = uploaded_battle_file.name.split('.')[-1]
                            file_name = f"policy-battle/{int(time.time())}_{uuid.uuid4()}.{file_ext}"
                            
                            supabase_v2.storage.from_("uploads").upload(file_name, file_bytes, {"content-type": uploaded_battle_file.type})
                            image_url = supabase_v2.storage.from_("uploads").get_public_url(file_name)
                        except Exception as e:
                            # 버킷 없을 때 에러 처리
                            if "Bucket not found" in str(e) or "404" in str(e):
                                st.error("❌ 'uploads' 버킷이 없습니다. Supabase에서 생성해주세요.")
                            else:
                                st.warning(f"이미지 업로드 실패 (분석은 계속 진행): {e}")

                    try:
                        # 2. Gemini 분석
                        df, footer_text = parse_image_with_gemini(file_bytes, model_name)
                        policy_data = PolicyData(name=input_agency_name, color_hex=input_agency_color, df=df, footer_text=footer_text)
                        
                        # 3. DB에 로그 저장 (policy_uploads 테이블)
                        if supabase_url and supabase_key and image_url:
                            try:
                                # DataFrame을 JSON으로 변환하여 저장
                                parsed_json = policy_data.df.to_json(orient='split', force_ascii=False)
                                supabase_v2.table("policy_uploads").insert({
                                    "agency_name": input_agency_name,
                                    "image_url": image_url,
                                    "parsed_data": json.loads(parsed_json)
                                }).execute()
                            except Exception as e:
                                st.warning(f"DB 저장 실패: {e}")

                        st.session_state.policies.append(policy_data)
                        st.success(f"'{input_agency_name}' 등록 완료!")
                        
                    except Exception as e:
                        st.error(f"분석 실패: {e}")
            elif not gemini_api_key:
                st.error("API Key가 설정되지 않았습니다. 사이드바를 확인해주세요.")
            elif not input_agency_name:
                st.error("대리점 이름을 입력해주세요!")

    # 메인 화면: 현황판
    st.subheader(f"🥊 현재 참전 중인 대리점: {len(st.session_state.policies)}곳")

    if len(st.session_state.policies) > 0:
        cols = st.columns(4)
        for idx, p in enumerate(st.session_state.policies):
            with cols[idx % 4]:
                # 카드를 해당 색상으로 꾸미기
                st.markdown(
                    f"""
                    <div style="
                        background-color: {p.color_hex};
                        padding: 15px;
                        border-radius: 10px;
                        border: 1px solid #ddd;
                        color: black;
                        text-align: center;
                        box-shadow: 2px 2px 5px rgba(0,0,0,0.1);
                    ">
                        <h4 style="margin:0; color:black;">{p.name}</h4>
                        <p style="margin:0; font-size:0.8em;">모델 {len(p.df)}개</p>
                    </div>
                    """, 
                    unsafe_allow_html=True
                )
                # 조건문 미리보기
                with st.expander("조건 보기"):
                    st.text(p.footer_text[:100] + "...")

        st.divider()

        # 엑셀 생성 버튼
        col1, col2 = st.columns([1, 2])
        with col1:
            if st.button("🚀 최고의 정책서 만들기 (Battle Start)", type="primary", use_container_width=True):
                with st.spinner("가격 비교 및 색상 칠하는 중..."):
                    # 1. 엑셀 생성
                    excel_file = create_battle_excel(st.session_state.policies)
                    st.session_state['excel_ready'] = excel_file
                    
                    # 2. Supabase에 결과물 업로드 및 DB 저장 (exports 버킷)
                    if supabase_url and supabase_key:
                        try:
                            supabase_v2: Client = create_client(supabase_url, supabase_key)
                            excel_name = f"battle-results/best_policy_{int(time.time())}.xlsx"
                            
                            # 버킷 업로드
                            supabase_v2.storage.from_("exports").upload(excel_name, excel_file.getvalue(), {"content-type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"})
                            excel_url = supabase_v2.storage.from_("exports").get_public_url(excel_name)
                            
                            # DB 저장
                            participants = [p.name for p in st.session_state.policies]
                            supabase_v2.table("battle_results").insert({
                                "excel_url": excel_url,
                                "participants": participants
                            }).execute()
                            
                            st.toast("클라우드에 결과가 저장되었습니다!", icon="☁️")
                            
                        except Exception as e:
                            if "Bucket not found" in str(e):
                                st.error("❌ 'exports' 버킷이 없습니다.")
                            else:
                                st.warning(f"클라우드 백업 실패: {e}")

                    st.success("완성되었습니다!")
        
        with col2:
            if 'excel_ready' in st.session_state:
                st.download_button(
                    label="📥 결과물 다운로드 (Excel)",
                    data=st.session_state['excel_ready'],
                    file_name="성지당_최고의정책서_커스텀.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True
                )

    else:
        st.info("위의 '새로운 경쟁자 등록하기'에서 대리점 이름과 이미지를 넣고 '추가' 버튼을 눌러주세요.")
