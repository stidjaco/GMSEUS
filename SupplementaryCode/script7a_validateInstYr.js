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
Date Updated: 01-08-2026
Contact: stidjaco@msu.edu (Jacob Stid)
 
-- Notes --
In this script, we use available NAIP, Sentinel, and Landsat Imagery to check the installation year of solar energy systems. 
We do this through two mechanisms: visual interpretation of the imagery (map) AND time series (console)
When an installation year is acquired, manually attribute it in script7 ipynb
When an exact installation year is uncertain, use the first year of high confidence (often, with NAIP). 
*/

//###############################\\
// Required Validation Variables \\
//###############################\\

// Required variables
var startYear = '2010'; 
var id = 8413; // CHECK BELOW: Automated method or manual entry for arrayIDcol
var getChart = false; // prevent running each time, save ee-memory. Chart is really only useful for larger installations (30m resolution)

// Optional variables
var idMethod = 'arrayID' // 'index' means when id = 0, first array is selected and so on. Any other choice is by arrayIDcol
var earliestYear = '1995'
var naipBuffer = 1250; 
var satBuffer = 1e3;

//#######################\\
// Select Array Boundary \\
//#######################\\

// Call joined GM-SEUS array shapes
var gmseus = ee.FeatureCollection("projects/ee-stidjaco/assets/BigPanel/GMSEUS_Arrays_instYr_joinedMerged");
var arrayIDcol = 'subArrID'

// Get gmseus with missing instYr
var gmseusNoInstYr = gmseus.filter(ee.Filter.eq("instYr", -9999)).sort(arrayIDcol, true);

// Get feature to manually validate. Alternatively, set arrayIDcol manually and comment out above code
if(idMethod === 'index'){
  var ids = gmseusNoInstYr.aggregate_array(arrayIDcol); var feature = ee.Feature(gmseusNoInstYr.filter(ee.Filter.eq(arrayIDcol, ids.get(id))).first()); print("By Index Method - Array ID being assessed: ", feature.getNumber(arrayIDcol));
} else {
  var feature = ee.Feature(gmseusNoInstYr.filter(ee.Filter.eq(arrayIDcol, id)).first()); print("By Array ID Method - Array ID being assessed: ", feature.getNumber(arrayIDcol));
}

// Set feature geometry as imagery input
var geom = feature.geometry(); Map.centerObject(geom, 18);

// Get geeUtilsStid.js functions
var geeUtilsStid = require('users/stidjaco/SourceCode:geeUtilsStid.js');
var ls_harmonize = geeUtilsStid.ls_harmonize_fromComposite;
var s2_harmonize = geeUtilsStid.s2_harmonize;
var getSpectralIndexBand = geeUtilsStid.getSpectralIndexBand;

// ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ MAPPING

//#############################\\
// Imagery Start and End dates \\
//#############################\\

// Set other time variables
var endYear = startYear
var startDate = '-10-01'
var endDate = '-12-31'

// Get ls and s2 imagery
var ls = ls_harmonize(geom.centroid().buffer(satBuffer).bounds(), ee.DateRange(startYear+startDate, endYear+endDate), '8day'); var lsVisParams = {bands: ['Red', 'Green', 'Blue'], min: 0, max: 0.5, gamma: 1.2};
var s2 = s2_harmonize(geom.centroid().buffer(satBuffer).bounds(), ee.DateRange(startYear+startDate, endYear+endDate)); var s2VisParams = {bands: ['Red', 'Green', 'Blue'], min: 0, max: 0.3, gamma: 1.2};
var naip = ee.ImageCollection('USDA/NAIP/DOQQ').filterDate(startYear+'-1-01', endYear+'-12-31').filterBounds(geom); var naipVisParams = {bands: ['R', 'G', 'B'], min: 0.0, max: 255.0};

//#####################\\
//     Map Imagery     \\
//#####################\\

