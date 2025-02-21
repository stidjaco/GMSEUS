//#####################################################################################################################//
/////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
//////////////////////////////////////////                                       ////////////////////////////////////////
//////////////////////////////////////////   Get Solar Array Installation Year   ////////////////////////////////////////
//////////////////////////////////////////                                       ////////////////////////////////////////
/////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
//#####################################################################################################################//
 
/*
-- Information --
Author: Jacob Stid
Date Created: 11-04-2024
Date Updated: 01-03-2025
Contact: stidjaco@msu.edu (Jacob Stid)

-- Notes --
This script is currently set up to export LandTrendr year of detection for one index. 
Run this script for each desired index, and collect the most common year outside earth engine in python. 
Currently, steps of 5 only result in 0-2 failed exports per index (which you then have to rerun with a step 1)
*/

exports.doc = 'LandTrendr and Installation Year Extraction';
//var arrays = ee.FeatureCollection('projects/ee-stidjaco/assets/BigPanel/initialGMSEUS_Arrays')//.filter(ee.Filter.eq('instYr', 2019)); Map.addLayer(arrays); //Map.centerObject(ee.Feature(arrays.filter(ee.Filter.eq("arrayID", 3478)).first()))

//######################################################################################################## 
//#                                                                                                    #\\
//#                                     LANDTRENDR Solar Function                                      #\\
//#                                                                                                    #\\
//########################################################################################################

// Set arrays
//var arrays = ee.FeatureCollection('projects/ee-stidjaco/assets/BigPanel/GMSEUS_Arrays_instYr');
var arrays = ee.FeatureCollection('projects/ee-stidjaco/assets/BigPanel/GMSEUS_Arrays_instYr_Update');

// Set subset range (0 to 1000 for full dataset) -- NBD 620 and 930 (by 5)
var start = 0; 
var end = 1000;
var step = 25;

// Give the run some names
var runName = "012625" ;

// Select multiple indices (no longer all at once, rapidly reach computational limit)
var index1 = 'NDPVI';
var index2 = 'NBD';
var index3 = 'BR';
var index4 = 'NDWI';
var index5 = 'NDVI';
var index6 = 'EVI';
var index7 = 'NBR';
var index8 = 'NDMI';
var index9 = 'TCA';
var index10 = 'TCG';
var index11 = 'TCW';
var index12 = 'TCB';
//var index13 = 'NDSI'; // Normalized difference snow index: snow still covers panels, low likelihood of change in annual snow reflectance due to solar alone

/*
Failed (by 5): 
NDPVI: -
NBD: -
BR: -
NDWI: -
NDVI: -
EVI: -
NBR: -
NDMI: -
TCA: (-)
TCG: (-)
TCW: 
TCB:
*/

// Set index 
var index = index12

// Set seed
var seed = 15; 

//##########################################################################\\
/////////////////////////////// Prep-LandTrendr \\\\\\\\\\\\\\\\\\\\\\\\\\\\\\
//##########################################################################\\

// Define collection parameters
var startYear = 2005; 
var endYear = 2024;
var maskThese = ['cloud'];

// Define boundary years for install year, which we also remove
var minYear = 2008;
var maxYear = 2024;
var nullYear = -9999; // Setting when no detected year of change

// Define landtrendr parameters
var runParams = { 
  maxSegments:            6,    // 6
  spikeThreshold:         0.5,  // 0.9
  vertexCountOvershoot:   2,    // 3
  preventOneYearRecovery: true, // true
  recoveryThreshold:      0.33, //  0.25, 1/years to recovery  # should be no recovery so 1/YOD range
  pvalThreshold:          0.05, // 0.05
  bestModelProportion:    0.75, // 0.75
  minObservationsNeeded:  6     // 6
};

// Define change parameters
var changeParams = {
  delta:  'loss',  // fastest loss of index values because index flipped in LT source script
  sort:   'newest', // fastest
  year:   {checked:true, start:minYear, end:maxYear},
  mag:    {checked:false, value:50,  operator:'>'}, //, dsnr:true}, // if remove dsnr, value changes to 100
  dur:    {checked:false, value:1,    operator:'>'}, // specific to year range
  preval: {checked:false, value:500,  operator:'<'},
  mmu:    {checked:false, value:3}};

//############################################################################
// END INPUTS
//############################################################################

// Load the LandTrendr.js module
var ltgee = require('users/stidjaco/BigPanel:SourceCode/LandTrendrSolarIndex.js'); 

