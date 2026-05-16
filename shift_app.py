import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
import calendar
import re
import json
import io
import time
import requests
import jwt as pyjwt
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont

SPREADSHEET_ID = '1sVh4_9vbkucCRSenosYISpw_mFSsUioPLs0zBfxNT0U'
APP_PASSWORD = 'Kandagawa0222'
ADMIN_PASSWORD = 'Kandagawa0222'

st.set_page_config(page_title='神田川ベーカリー シフト表', layout='wide')

# --- パスワード保護 ---
if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False

if not st.session_state.authenticated:
    st.title('神田川ベーカリー シフト表')
    st.markdown('---')
    pw = st.text_input('パスワードを入力してください', type='password')
    if st.button('ログイン'):
        if pw == APP_PASSWORD:
            st.session_state.authenticated = True
            st.rerun()
        else:
            st.error('パスワードが違います')
    st.stop()

# --- 認証済み以降の処理 ---
st.title('神田川ベーカリー シフト表')

# サイドバー：管理者ログイン
with st.sidebar:
    st.header('管理者メニュー')
    admin_pw = st.text_input('管理者パスワード', type='password')
    is_admin = (admin_pw == ADMIN_PASSWORD)
    if admin_pw and not is_admin:
        st.error('パスワードが違います')
    if is_admin:
        st.success('管理者モード')
    if st.button('ログアウト'):
        st.session_state.authenticated = False
        st.rerun()

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
    df = df.drop_duplicates(subset=['お名前'], keep='last')  # 再申請時は最新を使用
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
                "scope": "bot",
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

def render_calendar(daily_shifts, year, month):
    _, days_in_month = calendar.monthrange(year, month)
    first_weekday = calendar.weekday(year, month, 1)
    day_names = ['月', '火', '水', '木', '金', '土', '日']

    html = """
    <style>
    .cal-wrap { overflow-x: auto; }
    .cal-table { width: 100%; border-collapse: collapse; table-layout: fixed; }
    .cal-header { background: #3d3d7a; color: white; text-align: center;
                  padding: 10px 4px; font-weight: bold; font-size: 15px; }
    .cal-cell { border: 1px solid #ccc; vertical-align: top;
                padding: 6px 4px; min-height: 100px; }
    .cal-empty { background: #f0f0f0; }
    .cal-date { font-weight: bold; font-size: 15px; margin-bottom: 4px; color: #333; }
    .cal-label { font-size: 10px; color: #888; margin-top: 4px; }
    .cal-name-early { background: #d4edda; color: #155724; border-radius: 3px;
                      padding: 2px 5px; margin: 2px 0; font-size: 11px; display: block; }
    .cal-name-late  { background: #cce5ff; color: #004085; border-radius: 3px;
                      padding: 2px 5px; margin: 2px 0; font-size: 11px; display: block; }
    .cal-none { color: #bbb; font-size: 11px; }
    </style>
    <div class='cal-wrap'>
    <table class='cal-table'>
    <tr>
    """
    for d in day_names:
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
                wname = day_names[calendar.weekday(year, month, day)]
                date_label = f"{month}月{day}日（{wname}）"
                shifts = daily_shifts.get(date_label, {'早': [], '遅': []})
                early = shifts['早']
                late = shifts['遅']

                html += "<td class='cal-cell'>"
                html += f"<div class='cal-date'>{day}</div>"

                if early:
                    html += "<div class='cal-label'>早番</div>"
                    for n in early:
                        html += f"<span class='cal-name-early'>{n}</span>"
                if late:
                    html += "<div class='cal-label'>遅番</div>"
                    for n in late:
                        html += f"<span class='cal-name-late'>{n}</span>"
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

