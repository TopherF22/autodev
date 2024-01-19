import streamlit as st
from stqdm import stqdm
from time import sleep
from random import uniform

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

with st.expander("GitHub Repository Input"):
    input_option = st.selectbox("Select the repository input method:", ["Commit SHA", "Branch"])

    github_authentication_token = st.text_input("GitHub Authentication Token", help="Input your GitHub Authentication Token. Check the sidebar for instructions.")

    owner_input_value = st.text_input("GitHub Username", help="Input the username of the repository owner.")
    repo_name_input = st.text_input("GitHub Repository Name", help="Input the name of the GitHub repository.")

    if input_option == "Commit SHA":
        sha_input_value = st.text_input("Commit Hash", help="Input the full commit hash for the repository.")
        branch_input_value = None  
    else:
        branch_input_value = st.text_input("Branch Name", value="master", help="Input the branch name. Defaults to 'master' if left empty.")
        sha_input_value = None  

prompt_input_value = st.chat_input("Please input your code generation prompt here.")

if prompt_input_value:
    required_fields = [github_authentication_token, owner_input_value, repo_name_input, prompt_input_value]
    if input_option == "Commit SHA":
        required_fields.append(sha_input_value)
    else:
        required_fields.append(branch_input_value)
    
    if all_fields_filled(required_fields):
        info_placeholder = st.empty()
        total_steps = 10
        for i in stqdm(range(total_steps), desc="Processing..."):
            info_placeholder.info(f"Processing step {i+1} of {total_steps}")
            sleep(uniform(0.1, 0.5))  
        info_placeholder.success("Processing complete!")
        st.code("print('Here is your suggested code!')")
    else:
        st.error("Please fill in all the required fields to proceed.")
