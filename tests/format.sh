#!/bin/bash

poetry run black --check --diff .
poetry run isort --check --diff .
poetry run flake8 .
poetry run pylint *py


