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
Date Updated: 02-04-2025
Contact: stidjaco@msu.edu (Jacob Stid)

-- Notes --
This sript acquires 4-band NAIP imagery at native projection and CRS transform (0.6m forced) within a buffer around an array.
We then add a 5th band that is the panel-rows burned into NAIP resoltuion imagery, and export as a multi-banded raster. 
We then tile these images up in a python script: script_createLabeledImages.ipynb.

Currently, due to requirements for acquiring NAIP projection dynamically, this is a relatively intensive script. 
At best, we are exporting 200 arrays at a time (using the RUN ALL GEE extension), which takes several mintutes to load the server requests. 
*/

// Call GM-SEUS shapefile (getPanels)
var arrays = ee.FeatureCollection('projects/ee-stidjaco/assets/BigPanel/v1_0/GMSEUS_Arrays_Final4326');
var panels = ee.FeatureCollection('projects/ee-stidjaco/assets/BigPanel/v1_0/GMSEUS_Panels_Final4326');

// Due to georectification differences in NAIP and satellite/aerial imagery using for OSM, we will select only panels and arrays with panels where Source = 'CCVPV' or 'gmseus'
var panels = panels.filter(ee.Filter.inList('Source', ['CCVPV', 'gmseus'])); var naipPanelsList = panels.aggregate_array('arrayID').distinct(); 
var arrays = arrays.filter(ee.Filter.inList('arrayID', naipPanelsList));
var arrays = arrays.filter(ee.Filter.gt('numRow', 10)); 

// Filter for export efficiency
var minArrayID = 4600;
var maxArrayID = ee.Number(minArrayID).add(200).getInfo(); //var maxArrayID = 1000;
var arrays = arrays.filter(ee.Filter.gte('arrayID', minArrayID)).filter(ee.Filter.lt('arrayID', maxArrayID));

// Set variables
var tileBuffer = 100; // 80m buffer ensures that all arrays achieve at least one tile worth of labeled imagery 
var NAIPstart = '2019'; // really this is 2021, but there is a single array in the dataset where the most recent imagery is 2019 
var NAIPend = '2023'; // Set most recent NAIP year range (two years since NAIP is acquired at state level every two years)
var seed = 15; // Set seed
var scale = 0.6; // set as max of most recent imagery (0.3 to 0.6 as of 2024) 

// Set a geometrical operation error margin for NAIP imagery 
var naipErrorMargin = ee.ErrorMargin(0.1);

// Call NAIP
var NAIP = ee.ImageCollection('USDA/NAIP/DOQQ').filterDate(ee.DateRange(NAIPstart+'-01-01', NAIPend+'-12-31'));

// // TESTING & DEBUGGING -- Important: 2886
// var feature = ee.Feature(arrays.filter(ee.Filter.eq('arrayID', 4)).first()); Map.centerObject(feature); 
// var tileImage = NAIP.filterDate(2022+'-01-01', 2023+'-12-31').filterBounds(feature.geometry().buffer(250).bounds()).first()
// Map.addLayer(tileImage, {}, "Original NAIP"); print(tileImage.projection())

// ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ Create a function to export NAIP img and mask for array

// Define function
var getLabeledImages = function(arrayID){
  
  //##########################\\
  //// Get Most Recent NAIP \\\\
  //##########################\\
  
  // Set feature and aoi
  var feature = ee.Feature(arrays.filter(ee.Filter.eq('arrayID', arrayID)).first());
  var aoi = feature.geometry().buffer(tileBuffer).bounds();
  
  // Function to get the most recent image per location without reprojection
  var getMostRecentImageNAIP = function(collection) {
    // Get band names
    var bandNames = collection.first().bandNames();
    // Get NAIP id's. These are in the form: 'm_2909522_se_15_060_20201130'
    var longIDs = collection.aggregate_array('system:index').distinct();
    // For each id in uniqueIDs, drop the last 9 characters "_20201130"
    var uniqueIDs = longIDs.map(function(id){return ee.String(id).slice(0, -9);});
    // Within each non-dated index, get the most recent image
    var recentImages = uniqueIDs.map(function(id) {
      var imgs = collection.filter(ee.Filter.stringContains('system:index', id));
      var img = imgs.limit(1, 'system:time_start', false).first();  // Limit to first image when sorted by date // .sort('system:time_start', false) // Sort descending to get the most recent
      return ee.Image(img.copyProperties(imgs.first(), imgs.first().propertyNames()));
    });
    // Get the image collection 
    var imgColRecent = ee.ImageCollection(recentImages).select(bandNames);
    
    // Get projection info
    var origProj = imgColRecent.first().projection().getInfo(); // NAIP.filterBounds(aoi).limit(1, 'system:time_start', false).first().projection().atScale(scale).getInfo()
    var origCRS = origProj.crs;
    var origTransform = origProj.transform;
    
    // Return a non-mosaiced image that retains native resolution (mosaicing reduces resolution and reprojects to WGS84)
    return imgColRecent.median().set({origCRS: origCRS, origTransform: origTransform}); //.reproject({crs: origCRS, crsTransform: origTransform});
  };
  
  // Apply function to get most recent images per aoi
  var tileImage = getMostRecentImageNAIP(NAIP.filterBounds(aoi));
  
  //###########################\\
  //// Burn Panels into NAIP \\\\
  //###########################\\
  
  // Get panels for array
  var panelsArray = panels.filter(ee.Filter.eq('arrayID', arrayID));
  
  // Rasterize panel-row boundaries and create a binary NAIP image (0: no solar, 1: solar)
  var tileMask = panelsArray.filterBounds(aoi).reduceToImage({properties: ['arrayID'], reducer: ee.Reducer.first()}).gt(0)  // Convert to binary (1 for panels, 0 otherwise)
    .unmask(0).rename('mask')//.reproject({crs: 'EPSG:26920', scale: scale});
    
  // Add band to to NAIP tiled image 
  var finalImage = tileImage.addBands(tileMask).toInt().setDefaultProjection({crs: tileImage.get('origCRS'), crsTransform: tileImage.get('origTransform')});
    
  //######################################################\\
  //// Prepare Export for Labeled Image and Input Image \\\\
  //######################################################\\
  
  // Prepare whole image export
  var outFolder = "labelImgsWhole";
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

// ~~~~~~~~~~~~~~~~~~~~~~ Archive

  // // Set vars
  // var imageFolder = 'trainImages';
  // var maskFolder = 'trainMasks';
  // var fileName = 'id' + arrayID;
  // // Get projection info
  // var outCRS = finalImage.get('origCRS').getInfo(); // var outCRS = finalImage.projection().crs
  // var outTransform = finalImage.get('origTransform').getInfo();// var outTransform = finalImage.projection.transform
  // // Export
  // Export.image.toDrive({
  //   image: finalImage.select("R", "G", "B", "N"),
  //   description: fileName,
  //   dimensions: "256x256",
  //   folder: imageFolder, 
  //   crs: outCRS, 
  //   crsTransform: outTransform,
  //   region: tile, fileFormat: 'GeoTIFF', maxPixels: 1e13});
  // Export.image.toDrive({
  //   image: finalImage.select("mask"),
  //   description: fileName,
  //   dimensions: "256x256",
  //   folder: maskFolder,
  //   crs: outCRS, 
  //   crsTransform: outTransform,
  //   region: tile, fileFormat: 'GeoTIFF', maxPixels: 1e13});
  // return finalImage