//#####################################################################################################################//
/////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
///////////////////////////////                                                         /////////////////////////////////
/////////////////////////////// Get Random Sample Points For Solar Image Classification /////////////////////////////////
///////////////////////////////                                                         /////////////////////////////////
/////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
//#####################################################################################################################//

/*
-- Information --
Author: Jacob Stid
Date Created: 01-22-2021
Date Updated: 10-19-2024
Contact: stidjaco@msu.edu (Jacob Stid)

-- Notes --
This script runs in three parts/sections
*/
   
//##############################\\
////// Set Global Variables \\\\\\
//##############################\\

// Number of samples 
var panelSampleSize = 10000; // Solar samples from GMSEUS initial
var refSampleSize = 10000; // GLaNCE or LCMAP training dataset samples per class (split in half)

// Other Variables
var seed = 15; // seed used for random generation
var asset_name = '5e3_allPanels_lcmapRef'; // Asset name for export
var scale = 1; // set max NAIP scale -- after 2018, 0.3 to 0.6m

// Select GLCM band
var glcmBand1 = "_contrast"; 
var glcmBand2 = "_savg"; 
var glcmBand3 = "_var";

// Set bands
var bands = ["NDPVI", "NBD", "Br", "NDVI", "NDWI", "R", "G", "B", "N",
             "NDPVI" + glcmBand1, "NBD" + glcmBand1, "Br" + glcmBand1,
             "NDPVI" + glcmBand2, "NBD" + glcmBand2, "Br" + glcmBand2,
             "NDPVI" + glcmBand3, "NBD" + glcmBand3, "Br" + glcmBand3]; 

// Call base datasets
var NAIP = ee.ImageCollection('USDA/NAIP/DOQQ');
var aoi = ee.FeatureCollection('projects/ee-stidjaco/assets/CONUS_No_Great_Lakes');
var panelsGMSEUS = ee.FeatureCollection('projects/ee-stidjaco/assets/BigPanel/initialGMSEUS_Panels');
var panelsStid = ee.FeatureCollection('projects/ee-stidjaco/assets/BigPanel/PV_ID_Panels'); 
var GLANCE = ee.FeatureCollection('projects/sat-io/open-datasets/GLANCE/GLANCE_TRAINING_DATA_V1');
var LCMAP_ref = ee.FeatureCollection('projects/sat-io/open-datasets/LCMAP/LCMAP_CU_20200414_V01_REF'); 
var LCMAP_ref_table = ee.FeatureCollection('projects/ee-stidjaco/assets/BigPanel/TrainingData/LCMAP_ref').filter(ee.Filter.eq("image_year", 2018)); 
var LCMAP_ref_shps = ee.FeatureCollection('projects/ee-stidjaco/assets/BigPanel/TrainingData/LCMAP_ref_shp');
var glaciers = ee.FeatureCollection('projects/sat-io/open-datasets/RGI/RGI_VECTOR_MERGED_V7'); // RGI Glaciers
// Get lakes from NHD waterbody files (complicated because of GEE schema, so we do this below)

// Get CONUS Shape
var bounds = aoi.geometry().bounds();

// Add arbitrary property to create mask
var mask = aoi.map(function(feature){
    return feature.set({mask: 1});
}).reduceToImage({
    properties: ['mask'], // Arbitrary "value" for raster mask
    reducer: ee.Reducer.max()});

//###########################################################\\
////// Training Dataset of Validated Solar Panel Objects \\\\\\ ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ Section 1
//###########################################################\\

// Select panels with installation year < 2022 (most recent naip)
var panels = panelsGMSEUS.filter(ee.Filter.gt('instYr', -9999)).filter(ee.Filter.lt('instYr', 2022)); // print(panels.size())
var panels = panelsStid;

// Get panel centroids, add random column from 0 to 1
var panels = panels
  // Get centroid of each panel
  .map(function(feature){
    return feature.setGeometry(feature.geometry().centroid());
  }).randomColumn({
    seed: seed,
    columnName: "random", 
    distribution: "UNIFORM"
  });

// Select random panels points by sorting by 'random' and limiting to 10,000
var randomPanels = panels.sort('random').limit(panelSampleSize); // print('Number of training panels:', randomPanels.size()); Map.addLayer(randomPanels)

