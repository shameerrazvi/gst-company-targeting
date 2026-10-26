# Reference data

`australian_postcodes.csv` maps each postcode to ABS statistical areas (SA3 and SA4). It comes from
the community-maintained [Australian Postcodes](https://github.com/matthewproctor/australianpostcodes)
dataset by Matthew Proctor, and `run_analysis.py --rebuild` downloads it automatically. It isn't
stored in this repository.

Only the ASGS 2016 columns (`sa3name`, `sa4name`) are used. The file's 2021 columns
(`SA4_NAME_2021` and similar) are misaligned in the current version: postcode 3000 (Melbourne) is
listed under Mornington Peninsula, for example.
