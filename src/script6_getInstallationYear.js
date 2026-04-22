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
Date Updated: 12-22-2025
Contact: stidjaco@msu.edu (Jacob Stid)

-- What this script does --
For each polygon feature:
   - Build a harmonized Landsat collection (ls_harmonize) within the polygon
   - Compute an annual AOI (zonal) time series for a chosen index (index-agnostic)
   - Reverse the series (newest->oldest) and compute a single "best" breakpoint
   - Save properties onto the feature: instYrBP, bstScore, normScore

-- Sources -- 
GM-SEUS: https://doi.org/10.1038/s41597-025-05862-4
LandTrendr in GEE: https://doi.org/10.3390/rs10050691
Backtracking Solar Detection: https://doi.org/10.1016/j.srs.2025.100322
Tasseled Cap Transformations for OLI/-2: https://doi.org/10.1016/j.srs.2025.100353
*/

exports.doc = 'Back-tracked Breakpoint + Installation Year Extraction (AOI zonal annual)';


//########################################################################################################
//#                                                                                                    #\\
//#                                       IMPORT geeUtilsStid + ls_harmonize                            #\\
//#                                                                                                    #\\
//########################################################################################################

// Get geeUtilsStid.js functions
var geeUtilsStid = require('users/stidjaco/SourceCode:geeUtilsStid.js');
var ls_harmonize = geeUtilsStid.ls_harmonize_fromComposite;
var getSpectralIndexBand = geeUtilsStid.getSpectralIndexBand;

//########################################################################################################
//#                                                                                                    #\\
//#                                           SET ARRAYS / RUN                                          #\\
//#                                                                                                    #\\
//########################################################################################################

// Set arrays (optional; not used in single-feature test)
var arrays = ee.FeatureCollection('projects/ee-stidjaco/assets/BigPanel/GMSEUS_Arrays_GroundMounted');

// Subset range (0 to 1000 for full dataset)
var start = 0;
var end = 1000;
var step = 5;

// Give the run some names
var runName = "010526";

// Set seed
var seed = 15;


//########################################################################################################
//#                                                                                                    #\\
//#                                   BREAKPOINT / SERIES PARAMETERS                                   #\\
//#                                                                                                    #\\
//########################################################################################################

// Choose a band or index to use as an input to the breakpoint
// Bands: Blue, Green, Red, NIR, SWIR1, SWIR2, Thermal
// Indices: NDPVI, NBD, BR, NDWI, NDVI, EVI, NBR, NDMI, TCA, TCG, TCW, TCB
var indexBand = 'TCA';

// Annual series window
var seriesStartYear = 1985;
var seriesEndYear   = 2025;
var seriesStartDate = '-01-01';
var seriesEndDate   = '-12-31'

// Boundary years (will be set to nullYear)
var minYear  = 2005;
var maxYear  = 2024;
var nullYear = -9999;

// Breakpoint constraints on annual series
var minSide = 2;  // min years on each side
var minN    = 6;  // min valid years total (after dropping null years)
var windowYr= 5;  // number of years to look on either side of an installation year for a breapoint
var minFracOfRange = 0.2; // require breakpoint jump >= 20% of windowed series range to detect a breakpoint

// reduceRegion settings
var scale = 30;
var tileScale = 8;
var bestEffort = true;
var maxPixels = 1e13;

// Scalar reduction across AOI
var zonalReducer = ee.Reducer.mean();

//########################################################################################################
//#                                                                                                    #\\
//#                            ANNUAL COMPOSITE -> ZONAL SERIES (LISTS)                                 #\\ -- If we choose to use raw SR or the 8 or 32 day composites, this is the function we will change
//#                                                                                                    #\\
//########################################################################################################

/*
First, decide if index needs to be flipped to observe increase in relation to solar installation
  - based on index and solar spectral logic, decide indices to invert
Then, given:
  - lsAnnualIC: annual composite ImageCollection (1 image per year)
  - geom: AOI
  - bandName: one of the 7 renamed bands
Do:
  - for each image, reduceRegion over AOI to a scalar
  - keep only non-null scalars
  - return Dictionary with:
      yearSeries: newest -> oldest
      valSeries:  newest -> oldest
*/

