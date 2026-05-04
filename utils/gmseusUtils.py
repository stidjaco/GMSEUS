# Import Basic Libraries
import geopandas as gpd
import pandas as pd
import numpy as np
import os
import glob
import importlib.util
from pathlib import Path
import warnings
from shapely.ops import unary_union
from shapely.geometry import Polygon, mapping
from sklearn.linear_model import LinearRegression

# Import libraries for plotting
import matplotlib.pyplot as plt
from matplotlib_scalebar.scalebar import ScaleBar

# Import raster libraries
import rasterio
import rasterio.warp
from rasterio.merge import merge
from rasterio.warp import calculate_default_transform, reproject, Resampling
from rasterio.enums import Resampling as ResamplingEnum
from rasterio.features import rasterize

# Possibly unused libraries
# from shapely.geometry import MultiPolygon, Polygon, MultiPoint
# from shapely.ops import unary_union
# import re
# from shapely.geometry import Polygon, shape
# import random
# import re
# from datetime import datetime
# from matplotlib.colors import ListedColormap, Normalize
# import matplotlib.colors as mcolors

# Directory where gmseusUtils.py lives.
_HERE = Path(__file__).resolve().parent

# Project root: walk up from this file until we find pyproject.toml (the
# marker file at the repo root). Robust to restructuring — utils can live
# anywhere under the project root and this still resolves correctly.
_PROJECT_ROOT = next(
    (p for p in [_HERE, *_HERE.parents] if (p / 'pyproject.toml').exists()),
    _HERE.parent,
)

# Public alias for the project root (kept for notebooks that do `wd = gu.wd`).
wd = _PROJECT_ROOT

# Set pandas option to avoid future warning about downcasting
pd.set_option('future.no_silent_downcasting', True)

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ Startup and General Functions

# Function to check if folder exists, if not create it
def checkFolder(folder):
    if not os.path.exists(folder):
        os.makedirs(folder)

# Function to load config file
def load_config(filename=None):
    """Load config variables as a dict.

    Defaults to config.py at the project root (detected via pyproject.toml),
    so callers in any subfolder can just do `gu.load_config()` without path
    gymnastics. Supports .py (preferred) and .txt (legacy key=value format).
    """
    if filename is None:
        filename = _PROJECT_ROOT / 'config.py'
    filename = Path(filename)

    if filename.suffix == '.py':
        spec = importlib.util.spec_from_file_location('_gmseus_config', filename)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return {k: v for k, v in vars(module).items() if not k.startswith('_')}

    # Legacy .txt format: one "key=value" per line
    config = {}
    with open(filename, 'r') as f:
        for line in f:
            key, value = line.strip().split('=')
            try:
                value = float(value) if '.' in value else int(value)
            except ValueError:
                pass
            config[key] = value
    return config

# Function to load geodataframes from all files in a folder
def load_all_gdf(path, extension, target_crs):
    # List all files with the given extension in the folder
    files = [f for f in os.listdir(path) if f.endswith(f'.{extension}')]
    gdfs = [gpd.read_file(os.path.join(path, file)) for file in files]
    # Check for empty GeoDataFrames and filter them out
    gdfs = [gdf for gdf in gdfs if not gdf.empty]
    # Directly concatenate and reproject
    return gpd.GeoDataFrame(pd.concat(gdfs, ignore_index=True)).to_crs(target_crs)

# Function to get H3 hexagons covering an AOI geometry at a specified resolution
def getH3(aoi_geom, res=5, toCRS='EPSG:4326'):
    """
    aoi_geom: GeoDataFrame, GeoSeries, or shapely geometry.
              If GeoDataFrame/GeoSeries, CRS can be anything; it will be reprojected to EPSG:4326.
    res     : H3 resolution (int)

    Returns: GeoDataFrame with columns ['h3_index', 'geometry'] in EPSG:4326.

    Usage: 
    # Load AOI
    aoi = gpd.read_file(aoiPath)

    # Get H3 res 5 polygons
    h3_gdf = gu.getH3(aoi, res=4, toCRS=toCRS)

    # Save to a shapefile
    h3_gdf.to_file(os.path.join(derivedTemp_path, r'NA_AOI_h3res4.shp'), driver='ESRI Shapefile')

    # Plot AOI H3 hexagons, small white border with dark grey theme fill
    fig, ax = plt.subplots(figsize=(8, 8))
    h3_gdf.plot(ax=ax, edgecolor='white', facecolor=darkGreyTheme, linewidth=0.1)
    plt.show()
    """
    # Import h3 inside function to avoid hard dependency if not used
    import h3

    # ---- Normalize AOI geometry ----
    if isinstance(aoi_geom, (gpd.GeoDataFrame, gpd.GeoSeries)):
        if aoi_geom.crs is not None and aoi_geom.crs.to_epsg() != 4326:
            aoi_geom = aoi_geom.to_crs(4326)
        geom = unary_union(aoi_geom.geometry)  # dissolve to one (multi)polygon
    else:
        # assume a single shapely geometry already in EPSG:4326
        geom = aoi_geom

    # ---- Shapely to __geo_interface__ dict (lon/lat) ----
    geo = mapping(geom)  # this is standard GeoJSON-style: lon, lat

    # ---- __geo_interface__ to H3Shape to cells ----
    # h3 v4 polygon API: convert geo to H3Shape, then get cells at resolution
    h3shape = h3.geo_to_h3shape(geo)              # uses the polygon interface :contentReference[oaicite:0]{index=0}
    cells = h3.h3shape_to_cells(h3shape, res)     # collection of H3 indexes :contentReference[oaicite:1]{index=1}

    # ---- Cells to shapely hex polygons ----
    hex_polys = []
    hex_ids = []
    for cell in cells:
        # v4 function: returns sequence of (lat, lng) pairs :contentReference[oaicite:2]{index=2}
        boundary = h3.cell_to_boundary(cell)
        # shapely expects (x=lon, y=lat)
        lonlat = [(lng, lat) for (lat, lng) in boundary]
        hex_polys.append(Polygon(lonlat))
        hex_ids.append(cell)
    gdf_hex = gpd.GeoDataFrame(
        {"h3_index": hex_ids},
        geometry=hex_polys,
        crs="EPSG:4326")
    
    # Reproject to target CRS
    gdf_hex = gdf_hex.to_crs(toCRS)
    return gdf_hex

