//#####################################################################################################################//
/////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
////////////////////////////////////                                                /////////////////////////////////////
////////////////////////////////////  Get Panel Objects from Existing Array Shapes  /////////////////////////////////////
////////////////////////////////////                                                /////////////////////////////////////
/////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
//#####################################################################################################################//

/*
-- Information --
Author: Jacob Stid
Date Created: 07-22-2024
Date Updated: 11-13-2024
Contact: stidjaco@msu.edu (Jacob Stid)

-- Notes --
Prior to running this script, train_LCMAPref and train_LCMAPrnd must be run. 

For refernce for kernel logic and neighborhood based image transformation: https://google-earth-engine.com/Advanced-Image-Processing/Neighborhood-based-Image-Transformation/#google_vignette
*/
 
//######################################\\
///// Subsets for Method Development \\\\\ 
//######################################\\

// Load solar array shape file
//var arrays = ee.FeatureCollection('projects/ee-stidjaco/assets/BigPanel/initialGMSEUS_getPanels'); Map.addLayer(arrays); var arrays = arrays.map(validateGeometries); // var existingArrays = ee.FeatureCollection('projects/ee-stidjaco/assets/BigPanel/existingDatasetArrayShapes'); Map.addLayer(existingArrays)

// Get system index and feature
//var systemIndex = '00000000000000002c6a'; var feature = ee.Feature(arrays.filter(ee.Filter.eq("system:index", systemIndex)).first()); Map.addLayer(ee.ImageCollection('USDA/NAIP/DOQQ').filterDate(2021+'-01-01', 2022+'-12-31').median().clip(feature.geometry().buffer(25))); print("Original Ft info: ", feature); Map.centerObject(feature); Map.addLayer(feature); var numChunks = 1;
//var subArrID = 16441; var feature = ee.Feature(arrays.filter(ee.Filter.eq("subArrID", subArrID)).first());  Map.addLayer(ee.ImageCollection('USDA/NAIP/DOQQ').filterDate(2021+'-01-01', 2022+'-12-31').median().clip(feature.geometry().buffer(25))); Map.centerObject(feature); Map.addLayer(feature); var numChunks = 1

//############################\\
///// Set Export Variables \\\\\ ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ Section 1
//############################\\

// Load solar array shape file
var arrays = ee.FeatureCollection('projects/ee-stidjaco/assets/BigPanel/initialGMSEUS_getPanels'); // Arrays exploded

// Give the run some names
var runName = "geojson121924" ;

/*
Exports in need of rerunning: 
* List subset and error code here
*/

// This is a memory-intense process, often overloding GEE. Subset here by array chunks. Needs to be divisible by subsets. When debugging export errors, start is equivalent to export name 
var subsetMagnitude = 1e4 // Determines total subset number. Base is 1e3, may have to increase to 1e4 if memory still being overloaded by large arrays. If so, adjust start and end accordingly. LIKELY: If computation is timing out, it is because the panel-rows are creating too many vertices for a geojson object to export. Have to manually reexport these as shp files (Lines 733 to 740)
var start = 8200; 
var end = 8300;

// Set steps for arrays subsets (small: <1ha, med: <9ha, lrge: >9ha)
var smallStep = 200;
var medStep = 100;
var lrgeStep = 10;

// Set area limitations
var smallAreaLimit = 2e4; // 20,000 sqm or 2 ha
var medAreaLimit = 1e5; // 100,000 sqm or 10ha. Large will be anything greater than this

//###########################\\
///// Set Model Variables \\\\\
//###########################\\

// Set most recent NAIP year range (two years since NAIP is acquired at state level every two years)
var NAIPstart = '2019'; // really this is 2021, but there is a single array in the dataset where the most recent imagery is 2019 
var NAIPend = '2023'; 

// Set seed
var seed = 15; 

// Set imagery scale
var scale = 0.6 // set as max of most recent imagery (0.3 to 0.6 as of 2024) 

// Island and hole filling threshold and minimum panel area threshold
var islandHoleThresh = 9; // pixels, prevents pixels surrounded by 8 connected alone to be considered (initial filtering)
var minPanelRowArea = 15; // 15m2,
var minPanelRowCount = ee.Number(minPanelRowArea).divide(ee.Number(scale).multiply(scale)).round(); // min panel row area in pixel number

// Set RF and KM model variables
var trainingSampleNum = 2000; 
var numTrees = 200;

// Set a geometrical operation error margin for NAIP imagery 
var naipErrorMargin = ee.ErrorMargin(0.1);

//######################################\\
///// Load and Prepare Training Data \\\\\
//######################################\\

// Current training dataset
var SolIndexTraining = ee.FeatureCollection('projects/ee-stidjaco/assets/BigPanel/TrainingData/SolIndexTraining_5e3_allPanels_lcmapRef'); // GMSEUSPanels+LCMAPref+Glaciers (5,000 samples per class)

