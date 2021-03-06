*NOTE: This repository has been moved to https://gitlab.com/mcgrid/mcgridify-rivet-analyses.*

# mcgridifyRivetAnalyses.py
This script prepares existing [Rivet](rivet.hepforge.org) analyses for use with [MCgrid](mcgrid.hepforge.org):

- It downloads the analysis files or use a local copy.
- The prefix 'MCgrid_' is added to the analysis name.
- An include statement for MCgrid is added to the analysis source file.

Rivet hosts a [list of analyses](https://rivet.hepforge.org/analyses).

## Example usage

Let’s say you’d like to use `MC_WINC` and `MC_JETS` to produce interpolation grids using MCgrid.
You have Rivet 2.2.0 installed.
Just go to the directory where you want the output files to be put and run the following command:

```
/path/to/mcgridifyRivetAnalyses.py --help
/path/to/mcgridifyRivetAnalyses.py --rivet-version=2.2.0 MC_WINC MC_JETS
```

Note that you still need to add the lines to the resulting `.cc` file to create grids and fill them.