# Define a function to calculate the intersection over union (and all related metrics) of any two gdf datasets accounting for multiple potential intersections
def getIoU(gdf1, gdf2):

    # Explode both datasets into polygons, dissolve overlapping geometries, and explode again into spatially unique polygons
    gdf1 = gdf1.explode(index_parts=False).reset_index(drop=True)
    gdf2 = gdf2.explode(index_parts=False).reset_index(drop=True)
    gdf1 = gdf1.dissolve().reset_index(drop=True)
    gdf2 = gdf2.dissolve().reset_index(drop=True)
    gdf1 = gdf1.explode(index_parts=False).reset_index(drop=True)
    gdf2 = gdf2.explode(index_parts=False).reset_index(drop=True)

    # Drop all resulting polygons less than 45 square meters
    minArrayArea = 45 # 45 square meters
    gdf1['origArea_1'] = gdf1['geometry'].area
    gdf2['origArea_2'] = gdf2['geometry'].area
    gdf1 = gdf1[gdf1['origArea_1'] > minArrayArea].reset_index(drop=True)
    gdf2 = gdf2[gdf2['origArea_2'] > minArrayArea].reset_index(drop=True)

    # Add a tempIOUid column to both datasets that is the index
    gdf1['tempIOUid_1'] = gdf1.index
    gdf2['tempIOUid_2'] = gdf2.index

    # Spatial join the two datasets, copying the tempIOUid_2 column to the gdf1 dataset
    intersections = gpd.sjoin(gdf1[['geometry', 'tempIOUid_1']], gdf2[['geometry', 'tempIOUid_2']], how='inner', predicate='intersects')

    # Perform the intersection operation to get the actual intersection geometries
    intersections['geometry'] = intersections.apply(lambda row: gdf1.loc[row['tempIOUid_1'], 'geometry'].intersection(gdf2.loc[row['tempIOUid_2'], 'geometry']), axis=1)

    # Now dissolve intersections by tempIOUid_1 and tempIOUid_2
    intersections = intersections.dissolve(by=['tempIOUid_1'], aggfunc='sum').reset_index()
    intersections = intersections.dissolve(by=['tempIOUid_2'], aggfunc='sum').reset_index()

    # Set an index column
    intersections['intIndex'] = intersections.index

    # Spatially join intersections to gdf1 and gdf2 saving intIndex
    gdf1 = gpd.sjoin(gdf1, intersections[['intIndex', 'geometry']], how='left', predicate='intersects')
    gdf2 = gpd.sjoin(gdf2, intersections[['intIndex', 'geometry']], how='left', predicate='intersects')

    # Drop rows from both where intIndex is NaN
    gdf1 = gdf1.dropna(subset=['intIndex'])
    gdf2 = gdf2.dropna(subset=['intIndex'])

    # Drop any columns containing the substring 'index'
    gdf1 = gdf1.loc[:, ~gdf1.columns.str.contains('index')]

    # Calculate areas and IoU
    gdf1['areaA'] = gdf1['geometry'].area
    gdf2['areaB'] = gdf2['geometry'].area

    # Aggregate areas for each intIndex
    gdf1_agg = gdf1.groupby('intIndex')['areaA'].sum().reset_index()
    gdf2_agg = gdf2.groupby('intIndex')['areaB'].sum().reset_index()

    # Merge aggregated areas into intersections
    intersections = intersections.merge(gdf1_agg, on='intIndex', how='left')
    intersections = intersections.merge(gdf2_agg, on='intIndex', how='left')

    # Calculate intersectionArea and unionArea
    intersections['intersectionArea'] = intersections['geometry'].area
    intersections['unionArea'] = (
        intersections['areaA'] +
        intersections['areaB'] -
        intersections['intersectionArea'])

    # Calculate IoU
    intersections['IoU'] = intersections['intersectionArea'] / intersections['unionArea']

    # Calculate the proportional difference in area between the two areas
    intersections['propDiff'] = (intersections['areaB'] - intersections['areaA']) / intersections['areaA']
    return intersections

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ GM-SEUS General Functions

# Function to format the existing solar array datasets to the desired schema
def formatDf(df, nativeIdentifier, installationYear, capacityMWdc, capacityMWac, area_m2, moduleType, groundCover, azimuth, tilt, mountTechnology, source):
    # Change column names to match the schema
    df = df.rename(columns={nativeIdentifier: 'nativeID', capacityMWdc: 'capMWDC', capacityMWac: 'capMWAC', area_m2: 'area', installationYear: 'instYr', moduleType: 'modType', azimuth: 'azimuth', tilt: 'tilt', mountTechnology: 'mount', groundCover: 'grndCvr', source: 'Source'})

    # Set Source. If any Source is missing, print a warning.
    df['Source'] = df['Source'].fillna(source)
    df['Source'] = df['Source'].astype(str)
    if df['Source'].isnull().any():
        print('Warning: Some Source values are missing after formatting.')

    # Fill empy numeric column rows with -9999, and empty string column rows with NaN
    df['capMWDC'] = df['capMWDC'].fillna(-9999)
    df['capMWAC'] = df['capMWAC'].fillna(-9999)
    df['area'] = df['area'].fillna(-9999)
    df['instYr'] = df['instYr'].fillna(-9999)
    df['azimuth'] = df['azimuth'].fillna(-9999)
    df['tilt'] = df['tilt'].fillna(-9999)
    df['modType'] = df['modType'].fillna('')
    df['grndCvr'] = df['grndCvr'].fillna('')
    df['mount'] = df['mount'].fillna('')

    # Force data types to match schema
    df['nativeID'] = df['nativeID'].astype(str)
    df['instYr'] = df['instYr'].astype(int)
    df['capMWDC'] = df['capMWDC'].astype(float)
    df['capMWAC'] = df['capMWAC'].astype(float)
    df['area'] = df['area'].astype(float)
    df['azimuth'] = df['azimuth'].astype(float)
    df['tilt'] = df['tilt'].astype(float)
    df['modType'] = df['modType'].astype(str)
    df['modType'] = df['modType'].str.lower() # Ensure modtype is lowercase
    df['grndCvr'] = df['grndCvr'].astype(str)
    df['grndCvr'] = df['grndCvr'].str.lower() # Ensure grndCvr is lowercase
    df['mount'] = df['mount'].astype(str)
    df['mount'] = df['mount'].str.lower() # Ensure mount is lowercase

    # As a default, if modType is not in the accepted potential module types, set to c-si.
    potentialModTypes = ['mono-c-si', 'multi-c-si', 'c-si', 'csp', 'thin-film']
    df.loc[~df['modType'].isin(potentialModTypes), 'modType'] = 'c-si'

    # Select schema columns
    df = df[['nativeID', 'instYr', 'capMWDC', 'capMWAC', 'area', 'modType', 'grndCvr', 'azimuth', 'tilt', 'mount', 'Source', 'geometry']]
    df = df.reset_index(drop=True)
    return df

