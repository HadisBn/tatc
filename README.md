# Tradespace Analysis Toolkit for Constellations (TAT-C)

The Tradespace Analysis Toolkit for Constellations (TAT-C) provides low-level
data structures and functions for systems engineering analysis and design of
Earth-observing space missions.

Documentation: https://tatc.readthedocs.io

## Installation

TAT-C uses conda and the conda-forge channel for distribution because some of
the underlying libraries are platform dependent.

The simplest way to use TAT-C is to install it with the command:
```shell
conda install tatc -c conda-forge
```
Then, TAT-C is available for use in any Python script my importing:
```python
import python
```

Alternatively, to run TAT-C from a local source, (e.g., for editing
TAT-C functionality), clone this repository and create a new conda environment:
```shell
conda env create -f environment.yml
```
Then, activate the tatc_env environment and install the tatc library:
```shell
conda activate tatc_env
pip install -e .
```

### Faster Installation

For faster dependency solving during installation, consider installing the
mamba package:
```shell
conda install mamba -c conda-forge
```
and replace `conda` with `mamba` in the installation instructions above.

## Unit Tests

Run unit tests:
```shell
python -m unittest
```
## Contact

Paul T. Grogan <pgrogan@stevens.edu>

## Acknowledgements

This project was supported in part by the National Aeronautics and Space
Administration (NASA) Earth Science Division (ESD) Earth Science Technology
Office (ESTO) Advanced Information Systems Technology (AIST) program under
grant numbers: NNX17AE06G, 80NSSC17K0586, 80NSSC20K1118, and 80NSSC21K1515.

Current Project Team
 * PI: Paul T. Grogan <pgrogan@stevens.edu>
 * I. Josue Tapia-Tamayo <itapiata@stevens.edu>

Project Alumni
 * Isaac Feldman
 * Hayden Daly
 * Lindsay Portelli
 * Matthew Sabatini
 * Evan Abel
 * Sigfried Hache
