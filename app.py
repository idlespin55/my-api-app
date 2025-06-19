import streamlit as st
from openai import OpenAI

client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

st.title("My AI Chatbot")

user_input = st.text_input("You:", "")

if user_input:
    response = client.chat.completions.create(
        model="gpt-4",
        messages=[{"role": "user", "content": user_input}]
    )
    st.write("AI:", response.choices[0].message.content)