import os
import asyncio
import lionagi as li
from lionagi import chunk, text_chunker, ChunkerType
from llama_index.llms import OpenAI
from llama_index.schema import TextNode, Document
from llama_index import VectorStoreIndex, ServiceContext, SimpleDirectoryReader
from llama_index.text_splitter import CodeSplitter
from github import Github, GithubException
import autogen
import IPython
from typing import Dict, Union
import time
import requests
import ast

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")

# pulls the repo from github and returns it as one long string with a line starting with "File:"
def get_repo(owner, name, GITHUB_TOKEN, sha=None, branch=None):
    owner = str(owner)
    name = str(name)
    GITHUB_TOKEN = str(GITHUB_TOKEN)
    
    g = Github(GITHUB_TOKEN)
    repo = g.get_repo(f"{owner}/{name}")
    

    content_list = []

    def fetch_files_recursively(contents_url, content_list):
        if branch is not None:
            ref = branch
        elif sha is not None:
            ref = sha
        else:
            ref = None

        if ref is not None:
            contents = repo.get_contents(contents_url, ref=ref)
        else:
            contents = repo.get_contents(contents_url)

        for content_file in contents:
            if content_file.type == 'dir':
                fetch_files_recursively(content_file.path, content_list)
            else:
                # Check if the file extension is .py
                if content_file.name.endswith('.py'):
                    try:
                        if content_file.encoding == 'base64':
                            content_string = content_file.decoded_content.decode('utf-8')
                            # Check if the content is valid Python code
                            try:
                                ast.parse(content_string)
                                content_list.append(content_string)  # Add the content to the list
                            except SyntaxError:
                                print(f"Invalid Python code in file {content_file.path}")
                    except (GithubException, IOError) as exc:
                        print(f"Error processing file {content_file.path}: {exc}")

    fetch_files_recursively("", content_list)

    return '\n'.join(content_list)

def chunk(repo, chunk_lines=50, chunk_lines_overlap=10, max_chars=1500):
    print("Chunking repository...")
    splitter = CodeSplitter(
        language="python",
        chunk_lines=chunk_lines,
        chunk_lines_overlap=chunk_lines_overlap,
        max_chars=max_chars,
    )
    documents = [Document(id_=str(i), text=doc) for i, doc in enumerate(repo.split('\n'))]
    chunked_docs = []
    for doc in documents:
        try:
            if doc.text.strip():
                # Check if the chunk is valid Python code
                ast.parse(doc.text)
                chunked_docs.append(doc)
        except (ValueError, SyntaxError) as e:
            print(f"Skipping document due to error: {e}")
    print("Repository chunked successfully")
    return chunked_docs


def calculate_sleep_time(requests_made, time_window, max_requests_per_time_window):
    if requests_made < max_requests_per_time_window:
        return 0
    return (time_window * requests_made) / max_requests_per_time_window


def get_query_engine(chunked_docs, model="gpt-4-1106-preview", rate_limit=500, sleep_time=60):
    print("Setting up query engine...")
    splitter = CodeSplitter(language="python")
    documents = [Document(id_=str(i), text=doc.text) for i, doc in enumerate(chunked_docs)]
    nodes = [TextNode(text=doc.text) for doc in splitter.get_nodes_from_documents(documents)]
    print(f"Nodes: {nodes}")
    
    llm = OpenAI(temperature=0.1, model=model, embed_model="local")
    service_context = ServiceContext.from_defaults(llm=llm)

    requests_made = 0
    start_time = time.time()

    index = None  # Initialize index here
    retry_limit = 3
    for i in range(0, len(nodes), rate_limit):
        batch = nodes[i:i + rate_limit]
        retries = 0

        while retries < retry_limit:
            try:
                index = VectorStoreIndex(batch, include_embeddings=True, service_context=service_context)
                requests_made += 1
                break
            except Exception as e:
                print(f"Caught exception: {e}")
        else:
            print(f"Failed to process batch after {retry_limit} retries. Aborting.")
            break

        elapsed_time = time.time() - start_time
        dynamic_sleep_time = calculate_sleep_time(requests_made, 60, rate_limit)
        if dynamic_sleep_time > 0:
            print(f"Sleeping for {dynamic_sleep_time} seconds to avoid hitting rate limit.")
            time.sleep(dynamic_sleep_time)

    if index is None:
        raise Exception("Failed to create index")

    query_engine = index.as_query_engine(include_text=False, response_mode="tree_summarize")
    print("Query engine set up successfully")
    return query_engine