# Function to assign mount type to solar panel-rows based on azimuth and panel geometry. Also returns all relevant design parameters for each panel-row. Requires the setting of a length ratio threshold and an area ratio threshold.
def assignMountType(feature):
    # Estimate azimuth of solar panel-row short edge
    def getAzimuth(feature):
        # Get the minimum bounding rectangle (oriented)
        mbr = feature.geometry.minimum_rotated_rectangle
        
        # Get the coordinates of the MBR
        coords = list(mbr.exterior.coords)
        
        # Calculate distances between consecutive vertices to determine lengths of edges
        edge_lengths = []
        for i in range(len(coords) - 1):  # last point is a duplicate of the first
            p1, p2 = coords[i], coords[i + 1]
            dist = np.sqrt((p2[0] - p1[0])**2 + (p2[1] - p1[1])**2)
            # Set a tempArea 
            # panels = panels**2 + (p2[1] - p1[1])**2)
            edge_lengths.append(dist)
        
        # Identify shorter and longer sides
        short_edge_index = np.argmin(edge_lengths[:2])  # first two edges are enough to find shorter side
        
        # Use the shorter edge for azimuth calculation
        p1, p2 = coords[short_edge_index], coords[short_edge_index + 1]
        
        # Calculate the azimuth (angle relative to north, counterclockwise)
        delta_x = p2[0] - p1[0]
        delta_y = p2[1] - p1[1]

        # Azimuth relative to north (y-axis)
        angle_radians = np.arctan2(delta_x, delta_y)
        angle_degrees = np.degrees(angle_radians)

        # Normalize the angle to 0-360 degrees
        if angle_degrees < 0:
            angle_degrees += 360
        if angle_degrees > 360:
            angle_degrees -= 360
        
        # In the northern hemisphere, the a solar panel-row azimuth angle will never be towards the north (270 to 360 and 0 to 90 degrees). Therefore, if the azimuth is between 270 and 360 or 0 and 90, we need to add 180 degrees to the azimuth to get the correct orientation of the panel.
        if 270 <= angle_degrees <= 360 or 0 <= angle_degrees <= 90:
            angle_degrees += 180

        return angle_degrees
    
    # Get the ratio of the long edge to the short edge of the panel (and the lengths of the short and long edges)
    def getLengthRatio(feature):
        # Get the minimum bounding rectangle (oriented)
        mbr = feature.geometry.minimum_rotated_rectangle
        
        # Get the coordinates of the MBR
        coords = list(mbr.exterior.coords)
        
        # Calculate distances between consecutive vertices
        edge_lengths = []
        for i in range(len(coords) - 1):  # last point is a duplicate of the first
            p1, p2 = coords[i], coords[i + 1]
            dist = np.sqrt((p2[0] - p1[0])**2 + (p2[1] - p1[1])**2)
            edge_lengths.append(dist)
        
        # Sort the edge lengths to identify short and long sides
        sorted_lengths = sorted(edge_lengths[:2])  # Only need two sides (since rectangle has equal opposite sides)
        short_edge = sorted_lengths[0]
        long_edge = sorted_lengths[1]
        
        # Calculate the ratio of long edge to short edge
        length_ratio = long_edge / short_edge
        return length_ratio, short_edge, long_edge
    
    # Run the geteAzimuth function to get the azimuth of each panel row, getLengthRatio function to get the long and short edge ratio, and the and getAreaRatio function to get the panel area to bounding box ratio
    azimuth = getAzimuth(feature)
    length_ratio, short_edge, long_edge = getLengthRatio(feature)

    # Assign mount type based on azimuth and area ratio 
    # Fixed-axis: If the azimuth is within 60 degrees of S, and length ratio is greater than 2.5
    # Single-axis: If the azimuth is within 30 degrees of E or W (in southward radians), and length ratio is greater than 2.5
    # Dual-axis: Any azimuth and the length ratio is less than 2.5
    def classify_mount_type(azimuth, length_ratio):
        # Load the config from the text file and all required variables
        config = load_config()
        lengthRatioThresh = config['lengthRatioThresh']  # If length ratio < 3.0, set to dual_axis or else fixed_axis_diagonal, else single- or fixed-axis

        # Check if azimuth is within 60 degrees to to S (180) -- Should never be north
        if (abs(azimuth - 180) <= 60):
            if length_ratio >= lengthRatioThresh:
                return 'fixed_axis'
        
        # Check if azimuth is within 30 degrees of close to E (90) or W (270)
        elif (abs(azimuth - 90) <= 30 or abs(azimuth - 270) <= 30):
            if length_ratio >= lengthRatioThresh:
                return 'single_axis'
        
        # Otherwise, classify as dual-axis
        if length_ratio < lengthRatioThresh: # if area_ratio > areaRatioThresh and length_ratio < lengthRatioThresh:
            return 'dual_axis'
        
        # Default case -- no panel-rows should be missed, but default to fixed-axis
        return 'fixed_axis'
    
    # Classify the mount type
    mount = classify_mount_type(azimuth, length_ratio)

    # Assign mount type based on azimuth, and return the mount type, azimuth, length ratio, short edge, and long edge
    return mount, azimuth, length_ratio, short_edge, long_edge

# Function to check for and remove erroneous geometries in arrays
def checkArrayGeometries(arrays): 
    # Load the config from the text file
    config = load_config()
    minPanelRowArea = config['minPanelRowArea'] # 15 m2, minimum area for a single panel row from the 1st percentile panel area from Stid et al., 2022
    
    # For a collection of reasons, array boundaries may contain erroneous geometries that result in a near-zero area, linestrings, or points. 
    # To check for and remove these, we'll explode arrays, calculate a temporary area, remove subarrays that are less than a minimum area, then dissolve by tempID.
    arrays['tempDissolveID'] = (1 + np.arange(len(arrays)))  # Create a temporary ID for dissolving
    arrays = arrays.explode(index_parts=False)
    arrays['tempArea'] = arrays['geometry'].area
    arrays = arrays[arrays['tempArea'] >= minPanelRowArea]
    arrays = arrays.dissolve(by=['tempDissolveID'], as_index=False)
    arrays = arrays.drop(columns=['tempArea', 'tempDissolveID'])
    arrays = arrays.reset_index(drop=True)
    return arrays

# Function to create an array from a set of panel rows based on the distance between them
def createArrayFromPanels(panelsGDF, buffDist, dissolveID, areaID='area', getArrayStats=True):

    # Create a copy of the panels GeoDataFrame to avoid modifying the original
    panels = panelsGDF.copy()

    # If dissolveID is absent or "", create a temporary dissolveID
    if dissolveID is None or dissolveID == '':
        panels['tempDissolveID'] = 1
        dissolveID = 'tempDissolveID'
    
    # Buffer the geometries by buffDist, dissovle boundaries, and unbuffer by buffDist* -1. Assign the number of objects being dissovle into a numPanels column.
    arrays = panels.copy()
    arrays['geometry'] = arrays.buffer(buffDist)
    arrays = arrays.dissolve(by=[dissolveID], as_index=False)
    arrays['geometry'] = arrays.buffer(buffDist * -1)

    # If a temporary dissolveID was created, explode arrays
    if dissolveID == 'tempDissolveID':
        arrays = arrays.explode(index_parts=False).reset_index(drop=True)

    # If getArrayStats is True, calculate the number of panels and total panel area within each array
    if getArrayStats:
        # Count panels per group before dissolving
        panelCounts = panels.groupby(dissolveID).size().reset_index(name='numPanels')

        # Get the total area of the panels within each group (sum of area column). 
        panelAreas = panels.groupby(dissolveID)[areaID].sum().reset_index(name='pnlArea')

        # Merge the panel counts and panel areas back into the dissolved array DataFrame. Select only the dissolveID and respective columns in the right df
        arrays = arrays.merge(panelCounts[[dissolveID, 'numPanels']], on=dissolveID, how='left')
        arrays = arrays.merge(panelAreas[[dissolveID, 'pnlArea']], on=dissolveID, how='left')

    # Due to the buffering and unbuffering, some mulitpolygons contain erroneous geometries that result in a near-zero area, linestrings, or points. Remove these.
    arrays = checkArrayGeometries(arrays)

    # Reset index and drop temporary dissolveID if it was created
    arrays = arrays.reset_index(drop=True)
    arrays = arrays.drop(columns='tempDissolveID', errors='ignore')
    return arrays

# Define a function that groups solar panels by mount type and proximity
def groupArrayByVariableAndProximity(gdf, buffer_distance, variable):
    # Set a temporary gdf to buffer
    gdfBuffer = gdf.copy()

    # If variable is not defined (function only has two arguments), create a dummy variable column
    if variable is None or variable == '':
        gdfBuffer['tempVar'] = 1
        variable = 'tempVar'

    # Create a buffered version of the geometries
    gdfBuffer['geometry'] = gdfBuffer.buffer(buffer_distance)

    # Dissolve by mount
    gdfBuffer = gdfBuffer.dissolve(by = variable, dropna = False).reset_index()

    # Explode the dissolved gdf
    gdfBuffer = gdfBuffer.explode(index_parts=False).reset_index(drop = True)

    # Assign a temp ID to the gdfBuffer
    gdfBuffer['tempDissolveID'] = range(0, len(gdfBuffer))

    # Assign each panel the corresponding tempDissolveID and total panel num in array by spatial join.
    gdfOut = gpd.sjoin(gdf, gdfBuffer[['tempDissolveID', 'geometry']], how='left', predicate='intersects').drop(columns='index_right')

    # Group polygons into multiploygons by array ID. Keep the column
    gdfOut = gdfOut.dissolve(by = 'tempDissolveID').reset_index()

    # Drop the tempDissolveID column and the temporary variable column if it was created
    gdfOut = gdfOut.drop(columns='tempDissolveID', errors='ignore')
    gdfOut = gdfOut.drop(columns='tempVar', errors='ignore')
    return gdfOut

