//#################################################################################################################//
/////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
////////////////////////////                                                               //////////////////////////
////////////////////////////  Collection of functions with use-cases across GEE Projects   //////////////////////////
////////////////////////////                                                               //////////////////////////
/////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
//#################################################################################################################//

/*
-- Information --
Author: Jacob Stid
Date Created: 12-19-2025
Date Updated: 12-19-2025
Contact: stidjaco@msu.edu (Jacob Stid)

-- Functions --
* validateGeometries(feature): 
* splitFeatures(feature, numChunks):
* getColocatedFields(aoi): 
* getMostRecentImageNAIP(collection):
* ls_harmonize_fromSR(aoi, dateRange): 
* hls_harmonize(aoi, dateRange): 
* s2_harmonize(aoi, dateRange): 
* getSpectralIndexBand(img, bandName): 

*/

//######################################\\
////  Validate geometries for export  \\\\ ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
//######################################\\

/*
-- Notes --
*/
// Function to check for valid geometries (as polygons/multipolygons) in a feature or featureCollection
var validateGeometries = function(feature){
  //##################################################\\ 
  ///// Check array geometry for errant geometries \\\\\
  //##################################################\\
  
  // Extract and keep only Polygons
  var featurePolygon = feature.geometry().geometries().map(function(geom){
    var g = ee.Geometry(geom);
    return ee.Algorithms.If(g.type().compareTo('Polygon').eq(0), g, null);}, true); // true drops nulls
  
  // Filter shapes by area to remove artifacts of GEE geom operations (improbable value)
  var shpAreaThresh = 1; // m2
  var featurePolyFiltered = ee.List(featurePolygon).map(function(geom){
    var g = ee.Geometry(geom);
    return ee.Algorithms.If(g.area(ee.ErrorMargin(1)).gt(shpAreaThresh),g,null);}, true); // drop nulls

  // Set geometry to MultiPolygon or Polygon based on the content
  var newGeometry = ee.Geometry(ee.Algorithms.If(
    ee.Algorithms.IsEqual(featurePolyFiltered.size(), 1), // Check if the original geometry is a single polygon
    ee.Geometry(ee.List(featurePolyFiltered).get(0)), // If single polygon, return it directly
    ee.Geometry.MultiPolygon(featurePolyFiltered) // Otherwise, return as MultiPolygon
  ));
  
  // Return a new feature with valid geometries
  var newFeature = feature.setGeometry(newGeometry);
  return ee.Feature(newFeature);
};

//#######################################\\
////  Split feature equally by chunks  \\\\ ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
//#######################################\\

/*
-- Notes --
*/

// Function to split a feature into chunks along both X and Y axes
function splitFeatures(feature, numChunks) {
  var geometry = feature.geometry();
  var bounds = geometry.bounds();

  // Get bounding box coordinates
  var coords = ee.List(bounds.coordinates().get(0));
  var xCoords = coords.map(function(coord) { return ee.List(coord).get(0); });
  var yCoords = coords.map(function(coord) { return ee.List(coord).get(1); });
  var minX = ee.Number(xCoords.reduce(ee.Reducer.min()));
  var maxX = ee.Number(xCoords.reduce(ee.Reducer.max()));
  var minY = ee.Number(yCoords.reduce(ee.Reducer.min()));
  var maxY = ee.Number(yCoords.reduce(ee.Reducer.max()));

  // Calculate the number of splits along X and Y axes
  var splits = ee.Number(numChunks);

  // Calculate splits along X and Y axes (ensure integer number of splits)
  var splitsX = splits.sqrt().ceil();
  var splitsY = splits.divide(splitsX).ceil();

  // Generate split points along X and Y axes using 'count'
  var xSplitPoints = ee.List.sequence(minX, maxX, null, splitsX.add(1));
  var ySplitPoints = ee.List.sequence(minY, maxY, null, splitsY.add(1));

  // Create lists of start and end points for X and Y axes
  var xStarts = xSplitPoints.slice(0, xSplitPoints.length().subtract(1));
  var xEnds = xSplitPoints.slice(1);
  var yStarts = ySplitPoints.slice(0, ySplitPoints.length().subtract(1));
  var yEnds = ySplitPoints.slice(1);

  // Create intervals for X and Y axes
  var xIntervals = xStarts.zip(xEnds);
  var yIntervals = yStarts.zip(yEnds);

  // Create combinations of X and Y intervals to form rectangles
  var rectangles = xIntervals.map(function(xCoords) {
    xCoords = ee.List(xCoords);
    var x1 = ee.Number(xCoords.get(0));
    var x2 = ee.Number(xCoords.get(1));
    return yIntervals.map(function(yCoords) {
      yCoords = ee.List(yCoords);
      var y1 = ee.Number(yCoords.get(0));
      var y2 = ee.Number(yCoords.get(1));
      var rect = ee.Geometry.Rectangle([x1, y1, x2, y2], null, false);
      return rect;
    });
  }).flatten();
  
  // Intersect each rectangle with the feature geometry
  var chunksIntersection = ee.FeatureCollection(rectangles.map(function(rect) {
    var intersection = ee.Geometry(rect).intersection(geometry, naipErrorMargin).simplify(naipErrorMargin).buffer(3, naipErrorMargin); // Simplify to prevent unboudned geoemtrty, and buffer each geometry for overlap
    return ee.Feature(intersection).set({area: intersection.area(naipErrorMargin)});
  }));
  
  // Filter out features with empty geometries or negligible area
  var chunksInit = chunksIntersection.filter(ee.Filter.gt('area', 0));
  
  // Get featureCollection of exploded chunk geometries. Recalculate area as well. 
  var chunksPolyFC = ee.FeatureCollection(chunksInit.geometry().geometries().map(function(geom){return ee.Feature(ee.Geometry(geom)).set({area: ee.Geometry(geom).area(naipErrorMargin)})})); 

  // Some chunks might be erroneously small due to split dynamics. Thus, split into small and large chunks, merge based on threshold
  var chunkThreshold = 15; // 15 sqm minimum chunk geometry size
  var smallChunks = chunksPolyFC.filter(ee.Filter.lt("area", chunkThreshold)).map(function(feature){return feature.setGeometry(feature.geometry())}); // Small buffer to induce overlap
  var largeChunks = chunksPolyFC.filter(ee.Filter.gte("area", chunkThreshold));
  
  // Dissolve small chunks into larger chunks
  var chunksTemp = largeChunks.map(function(feature){return feature.setGeometry(feature.geometry().union(smallChunks.filterBounds(feature.geometry()).geometry(), naipErrorMargin));});
  
  // Validate chunk geometries and explode
  var chunksValid = chunksTemp.map(validateGeometries);
  
  // Finally, buffer chunks so that there is overlap and no boundary omissions
  var chunksFinal = chunksValid.map(function(feature){return feature.setGeometry(feature.geometry())}); // .bounds().buffer(3, ee.ErrorMargin(5))
  
  return ee.FeatureCollection(chunksFinal);
}

