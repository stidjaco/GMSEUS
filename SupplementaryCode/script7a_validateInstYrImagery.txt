//####################################################################################################################//
////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
////////////////////////////////////////                                         ///////////////////////////////////////
////////////////////////////////////////  Manually Validate InstYr With Imagery  ///////////////////////////////////////
////////////////////////////////////////                                         ///////////////////////////////////////
////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
//####################################################################################################################//
 
/*
-- Information --
Author: Jacob Stid
Date Created: 01-03-2025
Date Updated: 01-07-2025
Contact: stidjaco@msu.edu (Jacob Stid)

-- Notes --
In this script, we use available NAIP, Sentinel, and Landsat Imagery to check the installation year of solar energy systems. 
This script (script7a) can be used in collaboartion with script7b
When an installation year is acquired, manually attribute it in script7
When an exact installation year is uncertain, use the first year of high confidence (often, with NAIP). 
*/

//#######################\\
// Select Array Boundary \\
//#######################\\

// Call joined GM-SEUS array shapes
var gmseus = ee.FeatureCollection("projects/ee-stidjaco/assets/BigPanel/GMSEUS_Arrays_instYr_joined");

// Get gmseus with missing instYr
var gmseusNoInstYr = gmseus.filter(ee.Filter.eq("instYr", -9999));

// Print number and unique tempID
print("Number of array chunks missing an instYr:", gmseusNoInstYr.size());
print("Missing tempIDs:", gmseusNoInstYr.aggregate_array("tempID"));

// ~~~~~~~~~~~~~~~~~~~~~~~~~ Select automated or manual approach

// Get feature to manually validate 
var ids = gmseusNoInstYr.aggregate_array("tempID"); 
var feature = ee.Feature(gmseusNoInstYr.filter(ee.Filter.eq("tempID", ids.get(0))).first()); print("Array ID being assessed: ", feature.getNumber("tempID"));

// Alternatively, set tempID manually and comment out above code
//var id = '1983';
//var feature = ee.Feature(gmseusNoInstYr.filter(ee.Filter.eq("tempID", id)).first()); print("Array ID being assessed: ", feature.getNumber("tempID"));

// ~~~~~~~~~~~~~~~~~~~~~~~~~ Set geometry and focus

// Set feature geometry as imagery input
var geom = feature.geometry(); Map.addLayer(geom); Map.centerObject(geom);

//#############################\\
// Imagery Start and End dates \\
//#############################\\
 
// Select imagery year 
var start_date = '2018' ;
var end_date = start_date; // Selects imagery within the same year

//#####################\\
// Imagery Preparation \\
//#####################\\

// Cloud Mask function for landsat
var cloudMaskL457 = function(image) {
  var qa = image.select('QA_PIXEL');
  // If the cloud bit (5) is set and the cloud confidence (7) is high
  // or the cloud shadow bit is set (3), then it's a bad pixel.
  var cloud = qa.bitwiseAnd(1 << 5)
                  .and(qa.bitwiseAnd(1 << 7))
                  .or(qa.bitwiseAnd(1 << 3));
  // Remove edge pixels that don't occur in all bands
  var mask2 = image.mask().reduce(ee.Reducer.min());
  return image.updateMask(cloud.not()).updateMask(mask2);
};

// Function to mask clouds using the Sentinel-2 QA band.
var maskS2clouds = function(image){
  var qa = image.select('QA60');
  // Bits 10 and 11 are clouds and cirrus, respectively.
  var cloudBitMask = 1 << 10;
  var cirrusBitMask = 1 << 11;
  // Both flags should be set to zero, indicating clear conditions.
  var mask = qa.bitwiseAnd(cloudBitMask).eq(0).and(
             qa.bitwiseAnd(cirrusBitMask).eq(0));
  // Return the masked and scaled data, without the QA bands.
  return image.updateMask(mask).divide(10000)
      .select("B.*")
      .copyProperties(image, ["system:time_start"]);
};

//####################\\
//    Load Imagery    \\
//####################\\

// Load landsat 
var ls = ee.ImageCollection("LANDSAT/LE07/C02/T1_TOA")
    .filterDate(start_date+'-11-01', end_date+'-12-31')
    .map(cloudMaskL457)
    .qualityMosaic('B1')
    .clip(geom.buffer(10000));
var visParams = {bands: ['B3', 'B2', 'B1'], min: 0, max: 0.5, gamma: 1.2};

// Load Sentinel-2 TOA reflectance data.
var Sentinel = ee.ImageCollection('COPERNICUS/S2')
    .filterDate(start_date+'-11-01', end_date+'-12-31')
    // Pre-filter to get less cloudy granules.
    .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 20))
    .filterBounds(geom)
    .map(maskS2clouds)
    .qualityMosaic('B1')
    .clip(geom.buffer(10000));

// Load NAIP
var dataset = ee.ImageCollection('USDA/NAIP/DOQQ')
    .filterDate(start_date+'-1-01', end_date+'-12-31')
    .filterBounds(geom);
var NAIP = dataset.select(['R', 'G', 'B'])
    .qualityMosaic('B')
    .clip(geom.buffer(1000));
var trueColorVis = {min: 0.0, max: 255.0,};

//#####################\\
//     Map Imagery     \\
//#####################\\

Map.addLayer(NAIP, trueColorVis, 'NAIP', true);
Map.addLayer(Sentinel, {bands: ['B4', 'B3', 'B2'], min: 0, max: 0.3}, 'Sentinel', true);
Map.addLayer(ls, visParams, "Landsat", true);