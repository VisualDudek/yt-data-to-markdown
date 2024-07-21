# yt-data-to-markdown
Fetch YouTube data and saves it in a [markdown file](./yt_videos.md).

[App config](./yt_config.yaml)

# Dev Notes
- How to solve Pylance `missing imports` in VSCode when install package from git as editable.
```bash
#settings.json
	"python.analysis.extraPaths": ["/workspaces/yt-data-to-markdown/src/yt-viewer"]
```

## Features
- gh action workflow: `Python application` - build md file and if there is diff then commit to main
- gh action run on by scheduled trigger once per day 

## Branch/todo
- `dev-md` (merged) - create md file using MdUtils package