// Get Naip Date
var tStart = ee.Date(naip.first().get('system:time_start')).format('YYYY-MM-dd');
var tEnd = ee.Date(naip.first().get('system:time_end')).format('YYYY-MM-dd');
print('NAIP Date: ', tStart); 

// Print array of interest Source
print('Array Source: ', feature.get('Source'))

// Print number and unique tempID
print("Number of array chunks missing an instYr:", gmseusNoInstYr.size());

// Prep and map LS, S2, and NAIP
var lsMap = ls.mean().clip(geom.centroid().buffer(satBuffer).bounds())//.reproject({crs: 'EPSG:4326', scale: 30});
var s2Map = s2.mean().clip(geom.centroid().buffer(satBuffer).bounds())//.reproject({crs: 'EPSG:4326', scale: 10});
var naipMap = naip.mean().clip(geom.centroid().buffer(naipBuffer).bounds()); // .reproject({crs: 'EPSG:4326', scale: 0.6})
Map.addLayer(naipMap, naipVisParams, 'NAIP', true);
Map.addLayer(s2Map, s2VisParams, 'Sentinel', false);
Map.addLayer(lsMap, lsVisParams, 'Landsat', false);
Map.addLayer(gmseus, {fill: 'red'}, 'All Arrays', false)
Map.addLayer(feature.geometry(), {fill: 'blue'}, 'Array of Interest', true);

// ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ TIME SERIES



//########################################################################################################
//#                                                                                                    #\\
//#                                   BREAKPOINT / SERIES PARAMETERS                                   #\\
//#                                                                                                    #\\
//########################################################################################################

// Annual series window
var seriesStartYear = earliestYear;
var seriesEndYear   = 2025;
var seriesStartDate = '-01-01';
var seriesEndDate   = '-12-31'

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

// ------------------------------------------------------------
// Multi-index wrapper: compute 5 indices + print + chart
// ------------------------------------------------------------

// Only perform if getChart == true
if(getChart === true){
  
  var indexBands = ['NDPVI', 'NBD', 'NDMI', 'EVI', 'TCG']; // edit if needed
  
  // Localized Landsat annual collection for this polygon (same as you already do)
  var geom = feature.geometry();
  var dateRange = ee.DateRange(seriesStartYear + seriesStartDate, seriesEndYear + seriesEndDate);
  var lsAnnualIC = ls_harmonize(geom, dateRange, 'annual');
  var seriesByBand = {};
  indexBands.forEach(function(band) {
    seriesByBand[band] = annualCompositeZonalSeries(lsAnnualIC, geom, band);
  });
  //print('Series dictionary (newest → oldest)', seriesByBand);
  
  // Use first band as reference for years
  var ref = seriesByBand[indexBands[0]];
  var yearsNewest = ee.List(ref.get('yearSeries'));
  var yearsOldest = yearsNewest.reverse();
  var n = yearsOldest.size();
  
  var fcChart = ee.FeatureCollection(
    ee.List.sequence(0, n.subtract(1)).map(function(i) {
      i = ee.Number(i);
      var j = n.subtract(1).subtract(i); // map oldest → newest index
  
      var props = ee.Dictionary({year: yearsOldest.get(i)});
  
      indexBands.forEach(function(band) {
        var valsNewest = ee.List(seriesByBand[band].get('valSeries'));
        props = props.set(band, valsNewest.get(j));
      });
  
      return ee.Feature(null, props);
    })
  );
  
  var chart = ui.Chart.feature.byFeature(fcChart, 'year', indexBands)
    .setChartType('LineChart')
    .setOptions({
      title: 'Annual AOI Zonal Mean (' + seriesStartYear + '–' + seriesEndYear + ')',
      hAxis: { title: 'Year', format: '####' },
      vAxis: { title: 'Index value (inverted where flagged)' },
      lineWidth: 2,
      pointSize: 3,
      legend: { position: 'right' }
    });
  
  print(chart);
}