// Function to acquire training dataset with desired samples per class
var getSolarTrainingData = function(inTrainData, sampleSize, seed){
  return ee.FeatureCollection(ee.List([0,1,2,3,4,5]).map(function(value){
      var classId = ee.Number(value);
      var classFeatures = SolIndexTraining.filter(ee.Filter.eq('class_name', classId)); // Filter features for the current class
      var featureCount = ee.Number(classFeatures.size()); // Get the count of available features
      var numToSample = ee.Number(sampleSize).min(featureCount); // Sample up to desired sample size of samples or fewer if not enough features
      var sampled = classFeatures.randomColumn({columnName: 'random', seed: seed, distribution: 'UNIFORM'}).sort('random').limit(numToSample); // Sample the features
      return sampled;
  }).flatten()).flatten();
};

// Get desired dataset
var SolIndexTraining = getSolarTrainingData(SolIndexTraining, trainingSampleNum, seed); 

// Select GLCM bands and dist -- savg explanation paper: https://www.sciencedirect.com/science/article/pii/S1569843223003163
var glcmBand1 = "_savg"; 
var glcmBand2 = "_contrast"; 
var glcmBand3 = "_var";
var glcmDist = 1; // 2 if only savg

// Set bands
var rfBands = ["NDPVI", "NBD", "Br", "NDVI", "NDWI"];
var kmBands = ["NDPVI", "NBD", "Br", "NDVI", "NDWI", "NDPVI" + glcmBand1, "NBD" + glcmBand1, "Br" + glcmBand1, "NDVI" + glcmBand1, "NDWI" + glcmBand1];
var emptyBandList = [-1,-1,-1,-1,-1,-1,-1,-1,-1,-1]; // Needs to be the length of all unique bands we are using in BOTH rfBands and kmBands

// Functions to process NAIP
function scaleCollection(image) { // Rescale imagery function
  var scaler = 1 / 255; // NAIP is 8-bit data
  return image.select(["R", "G", "B", "N"]).multiply(scaler); } // 0 to 1 result

// Function to calculate GLCM texture features, ensuring integer input
function getGLCMTexture(image, bandName) {
  // Scale to deal with int32 limitation
  var scaled = image.select(bandName).multiply(255).toInt(); // Scale and convert to integer
  var glcm = scaled.glcmTexture({size: glcmDist}); // , kernel: kernelAll, average: true});
  // Add texture bands of interest (you can modify this as needed)
  return image.addBands(glcm.select([bandName + glcmBand1, bandName + glcmBand2, bandName + glcmBand3]))}
  
// Get Solar Indices
function getIndices(image) { // Grab imagery and add bands of interest
  return image
    // Add Normalized Difference Photovoltaic Index (NDPVI)
    .addBands(image.expression('(0.5*B-NIR)/(0.5*B+NIR)', { 
       'B': image.select('B'),
       'NIR': image.select('N')}).rename('NDPVI'))
    // Add Normalized Blue Deviation (NBD) Index
    .addBands(image.expression('(B-((R+G)/2))/(B+((R+G)/2))', { 
       'R': image.select('R'),
       'G': image.select('G'),
       'B': image.select('B')}).rename('NBD'))
    // Add Brightness (Br)
    .addBands(image.expression('(R+B+G+NIR)/4', { 
       'R': image.select('R'),
       'G': image.select('G'),
       'B': image.select('G'),
       'NIR': image.select('N')}).rename('Br'))
    // Add Normalized Different Water Index (NDWI)
    .addBands(image.normalizedDifference(['G', 'N']).rename('NDWI'))
    // Add Normalized Different Water Index (NDWI)
    .addBands(image.normalizedDifference(['N', 'R']).rename('NDVI')); }

// Get Lat/Long
function getLatLong(image) {
  var coords = ee.Image.pixelLonLat();
  return image.addBands(coords.select('longitude').rename('Long'))
    .addBands(coords.select('latitude').rename('Lat'))}
    
// Prepare NAIP 
function prepNAIP(image) { // Apply prep functions and copy properties 
  var orig = image;
  image = scaleCollection(image);
  image = getIndices(image);
  image = getGLCMTexture(image, 'NDPVI'); // For NDPVI index
  image = getGLCMTexture(image, 'NBD'); // For NBD index
  image = getGLCMTexture(image, 'Br'); // For Br index
  image = getGLCMTexture(image, 'NDVI'); // For NDVI index
  image = getGLCMTexture(image, 'NDWI'); // For NDWI index
  return ee.Image(image.copyProperties(orig, ['system:time_start']));}
  
// Set bands as the combination of rf and km bands
var bands = ee.List(rfBands).cat(ee.List(kmBands)).distinct();

// Call and process NAIP
var NAIP = ee.ImageCollection('USDA/NAIP/DOQQ')
  .filterDate(ee.DateRange(NAIPstart+'-01-01', NAIPend+'-12-31'))
  .map(prepNAIP)
  .select(bands); 