# Function to drop self-overlapping geometries in a GeoDataFrame
def dropSelfOverlapGDF(gdf: gpd.GeoDataFrame, unbuffer_m: float = 1.0) -> gpd.GeoDataFrame:
    # Check for empty GeoDataFrame and projected CRS
    if gdf.empty:
        return gdf.copy()
    if gdf.crs is None or gdf.crs.is_geographic:
        raise ValueError("dropSelfOverlapGDF expects a projected CRS in meters. Reproject first (e.g., to EPSG:5070).")

    # Create a copy of the gdf with a temporary ID column
    base = gdf.copy()
    base["tempID"] = range(len(base))

    # Unbuffer by 1 m (or set unbuffer_m). Fix invalids first to avoid buffer errors.
    tmp = base[["tempID", "geometry"]].copy()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        tmp["geometry"] = tmp.geometry.buffer(0)                    # light make-valid
        tmp["geometry"] = tmp.geometry.buffer(-abs(unbuffer_m))     # negative buffer

    # Drop empties produced by the unbuffer step
    tmp = tmp[tmp.geometry.notnull() & ~tmp.geometry.is_empty].copy()
    # Check if the temporary GeoDataFrame is empty
    if tmp.empty:
        # Nothing to collide with after unbuffer → keep everything
        out = base.drop(columns=["tempID"]).reset_index(drop=True)
        return out

    # Self spatial join on unbuffered shapes
    hits = gpd.sjoin(
        tmp, tmp[["tempID", "geometry"]],
        how="left", predicate="intersects",
        lsuffix="l", rsuffix="r"
    )

    # Only care about *other* shapes, not self
    hits = hits[hits["tempID_l"] != hits["tempID_r"]].copy()
    if hits.empty:
        out = base.drop(columns=["tempID"]).reset_index(drop=True)
        return out

    # Mark rows that intersect ANY earlier (smaller tempID) row → those should be dropped
    hits["has_prior"] = hits["tempID_r"] < hits["tempID_l"]
    to_drop_ids = set(hits.groupby("tempID_l")["has_prior"].any().pipe(lambda s: s[s].index))
    
    # Return the original gdf minus the to-drop rows
    out = base[~base["tempID"].isin(to_drop_ids)].copy()
    out = out.drop(columns=["tempID"]).reset_index(drop=True)
    return out

# Function to buffer point data and remove overlaps based on order of preference
def bufferFacilityPointData(gdf, bufferDist):
    gdf_buffer = gdf.copy()
    gdf_buffer['geometry'] = gdf_buffer.buffer(bufferDist)
    return gdf_buffer

# Function to preferentially filter overlapping polygons across multiple GeoDataFrames
def preferentialSpatialFilter(gdfList, predicate="intersects", ensure_same_crs=True, return_type="accepted"):
    """
    Preferentially keep polygons by list order. For each layer (after the first),
    drop features that spatially intersect anything already kept from earlier layers.

    Parameters
    ----------
    gdf_list : list[gpd.GeoDataFrame]
        Ordered by priority (0 = highest). Must be polygonal (or at least area-ish).
    predicate : str
        Spatial predicate to use (e.g., "intersects", "overlaps", "touches", "within").
    ensure_same_crs : bool
        If True, reproject all to the CRS of the first GDF.
    copy : bool
        If True, work on copies (leaves inputs untouched).

    Returns
    -------
    kept_layers : list[gpd.GeoDataFrame]
        Filtered GDFs in the same order as input.
    accepted_all : gpd.GeoDataFrame
        Concatenation of all kept features across layers (priority-resolved).
    masks : list[pd.Series]
        Boolean masks aligned to each *original* GDF index indicating which rows were kept.
    """
    if not gdfList:
        return [], gpd.GeoDataFrame(geometry=[], crs=None), []

    # Normalize CRS
    crs0 = gdfList[0].crs
    layers = []
    for g in gdfList:
        gi = g.copy()
        if ensure_same_crs and gi.crs != crs0:
            gi = gi.to_crs(crs0)
        # GeoPandas sometimes dislikes non-unique indices in sjoin;
        # keep original index for mask, but use a temporary, unique index for operations.
        gi = gi.copy()
        gi["_tmp_rowid"] = range(len(gi))
        layers.append(gi)

    kept_layers = []
    masks = []
    accepted = None  # grows as we go

    for i, cur in enumerate(layers):
        if i == 0 or (accepted is None or accepted.empty):
            kept = cur
            mask = pd.Series(True, index=gdfList[i].index)
        else:
            # sjoin to find rows that intersect any already-accepted feature
            # Left join: rows with a match (index_right notna) are conflicts and get dropped
            joined = gpd.sjoin(cur[["_tmp_rowid", "geometry"]],
                               accepted[["geometry"]],
                               how="left",
                               predicate=predicate)

            to_drop = joined["index_right"].notna()
            # keep the ones with NO match in accepted
            kept_rowids = set(joined.loc[~to_drop, "_tmp_rowid"])
            kept = cur[cur["_tmp_rowid"].isin(kept_rowids)]

            # Build a boolean mask aligned to original index
            mask = cur.set_index(gdfList[i].index).index.to_series().map(
                lambda idx: cur.loc[idx, "_tmp_rowid"] in kept_rowids
                if idx in cur.index else False
            )
            # If the original had non-unique indices, map by position instead:
            if mask.isna().any():
                # fallback: positional mask
                pos_mask = cur["_tmp_rowid"].isin(kept_rowids).values
                mask = pd.Series(pos_mask, index=gdfList[i].index)

        # Clean temp column for the outward-facing result
        kept = kept.drop(columns=["_tmp_rowid"], errors="ignore")

        kept_layers.append(kept)
        masks.append(mask)

        # Grow the accepted pool for the next iteration.
        accepted = kept if accepted is None else pd.concat([accepted, kept], ignore_index=True)

    # Finalize accepted_all CRS
    accepted_all = accepted.set_crs(crs0, allow_override=True)

    # Select return type
    if return_type == "kept":
        return kept_layers
    elif return_type == "accepted":
        return accepted_all
    elif return_type == "masks":
        return masks
    elif return_type == "all":
        return kept_layers, accepted_all, masks
    else:
        raise ValueError("Invalid return_type. Must be one of {'kept', 'accepted', 'masks', 'all'}.")

