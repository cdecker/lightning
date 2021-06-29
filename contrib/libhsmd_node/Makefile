#!/usr/bin/make

all: build/Release/hsmd.node

deps:
	npm install node-addon-api bindings 
	npm install -g node-gyp

build/Release/hsmd.node:
	node-gyp configure
	node-gyp rebuild

test: build/Release/hsmd.node
	node test.js

clean:
	rm -rf build
