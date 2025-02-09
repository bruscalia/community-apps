# Nextmv AMPL Python template

This template demonstrates how to solve a Mixed Integer Programming problem
using the AMPL Python package [amplpy][amplpy].

To solve a Mixed Integer Problem (MIP) is to optimize a linear objective
function of many variables, subject to linear constraints. We demonstrate this
by solving the knapsack problem.

Knapsack is a classic combinatorial optimization problem. Given a collection of
items with a value and weight, our objective is to maximize the total value
without exceeding the weight capacity of the knapsack.

The input defines a number of items which have an id to identify the item, a
weight and a value. Additionally there is a weight capacity.

The most important files created are `main.py`, `input.json`, and
`ampl_license_uuid.template`.

* `main.py` implements a MIP knapsack solver.
* `input.json` is a sample input file.
* `ampl_license_uuid.template` is a file demonstrating how to use the AMPL UUID
  license key.
  * If you have an AMPL license, remove the `.template` extension and replace
    the contents with your actual license key to be left with a file named
    `ampl_license_uuid`. Modify the `app.yaml` file to include the
    `ampl_license_uuid` in the files list. Note: when running on Nextmv Cloud,
    you should use a premium execution class to use your own AMPL license.
  * If you are just testing and don’t have an AMPL license, you don’t need to
    do anything, as this community app ships with logic that allows you to test
    AMPL with limits per AMPL’s website.

Follow these steps to run locally.

1. The packages listed in the `requirements.txt` will get bundled with the app
   as defined in the `app.yaml` manifest. When working locally, make sure that
   these are installed as well:

    ```bash
    pip3 install -r requirements.txt
    ```

2. Run the command below to check that everything works as expected:

    ```bash
    python3 main.py -input input.json -output output.json \
      -duration 30 -provider cbc
    ```

3. A file `output.json` should have been created with the optimal knapsack
   solution.

## Mirror running on Nextmv Cloud locally

Pre-requisites: Docker needs to be installed.

To run the application locally in the same docker image as the one used on the
Nextmv Cloud, you can use the following command:

```bash
cat input.json | docker run -i --rm \
-v $(pwd):/app ghcr.io/nextmv-io/runtime/python:3.11 \
sh -c 'pip install -r requirements.txt > /dev/null && python3 /app/main.py'
```

You can also debug the application by running it in a Dev Container. This
workspace recommends to install the Dev Container extension for VSCode. If you
have the extension installed, you can open the workspace in a container by using
the command `Dev Containers: Reopen in Container`.

## Next steps

* Open `main.py` and read through the comments to understand the model.
* Further documentation, guides, and API references about custom modeling and
  deployment can also be found on our [blog](https://www.nextmv.io/blog) and on
  our [documentation site](https://docs.nextmv.io).
* Need more assistance? Send us an [email](mailto:support@nextmv.io)!

[amplpy]: https://amplpy.ampl.com/en/latest/?_gl=1*16ca5pw*_ga*Nzk4OTUwMDgwLjE3MDgzNTIzMzg.*_ga_FY84K2YRRE*MTcwODQ0NTgwMy42LjEuMTcwODQ0NTgzOC4wLjAuMA..