// Function to invert 
function solarIndexInversion(bandName) {
  var invertList = ee.List(['EVI', 'NDVI', 'NDMI', 'NBR', 'TCG', 'TCW', 'TCA']);
  var invert = ee.Number(ee.Algorithms.If(invertList.contains(bandName),-1,1));
  return invert;
}

// Function to get dictionary with years and single index/band value across an image collection within an aoi
function annualCompositeZonalSeries(lsAnnualIC, geom, bandName) {

  // Ensure predictable order (oldest -> newest), then reverse at the end
  var ic = ee.ImageCollection(lsAnnualIC)
    .filterBounds(geom)
    .sort('system:time_start', true);

  // Convert the ImageCollection to a List so we can map Features safely
  var imgList = ic.toList(ic.size());

  // Build a FeatureCollection of (year, val)
  var fc = ee.FeatureCollection(
    imgList.map(function(el) {

      // Cast list element to Image explicitly
      var img = ee.Image(el);

      // Extract year from timestamp
      var y = ee.Number(ee.Date(img.get('system:time_start')).get('year'));

      // Build Index band (either direct band or computed index), then cast to Image
      var idx = ee.Image(getSpectralIndexBand(img, bandName)).multiply(solarIndexInversion(bandName));

      // AOI scalar
      var stat = idx.reduceRegion({
        reducer: zonalReducer,
        geometry: geom,
        scale: scale,
        tileScale: tileScale,
        bestEffort: bestEffort,
        maxPixels: maxPixels
      });

      // Get the scalar (may be null)
      var v = stat.get(bandName);

      return ee.Feature(null, {year: y, val: v});
    })
  ).filter(ee.Filter.notNull(['val'])); // drop nulls so we never List.add(null)

  // Aggregate lists (oldest->newest), then reverse to newest->oldest
  var years = ee.List(fc.aggregate_array('year')).reverse();
  var vals  = ee.List(fc.aggregate_array('val')).reverse();

  return ee.Dictionary({yearSeries: years, valSeries: vals});
}



//########################################################################################################
//#                                                                                                    #\\
//#                               BREAKPOINT (BACK-TRACK, LIST-BASED)                                   #\\
//#                                                                                                    #\\
//########################################################################################################

/*
  Directional + recent-preferred breakpoint (newest->oldest series)

  For each split k:
    m1 = mean(vals[0:k])   // recent
    m2 = mean(vals[k:N])   // older
    Score(k) = max(m1 - m2, 0) * (1 / (k+1)^p) * min(k, supportYears)/supportYears
      - only counts increases (directional)
      - favors more recent breaks (smaller k)
      - downweights breaks with very few recent years

  Pick k with highest Score, set:
    instYrBP = clamp(years[k] + 1, [minYear, maxYear])
    bstScore = best Score
    normScore = bstScore / sqrt(N) (0..1)
*/


