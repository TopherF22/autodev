import streamlit as st
from stqdm import stqdm
from time import sleep
from random import uniform

# sidebar
with st.sidebar:
    st.image("lionLogo.jpg", width=100)  # Adjust width as necessary
    st.title("LionAGI Demo")
    st.write("[GitHub](https://github.com/lion-agi/lionagi)")
    st.write("[Documentation](https://lionagi.readthedocs.io/en/latest/)")

# inputs
repo_input_value = st.text_input("Please input GitHub link, repo name, or commit hash", key="repo_box")
prompt_input_value = st.text_input("Please input prompt", key="prompt_box")



# main
info_placeholder = st.empty()
if repo_input_value and prompt_input_value:
    total_steps = 10
    for i in stqdm(range(total_steps), desc="Processing..."):
        info_placeholder.info(f"Processing step {i+1} of {total_steps}")
        sleep(uniform(0.1, 0.5))  
        
    info_placeholder.empty()

    st.write(f"Here is the prompt you provided: {prompt_input_value}")
    st.write(f"Here is the repo you provided: {repo_input_value}")
    st.code("print('Here is your suggested code!')")
    st.success("Complete!")
