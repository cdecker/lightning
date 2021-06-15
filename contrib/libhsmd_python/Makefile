#!/usr/bin/make
PKG="libhsmd"
VERSION="$(shell sed -n 's/VERSION="\(.*\)"/\1/p' setup.py)"
SDIST_FILE="dist/${PKG}-$(VERSION).tar.gz"

test:
	echo "${SDIST_FILE}"

LIBHSMD_PY_GEN_FILES := contrib/libhsmd_python/swig_wrap.c \
	contrib/libhsmd_python/libhsmd.py

PYTHON_GENERATED += contrib/libhsmd_python/libhsmd.py
CPPCHECK_OPTS += --suppress=nullPointer:contrib/libhsmd_python/swig_wrap.c

# Swig by default generates stubs in the file's directory, which is
# what we want.
$(LIBHSMD_PY_GEN_FILES): contrib/libhsmd_python/swig.i $(HSMD_SRC)
	swig -python -builtin contrib/libhsmd_python/swig.i


sdist $(SDIST_FILE):
	python3 setup.py sdist

test:
	python3 -m pytest test_libhsmd.py

# Create a test virtualenv, install from the testpypi and run the
# tests against it (make sure not to use any virtualenv that may have
# ${PKG} already installed).
test-release: sdist
	python3 -m twine upload --repository testpypi --skip-existing $(SDIST_FILE)
	virtualenv testpypi --python=/usr/bin/python3 --download --always-copy --clear
	testpypi/bin/python3 -m pip install -I --index-url https://test.pypi.org/simple/ --no-deps ${PKG}

	testpypi/bin/python3 -m pip install pytest
	testpypi/bin/python3 -m pytest test_libhsmd.py
	rm -rf testpypi

# Notice that since this uploads only the sdist file during its first
# run testing involves recompiling from source again. See [1] for
# details on how to build binary wheels for a variety of python
# versions and in a portable way.
#
# [1] https://github.com/cdecker/manylinux-builds
release: sdist
	python3 -m twine upload --skip-existing $(SDIST_FILE)
	virtualenv testpypi --python=/usr/bin/python3 --download --always-copy --clear
	testpypi/bin/python3 -m pip install -I --index-url https://test.pypi.org/simple/ --no-deps ${PKG}

	testpypi/bin/python3 -m pip install pytest
	testpypi/bin/python3 -m pytest test_libhsmd.py
	rm -rf testpypi
