from github import Github, GithubException
import lionagi as li
from lionagi import chunk, text_chunker, ChunkerType


def get_repo(owner, name, GITHUB_TOKEN, sha=None, branch=None):
    owner = str(owner)
    name = str(name)
    GITHUB_TOKEN = str(GITHUB_TOKEN)
    
    g = Github(GITHUB_TOKEN)
    repo = g.get_repo(f"{owner}/{name}")
    

    content_list = []

    def fetch_files_recursively(contents_url):
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
                fetch_files_recursively(content_file.path)
            else:
                # Check if the file extension is .py
                if content_file.name.endswith('.py'):
                    try:
                        if content_file.encoding == 'base64':
                            content_string = content_file.decoded_content.decode('utf-8')
                            content_list.append(f"File: {content_file.path}\n{content_string}")
                    except (GithubException, IOError) as exc:
                        print(f"Error processing file {content_file.path}: {exc}")

    fetch_files_recursively("")

    # Join the list into a single string and return it
    return '\n'.join(content_list)

def chunk(repo, chunk_size=100):
    print("Chunking repository...")
    documents = [li.DataNode(content=repo)]
    args = []
    kwargs = {"chunk_size": chunk_size}
    chunked_docs = text_chunker(documents, args, kwargs)
    chunked_docs = [doc for doc in chunked_docs if doc.content.strip()]
    print("Repository chunked successfully")
    return chunked_docs