// Add attribute of class name
var randomPanels = randomPanels.map(function(feature){return feature.set({class_name: 0})}); //print(panels.first())

// Add attribute of source
var randomPanels = randomPanels.map(function(feature){return feature.set({source: 'panels'})}); //print(panels.first())

//##############################################\\
////// Get LCMAP Landcover Training Samples \\\\\\ ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ LCMAP
//##############################################\\

// LCMAP Reference attribute and shape Products
var idFilter = ee.Filter.equals({leftField: 'plotid', rightField: 'plotid'});
var innerJoin = ee.Join.inner('primary', 'secondary');
var LCMAP_ref = innerJoin.apply(LCMAP_ref_shps, LCMAP_ref_table, idFilter).map(function(feature){return feature.setGeometry(ee.Feature(feature.get("primary")).geometry())}); 

// Get LCMAP class dictionary (and remap)
var keys = ee.List(['Developed','Cropland','Grass/Shrub','Tree Cover','Water','Wetland','Snow/Ice','Barren']);
var values = ee.List([1,2,2,2,3,2,4,5]); // nativeValues = ee.List([1, 2, 3, 4, 5, 6, 7, 8]);
var lcmap_classes = ee.Dictionary.fromLists(keys, values); 

// Assign class number to LCMAP classes
var refTrain = LCMAP_ref.map(function(feature){
  var class_string = ee.String(ee.Feature(feature.get("secondary")).get("LCMAP"));
  var class_id = ee.Number(lcmap_classes.get(ee.String(class_string)));
  return feature.set({class_name: class_id});
});


// Set a max sample per plot value (30m x 30m plot, 900 possible 1 meter pixels, set 90 samples -- 10%)
var maxPlotSamples = 90;

// Function to sample from each plot
var sampleFromPlot = function(feature, numSamples) {
  return ee.FeatureCollection.randomPoints(feature.geometry(), numSamples)
    .map(function(pt) {
      return pt.set({class_name: feature.get('class_name'), plotid: feature.get('plotid')});
    });
};

// Function to get samples for each landcover class
var samplePerClass = function(classId) {
  // Filter reference plots for this class
  var classPlots = refTrain.filter(ee.Filter.eq('class_name', classId));
  
  // Determine how many samples are needed from each plot
  var totalPlots = classPlots.size();
  var samplesPerPlot = ee.Number(refSampleSize).divide(totalPlots).toInt().max(1); // Ensure at least one sample per plot
  
  // Sample from each plot
  var sampledPlots = classPlots.map(function(feature) {
    var plotSampleCount = ee.Number(samplesPerPlot).min(maxPlotSamples); // Limit to max samples per plot
    return sampleFromPlot(feature, plotSampleCount);
  }).flatten();
  
  // Resample if total samples are less than the target sample size
  var totalSamples = sampledPlots.size();
  return sampledPlots.limit(refSampleSize); // Trim to target size
};

// Sample each landcover class
var sampledDeveloped = samplePerClass(1); 
var sampledVegetation = samplePerClass(2);
var sampledWater = samplePerClass(3);
var sampledSnowIce = samplePerClass(4);
var sampledBarren = samplePerClass(5);

// Merge all samples together
var refTrain = sampledDeveloped
  .merge(sampledVegetation)
  .merge(sampledWater)
  .merge(sampledSnowIce)
  .merge(sampledBarren);

// Include glacier (snow/ice) samples ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ (Only 3 LCMAP Ref Plots)

// Get CONUS glaciers 
var glaciersCONUS = glaciers.filterBounds(aoi);

// Get glacierSampleSize from refTrain requirements
var glaciersSampleSize = ee.Number(refSampleSize).subtract(ee.Number(refTrain.filter(ee.Filter.eq("class_name", 4)).size()).toInt())

// Get CONUS glaciers size and calculate the number of samples per glacier
var numGlaciers = ee.Number(glaciersCONUS.size()); 
var numSamplesInGlaciers = ee.Number(1).max(ee.Number(glaciersSampleSize).divide(numGlaciers)).toInt(); 
var numToSample = ee.Number(glaciersSampleSize).min(numGlaciers.multiply(numSamplesInGlaciers)).toInt(); 

