#!/usr/bin/env python3

from __future__ import annotations
from sys import version, version_info


pVersion: tuple[int, int] = (int(3), int(10))
pExclude: tuple[int, int] = (int(3), int(12))
versionPass: bool = int(version_info[0]) == pVersion[0] and int(version_info[1]) >= pVersion[1]
excludePass: bool = int(version_info[0]) == pExclude[0] and int(version_info[1]) < pExclude[1]

if not versionPass or not excludePass:
    print(f"Python >= {pVersion[0]}.{pVersion[1]}, < {pExclude[0]}.{pExclude[1]} is required to run this script.")
    print(f"Installed: Python {version}")
    exit(1)


from datetime import datetime
from difflib import unified_diff
from dotenv import load_dotenv
from fire import Fire
from json import loads as jsonLoads
from json.decoder import JSONDecodeError
from os import access, getenv, mkdir, W_OK
from os.path import abspath, dirname, isfile, isdir, join
from pathlib import Path
from shutil import copy, which as find_executable
from subprocess import run
from sys import executable as py_exec
from traceback import print_exc
from typing import Any, Iterator, NamedTuple
from fire import Fire
import openai


# --------------------------------------------------
#   MODELS
# --------------------------------------------------

class ChangesOp(NamedTuple):
    operation: Operation
    line: int
    content: str


class Choices(NamedTuple):
    index: int
    message: dict[str, str]
    finish_reason: str


class Message(NamedTuple):
    role: str
    content: str


# --------------------------------------------------
#   CLASSES
# --------------------------------------------------

class Environment():
    OPENAI_API_KEY: str
    OPENAI_MODEL: str
    OPENAI_ORG_ID: str


class MetaConstant(type):
    """ A metaclass that defines a class' static properties to behave similar to an actual constant. """

    def __getattr__(cls, key):
        return cls[key]  # type: ignore

    def __setattr__(cls, key, value):
        ...


class Model(metaclass=MetaConstant):
    """ OpenAI GPT models. """

    Chat35: str = "gpt-3.5-turbo"
    Chat40: str = "gpt-4"
    Chat40_32K: str = "gpt-4-32k"


class Operation(metaclass=MetaConstant):
    """ DebugAI debug operations. """
    Delete: str = "Delete"
    InsertAfter: str = "InsertAfter"
    Replace: str = "Replace"


class Role(metaclass=MetaConstant):
    """ OpenAI ChatGPT message roles. """

    Assistant: str = "assistant"
    System: str = "system"
    User: str = "user"


class Style(metaclass=MetaConstant):
    """
    Style class for stdout text colorization.

    Usage:

    ```
    print(f"Some {Style.GREEN}text{Style.END} here.")
    ```
    """

    END: str        = "\033[0m"
    BOLD: str       = "\033[1m"
    UNDERLINE: str  = "\033[4m"
    INVERSE: str    = "\033[7m"
    BLACK: str      = "\033[30m"
    RED: str        = "\033[91m"
    GREEN: str      = "\033[92m"
    YELLOW: str     = "\033[93m"
    BLUE: str       = "\033[94m"
    MAGENTA: str    = "\033[95m"
    CYAN: str       = "\033[96m"
    WHITE: str      = "\033[97m"


# --------------------------------------------------
#   PRIVATE FUNCTIONS
# --------------------------------------------------

def __generate_date_value(separate: bool = False) -> str:
    """
    Generate a string value based on the current date.

    Default format will in `YYYYMMDD`.
    If `separate` is `True`, the format will in `YYYY-MM-DD`.
    """

    dateToday = datetime.today()
    separator = "-" if separate else ""

    return dateToday.strftime(f"%Y{separator}%m{separator}%d")


def __get_exe(script_name: str):
    """ Get the full path of the executable that will run `script_name`. """

    exeName: str = ""

    match Path(script_name).suffix:
        case ".dart":
            exeName = "dart"
        case ".java":
            exeName = "java"
        case ".js":
            exeName = "node"
        case ".ps1":
            return "PowerShell -File"
        case ".py":
            return py_exec

    if exeName != "":
        exePath: str | None = find_executable(exeName)

        if exePath in [None, ""]:
            raise Exception(f"There is {Style.RED}no executable found{Style.END} to run {Style.CYAN}{script_name}{Style.END}.")
    else:
        raise Exception(f"The script is {Style.RED}not supported{Style.END} by {Style.YELLOW}{SCRIPT_NAME}{Style.END}: {Style.CYAN}{script_name}{Style.END}")

    return str(exePath)