//#######################################################################\\
// Set Functions to Prepare Inputs, Perform RF and KM Models and Export  \\ ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
//#######################################################################\\

// ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ Validate Geometries Function

// Function to check for valid geometries (as polygons/multipolygons) in a feature or featureCollection
function validateGeometries(feature){
  //##################################################\\ 
  ///// Check array geometry for errant geometries \\\\\
  //##################################################\\

  // Before running anything, check for errant geometries: Geometry collections with LineStrings
  var featurePolygon = feature.geometry().geometries().map(function(geometry){
    return ee.Algorithms.If(ee.Geometry(geometry).type().compareTo('Polygon'), null, geometry);}, true); // true is for drop nulls
  
  // Set geometry to MultiPolygon or Polygon based on the content
  var newGeometry = ee.Geometry(ee.Algorithms.If(
    ee.Algorithms.IsEqual(featurePolygon.size(), 1), // Check if the original geometry is a single polygon
    ee.Geometry(ee.List(featurePolygon).get(0)), // If single polygon, return it directly
    ee.Geometry.MultiPolygon(featurePolygon) // Otherwise, return as MultiPolygon
  ));
  
  // Create a new feature with corrected geometries
  var newFeature = ee.Feature(feature.setGeometry(newGeometry));
  
  // Return with a temp area to filter by if desired
  return newFeature.set({tempArea: newFeature.geometry().area(naipErrorMargin)});
}

// ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ Split Feature Function

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
    return ee.Feature(intersection).set('area', intersection.area(naipErrorMargin));
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

// ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ Classify Panels Function