def get_ipython_user_proxy():
    
    try:
        import autogen
        from IPython import get_ipython
    except Exception as e:
        raise ImportError(f"Please install autogen and IPython. {e}")
    
    class IPythonUserProxyAgent(autogen.UserProxyAgent):
        
        def __init__(self, name: str, **kwargs):
            super().__init__(name, **kwargs)
            self._ipython = get_ipython()

        def generate_init_message(self, *args, **kwargs) -> Union[str, Dict]:
            return super().generate_init_message(*args, **kwargs) + """If you suggest code, the code will be executed in IPython."""

        def run_code(self, code, **kwargs):
            result = self._ipython.run_cell("%%capture --no-display cap\n" + code)
            log = self._ipython.ev("cap.stdout")
            log += self._ipython.ev("cap.stderr")
            if result.result is not None:
                log += str(result.result)
            exitcode = 0 if result.success else 1
            if result.error_before_exec is not None:
                log += f"\n{result.error_before_exec}"
                exitcode = 1
            if result.error_in_exec is not None:
                log += f"\n{result.error_in_exec}"
                exitcode = 1
            return exitcode, log, None

    return IPythonUserProxyAgent

def get_autogen_coder(
    llm_config=None, 
    code_execution_config=None, 
    kernal='python', 
    config_list=None, 
    max_consecutive_auto_reply=15, 
    temperature=0, 
    cache_seed=42,
    env_='local',
    assistant_instruction=None
):
    assistant = ''
    try:
        import autogen
        from autogen.agentchat.contrib.gpt_assistant_agent import GPTAssistantAgent
    except Exception as e:
        raise ImportError(f"Please install autogen. {e}")
    
    if env_ =='local': 
        assistant = autogen.AssistantAgent(
            name="assistant",
            llm_config= llm_config or {
                "cache_seed": cache_seed, 
                "config_list": config_list, 
                "temperature": temperature, 
            },
        )
        
    elif env_ == 'oai_assistant': 
        assistant = GPTAssistantAgent(
            name="Coder Assistant",
            llm_config={
                "tools": [{"type": "code_interpreter"}],
                "config_list": config_list,
            },
            instructions=assistant_instruction,
        )
    
    if kernal == 'python':
        user_proxy = autogen.UserProxyAgent(
            name="user_proxy",
            human_input_mode="NEVER",
            max_consecutive_auto_reply=max_consecutive_auto_reply,
            is_termination_msg=lambda x: x.get("content", "").rstrip().endswith("TERMINATE"),
            code_execution_config=code_execution_config or {
                "work_dir": "coding",
                "use_docker": False,  
            },
        )
        return user_proxy, assistant

    elif kernal == "ipython":
        user_proxy = get_ipython_user_proxy(
            "ipython_user_proxy",
            human_input_mode="NEVER",
            max_consecutive_auto_reply=max_consecutive_auto_reply,
            is_termination_msg=lambda x: x.get("content", "").rstrip().endswith("TERMINATE") or x.get("content", "").rstrip().endswith('"TERMINATE".'),
        )
        return user_proxy, assistant
    
class Coder:
    
    @staticmethod
    def autogen(**kwargs):
        return get_autogen_coder(**kwargs)

def configure_coder():
    config_list = autogen.config_list_from_json(
    "OAI_CONFIG_LIST",
    filter_dict={
        "model": ["gpt-3.5-turbo","gpt-3.5-turbo-instruct","gpt-4", "gpt-4-0314", "gpt4", "gpt-4-32k", "gpt-4-32k-0314", "gpt-4-32k-v0314", "gpt-4-1106-preview"],
    },)
    autogen_coder_config = {
    "llm_config": None,         # follow autogen format
    "code_execution_config": None,
    "env_": "local",
    "kernal":'python',
    "config_list": config_list,
    "temperature": 0.1, 
    "cache_seed": 42,
    "max_consecutive_auto_reply": 15,
    "assistant_instruction": None,
}
    user_proxy, assistant = Coder.autogen(**autogen_coder_config)
    assistant.set_context(chunked_repo)
    return user_proxy, assistant


def chat_with_assistant(user_proxy, assistant, messages):
    for message in messages:
        response = assistant.generate_message(message)
        print(f"Assistant: {response['content']}")
        user_proxy.generate_message(response['content'])

def main():
    print("Fetching repository...")
    owner = "TopherF22"
    name = "BasicIntegration"
    branch = "master"
    repo = get_repo(owner, name, GITHUB_TOKEN)
    chunked_repo = chunk(repo)
    print(f"Number of chunks: {len(chunked_repo)}")
    print("Reository fetched successfully")

    return chunked_repo

if __name__ == '__main__':
    print("Starting script...")
    chunked_repo = main()
    query_engine = get_query_engine(chunked_repo)
    user_proxy, assistant = configure_coder()
    
    messages = ["What does this code do?", "Can you suggest an improvement?"]
    chat_with_assistant(user_proxy, assistant, messages)
    print("Script finished successfully")
