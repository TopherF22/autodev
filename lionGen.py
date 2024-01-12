import logging
import sys
import pickle
import os
import nest_asyncio
from llama_index import download_loader, GPTVectorStoreIndex, ServiceContext, VectorStoreIndex
from llama_hub.github_repo import GithubClient, GithubRepositoryReader
import lionagi as li
from llama_index.llms import OpenAI
from llama_index.schema import TextNode
import autogen
from autogen import AssistantAgent, UserProxyAgent, config_list_from_json
from autogen.agentchat.contrib.gpt_assistant_agent import GPTAssistantAgent



nest_asyncio.apply()
logging.basicConfig(stream=sys.stdout, level=logging.INFO)
logging.getLogger().addHandler(logging.StreamHandler(stream=sys.stdout))


GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")
github_client = GithubClient(os.getenv("GITHUB_TOKEN"))

download_loader("GithubRepositoryReader")


def load_and_chunk_repo(owner, name, branch):
    repo_reader = GithubRepositoryReader(github_client, f"{owner}/{name}", 'your-repo-name')
    repo_files = []
    try:
        print("Loading repository...")
        repo_files = [file['text'] for file in repo_reader.read()]
        print("Repository loaded.")
    except Exception as e:
        print(f"An error occurred: {e}")

    # save the repo files to a pickle file
    with open(f"{name}_repo_files.pkl", "wb") as f:
        pickle.dump(repo_files, f)

    #changed to load to read
    files = li.dir_to_files(repo_files, clean=True, project=name, to_csv=True, timestamp=False)

    chunks = li.file_to_chunks(files, chunk_size=512,  overlap=0.1, 
                               threshold=100, to_csv=True, project=name, 
                               filename=f"{name}_chunks.csv", timestamp=False)
    return chunks

def setup_vector_index(chunks):
    f = lambda content: TextNode(text=content)
    nodes = li.lcall(chunks, lambda x: f(x["chunk_content"]))

    llm = OpenAI(temperature=0.1, model="gpt-4-1106-preview")
    service_context = ServiceContext.from_defaults(llm=llm)
    index = VectorStoreIndex(nodes, include_embeddings=True, service_context=service_context)

    query_engine = index.as_query_engine(include_text=False, response_mode="tree_summarize")
    return query_engine

def setup_chat():
    config_list = autogen.config_list_from_json(
        "OAI_CONFIG_LIST",
        file_location=".",
        filter_dict={
            "model": ["gpt-3.5-turbo", "gpt-35-turbo", "gpt-4", "gpt4", "gpt-4-32k", "gpt-4-turbo"],
        },
    )

    coder_instruction = f"""
        You are an expert at writing python codes. Write pure python codes, and run it to validate the 
        codes, then return with the full implementation + the word TERMINATE when the task is solved 
        and there is no problem. Reply FAILED if you cannot solve the problem.
        """


    gpt_assistant = GPTAssistantAgent(
        name="Coder Assistant",
        llm_config={
            "tools": [
                {
                    "type": "code_interpreter"
                }
            ],
            "config_list": config_list,
        },
        instructions=coder_instruction,
    )

    user_proxy = UserProxyAgent(
        name="user_proxy",
        is_termination_msg=lambda msg: "TERMINATE" in msg["content"],
        code_execution_config={
            "work_dir": "coding",
            "use_docker": False,
        },
        human_input_mode="ALWAYS"
    )

    return gpt_assistant, user_proxy

def query_lionagi_codebase(str_or_query_bundle):
    return query_engine.query(str_or_query_bundle)

async def code_pure_python(instruction):
    user_proxy.initiate_chat(gpt_assistant, message=instruction)
    return gpt_assistant.last_message()

tool1 = [
    {
        "type": "function",
        "function": {
            "name": "query_lionagi_codebase",
            "description": "Perform a query to a QA bot with access to a vector index built with package lionagi codebase",
            "parameters": {
                "type": "object",
                "properties": {
                    "str_or_query_bundle": {
                        "type": "string",
                        "description": "a question to ask the QA bot",
                    }
                },
                "required": ["str_or_query_bundle"],
            },
        }
    }
]

