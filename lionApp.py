import streamlit as st
from stqdm import stqdm
from time import sleep
from random import uniform
import asyncio
asyncio.set_event_loop(asyncio.new_event_loop())
from lionAppFunctions import *

def all_fields_filled(fields):
    return all(field is not None and field != "" for field in fields)

# sidebar
with st.sidebar:
    st.image("lionLogo.jpg", width=150)  
    st.write("[LionAGI GitHub](https://github.com/lion-agi/lionagi)")
    st.write("[Documentation](https://lionagi.readthedocs.io/en/latest/)")
    with st.expander("Token Instructions"):
        st.write("Your GitHub access token must have 'repo' and 'read\\:org' options checked. Please see [here](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/managing-your-personal-access-tokens) for instructions on how to generate and use your token.")


# main
st.markdown("## Welcome to LionAGI Demo!")
st.markdown("Input a GitHub repo and a prompt, and LionAGI will generate code for you!")



github_authentication_token = str(st.text_input("GitHub Authentication Token", help="Input your GitHub Authentication Token. Check the sidebar for instructions."))

owner_input_value = str(st.text_input("Repo Owner Username", help="Input the username of the repository owner."))
repo_name_input = str(st.text_input("Repo Name", help="Input the name of the GitHub repository."))
input_value = st.text_input("Input Commit SHA or Branch (Optional)", help="Input the commit SHA or branch name for the repository. If left empty, the default branch will be used.")

# Determine if the input is a SHA or branch
if len(input_value) == 40 and all(c in '0123456789abcdef' for c in input_value):
    sha_input_value = input_value
    branch_input_value = None
else:
    branch_input_value = input_value if input_value else "master"
    sha_input_value = None

prompt_input_value = st.chat_input("Please input your code generation prompt here.")

if prompt_input_value:
    required_fields = [github_authentication_token, owner_input_value, repo_name_input, prompt_input_value]

    
    if all_fields_filled(required_fields):
        info_placeholder = st.empty()
        with st.spinner('Fetching repository...'):
            repo = get_repo(owner_input_value, repo_name_input, github_authentication_token)
            st.success('Repository fetched successfully.')
            
        with st.spinner('Chunking repository...'):
            chunked_repo = chunk(repo)
            st.success('Repository chunked successfully.')
        
        #output first chunk
        for chunk in chunked_repo[:5]:
            st.code(chunk.content)
        
        # TODO: Add vector index setup and chat configuration
        # with st.spinner('Setting up vector index...'):
        #     query_engine = setup_vector_index(chunked_repo)
        #     st.success('Vector index set up successfully.')
            
        # with st.spinner('Configuring chat...'):
        #     user_proxy, assistant = configure_chat(chunked_repo)
        #     st.success('Chat configured successfully.')
            
        # with st.spinner('Chatting with assistant...'):
        #     messages = ["What does this code do?", "Can you suggest an improvement?"]
        #     chat_with_assistant(user_proxy, assistant, messages)
        #     st.success('Chat completed successfully.')
    else:
        st.error("Please fill in all the required fields to proceed.")
