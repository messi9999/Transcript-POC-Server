import os
import tiktoken
import random
import string

from openai import OpenAI
client = OpenAI()


def calculate_tokens(text) -> int:
    # Choose the encoding based on the model you're using
    # For example, 'cl100k_base' is the encoding for GPT-4
    encoding = tiktoken.get_encoding('cl100k_base')

    # Encode the text to get tokens
    tokens = encoding.encode(text)

    # Count the number of tokens
    num_tokens = len(tokens)


    return num_tokens

def check_token_limit_status(num_token, max_token) -> bool:
    
    print("num_tokens: ", num_token)
    print("max_token: ", max_token)
    if num_token >= max_token:
        return False
    else:
        return True

def create_assistant(file_id):
    my_assistant = client.beta.assistants.create(
        instructions="Summarize the lecture content inside the file into 15%. The summary must less than 1000 tokens.",
        name="Summarization",
        tools=[{"type": "file_search"}],
        model="gpt-4o",
        tool_resources={"file_search": {"vector_stores": [{"file_ids": [file_id]}]}}
    )
    return my_assistant

def retrieve_assistant(assistant_id):
    my_assistant = client.beta.assistants.retrieve(assistant_id)
    return my_assistant

def delete_assistant(assistant_id):
    deleted_assistant = client.beta.assistants.delete(assistant_id)
    return deleted_assistant

def upload_txt_file_to_openai(file_path):
    my_file = client.files.create(
        file=open("." + file_path, "rb"),
        purpose="assistants"
    )
    return my_file

def delete_txt_file_from_openai(file_id):
    deleted_file = client.files.delete(file_id)
    return deleted_file

def create_thread():
    empty_thread = client.beta.threads.create()
    return empty_thread

def delete_thread(thread_id):
    deleted_thread = client.beta.threads.delete(thread_id)
    return deleted_thread

def run_thread(thread_id, assistant_id):
    run = client.beta.threads.runs.create(
        thread_id=thread_id,
        assistant_id=assistant_id
    )
    return run

def retrieve_run(run_id, thread_id):
    retrieved_run = client.beta.threads.runs.retrieve(
        thread_id=thread_id,
        run_id=run_id
    )
    return retrieved_run

def create_message(thread_id, message):
    thread_message = client.beta.threads.messages.create(
        thread_id,
        role="user",
        content=message,
    )
    return thread_message

def retrieve_message(message_id, thread_id):
    message = client.beta.threads.messages.retrieve(
        message_id=message_id,
        thread_id=thread_id,
    )
    return message

def get_list_messages(thread_id):
    thread_messages = client.beta.threads.messages.list(thread_id)
    return thread_messages

def store_txt_file(text):
    # Generate a random file name
    random_file_path = './uploads/' + generate_random_string(12) + '.txt'
    # Open a file in write mode
    with open( random_file_path, 'w') as file:
        # Write the text to the file
        file.write(text)
    return random_file_path

def remove_file(file_path):
    try:
        # Remove the file
        os.remove(file_path)
        print(f"File '{file_path}' removed successfully.")
    except FileNotFoundError:
        print(f"File '{file_path}' not found.")
    except PermissionError:
        print(f"Permission denied: unable to remove '{file_path}'.")
    except Exception as e:
        print(f"An error occurred while trying to remove the file: {e}")

def generate_random_string(length=10):
    # Define the character set: lowercase, uppercase letters, and digits
    characters = string.ascii_letters + string.digits
    # Generate a random string
    random_string = ''.join(random.choice(characters) for _ in range(length))
    return random_string

def chat_complete(text):
    completion = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": "Summarize the lecture content inside the prompt into 15%. The summary must less than 1000 tokens."},
            {"role": "user", "content": text}
        ]
    )
    return completion


