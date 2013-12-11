#!/bin/bash

set -e

# Create a new "orphaned" branch -- we don't need history for
# the built products
git checkout --orphan gh-pages

# This will delete all of the git-managed files here, but not
# the results of the build
git rm -rf .
# Copy the built files to the root
cp -r ${HTML_DIR}/* .

# Delete the original location of the built files
rm -rf ${HTML_DIR}

# We need to tell github this is not a Jekyll document
touch .nojekyll
git add .nojekyll
git add *
git commit -m "Generated from sources"

git push -f origin gh-pages
