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
from dotenv import load_dotenv
from enum import Enum
from fire import Fire
from os import access, getenv, mkdir, W_OK
from os.path import abspath, dirname, isfile, isdir, join
from pathlib import Path
from shutil import copy, which as find_executable
from subprocess import run
from sys import executable as py_exec
from traceback import print_exc
from typing import Any, Iterator, NamedTuple
from fire import Fire
import difflib
import json
import openai


# --------------------------------------------------
#   GLOBAL VARIABLES
# --------------------------------------------------

CURRENT_DIR: str = dirname(abspath(__file__))
OPENAI_PROMPT: str = ""
OPENAI_TEMPERATURE: float = 0.4
SCRIPT_NAME: str = "DebugAI"
SCRIPT_DESC: str = "OpenAI assisted debugging and code correction."


# --------------------------------------------------
#   MODELS
# --------------------------------------------------

class Environment():
    OPENAI_API_KEY: str
    OPENAI_MODEL: str
    OPENAI_ORG_ID: str


class ChangesOp(NamedTuple):
    operation: str
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

class MetaConstant(type):
    """ A metaclass that defines a class' static properties to behave similar to an actual constant. """

    def __getattr__(cls, key):
        return cls[key]  # type: ignore

    def __setattr__(cls, key, value):
        ...


class Models(Enum):
    __metaclass__ = MetaConstant

    Chat35 = "gpt-3.5-turbo"
    Chat40 = "gpt-4"
    Chat40_32K = "gpt-4-32k"
    DaVinci35 = "text-davinci-003"
    DaVinci35_Code = "code-davinci-002"


class Operation(Enum):
    __metaclass__ = MetaConstant

    Delete = "Delete"
    InsertAfter = "InsertAfter"
    Replace = "Replace"


class Style(metaclass=MetaConstant):
    """
    Style class for stdout text colorization.

    Usage:

    ```
    print(f"Some {Style.GREEN}text{Style.END} here.")
    ```
    """

    END         = "\033[0m"
    BOLD        = "\033[1m"
    UNDERLINE   = "\033[4m"
    INVERSE     = "\033[7m"
    BLACK       = "\033[30m"
    RED         = "\033[91m"
    GREEN       = "\033[92m"
    YELLOW      = "\033[93m"
    BLUE        = "\033[94m"
    MAGENTA     = "\033[95m"
    CYAN        = "\033[96m"
    WHITE       = "\033[97m"


# --------------------------------------------------
#   PRIVATE FUNCTIONS
# --------------------------------------------------

def __init() -> None:
    """ Initialize and prepare the script for execution. """

    load_dotenv(override=True)

    Environment.OPENAI_API_KEY = getenv("OPENAI_API_KEY", "")
    Environment.OPENAI_MODEL = getenv("OPENAI_MODEL", Models.Chat35.value)
    Environment.OPENAI_ORG_ID = getenv("OPENAI_ORG_ID", "")

    openai.api_key = Environment.OPENAI_API_KEY

    if Environment.OPENAI_ORG_ID not in [None, ""]:
        openai.organization = Environment.OPENAI_ORG_ID


def __generate_date_value(separate: bool = False) -> str:
    """
    Generate a string value based on the current date.

    Default format will in `YYYYMMDD`.
    If `separate` is `True`, the format will in `YYYY-MM-DD`.
    """

    dateToday = datetime.today()
    separator = "-" if separate else ""

    return dateToday.strftime(f"%Y{separator}%m{separator}%d")


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


def __openai_type_create(which_model: str, messages: list[dict[str, Any]]):
    """ Creates a new chat or text completion for the provided messages and parameters. """

    match which_model:
        case Models.Chat35.value | Models.Chat40.value | Models.Chat40_32K.value:
            return openai.ChatCompletion.create(
                model=which_model,
                messages=messages,
                temperature=OPENAI_TEMPERATURE,
            )
        case Models.DaVinci35.value | Models.DaVinci35_Code.value:
            return openai.Completion.create(
                model=which_model,
                messages=messages,
                temperature=OPENAI_TEMPERATURE,
            )
        case _:
            return openai.ChatCompletion.create(
                model=Models.Chat35.value,
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


def __request_response(model: str, messages: list[dict[str, Any]]) -> Any:
    response = __openai_type_create(model, messages)
    choices = Choices(**response["choices"][0]) # type: ignore
    message = Message(**choices.message)
    messages.append(message._asdict())
    content: str = message.content
    jsonResponse: Any = ""

    try:
        jsonStartIndex: int = content.index("[")
        jsonData: str = content[jsonStartIndex:]
        jsonResponse = json.loads(jsonData)
        jsonData = jsonData.replace("\n", "\n  ")
        history(f"GPT Response:\n\n  {jsonData}")

    except (json.decoder.JSONDecodeError, ValueError) as e:
        content = content.replace("\n", "\n  ")
        status = f"{Style.RED}Error{Style.END}:\n\n  Invalid JSON. {e}\n\n"
        status += f"{Style.YELLOW}GPT Response{Style.END}:\n\n  {content}\n\n"
        status += "Rerunning the query...\n"
        print(status)
        history(status)

        messages.append(Message("user", "Your JSON response could not be parsed. Please reiterate your last message as pure JSON.")._asdict())
        return __request_response(model, messages)

    except Exception as e:
        content = content.replace("\n", "\n  ")
        error = str(e).replace("\n", "\n  ")
        status = f"{Style.RED}Unknown error{Style.END}:\n\n  {error}"
        status += f"{Style.YELLOW}GPT Response{Style.END}:\n\n  {content}"
        raise Exception(status)

    return jsonResponse


__init()


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
            case Operation.Delete.value:
                del fileLines[change.line - 1]
            case Operation.InsertAfter.value:
                fileLines.insert(change.line, f"{change.content}\n")
            case Operation.Replace.value:
                fileLines[change.line - 1] = f"{change.content}\n"

    # Get the differences between the original and the changes.
    lineDiffs: Iterator[str] = difflib.unified_diff(originalFileLines, fileLines, lineterm="")

    print(f"{Style.YELLOW}Recommended changes to be made{Style.END}:")

    for lineDiff in lineDiffs:
        color: str = Style.WHITE

        if lineDiff.startswith("+"):
            color = Style.GREEN
        elif lineDiff.startswith("---"):
            pass
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


def main(script_name: str, *script_args, restore: bool = False, model: str = Environment.OPENAI_MODEL, confirm: bool = False):
    __header()

    if Environment.OPENAI_API_KEY in [None, ""]:
        print(f"The OpenAI {Style.CYAN}API Key{Style.END} is required before you can use this script.")
        exit(1)

    if model != Environment.OPENAI_MODEL:
        validatedModel: list[str] = [str(m.value) for m in Models if str(m.value) == model]

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

            changes = post_to_openai(script_name, scriptArgs, cmdError, model)

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

    openaiMessages: list[dict[str, Any]] = [
        Message("system", OPENAI_PROMPT)._asdict(),
        Message("user", openaiPrompt)._asdict()
    ]

    return __request_response(model, openaiMessages)


if __name__ == "__main__":
    try:
        OPENAI_PROMPT = __read_file("openai_prompt.txt")
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
