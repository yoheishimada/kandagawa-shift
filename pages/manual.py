import streamlit as st

st.set_page_config(page_title='使い方マニュアル', layout='wide')

st.markdown("""
<style>
h1 { font-size: 1.4rem !important; font-weight: 700 !important; }
h2 { font-size: 1.0rem !important; font-weight: 600 !important;
     text-transform: none !important; letter-spacing: normal !important; color: #1a1a1a !important; }
h3 { font-size: 0.9rem !important; font-weight: 600 !important; }
</style>
""", unsafe_allow_html=True)

try:
    with open('管理者マニュアル.md', 'r', encoding='utf-8') as f:
        st.markdown(f.read())
except:
    st.error('マニュアルを読み込めませんでした。')