tool2 = [
    {
        "type": "function",
        "function": {
            "name": "code_pure_python",
            "description": "Give an instruction to a coding assistant to write pure python codes",
            "parameters": {
                "type": "object",
                "properties": {
                    "instruction": {
                        "type": "string",
                        "description": "coding instruction to give to the coding assistant",
                    }
                },
                "required": ["instruction"],
            },
        }
    }
]



tools = [tool1[0], tool2[0]]
funcs = [query_lionagi_codebase, code_pure_python]

async def solve_in_python(chunks, context, num=10):
    global query_engine
    query_engine = setup_vector_index(chunks)
    
    global gpt_assistant, user_proxy
    gpt_assistant, user_proxy = setup_chat()

    await user_proxy.initiate_chat(gpt_assistant, message=instruct1)

    for _ in range(num):
        await user_proxy.send_message(tool1[0])

    for _ in range(2):
        await user_proxy.send_message(tool2[0])

    return gpt_assistant.last_message()

class Instruction:
    def __init__(self, step, name, objective, description, function_call=None):
        self.step = step
        self.name = name
        self.objective = objective
        self.description = description
        self.function_call = function_call


instruct1 = Instruction(
    step="1", 
    name="understand user requirements", 
    objective="get a comprehensive understanding of the task given", 
    description="user provided you with a task, please understand the task, propose plans on delivering it"
)

instruct2 = Instruction(
    step="2", 
    name="propose a pure python solution", 
    objective="give detailed instruction on how to achieve above task with pure python as if to a coding bot", 
    description="you are responsible for further customizing the coding task into our lionagi package requirements, you are provided with a QA bot, please keep on asking questions if there are anything unclear, your instruction should focus on functionalities and coding logic",
)

instruct3 = Instruction(
    step="3", 
    name="write pure python codes", 
    objective="write runnable python codes", 
    description="from your improved understanding of the task, please instruct the coding assistant on wiriting pure python codes. you will reply with the full implementation if the coding assistant succeed, which you need to return the full implementation in a well structured py format, run it once more if report back'failed', and return 'Task failed' with most recent effort, after the second failed attempt ",
)


async def main():
    testDict = {"testOwner": "TopherF22", "testName": "Fundamental-Visualizer", "testBranch": "master"}

    
    chunks = load_and_chunk_repo(owner= testDict["testOwner"], name="Fundamental-Visualizer", branch="master")
        
    global query_engine
    query_engine = setup_vector_index(chunks)
    
    global gpt_assistant, user_proxy
    gpt_assistant, user_proxy = setup_chat()


    system = {
        "persona": "a helpful software engineer",
        "requirements": "think step by step before returning a thoughtful answer that follows the instruction with clearly, precisely worded answer with a humble yet confident tone",
        "responsibilities": f"you are asked to help with coding on the python package of lionagi",
        "tools": "provided with a QA bot for grounding responses, and a coding assistant to write pure python codes"
    }

    function_call1 = {
        "notice":"""
            At each task step, identified by step number, you must use the tool 
            at least five times. Notice you are provided with a QA bot as your tool, 
            the bot has access to the source codes via a queriable index that takes 
            natural language query and return a natural language answer. You can 
            decide whether to invoke the function call, you will need to ask the bot 
            when there are things need clarification or further information. you 
            provide the query by asking a question, please use the tool extensively 
            as you can (up to ten times)
            """,}

    function_call2 = {
        "notice":"""
            At each task step, identified by step number, you must use the tool 
            at least once, and you must use the tool at least once more if the previous 
            run failed. Notice you are provided with a coding assistant as your tool, the 
            bot can write and run python codes in a sandbox environment, it takes natural 
            language instruction, and return with 'success'/'failed'. For the instruction 
            you give, it needs to be very clear and detailed such that an AI coding assistant 
            can produce excellent output.  
            """,}
   

    response = await solve_in_python(chunks, instruct1, num=10)
    print(response)


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
    