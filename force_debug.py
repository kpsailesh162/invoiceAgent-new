import os
os.environ['STREAMLIT_SERVER_PORT'] = '8502'
os.environ['STREAMLIT_SERVER_ADDRESS'] = '127.0.0.1'
os.environ['STREAMLIT_SERVER_HEADLESS'] = 'true'
os.environ['STREAMLIT_BROWSER_GATHER_USAGE_STATS'] = 'false'

import streamlit.web.bootstrap as bootstrap
import streamlit as st
import socket

def get_ip():
    try:
        hostname = socket.gethostname()
        ip = socket.gethostbyname(hostname)
        return ip
    except Exception as e:
        return str(e)

def main():
    st.title("Debug App")
    st.write("Server Information:")
    st.write(f"- IP Address: {get_ip()}")
    st.write(f"- Current Directory: {os.getcwd()}")
    st.write(f"- Python Path: {os.getenv('PYTHONPATH')}")
    st.write(f"- Streamlit Version: {st.__version__}")
    
    if st.button("Click Me"):
        st.success("Button clicked!")

if __name__ == "__main__":
    bootstrap.run(main, "", [], flag_options={}) 