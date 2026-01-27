---
name: pre-commit
description: Summarize commit messages for recent changes
disable-model-invocation: true
---

The following steps are done before `git commit`

## Instructions

1. Check if all Python files pass the linter

    ```bash
    uv run black --check --diff . && uv run isort --check --diff .
    ```

2. Handle linting issues, if any; otherwise, skip this step
   1. Show violations and list the diff summary for manual review
   2. Run `black` and `isort` to fix these issues

        ```bash
        uv run black . && uv run isort .
        ```

3. Run `git status` to see changed files

4. Generate a commit message for users

    - Keep it concise

5. Ask users if he/she wants to commit these changes on his/her behalf

    - List the commit message for manual review
    - List all changed files for manual review, in case we wrongly include any files
    - Remember to include the sign-off

        ```bash
        git commit -s -m "<your commit message>"
        # or
        git commit --signoff -m "<your commit message>"
        ```
