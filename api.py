"""Main script for the autogpt package."""
import logging
import random
import sys

from colorama import Fore

from autogpt.agent.agent import Agent
from autogpt.app import get_command, execute_command
from autogpt.chat import chat_with_ai, create_chat_message
from autogpt.config import Config, check_openai_api_key, AIConfig
from autogpt.configurator import create_config
from autogpt.json_utils.json_fix_llm import fix_json_using_multiple_techniques
from autogpt.json_utils.utilities import validate_json
from autogpt.logs import logger, print_assistant_thoughts
from autogpt.memory import get_memory, LocalCache
from autogpt.prompt import construct_prompt
from autogpt.spinner import Spinner
from autogpt.utils import get_current_git_branch, get_latest_bulletin

from flask import Flask, request
from flask import send_file
from flask_cors import CORS
import os
os.environ["PATH"] =os.environ["PATH"] +":/opt/render/project/.render/chrome/opt/google/chrome"

app = Flask(__name__)
CORS(app)


# #input
# Question - feedback - tasks

## output
# thoughts - reasoning

user_agent={}
user_assistant_reply={}
user_files={}
# id agent

# @app.route("/<id>/<ai_role>/<ai_goals>")
@app.route('/auth',methods = ['GET'])
def auth():
    # id=request.args.get('id')
    id=random.randint(0, 100)
    print(id)
    print(user_agent)
    while id in user_agent:
        id = random.randint(0, 100)

    ai_goals = request.args.get('goals')
    ai_role=request.args.get('role')
    print(ai_role)
    print(ai_goals)
    if id and ai_role and ai_goals:
        print("HERE")
    else:
        print("BAD REQUEST")
        return '{"statue":"BAD REQUEST"}'

    ai_goals = ai_goals.replace("'", "")
    ai_goals = ai_goals.replace("[", "")
    ai_goals = ai_goals.replace("]", "")
    print(id)
    print(ai_goals.split(","))
    # string h=""

    ai_name="AI Bot"
    # print(Goals)
    system_prompt = AIConfig(ai_name, ai_role, ai_goals.split(",")).construct_full_prompt()
    # Initialize variables
    full_message_history = []
    next_action_count = 0
    # Make a constant:
    triggering_prompt = (
        "Determine which next command to use, and respond using the"
        " format specified above:"
    )
    # print(system_prompt)
    cfg = Config()
    memory = LocalCache(cfg)
    memory.clear()
    agent = Agent(
        ai_name=ai_name,
        memory=memory,
        full_message_history=full_message_history,
        next_action_count=next_action_count,
        system_prompt=system_prompt,
        triggering_prompt=triggering_prompt,
    )
    user_agent[id]=agent
    # print(agent)
    return '{"statue":"Good","id":'+str(id)+'}'

# @app.route("/thoughts/<id>/")
@app.route('/thoughts',methods = ['GET'])
def get_thoughts():
    id=request.args.get('id')
    if id:
        id=int(id)
        pass
    else:
        return "BAD REQUEST"

    cfg = Config()
    print(user_agent)
    # memory = LocalCache(cfg).clear()
    # print("memory")
    # print(memory)
    # agent = Agent(
    #     ai_name=ai_name,
    #     memory=memory,
    #     full_message_history=full_message_history,
    #     next_action_count=next_action_count,
    #     system_prompt=system_prompt,
    #     triggering_prompt=triggering_prompt,
    # )
    # Send message to AI, get response

    print(type(id))
    print(user_agent[id])
    with Spinner("Thinking... "):
        assistant_reply = chat_with_ai(
            user_agent[id].system_prompt,
            user_agent[id].triggering_prompt,
            user_agent[id].full_message_history,
            user_agent[id].memory,
            cfg.fast_token_limit,
        )
    assistant_reply_json = fix_json_using_multiple_techniques(assistant_reply)
    # Print Assistant thoughts
    if assistant_reply_json != {}:
        validate_json(assistant_reply_json, "llm_response_format_1")
        # Get command name and arguments
        try:
            print_assistant_thoughts(user_agent[id].ai_name, assistant_reply_json)
            thoughts= assistant_reply_json.get("thoughts", {})
            command_name, arguments = get_command(assistant_reply_json)
            # command_name, arguments = assistant_reply_json_valid["command"]["name"], assistant_reply_json_valid["command"]["args"]
        except Exception as e:
            logger.error("Error: \n", str(e))
    user_assistant_reply[id]=assistant_reply
    return assistant_reply_json