// For each glacier, generate random sample points
var snowIceTrain = glaciersCONUS.randomColumn('random', seed).sort('random').limit(numToSample).map(function(feature) {
  return ee.FeatureCollection.randomPoints({
    region: feature.geometry(), 
    points: numSamplesInGlaciers,
    seed: seed
  });}).flatten();
  
// Add snow/ice class tag to feature collection
var snowIce = 4; 
var snowIceTrain = snowIceTrain.map(function(feature){return feature.set({class_name: snowIce})});

// Combine with refTrain
var refTrain = refTrain.merge(snowIceTrain);

// Add attribute of source
var refTrain = refTrain.map(function(feature){return feature.set({source: 'reference'})});


//#################################################\\
////// Merge Training Points to Export Dataset \\\\\\ ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ Section 2
//#################################################\\

// Merge
var newfc = randomPanels.select(['class_name', 'source']).merge(refTrain.select(['class_name', 'source'])); //.merge(lulcTrain.select(['class_name', 'source']))

// Export shp file to drive
Export.table.toAsset({
  collection: newfc,
  description:'samplepoints_'+asset_name,
  assetId: 'projects/ee-stidjaco/assets/BigPanel/TrainingData/samplepoints_'+asset_name,
  priority: 1000
});

//#################################################\\
////// Sample NAIP Imagery At Random Locations \\\\\\ ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ Section 2
//#################################################\\

// Once exported, run below
var newfc = ee.FeatureCollection('projects/ee-stidjaco/assets/BigPanel/TrainingData/samplepoints_'+asset_name); // will show error until this exists

// Select sources to acquire appropriate NAIP 
var panels = newfc.filter(ee.Filter.inList("source", ["panels"])); 
var reference = newfc.filter(ee.Filter.inList("source", ["reference"])); 

// Functions to process NAIP
function scaleCollection(image) { // Rescale imagery function
  var scaler = 1 / 255; // NAIP is 8-bit data
  return image.select(["R", "G", "B", "N"]).multiply(scaler); } // 0 to 1 result

