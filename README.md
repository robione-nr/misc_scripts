# Misc Scripts

Small operational scripts used for personal automation and maintenance tasks.

This repository is organized as one folder per script or workflow. Each folder should contain its own README, runtime notes, dependencies, and any non-secret configuration examples needed to operate that workflow.

## Scripts

- [X README Cards](x-readme-cards/README.md): fetches recent X posts and updates the `robione-nr` GitHub profile README with a three-card post row.

## Repository Notes

- Keep secrets out of git. Files such as `config.json`, virtualenvs, generated outputs, logs, cloned work directories, and state databases should be ignored.
- Prefer each script folder to be self-contained: script, README, requirements, and example config if needed.
- Run scripts from their own folder unless the script README says otherwise.