# @app.route("/choose_action/<id>/<action>")
@app.route('/choose_action',methods = ['GET'])
def choose_action():
    id=request.args.get('id')
    action=request.args.get('action')
    if id and action:
        id=int(id)
        print(id)
        print(user_assistant_reply)
        
        pass
    else:
        return "BAD REQUEST"
    assistant_reply = user_assistant_reply[id]
    assistant_reply_json = fix_json_using_multiple_techniques(assistant_reply)
    command_name, arguments = get_command(assistant_reply_json)
    if action.lower().strip() == "y":
        user_input = "GENERATE NEXT COMMAND JSON"
    elif action.lower().strip() == "":
        print("Invalid input format.")
    elif action.lower().startswith("y -"):
        try:
            next_action_count = abs(
                int(action.split(" ")[1])
            )
            user_input = "GENERATE NEXT COMMAND JSON"
        except ValueError:
            print(
                "Invalid input format. Please enter 'y -n' where n is"
                " the number of continuous tasks."
            )
    elif action.lower() == "n":
        user_input = "EXIT"
    else:
        user_input = action
        command_name = "human_feedback"

    # Execute command
    if command_name is not None and command_name.lower().startswith("error"):
        result = (
            f"Command {command_name} threw the following error: {arguments}"
        )
    elif command_name == "human_feedback":
        result = f"Human feedback: {user_input}"
    else:
        result = (
            f"Command {command_name} returned: "
            f"{execute_command(command_name, arguments)}"
        )
        if user_agent[id].next_action_count > 0:
            user_agent[id].next_action_count -= 1

    memory_to_add = (
        f"Assistant Reply: {assistant_reply} "
        f"\nResult: {result} "
        f"\nHuman Feedback: {user_input} "
    )
    print(user_agent[id].memory)
    user_agent[id].memory.add(memory_to_add)

    # Check if there's a result from the command append it to the message
    # history
    if result is not None:
        user_agent[id].full_message_history.append(create_chat_message("system", result))
        logger.typewriter_log("SYSTEM: ", Fore.YELLOW, result)
        return result
    else:
        user_agent[id].full_message_history.append(
            create_chat_message("system", "Unable to execute command")
        )
        logger.typewriter_log(
            "SYSTEM: ", Fore.YELLOW, "Unable to execute command"
        )
        # print("^^ RESULT ^^")
    # print(result)
        return "Unable to execute command"

#
@app.route('/download',methods = ['GET'])
def downloadFile():
    fileName=request.args.get('fileName')
    path = "/var/auto_gpt_workspace/"+fileName
    return send_file(path, as_attachment=True)
if __name__ == "__main__":
    app.run()

    # auth(1,"an AI designed to tech me about auto gpt", ['search auto gpt', 'find the github and figure out what the project is', 'explain what the auto gpt is in a file named autgpt.txt', 'terminate'])
    # print(get_thoughts(1))
    #
    # while True:
    # choose_action(1,"y -1")

# def main(
#         continuous: bool,
#         continuous_limit: int,
#         ai_settings: str,
#         skip_reprompt: bool,
#         speak: bool,
#         debug: bool,
#         gpt3only: bool,
#         gpt4only: bool,
#         memory_type: str,
#         browser_name: str,
#         allow_downloads: bool,
#         skip_news: bool,
# ) -> None:
#         cfg = Config()
#         check_openai_api_key()
#         create_config(
#             continuous,
#             continuous_limit,
#             ai_settings,
#             skip_reprompt,
#             speak,
#             debug,
#             gpt3only,
#             gpt4only,
#             memory_type,
#             browser_name,
#             allow_downloads,
#             skip_news,
#         )
#
#         ai_name = ""
#         # check versions
#         motd = get_latest_bulletin()
#         if motd:
#             logger.typewriter_log("NEWS: ", Fore.GREEN, motd)
#         git_branch = get_current_git_branch()
#         if git_branch and git_branch != "stable":
#             logger.typewriter_log(
#                 "WARNING: ",
#                 Fore.RED,
#                 f"You are running on `{git_branch}` branch "
#                 "- this is not a supported branch.",
#             )
#         if sys.version_info < (3, 10):
#             logger.typewriter_log(
#                 "WARNING: ",
#                 Fore.RED,
#                 "You are running on an older version of Python. "
#                 "Some people have observed problems with certain "
#                 "parts of Auto-GPT with this version. "
#                 "Please consider upgrading to Python 3.10 or higher.",
#             )
#
#         # AI Name Role Goals
#         ai_name = ""
#         ai_role=""
#         ai_goals=""
#         system_prompt = AIConfig(ai_name, ai_role, ai_goals).construct_full_prompt()
#         # system_prompt = construct_prompt()
#
#         # print(prompt)
#         # Initialize variables
#         full_message_history = []
#         next_action_count = 0
#         # Make a constant:
#         triggering_prompt = (
#             "Determine which next command to use, and respond using the"
#             " format specified above:"
#         )
#         # Initialize memory and make sure it is empty.
#         # this is particularly important for indexing and referencing pinecone memory
#         #
#         # memory = LocalCache(cfg)
#         # memory.clear()
#
#         memory = LocalCache(cfg).clear()#get_memory(cfg, init=True)
#
#         logger.typewriter_log(
#             "Using memory of type:", Fore.GREEN, f"{memory.__class__.__name__}"
#         )
#         logger.typewriter_log("Using Browser:", Fore.GREEN, cfg.selenium_web_browser)
#
#         # party start from here
#         agent = Agent(
#             ai_name=ai_name,
#             memory=memory,
#             full_message_history=full_message_history,
#             next_action_count=next_action_count,
#             system_prompt=system_prompt,
#             triggering_prompt=triggering_prompt,
#         )
#
#         agent.start_interaction_loop()
#
