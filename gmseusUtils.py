# Import Basic Libraries
import geopandas as gpd
import pandas as pd
import numpy as np
import os
import glob
from pathlib import Path
import warnings

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

# directory where gmseusUtils.py lives
_HERE = Path(__file__).resolve().parent

# one level up = your project root
wd = _HERE.parent

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ GM-SEUS Startup Functions

# Function to check if folder exists, if not create it
def checkFolder(folder):
    if not os.path.exists(folder):
        os.makedirs(folder)

# Function to load config file
def load_config(filename):
    config = {}
    with open(filename, 'r') as f:
        for line in f:
            # Strip whitespace and split by '='
            key, value = line.strip().split('=')
            # Try to convert to numeric values if possible
            try:
                value = float(value) if '.' in value else int(value)
            except ValueError:
                pass  # Leave as string if not a number
            config[key] = value
    return config

# Function to load geodataframes from all files in a folder
def load_all_gdf(path, extension, target_crs):
    files = [f for f in os.listdir(path) if f.endswith(f'.{extension}')]
    dfs = [gpd.read_file(os.path.join(path, file)) for file in files]
    # Directly concatenate and reproject
    return gpd.GeoDataFrame(pd.concat(dfs, ignore_index=True)).to_crs(target_crs)

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ GM-SEUS General Functions

# Function to format the existing solar array datasets to the desired schema
def formatDf(df, nativeIdentifier, installationYear, capacityMWdc, area_m2, moduleType, agrivoltaicType, azimuth, mountTechnology, source):
    # Change column names to match the schema
    df = df.rename(columns={nativeIdentifier: 'nativeID', capacityMWdc: 'cap_mw', area_m2: 'area', installationYear: 'instYr', moduleType: 'modType', azimuth: 'azimuth', mountTechnology: 'mount', agrivoltaicType: 'AVtype'})

    # Set source
    df['Source'] = source

    # Fill empy numeric column rows with -9999, and empty string column rows with NaN
    df['cap_mw'] = df['cap_mw'].fillna(-9999)
    df['area'] = df['area'].fillna(-9999)
    df['instYr'] = df['instYr'].fillna(-9999)
    df['azimuth'] = df['azimuth'].fillna(-9999)
    df['modType'] = df['modType'].fillna('')
    df['AVtype'] = df['AVtype'].fillna('')
    df['mount'] = df['mount'].fillna('')

    # Force data types to match schema
    df['nativeID'] = df['nativeID'].astype(str)
    df['instYr'] = df['instYr'].astype(int)
    df['cap_mw'] = df['cap_mw'].astype(float)
    df['area'] = df['area'].astype(float)
    df['azimuth'] = df['azimuth'].astype(float)
    df['modType'] = df['modType'].astype(str)
    df['modType'] = df['modType'].str.lower() # Ensure modtype is lowercase
    df['AVtype'] = df['AVtype'].astype(str)
    df['AVtype'] = df['AVtype'].str.lower() # Ensure AVtype is lowercase
    df['mount'] = df['mount'].astype(str)
    df['mount'] = df['mount'].str.lower() # Ensure mount is

    # As a default, if modType is not c-si or csp or thin-film, set to c-si. We use this information in the image classification.
    df.loc[~df['modType'].isin(['c-si', 'csp', 'thin-film']), 'modType'] = 'c-si'

    # Select schema columns
    df = df[['nativeID', 'instYr', 'cap_mw', 'area', 'modType', 'AVtype', 'azimuth', 'mount', 'Source', 'geometry']]
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
        config = load_config(os.path.join(wd, r'Code\config.txt'))
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
    config = load_config(os.path.join(wd, r'Code\config.txt'))
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
def createArrayFromPanels(panels, buffDist, dissolveID, areaID='area'):
 
    # Count panels per group before dissolving
    panelCounts = panels.groupby(dissolveID).size().reset_index(name='numPanels')

    # Get the total area of the panels within each group (sum of area column). 
    panelAreas = panels.groupby(dissolveID)[areaID].sum().reset_index(name='pnlArea')
    
    # Buffer the geometries by buffDist, dissovle boundaries, and unbuffer by buffDist* -1. Assign the number of objects being dissovle into a numPanels column.
    arrays = panels.copy()
    arrays['geometry'] = arrays.buffer(buffDist)
    arrays = arrays.dissolve(by=[dissolveID], as_index=False)
    arrays['geometry'] = arrays.buffer(buffDist * -1)

    # Merge the panel counts and panel areas back into the dissolved array DataFrame. Select only the dissolveID and respective columns in the right df
    arrays = arrays.merge(panelCounts[[dissolveID, 'numPanels']], on=dissolveID, how='left')
    arrays = arrays.merge(panelAreas[[dissolveID, 'pnlArea']], on=dissolveID, how='left')

    # Due to the buffering and unbuffering, some mulitpolygons contain erroneous geometries that result in a near-zero area, linestrings, or points. Remove these.
    arrays = checkArrayGeometries(arrays)

    # Reset index
    arrays = arrays.reset_index(drop=True)
    return arrays

# Define a function that groups solar panels by mount type and proximity
def groupArrayByVariableAndProximity(gdf, buffer_distance, variable):
    # Set a temporary gdf to buffer
    gdfBuffer = gdf.copy()

    # Create a buffered version of the geometries
    gdfBuffer['geometry'] = gdfBuffer.buffer(buffer_distance)

    # Dissolve by mount
    gdfBuffer = gdfBuffer.dissolve(by = variable)

    # Explode the dissolved gdf
    gdfBuffer = gdfBuffer.explode(index_parts=False).reset_index(drop = True)

    # Assign a temp ID to the gdfBuffer
    gdfBuffer['tempDissolveID'] = range(0, len(gdfBuffer))

    # Assign each panel the corresponding tempDissolveID and total panel num in array by spatial join.
    gdfOut = gpd.sjoin(gdf, gdfBuffer[['tempDissolveID', 'geometry']], how='left', predicate='intersects').drop(columns='index_right')

    # Group polygons into multiploygons by array ID. Keep the column
    gdfOut = gdfOut.dissolve(by = 'tempDissolveID').reset_index()

    # Drop the tempDissolveID column
    gdfOut = gdfOut.drop(columns='tempDissolveID', errors='ignore')
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