//####################################\\
////  Get Colocated Field Function  \\\\ ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
//####################################\\

/*
-- Notes --
*/

// Function to pull CSB boundaries, harmonize them by crop, and simplify inter-field chunk artifacts from CDL multi-year processing for a single aoi. Requires CSB fieldBoundaries and PLSS Qsection assets, and an aoi.
var getColocatedFields = function(aoi){
  
  // Set CSB Field variables
  var csbPeriod = '1623' // '1623', '0815', '1017'
  var cropAttribute = 'CDL2023' // CSB attribute that adjacent fields are merged on (e.g., 'CDL2023': '176')
  
  // Set areal variables
  var Twnshp_size = ee.Number(93.2e6) ; // 93.2 km2 -- PLSS Township Avg Size (36 sections)
  var Sec_size = ee.Number(2.6e6) ; // 2.6 km2 -- PLSS Section size
  var Qsec_size = ee.Number(64e4) ; // 0.65 km2 -- PLSS QSection size
  var QQsec_size = ee.Number(16e4) ; // 0.16 km2 -- PLSS QQSection size
  var fieldBuffer = 45 ; // meters, CSB derived from CDL at 30m resolution, check out at least one pixels (1.5 pixels ensures overlap of single pixel boundary removal)
  
  // Call field boundary
  var fieldBoundaries = ee.FeatureCollection('projects/sat-io/open-datasets/USDA/CSB_'+csbPeriod);
  
  // BLM PLSS Quarter Sections
  var plssQsec = ee.FeatureCollection('projects/ee-stidjaco/assets/PLSS_Qsec');
  
  // Get relevant PLSS boundaries, and clip field to plss boundary
  var plssBoundary = plssQsec.filterBounds(aoi).geometry(ee.ErrorMargin(1));

  // Filter the field boundaries to include only those that intersect with a geometry
  var intersectingFieldsAOI = fieldBoundaries.filterBounds(aoi); // Get primary field boundary intersecting aoi
  var intersectingFields = fieldBoundaries.filterBounds(intersectingFieldsAOI); // get adjacent and internal field chunks to aoi field

  // Ensure field has area attribute
  var intersectingFieldsArea = intersectingFields.map(function(f){return f.set({initFieldArea: f.geometry().area(ee.ErrorMargin(30)).toInt()})});
  
  // Split into small and large fields
  var smallFields = intersectingFieldsArea.filter(ee.Filter.lt("initFieldArea", QQsec_size));
  var largeFields = intersectingFieldsArea.filter(ee.Filter.gte("initFieldArea", QQsec_size));
  
  // Save number of small and large fields for manuscript
  var numSmallFields = ee.Number(smallFields.size());
  var numLargeFields = ee.Number(largeFields.size());
  
  // Further split largeFields by Qsec threshold (e.g., ~0.65 km2)
  var mergeableFields = largeFields.filter(ee.Filter.lt("initFieldArea", Qsec_size));
  var preservedFields = largeFields.filter(ee.Filter.gte("initFieldArea", Qsec_size));
  
  // Dissolve mergeable large fields by crop type
  var cropTypes = mergeableFields.aggregate_array(cropAttribute).distinct();
  var mergedCropFields = ee.FeatureCollection(cropTypes.map(function(cropType) {
    var group = mergeableFields.filter(ee.Filter.eq(cropAttribute, cropType));
    var dissolved = group
      .map(function(f) { return f.setGeometry(f.geometry()); }) // .buffer(1)
      .union();
    return ee.FeatureCollection(ee.Feature(dissolved.first()).geometry().geometries()
      .map(function(geom) {
        var setDict = ee.Dictionary().set(cropAttribute, cropType);
        return ee.Feature(ee.Geometry(geom)).set(setDict); // .buffer(-1).simplify(ee.ErrorMargin(10))
      }));
  })).flatten();
  
  // Re-merge large fields
  var allLargeFields = mergedCropFields.merge(preservedFields);
  
  // Sort large fields by area (attempting to merge small fields with large fields to approach a size of central tendency)
  var allLargeFieldsOrdered = allLargeFields.map(function(f){
    return f.set('sort_area', f.geometry().area(ee.ErrorMargin(30)).toInt());}).sort('sort_area');

  // Dissolve small fields only if they exist
  var dissolvedSmallList = ee.List(
    ee.Algorithms.If(
      smallFields.size().gt(0),
      smallFields
        .map(function(f) { return f.setGeometry(f.geometry()); }) // .buffer(1)
        .union(ee.ErrorMargin(10))                                // dissolved boundaries
        .first()                                                  // single feature
        .geometry()
        .geometries()                                             // explode multipolygon
        .map(function(g) {
          return ee.Feature(ee.Geometry(g));
        }),
      ee.List([]) // If not small fields, return an empty geometry
    )
  );
  
  // Set dissolved smallfields fc, ensure feature collection
  var dissolvedSmallFields = ee.FeatureCollection(dissolvedSmallList);
  
  // // Dissolve small fields with eachother
  // var dissolvedSmallFields = ee.FeatureCollection(smallFields
  //   .map(function(f){return f.setGeometry(f.geometry()); }) // .buffer(1) // Small buffer 
  //   .union(ee.ErrorMargin(10)) // Dissovled boundaries
  //   .first().geometry().geometries() // Explode union geometry
  //   .map(function(g){return ee.Feature(ee.Geometry(g)); })); //.buffer(-1).simplify(ee.ErrorMargin(10)) // Transform to features and unbuffer
  //   //.map(function(f){return f.set({fieldID: f.id()});}); // Set an ID
  // var dissolvedSmallList = dissolvedSmallFields.toList(dissolvedSmallFields.size());
  
  // Add an index interatively, rather than using system:index (.id()) -- Solves "filter too complex" issue
  var dissolvedSmallFieldsID = ee.FeatureCollection(
    ee.List.sequence(0, dissolvedSmallList.size().subtract(1)).map(function(i) {
      var f = ee.Feature(dissolvedSmallList.get(i));
      return f.set({'fieldID': i});
    }));
    
  // Initialize final fields as empty list to store both new large fields and leftover small fields
  var initial = {
    updated: ee.List([]),  // holds final large fields
    remainingSmalls: dissolvedSmallFieldsID
  };
  
  // Define function to merge smalls into each large field
  var mergeSmallsIntoLarge = function(feature, state) {
    state = ee.Dictionary(state);
    var remainingSmalls = ee.FeatureCollection(state.get('remainingSmalls'));
    var updated = ee.List(state.get('updated'));
  
    // Find small fields that touch this large field
    var touchingSmalls = remainingSmalls.filterBounds(feature.geometry());
  
    // If there are no smalls, just add the original
    var hasSmalls = touchingSmalls.size().gt(0);
    var newGeom = ee.Algorithms.If(
      hasSmalls,
      feature.geometry().union(touchingSmalls.geometry(), ee.ErrorMargin(10)), // .simplify(ee.ErrorMargin(10)) 
      feature.geometry());
    var updatedFeature = ee.Algorithms.If(
      hasSmalls,
      ee.Feature(ee.Geometry(newGeom)).copyProperties(feature),
      feature);
  
    // Remove merged smalls from remaining pool
    var mergedIDs = touchingSmalls.aggregate_array('fieldID');
    var updatedRemaining = remainingSmalls.filter(ee.Filter.inList('fieldID', mergedIDs).not());
  
    return ee.Dictionary({
      updated: updated.add(updatedFeature),
      remainingSmalls: updatedRemaining
    });
  };
  
  // Run the iteration
  var result = allLargeFieldsOrdered.iterate(mergeSmallsIntoLarge, initial);
  
  // Extract result pieces
  var resultDict = ee.Dictionary(result);
  var updatedList = ee.List(resultDict.get('updated')); 
  var remainingSmalls = ee.FeatureCollection(resultDict.get('remainingSmalls'));
  
  // Convert list of features to FeatureCollection here and ombine remaining smalls with updated large fields
  var fieldsFinal = ee.FeatureCollection(updatedList).merge(remainingSmalls);

  // IF fieldFinal is empty, return PLSS Qsec boundary and set a fieldPresent identifer to 0
  var fieldsFinalCheck = ee.FeatureCollection(
    ee.Algorithms.If(
      fieldsFinal.size().gt(0),
      fieldsFinal.map(function(f){return f.set({fieldsPresent: 1});}), // we have fields,  tag them and return
      ee.FeatureCollection([ee.Feature(plssBoundary).set({fieldsPresent: 0})])  // no fields, return plss Qsec as a single feature
    )
  );
  
  // Since we checked adjacent and internal fields, ensure field output is only the co-located field
  var fieldsFinalAOI = fieldsFinalCheck.filterBounds(aoi);
  
  // If PLSS boundary exists, clip fields to PLSS boundary and add a field area column
  var fieldsFinalOut = ee.FeatureCollection(
    ee.Algorithms.If(plssBoundary.area(ee.ErrorMargin(1)).gt(0),
    fieldsFinalAOI.map(function(f) {
      // Get clipped geometry
      var clippedGeom = f.geometry().intersection(plssBoundary, ee.ErrorMargin(1));
      // Recompute area
      return f.setGeometry(clippedGeom).set({fldArea: clippedGeom.area(ee.ErrorMargin(1)).toInt() });
    // If no plss boundary, set field boudnary to existing shape
    }), fieldsFinalAOI));
  
  // Return the final field product
  return fieldsFinalOut;
};