# Function to fill missing attributes in target from an overlapping source
def fillMetadataByOverlap(target, source, aggConfig, predicate='intersects'):
    """
    Fill attributes in `target` from overlapping `source` features based on aggConfig.

    Parameters
    ----------
    target, source : GeoDataFrame
        Input GeoDataFrames with same CRS and valid geometries.
    aggConfig : dict
        Mapping of column name -> (aggregator, kind, override)
        - aggregator: 'mode' | 'mean' | 'median' | 'first' | callable(series)->scalar
        - kind: 'num' | 'text' (determines cleaning/coercion)
        - override: bool (True = overwrite even if target already has a value)
    predicate : str
        Spatial predicate for matching ('intersects', 'overlaps', etc.)

    Returns
    -------
    GeoDataFrame : target with filled/overwritten attributes.
    """
    if target is None or source is None or target.empty or source.empty:
        return target

    tgt = target.copy().reset_index(drop=False).rename(columns={'index': '_i'})
    src = source.copy()
    cols = list(aggConfig.keys())

    # Ensure all columns exist
    for c in cols:
        if c not in tgt.columns: tgt[c] = np.nan
        if c not in src.columns: src[c] = np.nan

    # Spatial join (many sources per target)
    j = gpd.sjoin(
        tgt[['_i', 'geometry']],
        src[cols + ['geometry']],
        how='left',
        predicate=predicate)
    if j.empty:
        return gpd.GeoDataFrame(tgt.drop(columns=['_i']), geometry='geometry', crs=target.crs)

    # Cleaning helpers
    def _clean_num(s: pd.Series) -> pd.Series:
        s = pd.Series(s)                          # ensure Series
        s = s.mask(s.isin([-9999, ""]))           # set sentinels to NaN
        return pd.to_numeric(s, errors="coerce").dropna()
    def _clean_txt(s: pd.Series) -> pd.Series:
        s = pd.Series(s, dtype="object")
        s = s.mask(s.isin([-9999, ""]))           # set sentinels to NaN
        return s.dropna()

    # Define aggregators
    def _agg_mode(s: pd.Series, kind: str):
        s2 = _clean_num(s) if kind == "num" else _clean_txt(s)
        if s2.empty:
            return np.nan
        m = s2.mode()
        v = (m.iloc[0] if not m.empty else (s2.median() if kind == "num" else np.nan))
        # enforce type
        if kind == "num":
            v = float(v)  # ensure numeric scalar
        else:
            v = str(v)
        return v
    def _agg_mean(s: pd.Series, kind: str):
        s2 = _clean_num(s)
        return float(s2.mean()) if not s2.empty else np.nan
    def _agg_median(s: pd.Series, kind: str):
        s2 = _clean_num(s)
        return float(s2.median()) if not s2.empty else np.nan
    def _agg_first(s: pd.Series, kind: str):
        s2 = _clean_num(s) if kind == "num" else _clean_txt(s)
        if s2.empty:
            return np.nan
        v = s2.iloc[0]
        return float(v) if kind == "num" else str(v)
    agg_registry = {
        'mode': _agg_mode,
        'mean': _agg_mean,
        'median': _agg_median,
        'first': _agg_first}

    # Build per-column aggregator wrappers
    agg_funcs = {}
    for col, (agg, kind, _) in aggConfig.items():
        if callable(agg):
            def make_user_fn(user_fn, kind):
                def wrapper(s):
                    cleaned = _clean_num(s) if kind == 'num' else _clean_txt(s)
                    return np.nan if cleaned.empty else user_fn(cleaned)
                return wrapper
            agg_funcs[col] = make_user_fn(agg, kind)
        else:
            base = agg_registry.get(agg, _agg_mode)
            agg_funcs[col] = (lambda base=base, kind=kind: (lambda s: base(s, kind)))()

    # Aggregate overlapping values per target geometry
    agg = j.groupby('_i').agg(agg_funcs)

    # Fill or overwrite target
    tgt = tgt.set_index('_i')
    for col, (_, _, override) in aggConfig.items():
        vals = agg.get(col)
        if vals is None:
            continue
        # Identify rows to fill
        if override:
            to_fill = vals.index[vals.notna()]
        else:
            miss = tgt[col].isna() | (tgt[col] == -9999) | (tgt[col] == "")
            to_fill = miss.index[miss.loc[miss.index] & vals.loc[miss.index].notna()]
        
        # Before update: relax dtype so assignment is compatible
        if aggConfig[col][1] == "num":
            # allow floats during filling
            tgt[col] = pd.to_numeric(tgt[col], errors="coerce").astype("float64")
        else:
            tgt[col] = tgt[col].astype("string")  # pandas nullable string

        # Update
        tgt.loc[to_fill, col] = vals.loc[to_fill]

        # After update: tighten dtype again
        if aggConfig[col][1] == "num":
            if col == "instYr":
                # year should be integer; round then set nullable integer
                tgt[col] = pd.to_numeric(tgt[col], errors="coerce").round().astype("Int64")
            else:
                tgt[col] = pd.to_numeric(tgt[col], errors="coerce").astype("float64")
        else:
            tgt[col] = tgt[col].astype("string")

    return gpd.GeoDataFrame(tgt.reset_index(drop=True),geometry='geometry', crs=target.crs)

# Function to fill metadata gaps across multiple GeoDataFrames based on a provided preference order and overlap
# Starting at the lowest preference dataset, fill metadata gaps in gdfAll moving up the preference list. Function to iterate through preference list. 
def iterateFillMetadataByOverlap(gdfAll, gdfMetadataPriorityList, aggConfig):
    # Iterate through the gdfList in reverse order (from lowest to highest preference)
    for gdf in reversed(gdfMetadataPriorityList):
        gdfAll = fillMetadataByOverlap(gdfAll, gdf, aggConfig)
    return gdfAll

# Function to read in the shapefiles/geojsons from folder and return a processed panel geodataframe
def getPanels_method(path):

    # Load the config from the text file
    config = load_config()
    gee_crs = config['gee_crs'] # native projection of Google Earth Engine exports
    toCRS = config['to_crs']  # EPSG:6350 NAD83 (2011)

    # Append toCRS with the EPSG prefix for use in GeoPandas
    toCRS = f'EPSG:{toCRS}'

    # Function to load geodataframes if different files are present in the folder
    def load_gdf(path, extension, target_crs):
        files = [f for f in os.listdir(os.path.join(path)) if f.endswith(f'.{extension}')]
        dfs = [gpd.read_file(os.path.join(path, file)) for file in files]
        # Directly concatenate, set crs, and reproject
        return gpd.GeoDataFrame(pd.concat(dfs, ignore_index=True)).set_crs(gee_crs).to_crs(target_crs)
    
    # Handle both GeoJson and Shp files, both may be present depending on script4 output requirements (vertex limit of geojson)
    # Check what file extensions are present in the folder (either/or geojson or shapefile). 
    # If both are present, load both and concatenate. If only one is present, load that one.
    geoJsonFileNum = len([f for f in os.listdir(os.path.join(path)) if f.endswith('.geojson')])
    shpFileNum = len([f for f in os.listdir(os.path.join(path)) if f.endswith('.shp')])
    if geoJsonFileNum > 0 and shpFileNum > 0:
        solarPanelsJSON = load_gdf(path, 'geojson', toCRS)
        solarPanelsSHP = load_gdf(path, 'shp', toCRS)
        solarPanels = pd.concat([solarPanelsJSON, solarPanelsSHP], ignore_index=True)
        print('Both geojson and shapefile found in the folder. Concatenating both.')
    elif geoJsonFileNum > 0:
        solarPanels = load_gdf(path, 'geojson', toCRS)
    elif shpFileNum > 0:
        solarPanels = load_gdf(path, 'shp', toCRS)
    else:
        raise ValueError('No valid file extensions found in the folder. Please provide either a geojson or shapefile.')

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ Explode arrays into panels, remove array with missing panels

    # Remove rows where pnlsPres == "No"
    solarPanels = solarPanels[solarPanels['pnlsPres'] != 'No']

    # Remove rows where pnlNum is 1
    solarPanels = solarPanels[solarPanels['pnlNum'] > 1]

    # Explode the multipolygons
    solarPanels = solarPanels.explode(index_parts=False)

    # Reset the index
    solarPanels = solarPanels.reset_index(drop=True)

    # Drop the subset, pnlsPres columns
    solarPanels = solarPanels.drop(columns='pnlsPres')

    # Set area
    solarPanels['area'] = solarPanels.geometry.area

    # Return the geodataframe
    return solarPanels

