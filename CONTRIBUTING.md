# Contributing

## Where to start

All contributions, bug reports, bug fixes, documentation improvements, enhancements, and ideas are welcome.

The best place to start is to check the [issues](https://github.com/sanders41/async-search-client/issues)
for something that interests you.

## Bug Reports

Please include:

1. A short, self-contained Python snippet reproducing the problem. You can format the code by using
[GitHub markdown](https://docs.github.com/en/free-pro-team@latest/github/writing-on-github). For example:

    ```py
    from async_search_client import Client

    async with Client(BASE_URL, MASTER_KEY) as client:
        client.index("movies")
        ...
    ```

2. Explain what is currently happening and what you expect instead.

## Working on the code

### Fork the project

In order to work on the project you will need your own fork. To do this click the "Fork" button on
this project.

Once the project is forked clone it to your local machine:

```sh
git clone https://github.com/your-user-name/async-search-client.git
cd async-search-client
git remote add upstream https://github.com/sanders41/async-search-client.git
```

This creates the directory async-search-client and connects your repository to the upstream (main project) repository.

### Working with the code

Note: This project uses Poetry to manage dependencies. If you do not already have Poetry installed you will need to install it with the instuctions [here](https://python-poetry.org/docs/#installation)

Once you have cloned your fork of the repository you can create a virtual environment. When using Poetry the step is optional.
If you create a virtual environment Poetry will use the environment you have activated, or Poetry will create
and use it's own if you don't create one. If you want to create your own, once you are in the async-search-client directory create and activate
the virtual environment. This step is slightly different for Mac/Linux and Windows.

Mac/Linux

```sh
# Create the environment
python3 -m venv venv

# Activate the environment
. venv/bin/activate
```

Windows

```powershell
# Create the environment
python -m venv venv

#Activate the environment. Use activate.bat for cmd.exe
venv\Scripts\Activate.ps1
```

Next the requirements need to be installed.

```sh
poetry install
```

### Creating a branch

You want your main branch to reflect only production-ready code, so create a feature branch for
making your changes. For example:

```sh
git checkout -b my-new-feature
```

This changes your working directory to the my-new-feature branch. Keep any changes in this branch
specific to one bug or feature so the purpose is clear. You can have many my-new-features and switch
in between them using the git checkout command.

When creating this branch, make sure your main branch is up to date with the latest upstream
main version. To update your local main branch, you can do:

```sh
git checkout main
git pull upstream main --ff-only
```

### Code Standards and tests (isort, flake8, black, mypy, pytest, tox, and pre-commit)

async-search-client uses [isort](https://pycqa.github.io/isort/),
[Flake8](https://flake8.pycqa.org/en/latest/), [Black](https://github.com/psf/black), and [mypy](https://mypy.readthedocs.io/en/stable/) to ensure consistant code formmating.

You can run linting on your code at any time with:

```sh
# Run isort
isort async_search_client tests

# Run black
black async_search_client tests

# Run flake8
flake8 async_search_client test

# Run mypy
mypy async_search_client
```

* Note if you did not create your own virtual environment and are using the Poetry environment instead you will need to append `poetry run ...` to each command.

```sh
# Run isort
poetry run isort async_search_client tests

# Run black
poetry run black async_search_client tests

# Run flake8
poetry run flake8 async_search_client tests

# Run mypy
poetry run mypy async_search_client
```

It is also suggested that you setup [pre-commit](https://pre-commit.com/) in order to run linting when you commit changes to you branch. To setup pre-commit for this project run:

```sh
pre-commit install
```

After this pre-commit will automatically run any time you check in code to your branches. You can also run pre-commit at any time with:

```sh
pre-commit run --all
```

### Type Hints

At a minimum all variables/arguments that receive data should contain type hints, and all functions/methods should specify the return type.

Accepted examples:

```py
def my_function(argument: str) -> None:
    ...


def another_funciton(num: int) -> int:
    return num + 1
```

Rejected examples:

```py
def my_function(argument):
    ...


def another_function(num):
    return num + 1
```

Type hints on files in the tests directory are optional.

### Testing

This project uses [pytest](https://docs.pytest.org/en/stable/) and [tox](https://tox.readthedocs.io/en/latest/) for testing. Please ensure that any additions/changes you make to the code have tests to go along with them. Code coverage should not drop blow it's current level with any pull requests you make, if it does the pull request will not be accepted.
You can view the current coverage level in the codecov badge on the
[main github page](https://github.com/sanders41/async-search-client). You can run tests and see the
code coverage by running.

Before running the tests start a Docker container running MeiliSearch.

```sh
docker pull getmeili/meilisearch:latest
docker run -p 7700:7700 getmeili/meilisearch:latest ./meilisearch --master-key=masterKey --no-analytics=true
```

Now with the container running run the test suite

```sh
pytest
```

Or if you are using Poetry's virtual environment

```sh
poetry run pytest
```

If you want to see which lines are missing code coverage run the test with:

```sh
pytest --cov-report term-missing
```

or

```sh
poetry run pytest --cov-report term-missing
```

In additon to mainting the coverage percentage please ensure that all
tests are passing before submitting a pull request.

tox can be used to run both linting, and run the tests in all versions of Python async-search-client supports. Note that you will need to have all the verions of Python installed for this to work.

```sh
tox
```

or

```sh
poetry run tox
```

Running tox before submitting a pull request can save your time because these tests will be run by Continuious Integraion when a pull request is submitted and will need to pass there before being accepted.

## Committing your code

Once you have made changes to the code on your branch you can see which files have changed by running:

```sh
git status
```

If new files were created that and are not tracked by git they can be added by running:

```sh
git add .
```

Now you can commit your changes in your local repository:

```sh
git commit -am 'Some short helpful message to describe your changes'
```

If you setup pre-commit and any of the tests fail the commit will be cancelled and you will need to fix any errors. Once the errors are fixed you can run the same git commit command again.

## Push your changes

Once your changes are ready and all linting/tests are passing you can push your changes to your forked repositry:

```sh
git push origin my-new-feature
```

origin is the default name of your remote repositry on GitHub. You can see all of your remote repositories by running:

```sh
git remote -v
```

## Making a Pull Request

After pushing your code to origin it is now on GitHub but not yet part of the async-search-client project. When you’re ready to ask for a code review, file a pull request. Before you do, once again make sure that you have followed all the guidelines outlined in this document regarding code style, tests, and documentation.

### Make the pull request

If everything looks good, you are ready to make a pull request. This is how you let the maintainers of the async-search-client project know you have code ready to be reviewed. To submit the pull request:

1. Navigate to your repository on GitHub
2. Click on the Pull Request button for your feature branch
3. You can then click on Commits and Files Changed to make sure everything looks okay one last time
4. Write a description of your changes in the Conversation tab
5. Click Send Pull Request

This request then goes to the repository maintainers, and they will review the code.

### Updating your pull request

Changes to your code may be needed based on the review of your pull request. If this is the case you can make them in your branch, add a new commit to that branch, push it to GitHub, and the pull request will be automatically updated. Pushing them to GitHub again is done by:

```sh
git push origin my-new-feature
```

This will automatically update your pull request with the latest code and restart the Continuous Integration tests.

Another reason you might need to update your pull request is to solve conflicts with changes that have been merged into the main branch since you opened your pull request.

To do this, you need to rebase your branch:

```sh
git checkout my-new-feature
git fetch upstream
git rebase upstream/main
```

There may be some merge conficts that need to be resolved. After the feature branch has been update
locally, you can now update your pull request by pushing to the branch on GitHub:

```sh
git push origin my-new-feature
```

If you rebased and get an error when pushing your changes you can resolve it with:

```sh
git push origin my-new-feature --force
```

## Delete your merged branch (optional)

Once your feature branch is accepted into upstream, you’ll probably want to get rid of the branch. First, merge upstream main into your main branch so git knows it is safe to delete your branch:

```sh
git fetch upstream
git checkout main
git merge upstream/main
```

Then you can do:

```sh
git branch -d my-new-feature
```

Make sure you use a lower-case -d, or else git won’t warn you if your feature branch has not actually been merged.

The branch will still exist on GitHub, so to delete it there do:

```sh
git push origin --delete my-new-feature
```
