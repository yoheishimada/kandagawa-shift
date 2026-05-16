import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
import calendar
import datetime
import re
import json
import io
import time
import requests
import jwt as pyjwt
import jpholiday
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont

SPREADSHEET_ID = '1sVh4_9vbkucCRSenosYISpw_mFSsUioPLs0zBfxNT0U'
APP_PASSWORD = 'Kandagawa0222'
ADMIN_PASSWORD = '0222'

st.set_page_config(page_title='神田川ベーカリー シフト申請・調整アプリ', layout='wide')

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=Noto+Sans+JP:wght@300;400;500;700&display=swap');

html, body, [class*="css"] {
    font-family: 'Inter', 'Noto Sans JP', sans-serif;
}

.stApp { background-color: #f7f5f2; }

/* タイトル */
h1 {
    font-size: 2.2rem !important;
    font-weight: 700 !important;
    letter-spacing: -0.02em !important;
    color: #1a1a1a !important;
}
h2 {
    font-size: 0.75rem !important;
    font-weight: 600 !important;
    letter-spacing: 0.15em !important;
    text-transform: uppercase !important;
    color: #888 !important;
    margin-top: 2.5rem !important;
}

/* サイドバー */
[data-testid="stSidebar"] {
    background-color: #ffffff !important;
    border-right: 1px solid #e8e4de !important;
}

/* ボタン */
.stButton > button {
    background-color: #1a1a1a !important;
    color: #ffffff !important;
    border: none !important;
    border-radius: 6px !important;
    font-weight: 500 !important;
    font-size: 0.62rem !important;
    letter-spacing: 0.06em !important;
    padding: 0.2rem 0.7rem !important;
    transition: opacity 0.2s ease !important;
}
.stButton > button:hover {
    opacity: 0.7 !important;
}

/* 入力 */
.stTextArea textarea, .stTextInput input {
    background-color: #ffffff !important;
    border: 1px solid #e0dbd4 !important;
    border-radius: 0px !important;
    color: #1a1a1a !important;
    font-size: 0.9rem !important;
}

/* カレンダー */
.cal-table { background: #f7f5f2 !important; }
.cal-header {
    background: #1a1a1a !important;
    color: #ffffff !important;
    letter-spacing: 0.08em;
    font-size: 12px !important;
    font-weight: 500 !important;
}
.cal-cell { border-color: #e8e4de !important; background: #ffffff; }
.cal-empty { background: #f0ece6 !important; }
.cal-date { color: #1a1a1a !important; font-size: 18px !important; font-weight: 700 !important; }
.cal-section {
    color: #aaa !important;
    border-top-color: #f0ece6 !important;
    font-size: 9px !important;
    letter-spacing: 0.12em;
    text-transform: uppercase;
}
.cal-name { font-size: 12px !important; border-radius: 0px !important; }
.cal-none { color: #ccc !important; }

/* multiselect タグ：白抜き */
[data-baseweb="tag"] {
    background-color: #ffffff !important;
    border: 1px solid #1a1a1a !important;
    border-radius: 4px !important;
}
[data-baseweb="tag"] span {
    color: #1a1a1a !important;
}
[data-baseweb="tag"] [role="presentation"] svg {
    fill: #1a1a1a !important;
}

/* multipage ナビ非表示 */
[data-testid="stSidebarNav"] { display: none !important; }

/* セパレーター */
hr { border-color: #e8e4de !important; }

/* caption */
.stCaption { color: #aaa !important; font-size: 0.72rem !important; letter-spacing: 0.05em; }

/* progress */
.stProgress > div > div { background-color: #1a1a1a !important; }
</style>
""", unsafe_allow_html=True)

# --- マニュアル直接表示（認証不要）---
if st.query_params.get('view') == 'manual':
    try:
        with open('管理者マニュアル.md', 'r', encoding='utf-8') as f:
            st.markdown(f.read())
    except:
        st.error('マニュアルを読み込めませんでした。')
    st.stop()

# --- パスワード保護 ---
if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False

if not st.session_state.authenticated:
    st.markdown("""
    <div style='padding: 2rem 0 1.5rem 0; border-bottom: 1px solid #e8e4de; margin-bottom: 1.5rem;'>
      <div style='font-size:0.65rem;letter-spacing:0.3em;color:#aaa;text-transform:uppercase;margin-bottom:0.6rem;'>Kandagawa Bakery</div>
      <div style='font-size:1.6rem;font-weight:600;letter-spacing:0.02em;color:#1a1a1a;line-height:1;'>シフト申請・調整アプリ</div>
    </div>
    """, unsafe_allow_html=True)
    col, _ = st.columns([1, 2])
    with col:
        pw = st.text_input('パスワードを入力してください', type='password')
        if st.button('ログイン', use_container_width=False):
            if pw == APP_PASSWORD:
                st.session_state.authenticated = True
                st.rerun()
            else:
                st.error('パスワードが違います')
    st.stop()

# --- 認証済み以降の処理 ---
st.markdown("""
<div style='padding: 2rem 0 1.5rem 0; border-bottom: 1px solid #e8e4de; margin-bottom: 1.5rem;'>
  <div style='font-size:0.65rem;letter-spacing:0.3em;color:#aaa;text-transform:uppercase;margin-bottom:0.6rem;'>Kandagawa Bakery</div>
  <div style='font-size:1.6rem;font-weight:600;letter-spacing:0.02em;color:#1a1a1a;line-height:1;'>ダッシュボード</div>
</div>
""", unsafe_allow_html=True)

# サイドバー：管理者ログイン
with st.sidebar:
    st.header('管理者メニュー')
    admin_pw = st.text_input('管理者パスワード')
    is_admin = (admin_pw == ADMIN_PASSWORD)
    if admin_pw and not is_admin:
        st.error('パスワードが違います')
    if is_admin:
        st.success('管理者モード')
    if st.button('ログアウト'):
        st.session_state.authenticated = False
        st.rerun()
    st.markdown('---')
    st.markdown("<a href='?view=manual' target='_blank' style='display:inline-block;background:#1a1a1a;color:#fff;font-size:0.62rem;font-weight:500;letter-spacing:0.06em;padding:0.3rem 1rem;border-radius:6px;text-decoration:none;'>使い方マニュアル</a>", unsafe_allow_html=True)

@st.cache_data(ttl=300)
def load_data():
    # Streamlit Cloud環境ではst.secretsを使用、ローカルではJSONファイルを使用
    try:
        credentials_info = dict(st.secrets['gcp_service_account'])
        creds = Credentials.from_service_account_info(credentials_info, scopes=[
            'https://www.googleapis.com/auth/spreadsheets',
            'https://www.googleapis.com/auth/drive',
        ])
    except Exception:
        KEY_FILE = '/Users/shimadayohei/kandagawa-bakery/kandagawa_shift_key.json'
        creds = Credentials.from_service_account_file(KEY_FILE, scopes=[
            'https://www.googleapis.com/auth/spreadsheets',
            'https://www.googleapis.com/auth/drive',
        ])

    gc = gspread.authorize(creds)
    sh = gc.open_by_key(SPREADSHEET_ID)
    sheet = None
    for ws in sh.worksheets():
        if 'Form' in ws.title or 'フォーム' in ws.title:
            sheet = ws
            break
    if sheet is None:
        return None
    values = sheet.get_all_values()
    if len(values) < 2:
        return None
    headers = values[0]
    # フォームを作り直すと古い列が残るため、最後の「お名前」列以降を使用
    last_name_idx = None
    for i, h in enumerate(headers):
        if h == 'お名前':
            last_name_idx = i
    if last_name_idx is None:
        return None
    relevant_headers = headers[last_name_idx:]
    relevant_data = [row[last_name_idx:] for row in values[1:]]
    df = pd.DataFrame(relevant_data, columns=relevant_headers)
    df = df[df['お名前'] != '']  # 名前が空の行を除外
    # 同一スタッフの複数回答をマージ（どちらかの回答で〇なら〇）
    date_cols = [c for c in df.columns if 'シフト希望' in c]
    merged_rows = []
    for name, group in df.groupby('お名前', sort=False):
        row = {'お名前': name}
        for col in date_cols:
            has_early = any('早番' in str(v) for v in group[col])
            has_late = any('遅番' in str(v) for v in group[col])
            if has_early and has_late:
                row[col] = '早番,遅番'
            elif has_early:
                row[col] = '早番'
            elif has_late:
                row[col] = '遅番'
            else:
                row[col] = ''
        merged_rows.append(row)
    df = pd.DataFrame(merged_rows, columns=['お名前'] + date_cols)
    return df if not df.empty else None

@st.cache_data(ttl=300)
def load_staff():
    try:
        credentials_info = dict(st.secrets['gcp_service_account'])
        creds = Credentials.from_service_account_info(credentials_info, scopes=[
            'https://www.googleapis.com/auth/spreadsheets',
            'https://www.googleapis.com/auth/drive',
        ])
    except Exception:
        KEY_FILE = '/Users/shimadayohei/kandagawa-bakery/kandagawa_shift_key.json'
        creds = Credentials.from_service_account_file(KEY_FILE, scopes=[
            'https://www.googleapis.com/auth/spreadsheets',
            'https://www.googleapis.com/auth/drive',
        ])
    gc = gspread.authorize(creds)
    sh = gc.open_by_key(SPREADSHEET_ID)
    staff_sheet = sh.worksheet('スタッフ')
    names = staff_sheet.col_values(1)[1:]
    return [n for n in names if n]

def get_lineworks_token():
    """LINE WORKS Service Account認証でアクセストークンを取得"""
    try:
        lw = st.secrets["lineworks"]
        client_id = lw["client_id"]
        client_secret = lw["client_secret"]
        service_account = lw["service_account"]
        private_key = lw["private_key"]
    except Exception as e:
        return None, f"LINE WORKS secrets設定エラー: {e}"

    payload = {
        "iss": client_id,
        "sub": service_account,
        "iat": int(time.time()),
        "exp": int(time.time()) + 3600,
    }
    try:
        jwt_token = pyjwt.encode(payload, private_key, algorithm="RS256")
    except Exception as e:
        return None, f"JWT生成エラー: {e}"

    try:
        resp = requests.post(
            "https://auth.worksmobile.com/oauth2/v2.0/token",
            data={
                "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
                "assertion": jwt_token,
                "client_id": client_id,
                "client_secret": client_secret,
                "scope": "bot user",
            },
            timeout=10,
        )
        data = resp.json()
        if "access_token" in data:
            return data["access_token"], None
        return None, f"トークン取得失敗: {data}"
    except Exception as e:
        return None, f"LINE WORKS APIエラー: {e}"


def get_lineworks_users(access_token, domain_id):
    """LINE WORKS全ユーザー一覧を取得（ページング対応）"""
    users = []
    cursor = None
    for _ in range(20):  # 最大2000人
        params = {"domainId": domain_id, "count": 100}
        if cursor:
            params["cursor"] = cursor
        resp = requests.get(
            "https://www.worksapis.com/v1.0/users",
            headers={"Authorization": f"Bearer {access_token}"},
            params=params,
            timeout=10,
        )
        data = resp.json()
        users.extend(data.get("users", []))
        cursor = data.get("responseMetaData", {}).get("nextCursor")
        if not cursor:
            break
    return users


def send_lineworks_dm(access_token, bot_id, user_id, message):
    """LINE WORKSユーザーにDMを送信。(status_code, response_body)を返す"""
    resp = requests.post(
        f"https://www.worksapis.com/v1.0/bots/{bot_id}/users/{user_id}/messages",
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        },
        json={"content": {"type": "text", "text": message}},
        timeout=10,
    )
    try:
        body = resp.json()
    except Exception:
        body = {}
    return resp.status_code, body


def build_daily_shifts(df):
    date_cols = [c for c in df.columns if 'シフト希望' in c]
    daily = {}
    for col in date_cols:
        date_label = col.replace('シフト希望 [', '').replace(']', '').strip()
        early_staff, late_staff = [], []
        for _, row in df.iterrows():
            val = str(row[col])
            name = row['お名前']
            if '早番' in val:
                early_staff.append(name)
            if '遅番' in val:
                late_staff.append(name)
        daily[date_label] = {'早': early_staff, '遅': late_staff}
    return daily

STAFF_COLOR_PALETTE = [
    ('#FF6B6B', 'white'), ('#4ECDC4', 'white'), ('#45B7D1', 'white'),
    ('#A29BFE', 'white'), ('#FECA57', '#333'),  ('#FF9FF3', '#333'),
    ('#54A0FF', 'white'), ('#5F27CD', 'white'), ('#00D2D3', 'white'),
    ('#FF9F43', 'white'), ('#10AC84', 'white'), ('#EE5A24', 'white'),
    ('#C4E538', '#333'),  ('#9980FA', 'white'), ('#F368E0', 'white'),
]

def get_staff_colors(staff_list):
    return {
        name: STAFF_COLOR_PALETTE[i % len(STAFF_COLOR_PALETTE)]
        for i, name in enumerate(staff_list)
    }

def render_calendar(daily_shifts, year, month, staff_colors=None):
    _, days_in_month = calendar.monthrange(year, month)
    first_weekday = calendar.weekday(year, month, 1)
    day_names = ['月', '火', '水', '木', '金', '土', '日']
    if staff_colors is None:
        staff_colors = {}

    html = """
    <style>
    .cal-wrap { overflow-x: auto; }
    .cal-table { width: 100%; border-collapse: collapse; table-layout: fixed; }
    .cal-header { background: #1a1a1a; color: white !important; text-align: center;
                  padding: 10px 4px; font-weight: bold !important; font-size: 15px !important;
                  text-transform: none !important; letter-spacing: normal !important; margin: 0 !important; }
    .cal-header-sat { background: #4a90d9; color: white !important; text-align: center;
                      padding: 10px 4px; font-weight: bold !important; font-size: 15px !important;
                      text-transform: none !important; letter-spacing: normal !important; margin: 0 !important; }
    .cal-header-sun { background: #e07070; color: white !important; text-align: center;
                      padding: 10px 4px; font-weight: bold !important; font-size: 15px !important;
                      text-transform: none !important; letter-spacing: normal !important; margin: 0 !important; }
    .cal-cell { border: 1px solid #e8e4de; vertical-align: top;
                padding: 6px 4px; min-height: 100px; background: #fff; }
    .cal-sat { background: #e8f4fd !important; }
    .cal-sun { background: #fdeaea !important; }
    .cal-empty { background: #f0f0f0; }
    .cal-date { font-weight: bold; font-size: 15px; margin-bottom: 4px; color: #333; }
    .cal-date-sat { font-weight: 700; font-size: 18px; margin-bottom: 4px; color: #4a90d9; }
    .cal-date-sun { font-weight: 700; font-size: 18px; margin-bottom: 4px; color: #e07070; }
    .cal-section { font-size: 10px; color: #888; margin-top: 4px; border-top: 1px solid #eee; padding-top: 2px; }
    .cal-name { border-radius: 3px; padding: 2px 5px; margin: 2px 0;
                font-size: 11px; display: block; font-weight: bold; }
    .cal-none { color: #bbb; font-size: 11px; }
    </style>
    <div class='cal-wrap'>
    <table class='cal-table'>
    <tr>
    """
    for i, d in enumerate(day_names):
        if i == 5:
            html += f"<th class='cal-header-sat'>{d}</th>"
        elif i == 6:
            html += f"<th class='cal-header-sun'>{d}</th>"
        else:
            html += f"<th class='cal-header'>{d}</th>"
    html += "</tr>"

    day = 1
    for week in range(6):
        if day > days_in_month:
            break
        html += "<tr>"
        for weekday in range(7):
            if (week == 0 and weekday < first_weekday) or day > days_in_month:
                html += "<td class='cal-cell cal-empty'></td>"
            else:
                wd = calendar.weekday(year, month, day)
                wname = day_names[wd]
                date_label = f"{month}月{day}日（{wname}）"
                shifts = daily_shifts.get(date_label, {'早': [], '遅': []})
                early = shifts['早']
                late = shifts['遅']

                is_sat = (wd == 5)
                is_sun = (wd == 6)
                is_holiday = jpholiday.is_holiday(datetime.date(year, month, day))
                is_red = is_sun or is_holiday

                cell_class = 'cal-sat' if is_sat else ('cal-sun' if is_red else '')
                date_class = 'cal-date-sat' if is_sat else ('cal-date-sun' if is_red else 'cal-date')

                html += f"<td class='cal-cell {cell_class}'>"
                html += f"<div class='{date_class}'>{day}</div>"

                if early:
                    html += "<div class='cal-section'>早番</div>"
                    for n in early:
                        bg, fg = staff_colors.get(n, ('#d4edda', '#155724'))
                        html += f"<span class='cal-name' style='background:{bg};color:{fg}'>{n}</span>"
                if late:
                    html += "<div class='cal-section'>遅番</div>"
                    for n in late:
                        bg, fg = staff_colors.get(n, ('#cce5ff', '#004085'))
                        html += f"<span class='cal-name' style='background:{bg};color:{fg}'>{n}</span>"
                if not early and not late:
                    html += "<div class='cal-none'>ー</div>"

                html += "</td>"
                day += 1
        html += "</tr>"

    html += "</table></div>"
    return html

def build_admin_ranking(df, date_cols):
    stats = {}
    for _, row in df.iterrows():
        name = row['お名前']
        early = sum(1 for col in date_cols if '早番' in str(row[col]))
        late  = sum(1 for col in date_cols if '遅番' in str(row[col]))
        total = early + late
        if name not in stats:
            stats[name] = {'早番日数': 0, '遅番日数': 0, '合計日数': 0}
        stats[name]['早番日数'] += early
        stats[name]['遅番日数'] += late
        stats[name]['合計日数'] += total
    rank_df = pd.DataFrame(stats).T.sort_values('合計日数', ascending=False).astype(int)
    return rank_df

def generate_staff_manual_pdf():
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, HRFlowable, Table, TableStyle
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.lib import colors
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.cidfonts import UnicodeCIDFont
    from reportlab.lib.pagesizes import A4

    pdfmetrics.registerFont(UnicodeCIDFont('HeiseiKakuGo-W5'))
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4,
                            leftMargin=16*mm, rightMargin=16*mm,
                            topMargin=12*mm, bottomMargin=12*mm)

    F = 'HeiseiKakuGo-W5'
    BLACK  = colors.HexColor('#1a1a1a')
    GRAY   = colors.HexColor('#888888')
    LGRAY  = colors.HexColor('#f5f5f5')
    ACCENT = colors.HexColor('#4a90d9')
    GREEN  = colors.HexColor('#10AC84')
    WHITE  = colors.white

    def ps(name, size, color=BLACK, align=0, leading=None):
        return ParagraphStyle(name, fontName=F, fontSize=size,
                              textColor=color, alignment=align,
                              leading=leading or size * 1.5)

    W = 178*mm  # 有効幅

    elems = []

    # ── タイトル ──
    elems.append(Paragraph('KANDAGAWA BAKERY', ps('sub', 7, GRAY, align=1)))
    elems.append(Spacer(1, 1*mm))
    elems.append(Paragraph('シフト申請マニュアル', ps('ttl', 18, BLACK, align=1)))
    elems.append(Spacer(1, 2*mm))
    elems.append(HRFlowable(width='100%', thickness=1.5, color=BLACK))
    elems.append(Spacer(1, 5*mm))

    # ── フロー図（横並び） ──
    elems.append(Paragraph('申請の流れ', ps('lbl', 8, GRAY)))
    elems.append(Spacer(1, 2*mm))

    def flow_box(text, bg, fg=WHITE, size=8):
        return Paragraph(text, ParagraphStyle('fb', fontName=F, fontSize=size,
                         textColor=fg, alignment=1, leading=size*1.4))

    arrow = Paragraph('→', ps('arr', 10, GRAY, align=1))

    flow_items = [
        ('毎月\n25日', ACCENT),
        ('LINE WORKSに\n吉田さんから\nメッセージ届く', BLACK),
        ('リンクを\nタップ', BLACK),
        ('フォームで\n希望を入力・\n送信', BLACK),
        ('完了！', GREEN),
    ]

    bw = 28*mm
    aw = 8*mm
    row = []
    for i, (text, bg) in enumerate(flow_items):
        cell = Table([[flow_box(text, bg)]], colWidths=[bw], rowHeights=[16*mm])
        cell.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,-1), bg),
            ('VALIGN',     (0,0), (-1,-1), 'MIDDLE'),
            ('BOX',        (0,0), (-1,-1), 0.5, WHITE),
        ]))
        row.append(cell)
        if i < len(flow_items) - 1:
            row.append(Table([[arrow]], colWidths=[aw], rowHeights=[16*mm]))

    col_widths = []
    for i in range(len(flow_items)):
        col_widths.append(bw)
        if i < len(flow_items) - 1:
            col_widths.append(aw)

    flow_tbl = Table([row], colWidths=col_widths)
    flow_tbl.setStyle(TableStyle([('VALIGN', (0,0), (-1,-1), 'MIDDLE')]))
    elems.append(flow_tbl)
    elems.append(Spacer(1, 6*mm))
    elems.append(HRFlowable(width='100%', thickness=0.5, color=LGRAY))
    elems.append(Spacer(1, 5*mm))

    # ── 2カラムレイアウト（入力方法 | 再申請・注意） ──
    def section_title(text):
        return Paragraph(text, ps('sh', 9, GRAY))

    def body(text):
        return Paragraph(text, ps('bd', 8, BLACK, leading=13))

    def step_row(num, title, desc):
        num_cell  = Paragraph(num,   ps('n',  9, ACCENT, align=1))
        text_cell = Paragraph(f'<b>{title}</b><br/>{desc}',
                              ParagraphStyle('sc', fontName=F, fontSize=8,
                                            textColor=BLACK, leading=12))
        t = Table([[num_cell, text_cell]], colWidths=[7*mm, 73*mm])
        t.setStyle(TableStyle([('VALIGN', (0,0), (-1,-1), 'TOP'),
                                ('TOPPADDING', (0,0), (-1,-1), 1),
                                ('BOTTOMPADDING', (0,0), (-1,-1), 3)]))
        return t

    # 左カラム：フォーム入力方法
    left = [
        section_title('フォームの入力方法'),
        Spacer(1, 2*mm),
        step_row('①', '名前を選ぶ', 'リストから自分の名前を選ぶ'),
        Spacer(1, 1*mm),
        step_row('②', 'シフトにチェック',
                 '早番（10〜15時）\n遅番（15〜19時）\n両方入れる日は両方チェック'),
        Spacer(1, 1*mm),
        step_row('③', '送信する', '一番下の「送信」ボタンを押して完了'),
    ]

    # 右カラム：再申請・締め切り・問い合わせ
    right = [
        section_title('再申請を求められたとき'),
        Spacer(1, 2*mm),
        body('再申請は「上書き」ではなく「追加」です。\n最初の申請内容はそのまま残るので、'
             '新たに入れる日だけチェックして送信してください。'),
        Spacer(1, 4*mm),
        section_title('締め切り'),
        Spacer(1, 2*mm),
        body('フォームの説明文に記載されています。\n届いてから約10日以内を目安に回答してください。'),
        Spacer(1, 4*mm),
        section_title('困ったときは'),
        Spacer(1, 2*mm),
        body('吉田さんに連絡してください。'),
    ]

    def build_col(items):
        from reportlab.platypus import KeepTogether
        tbl_data = [[item] for item in items]
        t = Table(tbl_data, colWidths=[83*mm])
        t.setStyle(TableStyle([
            ('VALIGN',        (0,0), (-1,-1), 'TOP'),
            ('LEFTPADDING',   (0,0), (-1,-1), 0),
            ('RIGHTPADDING',  (0,0), (-1,-1), 0),
            ('TOPPADDING',    (0,0), (-1,-1), 0),
            ('BOTTOMPADDING', (0,0), (-1,-1), 0),
        ]))
        return t

    divider = Table([['']], colWidths=[0.5*mm], rowHeights=[60*mm])
    divider.setStyle(TableStyle([('BACKGROUND', (0,0), (-1,-1), LGRAY)]))

    two_col = Table(
        [[build_col(left), divider, build_col(right)]],
        colWidths=[83*mm, 6*mm, 83*mm]
    )
    two_col.setStyle(TableStyle([('VALIGN', (0,0), (-1,-1), 'TOP')]))
    elems.append(two_col)

    doc.build(elems)
    return buf.getvalue()

def generate_shift_pdf(daily_shifts, year, month, staff_colors=None):
    if staff_colors is None:
        staff_colors = {}

    pdfmetrics.registerFont(UnicodeCIDFont('HeiseiKakuGo-W5'))
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=landscape(A4),
                            leftMargin=12*mm, rightMargin=12*mm,
                            topMargin=10*mm, bottomMargin=8*mm)

    def hex_to_color(h):
        h = h.lstrip('#')
        if len(h) == 3:
            h = h[0]*2 + h[1]*2 + h[2]*2
        return colors.Color(int(h[0:2],16)/255, int(h[2:4],16)/255, int(h[4:6],16)/255)

    title_style = ParagraphStyle('title', fontName='HeiseiKakuGo-W5', fontSize=11,
                                 leading=16, textColor=colors.HexColor('#1a1a1a'))
    label_style = ParagraphStyle('label', fontName='HeiseiKakuGo-W5', fontSize=6,
                                 leading=8, textColor=colors.HexColor('#999999'))
    date_style  = ParagraphStyle('date',  fontName='HeiseiKakuGo-W5', fontSize=10,
                                 leading=13, textColor=colors.HexColor('#1a1a1a'))
    header_style = ParagraphStyle('hdr',  fontName='HeiseiKakuGo-W5', fontSize=9,
                                  leading=12, textColor=colors.white, alignment=1)

    def name_para(name):
        bg_hex, fg = staff_colors.get(name, ('#e0e0e0', '#333333'))
        fg_hex = '#ffffff' if fg == 'white' else fg
        style = ParagraphStyle(
            f'n_{name}', fontName='HeiseiKakuGo-W5', fontSize=7, leading=10,
            textColor=hex_to_color(fg_hex),
            backColor=hex_to_color(bg_hex),
            leftPadding=3, rightPadding=3, topPadding=1, bottomPadding=1,
            spaceAfter=1,
        )
        return Paragraph(name, style)

    day_names   = ['月', '火', '水', '木', '金', '土', '日']
    _, days_in_month = calendar.monthrange(year, month)
    first_weekday = calendar.weekday(year, month, 1)

    # ヘッダー行
    header_row = [Paragraph(d, header_style) for d in day_names]
    table_data = [header_row]

    day = 1
    for week in range(6):
        if day > days_in_month:
            break
        row = []
        for weekday in range(7):
            if (week == 0 and weekday < first_weekday) or day > days_in_month:
                row.append('')
            else:
                wname = day_names[calendar.weekday(year, month, day)]
                date_label = f'{month}月{day}日（{wname}）'
                shifts = daily_shifts.get(date_label, {'早': [], '遅': []})

                cell_items = [Paragraph(f'<b>{day}</b>', date_style)]
                if shifts['早']:
                    cell_items.append(Paragraph('早番', label_style))
                    for n in shifts['早']:
                        cell_items.append(name_para(n))
                if shifts['遅']:
                    cell_items.append(Spacer(1, 2))
                    cell_items.append(Paragraph('遅番', label_style))
                    for n in shifts['遅']:
                        cell_items.append(name_para(n))

                row.append(cell_items)
                day += 1
        table_data.append(row)

    col_width  = (landscape(A4)[0] - 24*mm) / 7
    row_height = (landscape(A4)[1] - 28*mm) / (len(table_data))

    t = Table(table_data, colWidths=[col_width]*7,
              rowHeights=[8*mm] + [row_height]*(len(table_data)-1))

    ts = TableStyle([
        ('FONTNAME',    (0,0), (-1,-1), 'HeiseiKakuGo-W5'),
        ('BACKGROUND',  (0,0), (-1,0),  colors.HexColor('#1a1a1a')),
        ('TEXTCOLOR',   (0,0), (-1,0),  colors.white),
        ('ALIGN',       (0,0), (-1,0),  'CENTER'),
        ('VALIGN',      (0,0), (-1,-1), 'TOP'),
        ('GRID',        (0,0), (-1,-1), 0.3, colors.HexColor('#e0dbd4')),
        ('BACKGROUND',  (5,1), (5,-1),  colors.HexColor('#fdf5f5')),
        ('BACKGROUND',  (6,1), (6,-1),  colors.HexColor('#f5f5fd')),
        ('TOPPADDING',  (0,0), (-1,-1), 4),
        ('LEFTPADDING', (0,0), (-1,-1), 4),
        ('BOTTOMPADDING',(0,0),(-1,-1), 4),
    ])
    t.setStyle(ts)

    elements = [
        Paragraph(f'神田川ベーカリー　{year}年{month}月 シフト表', title_style),
        Spacer(1, 4*mm),
        t,
    ]
    doc.build(elements)
    buf.seek(0)
    return buf.read()

# --- メイン ---
df = load_data()

if df is None:
    st.warning('まだ回答がありません。スタッフがフォームを送信すると表示されます。')
else:
    all_date_cols = [c for c in df.columns if 'シフト希望' in c]

    # 最新月・年を自動取得
    latest_year, latest_month = 2000, 1
    for col in all_date_cols:
        m = re.search(r'(\d{4})年(\d+)月', col)
        if m:
            y, mo = int(m.group(1)), int(m.group(2))
        else:
            m2 = re.search(r'(\d+)月', col)
            mo = int(m2.group(1)) if m2 else 1
            import datetime
            y = datetime.date.today().year
        if (y, mo) > (latest_year, latest_month):
            latest_year, latest_month = y, mo
    year, month = latest_year, latest_month

    # 最新月の列だけ絞り込む
    date_cols = [c for c in all_date_cols if f'{month}月' in c]
    if not date_cols:
        date_cols = all_date_cols

    all_staff = load_staff()
    submitted = set(df['お名前'].tolist())
    not_submitted = [n for n in all_staff if n not in submitted]

    daily_shifts = build_daily_shifts(df)
    staff_colors = get_staff_colors(all_staff)

    # KPIカード計算
    _, days_in_month_kpi = calendar.monthrange(year, month)
    total_slots = days_in_month_kpi * 2  # 早番+遅番
    filled_slots = sum(
        (1 if daily_shifts.get(f'{month}月{d}日（{"月火水木金土日"[calendar.weekday(year,month,d)]}）', {}).get('早') else 0) +
        (1 if daily_shifts.get(f'{month}月{d}日（{"月火水木金土日"[calendar.weekday(year,month,d)]}）', {}).get('遅') else 0)
        for d in range(1, days_in_month_kpi + 1)
    )
    shortage_days = sum(
        1 for d in range(1, days_in_month_kpi + 1)
        if not daily_shifts.get(f'{month}月{d}日（{"月火水木金土日"[calendar.weekday(year,month,d)]}）', {}).get('早')
        or not daily_shifts.get(f'{month}月{d}日（{"月火水木金土日"[calendar.weekday(year,month,d)]}）', {}).get('遅')
    )
    total_shifts = sum(
        len(v.get('早', [])) + len(v.get('遅', []))
        for v in daily_shifts.values()
    )
    fulfillment = int(filled_slots / total_slots * 100) if total_slots > 0 else 0

    kpi_color = '#10AC84' if fulfillment >= 80 else ('#FECA57' if fulfillment >= 50 else '#FF6B6B')
    shortage_color = '#FF6B6B' if shortage_days > 0 else '#10AC84'

    st.markdown(f"""
<div style='display:flex;gap:16px;margin:1.2rem 0 1.6rem 0;flex-wrap:wrap;'>
  <div style='flex:1;min-width:140px;background:#fff;border-radius:8px;padding:20px 24px;border:1px solid #e8e4de;'>
    <div style='font-size:0.65rem;letter-spacing:0.15em;text-transform:uppercase;color:#aaa;margin-bottom:8px;'>回答済み</div>
    <div style='font-size:2rem;font-weight:700;color:#1a1a1a;line-height:1;'>{len(submitted)}<span style='font-size:1rem;font-weight:400;color:#888;margin-left:4px;'>名</span></div>
    <div style='font-size:0.75rem;color:#bbb;margin-top:6px;'>未提出 {len(not_submitted)}名</div>
  </div>
  <div style='flex:1;min-width:140px;background:#fff;border-radius:8px;padding:20px 24px;border:1px solid #e8e4de;'>
    <div style='font-size:0.65rem;letter-spacing:0.15em;text-transform:uppercase;color:#aaa;margin-bottom:8px;'>シフト充足率</div>
    <div style='font-size:2rem;font-weight:700;color:{kpi_color};line-height:1;'>{fulfillment}<span style='font-size:1rem;font-weight:400;color:#888;margin-left:2px;'>%</span></div>
    <div style='font-size:0.75rem;color:#bbb;margin-top:6px;'>{filled_slots} / {total_slots} 枠</div>
  </div>
  <div style='flex:1;min-width:140px;background:#fff;border-radius:8px;padding:20px 24px;border:1px solid #e8e4de;'>
    <div style='font-size:0.65rem;letter-spacing:0.15em;text-transform:uppercase;color:#aaa;margin-bottom:8px;'>シフト希望なしの日</div>
    <div style='font-size:2rem;font-weight:700;color:{shortage_color};line-height:1;'>{shortage_days}<span style='font-size:1rem;font-weight:400;color:#888;margin-left:4px;'>日</span></div>
    <div style='font-size:0.75rem;color:#bbb;margin-top:6px;'>早番または遅番が0名</div>
  </div>
  <div style='flex:1;min-width:140px;background:#fff;border-radius:8px;padding:20px 24px;border:1px solid #e8e4de;'>
    <div style='font-size:0.65rem;letter-spacing:0.15em;text-transform:uppercase;color:#aaa;margin-bottom:8px;'>総シフト数</div>
    <div style='font-size:2rem;font-weight:700;color:#1a1a1a;line-height:1;'>{total_shifts}<span style='font-size:1rem;font-weight:400;color:#888;margin-left:4px;'>コマ</span></div>
    <div style='font-size:0.75rem;color:#bbb;margin-top:6px;'>全スタッフ合計</div>
  </div>
</div>
<div style='font-size:0.7rem;color:#ccc;margin-bottom:1.2rem;'>※5分ごとに自動更新</div>
""", unsafe_allow_html=True)

    if not_submitted:
        badges = ''.join(
            f"<span style='background:{staff_colors.get(n, ('#e0e0e0','#333'))[0]};color:{staff_colors.get(n, ('#e0e0e0','#333'))[1]};border-radius:4px;padding:3px 10px;font-size:12px;font-weight:bold;white-space:nowrap;'>{n}</span>"
            for n in not_submitted
        )
        st.markdown(f"""
<div style='background:#fff;border:1px solid #e8e4de;border-radius:8px;padding:16px 20px;margin-bottom:1rem;'>
  <div style='font-size:0.65rem;letter-spacing:0.15em;text-transform:uppercase;color:#aaa;margin-bottom:10px;'>未提出のスタッフ</div>
  <div style='display:flex;flex-wrap:wrap;gap:6px;'>{badges}</div>
</div>
""", unsafe_allow_html=True)

    st.subheader(f'{year}年{month}月 シフト申請状況')
    st.markdown(render_calendar(daily_shifts, year, month, staff_colors), unsafe_allow_html=True)

    if is_admin:
        st.markdown('---')
        st.subheader('シフト希望なし')
        shortage_rows = []
        _, days_in_month = calendar.monthrange(year, month)
        day_names_list = ['月', '火', '水', '木', '金', '土', '日']
        for d in range(1, days_in_month + 1):
            wname = day_names_list[calendar.weekday(year, month, d)]
            date_label = f'{month}月{d}日（{wname}）'
            shifts = daily_shifts.get(date_label, {'早': [], '遅': []})
            if not shifts['早']:
                shortage_rows.append({'日付': date_label, 'シフト': '早番（10〜15時）'})
            if not shifts['遅']:
                shortage_rows.append({'日付': date_label, 'シフト': '遅番（15〜19時）'})

        if shortage_rows:
            shortage_df = pd.DataFrame(shortage_rows)
            # 日付ごとに1行にまとめる
            pivot_rows = []
            _, days_in_month2 = calendar.monthrange(year, month)
            for d in range(1, days_in_month2 + 1):
                wname = day_names_list[calendar.weekday(year, month, d)]
                date_label = f'{month}月{d}日（{wname}）'
                shifts = daily_shifts.get(date_label, {'早': [], '遅': []})
                early_short = not shifts['早']
                late_short = not shifts['遅']
                if early_short or late_short:
                    pivot_rows.append({
                        '日付': date_label,
                        '早番（10〜15時）': '希望なし' if early_short else '',
                        '遅番（15〜19時）': '希望なし' if late_short else '',
                    })
            pivot_df = pd.DataFrame(pivot_rows)
            st.dataframe(pivot_df, use_container_width=True, hide_index=True)
            csv = pivot_df.to_csv(index=False, encoding='utf-8-sig')
            st.download_button(
                label='CSVでダウンロード',
                data=csv,
                file_name=f'shortage_{year}_{month:02d}.csv',
                mime='text/csv',
            )

            st.markdown('---')
            st.subheader('LINE WORKSメッセージ送信')

            shortage_lines = '\n'.join(
                f"・{r['日付']}　{r['シフト']}" for r in shortage_rows
            )
            default_msg = (
                f"【シフト再調整の協力のお願い】\n\n"
                f"{year}年{month}月の以下の日程でシフトが不足しています。\n"
                f"不足している日の出勤に協力をお願いします。\n\n"
                f"すでに申請いただいた日はチェックしなくても大丈夫です。\n"
                f"以下の日程で調整が可能な日があれば追加でチェックの上送信してください。\n"
                f"再申請の際に早番・遅番フル出勤が難しい場合でも、吉田まで相談いただけると嬉しいです。\n\n"
                f"{shortage_lines}"
            )

            def do_lw_send(targets, message):
                with st.spinner('LINE WORKSに接続中...'):
                    token, err = get_lineworks_token()
                if err:
                    st.error(f'認証エラー: {err}')
                    return
                try:
                    domain_id = st.secrets["lineworks"]["domain_id"]
                    bot_id = st.secrets["lineworks"]["bot_id"]
                except Exception as e:
                    st.error(f'secrets設定エラー: {e}')
                    return
                with st.spinner('ユーザー一覧を取得中...'):
                    lw_users = get_lineworks_users(token, domain_id)
                name_to_userid = {}
                for u in lw_users:
                    un = u.get("userName", {})
                    full1 = un.get("lastName", "") + un.get("firstName", "")
                    full2 = un.get("firstName", "") + un.get("lastName", "")
                    uid = u.get("userId", "")
                    if full1:
                        name_to_userid[full1] = uid
                    if full2 and full2 != full1:
                        name_to_userid[full2] = uid
                sent, failed, unmatched = [], [], []
                for staff_name in targets:
                    uid = name_to_userid.get(staff_name)
                    if not uid:
                        unmatched.append(staff_name)
                        continue
                    status, _ = send_lineworks_dm(token, bot_id, uid, message)
                    if status in (200, 201):
                        sent.append(staff_name)
                    else:
                        failed.append(f"{staff_name}（{status}）")
                if sent:
                    st.success(f'送信成功 {len(sent)}名：' + '、'.join(sent))
                if failed:
                    st.error(f'❌ 送信失敗 {len(failed)}名：' + '、'.join(failed))
                if unmatched:
                    st.warning(f'アカウントが見つからなかったスタッフ：' + '、'.join(unmatched))

            # ① 複数人への一斉送信
            st.markdown('**① 選択したスタッフに一斉送信**')
            selected_staff = st.multiselect(
                '送信先を選択（複数可）',
                options=all_staff,
                default=all_staff,
            )
            lw_message = st.text_area('送信メッセージ（編集可）', default_msg, height=180)
            _, col_btn1, col_btn2 = st.columns([3, 1.2, 1.2])
            with col_btn1:
                if st.button(f'選択した{len(selected_staff)}名に送信'):
                    if not selected_staff:
                        st.warning('送信先を選択してください')
                    else:
                        do_lw_send(selected_staff, lw_message)
            with col_btn2:
                if st.button('全スタッフに一斉送信'):
                    do_lw_send(all_staff, lw_message)

            st.markdown('---')

            # ② 個人への個別メッセージ
            st.markdown('**② 個人への個別メッセージ**')
            target_person = st.selectbox('送信相手', options=all_staff)
            personal_msg = st.text_area('メッセージを入力', height=120, key='personal_msg')
            _, col_send = st.columns([3, 1.2])
            with col_send:
                if st.button('個別送信', use_container_width=True):
                    if not personal_msg.strip():
                        st.warning('メッセージを入力してください')
                    else:
                        do_lw_send([target_person], personal_msg)
        else:
            st.success('全日程・全シフトに1名以上入っています！')

        st.markdown('---')
        st.subheader('PDFダウンロード')
        col_pdf1, col_pdf2 = st.columns(2)
        with col_pdf1:
            pdf_bytes = generate_shift_pdf(daily_shifts, year, month, staff_colors)
            st.download_button(
                label=f'{year}年{month}月 シフト表',
                data=pdf_bytes,
                file_name=f'shift_{year}_{month:02d}.pdf',
                mime='application/pdf',
                use_container_width=True,
            )
        with col_pdf2:
            manual_pdf = generate_staff_manual_pdf()
            st.download_button(
                label='スタッフ用マニュアル',
                data=manual_pdf,
                file_name='staff_manual.pdf',
                mime='application/pdf',
                use_container_width=True,
            )

        st.markdown('---')
        st.subheader('スタッフ出勤ランキング')
        st.caption('合計出勤日数が多いスタッフほど上位。シフト競合時の優先順位の参考に。')
        rank_df = build_admin_ranking(df, date_cols)
        medals = ['1位', '2位', '3位']
        for i, (name, row) in enumerate(rank_df.iterrows()):
            medal = medals[i] if i < 3 else f'{i+1}位'
            total = row['合計日数']
            max_days = rank_df['合計日数'].max()
            pct = total / max_days if max_days > 0 else 0
            col_a, col_b, col_c, col_d, col_e = st.columns([1, 3, 2, 2, 4])
            col_a.write(medal)
            col_b.write(f'**{name}**')
            col_c.write(f'早番 {row["早番日数"]}日')
            col_d.write(f'遅番 {row["遅番日数"]}日')
            col_e.progress(float(pct), text=f'合計 {total}日')

_, col_reload = st.columns([3, 1.2])
with col_reload:
    if st.button('データを再読み込み', use_container_width=True):
        st.cache_data.clear()
        st.rerun()