// Function for every array shape, acquire random forest identifying PV panels
function classifyPanels(feature){
  //###################\\ 
  ///// Get Imagery \\\\\
  //###################\\ 
  // Get aoi
  var aoi = feature.geometry(); //.buffer(5,1); // Buffer image classification region and unbuffer later to remove boundary effects
  
  /*
  // Get 2.5 km buffer bounds for image collection filtering
  var listCoords = ee.Array.cat(aoi.centroid(naipErrorMargin).buffer(2500).bounds().coordinates(), 1); // 2.5 km buffer, naip tiles are about 5km
  var xCoords = listCoords.slice(1, 0, 1); 
  var yCoords = listCoords.slice(1, 1, 2);
  var xMin = xCoords.reduce('min', [0]).get([0,0]);
  var xMax = xCoords.reduce('max', [0]).get([0,0]);
  var yMin = yCoords.reduce('min', [0]).get([0,0]);
  var yMax = yCoords.reduce('max', [0]).get([0,0]);
  
  // Select the most recent image from image collection for aoi, this process ensure that images at different dates and flight paths are still included
  // the IF is for if imagery is not available in this location (some regions naip is not available)
  var PV_indices_0 = ee.Image(NAIP.filterBounds(aoi.centroid(1)).limit(1, 'system:time_start', false).first());
  var PV_indices_1 = ee.Image(NAIP.filterBounds(ee.Geometry.Point(xMin, yMin)).limit(1, 'system:time_start', false).first());
  var PV_indices_2 = ee.Image(NAIP.filterBounds(ee.Geometry.Point(xMin, yMax)).limit(1, 'system:time_start', false).first());
  var PV_indices_3 = ee.Image(NAIP.filterBounds(ee.Geometry.Point(xMax, yMin)).limit(1, 'system:time_start', false).first());
  var PV_indices_4 = ee.Image(NAIP.filterBounds(ee.Geometry.Point(xMax, yMax)).limit(1, 'system:time_start', false).first());
  
  // Helper function to get geometry if it exists
  function getGeometryOrNull(image){return ee.Algorithms.If(image, ee.Image(image).geometry(), null);}

  // Collect geometries, filtering out any null geometries
  var geomList = ee.List([getGeometryOrNull(PV_indices_0),getGeometryOrNull(PV_indices_1),getGeometryOrNull(PV_indices_2),getGeometryOrNull(PV_indices_3),getGeometryOrNull(PV_indices_4)
    ]).removeAll([null]);  // Remove null entries from the list
  
  // Check if geomList is empty or has valid geometries
  var PV_indices_geom = ee.Geometry(ee.Algorithms.If(geomList.length().gt(0), ee.Geometry.MultiPolygon(geomList).dissolve(), null));

  // Check if the dissolved geometry intersects with AOI, only if PV_indices_geom exists
  var overlaps = ee.Algorithms.If(PV_indices_geom, ee.Geometry(PV_indices_geom).intersects(aoi, ee.ErrorMargin(1)), false);
  
  // Conditional to create PV_indices only if there’s an overlap
  var emptyBandList = [-1,-1,-1,-1,-1,-1,-1,-1,-1,-1];
  var PV_indices1 = ee.Image(ee.Algorithms.If(overlaps, ee.ImageCollection([PV_indices_0, PV_indices_1, PV_indices_2, PV_indices_3, PV_indices_4]).mosaic().clip(aoi), 
    ee.Image(emptyBandList).rename(bands).clip(aoi)));
  */
  
  // Get band names
  var bandNames = NAIP.first().bandNames();
  
  // Filter the NAIP collection to the area of interest (feature)
  var mostRecent = NAIP
    .filterBounds(aoi)
    .map(function(image){return image.addBands(image.metadata('system:time_start').rename('time'));})
    .qualityMosaic('time')//.sort('system:time_start', false).limit(1).first()
    
  // Ensure the image is not null, handle the case where no image is found
  var PV_indices = ee.Image(ee.Algorithms.If(
    mostRecent.bandNames().size().gt(0), // If the image exists
    mostRecent.select(bandNames).unmask(-1).clip(aoi), //.rename(bandNames), // Save mostRecent, fill empty image space with a null classification value for all bands, clip to aoi, and rename to original names
    ee.Image.constant(emptyBandList).rename(bandNames).unmask(-1).clip(aoi))) // Create a null image if none is present

  //############################\\ 
  ///// Get RF Model Results \\\\\ -- c-Si: PV or Snow/Ice, csp: PV, Snow/Ice, thin-film (CdTe): PV or Water
  //############################\\ 
  
  // Get PV type (changes class considerations): c-Si = PV, thin-film = water, csp = PV and Water
  var pvType = ee.List([feature.get('modType')]); 
  var thinFilm = ee.Number(pvType.indexOf('thin-film')).gt(-1); // 0 if not thin film, 1 if thin-film
  var csp = ee.Number(pvType.indexOf('csp')).gt(-1); // 0 if not csp, 1 if csp

  // Set class values
  var solar = 0;
  var snowIce = 5; 
  var water = 4;
  
  // Train a random forest classifier from the training sample. Use multiprobabitliy confidenc output
  var classClassifier = ee.Classifier.smileRandomForest(numTrees).setOutputMode('CLASSIFICATION').train({ // Output mode set to class of greatest probability across trees
    features: SolIndexTraining,
    classProperty: 'class_name',
    inputProperties: rfBands
  });
  
  // Apply RF class classifier: Conditionally mask based on PV type (thin-film is spectrally similar to water, we trained on crystalline silicon modules)
  var resultRFclassTemp = PV_indices.classify(classClassifier); //Map.addLayer(resultRFclass, {min: 0, max: 8})
  var resultRFclass = ee.Image(ee.Algorithms.If(thinFilm.eq(1), 
    resultRFclassTemp.eq(water), // Thin-film is class Water
    ee.Algorithms.If(csp.eq(1), 
      resultRFclassTemp.eq(solar).or(resultRFclassTemp.eq(snowIce)), // CSP is class PV, Water, or Snow/Ice // .or(resultRFclassTemp.eq(water))
      resultRFclassTemp.eq(solar)))); // PV is class PV  -- old method: .or(resultRFclassTemp.eq(snowIce)) // or snow/ice
  
  /*
  // Train a random forest classifier from the training sample. Use multiprobability confidence output
  var confidenceClassifier = ee.Classifier.smileRandomForest(numTrees).setOutputMode('MULTIPROBABILITY').train({ // Output mode set to an array of probabilities that each class is correct ordered by classes seen
    features: SolIndexTraining,
    classProperty: 'class_name',
    inputProperties: rfBands
  });
  
  // Apply RF Confidence classifier: PV is array index '0' of 9 (8 LCMAP Classes after).
  var resultRFconfTemp = PV_indices.classify(confidenceClassifier); // Result is confidence map from 0 to 1.
  var resultRFconf = ee.Image(ee.Algorithms.If(thinFilm.eq(1), 
    resultRFconfTemp.arrayGet([solar]).max(resultRFconfTemp.arrayGet([water])), // Thin-film is considered class 0 or 5
    ee.Algorithms.If(csp.eq(1), 
      resultRFconfTemp.arrayGet([solar]).max(resultRFconfTemp.arrayGet([snowIce])), // CSP is the max confidence of class 0 or 5 // .max(resultRFconfTemp.arrayGet([water]))
      resultRFconfTemp.arrayGet([solar])))); // Default PV is class 0 --  .max(resultRFconfTemp.arrayGet([snowIce])) ice
  */
  
  //#########################\\ 
  /// Get SNIC Segmentation \\\
  //#########################\\ 
  
  // SNIC operations were modified from: https://google-earth-engine.com/Advanced-Image-Processing/Object-based-Image-Analysis/
  // SNIC Segmentation function to set seeds and run SNIC
  var getSNIC = function(imageOriginal, SuperPixelSize, Compactness, Connectivity, NeighborhoodSize, SeedShape){
    // Set SNIC seeds
    var theSeeds = ee.Algorithms.Image.Segmentation.seedGrid(SuperPixelSize, SeedShape);
    
    // Call SNIC algorithm and apply variables
    var snic2 = ee.Algorithms.Image.Segmentation.SNIC({
      image: imageOriginal,
      size: SuperPixelSize,
      compactness: Compactness,
      connectivity: Connectivity,
      neighborhoodSize: NeighborhoodSize,
      seeds: theSeeds});
      
    // Add seeds to the final image and rename bands
    var theStack = snic2.addBands(theSeeds);
    var bandNames = theStack.bandNames();
    var newBandNames = bandNames.map(function(bandName){
      return ee.String(bandName).replace('_mean', ''); });
    var finalStack = theStack.rename(newBandNames);  
    return finalStack;
  };
  
  // SNIC Parameters
  var SNIC_Image = PV_indices;
  var SNIC_SuperPixelSize = 2; 
  var SNIC_Compactness = 0;
  var SNIC_Connectivity = 4;
  var SNIC_SeedShape = 'square';
  var SNIC_NeighborhoodSize = 6 * SNIC_SuperPixelSize;
  
  // Apply SNIC segmentation and get cluster mean values 
  var SNIC_MultiBandedResults = getSNIC(
    SNIC_Image,
    SNIC_SuperPixelSize,
    SNIC_Compactness,
    SNIC_Connectivity,
    SNIC_NeighborhoodSize,
    SNIC_SeedShape);
    
  // Select only bands of interest (result is the mean value within the spatial cluster)
  var snicClusterMeans = SNIC_MultiBandedResults.select(kmBands)//.addBands(resultRFconf);
  
  // Generate new random training dataset that is array specific
  var arraySamples = snicClusterMeans.sample({
    region: aoi,
    scale: scale, // Set scale to match your data resolution
    numPixels: 1000, // Number of random points to sample
    seed: seed, // Seed for reproducibility
    geometries: true // Include geometries to allow visualization and further use
  });

  /*
  // Instantiate the Kmeans clusterer and train it.
  var clusterer = ee.Clusterer.wekaKMeans({
    nClusters: numClusters,
    init: 0,
    canopies: false,
    maxCandidates: 100,
    periodicPruning: 10000,
    minDensity: 2,
    t1: -1.5,
    t2: -1,
    distanceFunction: "Euclidean",
    maxIterations: null,
    preserveOrder: false,
    fast: true,
    seed: seed,
  }).train({
    features: arraySamples,
    inputProperties: ee.List(kmBands)//.cat(['classification'])
  });
  */
  
  // Instantiate the Xmeans clusterer and train it.
  var clusterer = ee.Clusterer.wekaXMeans({
    minClusters: 2, // at minimum, solar and non-solar
    maxClusters: 4, // allows for variation in solar and/or groundcover, but not enough to increase confusion
    maxIterations: 3,
    maxKMeans: 1000,
    maxForChildren: 1000,
    useKD: false,
    cutoffFactor: 0,
    distanceFunction: "Euclidean",
    seed: seed,
  }).train({
    features: arraySamples,
    inputProperties: ee.List(kmBands)//.cat(['classification'])
  });
  
  // Cluster the input using the trained clusterer.
  var resultClusters = snicClusterMeans.cluster(clusterer); 

  //#############################################\\ 
  ///// Get Clusters with Majority Vote Solar \\\\\ 
  //#############################################\\
  
  // For each cluster, get the proportional area classified as solar from resultRFclass, and select majority solar classes (>50%)

  // Get the total pixel count in each cluster
  var totalCountsDict = ee.Dictionary(
    resultClusters.reduceRegion({
      reducer: ee.Reducer.frequencyHistogram(),
      geometry: aoi,
      scale: scale,
      maxPixels: 1e13
    }).get('cluster'));
  
  // Get the total pixel count in each cluster that is classified by RF as solar
  var countsSolarDict = ee.Dictionary(
    resultClusters.updateMask(resultRFclass.eq(1)).reduceRegion({
      reducer: ee.Reducer.frequencyHistogram(),
      geometry: aoi,
      scale: scale,
      maxPixels: 1e13
    }).get('cluster'));

  // Calculate proportional solar cluster area
  var proportionsDict = totalCountsDict.keys().map(function(clusterId){
    clusterId = ee.String(clusterId);
    var total = ee.Number(totalCountsDict.get(clusterId));
    var count1 = ee.Number(countsSolarDict.get(clusterId, 0)); // Defaults to 0 if not present
    var proportion = count1.divide(total).multiply(1e4).toInt().divide(1e4);
    return [clusterId, proportion];  });

  // Convert the list of pairs into a dictionary
  var proportionsDict = ee.Dictionary(proportionsDict.flatten());

  // Get lists of cluster IDs and their corresponding proportions
  var clusterIdsList = proportionsDict.keys().map(ee.Number.parse);
  var proportionsList = clusterIdsList.map(function(clusterId){
    return ee.Number(proportionsDict.get(clusterId)); });

  // Remap cluster IDs in resultClusters to their proportions
  var proportionImage = resultClusters.remap(clusterIdsList, proportionsList);
  
  // Get clusters with greater than 50% solar agreement
  var threshold = 0.50; 
  var resultThresh = proportionImage.gt(threshold); 
  
  // Remove islands
  var result_connected = resultThresh.selfMask().connectedPixelCount({maxSize: minPanelRowCount, eightConnected: true});
  var resultIslands = resultThresh.updateMask(result_connected.gte(minPanelRowCount)).clip(aoi);

  // Fill gaps
  var gapFill = resultIslands.unmask(-9999).eq(-9999).connectedPixelCount({maxSize: minPanelRowCount, eightConnected: true}).lt(islandHoleThresh);
  var resultGaps = gapFill.updateMask(gapFill.gt(0)).clip(aoi); 
  var result = ee.ImageCollection([resultIslands, resultGaps]).mosaic().neq(-9999).toInt(); 
  return result.toInt().selfMask();
}

// ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ Compile and Run Functions for Full Solar Array


// Function to get array panel-rows
function getPanels(feature){

  //################################################\\ 
  ///// Chunk Up Array and Get Classified Panels \\\\\
  //################################################\\
  
  // Get RF and SNIC/Kmeans result, regardless of chunked requirements
  var result = classifyPanels(feature);

  // Get number of chunks
  var maxChunkArea = 50000; // 5 ha
  var numChunks = ee.Number(feature.geometry().area(naipErrorMargin) // get array area
    .divide(maxChunkArea).round().divide(2).round().multiply(2) // Evenly chunk array area
    .max(1).toInt()); // with a minimum of one chunk

  // Split feature 
  var chunks = splitFeatures(feature, numChunks); 

  // Create an image collection of result clipped by each feature
  var panelsChunkedImg = ee.ImageCollection(chunks.map(function(chunk){return ee.Image(result.clip(chunk))})); 

  // For each chunk image, vectorize panels
  var panelsChunked = panelsChunkedImg.map(function(img){
    //############################\\ 
    ///// Create Panel Vectors \\\\\
    //############################\\
    // Vectorize the random forest image to get panel objects
    var cellPanels = img.reduceToVectors({
      geometry: img.geometry(),
      scale: scale,
      geometryType: 'polygon',
      eightConnected: true,
      labelProperty: 'panel',
      maxPixels: 1e13,
      bestEffort: true, 
      tileScale: 16 // Allows process to succeed, memory and size issues if this is not set properly
    });
    // Return panels
    return cellPanels; 
  }).flatten();

  // Union geometries and return single featureCollection
  var panels = ee.FeatureCollection(
    panelsChunked.union(1).geometry().buffer(0,naipErrorMargin).geometries().map(function(geom) {
      geom = ee.Geometry(geom); // Cast to ee.Geometry
      return ee.Feature(geom);
    })
  ); 

  //############################################\\ 
  ///// Determine if panels exist in imagery \\\\\ -- Using a temporary array shape
  //############################################\\
  
  // Reset aoi 
  var aoi = feature.geometry();

  // Get the number of panels and a temporary array boundary to determine if the array is rooftop or ground-mounted
  var panelNum = ee.Number(panels.size()); // NOTE: this is temporary, because the gridding above may inflate panel number
  var arrayTemp = panels.union(1).geometry().buffer(10).buffer(-10);
  
  // Set array geometry if panels existing and classification created panel objects of reasonable area
  var newArea = arrayTemp.area(naipErrorMargin); 
  var origArea = feature.geometry().area(naipErrorMargin);// Check original geometry
  var minAreaThresh = 0.15; // New area must be at least 15% of the original area
  
  // If high quality panel classification for existing NAIP year, use new shape. Else use original shape.
  var panelsAbsent = newArea.eq(0).or(
                     newArea.lt(origArea.multiply(minAreaThresh))).or(
                     panelNum.lt(2)); // Conditionals for checking if panels exist
  var panels = ee.FeatureCollection(ee.Algorithms.If(panelsAbsent, ee.FeatureCollection(aoi), panels)); // Save panels as aoi if panels absent
  var array = ee.Geometry(ee.Algorithms.If(panelsAbsent, aoi, arrayTemp)); // If present use new geom, else use input geom

  // Save attribute for post processing
  var panelsPresent = ee.String(ee.Algorithms.If(panelsAbsent, "No", "Yes"));

  //###########################################\\ 
  ///// Process and Remove Erroneous Panels \\\\\
  //###########################################\\

  // Because some features might have split, so we need to get individual geometries and create a new featureCollection (because we calcualte a median panel area)
  var panels = ee.FeatureCollection(panels.union(naipErrorMargin).geometry().geometries().map(function(geom){return ee.Feature(ee.Geometry(geom))}))
  
  // Set an initial panel area to test if panels are erronously sized. Set the size threshold to determine if convexHull or original shape saved
  var panels = panels.map(function(feature){return feature.set({pnlArea: feature.geometry().area(naipErrorMargin).toInt()})});
  var initialMedPnlArea = ee.Number(panels.aggregate_array("pnlArea").reduce(ee.Reducer.median())); 
  var multiPanelSizeThresh = 2; 
  
  // Set erode distance to try and dissolve connecting panel-row geometries
  var erodeBuffer = ee.Number(scale).add(0.05); // 5cm erode buffer

  // For each panel, simplify get the convexHull (allows for complex shapes and orientations), get area, dissolve connected panel boundaries
  var panels = panels.map(function(feature){
    // Get convext hull data
    var convHullTemp = feature.geometry().buffer(0,naipErrorMargin).convexHull(naipErrorMargin);
    var pnlArea = convHullTemp.area(naipErrorMargin).toInt();
    var convHull = ee.Geometry(ee.Algorithms.If(pnlArea.gte(minPanelRowArea), convHullTemp,  null)); // Else return null
 
    // Erode single pixel connecting boundaries. Unbuffer by just more than one pixel (0.6m), check for erroneous geometries, and rebuffer. 
    var geom = feature.geometry().buffer(0,naipErrorMargin);
    var dissolved = ee.Geometry(ee.Algorithms.If(panelsAbsent, geom, geom.buffer(erodeBuffer.multiply(-1), 1)));
    // Check for newly created errant geometries and filter
    var dissolvedPoly = dissolved.geometries().map(function(geometry){return ee.Algorithms.If(ee.Geometry(geometry).type().compareTo('Polygon'), null, geometry);}, true); // true is for drop nulls
    var dissolvedPolys = ee.Geometry(ee.Algorithms.If(
      ee.Algorithms.IsEqual(dissolvedPoly.size(), 1), // Check if the original geometry is a single polygon
      ee.Geometry(dissolvedPoly.get(0)), // If single polygon, return it directly
      ee.Geometry.MultiPolygon(dissolvedPoly))); // Otherwise, return as MultiPolygon
    // Rebuffer, and save new geometrty
    var newGeom = ee.Geometry(ee.Algorithms.If(panelsAbsent, geom, dissolvedPolys.buffer(erodeBuffer,naipErrorMargin)));

    // Get feature data and decide if we will use convexHull or a eroded pixel-based vector
    var area = newGeom.area(1).toInt(); 
    var shpConnected = area.gt(initialMedPnlArea.multiply(multiPanelSizeThresh)); 
    var outShp = ee.Geometry(ee.Algorithms.If(shpConnected, newGeom, convHull));
    return ee.Feature(feature.setGeometry(convHull)).set({pnlArea: pnlArea, shpCnctd: shpConnected})}, true); // dropNulls = true

  // Get a new median panel area and remove panels more than 4-times and less than 1/4 the median area
  var newMedPnlThreshold = 4; 
  var medPnlArea = ee.Number(panels.aggregate_array("pnlArea").reduce(ee.Reducer.median()));
  var panels = panels.filter(ee.Filter.gt("pnlArea", medPnlArea.divide(newMedPnlThreshold))); // remove any objects < 1/4 the average panel size -- //.filter(ee.Filter.lt("pnlArea", medPnlArea.multiply(10))) // remove any objects > 10-times the average panel size

  // For fixed and single axis tracking arrays, remove panels smaller than 34 sqm
  var panels = panels.filter(ee.Filter.gt("pnlArea", minPanelRowArea));

  //#####################################\\ 
  ///// Prepare Geometries for Export \\\\\ -- Remove null or erroneous geometries that GEE does not like
  //#####################################\\
  
  // Validate new panel geometries
  var panels = panels.map(validateGeometries);
  
  // Get panel number for export
  var panelNumber = panels.size(); 
  
  // Set panels to a multipolygon object for export
  var panels = ee.Geometry(panels.union(naipErrorMargin).first().geometry());
  
  // Get total panel area
  var totalPanelArea = panels.area(naipErrorMargin).toInt();
  
  // If panels don't exist, use input array geometry
  var panels = ee.Geometry(ee.Algorithms.If(panelsPresent.equals("Yes"), panels, aoi));

  // Export new geometry and relevent attributes
  var exportObject = feature.setGeometry(panels).set({pnlsPres: panelsPresent, pnlNum: panelNumber});
  return exportObject;
}

// ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ Export Panel Rows By Subset Arrays

// Prior to any operation, check for valid array geometries
var arrays = arrays.map(validateGeometries)

// Add arbitrary random number to subset featureCollection
var arrays = arrays.randomColumn("subset", seed, "uniform");
var arrays = arrays.map(function(feature){return feature.set({subset: feature.getNumber("subset").multiply(subsetMagnitude).toInt()})});

// Set export function
var exportPanelRows = function(subset){
  // Subset array dataset
  var exportFCTemp = fc.filter(ee.Filter.and(ee.Filter.gte("subset", subset), ee.Filter.lt("subset", ee.Number(subset).add(step))));
  
  // Run function
  var exportFC = exportFCTemp.map(getPanels); var folderName = 'solPanelExport_'; 
  
  ///*// Export the data as geojson (default)
  Export.table.toDrive({
      collection: exportFC,
      description: descriptionName + subset,
      fileFormat: 'GeoJSON',
      folder: folderName + runName,
      selectors: ['arrayID', 'subArrID', 'nativeID', 'Source', 'pnlsPres', 'pnlNum', '.geo'] // 'instYr', 'modType', 'mount', 'azimuth',
  });//*/
  
  /*// Export the data as shp
  Export.table.toDrive({
      collection: exportFC,
      description: descriptionName + subset,
      fileFormat: 'SHP',
      folder: folderName + runName,
      selectors: ['arrayID', 'subArrID', 'nativeID', 'Source', 'pnlsPres', 'pnlNum'] // 'instYr', 'modType', 'mount', 'azimuth',
  });  */
};

