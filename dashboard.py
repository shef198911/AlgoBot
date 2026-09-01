import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import json
import os

# Конфигурация страницы (Темная тема)
st.set_page_config(page_title="AI AlgoBot Dashboard", layout="wide", page_icon="📈")

# Стилизация (минимализм)
st.markdown("""
    <style>
    .main {background-color: #0e1117;}
    h1, h2, h3 {color: #fafafa;}
    .stMetric {background-color: #1e212b; padding: 15px; border-radius: 10px;}
    </style>
""", unsafe_allow_html=True)

st.title("🧠 Гибридный ИИ Трейдинг Бот")

# Получение данных
df_trades = pd.DataFrame()
if os.path.exists("analytics_data.json"):
    try:
        with open("analytics_data.json", "r", encoding="utf-8") as f:
            data = json.load(f)
            if data:
                # Нормализация старых данных, где не было timestamp
                for row in data:
                    if 'timestamp' not in row:
                        row['timestamp'] = '2026-01-01 00:00:00'
                    if 'profit_usdt' not in row and 'pnl' in row:
                        row['profit_usdt'] = row['pnl']
                    if 'ai_confidence' not in row:
                        row['ai_confidence'] = 0.0
                        
                df_trades = pd.DataFrame(data)
                df_trades['timestamp'] = pd.to_datetime(df_trades['timestamp'])
                df_trades = df_trades.sort_values(by='timestamp')
    except Exception as e:
        st.error(f"Ошибка чтения данных: {e}")
        
status = None
if os.path.exists("bot.log"):
    try:
        with open("bot.log", "r", encoding="utf-8") as f:
            lines = f.readlines()
            for line in reversed(lines):
                if "Уверенность:" in line:
                    conf = float(line.split("Уверенность: ")[1].split(".")[0] + "." + line.split("Уверенность: ")[1].split(".")[1][:2])
                    msg = line.strip().split("] ")[-1]
                    status = {"message": msg, "ai_confidence": conf}
                    break
    except:
        pass

# 1. Верхний ряд: Ключевые метрики
col1, col2, col3, col4 = st.columns(4)

if not df_trades.empty:
    total_pnl = df_trades['profit_usdt'].sum()
    win_rate = (len(df_trades[df_trades['profit_usdt'] > 0]) / len(df_trades)) * 100
    total_trades = len(df_trades)
    
    col1.metric("Текущий PNL (USDT)", f"${total_pnl:.2f}", f"{'+' if total_pnl > 0 else ''}{total_pnl:.2f}")
    col2.metric("Win Rate", f"{win_rate:.1f}%")
    col3.metric("Всего сделок", total_trades)
else:
    col1.metric("Текущий PNL", "$0.00")
    col2.metric("Win Rate", "0%")
    col3.metric("Всего сделок", "0")

if status:
    ai_conf = status['ai_confidence'] * 100
    col4.metric("Уверенность ИИ (Сейчас)", f"{ai_conf:.1f}%")

st.markdown("---")

# 2. Средний ряд: Графики
col_graph1, col_graph2 = st.columns([2, 1])

with col_graph1:
    st.subheader("📊 Кривая доходности (Equity Curve)")
    if not df_trades.empty:
        # Считаем нарастающий итог
        df_trades['Cumulative_Profit'] = df_trades['profit_usdt'].cumsum()
        fig_equity = px.area(df_trades, x='timestamp', y='Cumulative_Profit', 
                             color_discrete_sequence=['#00FFAA'],
                             template='plotly_dark')
        fig_equity.update_layout(xaxis_title="Время", yaxis_title="Прибыль (USDT)")
        st.plotly_chart(fig_equity, use_container_width=True)
    else:
        st.info("Нет данных для отображения графика.")

with col_graph2:
    st.subheader("🎯 Статус ИИ (XGBoost)")
    if status:
        conf_val = status['ai_confidence']
        fig_gauge = go.Figure(go.Indicator(
            mode = "gauge+number",
            value = conf_val * 100,
            domain = {'x': [0, 1], 'y': [0, 1]},
            title = {'text': "Уверенность в сетапе"},
            gauge = {
                'axis': {'range': [0, 100]},
                'bar': {'color': "#00FFAA" if conf_val > 0.65 else "#FF4444"},
                'steps': [
                    {'range': [0, 65], 'color': "rgba(255, 68, 68, 0.2)"},
                    {'range': [65, 100], 'color': "rgba(0, 255, 170, 0.2)"}
                ],
                'threshold': {
                    'line': {'color': "white", 'width': 2},
                    'thickness': 0.75,
                    'value': 65
                }
            }
        ))
        fig_gauge.update_layout(template='plotly_dark', height=300)
        st.plotly_chart(fig_gauge, use_container_width=True)
        st.write(f"**Последнее сообщение бота:** {status['message']}")
    else:
        st.info("Бот еще не передал статус.")

st.markdown("---")

# 3. Нижний ряд: Таблица истории
st.subheader("📝 История сделок")
if not df_trades.empty:
    # Стилизуем датафрейм для вывода
    display_df = df_trades[['timestamp', 'symbol', 'side', 'entry_price', 'exit_price', 'profit_usdt', 'ai_confidence']].copy()
    display_df = display_df.sort_values(by='timestamp', ascending=False)
    display_df['ai_confidence'] = (display_df['ai_confidence'] * 100).round(1).astype(str) + '%'
    display_df['profit_usdt'] = display_df['profit_usdt'].round(2)
    
    st.dataframe(display_df, use_container_width=True, hide_index=True)
else:
    st.info("История сделок пуста.")

st.markdown("---")

# 4. Открытые позиции (Live)
st.subheader("🟢 Открытые позиции и ордера (Live)")
if os.path.exists("live_state.json"):
    try:
        with open("live_state.json", "r", encoding="utf-8") as f:
            live_data = json.load(f)
            if live_data:
                live_df = pd.DataFrame.from_dict(live_data, orient='index').reset_index()
                live_df.rename(columns={'index': 'symbol'}, inplace=True)
                st.dataframe(live_df[['symbol', 'side', 'entry', 'amount', 'sl_price', 'tp_price']], use_container_width=True, hide_index=True)
            else:
                st.info("В данный момент нет открытых позиций.")
    except Exception as e:
        st.error(f"Ошибка загрузки открытых позиций: {e}")
else:
    st.info("В данный момент нет открытых позиций.")