function breakpointBacktrack(seriesDict) {
  
  // Set series and check number of observations
  seriesDict = ee.Dictionary(seriesDict);
  var years = ee.List(seriesDict.get('yearSeries')); // newest->oldest
  var vals  = ee.List(seriesDict.get('valSeries'));  // newest->oldest
  var N = ee.Number(vals.size());
  var enough = N.gte(minN);
  var bestScoreNull = -1e18;

  // If not enough observations, return nullYear + zero scores
  var fallback = ee.Dictionary({instYrBP: nullYear, bstScore: 0, normScore: 0});
  var result = ee.Dictionary(ee.Algorithms.If(enough, (function() {

    // Iterate over k to find best score
    var init = ee.Dictionary({bestScore: bestScoreNull, bestK: -1});
    var best = ee.Dictionary(
      ee.List.sequence(0, N.subtract(1)).iterate(function(k, acc) {
        k = ee.Number(k);
        acc = ee.Dictionary(acc);
        
        //-------------------------------------------------------- \\
        // Directional Breakpoint of Windowed Means with Weighting \\
        //-------------------------------------------------------- \\
        
        /* Directional breakpoint. Looks for large difference in 
        population means before and after each year, considering
        only increases in image band and weighting for recent 
        years and mutliple observed years*/
        
        // Windowed breakpoint parameters. Looks at a windowed timeseries of (all) years before and after each valid year
        // recent side (s1) uses the last w obs before k: [k-w, k)
        // older side (s2) uses the first w obs after k: [k, k+w)
        function meanSlice(lst, start, end){return ee.Number(ee.List(lst).slice(start, end).reduce(ee.Reducer.mean()));}
        var w = ee.Number(windowYr);
        var s1 = k.subtract(w).max(0);
        var e1 = k;
        var s2 = k;
        var e2 = k.add(w).min(N);
        var m1 = meanSlice(vals, s1, e1);
        var m2 = meanSlice(vals, s2, e2);
        var n1 = e1.subtract(s1);
        var n2 = e2.subtract(s2);

        // Require minSide points before and after breakpoint for all years and window years
        var okAll = k.gte(minSide).and(k.lte(N.subtract(minSide)));
        var okWin = n1.gte(minSide).and(n2.gte(minSide));
        var score = ee.Number(ee.Algorithms.If(okAll.and(okWin), (function() {
          
          // Sert recency preference: smaller k gets higher weight
          var p = 0.25; // try 0.25 (gentle), 0.5 (medium), 1.0 (strong)
          var recency = ee.Number(1).divide(k.add(1).pow(p));
          
          // Support in the recent segment (don’t over-trust 1-year changes). Though, too high support doenst allow for recent years.
          var supportYears = 3; // saturate after 3 recent years
          var support = n1.min(supportYears).divide(supportYears);
          
          // Directional: only accept increases (solar-like)
          var diff = m1.subtract(m2); // positive = recent NDPVI higher than old
          var dirCheck = ee.Number(ee.Algorithms.If(diff.gt(0), diff, bestScoreNull));
          
          // Magnitude: Only accept if increase is of suffiecent magnitude 
          var winVals = ee.List(vals).slice(s1, e2);  // combined local window (recent + older)
          var winMin  = ee.Number(winVals.reduce(ee.Reducer.min()));
          var winMax  = ee.Number(winVals.reduce(ee.Reducer.max()));
          var winRange = winMax.subtract(winMin);
          var jump = diff.abs();   // magnitude of windowed change
          var jumpCheck = ee.Number(ee.Algorithms.If(dirCheck.neq(bestScoreNull).and(winRange.gt(0)).and(jump.gte(winRange.multiply(minFracOfRange))), dirCheck, bestScoreNull));
          
          // Final: If all checks pass, return weighted score
          var finalScore = ee.Number(ee.Algorithms.If(jumpCheck.neq(bestScoreNull), jumpCheck.multiply(recency).multiply(support), bestScoreNull))
          
          return finalScore;
        })(), bestScoreNull));
        
        // Get best score and best k and if the change passed the magnitude gate. If score is better, return it to dictionary
        var bestScore = ee.Number(acc.get('bestScore'));
        var bestK     = ee.Number(acc.get('bestK'));
        var better = score.gt(bestScore);
        return ee.Dictionary({
          bestScore: ee.Number(ee.Algorithms.If(better, score, bestScore)),
          bestK:     ee.Number(ee.Algorithms.If(better, k, bestK)),
        });

      }, init)
    );

    var bestK = ee.Number(best.get('bestK'));
    var bestScore = ee.Number(best.get('bestScore'));
    
    // Valid detection if score is not null or NaN
    var detected = bestK
      .gte(0)
      .and(bestScore.neq(bestScoreNull))
      .and(bestScore.eq(bestScore));   // filters NaN

    // Only produce a year if detected
    var bpYear = ee.Number(ee.Algorithms.If(detected, years.get(bestK), nullYear));
    var shifted = ee.Number(ee.Algorithms.If(detected, bpYear.add(1), nullYear));
    
    // If no detection, keep nullYear (do NOT clamp)
    var instYrBP = ee.Number(ee.Algorithms.If(
      shifted.eq(nullYear),
      nullYear,
      shifted.max(minYear).min(maxYear)
    )).toInt();

    // Scores only if detection passed
    var normScore = ee.Number(ee.Algorithms.If(
      instYrBP.neq(nullYear),
      bestScore.divide(N.sqrt()).clamp(0, 1),
      0
    ));
    
    var bstScore = ee.Number(ee.Algorithms.If(instYrBP.neq(nullYear), bestScore, 0));
    return ee.Dictionary({instYrBP: instYrBP, bstScore: bstScore, normScore: normScore});
  })(), fallback));

  return result;
}

