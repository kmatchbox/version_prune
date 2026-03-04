# Version Prune

A tool to help managed old comps, pre-comps or renders as a project progresses.

### How To Use:
`python version_prune.py --path /path/to/project --threshold 5 --folders comp renders`

#### Flags:
**--path / p** = The path to start crawling from

**--threshold / -t** = Number of versions to keep

**--folders / -f** = List of folders to search for versioned folder in (i.e comp, pre_comp, renders)

**--dry / -d** = Dry-run 



### What It Does:
Scans for version folders within the specified folders. If there are more version folders than are specified by the threshold, then those will be added to a list. You'll be prompted at the end of the run if you wish to remove all the matches.

**Important:** Currently this assumes that your version folders begin with v0. It assume a folder structre like the following:
shot_0010/comps/v001, v002, v003, etc.