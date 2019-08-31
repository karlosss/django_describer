#!/bin/bash -x

pip install --user --upgrade setuptools wheel
python setup.py sdist bdist_wheel
pip install --user --upgrade twine
python3 -m twine upload dist/*
rm -rf build dist *.egg-info
