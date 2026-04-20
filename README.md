<p align="center">
    <img width="1008" src = "https://github.com/stidjaco/GMSEUS/blob/main/images/GMSEUS_logo_v2_0.png">
 </p>

# A harmonized dataset of ground-mounted solar energy in the US with enhanced metadata
Code repository for creating and maintaining the Ground-Mounted Solar Energy in the United States (GM-SEUS) spatiotemporal dataset of solar arrays and panel-rows using existing datasets, machine learning, and object-based image analysis to enhance existing sources. A [peer-reviewed article](http://doi.org/10.1038/s41597-025-05862-4) describing the purpose and methods behind GM-SEUS has been accepted in Scientific Data (link not yet live)

## Current Version Notes
This is the 2025 release of GM-SEUS (version 2.0). All input datasets and solar panel-row delineation results are up-to-date through November 7th, 2025. The Zenodo repository for the dataset, version notes, and documentation can be found [here](https://doi.org/10.5281/zenodo.14827818), and for the current code version can be found [here](https://doi.org/10.5281/zenodo.14829529).

### v2.0 Technical Updates
* Updated all source datasets to latest versions (as of 11-07-2025)  
* Added **CEC Solar Footprints in California (CECSFC)** and **Global Renewables Watch (GRW)** polygon datasets  
* Added **24,182 hand-delineated panel-rows** (5.29 km²) across 1,485 arrays  
* Expanded dataset with **24.4 km² new array area (95 arrays)**, **89 new arrays (17.4 km²)**, and georeferenced metadata for **1,225 arrays**
* Added **ground cover management practice attribute (`grndCvr`)**, derived from NREL InSPIRE (agrivoltaic arrays = *vegetation*) and California Energy Commission (parking lot arrays = *impervious*)  
* Added **reported and estimated AC capacity attributes (`capMWAC` and `capMWACest`)**
* Implemented new **reverse temporal segmentation** method for installation year (inspired by [Cullerton et al., 2025](https://doi.org/10.1016/j.srs.2025.100322)), extending range to 2006–2024 (MAE: 1.84 years)  
* Added documentation for panel-row digitization and array georeferencing workflows  
* Centralized core utilities: `osmUtils.py`, `gmseusUtils.py`, and `geeUtils.js`  
* Consolidated installation year validation into a single Google Earth Engine script  
* Updated CRS for SHP and GPKG outputs to **EPSG:6350**  

# Product Description

## Overview

Solar energy generating systems are critical components of our expanding energy infrastructure, yet available datasets remain incomplete or not publicly available–particularly at the sub-array level. Combining the best open-access datasets in the US with image analysis on freely available remotely-sensed imagery, we present the Ground-Mounted Solar Energy in the United States (GM-SEUS) dataset, a harmonized, open access geospatial and temporal repository of solar energy arrays and panel-rows.

GM-SEUS v2.0 includes 18,980 commercial- and utility-scale ground-mounted solar photovoltaic and concentrating solar energy arrays (292 GW<sub>DC</sub>), spanning 3,817 km<sup>2</sup>. Of these, 12,739 arrays (112 GW<sub>DC</sub>) include detailed panel-row geometries, comprising 3.43 million unique solar panel-rows across 527 km<sup>2</sup>. When restricted to arrays verifiable through high-resolution satellite and aerial imagery (hand-delineated spatial data sources and/or containing panel-row information ~ low commission error), the dataset contains 15,744 arrays, representing 204 GW<sub>DC</sub> and 2,586 km<sup>2</sup>.

We use these newly compiled and delineated solar arrays and panel-rows to harmonize and independently estimate value-added attributes to existing datasets including installation year, azimuth, mount technology, panel-row area and dimensions, inter-row spacing, ground cover ratio, tilt, and installed capacity. By estimating and harmonizing these attributes of the distributed US solar energy landscape, GM-SEUS supports diverse applications in renewable energy modeling, ecosystem service assessment, and infrastructure planning. 

![alt text](images/GMSEUS_CONUS_H3_v2_0.png "GM-SEUS solar array distribution")

## Approach

GM-SEUS is both a harmonization of existing solar energy array data in the US and a new product of solar panel-row spatiotemporal information, providing new insights on perviously under-reported metadata attributes. We used a combination of machine learning and geographic object-based image analysis, often referred to as GEOBIA or OBIA. Importantly, this new dataset is publicly available, with code available here and the associated Zenodo Repository containing all final products of GM-SEUS v2.0 and locations for source datasets.

We defined a solar array spatial footprint as: _adjacent, existing, and connected rows of solar panel-rows (PV or CSP) of the same installation year, and the row-spacing between them_. Panel-rows are defined by: _spatially-unique collection of one or more panel-assemblies connected by proximity and often sharing one mount, but not necessarily electrically connected_. Datasets with existing solar array boundaries in the United States are GM-SEUS (v1.0), United States Solar Photovoltaic Database (USPVDB), OpenStreetMap (OSM), TransitionZero Global Solar Asset Mapper (TZSAM), The Nature Concervancy, Microsoft, and Planet Labs Global Renewables Watch (GRW), with regional datasets from California Energy Commission (CEC) Solar Footprints in California (SFC), California's Central Valley Photovoltaic Dataset (CCVPV), and Chesapeake Watershed Solar Data (CWSD). Datasets containing value-added attributes and point-locations included the NREL Agrivoltaic Map from the InSPIRE initiative, the LBNL Utility-Scale Solar 2024 Edition Report, IEA and NREL SolarPACES initiative, Global Energy Monitor’s Global Solar Power Tracker, and The World Resources Institute's Global Power Plant Database. 

We removed repeat geometries in order of spatial quality in relation to our deviation of an array, and georectified existing point-location sources within 190 m of existing array shapes. For points without a georectified array boundary, we manually annotated new array boundaries or rectify existing boundaries outside 190 m. Finally, rooftop solar arrays were removed by intersection with OpenBuildingMap from Oostwegel et al. ([2025](https://doi.org/10.1038/s41597-025-06132-z)). The conceptual hierarchy of system boundaries and logic behind mount classification are shown below. 

![alt text](images/SystemBoundriesAndMountClassificationLogic.png "Conceptual hierarchical system boundaries when considering solar infrastructure and solar panel-row metadata logic")

The above image is the conceptual hierarchical system boundaries when considering solar infrastructure and solar panel-row metadata logic, critical for understanding this dataset and approach. Green boundaries indicate the conceptual boundary for each term. This study reports the geospatial and temporal characteristics of panel-rows and arrays. A panel-row a spatially-unique collection of one or more panel-assemblies connected by proximity and often sharing one mount, but not necessarily electrically connected. An array is composed of one or more adjacent rows of the same installation year, and the row-spacing between them. The cell, panel, assembly and project are not the system boundaries focused on in this study. The ratio of the long-edge to the short-edge is the L/W ratio. Azimuth is initially defined as the primary cardinal direction of the short-edge vector (face of the panel-row) in the minimum bounding rectangle in south facing angles given that all solar arrays were in the northern hemisphere.

Existing solar panel-rows datasets were compiled from GMSEUS v1.0, OpenStreetMap, and a newly digitized panel-row [dataset](https://doi.org/10.5281/zenodo.17042798). To acquire panel-rows within solar array boundaries without existing panel-row information we used National Agriculture Imagery Program (NAIP) imagery and applied unsupervised object-based image segmentation and supervised machine learning approaches. We classified NAIP imagery using a Random Forest model and four spectral indices with displayed utility in classify solar energy: normalized difference photovoltaic index (NDPVI), normalized blue deviation (NBD), brightness (Br), normalized difference vegetation index (NDVI), normalized difference water index (NDWI). We trained the model using 2,000 panel-row samples from Stid et al. (2022), and 10,000 landcover validation points from Pengra et al. (2020). NAIP imagery dates used in the development of GM-SEUS v2.0 are shown below.

![alt text](images/naipMostRecentGEE_ColorMap_v2_0.png "The most recently available NAIP imagery dates as of November 7th, 2025. ")

Spatial context was incorporated using object-based imagery analysis methods, including using simple non-iterative clustering (SNIC) of each spectral index’s grey-level co-occurrence matrix (GLCM) sum average. We then clustered SNIC values using X-means clustering, and use the Random Forest model to classify pixel-clusters. We also removed low-quality panel-rows using several object-based metrics of geometrical similarity including minimum (15 m<sup>2</sup>) and maximum (2,750 m<sup>2</sup>) panel-row area, perimeter-area-ratio, area-bounding-box, long-edge to short-edge ratios, and compactness, all relative to metric values form existing solar panel-row. The logic behind panel-row and new array boundary delineation is shown below. 

![alt text](images/panelRowDelineationLogic.png "Example panel-row delineation and array boundary logic for each mount technology")

## Source Datasets

### Array Polygon-Level Data

* **Ground-Mounted Solar Energy in the US (GMSEUS) Array and Panels**: Arrays downloaded from [GMSEUS Portal](https://zenodo.org/records/14827819), Last Download: 08-20-2025 (Up-to-date as of 11-07-2025), Version 1.0
  * GMSEUS v1.0 panel rows were contained within the repository, while newly digitized panel-rows used in this work were stored and downloaded from [Zenodo Portal](https://doi.org/10.5281/zenodo.17042798). These new panel-rows were also uploaded to OpenStreetMap as part of the current GM-SEUS version, independently of other products.
  * We also digitized and georeferenced the remaining point-level array data from version 1.0. These were stored locally and are included as part of the current GM-SEUS version.

* **GM-SEUS Digitized and Georeferenced Arrays**: Downloaded from Google Earth Engine assets, Last Download: 09-30-2025 (Up-to-date as of 11-07-2025), Unpublished dataset prepared for this GM-SEUS version

* **GM-SEUS Digitized Panel-Rows**: Panel-rows downloaded from [Zenodo](https://doi.org/10.5281/zenodo.17042798), Last Download: 09-12-2025 (Up-to-date as of 11-07-2025), Version 1.1
  * Created for this GM-SEUS version. Note: v2.0 existed internally, but v1.1 was never formally released.

* **United States Solar Photovoltaic Database (USPVDB)**: Downloaded from [USPVDB Portal](https://eerscmap.usgs.gov/uspvdb/data/), Last Download: 08-25-2025 (Up-to-date as of 11-07-2025), Version 3.0

* **California Energy Commission (CEC) Solar Footprints in California (SFC)**: Downloaded from [CEC Portal](https://cecgis-caenergy.opendata.arcgis.com/datasets/CAEnergy::solar-footprints-in-california/explore), more information at [CA Open Data Portal](https://lab.data.ca.gov/dataset/solar-footprints-in-california), Last Download: 09-12-2025 (Up-to-date as of 11-07-2025), Version - Last updated: September 12, 2025; Created: July 2, 2025

* **California's Central Valley Photovoltaic Dataset (CCVPV) Arrays and Panels**: Downloaded from [figshare](https://doi.org/10.6084/m9.figshare.23629326.v1), Last Download: 07-18-2024 (Up-to-date as of 11-07-2025), Version 1.0

* **Chesapeake Watershed Solar Data (CWSD) Arrays**: Downloaded from [OSFHOME](https://osf.io/vq7mt/), Last Download: 12-01-2024 (Up-to-date as of 11-07-2025), We downloaded derived polygons as well as manually annotated training polygons and preferenced training polygons over derived for their completeness and quality, No version details

* **OpenStreetMap Solar Panels and Arrays (OSM)**: Array and panel objects were downloaded using the _osmnx_ package in `script1_getOSMdata.ipynb`, Last OSM scrape: 11-02-2025

* **TransitionZero Global Solar Asset Mapper (TZSAM)**: Downloaded from [TZ-SAM Portal](https://www.transitionzero.org/products/solar-asset-mapper/download), Last Download: 11-07-2025 (Up-to-date as of 11-07-2025), Other information: [Website](https://solar.transitionzero.org/), [Viewer](https://solar-map.transitionzero.org/), [SciData Preprint](https://zenodo.org/records/11368204/files/tz-sam_scientific_data.pdf?download=1), Version Q3-2025 (Version 6)
  * Follow-on project containing all information from [Kruitwagen et al., 2021](https://zenodo.org/records/5005868).

* **The Nature Conservancy, Microsoft, and Planet Labs Global Renewables Watch (GRW)**: Downloaded from [GitHub](https://github.com/microsoft/global-renewables-watch/releases/tag/v1.0), Last Download: 10-30-2025 (Up-to-date as of 11-07-2025), Other information: [Atlas](https://www.globalrenewableswatch.org/atlas), [Preprint](https://arxiv.org/pdf/2503.14860v1), Version 1

### Array Point-Level Data

* **NREL Innovative Solar Practices Integrated with Rural Economies and Ecosystems (InSPIRE) Database**: Downloaded from [InSPIRE Portal](https://openei.org/wiki/InSPIRE/Agrivoltaics_Map), Last Download: 10-30-2025 (Up-to-date as of 11-07-2025)

* **LBNL Utility-Scale Solar (USS), 2025 Edition**: Downloaded from [LBNL Utility-Scale Solar Portal](https://emp.lbl.gov/utility-scale-solar/), Last Downloaded: 10-30-2025 (Up-to-date as of 11-07-2025), Version 2025
  * Large Excel report; project-level data were copied from the original `.xlsx` file to a new `.csv` from the `Individual_Project_Data` tab.

* **NREL PV Data Acquisition (PV-DAQ) Database**: Downloaded from [PV-DAQ Portal - Available Systems Information](https://data.openei.org/submissions/4568), and [PVDAQ Data Map](https://openei.org/wiki/PVDAQ/PVData_Map), Last Downloaded: 10-30-2025 (Up-to-date as of 11-07-2025)

* **International Energy Agency (IEA) & NREL Solar Power and Chemical Energy System (SolarPACES) Database**: Downloaded from [Project Page](https://solarpaces.nrel.gov/), Last Downloaded: 07-29-2024 (Up-to-date as of 11-07-2025), More information at [US CSP Project Pages](https://solarpaces.nrel.gov/by-country/US)
  * While SolarPACES is the overarching project (and how we refer to the dataset here), the product is called [CSP.guru](https://csp.guru/).

* **Global Solar Power Tracker (GSPT) from Global Energy Monitor (GEM) and TransitionZero**: Downloaded from [GEM Portal](https://globalenergymonitor.org/download-data-success/), Last Downloaded: 07-16-2025 (Up-to-date as of 11-07-2025), Version Feb 2025 release
  * Access request required.

* **World Resource Institute (WRI) Global Power Plant Database (GPPDB)**: Downloaded from [WRI Portal](https://datasets.wri.org/dataset/globalpowerplantdatabase), Last Downloaded: 10-30-2025 (Up-to-date as of 11-07-2025), Version 1.3.0

## Codebase Description:

All code used in the acquisition and development of this dataset is available in this [Github repository](https://github.com/stidjaco/GMSEUS). Files are ipynb or js files, where js files are JavaScript files intended to be run in the [GEE code editor](https://code.earthengine.google.com/). Files are named in order of operation (e.g., `script1` < `script2`).

### The GM-SEUS open code repository contains the following files

Environment Files: 
* `BigPanel.yml`: General python environment for most ipynb files. 
* `BigPanelGEE.yml`: Python environment for `script5` that requires GEE access and cloud repository. 
* `BigPanelTilt.yml`: Python environment for `script8` that requires pvlib integration and thus a different version of python.
 
Utility Files: 
* `gmseusUtils.py`: General helper functions for all GM-SEUS processing.
* `osmUtils.py`:  Helper functions for OpenStreetMap related processing. 
* `geeUtils.js`:  Helper functions for Google Earth Engine related processing.

General Code Files: All file require the completion of all prior files for inputs. 
* `config.txt`: Config file containing variable constants used throughout processing.
* `script1_getOSMdata.ipynb`: Python file for pulling and processing OSM data for each state. No required inputs.
* `script2_prepareExistingSolarDB.ipynb`: Python file for compiling and harmonizing existing solar databases.
* `script3_getSolarPanels.js`: GEE file for acquiring NAIP imagery within array bounds and extracting panel-row boundaries if they exist in available imagery. 
* `script4_processSolarPanels.ipynb`: Python file for compiling and quality control of solar panel-row objects. File also creates new array boundaries.
* `script5_getGroundMounted.ipynb`: Python file for removing rooftop mounted solar arrays and panel-rows. 
* `script6_getInstallationYear.js`: GEE file for applying LandTrendr temporal segmentation within array boundaries to acquire a year of change.
* `script7_harmonizeFillAttributes.ipynb`: Python file for preparing and harmonizing all final GM-SEUS attributes (except tilt).
* `script8_getOptimalTilt.ipynb`: Python file for using _pvlib_ to estimate the optimum tilt angle of fixed-axis (and mixed-axis) arrays.
* `script9_prepRepository.ipynb`: Python file for preparing the final checks and exports for upload to the Zenodo Repository.
* `script10_technicalValidation.ipynb`: Python file for processing technical validation of GM-SEUS.

Supplementary Files: 
* `script7a_validateInstYr.js`: GEE file for manual validation of installation year using available snapshot NAIP, Sentinel-2, and Landsat 7 ETM+ imagery and timeseries. 
* `scriptTrainRF.js`: GEE file for compiling and assessing the new landcover training dataset to classify solar panel-rows in NAIP imagery.
* `scriptGetLabeledImages.js`: GEE file for preparing and exporting 4-band NAIP and a GM-SEUS panel-row burned in imagery (as a 5th band) over an array to generate labeled imagery. 
* `script_createLabeledImages.ipynb`: Python file for taking in whole labeled images from `scriptGetLabeledImages.txt` and splitting into 256 x 256 pixel tiled images and masks. 
* `scriptPlot_maps.ipynb`: Python file for printing and export relevant result maps.
  
## Dataset Description: 
Files are within subdirectories **GPKG**, **SHP**, and **CSV**. All data products are available in the Zenodo Repository. All input datasets can be downloaded from source files described in the associated paper, at the top of this document, at the top of `script2`, and in the Zenodo data README. All intermediate products are available upon request, and are automatically generated in the processing of the code repo. Geospatial files in the final database are provided as shapefiles, geopackages, and comma separated values. 

### The GM-SEUS v1.0 data repository contains the following files

* **GMSEUS_Arrays_Final_2025_v2_0**: Final array dataset containing boundaries from existing datasets and enhanced by buffer-dissolve-erode technique with GM-SEUS panel-rows containing all array-level attributes (EPSG:6350), geopackage, shapefile, and csv
* **GMSEUS_Panels_Final_2025_v2_0**: Final panel-row dataset containing boundaries from existing datasets and newly delineated GM-SEUS panel-rows containing all panel-row-level attributes (EPSG:6350),  geopackage, shapefile, and csv
* **GMSEUS_NAIP_Arrays_2025_v2_0**: All array boundaries created by buffer-dissolve-erode method of newly delineated (NAIP) GM-SEUS panel-rows (EPSG:6350),  geopackage, shapefile, and csv
* **GMSEUS_NAIP_Panels_2025_v2_0**: All newly delineated panel-row boundaries (EPSG:6350), geopackage, shapefile, and csv
* **GMSEUS_NAIP_PanelsNoQAQC_2025_v2_0**: All newly delineated panel-rows from NAIP imagery without any quality control (EPSG:6350),  geopackage, shapefile, and csv
* **NAIPtrainRF**: Training dataset of 12,000 NAIP training points (2,000 class<sup>-2</sup>) containing class values, spectral index values, the year of NAIP imagery accessed, and point coordinates (WGS84), comma separated values
* **NAIPclassifyRF**: Random forest classifier trees and weights as output from Google Earth Engine classifier, comma separated values
* **LabeledImages**: Directory containing image and mask subdirectories with ~17,500 input and target images for deep learning pattern recognition applications, GeoTIFF
  * NOTE: As of v2.0, NAIPtrainRF, NAIPclassifyRF, and LabeledImages have not been updated beyond v1.0.

### We provide the following attribute fields in GM-SEUS Final Arrays

* **arrayID**: unique numeric ID of each solar array in GM-SEUS, unitless  
* **Source**: array boundary source from existing datasets, unitless  
* **nativeID**: numeric ID of each solar array from the source spatial dataset if an indexing system existed, unitless  
* **latitude**: latitude of the array boundary centroid (NAD83), decimal degrees  
* **longitude**: longitude of the array boundary centroid (NAD83), decimal degrees  
* **newBound**: binary, whether the array boundary was derived from the existing data sources (0) or from a buffer-dissolve-erode of panel-rows following our definition of an array boundary (1), unitless  
* **totArea**: total land footprint of panel-rows and the space between them, m²  
* **totRowArea**: If **numRow** is greater than 0, sum of rowArea within an array. Otherwise, estimated based on **totArea** and **GCR1** estimation where no panel-rows were detected, m²  
* **numRow**: number of panel-rows within an array, m²  
* **instYr**: installation year from existing sources, with gaps filled in by **instYrLT**, year  
* **instYrEst**: Reverse temporal segmentation-derived installation year independent of any data source other than Landsat spectral trajectory, year  
* **capMWDC**: installed peak capacity from existing sources, with gaps filled in by **capMWDCest**, MWDC or MWth  
* **capMWDCest**: estimated installed peak capacity derived from capacity to panel-row area relationships independent of any data source, MWDC or MWth 
* **capMWAC**: installed AC capacity from existing sources, with gaps filled using **capMWACest**, MWAC  
* **capMWACest**: estimated AC capacity derived from DC capacity (reported or estimated) using DC-to-AC conversion assumptions, independent of any external AC data source, MWAC  
* **modType**: reported panel-row (module) technology at the array level (c-si, mono-c-si, multi-c-si, thin-film, csp). If unreported, assumed to be c-si, unitless  
* **effInit**: initial panel-rows efficiency from existing sources with gaps filled in based on efficiency estimation from **modType** and **instYr** taken from the annual Tracking the Sun report, %  
* **GCR1**: 0-1, the ratio of **totRowArea** to the total area of panel-rows and the space between them. For arrays with complete panel delineation and arrays where **newBound** is 1, this is equivalent to **totArea**. This is also called packing factor. If **numRow** is greater than 0, **GCR1** is an actual **GCR1** for the array. Otherwise, **GCR1** is estimated by linear regression of latitude and longitude by mount and module type, unitless  
* **GCR2**: 0-1, the ratio of the average width of the panel-row short edge (**rowWidth**) to the horizontal ground distance between identical panel-rows points, defined as the sum of **widthAvg** and **rowSpace**. If **numRow** is greater than 0, **GCR2** is an actual **GCR2** for the array. Otherwise, **GCR2** is estimated by linear regression of latitude and longitude by mount and module type, unitless  
* **mount**: mount technology derived from the azimuth and geometry of each panel-row within the array or from existing sources, with preference given to newly derived mount technology. Either `fixed_axis`, `single_axis`, `dual_axis`, `mixed`, or `mixed_` with a lower-case letter denoting the mixed mounts (e.g., `mixed_fs`). Else, `unknown`, unitless  
* **tilt**: panel-row tilt for fixed-axis arrays (including arrays with mixed-mounting) from existing sources and filled in by **tiltEst**, degrees from zenith  
* **tiltEst**: estimated panel-row tilt for fixed-axis arrays (including arrays with mixed-mounting) estimated using pvlib, degrees above horizontal
* **avgAzimuth**: median estimated azimuth of panel-rows within array bounds or reported azimuth from existing sources, with preference given to newly estimated azimuth. For single-axis tracking arrays, this is the cardinal direction of the long edge. For all other mount types, this is the cardinal direction of the panel-row face, degrees from north  
* **avgLength**: median length of the long edge of panel-rows within an array, meters  
* **avgWidth**: median length of the short edge of panel-rows within an array, meters  
* **avgSpace**: median spacing between the solar array rows, in meters, between edges of the panel-row projected onto the ground, meters  
* **grndCvr**: ground cover management classification derived from external datasets, with agrivoltaic arrays labeled as `vegetation` (from NREL InSPIRE) and parking-lot arrays labeled as `impervious` (from California Energy Commission). Else, `unknown`, unitless  
* **STATEFP**: unique geographic identifier for the U.S. Census Bureau state entity, unitless  
* **COUNTYFP**: unique geographic identifier for the U.S. Census Bureau county entity, unitless  
* **geometry**: best new or available geometry matching the array definition which contains panel-rows and the space between them, derived from existing sources (**newBound = 0**) or from a buffer-dissolve-erode of newly delineated panel-rows (**newBound = 1**), meters  
* **version**: GM-SEUS version in which the array geometry and attributes are derived. Each subsequent version will re-derive new geometries and the best delineation from each version will be selected, unitless  

### We provide the following attribute fields in GM-SEUS Final Panel-Rows

* **panelID**: unique numeric ID of the panel-row in GM-SEUS, unitless  
* **arrayID**: unique numeric ID of each solar array in GM-SEUS that the panel-row is associated with, unitless  
* **Source**: panel-row boundary source from OSM, CCVPV, or GM-SEUS, unitless  
* **rowArea**: top-down or apparent panel-row area directly from the output of image classification, m²  
* **rowWidth**: length of the short edge of the panel-row, meters  
* **rowLength**: length of the long edge of the panel-row, meters  
* **rowAzimuth**: azimuth of the panel-row, with 0 at North, degrees  
* **rowMount**: mount technology (fixed-axis, single-axis, or dual-axis) of the panel-row, unitless  
* **rowSpace**: the inter-row spacing between the panel-row and the nearest panel-row in the azimuthal direction (fixed- and single-axis) or any direction (dual-axis), meters  
* **geometry**: top-down or perceived geometry, meters  
* **version**: GM-SEUS version in which the panel-row geometry and attributes are derived. Each subsequent version will re-derive new geometries and the best delineation from each version will be selected, unitless  

## Labeled Images for Deep Learning and Pattern Recognition
To add value to the dataset, we generate ~17,500 labeled images intended for deep learning and pattern recognition applications. We generated labeled imagery for arrays within GM-SEUS that contained NAIP generated panel-rows (CCVPV or gmseus Source) and with at least 10 identified panel-rows. We also only allowed imagery within the array where panels were present, to reduce panel-row omission error inclusion into the image dataset. Images and masks are provided at 256x256 pixel dimensions. We allowed arrays to contain random point centered image windows equal to 50% of the panel-row containing array area divided by tiled area (e.g., 377,500 m² / 23,593 m² * 0.5 = ~8 tiles). This resulted in ~17,500 images and masks over 4,605 arrays.

![alt text](images/image_mask_pairs.png "Deep learning and pattern recognition use case image product examples")

Three columns of six examples containing inputs or images (left) and targets or masks (right) for fixed-, single-, and dual-axis mounted arrays contained within GM-SEUS. Note, this data was not used to create GM-SEUS, but is provided as a value added product within the data repository.