//####################\\
//    Run Function    \\
//####################\\

// ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ Run export for small arrays (<2ha or ~2MW) -- ~5500 arrays

/*
// Area limitation
var arraysSmall = arrays.filter(ee.Filter.lte('tempArea', smallAreaLimit));

// Save to fc variable
var fc = arraysSmall;
var step = smallStep;

// Run export over sequence
var descriptionName = 'smallArrays_'; var end = ee.Number(end).subtract(step).getInfo(); var sequence = ee.List.sequence({start: start, end: end, step: step}).getInfo();
var exportPanels = sequence.map(exportPanelRows);
*/

// ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ Run export for medium arrays (2ha<x>10ha or ~2-10MW) -- ~4,100 arrays

///*
// Area limitation
var arraysMed = arrays.filter(ee.Filter.lte('tempArea', medAreaLimit)).filter(ee.Filter.gt('tempArea', smallAreaLimit));

// Save to fc variable
var fc = arraysMed;
var step = medStep;

// Run export over sequence
var descriptionName = 'medArrays_'; var end = ee.Number(end).subtract(step).getInfo(); var sequence = ee.List.sequence({start: start, end: end, step: step}).getInfo();
var exportPanels = sequence.map(exportPanelRows);
//*/

// ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ Run export for large arrays (>10ha or 10MW) -- ~2,300 arrays