//####################################\\
////  Get Most Recent NAIP Imagery  \\\\ ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
//####################################\\

/*
-- Notes --
*/

// Function to get the most recent image per location without reprojection
function getMostRecentImageNAIP(collection) {
  // Get band names
  var bandNames = collection.first().bandNames();
  // Get NAIP id's. These are in the form: 'm_2909522_se_15_060_20201130'
  var longIDs = collection.aggregate_array('system:index').distinct();
  // For each id in uniqueIDs, drop the last 9 characters "_20201130"
  var uniqueIDs = longIDs.map(function(id){return ee.String(id).slice(0, 16);});
  // Within each non-dated index, get the most recent image
  var recentImages = uniqueIDs.map(function(id) {
    var imgs = collection.filter(ee.Filter.stringContains('system:index', id));
    var img = imgs.limit(1, 'system:time_start', false).first();  // Limit to first image when sorted by date // .sort('system:time_start', false) // Sort descending to get the most recent
    return ee.Image(img.copyProperties(imgs.first(), imgs.first().propertyNames()));
  });
  // Ensure the imageCollection is not null, handle the case where no image is found (set an empty image)
  var imgRecent = ee.Image(ee.Algorithms.If(
    recentImages.size().gt(0),
    ee.ImageCollection(recentImages).select(bandNames).median(), // select for desired bandnames and get median (output: Image)
    ee.Image([]))); // (output: Image)
  // // Get projection info
  // var origProj = imgColRecent.first().projection().getInfo(); // NAIP.filterBounds(aoi).limit(1, 'system:time_start', false).first().projection().atScale(scale).getInfo()
  // var origCRS = origProj.crs; var origTransform = origProj.transform;
  // Return a non-mosaiced image that retains native resolution (mosaicing reduces resolution and reprojects to WGS84)
  return imgRecent; //.set({origCRS: origCRS, origTransform: origTransform}); 
}