# Function to give a gdf list that is in preferential order for spatial filtering, and create merged panel datasets
def preferentialSpatialPanelRowFilter(gdfList):

    # Load the config from the text file
    config = load_config()
    panelArrayBuff = config['panelArrayBuff']  # Buffer distance between panels and arrays in meters
    toCRS = config['to_crs']  # EPSG:6350 NAD83 (2011)

    # Append toCRS with the EPSG prefix for use in GeoPandas
    toCRS = f'EPSG:{toCRS}'

    # Check that both GeoDataFrames have the toCRS
    for i in range(len(gdfList)):
        if gdfList[i].crs != toCRS:
            gdfList[i] = gdfList[i].to_crs(toCRS)

    # Set desired panel columns prior to merging
    panelColumns = ['pnlSource', 'nativeID', 'Source', 'area', 'geometry']
    for i in range(len(gdfList)):
        gdfList[i] = gdfList[i][panelColumns].copy()

    # Create arrays from panels for each GeoDataFrame
    arrayGdfList = []
    for i in range(len(gdfList)):
        arrayGdf = createArrayFromPanels(gdfList[i], panelArrayBuff, '', '', False)
        arrayGdfList.append(arrayGdf)

    # Set source columns WITHIN GDF to compare after preferential spatial filtering
    # pnlSource = gdf_1 for the first GeoDataFrame in the list, and so on
    for i in range(len(gdfList)):
        gdfList[i]['tmpPnlSource'] = f'gdf_{i+1}'
    for i in range(len(arrayGdfList)):
        arrayGdfList[i]['pnlArrSource'] = f'gdf_{i+1}'

    # Perform preferential spatial filtering on the array gdfs
    prefArrays = preferentialSpatialFilter(arrayGdfList)

    # Perform spatial join for each original panel GDF → preferred arrays
    # Keep only panels whose pnlSource matches pnlArrSource
    filteredPanelsList = []
    for i in range(len(gdfList)):
        joined = gpd.sjoin(
            gdfList[i],
            prefArrays[['pnlArrSource', 'geometry']],
            how='left',
            predicate='intersects'
        )

        # Keep only rows where the panel's source matches the chosen array source
        keep = joined[joined['tmpPnlSource'] == joined['pnlArrSource']].copy()

        # Drop sjoin artifacts and pnlArrSource (optionally keep pnlSource)
        keep = keep.drop(columns=['index_right', 'tmpPnlSource', 'pnlArrSource'], errors='ignore')

        filteredPanelsList.append(keep)

    # Merge all preferentially filtered panels into a single GeoDataFrame
    mergedPanels = pd.concat(filteredPanelsList, ignore_index=True)
    mergedPanels = gpd.GeoDataFrame(mergedPanels, geometry='geometry', crs=toCRS)
    mergedPanels = mergedPanels.reset_index(drop=True)

    # Set the final panelID as 1 through n for the entire dataset
    mergedPanels['panelID'] = range(1, len(mergedPanels) + 1)
    return mergedPanels

