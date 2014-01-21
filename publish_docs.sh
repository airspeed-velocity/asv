#!/bin/bash
# Convenience script to build and publish the docs to gh-pages

set -e

git clean -fxd
cd docs
make html
cd ..

git checkout --orphan gh-pages
# Clean out everything but the built files
git rm -rf .
cp -r docs/build/html/* .
rm -rf docs/build

touch .nojekyll
git add .nojekyll
git add *
git commit -m "Generated from sources"

git push -f upstream gh-pages

git checkout master
git branch -D gh-pages