//############################################\\
////  Landsat 5, 7, 8, and 9 Harmonization  \\\\ ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
//############################################\\

/*
-- Notes --
To use multi-sensor imagery from Landsat Collection 1 (C1), a cross-sensor adjustment (harmonization) was requried using 
defined band coefficients from Roy et al., 2016. However, according to the best available knowledge on Collection 2, 
"there seems to be a general consensus among influential Landsat users that no correction is needed for Collection 2, Level
2 (surface reflectance) data" (https://developers.google.com/earth-engine/faq#is_cross-sensor_landsat_surface_reflectance_harmonization_needed).
Therefore, we no longer harmonize with band coefficients like those from Roy et al., 2016. 
*/

// Get all Landsat 5, 7, and 8 ~~~~~~~~~~~~~~~

// Landsat 9 OLI/TIRS, 8 OLI, 7 ETM, and 5 TM (Surface Reflectance -- )
var olitirsCol_temp = ee.ImageCollection("LANDSAT/LC09/C02/T1_L2");
var oliCol_temp = ee.ImageCollection("LANDSAT/LC08/C02/T1_L2");
var etmCol_temp = ee.ImageCollection("LANDSAT/LE07/C02/T1_L2");
var tmCol_temp = ee.ImageCollection("LANDSAT/LT05/C02/T1_L2");

// Set Preparation Functions ~~~~~~~~~~~~~~~~~~

// Function to scale optical bands -- from https://www.usgs.gov/faqs/how-do-i-use-a-scale-factor-landsat-level-2-science-products
function scaleCollection2Optical(img){
  return img.multiply(0.0000275).add(-0.2);
}

// Function to get and rename bands of interest from OLI.
function renameOliTirs(img) {
  return img.select(
      ['SR_B2', 'SR_B3', 'SR_B4', 'SR_B5', 'SR_B6', 'SR_B7', 'QA_PIXEL'],
      ['Blue', 'Green', 'Red', 'NIR', 'SWIR1', 'SWIR2', 'pixel_qa']);
}