// Function to calculate GLCM texture features, ensuring integer input
function getGLCMTexture(image, bandName) {
  // Scale to deal with int32 limitation
  var scaled = image.select(bandName).multiply(255).toInt(); // Scale and convert to integer
  var glcm = scaled.glcmTexture({size: 1}); // , kernel: kernelAll, average: true});
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

function prepNAIP(image) { // Apply prep functions and copy properties 
  var orig = image;
  image = scaleCollection(image);
  image = getIndices(image);
  image = getGLCMTexture(image, 'NDPVI'); // For NDPVI index
  image = getGLCMTexture(image, 'NBD'); // For NBD index
  image = getGLCMTexture(image, 'Br'); // For Br index
  image = getLatLong(image);
  return ee.Image(image);}

// Call and process NAIP
var NAIP_recent = NAIP
  .filterDate(ee.DateRange('2021-01-01', '2022-12-31')) // Most recently available NAIP
  .map(prepNAIP)
  .select(bands)
  .max()
  .updateMask(mask);
var NAIP_ref = NAIP
  .filterDate(ee.DateRange('2018-01-01', '2019-12-31')) // LCMAP and GLaNCE Reference points were from 2018
  .map(prepNAIP)
  .select(bands)
  .max()
  .updateMask(mask);

// Get NAIP index values for recent NAIP (panels)
var SolIndexTraining_recent = NAIP_recent.sampleRegions({
  collection: panels,
  properties: ['class_name'],
  scale: scale, 
  geometries: true
});

// Get NAIP index values for reference NAIP (reference)
var SolIndexTraining_reference = NAIP_ref.sampleRegions({
  collection: reference,
  properties: ['class_name'],
  scale: scale, 
  geometries: true
});

// Merge 
var SolIndexTraining = SolIndexTraining_recent.merge(SolIndexTraining_reference);

// Get the count of each 'class_name' in SolIndexTraining_ref, and the final SolIndexTraining
var classCountsRef = SolIndexTraining_reference.reduceColumns({
  reducer: ee.Reducer.frequencyHistogram(),
  selectors: ['class_name']});
var classCounts = SolIndexTraining.reduceColumns({
  reducer: ee.Reducer.frequencyHistogram(),
  selectors: ['class_name']});

/*
// Print new size
print("Total Panel Sample Num: ", SolIndexTraining_recent.size());
print("Total Ref Sample Num: ", SolIndexTraining_reference.size());

// Print the class distributions
print("Number of each class in Reference Training Dataset: ", classCountsRef);
print("Number of each class in Final Training Dataset: ", classCounts);
*/

// Export shp file to asset for RandomForest model run
Export.table.toAsset({
  collection: SolIndexTraining,
  description:'SolIndexTraining_'+asset_name,
  assetId: 'projects/ee-stidjaco/assets/BigPanel/TrainingData/SolIndexTraining_'+asset_name, 
  priority: 1000
});


//##############################\\
////// Train and Test Model \\\\\\ ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ Section 3
//##############################\\

// Pull in dataset
var SolIndexTraining = ee.FeatureCollection('projects/ee-stidjaco/assets/BigPanel/TrainingData/SolIndexTraining_'+asset_name); print("Training Dataset Size: ", SolIndexTraining.size())

// Select bands
// Test bands
var bands = ["NDPVI", "NBD", "Br", "NDVI", "NDWI"];

// Function to sample each class by a fixed sample size of sampleSize
var sampleSize = 2000;
var SolIndexTraining = ee.FeatureCollection(ee.List([0,1,2,3,4,5]).map(function(value) {
    var classId = ee.Number(value);
    var classFeatures = SolIndexTraining.filter(ee.Filter.eq('class_name', classId)); // Filter features for the current class
    var featureCount = ee.Number(classFeatures.size()); // Get the count of available features
    var numToSample = ee.Number(sampleSize).min(featureCount); // Sample up to desired sample size of samples or fewer if not enough features
    var sampled = classFeatures.randomColumn({columnName: 'random', seed: seed, distribution: 'UNIFORM'}).sort('random').limit(numToSample); // Sample the features
    return sampled;
}).flatten()).flatten();

// Train a random forest classifier from the training sample. Use multiprobabitliy confidenc output
var trainedClassifier = ee.Classifier.smileRandomForest(200).setOutputMode('CLASSIFICATION').train({ // Output mode set to class of greatest probability across trees
  features: SolIndexTraining,
  classProperty: 'class_name',
  inputProperties: bands
});

// Get info on classifer
var trainAccuracy = trainedClassifier.confusionMatrix();
print('Selected Training Dataset Size: ', SolIndexTraining.size())
print('Training error matrix', trainAccuracy);
print('Training overall accuracy', trainAccuracy.accuracy())
print('Band Importance', trainedClassifier.explain().get('importance'))
print('Results of trained classifier', trainedClassifier.explain());

/*
// Apply RF class classifier: Conditionally mask based on PV type (thin-film is spectrally similar to water, we trained on crystalline silicon modules)
var testResult = NAIP_recent.classify(trainedClassifier); 
var palette = {min: 0, max: 5, palette: ['black', 'grey', 'green', 'blue', 'white', 'yellow']}
Map.addLayer(NAIP.filterDate('2021-01-01', '2022-12-31'))
Map.addLayer(testResult.reproject({crs: 'EPSG:4326', scale: 0.6}), palette)

Map.addLayer(table.filter(ee.Filter.lt("instYr", 2016))); 
//Map.addLayer(NAIP_lulc.where(NAIP_lulc.select(['NDPVI']).lt(-0.3), 0).where(NAIP_lulc.select(['NBD']).lt(0), 0).where(NAIP_lulc.select(['Br']).lt(0.2), 0).gt(0))
*/

//##########################################\\
////// Export Training Data and Weights \\\\\\ ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ Section 4
//##########################################\\

// Export training dataset
Export.table.toDrive({
  collection: SolIndexTraining,
  description: 'trainRF_'+asset_name,
  fileFormat: 'CSV',
  folder: 'SolarTrainingPointsRF'});

// Export classifier weights
var trees = ee.List(ee.Dictionary(trainedClassifier.explain()).get('trees')); var dummy = ee.Feature(null, {});
var col = ee.FeatureCollection(trees.map(function(x){return dummy.set('tree',x)}));
Export.table.toDrive({
  collection: col,
  description: 'classifier_'+asset_name,
  fileFormat: 'CSV',
  folder: 'SolarClassifierWeights'});

