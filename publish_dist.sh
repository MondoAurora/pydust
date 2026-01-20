rm -rf dist
python3 -m build -v
twine upload dist/*