#!/bin/bash

set -e

# Create a new "orphaned" branch -- we don't need history for
# the built products
git checkout --orphan gh-pages

# We need to tell github this is not a Jekyll document
touch .nojekyll
git add .nojekyll
git add -f html
git mv html/* .
git commit -m "Generated from sources"

git push -f origin gh-pages
git checkout master
