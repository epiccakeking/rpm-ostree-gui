dist:
	python3 -m build
clean:
	-rm -r dist rpm_ostree_gui.egg-info
pypi_upload:
	python3 -m twine upload dist/*
