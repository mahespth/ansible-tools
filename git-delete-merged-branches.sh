
git branch --merged | grep -vE '^\*|main|master' | xargs -n 1 git branch -d