//########################################################################################################
//#                                                                                                    #\\
//#                         MAIN: RUN BREAKPOINT PER FEATURE + SAVE PROPERTIES                          #\\
//#                                                                                                    #\\
//########################################################################################################

/*
PSEUDOCODE:
  For each feature:
    geom = feature.geometry()
    lsLocal = ls_harmonize(dateRange, geom)
    series = annualZonalSeries(lsLocal, geom, index, seriesStartYear, seriesEndYear)
    stats = breakpointBacktrack(series)
    set instYrBP, bstScore, normScore on feature
*/
var runSolarBreakpoint = function(feature) {

  // Localized Landsat collection for this polygon (memory-friendly)
  var geom = feature.geometry();
  var dateRange = ee.DateRange(seriesStartYear + seriesStartDate, seriesEndYear + seriesEndDate)
  var lsLocal = ls_harmonize(geom, dateRange, 'annual');
  
  // Run breakpoint analysis 
  var seriesDict = annualCompositeZonalSeries(lsLocal, geom, indexBand);
  var stats = breakpointBacktrack(seriesDict);

  return feature.set({
    instYrBP: stats.get('instYrBP'),
    bstScore: stats.get('bstScore'),
    normScore: stats.get('normScore')
  });
};

//########################################################################################################
//#                                                                                                    #\\
//#                                     EXPORT CHUNKING (OPTIONAL)                                      #\\
//#                                                                                                    #\\
//########################################################################################################

/*
PSEUDOCODE:
  - add random subset column (0..999)
  - for each subset window [subset, subset+step):
      - filter fc to that window
      - map runSolarBreakpoint
      - export table
*/

arrays = arrays.randomColumn("subset", seed, "uniform");
arrays = arrays.map(function(feature){return feature.set({subset: feature.getNumber("subset").multiply(1000).toInt()});});
var fc = arrays;
var exportInstYr = function(subset) {
  var exportFCTemp = fc.filter(ee.Filter.and(
    ee.Filter.gte("subset", subset),
    ee.Filter.lt("subset", ee.Number(subset).add(step))
  ));
  var exportFC = exportFCTemp.map(runSolarBreakpoint);
  var folderName = indexBand + '_solInstYrExport_';
  Export.table.toDrive({
    collection: exportFC,
    description: indexBand + '_instYrBPArrays_' + subset,
    fileFormat: 'CSV',
    folder: folderName + runName,
    selectors: ['tmpArrID', 'subArrID', 'nativeID', 'instYr', 'instYrBP', 'bstScore', 'normScore', 'Source']
  });
};

// Run Batch Export
var endAdj = ee.Number(end).subtract(step).getInfo();
var sequence = ee.List.sequence({start: start, end: endAdj, step: step}).getInfo();
sequence.map(exportInstYr);


//########################################################################################################
//#                                                                                                    #\\
//#                               ONE-SHOT RUN ON A SINGLE FEATURE(AOI)                                 #\\
//#                                                                                                    #\\
//########################################################################################################

// // By drawn polygon
// var feature = ee.Feature(aoi);

// // By GM-SEUS temporary array ID
// var feature = ee.Feature(arrays.filter(ee.Filter.eq('tmpArrID', 4652)).first());
// var aoi = feature.geometry();
// // Map.addLayer(ee.ImageCollection("USDA/NAIP/DOQQ").filterDate('2018-01-01', '2018-12-31').filterBounds(aoi));

// // Build the annual zonal series directly from annual composites (no annual reducer needed)
// var ls = ls_harmonize(aoi, ee.DateRange(seriesStartYear+seriesStartDate, seriesEndYear+seriesEndDate), 'annual');
// var series = annualCompositeZonalSeries(ls, feature.geometry(), indexBand);

// // Run breakpoint
// var stats = breakpointBacktrack(series);

// // Print outputs
// print('Series (newest->oldest):', series);
// print('Breakpoint stats:', stats);

// // Optional: attach to feature to mimic your FC pipeline
// var outFeature = feature.set({
//   instYrBP: stats.get('instYrBP'),
//   bstScore: stats.get('bstScore'),
//   normScore: stats.get('normScore')
// });

// print('Feature with properties:', outFeature);

// // Map
// Map.centerObject(aoi, 15);
// Map.addLayer(ee.Image.constant(1).clip(aoi), {}, 'AOI');