# Create a function to calculate the inter-row spacing for each panel in the same array in the direction of the azimuth (for fixed-axis and single-axis arrays) and any direction (for dual-axis arrays)
def calculateRowSpacing(gdf):
    # Load the config from the text file
    config = load_config()
    panelArrayBuff = config['panelArrayBuff']  # Buffer distance between panels and arrays in meters
    
    # Set columns
    azimuth_col = 'rowAzimuth'
    row_mount_col = 'rowMount'
    group_col = 'arrayID'
    geometry_col = 'geometry'
    panel_col = 'panelID'

    # Initialize with NaN for no results
    gdf.loc[:, 'rowSpace'] = np.nan

    # For the sake of printing progress, order gdf by increasing arrayID
    gdf = gdf.sort_values(group_col)

    # Define a function to filter candidates based on azimuth direction
    def filter_candidates(base_azimuth, candidate_azimuths, row_mount):
        # Filter candidates based on azimuth direction.
        if row_mount in ['fixed_axis', 'single_axis']:
            # Define the valid azimuth directions (forward and backward vectors)
            forward_azimuth = base_azimuth % 360
            backward_azimuth = (base_azimuth + 180) % 360

            # Allow some tolerance for alignment (e.g., ±15 degrees)
            tolerance = 15
            valid = (
                (np.abs(candidate_azimuths - forward_azimuth) <= tolerance) |
                (np.abs(candidate_azimuths - backward_azimuth) <= tolerance)
            )
            return valid
        # For dual_axis, allow all candidates
        return np.full(len(candidate_azimuths), True)

    # Iterate over each array
    for arrayID, group in gdf.groupby(group_col):
        # Because this is an intensive operation, print progress as a percentage. Only print every 1%, based on group_col as a proportion of the number of unique ids in group_col.
        uniqueIDs = gdf[group_col].nunique()
        currentID = arrayID
        if uniqueIDs > 0 and (uniqueIDs // 20) > 0:
            if currentID % (uniqueIDs // 20) == 0:
                print(f'{currentID} of {uniqueIDs} ({100 * currentID / uniqueIDs:.0f}%) in progress')
                pass
        else:
            print('Not enough groups to print progress. Will complete shortly.')
        
        # Skip groups with only one polygon
        if len(group) < 2:
            continue  # Skip groups with only one polygon
        group = group.copy()  # Copy for memory safety

        # Build a spatial index for the current group
        spatial_index = group.sindex

        results = []
        for idx, row in group.iterrows():
            base_geom = row[geometry_col]
            base_azimuth = row[azimuth_col]
            row_mount = row[row_mount_col]

            # Calculate distances to all other geometries in the group within panelArrayBuff * 2 + 1 (21m, just to be sure we capture an panel from the buffer-dissolve-erode method). 
            base_geom_buffered = base_geom.buffer(panelArrayBuff * 2 + 1)

            # Query the spatial index for geometries within the buffer
            possible_matches_index = list(spatial_index.intersection(base_geom_buffered.bounds))
            possible_matches = group.iloc[possible_matches_index]

            # Exclude the current geometry (self-match)
            candidates = possible_matches[possible_matches.index != idx]

            # Further refine candidates by checking if they fall within the buffered area
            candidates = candidates[candidates[geometry_col].intersects(base_geom_buffered)]

            # Filter candidates by azimuth direction (valid)
            if not candidates.empty:
                # Get the valid candidates
                valid = filter_candidates(base_azimuth, candidates[azimuth_col], row_mount)
                valid_candidates = candidates[valid].copy() # Copy for memory safety
                valid_candidates['distance_to_base'] = valid_candidates[geometry_col].apply(base_geom.distance)

                # Calculate distances to valid candidates
                if not valid_candidates.empty:
                    # Use a list comprehension to calculate distances and ensure numeric output
                    distances = [base_geom.distance(candidate_geom) for candidate_geom in valid_candidates[geometry_col]]
                    valid_candidates = valid_candidates.copy()  # Avoid SettingWithCopyWarning
                    valid_candidates['distance_to_base'] = distances

                    # Ensure removed self interseciton and set distance max to panelArrayBuff*2 (20m). If distance to base is greater, set to 20. Copy for memory safety.
                    valid_candidates = valid_candidates[valid_candidates['distance_to_base'] > 0]
                    valid_candidates['distance_to_base'] = valid_candidates['distance_to_base'].apply(lambda x: panelArrayBuff * 2 if x > panelArrayBuff * 2 else x)

                    # Get the minimum distance among valid candidates
                    if not valid_candidates.empty:
                        min_distance = valid_candidates['distance_to_base'].min()
                        results.append((idx, min_distance))

        # Update distances in the original GeoDataFrame
        for idx, min_distance in results:
            gdf.loc[idx, 'rowSpace'] = min_distance

    return gdf

# Get array mount type from the majority class, or create a mixed class if no majority. Result is fixed_axis, single_axis, dual_axis, or mixed_[unique_classes] if there is not a 90% majority class.
def getArrayMount(group):
    counts = group.value_counts()
    total = counts.sum()
    # Check if any class makes up more than 75% of the total
    if (counts / total).max() > 0.75:
        return counts.idxmax()  # Majority class
    else:
        # If mixed, create the "mixed_" label with sorted unique classes that are only the first letter of each class in the group
        unique_classes = ''.join(sorted({g[0] for g in group.unique()}))
        return f'mixed_{unique_classes}'

# Get array azimuth from panel-row azimuths depdending on mount. Fixed- and dual-axis arrays have an avgAzimuth of the median of rowAzimuth. Single-axis arrays have an avgAzimuth of the median of rowAzimuth IF rowAzimuth is  + 90 degrees. Mixed arrays should be ignored, but have an avearge azimuth of the median of rowAzimuth.
def getArrayAzimuth(group):
    # Get most common mount type in group (fixed_axis, single_axis, dual_axis, mixed_[unique_classes])
    mount_type = getArrayMount(group['rowMount'])
    row_azimuth = group['rowAzimuth']
    if mount_type in ['fixed_axis', 'dual_axis']:
        # Median for fixed and dual-axis
        return np.median(row_azimuth)
    elif mount_type == 'single_axis':
        # If single-axis, azimuths could be east (90 to 120) or west (240 to 270). Separate by east and west, take the median for each, then convert the west average azimuth to the equivalent southfacing east average azimuth, and get the average of the two.
        # For example, if west azimuth average is 260 and east azimuth average if 105, the adjusted west azimuth average would be 90+(270-westAvgAzimuth) = 100. The average azimuth would be (100+105)/2 = 102.5
        east_azimuths = row_azimuth[(row_azimuth >= 90) & (row_azimuth <= 120)]
        west_azimuths = row_azimuth[(row_azimuth >= 240) & (row_azimuth <= 270)]
        east_avg = np.median(east_azimuths)
        west_avg = np.median(west_azimuths)
        west_avg_adj = 90 + (270 - west_avg)
        return np.nanmean([east_avg, west_avg_adj])
    elif mount_type.startswith('mixed'):
        # Median for mixed arrays (ignore NaN)
        return np.median(row_azimuth)
    else:
        return np.median(row_azimuth)
    
# Create a multiple linear regression model between latitude and longitude to predict GCR1 and GCR2 for each mountType and modType
def spatiallyExtrapolateGCR(df):
    '''
    Spatially extrapolate GCR1 and GCR2 values for arrays missing GCR data based on latitude and longitude using 
    logistic regression for fixed-axis mounts and linear regression for single- and dual-axis mounts.
    Mount relationship and bounds are based on [Tonita et al., 2023](https://doi.org/10.1016/j.solener.2023.04.038).
    '''
    # Define logit and inverse logit functions for GCR scaling between bounds a and b for fixed-axis mounts
    EPS = 1e-6  # prevents infs in logit
    def to_logit_gcr(y, a, b, eps=EPS):
        # scale to (0,1) then logit
        p = (y - a) / (b - a)
        p = np.clip(p, eps, 1 - eps)
        return np.log(p / (1 - p))
    def from_logit_gcr(z, a, b):
        # logistic then rescale back to [a,b]
        p = 1 / (1 + np.exp(-z))
        return a + (b - a) * p

    # Define mount GCR extrapolation bounds
    mountBounds = {
        'fixed_axis':  (0.1, 0.8),
        'single_axis': (0.1, 0.7),
        'dual_axis':   (0.2, 0.8),
        'else':        (0.1, 0.8)}

    # Define PV and CSP mod type groups
    modGroups = {'PV': ['c-si', 'thin-film'], 'CSP': ['csp']}

    # Get unique mount types
    mountTypes = df['mount'].unique()

    # Iterate over each mount type -- Select mount data to consdier for spatial extrapolation
    for mountType in mountTypes:
        # Get GCR bounds for the current mount type
        if mountType in mountBounds:
            a, b = mountBounds[mountType]
        else:
            a, b = mountBounds['else']
        
        # Filter data for the current mount type
        # Consider all data if mountType is unknown
        if mountType == 'unknown':
            print("Not all arrays contain a mount type. For these, we will use arrays of all mount types for training and prediction.")
            mountData = df.copy()
        # Else, if mountType contains 'mixed', set mountType to 'mixed' and filter all df rows with mountType containing 'mixed'
        elif 'mixed' in mountType:
            print("Mixed mount type detected. For these, we will use arrays of all mount types for training and prediction.")
            mountData = df[df['mount'].str.contains('mixed')].reset_index(drop=True)
        # Else, filter data for the current mount type (fixed_axis, single_axis, or dual_axis)
        else:
            print(f"Mount type assessed: {mountType}")
            # df rows with mountType and gcr is not null
            mountData = df[(df['mount'] == mountType)].reset_index(drop=True)

        # Iterate over PV and CSP mod type groups
        for modGroup, modTypes in modGroups.items():
            # Filter data for the current mod type group
            modData = mountData[mountData['modType'].isin(modTypes)]

            # Separate into withGCR and withoutGCR subsets (with GCR1 and GCR2)
            # withGCR = modData[modData['numRow'] > 0].reset_index(drop=True)
            # withoutGCR = modData[modData['numRow'] <= 0].reset_index(drop=True)
            withGCR = modData[modData['GCR1'].notna() & modData['GCR2'].notna()].reset_index(drop=True)
            withoutGCR = modData[modData['GCR1'].isna() | modData['GCR2'].isna()].reset_index(drop=True)

            # Use broader mount type dataset if not enough data for this mod group
            if withGCR.empty: # or withoutGCR.empty:
                print(f"- Insufficient data for mount: {mountType}, modGroup: {modGroup}. Using broader dataset.")
                withGCR = mountData[mountData['numRow'] > 0].reset_index(drop=True)
                withoutGCR = mountData[mountData['numRow'] <= 0].reset_index(drop=True)

            # Drop rows with missing latitude, longitude, GCR1, or GCR2
            withGCR = withGCR.dropna(subset=['latitude', 'longitude', 'GCR1', 'GCR2'])
            withoutGCR = withoutGCR.dropna(subset=['latitude', 'longitude'])

            # Proceed if we have training and prediction data
            if not withGCR.empty and not withoutGCR.empty:
                
                # Get training and prediction data
                xTrain = withGCR[['latitude', 'longitude']]
                yTrainGCR1 = withGCR['GCR1']
                yTrainGCR2 = withGCR['GCR2']
                xPredict = withoutGCR[['latitude', 'longitude']]
                
                # If mountType is fixed_axis, use logit transformation for GCR1 and GCR2
                if mountType == 'fixed_axis':
                    # Train regression models for GCR1 and GCR2 with logit transformation
                    zTrain1 = to_logit_gcr(yTrainGCR1.values, a=a, b=b)
                    modelGCR1 = LinearRegression().fit(xTrain, zTrain1)
                    zPred1 = modelGCR1.predict(xPredict)
                    withoutGCR['GCR1'] = from_logit_gcr(zPred1, a=a, b=b)
                    zTrain2 = to_logit_gcr(yTrainGCR2.values, a=a, b=b)
                    modelGCR2 = LinearRegression().fit(xTrain, zTrain2)
                    zPred2 = modelGCR2.predict(xPredict)
                    withoutGCR['GCR2'] = from_logit_gcr(zPred2, a=a, b=b)
                
                # Else, use straight linear regression for other mount types 
                else:
                    # Train regression models for GCR1 and GCR2
                    modelGCR1 = LinearRegression().fit(xTrain, yTrainGCR1)
                    modelGCR2 = LinearRegression().fit(xTrain, yTrainGCR2)
                    withoutGCR['GCR1'] = modelGCR1.predict(xPredict)
                    withoutGCR['GCR2'] = modelGCR2.predict(xPredict)

                    # Enforce mount-specific bounds
                    withoutGCR['GCR1'] = withoutGCR['GCR1'].clip(lower=a, upper=b)
                    withoutGCR['GCR2'] = withoutGCR['GCR2'].clip(lower=a, upper=b)

                # Merge the updated rows back
                df = df.merge(
                    withoutGCR[['arrayID', 'GCR1', 'GCR2']],
                    on='arrayID',
                    how='left',
                    suffixes=('', '_new'))
                df['GCR1'] = df['GCR1_new'].combine_first(df['GCR1'])
                df['GCR2'] = df['GCR2_new'].combine_first(df['GCR2'])
                df = df.drop(columns=['GCR1_new', 'GCR2_new'])

    # As a check, set the max GCR1 and GCR2 values from zero to one
    df['GCR1'] = df['GCR1'].clip(lower=0, upper=1)
    df['GCR2'] = df['GCR2'].clip(lower=0, upper=1)

    # Round GCR1 and GCR2 to four decimal places
    df['GCR1'] = df['GCR1'].round(4)
    df['GCR2'] = df['GCR2'].round(4)

    return df

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ GM-SEUS Plotting Functions

# Create a function to merge raster files in a folder. This function will merge all TIFF files in a folder and reproject the merged raster to the specified CRS
def mergeRaster(folder_path, plotCRS, output_file):
    # Find all TIFF files in the folder
    tiff_files = glob.glob(os.path.join(folder_path, '*.tif'))
    
    # Open and read the TIFF files
    src_files_to_mosaic = []
    for tif_file in tiff_files:
        src = rasterio.open(tif_file)
        src_files_to_mosaic.append(src)
    
    # Merge the TIFF files into a single mosaic
    mosaic, out_trans = merge(src_files_to_mosaic)
    
    # Get metadata of the first file to use for output metadata
    out_meta = src_files_to_mosaic[0].meta.copy()
    
    # Update the metadata with new dimensions, transform, and CRS
    out_meta.update({
        "driver": "GTiff",
        "height": mosaic.shape[1],
        "width": mosaic.shape[2],
        "transform": out_trans,
        "crs": src_files_to_mosaic[0].crs
    })
    
    # Reproject the mosaic to the specified CRS
    dest_crs = plotCRS

    # Calculate the bounding box of the mosaic
    bounds = rasterio.transform.array_bounds(mosaic.shape[1], mosaic.shape[2], out_trans)

    # Calculate the transformation for reprojection
    transform, width, height = calculate_default_transform(
        src_files_to_mosaic[0].crs, dest_crs, mosaic.shape[2], mosaic.shape[1], *bounds)
    
    # Update metadata with the new CRS, width, and height
    out_meta.update({
        'crs': dest_crs,
        'transform': transform,
        'width': width,
        'height': height
    })

    # Create a new raster to save the reprojected data
    with rasterio.open(output_file, "w", **out_meta) as dest:
        # Reproject the mosaic to the destination CRS
        for i in range(1, mosaic.shape[0] + 1):
            reproject(
                source=mosaic[i - 1],
                destination=rasterio.band(dest, i),
                src_transform=out_trans,
                src_crs=src_files_to_mosaic[0].crs,
                dst_transform=transform,
                dst_crs=dest_crs,
                resampling=ResamplingEnum.nearest)

    # Close all open source files
    for src in src_files_to_mosaic:
        src.close()

    print(f"Mosaic created and saved to {output_file}")

# Create a read raster function. This function will read a raster file and reproject it to the specified CRS
def readRaster(raster_path, plotCRS, fromGEE=False):
    # Open the raster file and reproject it to Albers Equal Area
    with rasterio.open(raster_path) as src:
        transform, width, height = rasterio.warp.calculate_default_transform(
            src.crs, plotCRS, src.width, src.height, *src.bounds)
        kwargs = src.meta.copy()
        kwargs.update({
            'crs': plotCRS,
            'transform': transform,
            'width': width,
            'height': height
        })

        # Reproject the raster
        raster = np.zeros((height, width), dtype=rasterio.float32)
        rasterio.warp.reproject(
            source=rasterio.band(src, 1),
            destination=raster,
            src_transform=src.transform,
            src_crs=src.crs,
            dst_transform=transform,
            dst_crs=plotCRS,
            resampling=Resampling.nearest
        )

    return raster, kwargs

# Rasterize the CONUS_union boundary
def create_boundary_mask(geometry, raster_shape, transform):
    """
    Rasterize a geometry to match the raster dimensions.
    """
    boundary_mask = rasterize(
        [(geometry, 1)],  # Geometry to rasterize
        out_shape=raster_shape,  # Match raster dimensions
        transform=transform,  # Match raster transform
        fill=0,  # Background pixels (outside geometry)
        dtype='uint8'
    )
    return boundary_mask

# Create a function to plot a raster image with a scale bar
def convert_tif_to_png_with_scalebar(tif_file, output_png, dpi=600, add_scalebar=False, rgb=True):
    # Load the image using rasterio
    with rasterio.open(tif_file) as src:

        # If the image is RGB, read all bands and stack them, else, read the first band
        if rgb:
            img = src.read([1, 2, 3])  # Read the first three bands (Red, Green, Blue)
            img = np.stack([img[0], img[1], img[2]], axis=-1)  # Stack bands along the last dimension
        else:
            img = src.read(1)
        
        # Normalize pixel values to [0, 1] range for matplotlib
        img = img.astype(float)
        img -= img.min()
        img /= img.max()
    
    # Create a figure and axis to plot the image
    fig, ax = plt.subplots()
    ax.imshow(img)
    ax.axis('off')  # Turn off the axis

    # Add scale bar if required
    if add_scalebar:
        scalebar = ScaleBar(1, units='m', location='lower right')  # Adjust units and location as needed
        ax.add_artist(scalebar)

    # Save the plot as a PNG
    fig.savefig(output_png, dpi=dpi, bbox_inches='tight', pad_inches=0)
    plt.close(fig)

# Example usage to process multiple files
def process_multiple_tif_files(tif_folder, output_folder, dpi=600):
    tif_files = [os.path.join(tif_folder, f) for f in os.listdir(tif_folder) if f.endswith('.tif')]
    output_pngs = [os.path.join(output_folder, f.replace('.tif', '.png')) for f in os.listdir(tif_folder) if f.endswith('.tif')]

    for i, tif_file in enumerate(tif_files):
        # If tif_file contains the string 'trueColor', set rgb=True, else, set rgb=False
        rgbTemp = 'trueColor' in tif_file
        output_png = output_pngs[i]
        convert_tif_to_png_with_scalebar(tif_file, output_png, dpi=dpi, add_scalebar=(i == 0), rgb=rgbTemp)  # Add scale bar to the first file

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ GM-SEUS LULC Module Functions

# Function to map each element in an array to the corresponding GMSEUS class
def mapClass(npArray, schema, className):
    # Ensure schema lookup dictionary for faster mapping
    value_to_class = schema.set_index('Value')[className].to_dict()

    # Convert input array to NumPy array if it's not already
    npArray = np.asarray(npArray, dtype=object)  # Keep object dtype to avoid coercion issues

    # Map values, handling missing entries safely
    return np.array([value_to_class.get(val, np.nan) for val in npArray], dtype=object)

# Function to classify the most commen land use type (mode) based on 5 years of data
def mostCommonLandUse(npArray):
    # Set NaN value
    lulcNaN = np.nan
    # Get the mode of the array, ignoring NaN values. If only one value is present, it will be returned.
    mode = pd.Series(npArray).mode(dropna=True)
    # Drop "nan" and NaN from the mode series
    mode = mode[mode != 'nan']
    mode = mode[mode.notna()]
    # If mode is empty, return NaN
    if mode.empty:
        return lulcNaN
    else:
        return mode[0]