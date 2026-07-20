# Changelog

All notable changes to the GM-SEUS dataset and code are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Versions correspond to the citable Zenodo releases of the dataset and code, not
to individual commits. A new entry is added when a new version DOI is minted.

- Dataset (all versions): https://doi.org/10.5281/zenodo.14827818
- Code (all versions): https://doi.org/10.5281/zenodo.14829529
- Article: [Stid et al., 2025, *Scientific Data*](https://doi.org/10.1038/s41597-025-05862-4)

## [2.1] - 2026-07-19

### Added
- `name`: project name from source datasets where available
- `storage`: whether the array is co-located with battery storage (`Yes`, `No`, `Unknown`), from USPVDB and LBNL USS
- `storTech`: storage technology type (e.g., lithium-ion), from LBNL USS
- `storMW`: storage power capacity (MW), from LBNL USS
- `storMWh`: storage energy capacity (MWh), from LBNL USS
- `storInstYr`: storage installation year, from LBNL USS
- `sourceConf`: geometry confidence rating (`high`, `medium`, `low`), qualitatively attributed from array `Source` based on boundary delineation method (e.g., expert interpretation, citizen science, machine learning), and panel-row presence (`numRow` > 0)

### Changed
- Updated USPVDB source dataset to the most recent version (as of 2025-07-13)
- `modType` now separates `thin-film` into `cdte`, `cigs`, `a-si`, and `thin-film-other` using EIA Form 860 data where available (e.g., USPVDB, LBNLUSS)
- Updated array `Source` for all `GMSEUSgeoref_v2_0` arrays, properly attributing the original spatial source and the georeferencing or digitization method for arrays derived from the v1.0 point data and released in v2.0

## [2.0] - 2026-04-20

### Added
- CEC Solar Footprints in California (CECSFC) and Global Renewables Watch (GRW) polygon datasets
- 24,182 hand-delineated panel-rows (5.29 km²) across 1,485 arrays
- 24.4 km² of new array area (95 arrays), 89 new arrays (17.4 km²), and georeferenced metadata for 1,225 arrays
- `grndCvr` ground cover management practice attribute, derived from NREL InSPIRE (agrivoltaic = vegetation) and CEC (parking lot = impervious)
- `capMWAC` and `capMWACest` reported and estimated AC capacity attributes
- Documentation for panel-row digitization and array georeferencing workflows

### Changed
- Updated all source datasets to latest versions (as of 2025-11-07)
- Installation year now uses reverse temporal segmentation (inspired by [Cullerton et al., 2025](https://doi.org/10.1016/j.srs.2025.100322)), extending the range to 2006–2024 (MAE: 1.84 years)
- Centralized core utilities into `osmUtils.py`, `gmseusUtils.py`, and `geeUtils.js`
- Consolidated installation year validation into a single Google Earth Engine script
- Updated CRS for SHP and GPKG outputs to EPSG:6350

## [1.0] - 2025-04-06

### Added
- Initial public release of GM-SEUS: harmonized ground-mounted solar arrays and panel-rows across CONUS, with value-added attributes (installation year, azimuth, mount technology, panel-row dimensions, inter-row spacing, ground cover ratio, tilt, and installed capacity)