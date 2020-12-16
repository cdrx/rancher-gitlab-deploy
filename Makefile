publish:
	pip install wheel
	python setup.py sdist bdist_wheel

upload:
	pip install twine
	python -m twine upload dist/*