// Function to get and rename bands of interest from OLI.
function renameOli(img) {
  return img.select(
      ['SR_B2', 'SR_B3', 'SR_B4', 'SR_B5', 'SR_B6', 'SR_B7', 'QA_PIXEL'],
      ['Blue', 'Green', 'Red', 'NIR', 'SWIR1', 'SWIR2', 'pixel_qa']);
}

// Function to get and rename bands of interest from ETM+.
function renameEtm(img) {
  return img.select(
      ['SR_B1', 'SR_B2', 'SR_B3', 'SR_B4', 'SR_B5', 'SR_B7', 'QA_PIXEL'],
      ['Blue', 'Green', 'Red', 'NIR', 'SWIR1', 'SWIR2', 'pixel_qa']);
}

// Function to create mask for clouds
function makeFmaskMask(img) {
  var cloudShadowBitMask = 1 << 3;
  var cloudsBitMask = 1 << 5;
  var qa = img.select('pixel_qa');
  return qa.bitwiseAnd(cloudShadowBitMask).eq(0)
           .and(qa.bitwiseAnd(cloudsBitMask).eq(0));
}

// Function to create mask for bad pixels
function makeBadValueMask(image) {
  var minValue = 7273;
  var minValueScaled = 0;
  var maxValue = 43636;
  var maxValueScaled = 1;
  var bands = ['Blue','Green','Red','NIR','SWIR1','SWIR2'];
  var minMask = image.select(bands).reduce(ee.Reducer.min()).gte(minValue);
  var maxMask = image.select(bands).reduce(ee.Reducer.max()).lte(maxValue);
  return minMask.and(maxMask);
}

// Set Harmonization Functions ~~~~~~~~~~~~~~~~~~~

// Define function to prepare OLI/TIRS images.
function prepOliTirs(img) {
  var orig = img;
  img = renameOliTirs(img);
  var m = makeFmaskMask(img).and(makeBadValueMask(img));
  img = img.updateMask(m);
  img = scaleCollection2Optical(img); 
  return ee.Image(img.copyProperties(orig, ['system:time_start']));
}

// Define function to prepare OLI images.
function prepOli(img) {
  var orig = img;
  img = renameOli(img);
  var m = makeFmaskMask(img).and(makeBadValueMask(img));
  img = img.updateMask(m);
  img = scaleCollection2Optical(img); 
  return ee.Image(img.copyProperties(orig, ['system:time_start']));
}

// Define function to prepare ETM+ images.
function prepEtm(img) {
  var orig = img;
  img = renameEtm(img);
  var m = makeFmaskMask(img).and(makeBadValueMask(img));
  img = img.updateMask(m);
  img = scaleCollection2Optical(img); 
  return ee.Image(img.copyProperties(orig, ['system:time_start']));
}

// Create function with filtering criteria ~~~~~~~~~~~~~~~~~~~

// Harmonization function pull
var ls_harmonize_fromSR = function(aoi, dateRange){
  // Set image bounds
  var imgBounds = aoi.bounds(ee.ErrorMargin(10))
  
  // Landsat 9 OLI/TIRS, 8 OLI, 7 ETM, and 5 TM
  var olitirsCol = olitirsCol_temp.filterDate(dateRange).filterBounds(imgBounds).map(prepOliTirs);
  var oliCol = oliCol_temp.filterDate(dateRange).filterBounds(imgBounds).map(prepOli);
  var etmCol = etmCol_temp.filterDate(dateRange).filterBounds(imgBounds).map(prepEtm);
  var tmCol = tmCol_temp.filterDate(dateRange).filterBounds(imgBounds).map(prepEtm);
  
  // Merge the collections.
  var col_merge = ee.ImageCollection(olitirsCol.merge(oliCol).merge(etmCol).merge(tmCol));
  
  // Now, to reduce computational requirements, clip each image by aoi with a little buffer
  var col = col_merge//.map(function(img){return img.clip(aoi)});
  return col;
};

// Example
//var lsExamp = ls_harmonize(ee.DateRange('2019-01-01', '2019-12-31'), geometry).select(['GCVI']); var uswtdb = ee.FeatureCollection("users/stidjaco/uswtdb_v6_1_20231128"); 
//Map.addLayer(lsExamp.median(), {min: 0, max: 2.5, palette: ['yellow','green']}, "LS Median"); Map.addLayer(lsExamp.mean(), {min: 0, max: 2.5, palette: ['yellow','green']}, "LS Mean"); 
//Map.addLayer(uswtdb.filterBounds(geometry), {}, "US Wind Turbine Database Centroids"); Map.centerObject(geometry, 14);

//############################################\\
////    Landsat 5, 7, 8, and 9 Composites   \\\\ ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
//############################################\\

/*
-- Notes --
*/

