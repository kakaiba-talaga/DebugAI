# DebugAI

OpenAI assisted debugging and code correction.

This has been _inspired_ by Wolverine ➜ [https://github.com/biobootloader/wolverine](https://github.com/biobootloader/wolverine)

- [DebugAI](#debugai)
    - [Dependencies](#dependencies)
    - [Directory and File Structure](#directory-and-file-structure)
    - [Set-up](#set-up)
    - [Supported Scripts](#supported-scripts)
    - [Usage](#usage)
        - [Normal](#normal)
        - [Set the Model to Use](#set-the-model-to-use)
        - [Confirmation before any Changes](#confirmation-before-any-changes)
        - [Restore Back-up](#restore-back-up)
    - [Contribute](#contribute)
    - [License](#license)


## Dependencies

- Python `>= 3.11`


## Directory and File Structure

- `/.debugai-history` ➜ This is the directory where the logs are being stored.

- `.env-template` ➜ The environment template file to get you started. Specify the credentials in key-value format. Rename this to `.env`. Once _renamed_, it is meant to be stored _locally_ and _not to be uploaded_ to any code repositories.

- `debugai.py` ➜ The main script.

- `debugai_requirements.txt` ➜ The list of all the python packages needed to run the script.


## Set-up

1. Create a virtual environment:

    ```shell
    python -m venv {VENV_DIRECTORY_NAME}
    ```

2. Activate the virtual environment:

    ```shell
    source ./{VENV_DIRECTORY_NAME}/bin/activate
    ```

3. Install the python package dependencies:

    ```shell
    python -m pip install -r debugai_requirements.txt
    ```

[Go back to TOC](#debugai)


## Supported Scripts

This now supports multiple but limited types of scripts:

1. Dart ➜ `*.dart`
2. Java ➜ `*.java`
3. Node.js ➜ `*.js`
4. PowerShell ➜ `*.ps1`
5. Python ➜ `*.py`

[Go back to TOC](#debugai)


## Usage

There are several ways to use this script.

### Normal

```shell
python debugai.py {SCRIPT_NAME} {SCRIPT_ARGUMENTS}
```

### Set the Model to Use

By default, this uses the `gpt-3.5-turbo` model.

```shell
python debugai.py {SCRIPT_NAME} {SCRIPT_ARGUMENTS} --model=gpt-4
```

I recommend using `gpt-3.5-turbo` over the other GPT-3.5 models because of its lower cost.

Reference ➜ [https://platform.openai.com/docs/models](https://platform.openai.com/docs/models)

### Confirmation before any Changes

Once set, this will ask the user for confirmation before doing any changes.

```shell
python debugai.py {SCRIPT_NAME} {SCRIPT_ARGUMENTS} --confirm=True
```

### Restore Back-up

By default, depending on the number of batch changes, there could be several back-up files being created. To restore the script to its _original state_:

```shell
python debugai.py {SCRIPT_NAME} --restore
```

[Go back to TOC](#debugai)


## Contribute

Community contributions are encouraged! Feel free to report bugs and feature requests to the [issue tracker](https://github.com/kakaiba-talaga/DebugAI/issues) provided by _GitHub_.


## License

`DebugAI` is an Open-Source Software _(OSS)_ and is available for use under the [GNU GPL v3](https://github.com/kakaiba-talaga/DebugAI/blob/main/LICENSE) license.

[Go back to TOC](#debugai)
