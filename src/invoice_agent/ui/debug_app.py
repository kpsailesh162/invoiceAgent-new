import streamlit as st
import socket
import os

def get_ip():
    try:
        # Get hostname
        hostname = socket.gethostname()
        # Get IP
        ip = socket.gethostbyname(hostname)
        return ip
    except Exception as e:
        return str(e)

st.title("Debug App")
st.write("Server Information:")
st.write(f"- IP Address: {get_ip()}")
st.write(f"- Current Directory: {os.getcwd()}")
st.write(f"- Python Path: {os.getenv('PYTHONPATH')}")
st.write(f"- Streamlit Version: {st.__version__}")

# Add a button to test interactivity
if st.button("Click Me"):
    st.success("Button clicked!") 