// Actual Landtrendr function to aquire installation year
var runSolarLT = function(feature){
  
  //############################################################################
  // END INPUTS
  //############################################################################
  
  // Set aoi
  var aoi = feature.geometry();
  
  //  Consider, if array is in eastern state, set winter time start and end dates, else use full year. 
  // or just run all three and pick the most recent YOD

  // Define base start and end dates and off-growing season dates
  var startDay = '01-01';
  var endDay = '12-31'; 
  //var startDay = '01-01';
  //var endDay = '03-31';
  
  // For each index, run landTrendr
  var runIndexLT = function(indx){
    
    // Set index for changeParams
    changeParams.index = indx;
    
    // run landtrendr
    var lt = ltgee.runLT(startYear, endYear, startDay, endDay, aoi, indx, [], runParams, maskThese);
    
    // get the change map layers
    var changeImg = ltgee.getChangeMap(lt, changeParams).clip(aoi);
  
    // Subset for year of detection
    var YOD_installed = changeImg.select(['yod']).clip(aoi);
    
    //###########################################################################
    // Extract YOD from shape
    //###########################################################################
  
    // Year of detection mode within renewable boundary (includes nulls where no change detected) -- First Segmentation period
    var YOD_wnull = YOD_installed.reduceRegion({
        reducer: ee.Reducer.mode({maxRaw: 1e6}),
        geometry: aoi,
        scale: 30,
        maxPixels: 1e13
      }).getNumber('yod');
      
    // If no LandTrendr detected change within polygon, set to NA
    var YOD_init = ee.Number(ee.Algorithms.If(YOD_wnull, YOD_wnull, nullYear)).toInt();

    // Remove boundary years, and set nulls
    var YOD = ee.Number(ee.Algorithms.If(YOD_init.gt(minYear).and(YOD_init.lt(maxYear)), YOD_init, nullYear));
    return(YOD);
  };
  
  // Run LT for each index and store results
  var YOD = runIndexLT(index);
  
  /*
  // Run LT for each index and store results
  var YOD1 = runIndexLT(index1);
  var YOD2 = runIndexLT(index2);
  var YOD3 = runIndexLT(index3);
  var YOD4 = runIndexLT(index4);
  var YOD5 = runIndexLT(index5);
  var YOD6 = runIndexLT(index6);
  var YOD7 = runIndexLT(index7);
  var YOD8 = runIndexLT(index8);

  // Initialize an empty dictionary to count occurrences
  var yodCounts = ee.Dictionary({});

  // Helper function to update counts in yodCounts
  var updateYODCount = function(yod){yodCounts = yodCounts.set(yod, ee.Number(yodCounts.get(yod, 0)).add(1));  };

  // Update counts for each YOD, if they are valid
  if (YOD1.neq(nullYear)) updateYODCount(YOD1);
  if (YOD2.neq(nullYear)) updateYODCount(YOD2);
  if (YOD3.neq(nullYear)) updateYODCount(YOD3);
  if (YOD4.neq(nullYear)) updateYODCount(YOD4);
  if (YOD5.neq(nullYear)) updateYODCount(YOD5);
  if (YOD6.neq(nullYear)) updateYODCount(YOD6);
  if (YOD7.neq(nullYear)) updateYODCount(YOD7);
  if (YOD8.neq(nullYear)) updateYODCount(YOD8);
  //var yodCounts = ee.Dictionary.fromLists(['2015','2016'], [4,4]) // Test to see if function can handle the latest year approach
  
  // Helper function to get the most common year, with ties resolved by selecting the largest year
  var getMostCommonYear = function(countsDict) {
    // Convert the dictionary into a list of dictionaries with 'year' and 'count' properties
    var years = countsDict.keys();
    var counts = countsDict.values();
    var yearCountPairs = years.map(function(year) {
      return ee.Dictionary({
        year: ee.Number.parse(year),  // Convert year from string to number
        count: countsDict.get(year)   // Get the corresponding count for each year
      });
    });
  
    // Initialize an empty dictionary to store the most common year and count
    var initial = ee.Dictionary({year: -1, count: -1});
  
    // Use iterate to find the most common year with the largest year in case of a tie
    var mostCommon = yearCountPairs.iterate(function(current, acc) {
      current = ee.Dictionary(current);
      acc = ee.Dictionary(acc);
  
      var currentCount = ee.Number(current.get('count'));
      var accCount = ee.Number(acc.get('count'));
      var currentYear = ee.Number(current.get('year'));
      var accYear = ee.Number(acc.get('year'));
  
      // Check if the current count is higher than the accumulated count
      var isMoreCommon = currentCount.gt(accCount);
      // Check if counts are the same but current year is larger
      var isSameCountButLargerYear = currentCount.eq(accCount).and(currentYear.gt(accYear));
  
      // Update accumulated year and count if either condition is true
      return ee.Algorithms.If(
        isMoreCommon.or(isSameCountButLargerYear),
        current,  // Update to current if it's more common or same count but larger year
        acc       // Keep accumulated if current doesn't meet conditions
      );
    }, initial);
  
    // Extract the most common year from the result dictionary
    return ee.Dictionary(mostCommon).get('year');
  };
  
  // Get the most common year from yodCounts
  var mostCommonYear = getMostCommonYear(yodCounts);
  */
  
  // Set return variable
  var mostCommonYear = YOD; 

  // Return the feature with the year set
  return feature.set({instYrLT: mostCommonYear});
};

// ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ Export

// Set export function
var exportInstYr = function(subset){
  // Subset array dataset
  var exportFCTemp = fc.filter(ee.Filter.and(ee.Filter.gte("subset", subset), ee.Filter.lt("subset", ee.Number(subset).add(step))));
  
  // Run function
  var exportFC = exportFCTemp.map(runSolarLT); 
    
  // Export the data
  var folderName = index+'_solInstYrExport_'; 
  Export.table.toDrive({
      collection: exportFC,
      description: descriptionName + subset,
      fileFormat: 'CSV',
      folder: folderName + runName,
      selectors: ['arrayID', 'nativeID', 'tempID', 'instYr', 'instYrLT', 'modType', 'Source'] // '.geo' -- if GeoJSON
  });
};

// Add arbitrary random number to subset featureCollection
var arrays = arrays.randomColumn("subset", seed, "uniform");
var arrays = arrays.map(function(feature){return feature.set({subset: feature.getNumber("subset").multiply(1000).toInt()})});

// Save to fc variable
var fc = arrays;
var step = step;

// Run export over sequence
var descriptionName = index+'_instYrArrays_'; var end = ee.Number(end).subtract(step).getInfo(); var sequence = ee.List.sequence({start: start, end: end, step: step}).getInfo();
var exportInstYr = sequence.map(exportInstYr);