def __has_write_access(directory: str | None = None) -> bool:
    """ Checks if the current user has write permission for the `directory`. """

    directory = CURRENT_DIR if directory == None else directory

    if directory in [None, ""]:
        raise Exception("The directory to check for write access should be specified.")

    return access(directory, W_OK)


def __header():
    """ Prints a header for this script. """

    separator = '-' * ((len(SCRIPT_NAME) + len(SCRIPT_DESC)) + 3)
    print(f"{Style.CYAN}{SCRIPT_NAME}{Style.END} | {Style.MAGENTA}{SCRIPT_DESC}{Style.END}")
    print(separator)


def __init() -> None:
    """ Initialize and prepare the script for execution. """

    load_dotenv(override=True)

    Environment.OPENAI_API_KEY = getenv("OPENAI_API_KEY", "")
    Environment.OPENAI_MODEL = getenv("OPENAI_MODEL", Model.Chat35)
    Environment.OPENAI_ORG_ID = getenv("OPENAI_ORG_ID", "")

    if Environment.OPENAI_API_KEY in [None, ""]:
        print(f"The OpenAI {Style.CYAN}API Key{Style.END} is required before you can use this script.")
        exit(1)

    openai.api_key = Environment.OPENAI_API_KEY

    if Environment.OPENAI_ORG_ID not in [None, ""]:
        openai.organization = Environment.OPENAI_ORG_ID


def __openai_type_create(model: str, messages: list[dict[str, str]]):
    """ Creates a new chat completion for the provided messages and parameters. """

    return openai.ChatCompletion.create(
        model=model,
        messages=messages,
        temperature=OPENAI_TEMPERATURE,
    )


def __read_file_base(fileName: str, lineByLine: bool = False) -> list[str] | str:
    """ Reads the contents from the file specified in `fileName`. """

    fileNamePath: str = join(CURRENT_DIR, fileName)

    if isfile(fileNamePath):
        with open(fileNamePath, "r", encoding="utf-8") as fileIn:
            return fileIn.readlines() if lineByLine else fileIn.read().strip()

    return ""


def __read_file(fileName: str) -> str:
    """ Reads all the contents from the file specified in `fileName`. """

    return str(__read_file_base(fileName))


def __read_file_line(fileName: str) -> list[str]:
    """ Reads the contents, line by line, from the file specified in `fileName`. """

    return [line for line in __read_file_base(fileName, lineByLine=True)]


def __remove_styles(s: str) -> str:
    """ Removes any formatting made by the Style class. """

    replace = [value for name, value in vars(Style).items() if not name.startswith("_")]

    for value in replace:
        s = s.replace(value, "")

    return s


def __request_response(model: str, messages: list[dict[str, str]]) -> Any:
    jsonResponse: Any = ""
    response = __openai_type_create(model, messages)
    choices = Choices(**response["choices"][0]) # type: ignore
    message = Message(**choices.message)
    origContent: str = message.content
    formattedContent: str = origContent.replace("\n", "\n  ")

    # Include the response for context.
    messages.append(message._asdict())

    try:
        # Instead of just loading the supposed JSON response,
        #   it's better to look for it in the response before parsing it
        #   in case there are other texts before or after the actual JSON.
        jsonStartIndex: int = origContent.index("[")
        jsonContent: str = origContent[jsonStartIndex:]

        jsonResponse = jsonLoads(jsonContent)
        history(f"GPT Response:\n\n{origContent}")

    except (JSONDecodeError, ValueError) as e:
        status = f"{Style.RED}Error{Style.END}:\n\n  Invalid JSON. {e}\n\n"
        status += f"{Style.YELLOW}GPT Response{Style.END}:\n\n  {formattedContent}\n\n"
        status += "Rerunning the query...\n"
        print(status)
        history(status)

        # Add more context.
        messages.append(Message(Role.User, f"Invalid JSON. {e} Please fix and reiterate your last response.")._asdict())

        return __request_response(model, messages)

    except Exception as e:
        error = str(e).replace("\n", "\n  ")
        status = f"{Style.RED}Unknown error{Style.END}:\n\n  {error}"
        status += f"{Style.YELLOW}GPT Response{Style.END}:\n\n  {formattedContent}"
        raise Exception(status)

    return jsonResponse