def generate_shift_pdf(daily_shifts, year, month):
    pdfmetrics.registerFont(UnicodeCIDFont('HeiseiKakuGo-W5'))
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=landscape(A4),
                            leftMargin=10*mm, rightMargin=10*mm,
                            topMargin=10*mm, bottomMargin=10*mm)

    styles = getSampleStyleSheet()
    jp = ParagraphStyle('jp', fontName='HeiseiKakuGo-W5', fontSize=8, leading=11)
    jp_small = ParagraphStyle('jp_small', fontName='HeiseiKakuGo-W5', fontSize=7, leading=10, textColor=colors.HexColor('#555555'))
    title_style = ParagraphStyle('title', fontName='HeiseiKakuGo-W5', fontSize=14, leading=18)

    day_names = ['月', '火', '水', '木', '金', '土', '日']
    _, days_in_month = calendar.monthrange(year, month)
    first_weekday = calendar.weekday(year, month, 1)

    # カレンダーテーブルデータ作成
    header = [Paragraph(d, jp) for d in day_names]
    table_data = [header]

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
                cell_text = f'<b>{day}</b><br/>'
                if shifts['早']:
                    cell_text += '<font color="#155724">早番</font><br/>' + '<br/>'.join(shifts['早']) + '<br/>'
                if shifts['遅']:
                    cell_text += '<font color="#004085">遅番</font><br/>' + '<br/>'.join(shifts['遅'])
                row.append(Paragraph(cell_text, jp))
                day += 1
        table_data.append(row)

    col_width = (landscape(A4)[0] - 20*mm) / 7
    row_height = (landscape(A4)[1] - 30*mm) / (len(table_data))

    t = Table(table_data, colWidths=[col_width]*7, rowHeights=[10*mm] + [row_height]*(len(table_data)-1))
    t.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, -1), 'HeiseiKakuGo-W5'),
        ('FONTSIZE', (0, 0), (-1, 0), 9),
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#3d3d7a')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cccccc')),
        ('BACKGROUND', (5, 1), (5, -1), colors.HexColor('#fff0f0')),
        ('BACKGROUND', (6, 1), (6, -1), colors.HexColor('#f0f0ff')),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('LEFTPADDING', (0, 0), (-1, -1), 3),
    ]))

    elements = [
        Paragraph(f'{year}年{month}月 シフト表　神田川ベーカリー', title_style),
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

    st.caption(f'※5分ごとに自動更新　　{len(df)}名回答済み　／　未提出 {len(not_submitted)}名')

    if not_submitted:
        st.warning('📋 未提出のスタッフ：' + '　'.join(not_submitted))

    col1, col2 = st.columns(2)
    col1.success('■ 早番（10〜15時）')
    col2.info('■ 遅番（15〜19時）')

    daily_shifts = build_daily_shifts(df)

    st.subheader(f'{year}年{month}月 シフト表')
    st.markdown(render_calendar(daily_shifts, year, month), unsafe_allow_html=True)

    if is_admin:
        st.markdown('---')
        st.subheader('⚠️ 人手不足リスト')
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
                        '早番（10〜15時）': '不足' if early_short else '',
                        '遅番（15〜19時）': '不足' if late_short else '',
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
            st.subheader('📨 シフト再調整依頼をLINE WORKSで送る')
            shortage_lines = '\n'.join(
                f"・{r['日付']}　{r['シフト']}" for r in shortage_rows
            )
            default_msg = (
                f"【シフト再調整のお願い】\n\n"
                f"{year}年{month}月の以下の日程でシフトが不足しています。\n"
                f"入れる方はシフト申請フォームから再申請をお願いします。\n\n"
                f"{shortage_lines}"
            )
            lw_message = st.text_area('送信メッセージ（編集可）', default_msg, height=220)

            if st.button('📨 全スタッフにLINE WORKSで一斉送信'):
                with st.spinner('LINE WORKSに接続中...'):
                    token, err = get_lineworks_token()
                if err:
                    st.error(f'認証エラー: {err}')
                else:
                    try:
                        domain_id = st.secrets["lineworks"]["domain_id"]
                        bot_id = st.secrets["lineworks"]["bot_id"]
                    except Exception as e:
                        st.error(f'secrets設定エラー: {e}')
                        st.stop()

                    with st.spinner('ユーザー一覧を取得中...'):
                        lw_users = get_lineworks_users(token, domain_id)

                    # LINE WORKSの名前(姓+名)とスタッフリストをマッチング
                    name_to_userid = {}
                    for u in lw_users:
                        un = u.get("userName", {})
                        # 姓名を結合（姓+名、名+姓の両方を登録）
                        full1 = un.get("lastName", "") + un.get("firstName", "")
                        full2 = un.get("firstName", "") + un.get("lastName", "")
                        uid = u.get("userId", "")
                        if full1:
                            name_to_userid[full1] = uid
                        if full2 and full2 != full1:
                            name_to_userid[full2] = uid

                    sent, failed, unmatched = [], [], []
                    progress = st.progress(0)
                    for i, staff_name in enumerate(all_staff):
                        progress.progress((i + 1) / len(all_staff))
                        uid = name_to_userid.get(staff_name)
                        if not uid:
                            unmatched.append(staff_name)
                            continue
                        status, body = send_lineworks_dm(token, bot_id, uid, lw_message)
                        if status in (200, 201):
                            sent.append(staff_name)
                        else:
                            failed.append(f"{staff_name}（{status}）")
                    progress.empty()

                    if sent:
                        st.success(f'✅ 送信成功 {len(sent)}名：' + '、'.join(sent))
                    if failed:
                        st.error(f'❌ 送信失敗 {len(failed)}名：' + '、'.join(failed))
                    if unmatched:
                        st.warning(
                            f'⚠️ LINE WORKSアカウントが見つからなかったスタッフ {len(unmatched)}名：'
                            + '、'.join(unmatched)
                        )
        else:
            st.success('全日程・全シフトに1名以上入っています！')

        st.markdown('---')
        st.subheader('📄 シフト表PDFダウンロード')
        pdf_bytes = generate_shift_pdf(daily_shifts, year, month)
        st.download_button(
            label=f'{year}年{month}月 シフト表をPDFでダウンロード',
            data=pdf_bytes,
            file_name=f'shift_{year}_{month:02d}.pdf',
            mime='application/pdf',
        )

        st.markdown('---')
        st.subheader('👑 管理者ビュー：スタッフ出勤ランキング')
        st.caption('合計出勤日数が多いスタッフほど上位。シフト競合時の優先順位の参考に。')
        rank_df = build_admin_ranking(df, date_cols)
        medals = ['🥇', '🥈', '🥉']
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

if st.button('🔄 データを再読み込み'):
    st.cache_data.clear()
    st.rerun()