// Landsat C2 composites (from: https://jstnbraaten.medium.com/ditch-the-boilerplate-use-earth-engines-on-the-fly-landsat-composites-60fb9abe707c) 
// Note: Annual, 32 day, and 8 day composites exist for 7-band and 5 indices: BAI, EVI, NBR, NDVI, NDWI
var lsAnnual_base = 'LANDSAT/COMPOSITES/C02/T1_L2_ANNUAL';
var ls32Day_base  = 'LANDSAT/COMPOSITES/C02/T1_L2_32DAY';
var ls8Day_base   = 'LANDSAT/COMPOSITES/C02/T1_L2_8DAY';

// Function to get and rename bands of interest 
function renameComposite(img) {
  return img.select(
      ['blue', 'green', 'red', 'nir', 'swir1', 'swir2', 'thermal'],
      ['Blue', 'Green', 'Red', 'NIR', 'SWIR1', 'SWIR2', 'Thermal']);
}

// Resolve base composite path from period
function compositeBase(period) {
  period = String(period).toLowerCase();
  return (period === '8day')  ? ls8Day_base :
         (period === '32day') ? ls32Day_base :
                                lsAnnual_base;
}

// Harmonized pull from Landsat composite collections
// period: 'annual' | '32day' | '8day'
var ls_harmonize_fromComposite = function(aoi, dateRange, period) {
  // Set image bounds
  var imgBounds = aoi.bounds(ee.ErrorMargin(10))

  // Resolve the composite asset path
  var baseId = compositeBase(period);

  // Load, filter, and standardize bands
  return ee.ImageCollection(baseId)
    .filterDate(dateRange)
    .filterBounds(imgBounds)
    .map(renameComposite)
    .map(function(img){return img.clip(imgBounds)}); // for these composites, filterBounds returns a non-bounded image (all one scene)
};

// // Example
// var lsExamp = ls_harmonize_fromComposite(geometry, ee.DateRange('2019-01-01', '2019-12-31'), 'annual').select(['Thermal']);// var uswtdb = ee.FeatureCollection("users/stidjaco/uswtdb_v6_1_20231128"); 
// Map.addLayer(lsExamp, {min: 300, max: 325}, "LS Median"); 

//#################################################\\
////  Get Harmonized Landsat + Sentinel Product  \\\\ ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
//#################################################\\

/*
-- Notes --
Oringal HLS Paper: https://www.sciencedirect.com/science/article/pii/S0034425718304139#s0025
*/

// Call Existing HLS

// Get Harmonized LS+S2 function
var HLS = ee.ImageCollection("NASA/HLS/HLSL30/v002"); 

// Preparation and Spectral Index Functions 
// Rescale imagery -- In theory, HLS ranges from 0 to 1. However, due possibly to Atmospheric Correction, BRDF Normalization, and/or Bandpass Adjustment, true optical values range from ~ -0.43 to 1.71 
function scaleCollection(img){
  var bitMax = 65535; // 16-bit
  var scaler = 0.0001; // Scaler from HLS helper guide
  var minHLS = -0.45; 
  var maxHLS = 1.75; 
  var hlsBandRange = ee.Number(maxHLS).subtract(minHLS);
  return img.select(["B1","B2","B3","B4","B5","B6","B7","B9"]);//.add(minHLS).divide(hlsBandRange).multiply(bitMax).toInt();
}

// Grab imagery and add bands of interest -- Harmonized
function getIndices(image){return image
    // Add GCVI
    .addBands(image.expression('NIR/G-1', { 
       'G': image.select('B3'),
       'NIR': image.select('B5')}).rename('GCVI'))
    // Add Bloom Index
    .addBands(image.expression('( (R+G+B) / ((G/B) * (R-B+e)) )', { 
       'B': image.select('B2'),
       'R': image.select('B4'),
       'G': image.select('B3'),
       'e': ee.Number(1)}).rename('EBI'))}; // e is max band value, we chose to go with 0 to 65535 (16-bit)

// Create function with filtering criteria
// Harmonization function pull
var hls_harmonize = function(dateRange, aoi){
  // Apply filters and functions
  var colFilter = HLS
    .filterDate(dateRange)
    .filterBounds(aoi)
    .filter(ee.Filter.lt('CLOUD_COVERAGE', 30))
    //.map(scaleCollection)
    .map(getIndices)
    .select(['GCVI', 'EBI']);
    
  // Now, to reduce computational requirements, clip each image by aoi with a little buffer
  var col = colFilter.map(function(img){return img.clip(aoi)});
  
  return col;
};

// // Example
// var hlsExamp = hls_harmonize(ee.DateRange('2019-01-01', '2019-12-31'), geometry); Map.centerObject(geometry, 16);
// Map.addLayer(hlsExamp.median().select("EBI"), {min: 0, max: 1, palette: ['yellow','green']}, "HLS Median"); 
// Map.addLayer(hlsExamp.median().select("GCVI"), {min: 0, max: 5, palette: ['yellow','green']}, "HLS Median"); 


//############################################\\
////        Sentinel-2 Acquisition          \\\\ ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
//############################################\\

/*
-- Notes --

*/

// Call asset
var s2 = ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")

