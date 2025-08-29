# Import Libraries
import geopandas as gpd
import pandas as pd
import numpy as np
import os
from shapely.ops import unary_union
import re

# Load OSM libraries and variables
import osmnx as ox
from osmnx._errors import InsufficientResponseError
ox.settings.use_cache = True
ox.settings.cache_folder = r"F:\OSM_Cache" # Create a local cache folder
ox.settings.overpass_url = 'https://overpass-api.de/api/interpreter' # "https://overpass.kumi.systems/api/interpreter"  # new name for endpoint

# Import gmseusUtils functions
import gmseusUtils as gu

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ OpenStreetMap Functions

# Define a function that grabs all solar panel and array data from OSM for a given region
def getSolarOSMData(regionName, countryName):

    # Load the config from the text file and all required variables
    config = gu.load_config('config.txt')    
    toCRS = config['to_crs']  # EPSG:6350 NAD83 (2011)
    toCRS = f'EPSG:{toCRS}'

    # Define your area of interest (e.g., 'Newfoundland and Labrador, Canada' or 'Michigan, USA')
    place = regionName + ', ' + countryName 

    # Define grouped tag for solar panels and arrays (NOTE: We will still have to filter out the arrays from panels)
    solarTags = {"plant:source": "solar",
                 "generator:source": "solar"}

    # Retrieve the data from OSM
    try:
        # Try retrieving solar data
        print(f"{regionName}: Attempting to retrieve solar data...")
        solarData = ox.features_from_place(place, tags=solarTags)
    except InsufficientResponseError:
        print(f"No solar data found for {regionName}.")
        solarData = gpd.GeoDataFrame(geometry=[], crs=toCRS)

    # If solarData contains data, try to split into arrays and panels respectively. Otherwise build empty gdfs.
    # If only one exists and not the other (e.g., arrays but not panels), parse and build one empty gdf
    if solarData.empty:
        arrayData = gpd.GeoDataFrame(geometry=[], crs=toCRS)
        panelData = gpd.GeoDataFrame(geometry=[], crs=toCRS)
    else:
        # Prefer splitting by 'power'; fall back to which :source tag exists
        power = solarData.get("power")
        if power is not None:
            arrays_mask = power.eq("plant")
            panels_mask = power.eq("generator")
        else:
            arrays_mask = solarData.get("plant:source", "").eq("solar")
            panels_mask = solarData.get("generator:source", "").eq("solar")

        # Build outputs; if one mask yields zero rows, you still get a valid empty GeoDataFrame
        arrayData = solarData[arrays_mask].copy()
        panelData = solarData[panels_mask].copy()
 
    # First, check if 'geometry' column exists and clean DataFrames by removing non-Polygon geometries
    # Solves an issue where regions like West Virgina, do not have arrayData
    if 'geometry' in panelData.columns:
        panelData = panelData[panelData['geometry'].apply(lambda x: x.geom_type in ['Polygon', 'MultiPolygon'])]
    else:
        panelData = gpd.GeoDataFrame(columns=['geometry'])  # Empty GeoDataFrame if no geometry column
    if 'geometry' in arrayData.columns:
        arrayData = arrayData[arrayData['geometry'].apply(lambda x: x.geom_type in ['Polygon', 'MultiPolygon'])]
    else:
        arrayData = gpd.GeoDataFrame(columns=['geometry'])  # Empty GeoDataFrame if no geometry column

    ''' This code block tests for non-Polygon or MultiPolygon geometries in the dataframes.
    # Create the same if else structure but for not 'Polygon' or 'MultiPolygon' geometries
    # Solves an issue where regions like West Virgina, do not have arrayData
    if 'geometry' in panelData.columns:
        panelData = panelData[panelData['geometry'].apply(lambda x: x.geom_type not in ['Polygon', 'MultiPolygon'])]
    else:
        panelData = gpd.GeoDataFrame(columns=['geometry'])
    if 'geometry' in arrayData.columns:
        arrayData = arrayData[arrayData['geometry'].apply(lambda x: x.geom_type not in ['Polygon', 'MultiPolygon'])]
    else:
        arrayData = gpd.GeoDataFrame(columns=['geometry'])
    '''
    
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ arrayData

    # IF: arrayData is not empty, process arrayData
    if arrayData is not None and not arrayData.empty:

        # Set CRS as WGS84 (OSM native proj). Then, transform the data to toCRS CRS. Solves naive projection issues for emtpy array and panel
        arrayData = arrayData.set_crs('EPSG:4326')
        arrayData = arrayData.to_crs(toCRS)

        # Save the index as osmid
        arrayData['osmid'] = arrayData.index

        # Reset index
        arrayData = arrayData.reset_index(drop=True)

        # Save osmid as string
        arrayData['osmid'] = arrayData['osmid'].astype(str)

        # osmid column is currently structured as (way, 1155615180), we want only the number
        arrayData['osmid'] = arrayData['osmid'].str.split(', ').str[1].str.replace(')', '')

    # For arrayData, select the following columns: start_date, plant:method, osmid, source, name, plant:output:electricity, geometry
    # If any of these columns do not exist, create an empty column of NA values (as a string)
    # Rename them to: instYr, modType, nativeID, Source, ProjName, cap_mw, geometry
    # Ensure required columns exist, creating them with NA values if missing
    required_columns = {
        'start_date': 'instYr',
        'plant:method': 'modType',  
        'osmid': 'nativeID',
        'source': 'Source',
        'name': 'ProjName',
        'plant:output:electricity': 'cap_mw',
        'geometry': 'geometry'}
    for col, new_col in required_columns.items():
        if col not in arrayData.columns:
            arrayData[col] = pd.NA
        arrayData[new_col] = arrayData[col]
    
    # Select only the new columns
    arrayData = arrayData[list(required_columns.values())]

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ panelData

    # IF: panelData is not empty, process panelData
    if panelData is not None and not panelData.empty:

        # Set CRS as WGS84 (OSM native proj). Then, transform the data to toCRS CRS. Solves naive projection issues for emtpy array and panel
        panelData = panelData.set_crs('EPSG:4326')
        panelData = panelData.to_crs(toCRS)

        # Save the index as osmid
        panelData['osmid'] = panelData.index

        # Reset index
        panelData = panelData.reset_index(drop=True)

        # Save osmid as string
        panelData['osmid'] = panelData['osmid'].astype(str)

        # osmid column is currently structured as (way, 1155615180), we want only the number
        panelData['osmid'] = panelData['osmid'].str.split(', ').str[1].str.replace(')', '')

        '''If we want rooftop data, comment out this block and for any rooftop classification, do not do createArrayFromPanels. Otherwise, creates arrays that are rooftop solar connected across houses. Also, need to modify minPanelRowArea to prevent dropping of small panels.'''
        # From panelData, remove all rows where 'location', 'building', or 'generator:place' column is = 'roof'. 
        # If these columns are not present, do nothing.
        if 'location' in panelData.columns:
            panelData = panelData[~panelData['location'].isin(['roof'])]
        if 'building' in panelData.columns:
            panelData = panelData[~panelData['building'].isin(['roof'])]
        if 'generator:place' in panelData.columns:
            panelData = panelData[~panelData['generator:place'].isin(['roof'])]

    # Select the following columns for panelData: start_date, generator:method, osmid, source, name, geometry
    # If any of these columns do not exist, create an empty column of NA values (as a string)
    # Rename them to: instYr, modType, nativeID, Source, ProjName, geometry
    # Ensure required columns exist, creating them with NA values if missing
    # NOTE: there may be a 'generator:output:electricity' column, but we will ignore it for now and estiamte capacity from area and installation year later.
    required_columns = {
        'start_date': 'instYr',
        'generator:method': 'modType',
        'osmid': 'nativeID',
        'source': 'Source',
        'name': 'ProjName',
        'geometry': 'geometry'}
    for col, new_col in required_columns.items():
        if col not in panelData.columns:
            panelData[col] = pd.NA
        panelData[new_col] = panelData[col]

    # Select only the new columns
    panelData = panelData[list(required_columns.values())]

    return panelData, arrayData