# --------------------------------------------------
#   PUBLIC FUNCTIONS
# --------------------------------------------------

def apply_changes(file_path: str, changes: list[dict[str, Any]], confirm: bool = False) -> None:
    """ Implement the recommended changes to the script. """

    status: str = ""
    originalFileLines: list[str] = __read_file_line(file_path)
    fileLines: list[str] = originalFileLines.copy()
    operationChanges: list[ChangesOp] = [ChangesOp(**change) for change in changes if "operation" in change]
    explanations: list[str] = [str(change["explanation"]) for change in changes if "explanation" in change]

    # Reverse the order based on the line number.
    operationChanges.sort(key=lambda x: x.line, reverse=True)

    for change in operationChanges:
        match change.operation:
            case Operation.Delete:
                del fileLines[change.line - 1]
            case Operation.InsertAfter:
                fileLines.insert(change.line, f"{change.content}\n")
            case Operation.Replace:
                fileLines[change.line - 1] = f"{change.content}\n"

    # Get the differences between the original and the changes.
    lineDiffs: Iterator[str] = unified_diff(originalFileLines, fileLines, lineterm = "")

    print(f"{Style.YELLOW}Recommended changes to be made{Style.END}:")

    for lineDiff in lineDiffs:
        color: str = Style.WHITE

        if lineDiff.strip() == "+++" or lineDiff.strip() == "---":
            pass
        elif lineDiff.startswith("+"):
            color = Style.GREEN
        elif lineDiff.startswith("-"):
            color = Style.RED

        print(f"  {color}{lineDiff}{Style.END}")

    if len(explanations) > 0:
        status = f"\n{Style.BLUE}Explanation{Style.END}:\n\n"

        for explanation in explanations:
            status += f"  - {explanation}\n"

        print(status)

    if confirm:
        confirmApply = input("Do you want to apply these changes? (Y/n): ")
        confirmApply = confirmApply.lower().strip()

        if confirmApply in ["n", "no"]:
            print(f"\nThe recommended changes were {Style.RED}not{Style.END} applied.")
            exit()

    # Apply the changes.
    with open(file_path, "wt+") as f:
        f.writelines(fileLines)

    print("\nThe recommended changes have been applied.\n")


def execute_command(command: str, captureOutput: bool = True) -> tuple[str, str]:
    """
    This will execute the specified `command`.
    Then, it will capture and suppress any output (stdout) when `captureOutput` is set to `True`.

    When `captureOutput` is set to `True`, returns both the output and error in a tuple - `Output`, `Error`.
    Otherwise, will show the stdout as it happens.
    """

    cmdOutput: str = ""
    cmdError: str = ""

    cmdObj = run(command, shell=True, capture_output=captureOutput)

    if captureOutput:
        cmdOutput = "" if cmdObj.stdout in [None, ""] else cmdObj.stdout.decode("utf-8").strip()

    if cmdObj.returncode != 0:
        cmdError = "" if cmdObj.stderr in [None, ""] else cmdObj.stderr.decode("utf-8").strip()

    return cmdOutput, cmdError


def history(message: str) -> None:
    """ Log the execution details to history. """

    if message in [None, ""]:
        raise Exception("The history message should be specified.")

    historyDir: str = ".debugai-history"
    historyFile: str = join(historyDir, f"{__generate_date_value()}.log")
    dateToday = datetime.today()
    timestamp: str = dateToday.strftime(f"%H:%M:%S >>> ")

    if __has_write_access():
        if not isdir(historyDir):
            mkdir(historyDir)

        with open(historyFile, "at") as fileOut:
            fileOut.write(f"{timestamp}{__remove_styles(message)}\n")


