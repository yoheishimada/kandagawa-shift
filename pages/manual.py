import streamlit as st

st.set_page_config(page_title='使い方マニュアル', layout='wide')

try:
    with open('管理者マニュアル.md', 'r', encoding='utf-8') as f:
        st.markdown(f.read())
except:
    st.error('マニュアルを読み込めませんでした。')
