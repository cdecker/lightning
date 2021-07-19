#!/usr/bin/make

all: build/Release/hsmd.node

deps:
	npm install node-addon-api bindings 
	npm install -g node-gyp

build/Release/hsmd.node: src
	node-gyp configure binding-$(shell uname -s).gyp
	node-gyp rebuild binding-$(shell uname -s).gyp

test: build/Release/hsmd.node
	node test.js

clean:
	rm -rf build src

src:
	git clone --recursive ../../ src
	(cd src; ./configure --disable-developer --disable-valgrind --enable-experimental-features && make)