# Define Function to Process Solar OSM Data
def processSolarOSMData(regionName, countryName):   

    # Load the config from the text file and all required variables
    config = gu.load_config('config.txt')   
    minPanelRowArea = config['minPanelRowArea'] # 15 m2, minimum area for a single panel row from the 1st percentile panel area from Stid et al., 2022
    maxPanelRowArea = config['maxPanelRowArea'] # 254 m2 95th perccentile for a single panel row from Stid et al., 2022. MSU Solar Carport has max 1890m2
    minNumPanelRows = config['minNumPanelRows'] # 3 panels, minimum number of panels rows to form a ground mounted solar array, definition from Stid et al., 2022
    minPmArRatio = config['minPmArRatio'] # 18.8%, 20% was minimum ratio of panel perimeter to area ratio for panels from Stid et al., 2022, MSU Solar Carport has min 18.9%
    panelArrayBuff = config['panelArrayBuff'] # 10m buffer, 20m maximum distance between panel rows to form an array. We used 5m in Stid et al., 2022, but there are lower packing factors at greater latitudes (nativeID: '1229957948')
    arrayArrayBuff = config['arrayArrayBuff'] # 20m buffer, 40m maximum distance between arrays subsections of the same mount type to form a complete array. In Stid et al., 2022, we used 50m, but we checked for same installation year in addition to mount type.
    toCRS = config['to_crs']  # EPSG:6350 NAD83 (2011)
    toCRS = f'EPSG:{toCRS}'

    # Get the solar panel and array data from OSM
    panelData, arrayData = getSolarOSMData(regionName, countryName)

    #~~~~~~~~~~~~~~~~~~~~# 
    # Process Array Data # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    #~~~~~~~~~~~~~~~~~~~~#

    # If arrayData is not empty, process arrayData
    if arrayData is not None and not arrayData.empty:
        # Capacity (cap_mw) is currently formated as a string and contains: '1 GW', '1 MW', '1 kW', or 'yes'. 
        # Formatting can also include '1GW', '1MW', '1kW', or the lower case version of any of these. 
        # It may also contain other strings that should be treated as nan, including existing nan values.
        # If the string contains GW, remove everything except the number and multiply by 1000.
        # If the string contais MW, remove everything except the number and leave as is.
        # If the string contains kW, remove everything except the number and divide by 1000.
        # If the string contains 'yes', set to -9999 (null value).
        # If the string contains anything else, set to -9999 (null value).
        # Function to process capacity
        def process_capacity(value):
            if pd.isna(value):
                return np.nan
            value = value.lower().strip()  # Make the string lowercase for easier matching and strip whitespaces
            try:
                if 'gw' in value:
                    return float(value.replace('gw', '').strip()) * 1000
                elif 'mw' in value:
                    return float(value.replace('mw', '').strip())
                elif 'kw' in value:
                    return float(value.replace('kw', '').strip()) / 1000
                elif value == 'yes':
                    return -9999
                else:
                    return -9999
            except ValueError:  # If the string cannot be converted to a float
                return -9999

        # Apply the function to the 'cap_mw' column dynamically. Round to 3 decimal places.
        arrayData['cap_mw'] = arrayData['cap_mw'].apply(process_capacity).round(3)

        # ~~~~~~~~~~~~~~~~~ Get Panel Boundaries In Array Data (e.g. MSU Solar Carport, and 1229957948)

        # Explode the MultiPolygons into individual Polygons
        arrayData = arrayData.explode(index_parts=False).reset_index(drop=True)

        # Filter out any rows where the geometry is invalid or empty
        arrayData = arrayData[arrayData.geometry.notna()]

        # Calculate the area of each array (in square meters)
        arrayData['area'] = arrayData['geometry'].apply(lambda x: x.area if x.is_valid and x.area > 0 else np.nan)

        # Calculate the perimeter-to-area ratio of each array
        arrayData['PmArRatio'] = arrayData['geometry'].apply(lambda x: x.length / x.area if x.is_valid and x.area > 0 else np.nan)

        # Drop rows where area or PmArRatio couldn't be calculated (NaN values)
        arrayData = arrayData.dropna(subset=['area', 'PmArRatio'])

        # IF: an array is less than minimum panel size, remove it (more likely to be rooftop or inverter station)
        arrayData = arrayData[arrayData['area'] >= minPanelRowArea]

        # IF: an array has a perimeter to area ratio greater than 0.188 or area is less than the max panel row area, save it to an panelArrayData dataframe. 
        # Then remove it from arrayData
        panelInArrayData = arrayData[(arrayData['PmArRatio'] > minPmArRatio) | (arrayData['area'] < maxPanelRowArea)].reset_index(drop=True)
        arrayData = arrayData[~arrayData['nativeID'].isin(panelInArrayData['nativeID'])]

        # Dissolve by nativeID to return to multipolygon
        arrayData = arrayData.dissolve(by = 'nativeID').reset_index()

        # Remove panelArrayData shapes that are already in panelData, then merge the remaining dataframes
        # First, check if data exists, then clean DataFrames by dropping rows with invalid or empty geometries, then remove overlapping arrays
        if panelInArrayData is not None:
            panelInArrayData = panelInArrayData[panelInArrayData.geometry.notna()]
            if not panelInArrayData.empty:
                panelInArrayData = panelInArrayData[~panelInArrayData.intersects(unary_union(panelData.geometry))]
        panelData = pd.concat([panelData, panelInArrayData])
    
    # Else, if arrayData is empty, return an empty gdf for arrayData and panelInArrayData
    else:
        arrayData = gpd.GeoDataFrame(columns=['instYr', 'modType', 'nativeID', 'Source', 'ProjName', 'cap_mw', 'geometry'])
        panelInArrayData = gpd.GeoDataFrame(columns=['instYr', 'modType', 'nativeID', 'Source', 'ProjName', 'geometry'])

    #~~~~~~~~~~~~~~~~~~~~# 
    # Process Panel Data # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    #~~~~~~~~~~~~~~~~~~~~#

    # IF: panelData is not empty, process panelData
    if panelData is not None and not panelData.empty:
        # Explode the MultiPolygons into individual Polygons
        panelData = panelData.explode(index_parts=False).reset_index(drop=True)
        panelData['nativeID'] = panelData['nativeID'] + '_' + panelData.groupby('nativeID').cumcount().astype(str)

        # Filter out any rows where the geometry is invalid or empty
        panelData = panelData[panelData.geometry.notna()]

        # Calculate the area of each panel (in square meters)
        panelData['area'] = panelData['geometry'].apply(lambda x: x.area if x.is_valid and x.area > 0 else np.nan)

        # Calculate the perimeter-to-area ratio of each panel
        panelData['PmArRatio'] = panelData['geometry'].apply(lambda x: x.length / x.area if x.is_valid and x.area > 0 else np.nan)

        # Drop rows where area or PmArRatio couldn't be calculated (NaN values)
        panelData = panelData.dropna(subset=['area', 'PmArRatio'])

        # IF: a panel is less than the mimum panel row area, remove it (more likely to be rooftop or inverter station)
        panelData = panelData[panelData['area'] >= minPanelRowArea]

        # ~~~~~~~~~~~~~~~~~~ Get Array Boundaries In Panel Data

        # IF: a panel has a perimeter to area ratio less than 0.188 or area is greater than max panel row area, save it to an arrayPanelData dataframe. 
        # Then remove it from panelData
        arrayInPanelData = panelData[(panelData['PmArRatio'] < minPmArRatio) | (panelData['area'] > maxPanelRowArea)]
        panelData = panelData[~panelData['nativeID'].isin(arrayInPanelData['nativeID'])]

        # ~~~~~~~~~~~~~~~~~~ Get New Array Boudaries From Panel Data

        # Get the mount type for each panel based on the geometry. assignMountType returns multiple columns, so only return the mount column.
        panelData['mount'] = panelData.apply(gu.assignMountType, axis=1).apply(lambda x: x[0]) # panelData['mount'] = panelData.apply(assignMountType, axis=1)

        # Buffer the geometries by panelArrayBuff, dissovle boundaries by overlap, explode again, and unbuffer by panelArrayBuff * -1. 
        arrayFromPanelData = panelData.copy()
        arrayFromPanelData['geometry'] = arrayFromPanelData.buffer(panelArrayBuff)
        arrayFromPanelData = arrayFromPanelData.dissolve().explode(index_parts=False).reset_index(drop=True)

        # Unbuffer the geometries by the same distance (negative buffer)
        arrayFromPanelData['geometry'] = arrayFromPanelData.buffer(panelArrayBuff * -1)

        # Check for and remove erroneous geometries in arrays
        arrayFromPanelData = gu.checkArrayGeometries(arrayFromPanelData)

        # Save the most common mount type for each array based on panels that intersect with the array
        arrayFromPanelData['mount'] = arrayFromPanelData['geometry'].apply(lambda x: panelData[panelData.intersects(x)]['mount'].mode()[0])

        # IF any arrayFromPanelData shape is within a 20m buffer (arrayArrayBuff) of another arrayFromPanelData, merge them into a single array shape
        arrayFromPanelData = gu.groupArrayByVariableAndProximity(arrayFromPanelData, arrayArrayBuff, 'mount')

        # Assign each array a unique identifier
        arrayFromPanelData['arrayID'] = arrayFromPanelData.index

        # Save the number of panels in each array based number of intersecting panels
        arrayFromPanelData['PnlNum'] = arrayFromPanelData['geometry'].apply(lambda x: len(panelData[panelData.intersects(x)]))

        # Assign each panel the corresponding arrayID and total panel num in array by spatial join.
        panelData = gpd.sjoin(panelData, arrayFromPanelData[['arrayID', 'PnlNum', 'geometry']], how='left', predicate='intersects').drop(columns='index_right')

        # Remove arrays and panels that do not meet the minimum number of panels in an array
        arrayFromPanelData = arrayFromPanelData[arrayFromPanelData['PnlNum'] >= minNumPanelRows]
        panelData = panelData[panelData['PnlNum'] >= minNumPanelRows]
    
    # Else, if panelData is empty, return an empty gdf for panelData, arrayInPanelData, and arrayFromPanelData
    else:
        panelData = gpd.GeoDataFrame(columns=['instYr', 'modType', 'nativeID', 'Source', 'ProjName', 'geometry', 'mount'])
        arrayInPanelData = gpd.GeoDataFrame(columns=['instYr', 'modType', 'nativeID', 'Source', 'ProjName', 'geometry'])
        arrayFromPanelData = gpd.GeoDataFrame(columns=['instYr', 'modType', 'nativeID', 'Source', 'ProjName', 'geometry', 'mount', 'arrayID', 'PnlNum'])

    #~~~~~~~~~~~~~~~~~~# 
    # Merge Array Data # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    #~~~~~~~~~~~~~~~~~~# 

    # Remove arrays with overlap in the following level of priority: arrayData, arrayInPanelData, arrayFromPanelData
    # This order maintains arrays composed of subarray sections (multipolygons)
    # First, check if data exists, then clean DataFrames by dropping rows with invalid or empty geometries, then remove overlapping arrays
    # Solves an issue where an array df is empty, or contains errant geometries
    if arrayInPanelData is not None:
        arrayInPanelData = arrayInPanelData[arrayInPanelData.geometry.notna()]
        if not arrayInPanelData.empty and not arrayData.empty:
            arrayInPanelData = arrayInPanelData[~arrayInPanelData.intersects(unary_union(arrayData.geometry.values))]
    if arrayFromPanelData is not None:
        arrayFromPanelData = arrayFromPanelData[arrayFromPanelData.geometry.notna()]
        if not arrayFromPanelData.empty and not arrayData.empty:
            arrayFromPanelData = arrayFromPanelData[~arrayFromPanelData.intersects(unary_union(arrayData.geometry.values))]
        if arrayInPanelData is not None and not arrayInPanelData.empty:
            arrayFromPanelData = arrayFromPanelData[~arrayFromPanelData.intersects(unary_union(arrayInPanelData.geometry.values))]

    # For arrayFromPanelData and arrayInPanelData, select the following columns: instYr, modType, nativeID, Source, ProjName, PnlNum, geometry
    arrayFromPanelData = arrayFromPanelData[['instYr', 'modType', 'nativeID', 'Source', 'ProjName', 'geometry']]
    arrayInPanelData = arrayInPanelData[['instYr', 'modType', 'nativeID', 'Source', 'ProjName', 'geometry']]

    # For arrayFromPanelData and arrayInPanelData, add a cap_mw column and set it to -9999
    arrayFromPanelData['cap_mw'] = -9999
    arrayInPanelData['cap_mw'] = -9999

    # Merge the array data
    arrayData = pd.concat([arrayData, arrayInPanelData, arrayFromPanelData])

    #~~~~~~~~~~~~~~~~~~~~~~~~~# 
    # Fill Gaps and Save Data # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    #~~~~~~~~~~~~~~~~~~~~~~~~~#

    # Save the final number of panels in each array based number of intersecting panels (overwrites initial count)
    arrayData['PnlNum'] = arrayData['geometry'].apply(lambda x: len(panelData[panelData.intersects(x)]))

    # For each array and each panel, calculate the area and save as a new column
    panelData['area'] = panelData.area
    arrayData['area'] = arrayData.area

    # instYr values are formatted in several ways: 'YYYY-MM' or 'YYYY-MM-DD', 'MM/YYYY', 'YYYY', m/d/YYYY, with additional examples of: 'October 2018', 'March 1, 2015', '6/11/2011', '11/2019', '20183', '2021.0'
    # We want to extract the year from these strings. If the year is not present, or if the year is not between 1900 and 2025, set to -9999
    # Set the instYr column to an integer type when finished.
    # Function to extract a valid year from various formats
    def extract_year(instYr):
        # Patterns to capture the year from different formats
        patterns = [
            r'(\b\d{4})[-/]\d{2}[-/]\d{2}',    # Match 'YYYY-MM-DD' or 'YYYY/MM/DD' (e.g., '2020-05-25')
            r'(\b\d{4})[-/]\d{2}',              # Match 'YYYY-MM' or 'YYYY/MM' (e.g., '2020-05')
            r'\b(\d{1,2})/\d{1,2}/(\d{4})\b',   # Match 'm/d/YYYY' or 'MM/DD/YYYY' (e.g., '6/11/2011')
            r'([A-Za-z]+\s+\d{1,2},?\s+)?(\d{4})',  # Match 'Month YYYY' (e.g., 'October 2018') or 'March 1, 2015'
            r'(\b\d{4}\b)'                      # Match standalone 'YYYY' (e.g., '2020')
        ]
        
        # Iterate through the patterns and try to match
        for pattern in patterns:
            match = re.search(pattern, str(instYr))
            if match:
                # Extract the year from the matched group
                year = int(match.group(1)) if len(match.groups()) == 1 else int(match.group(2))
                # Ensure the year is valid (between 1983 and 2025) -- 1983 is the install year of Solar One, the first commercial solar power plant in the US
                if 1983 <= year <= 2025:
                    return year
        # If no valid year is found, return -9999
        return -9999

    # Apply the function to the 'instYr' column for both panelData and arrayData
    panelData['instYr'] = panelData['instYr'].apply(extract_year).astype(int)
    arrayData['instYr'] = arrayData['instYr'].apply(extract_year).astype(int)
        
    # For both dataframes, fill missing Source and ProjName with 'Unknown'
    panelData['Source'] = panelData['Source'].fillna('Unknown')
    arrayData['Source'] = arrayData['Source'].fillna('Unknown')
    panelData['ProjName'] = panelData['ProjName'].fillna('Unknown')
    arrayData['ProjName'] = arrayData['ProjName'].fillna('Unknown')

    # For respective modType columns, replace 'photovoltaic' with 'c-Si' and 'thermal' with 'csp'. 
    panelData['modType'] = panelData['modType'].replace('photovoltaic', 'c-si')
    arrayData['modType'] = arrayData['modType'].replace('photovoltaic', 'c-si')
    panelData['modType'] = panelData['modType'].replace('thermal', 'csp')
    arrayData['modType'] = arrayData['modType'].replace('thermal', 'csp')

    # For both dataframes, fill missing modType with 'c-Si'
    panelData['modType'] = panelData['modType'].fillna('c-si')
    arrayData['modType'] = arrayData['modType'].fillna('c-si')

    # If dataframes are empty, ignore, otherwise save the data to a shapefile in the OSM download folder for the region
    if panelData is not None and not panelData.empty:
        panelData.to_file(os.path.join(osmPanelsPath, regionName + 'SolarPanels.shp'))
    if arrayData is not None and not arrayData.empty:
        arrayData.to_file(os.path.join(osmArraysPath, regionName + 'SolarArrays.shp'))

    # If desired, return the dataframes
    #return panelData, arrayData