// Function to mask clouds using the Sentinel-2 QA band.
function maskS2clouds(image) {
  var qa = image.select('QA60');

  // Bits 10 and 11 are clouds and cirrus, respectively.
  var cloudBitMask = 1 << 10;
  var cirrusBitMask = 1 << 11;

  // Both flags should be set to zero, indicating clear conditions.
  var mask = qa.bitwiseAnd(cloudBitMask).eq(0)
      .and(qa.bitwiseAnd(cirrusBitMask).eq(0));

  return image.updateMask(mask).divide(10000);
}

// Function to get and rename bands of interest 
function renameS2(img) {
  return img.select(
      ['B1', 'B2', 'B3', 'B4', 'B5', 'B6', 'B7', 'B8', 'B8A', 'B9', 'B11', 'B12'],
      ['Aerosols', 'Blue', 'Green', 'Red', 'RedEdge1', 'RedEdge2', 'RedEdge3', 'NIR', 'RedEdge4', 'WaterVapor', 'SWIR1', 'SWIR2']);
}

// Define function to prepare s2
function prepS2(img) {
  var orig = img;
  img = maskS2clouds(img);
  img = renameS2(img);
  return ee.Image(img.copyProperties(orig, ['system:time_start']));
}

// Harmonization function pull
var s2_harmonize = function(aoi, dateRange){
  // Set image bounds
  var imgBounds = aoi.bounds(ee.ErrorMargin(10));
  
  // Load Sentinel-2 TOA reflectance data.
  var col = s2
    .filterDate(dateRange)
    .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 20))
    .map(prepS2)
    .filterBounds(imgBounds);
  return col;
};

// Example
//var lsExamp = ls_harmonize(ee.DateRange('2019-01-01', '2019-12-31'), geometry).select(['GCVI']); var uswtdb = ee.FeatureCollection("users/stidjaco/uswtdb_v6_1_20231128"); 
//Map.addLayer(lsExamp.median(), {min: 0, max: 2.5, palette: ['yellow','green']}, "LS Median"); Map.addLayer(lsExamp.mean(), {min: 0, max: 2.5, palette: ['yellow','green']}, "LS Mean"); 
//Map.addLayer(uswtdb.filterBounds(geometry), {}, "US Wind Turbine Database Centroids"); Map.centerObject(geometry, 14);


//#################################################\\
////             Get Spectral Indices            \\\\ ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
//#################################################\\

/*
-- Notes --
Returns a single-band image of selected band OR a specificed spectral index from any image collection. Conditionals enhance efficiency over computing all indices. Check for assumptions about specific indices (like max band range).

Requires band nomenclature: 
- All Collections: 'Blue', 'Green', 'Red', 'NIR', 'SWIR1', 'SWIR2'
- Landsat 8/9: 'Thermal'
- Sentinel-2: 'Aerosols', 'RedEdge1', 'RedEdge2', 'RedEdge3', 'RedEdge4'
*/