def main(script_name: str, *script_args, restore: bool = False, model: str = "", confirm: bool = False):
    if model.strip() != "":
        validatedModel: list[str] = [value for name, value in vars(Model).items() if not name.startswith("_") and value == model]

        if len(validatedModel) == 0:
            print(f"You have specified an {Style.RED}invalid{Style.END} model: {Style.CYAN}{model}{Style.END}")
            exit(1)
        else:
            Environment.OPENAI_MODEL = model

    print(f"The {Style.UNDERLINE}model{Style.END} being used is {Style.GREEN}{Environment.OPENAI_MODEL}{Style.END}.\n")
    history(f"Model: {Environment.OPENAI_MODEL}")

    status: str = ""
    iterCount: int = 0
    currIterCount: int = iterCount

    if restore:
        backupFile: str = f"{script_name}_0.bak"

        if isfile(backupFile):
            copy(backupFile, script_name)
            status = f"Restored {Style.CYAN}{script_name}{Style.END} to its original state."
            print(status)
            history(status)
            exit(0)
        else:
            status = f"There is no back-up file to restore for {Style.CYAN}{script_name}{Style.END}."
            print(status)
            history(status)
            exit(1)

    exePath: str = __get_exe(script_name)
    scriptArgs: list[str] = [str(arg) for arg in script_args]

    while True:
        command: str = f"{exePath} {script_name} {' '.join(scriptArgs)}"
        cmdOutput, cmdError = execute_command(command.strip())
        history(f"{command = }")

        if cmdError in [None, ""]:
            status = f"{Style.CYAN}{script_name}{Style.END} has executed {Style.GREEN}without{Style.END} any errors.\n\n"
            status += f"Output:\n\n  {cmdOutput}"
            print(status)
            history(status)
            break
        else:
            cmdError = cmdError.replace("\n", "\n  ")

            if f"{script_name} --help" in cmdError:
                status = f"{Style.RED}Error{Style.END}:\n\n  {cmdError.strip()}"
                print(status)
                history(status)
                exit(1)

            # Create a backup of the original script.
            copy(script_name, f"{script_name}_{iterCount}.bak")

            status = f"{Style.CYAN}{script_name}{Style.END} has encountered {Style.RED}some issues{Style.END}.\n\n"
            status += f"{Style.RED}Error{Style.END}:\n\n  {cmdError.strip()}\n\n"
            status += "Debugging...\n"
            print(status)
            history(status)

            changes = post_to_openai(script_name, scriptArgs, cmdError, Environment.OPENAI_MODEL)

            if len(changes) > 0:
                # Create another backup of the script when there are more changes since the last one.
                if currIterCount < iterCount:
                    currIterCount = iterCount
                    copy(script_name, f"{script_name}_{iterCount}.bak")

                apply_changes(script_name, changes, confirm)

                status = f"Rerunning...\n"
                print(status)
            else:
                status = f"There are {Style.RED}no{Style.END} recommended changes even though there are issues."
                history(status)
                exit(0)

        iterCount += 1


def post_to_openai(script_name: str, script_args, error: str, model: str):
    fileLines: list[str] = __read_file_line(script_name)
    scriptLines: list[str] = []

    for i, line in enumerate(fileLines):
        scriptLines.append(f"{str(i + 1)}: {line}")

    scriptContentLines: str = "".join(scriptLines)
    openaiPrompt: str = (
        "Here is the script that needs to be fixed:\n\n"
        f"{scriptContentLines}\n\n"
        "Here are the arguments that were provided:\n\n"
        f"{script_args}\n\n"
        "Here is the error message:\n\n"
        f"{error}"
    )

    openaiMessages: list[dict[str, str]] = [
        Message(Role.System, OPENAI_PROMPT)._asdict(),
        Message(Role.User, openaiPrompt)._asdict()
    ]

    return __request_response(model, openaiMessages)


# --------------------------------------------------
#   GLOBAL VARIABLES
# --------------------------------------------------

CURRENT_DIR: str = dirname(abspath(__file__))
OPENAI_PROMPT: str = __read_file("openai_prompt.txt")
OPENAI_TEMPERATURE: float = 0.4
SCRIPT_NAME: str = "DebugAI"
SCRIPT_DESC: str = "OpenAI ChatGPT assisted debugging and code correction."


if __name__ == "__main__":
    __header()
    __init()

    try:
        Fire(main)

    except Exception as error:
        print(f"{Style.INVERSE}{Style.RED}Something went wrong:{Style.END}")
        print()
        print(error)
        history(str(error))

        # Print the stack trace to give a hint where to start looking.
        print(f"\n\n{Style.INVERSE}{Style.WHITE}Stack Trace:{Style.END}\n")
        print_exc()

    except KeyboardInterrupt:
        notice: str = f"The user has {Style.RED}interrupted{Style.END} the execution."
        print(notice)
        history(notice)

    finally:
        print()
