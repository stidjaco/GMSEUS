<p align="center">
    <img width="600" src = https://github.com/stidjaco/GMSEUS/blob/master/images/GMSEUS_githubheader.png>
 </p>

# A distributed ground-mounted solar energy dataset with sub-array design metadata in the United States
Repository for creating and maintaining the Ground-Mounted Solar Energy in the United States (GM-SEUS) spatiotemporal dataset of solar arrays and panel-rows using existing datasets, machine learning, and object-based image analysis to enhance existing sources. A paper in is preparation for this dataset. 

## Current Version Notes
This is the initial release of GM-SEUS (version 1.0). All input datasets and solar panel-row delineation results are up-to-date through December 11th, 2024. 

# Product Description

## Overview

Solar energy generating systems are a critical component of net-zero infrastructure, yet comprehensive datasets characterizing systems remain incomplete or not publicly available, particularly at the sub-array level. Leveraging the best freely available existing solar datasets in the US with object-based image analysis and machine learning, we present the Ground-Mounted Solar Energy in the United States (GM-SEUS) dataset, a harmonized, open access, and regularly updated geospatial and temporal repository of solar energy arrays and panel-rows. GM-SEUS v1.0 includes nearly 15,000 commercial- and utility-scale ground-mounted solar photovoltaic and concentrating solar energy arrays (## GW) covering nearly 2,900 km<sup>2</sup> and includes 2.92 million unique solar panel-rows. We use newly compiled and delineated solar panel-rows to fill gaps in, and contribute several value-added attributes to existing databases and enhance consistency across spatiotemporal attributes. Value-added attributes include installation year, azimuth, mount technology, panel-row area and dimensions, inter-row spacing, ground cover ratio, tilt, and installed capacity. By estimating and harmonizing these spatial and temporal attributes of the distributed US solar energy landscape, GM-SEUS supports diverse applications in renewable energy modeling, ecosystem service assessment, and infrastructural planning. 

## Source Datasets

### Array Polygon-Level Data

* **United States Solar Photovoltaic Database (USPVDB)**: Downloaded from [USPVDB Portal](https://eerscmap.usgs.gov/uspvdb/data/), Last Download: 10-11-2024 (Up-to-date as of 12-11-2024), Version 2.0
* **California's Central Valley Photovoltaic Dataset (CCVPV) Arrays and Panels**: Downloaded from [figshare](https://doi.org/10.6084/m9.figshare.23629326.v1), Last Download: 07-18-2024 (Up-to-date as of 12-11-2024), Version 1.0
* **Chesapeake Watershed Solar Data (CWSD) Arrays**: Downloaded from [OSFHOME](https://osf.io/vq7mt/), Last Download: 12-01-2024 (Up-to-date as of 12-11-2024), We downloaded derived polygons as well as manually annotated training polygons, and preferenced training polygons over derived for their completeness and quality, No Version details
* **OpenStreetMap Solar Panels and Arrays (OSM)**: Array and panel objects were downloaded _osmnx_ package in `script0_getOSMdata.ipynb`, Last OSM scrape: 12-11-2024,
  * Previously, we used data from **Harmonzied Global Wind and Solar Farm Locations (HGLOBS)** Downloaded from [figshare](https://doi.org/10.6084/m9.figshare.11310269.v6)
* **TransitionZero Global Solar Asset Mapper (SAM)**: Downloaded from [TZ-SAM Portal](https://zenodo.org/records/11368204), Last Download: 12-11-2024, Other information: [Website](https://solar.transitionzero.org/), [Viewer](https://solar-map.transitionzero.org/), [SciData Preprint](https://zenodo.org/records/11368204/files/tz-sam_scientific_data.pdf?download=1), Version Q3-2024 (Version 2)
  * Follow-on project containing all information from [Kruitwagen et al., 2021](https://zenodo.org/records/5005868). 

### Array Point-Level Data

* **NREL Innovative Solar Practices Integrated with Rural Economies and Ecosystems (InSPIRE) Database**: Downloaded from [InSPIRE Portal](https://openei.org/wiki/InSPIRE/Agrivoltaics_Map), Last Download: 12-11-2024,
* **LBNL Utility-Scale Solar (USS), 2024 Edition**: Downloaded from [LBNL Utility-Scale Solar Portal](hhttps://emp.lbl.gov/utility-scale-solar/), Last Downloaded: 11-16-2024 (Up-to-date as of 12-11-2024), Large excel report, project level data was copied from original report .xlsx to a new .csv from Individual_Project_Data tab
* **NREL PV Data Acquisition (PV-DAQ) Database**: Downloaded from [PV-DAQ Portal - Available Systems Information](https://data.openei.org/submissions/4568), and [PVDAQ Data Map](https://openei.org/wiki/PVDAQ/PVData_Map), Last Downloaded: 07-23-2024 (Up-to-date as of 12-11-2024)
* **International Energy Agency (IEA) & NREL Solar Power and Chemical Energy System (SolarPACES) Database**: Downloaded from [Project Page](https://solarpaces.nrel.gov/), Last Downloaded: 07-29-2024 (Up-to-date as of 12-11-2024), More information at [US CSP Project Pages](https://solarpaces.nrel.gov/by-country/US)
  * While SolarPACES is the overarching project (and how we refer to the dataset here), the product is called [CSP.guru](https://csp.guru/)
* **Global Solar Power Tracker (GSPT) from Global Energy Monitor (GEM) and TransistionZero**: Downloaded from [GEM Portal](https://globalenergymonitor.org/download-data-success/), Last Downloaded: 07-24-2024 (Up-to-date as of 12-11-2024), Access request required.
* **World Resource Institute (WRI) Global Power Plant Database (GPPDB)**: Downloaded from [WRI Portal](https://datasets.wri.org/dataset/globalpowerplantdatabase), Last Downloaded: 07-30-2024 (Up-to-date as of 12-11-2024), Version 1.3.0

## Codebase Description:

All code used in the acquisition and development of this dataset is available in this [Github repository](https://github.com/stidjaco/GMSEUS). Files are ipynb or txt files, where txt files are JavaScript files intended to be run in the [GEE code editor](https://code.earthengine.google.com/). 

### The GM-SEUS open code repository contains the following files

General Code Files: All file require the completion of all prior files for inputs. 
* `config.txt`: Config file containing variable constants used throughout processing.
* `script0_getOSMdata.ipynb`: Python file for pulling and processing OSM data for each state. No required inputs.
* `script1_prepareExistingSolarDB.ipynb`: Python file for compiling and harmonizing existing solar databases.
* `script2_digitizeSolarLocations.txt`: GEE file for preparing manual digitization of solar array point data not able to be georectified to existing array polygon data.
* `script3_compileGetGroundMounted.ipynb`: Python file for compiling existing and digitized boundaries, and removing rooftop mounted solar arrays. 
* `script4_getSolarPanels.txt`: GEE file for acquiring NAIP imagery within array bounds and extracting panel-row boundaries if they exist in available imagery. 
* `script5_processSolarPanels.ipynb`: Python file for compiling and quality control of solar panel-row objects. File also creates new array boundaries.
* `script6_getInstallationYear.txt`: GEE file for applying LandTrendr temporal segmentation within array boundaries to acquire a year of change (requires `scriptLandTrendrSolarIndex.txt`).
* `script7_prepAttributes.ipynb`: Python file for preparing and harmonizing all final GM-SEUS attributes.
* `script7a_validateInstYrImagery.txt`: GEE file for manual validation of installation year using available NAIP, Sentinel-2, and Landsat 7 ETM+ imagery. 
* `script7b_validateInstYrTimeSeries.txt`: GEE file for LandTrendr provided User-Interface (UI) file with solar PV indices included. 
* `script8_technicalValidation.ipynb`: Python file for processing technical validation of GM-SEUS.

Environment Files: 
* `BigPanel.yml`: General python environment for all ipynb files except `script3`.
* `BigPanelGEE.yml`: General python environment for `script3` that requires GEE access and cloud repository. 

Supplementary Files: 
* `scriptLandTrendrSolarIndex.txt`: GEE file for LandTrendr temporal segmentation, modified to include solar indices.
* `scriptTrainRF.txt`: GEE file for compiling and assessing the new landcover training dataset to classify solar panel-rows in NAIP imagery. 
* `scriptPlot_maps.ipynb`: Python file for printing and export relevant result maps.
  
## Dataset Description: 
All data products are available in the Zenodo Repository. All input datasets can be downloaded from source files described in the associated paper, at the top of this document, and at the top of `script1`. All intermediate products are available upon request, and are automatically generated in the processing of the code repo. 

### The GM-SEUS open repository contains the following files

* **GMSEUS_Arrays_Final.gpkg**: Final array dataset containing boundaries from existing datasets and enhanced by buffer-dissolve-erode technique with GM-SEUS panel-rows containing all array-level attributes (NAD83), geopackage and shapefile
* **GMSEUS_Panels_Final.gpkg**: Final panel-row dataset containing boundaries from existing datasets and newly delineated GM-SEUS panel-rows containing all panel-row-level attributes (NAD83), geopackage and shapefile
* **GMSEUS_NAIP_Arrays.gpkg**: All array boundaries created by buffer-dissolve-erode method of newly delineated (NAIP) GM-SEUS panel-rows (NAD83), geopackage and shapefile
* **GMSEUS_NAIP_Panels.gpkg**: All newly delineated panel-row boundaries (NAD83), geopackage and shapefile
* **GMSEUS_Arrays_Final.csv**: Final array dataset containing all array-level attributes and array centroid coordinates (WGS84), comma separated values
* **NAIPtrainRF.csv**: Training dataset of 12,000 NAIP training points (2,000 class–1) containing class values, spectral index values, the year of NAIP imagery accessed, and point coordinates (WGS84), comma separated values
* **NAIPclassifyRF.csv**: Random forest classifier trees and weights, comma separated values

### We provide the following attribute fields in GM-SEUS Final Arrays

* **arrayID**: unique numeric ID of each solar array in GM-SEUS, unitless
* **Source**: array boundary source from existing datasets, unitless
* **newBound**: binary, whether the array boundary was derived from the existing data sources (0) or from a buffer-dissolve-erode of panel-rows following our definition of an array boundary (1), unitless
* **totArea**: total land footprint of panel-rows and the space between them, m2
* **totRowArea**: If numRow is greater than 0, sum of rowArea within an array. Otherwise, estimated totRowArea based on totArea and GCR1 estimation where no panel-rows were detected, m2
* **numRow**: number of panel-rows within an array, m2
* **instYr**: installation year from existing sources, with gaps filled in by instYrLT, year
* **instYrLT**: LandTrendr-derived installation year independent of any data source other than Landsat spectral trajectory, year
* **capMW**: installed peak capacity from existing sources, with gaps filled in by capMWest, MW
* **capMWest**: estimated installed peak capacity derived from capacity to panel-row area relationships described in Eq. 13, 14, 15, and 16 independent of any data source, MWDC or MWth
* **modType**: reported panel-row (module) technology at the array level (c-si, thin-film, csp). If unreported, assumed to be c-si, unitless
* **effInit**: initial panel-rows efficiency from existing sources with gaps filled in by based on efficiency estimation from modType and instYr taken from the annual Tracking the Sun report, %
* **GCR1**: 0-1, the ratio of totRowArea to the total area of panel-rows and the space between them. For arrays with complete panel delineation and arrays where newBound is 1, this is equivalent to totArea. This is also called packing factor. If numRow is greater than 0, GCR1 is an actual GCR1 for the array. Otherwise, GCR is estimated by linear regression of latitude and longitude by mount and module type, unitless
* **GCR2**: 0-1, the ratio of the average width of the panel-row short edge (rowWidth) to the horizontal ground distance between identical panel-rows points, defined as the sum of widthAvg and rowSpace.  If numRow is greater than 0, GCR1 is an actual GCR2 for the array. Otherwise, GCR1 is estimated by linear regression of latitude and longitude by mount and module type, unitless
* **mount**: mount technology derived from the azimuth and geometry of each panel-row within the array. Either ‘fixed_axis’, ‘single_axis’, ‘dual_axis’, or ‘mixed_’ with a lower-case letter denoting the mixed mounts (e.g., mixed_fs), unitless
* **tilt**: panel-row tilt for fixed-axis arrays from existing sources and estimated by a latitudinal relationship, degrees from zenith
* **avgAzimuth**: median estimated azimuth of panel-rows within array bounds. For single-axis tracking arrays , degrees from north
* **avgLength**: median length of the long edge of panel-rows within an array, meters
* **avgWidth**: median length of the short edge of panel-rows within an array, meters
* **avgSpace**: median spacing between the solar array rows, in meters, between edges of the panel-row projected onto the ground, meters
* **geometry**: best new or available geometry matching the array definition which contains panel-rows and the space between them, derived from existing sources (newBound = 0) or from a buffer-dissolve-erode of newly delineated panel-rows (newBound = 1), NAD83
* **version**: GM-SEUS version in which the array geometry and attributes are derived. Each subsequent version will re-derive new geometries and the best delineation from each version will be selected, unitless

### We provide the following attribute fields in GM-SEUS Final Panel-Rows

* **panelID**: unique numeric ID of the panel-row in GM-SEUS, unitless
* **arrayID**: unique numeric ID of each solar array in GM-SEUS that the panel-row is associated with, unitless
* **Source**: panel-row boundary source from OSM, CCVPV, or GM-SEUS, unitless
* **rowArea**: top-down or apparent panel-row area directly from the output of image classification, m2
* **rowWidth**: length of the short-edge of the panel-row, meters
* **rowLength**: length of the long-edge of the panel-row, meters
* **rowAzimuth**: azimuth of the panel-row, with 0 at North, degrees
* **rowMount**: mount technology (fixed-axis, single-axis, or dual-axis) of the panel-row, unitless
* **rowSpace**: the inter-row spacing between the panel-row and the nearest panel-row in the azimuthal direction (fixed- and single-axis) or any direction (dual-axis), meters
* **geometry**: top-down or perceived geometry, NAD83
* **version**: GM-SEUS version in which the panel-row geometry and attributes are derived. Each subsequent version will re-derive new geometries and the best delineation from each version will be selected, unitless

# Considerations for updates in Version 2

* Add tilt to preprocessing steps in `script1` then update Check Tilt in `script7`
* Consider dropping CWSD on spatial priority list, often qualitatively under-represents array bounds. 
* Consider installation year accuracy from TZ-SAM, should it be the constructed_before date alone, or average of before and after? Currently average. 
* Consider making QA/QC criteria less strict, removal of panel groupings to generate array area first?
* Manually digitize/georectify remaining point data (1,490 points)
* Consider following methods of TZ-SAM for version updates: Compile into *raw_polygons* and consider spatial quality that way. 
* TZ-SAM also contains *raw_polygons*, which are all overlapping polygon shapefiles from all sources (including prior TZ-SAM versions). Could be useful in the future, or even a pathway that we use to share data. 
* Solve overlap issue due to USPVDB array boundary "cut" from V1 to V2
    * Choose if new array delineation in script5 should be independent or dependent on existing array boundaries (group by arrayID or only by proximity then explode?). Currently group by arrayID.
    * Would result in array boundaries that may overlap multiple original array shapes (maybe only a problem for cut USPVDB boundaries)
