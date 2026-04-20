//#####################################################################################################################//
/////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
//////////////////////////////////                                                  /////////////////////////////////////
//////////////////////////////////   Acquire Labeled Imagery for GM-SEUS Release    /////////////////////////////////////
//////////////////////////////////                                                  /////////////////////////////////////
/////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
//#####################################################################################################################//

/*
-- Information --
Author: Jacob Stid
Date Created: 02-03-2025
Date Updated: 04-16-2026
Contact: stidjaco@msu.edu (Jacob Stid)

-- Notes --
This sript acquires 4-band NAIP imagery at native projection and CRS transform (0.6m forced) within a buffer around an array.
We then add a 5th band that is the panel-rows burned into NAIP resoltuion imagery, and export as a multi-banded raster. 
We then tile these images up in a python script: script_createLabeledImages.ipynb.

Currently, due to requirements for acquiring NAIP projection dynamically, this is a relatively intensive script. 
Approach is to only look at a small range of arrayID's for viable exports (e.g., arrayID 0 to 2000 contains 140 arrays of interest)
Wait for all tasks to be generated before hitting RUNALL
*/

// Call GM-SEUS shapefile (getPanels)
var arrays = ee.FeatureCollection('projects/ee-stidjaco/assets/BigPanel/GMSEUS_Arrays_Final_2025_v2_0');
var panels = ee.FeatureCollection('projects/ee-stidjaco/assets/BigPanel/GMSEUS_Panels_Final_2025_v2_0');

// Filter for export efficiency (1 to 18,980 -- v2.0)
var minArrayID = 18000; // Finished through: 0-14000
var stepArrayID = 2000; // Unless computation is getting too slow, no change needed. Just change minArrayID. 

// Set date for export folder
var date = '041626';

// Set variables
var seed = 15; // Set seed
var NAIPstart = '2019'; // really this is 2021, but there is a single array in the dataset where the most recent imagery is 2019 
var NAIPend = '2023'; // Set most recent NAIP year range (two years since NAIP is acquired at state level every two years)
var scale = 0.6; // set as max of most recent imagery (0.3 to 0.6 as of 2024) 
var tileSize = 256; // 256x256
var naipErrorMargin = ee.ErrorMargin(0.1); // Set a geometrical operation error margin for NAIP imagery 

// We want this dataset to be internally consistent with NAIP imagery. 
// Thus, due to georectification differences in NAIP and satellite/aerial imagery using for OSM, we will restrict panel-row sources to those derived by or from NAIP
// We also want to identify a pattern (for recognition). Thus, we require a minimum number of panel-rows to create a tile
var naipPanelRowSources = ['CCVPV', 'GMSEUS_NAIP_v1_0', 'GMSEUS_NAIP_v2_0', 'GMSEUSdigArraysPanels_v2_0']; 
var minNumRow = 10;

// Get geeUtilsStid.js functions
var geeUtilsStid = require('users/stidjaco/SourceCode:geeUtilsStid.js');
var getMostRecentImageNAIP = geeUtilsStid.getMostRecentImageNAIP;

/*
// TESTING & DEBUGGING
var feature = ee.Feature(arrays.filter(ee.Filter.eq('arrayID', 4123)).first()); Map.centerObject(feature); 
var aoi = feature.geometry().buffer(tileBuffer).bounds();
var tileImage = getMostRecentImageNAIP(NAIP.filterBounds(aoi), true);
var panelsArrayAndAdjacent = panels.filterBounds(aoi);  //var panelsArray = panels.filter(ee.Filter.eq('arrayID', arrayID));
var tileMask = panelsArrayAndAdjacent.reduceToImage({properties: ['arrayID'], reducer: ee.Reducer.first()}).gt(0).unmask(0).rename('mask'); // Convert to binary (1 for panels, 0 otherwise)
var finalImage = tileImage.addBands(tileMask).toInt().setDefaultProjection({crs: tileImage.get('origCRS'), crsTransform: tileImage.get('origTransform')});
Map.addLayer(finalImage.select('mask'), {min: 0, max: 1})
fdsa
*/

// ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ Setup

// Set max arrayID to filter by
var maxArrayID = ee.Number(minArrayID).add(stepArrayID).getInfo(); 

// Based on desired tile size, set a minimum tile buffer. 
var tileBuffer = ee.Number(tileSize).multiply(scale).divide(2) // pixel buffer in each direciton
  .divide(100).round().multiply(100).getInfo(); // round to nearest 100's place for buffering -- print("Tile Buffer Distance for Desired Tile Size: ", tileBuffer)

// Filter panels and arrays
var panels = panels.filter(ee.Filter.inList('Source', naipPanelRowSources)); var naipPanelsList = panels.aggregate_array('arrayID').distinct(); // Select for high-fidelity NAIP delineated panel-rows
var arrays = arrays.filter(ee.Filter.inList('arrayID', naipPanelsList)); // Get only arrays associated with high-fidelity panel-rows
var arrays = arrays.filter(ee.Filter.gt('numRow', ee.Number(minNumRow))); // Set minimun panel-row threshold (goal is to define a pattern)
print("Total number of candidate arrays: ", arrays.size()); 
var arrays = arrays.filter(ee.Filter.gte('arrayID', minArrayID)).filter(ee.Filter.lt('arrayID', maxArrayID)); // Subset arrays for export -- computationally expensive, avoid memory issues
print("Number of arrays exporting: ", arrays.size()); 

// Call NAIP
var NAIP = ee.ImageCollection('USDA/NAIP/DOQQ').filterDate(ee.DateRange(NAIPstart+'-01-01', NAIPend+'-12-31'));

// ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ Create a function to export NAIP img and mask for array

// Define function
var getLabeledImages = function(arrayID){
  
  //##########################\\
  //// Get Most Recent NAIP \\\\
  //##########################\\
  
  // Set feature and aoi
  var feature = ee.Feature(arrays.filter(ee.Filter.eq('arrayID', arrayID)).first());
  var aoi = feature.geometry().buffer(tileBuffer).bounds();
  
  // Apply function to get most recent images per aoi
  var tileImage = getMostRecentImageNAIP(NAIP.filterBounds(aoi), true);
  
  //###########################\\
  //// Burn Panels into NAIP \\\\
  //###########################\\
  
  // Get panels for array (and any adjacent panels, incase theres an edge case where another array is included in the tile)
  var panelsArrayAndAdjacent = panels.filterBounds(aoi);  //var panelsArray = panels.filter(ee.Filter.eq('arrayID', arrayID));
  
  // Rasterize panel-row boundaries and create a binary NAIP image (0: no solar, 1: solar)
  var tileMask = panelsArrayAndAdjacent.reduceToImage({properties: ['arrayID'], reducer: ee.Reducer.first()}).gt(0).unmask(0).rename('mask'); // Convert to binary (1 for panels, 0 otherwise)
    
  // Add band to to NAIP tiled image 
  var finalImage = tileImage.addBands(tileMask).toInt().setDefaultProjection({crs: tileImage.get('origCRS'), crsTransform: tileImage.get('origTransform')});
    
  //######################################################\\
  //// Prepare Export for Labeled Image and Input Image \\\\
  //######################################################\\
  
  // Prepare whole image export
  var outFolder = "labelImgsWhole_" + date;
  var fileName = 'id' + arrayID;
  
  // Export. Omit CRS and CRS transform to allow default projection to be maintained.
  Export.image.toDrive({
    image: finalImage.select("R", "G", "B", "N", "mask"),
    description: fileName,
    folder: outFolder, 
    scale: scale,
    region: aoi, 
    fileFormat: 'GeoTIFF', 
    maxPixels: 1e13});
};

// Get list of Solar dataset indices to map over
var idList = arrays.aggregate_array('arrayID'); 

// Map the function over the indexList
idList.evaluate(function(id){
  id.forEach(function(arrayID){
    getLabeledImages(arrayID);
  });
});