# Shift assignment with Pyomo

This app solves a shift asssignment problem using [Pyomo][pyomo]. Given a
set of previously planned shifts, in this app we assign workers to those shifts,
taking different factors into account such as availability and qualification.

The most important files created are `main.py` and `input.json`.

* `main.py` implements a MIP shift assignment solver.
* `input.json` is a sample input file.

## Usage

Follow these steps to run locally.

1. The packages listed in the `requirements.txt` file are available when using
   the runtime specified in the `app.yaml` manifest. This runtime is used when
   making remote runs. When working locally, make sure that all the required
   packages are installed:

    ```bash
    pip3 install -r requirements.txt
    ```

1. Further dependencies can be specified in the `requirements_extra.txt` file.
   These dependencies will get bundled with the app on push.

1. Run the command below to check that everything works as expected:

    ```bash
    python3 main.py -input input.json -output output.json -duration 30
    ```

1. A file `output.json` should have been created with a solution to the shift
   assignment problem.

## Mirror running on Nextmv Cloud locally

Pre-requisites: Docker needs to be installed.

To run the application locally in the same docker image as the one used on the
Nextmv Cloud, you can use the following command:

```bash
cat input.json | docker run -i --rm \
-v $(pwd):/app ghcr.io/nextmv-io/runtime/pyomo:latest \
sh -c 'python3 /app/main.py'
```

You can also debug the application by running it in a Dev Container. This
workspace recommends to install the Dev Container extension for VSCode. If you
have the extension installed, you can open the workspace in a container by using
the command `Dev Containers: Reopen in Container`.

[pyomo]: http://www.pyomo.org/