function getSpectralIndexBand(img, bandName) {
  
  // ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ Normalized Difference
  
  // Compute Normalized Difference Vegetation Index (NDVI)
  if (bandName === 'NDVI') {
    var ndvi = img.normalizedDifference(['NIR', 'Red']);
    return ndvi.rename('NDVI').copyProperties(img, ['system:time_start']);  } 

  // Compute Normalized Difference Wettness Index (NDWI)
  if (bandName === 'NDWI') {
    var ndwi = img.normalizedDifference(['Green', 'NIR']);
    return ndwi.rename('NDWI').copyProperties(img, ['system:time_start']);  } 
    
  // Compute Normalized Difference Moisture Index (NDMI)
  if (bandName === 'NDMI') {
    var ndmi = img.normalizedDifference(['NIR', 'SWIR1']);
    return ndmi.rename('NDMI').copyProperties(img, ['system:time_start']);  } 
  
  // Compute Normalized Difference Moisture Index (NDMI)
  if (bandName === 'NBR') {
    var nbr = img.normalizedDifference(['NIR', 'SWIR2']);
    return nbr.rename('NBR').copyProperties(img, ['system:time_start']);  } 
    
  // ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ Custom Expression

  // Compute Normalized Difference Photovoltaic Index (NDPVI)
  if (bandName === 'NDPVI') {
    var ndpvi = img.expression('(0.5*B-N)/(0.5*B+N)', 
      {'B': img.select('Blue'), 'N': img.select('NIR')});
    return ndpvi.rename('NDPVI').copyProperties(img, ['system:time_start']); } 
  
  // Compute Normalized Blue Deviation (NBD)
  if (bandName === 'NBD') {
    var nbd = img.expression('(B-((R+G)/2))/(B+((R+G)/2))', 
      {'B': img.select('Blue'), 'G': img.select('Green'), 'R': img.select('Red')});
    return nbd.rename('NBD').copyProperties(img, ['system:time_start']);  } 
  
  // Compute Brightness (BR) -- 3 band
  if (bandName === 'BR') {
    var br = img.expression('(R+G+B)/3', // Removed NIR
      {'B': img.select('Blue'), 'G': img.select('Green'), 'R': img.select('Red'), 'N': img.select('NIR')});
    return br.rename('BR').copyProperties(img, ['system:time_start']);  } 
  
  // Compute Enhanced Vegetation Index (EVI)
  if (bandName === 'EVI') {
    var evi = img.expression('2.5 * ((N - R) / (N + 6 * R - 7.5 * B + 1))',
      {'B': img.select('Blue'), 'R': img.select('Red'), 'N': img.select('NIR')});
    return evi.rename('EVI').copyProperties(img, ['system:time_start']);  } 
    
  // Compute Near Infrared Reflectance of Vegeatation (NIRv) -- Badgley et al., 2017 (https://doi.org/10.1126/sciadv.1602244), Zhang et al., 2022 (https://doi.org/10.1016/j.agrformet.2022.108819)
  if (bandName === 'NIRv') {
    var nirv = img.expression('((N-R)/(N+R) * N)',
      {'R': img.select('Red'), 'N': img.select('NIR')});
    return nirv.rename('NIRv').copyProperties(img, ['system:time_start']);  } 
    
  // Compute Green Chlorophyll Vegetation Index (GCVI)
  if (bandName === 'GCVI') {
    var gcvi = img.expression('(N/G)-1',
      {'G': img.select('Green'), 'N': img.select('NIR')});
    return gcvi.rename('GCVI').copyProperties(img, ['system:time_start']);  } 
    
  // Compute Modified Soil-Adjusted Vegetation Index 2 (MSAVI2)
  if (bandName === 'MSAVI2') {
    var msavi2 = img.expression('(2 * N + 1 - sqrt(pow((2 * N + 1), 2) - 8 * (N - R)) ) / 2',
      {'R': img.select('Red'), 'N': img.select('NIR')});
    return msavi2.rename('MSAVI2').copyProperties(img, ['system:time_start']);  } 
  
  // Compute Enhanced Bloom Index (EBI)
  if (bandName === 'EBI') {
    var ebi = img.expression('( (R+G+B) / ((G/B) * (R-B+e)) )',
      {'R': img.select('Red'), 'G': img.select('Green'), 'B': img.select('Blue'), 'e': ee.Number(1)}); // e is max band value
    return ebi.rename('ebi').copyProperties(img, ['system:time_start']);  } 

  // ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ Tasseled Cap Series
    
  // Compute tassled cap brightness, greeness, wetness, and angle
  var tcBands = ['Blue', 'Green', 'Red', 'NIR', 'SWIR1', 'SWIR2'];
  var coeffsB = [0.1348, 0.4566, 0.4933, 0.5337, 0.0613, 0.4914];
  var coeffsG = [-0.1663, -0.2251, -0.3604, 0.8399, -0.0515, -0.2891]; // average OLI/OLI-2 coeffs from https://doi.org/10.1016/j.srs.2025.100353
  var coeffsW = [-0.0659, 0.2566, 0.0672, -0.0233, -0.9508, -0.1440];
  
  // Compute tassled cap brightness
  if (bandName === 'TCB') {
    var tcb = img.select(tcBands).multiply(ee.Image.constant(coeffsB)).reduce(ee.Reducer.sum());
    return tcb.rename('TCB').copyProperties(img, ['system:time_start']);  } 
  
  // Compute tassled cap greeness
  if (bandName === 'TCG') {
    var tcg = img.select(tcBands).multiply(ee.Image.constant(coeffsG)).reduce(ee.Reducer.sum());
    return tcg.rename('TCG').copyProperties(img, ['system:time_start']);  } 
    
  // Compute tassled cap wettness
  if (bandName === 'TCW') {
    var tcw = img.select(tcBands).multiply(ee.Image.constant(coeffsW)).reduce(ee.Reducer.sum());
    return tcw.rename('TCW').copyProperties(img, ['system:time_start']);  } 
  
  // Compute tasseled cap angle
  if (bandName === 'TCA') {
    var tcb = img.select(tcBands).multiply(ee.Image.constant(coeffsB)).reduce(ee.Reducer.sum());
    var tcg = img.select(tcBands).multiply(ee.Image.constant(coeffsG)).reduce(ee.Reducer.sum());
    var eps = ee.Image.constant(1e-6);
    var safeTcb = tcb.where(tcb.abs().lt(eps), eps); // guard against near zero issues of atan function (opposed to atan2)
    var tca = tcg.divide(safeTcb).atan().multiply(180/Math.PI);
    return tca.rename('TCA').copyProperties(img, ['system:time_start']);  } 

  // Select the requested band
  var base = img.select([bandName]);
  return base.copyProperties(img, ['system:time_start']);
  
}

//###################################\\
////   Export functions for use    \\\\ ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
//###################################\\

exports.validateGeometries = validateGeometries;
exports.splitFeatures = splitFeatures;
exports.getMostRecentImageNAIP = getMostRecentImageNAIP;
exports.getColocatedFields = getColocatedFields;
exports.ls_harmonize_fromSR = ls_harmonize_fromSR;
exports.ls_harmonize_fromComposite = ls_harmonize_fromComposite;
exports.hls_harmonize = hls_harmonize;
exports.s2_harmonize = s2_harmonize;
exports.getSpectralIndexBand = getSpectralIndexBand;