/*
// Area limitation
var arraysLrge = arrays.filter(ee.Filter.gte('tempArea', medAreaLimit));

// Save to fc variable
var fc = arraysLrge;
var step = lrgeStep;

// Run export over sequence
var descriptionName = 'lrgeArrays_'; var end = ee.Number(end).subtract(step).getInfo(); var sequence = ee.List.sequence({start: start, end: end, step: step}).getInfo();
var exportPanels = sequence.map(exportPanelRows);
*/


// ################################################################################## END of regular script

/*

// Debugging code
var subset = 318;
var temp = fc.filter(ee.Filter.and(ee.Filter.gte("subset", subset), ee.Filter.lt("subset", ee.Number(subset).add(step))));
var ids = temp.aggregate_array('subArrID'); print("Subset IDs: ", ids)
var feature = temp.filter(ee.Filter.eq("subArrID", ids.get(0)))
Map.addLayer(feature); Map.centerObject(feature.first()); print(feature); Map.addLayer(classifyPanels(ee.Feature(feature.first()))); Map.addLayer(feature.map(getPanels))
fdsa


// ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ By individual array

// Add arbitrary random number to subset featureCollection
//var arrays = arrays.randomColumn("subset", seed, "uniform");
//var arrays = arrays.map(function(feature){return feature.set({subset: feature.getNumber("subset").multiply(1000).toInt()})});

// Subset array dataset
var arraysTemp = arrays.filter(ee.Filter.and(ee.Filter.gte("subset", start), ee.Filter.lt("subset", ee.Number(end))));

// Get list of Solar dataset indices to map over
var indexList = arraysTemp.aggregate_array('nativeID'); 

// Map the getGCTimeseries function over the indexList
indexList.evaluate(function(indices){
  indices.forEach(function(index){
    // Run the function on an array
    var array = ee.Feature(arraysTemp.filter(ee.Filter.eq("nativeID", index)).first());
    var panels = ee.FeatureCollection([getPanels(array)]);
    
    // Export the data
    Export.table.toDrive({
        collection: panels,
        description:'solarPanels_' + index,
        fileFormat: 'SHP',
        folder: "solarPanels_" + date,
        selectors: ['arrayID', 'nativeID', 'instYr', 'modType', 'AVtype', 'Source', 'pnlsPres', 'mount', 'pnlArea', 'pnlNum', '.geo']
    });
  });
});
*/