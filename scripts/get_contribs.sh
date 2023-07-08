#!/bin/bash

# Function to fetch full name from GitHub
fetch_full_name() {
    username=$1
    full_name=$(curl -s -L "https://github.com/$username" | head -n 100 | grep -oP '(?<=<title>).*(?=· GitHub</title>)' | awk -F'(' '{print $2}' | awk -F')' '{print $1}')
    if [[ -n $full_name ]]; then
        echo "$full_name"
    else
        echo "@$username"
    fi
}

export -f fetch_full_name

# Get unique names from git log
names=$(git log --all --pretty="%an" | sort -u)

# Separate single-word names (usernames) and multi-word names
usernames=$(echo "$names" | grep -P '^\w+$')
multi_word_names=$(echo "$names" | grep -Pv '^\w+$')

# Use xargs for parallelism
full_names=$(echo "$usernames" | xargs -P 10 -I {} bash -c 'fetch_full_name "$@"' _ {})

# Combine multi-word names and full names, remove duplicates
all_names=$(echo -e "$multi_word_names\n$full_names" | sort -u)

# Print the names in rst format
# echo "Credits"
# echo "-------"
# echo ""
# echo ".. rst-class:: credits-list"
# echo ""
while IFS= read -r name; do
    # echo "- $name"
    echo "$name"
done <<< "$all_names"

