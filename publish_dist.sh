rm dist/PyDust-*
python3 setup.py bdist_wheel sdist
twine upload dist/*