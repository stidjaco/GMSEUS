//########################################################################################################################################## 
//#                                                                                                                                      #\\
//#                                        Digitize Array Bounds for Existing Database Point Locations                                   #\\
//#                                                                                                                                      #\\
//##########################################################################################################################################
 
/*
-- Information --
Author: Jacob Stid & Aster Ellsworth
Date Created: 09-11-2025
Date Updated: 09-29-2025
Contact: stidjaco@msu.edu (Jacob Stid)


-- Notes --
This script compiles and exports all newly digtized and georeferenced boundaries and metadata from points without spatial data in GM-SEUS v1.0. 
Point data was either: (1) georeferenced with a point-connector (line) between existing polygon and point objects, (2) georeferenced with a 
point-connector between a point object and a new array shape (polygon), (3) newly discovered and digizied with no existing metadata, or (4) 
georeferenced with a point-connector (line) between existing or newly digitized objects and newly created point objects. 

Digitization and georeferencing occur in *digitizeSolarArrays_v2_X*, where X is the script iteration to avoid memory overload issues. We will
export new boundaries and point-connectors togther for georeferencing future GM-SEUS versions (misaligned points will still be present in
import datasets), as well as just georeferenced and digitized array boundaries (no connections) with copied metadata. 

Asset definitions are: 
* digGeoref: Contains newly digitized and georeferenced array boundaries AND point-connectors for solar arrays without spatial boundaries in GM-SEUS v1.0. 
* newArrays: Contains newly digitized array boundaries that were discovered during the digitization process and with no metadata. 
* dupPolys: Contains newly created point objects with point metadata copied from existing point sources to avoid overlap between point spatial location. 
*/

 
// ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
// ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ Variables and imagery prep
// ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

//###################\\
//  Call Solar Data  \\
//###################\\

// Call in solar database to digitize
var toDigitizeID = 'projects/ee-stidjaco/assets/BigPanel/points_toDigitize';

// Call existing array shapes to see if buffer distance just did not catch existing shape
var existingArraysID = 'projects/ee-stidjaco/assets/BigPanel/existingDatasetArrayShapes'; 

// Call all existing points (to check after digitization process for removal of new array bounds)
var allPointsID = 'projects/ee-stidjaco/assets/BigPanel/points_all';

// Call all digitized and georeferenced arrays from prior script iterations
var newDigGeoRef_v2_asset0 = 'projects/ee-asterellsworth/assets/newDigGeoRef_v2_asset_0';
var newDigGeoRef_v2_asset1 = 'projects/ee-asterellsworth/assets/newDigGeoRef_v2_asset_1';
var newDigGeoRef_v2_asset2 = 'projects/ee-asterellsworth/assets/newDigGeoRef_v2_asset_2';
var newDigGeoRef_v2_assetInSPIRE = 'projects/ee-asterellsworth/assets/newDigGeoRef_v2_asset_inspire';
var newArrays_v2_asset0 = 'projects/ee-asterellsworth/assets/newArrays_v2_asset_0';
var newArrays_v2_asset1 = 'projects/ee-asterellsworth/assets/newArrays_v2_asset_1';
var newArrays_v2_asset2 = 'projects/ee-asterellsworth/assets/newArrays_v2_asset_2';
var dupPolys_v2_asset1 = 'projects/ee-asterellsworth/assets/duplicatePolys_v2_asset_1'; 
var dupPolys_v2_asset2 = 'projects/ee-asterellsworth/assets/duplicatePolys_v2_asset_2'; 

// Get states for breaking up export
var States = ee.FeatureCollection("TIGER/2018/States"); 

// Set date
var date = '093025';

// Set GM-SEUS version
var version = 'v1_1'

// Set asset folder for final export
var assetFolder = 'BigPanel/digGeoref_v1_1'

// Always set a seed
var seed = 15;

// Set geometry error margin and line buffer distance
var geomErrorMargin = ee.Number(1); 
var lineBuffer = ee.Number(0.1);

// Define grid and grid cell tagto fractionate export into
var grid = States; 
var gridCellIDtag = 'STUSPS'; 

// Required attributes to check existing sources for
var attList = [
  {name: 'AVtype',   type: 'String'},
  //{name: 'Source',   type: 'String'},
  {name: 'area',     type: 'Float'},
  {name: 'azimuth',  type: 'Float'},
  {name: 'cap_mw',   type: 'Float'},
  {name: 'instYr',   type: 'Long'},
  {name: 'modType',  type: 'String'},
  {name: 'mount',    type: 'String'},
  {name: 'nativeID', type: 'String'}
];

// ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
// ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ Helper Functions
// ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

// Function to check for valid geometries (as polygons/multipolygons) in a feature or featureCollection
var validateGeometries = function(feature){
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

// Functiont to copy attributes from a feature collection to another by intersection, checking for NA's 
var copyAttributes = function(fcFrom, fcTo, attList){
  //#################################\\
  // Internal attribute helper funcs \\
  //#################################\\
  // Target feature needs value if prop missing OR NA
  var needsValue = function(f, name, type) {
    var hasProp = f.propertyNames().contains(name);
    return ee.Algorithms.If(
      hasProp,
      (type === 'String')
        ? ee.String(f.get(name)).length().eq(0)   // empty string
        : ee.Number(f.get(name)).eq(-9999),       // -9999
      true // doesn’t exist at all
    );
  };
  
  // Source is valid if exists AND not NA (source being the source feature/attribute)
  var sourceValid = function(src, name, type) {
    var hasProp = src.propertyNames().contains(name);
    return ee.Algorithms.If(
      hasProp,
      (type === 'String')
        ? ee.String(src.get(name)).length().gt(0)
        : ee.Number(src.get(name)).neq(-9999),
      false
    );
  };
  
  // Conditionally set from source
  var setFromSourceIfNeeded = function(accF, srcF, name, type) {
    var need = ee.Algorithms.If(needsValue(accF, name, type), 1, 0);
    var valid = ee.Algorithms.If(sourceValid(srcF, name, type), 1, 0);
    var doSet = ee.Number(need).multiply(ee.Number(valid)).eq(1);
    return ee.Feature(ee.Algorithms.If(
      doSet,
      accF.set(name, srcF.get(name)),
      accF
    ));
  };
  
  // After merge: ensure every att exists; if missing, fill with NA
  var setMissingToNA = function(f, name, type) {
    var hasProp = f.propertyNames().contains(name);
    return ee.Feature(ee.Algorithms.If(
      hasProp,
      f, // already present; leave as-is (even if NA)
      f.set(name, (type === 'String') ? '' : -9999)
    ));
  };
  
  //#####################################\\
  // Apply functions and copy attributes \\
  //#####################################\\
  var fcOut = ee.FeatureCollection(fcTo.map(function(targetF) {
    // Overlapping sources
    var hits = fcFrom.filter(ee.Filter.intersects('.geo', targetF.geometry()));

    // Merge values from overlaps (first non-NA wins)
    var merged = ee.Feature(hits.iterate(function(srcF, acc) {
      acc = ee.Feature(acc);
      srcF = ee.Feature(srcF);
      attList.forEach(function(att){
        acc = setFromSourceIfNeeded(acc, srcF, att.name, att.type);
      });
      return acc;
    }, targetF));

    // Post-pass: guarantee all columns exist; fill missing with NA
    attList.forEach(function(att){
      merged = setMissingToNA(merged, att.name, att.type);
    });

    return ee.Feature(merged);
  }));
  
  return fcOut;
};

// Function to minor-buffor and union all objects in a fc, and return exploded resulting objects
var createUnionFC = function(fc){
 return ee.FeatureCollection(
  fc.geometry(geomErrorMargin).buffer(lineBuffer) // Small buffer to create intersecting polygons from connecting lines
  .geometries().map(function(geom) {
    return ee.Feature(ee.Geometry(geom));  // Wrap each geometry into a Feature
  })); 
};

//#####################################\\
// Data Call, Preparation, and Merging \\
//#####################################\\

// Get featureCollections 
var arraysToDigitize = ee.FeatureCollection(toDigitizeID); // Call the digitizing dataset
var existingArrays = ee.FeatureCollection(existingArraysID); // Call the existing dataset

// Get digitized and georeferenced arrays from previous script iterations
var digGeoref_0 = ee.FeatureCollection(newDigGeoRef_v2_asset0);
var digGeoref_1 = ee.FeatureCollection(newDigGeoRef_v2_asset1);
var digGeoref_2 = ee.FeatureCollection(newDigGeoRef_v2_asset2);
var digGeoref_InSPIRE = ee.FeatureCollection(newDigGeoRef_v2_assetInSPIRE);
var newArrays_0 = ee.FeatureCollection(newArrays_v2_asset0);
var newArrays_1 = ee.FeatureCollection(newArrays_v2_asset1);
var newArrays_2 = ee.FeatureCollection(newArrays_v2_asset2);
var dupPolys_1 = ee.FeatureCollection(dupPolys_v2_asset1);
var dupPolys_2 = ee.FeatureCollection(dupPolys_v2_asset2);

// Bring together digGeoref, newArrays, and dupPolys to map
var digGeoref = digGeoref_0.merge(digGeoref_1).merge(digGeoref_2).merge(digGeoref_InSPIRE); // print(digGeoref.size());
var newArrays = newArrays_0.merge(newArrays_1).merge(newArrays_2); // print(newArrays.size());
var dupPolys = dupPolys_1.merge(dupPolys_2); // print(dupPolys.size());

// ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
// ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ Report Numbers and Export
// ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

//####################################\\
//  Report numbers for digitization   \\
//####################################\\
/*
// Get new array area in newly digitized and georeferenced arrays (digGeoref) and not in existing sources, in km2
var nonIntersectingArrays = digGeoref.filter(ee.Filter.intersects('.geo', existingArrays.geometry(geomErrorMargin)).not()); print()
var nonIntersectingArea = nonIntersectingArrays.geometry(geomErrorMargin).area(geomErrorMargin).round().divide(1e6); print("New array area (existing point): ", nonIntersectingArea, 'km2');

// Get new array area in newly discovered and digitized arrays (newArrays) and not in existing sources, in km2
var nonIntersectingDiscoveredArrays = newArrays.filter(ee.Filter.intersects('.geo', existingArrays.geometry(1)).not());
var nonIntersectingDiscoveredArea = nonIntersectingDiscoveredArrays.geometry(geomErrorMargin).area(geomErrorMargin).round().divide(1e6); print("New array area (discovered): ", nonIntersectingDiscoveredArea, 'km2');

// Print total new array area (digitized, georeferenced, and discovered)
print("New array area (all): ", nonIntersectingArea.add(nonIntersectingDiscoveredArea), 'km2');

//#################################\\
//  Export all featureCollections  \\
//#################################\\

// Function to export newly digitized and georeferenced arrays to asset
var exportAsset = function(asset, name, folder){
 Export.table.toAsset({
   collection: asset, 
   description: "ExportAll_"+name, 
   assetId: folder+name+"_all", 
   maxVertices: 1e9, 
 });
};
 
// Export compiled assets
exportAsset(digGeoref, "newDigGeoRef_v2", "BigPanel/v1_1/");
exportAsset(newArrays, "newArrays_v2", "BigPanel/v1_1/");
exportAsset(dupPolys, "duplicatePolys_v2", "BigPanel/v1_1/");
*/

// ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
// ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ Lists of Source+nativeID of points to remove from existing point datasets (through quality selection)
// ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

// Set list of nativeID's where no panels exist in imagery. Take notes for each
var noPanelsPresent = [
  {Source: "GPPDB", nativeID: "Pacific Cruise Ship Terminals Berth 93"},
  {Source: "GPPDB", nativeID: "Silver State Solar Power North"},
  {Source: "GPPDB", nativeID: "Silver State Solar Power South"},
  {Source: "GPPDB", nativeID: "Solar Photovoltaic Project #05"},
  {Source: "GPPDB", nativeID: "Solar Photovoltaic Project #07"},
  {Source: "GPPDB", nativeID: "Solar Photovoltaic Project #13"},
  {Source: "GPPDB", nativeID: "Solar Photovoltaic Project #16"},
  {Source: "GPPDB", nativeID: "Solar Photovoltaic Project #17"},
  {Source: "GPPDB", nativeID: "Amazon Denver DEN3"},
  {Source: "GPPDB", nativeID: "ELACC Photovoltaic Power Facility"},
  {Source: "GPPDB", nativeID: "Solar Photovoltaic Project #09"},
  {Source: "GPPDB", nativeID: "Bergenmand Solar Partners  LLC Mahwah"},
  {Source: "GPPDB", nativeID: "Lakewood Seven Solar LLC"},
  {Source: "GPPDB", nativeID: "IKEA Canton Rooftop PV System"},
  {Source: "GPPDB", nativeID: "Amazon_DEN2"},
  {Source: "GPPDB", nativeID: "Stockton Athletic Center"},
  {Source: "GPPDB", nativeID: "Solar Photovoltaic Project #06"},
  {Source: "GPPDB", nativeID: "Solar Photovoltaic Project #08"},
  {Source: "GPPDB", nativeID: "Castalia Solar"},
  {Source: "GPPDB", nativeID: "Solar Photovoltaic Project #27"},
  {Source: "LBNLUSS", nativeID: "Solar Energy Generating Systems (SEGS) VIII"},
  {Source: "LBNLUSS", nativeID: "Warren Solar Farm (Mass Midstate 1-3, Ecos Energy LLC)"},
  {Source: "LBNLUSS", nativeID: "Bayshore Solar C"},
  {Source: "LBNLUSS", nativeID: "GMP Solar/Storage-Ferrisburgh Hybrid"},
  {Source: "LBNLUSS", nativeID: "Rio Rancho Solar Energy Center"},
  {Source: "LBNLUSS", nativeID: "GDIM 1, LLC (Iron Mine Solar)"},
  {Source: "LBNLUSS", nativeID: "GDIM 3, LLC (Iron Mine Solar)"},
  {Source: "LBNLUSS", nativeID: "GDIM 4, LLC (Iron Mine Solar)"},
  {Source: "LBNLUSS", nativeID: "Spectrum Solar Hybrid"},
  {Source: "LBNLUSS", nativeID: "Steamboat II"},
  {Source: "LBNLUSS", nativeID: "Steamboat III"},
  {Source: "LBNLUSS", nativeID: "SR DeSoto III"},
  {Source: "LBNLUSS", nativeID: "SR DeSoto II"},
  {Source: "LBNLUSS", nativeID: "Great Cove Solar"},
  {Source: "LBNLUSS", nativeID: "Great Cove Solar II"},
  {Source: "LBNLUSS", nativeID: "Storey Solar and Storage"},
  {Source: "LBNLUSS", nativeID: "Daggett 2"},
  {Source: "LBNLUSS", nativeID: "Daggett 3"},
  {Source: "LBNLUSS", nativeID: "Brady"},
  {Source: "PVDAQ", nativeID: "NREL CIS -1"},
  {Source: "PVDAQ", nativeID: "NREL x-Si -1"},
  {Source: "PVDAQ", nativeID: "NREL CIGS-11"},
  {Source: "PVDAQ", nativeID: "NREL low-X x-Si -1"},
  {Source: "PVDAQ", nativeID: "RTC-FSEC-Baseline"},
  {Source: "PVDAQ", nativeID: "RTC-NV-Baseline"},
  {Source: "gspt", nativeID: "Orion Solar I"},
  {Source: "gspt", nativeID: "Orion Solar II"},
  {Source: "gspt", nativeID: "Westlands Solar PV Farm"},
  {Source: "gspt", nativeID: "FLS Solar 230 Warren"},
  {Source: "gspt", nativeID: "Hatfield Solar PV"},
  {Source: "gspt", nativeID: "Independence II Solar Farm"},
  {Source: "gspt", nativeID: "Westmont 401 solar farm"},
  {Source: "gspt", nativeID: "Amazon PSP1 solar farm"},
  {Source: "gspt", nativeID: "Columbus Park solar farm"},
  {Source: "gspt", nativeID: "25 Mile Creek solar farm"},
  {Source: "gspt", nativeID: "SunEdison Walgreens Moreno Valley solar farm"},
  {Source: "gspt", nativeID: "SunEdison Procter & Gamble Oxnard solar farm"},
  {Source: "gspt", nativeID: "General Motors Corp at White Marsh MD solar farm"},
  {Source: "gspt", nativeID: "North County solar farm"},
  {Source: "gspt", nativeID: "Advance Stores Company Inc solar farm"},
  {Source: "gspt", nativeID: "BJ's Wholesale Club Inc- Uxbridge solar farm"},
  {Source: "gspt", nativeID: "Carina Community Solar"},
  {Source: "gspt", nativeID: "Niagara Bottling Stockton solar farm"},
  {Source: "gspt", nativeID: "SunE Stolee CSG solar farm"},
  {Source: "gspt", nativeID: "WasecaSun solar farm"},
  {Source: "gspt", nativeID: "Amazon BDL3 Solar Project"},
  {Source: "gspt", nativeID: "Douglas Todd Community Solar One CSG"},
  {Source: "gspt", nativeID: "Allie L.L.C. solar farm"},
  {Source: "gspt", nativeID: "Dodge Renewables 1 solar farm"},
  {Source: "gspt", nativeID: "Dodge Renewables 2 solar farm"},
  {Source: "gspt", nativeID: "NY - PANYNJ - LaGuardia - Rooftop solar farm"},
  {Source: "gspt", nativeID: "IGS Solar I - BWI5"},
  {Source: "gspt", nativeID: "Johnson Co. Solar RES"},
  {Source: "gspt", nativeID: "Jackson Co. Solar RES"},
  {Source: "gspt", nativeID: "ASTI solar farm"},
  {Source: "gspt", nativeID: "Oregon University System Rabbit Field solar farm"},
  {Source: "gspt", nativeID: "IKEA Grand Prairie Rooftop PV System solar farm"},
  {Source: "gspt", nativeID: "ALDI DC 2 solar farm"},
  {Source: "gspt", nativeID: "IKEA Oak Creek Rooftop PV System solar farm"},
  {Source: "gspt", nativeID: "Kroger La Habra solar farm"},
  {Source: "gspt", nativeID: "Blue Sky One solar farm"},
  {Source: "gspt", nativeID: "Sterlington Greenworks solar farm"},
  {Source: "gspt", nativeID: "DG Webster CSG solar farm"},
  {Source: "gspt", nativeID: "Aerolease solar farm"},
  {Source: "gspt", nativeID: "Amazon Maryland DCA1 solar farm"},
  {Source: "gspt", nativeID: "Reed Road Solar"},
  {Source: "gspt", nativeID: "Corvias - Fort Riley II solar project"},
  {Source: "gspt", nativeID: "Beringer solar farm"},
  {Source: "gspt", nativeID: "ISH Solar Central"},
  {Source: "gspt", nativeID: "4 Applegate Solar"},
  {Source: "gspt", nativeID: "12 Applegate Solar"},
  {Source: "gspt", nativeID: "IKEA Jacksonville Rooftop PV System solar farm"},
  {Source: "gspt", nativeID: "Riverhead I solar farm"},
  {Source: "gspt", nativeID: "Town of Cary solar farm"},
  {Source: "gspt", nativeID: "Oltmans SCE at Jurupa solar farm"},
  {Source: "gspt", nativeID: "Lancaster Solar 1"},
  {Source: "gspt", nativeID: "Lancaster Solar 2"},
  {Source: "gspt", nativeID: "Quincy II Solar Garden"},
  {Source: "gspt", nativeID: "Oak Leaf Solar XXV CSG"},
  {Source: "gspt", nativeID: "7448 Candlewood Road solar farm"},
  {Source: "gspt", nativeID: "5601 Westside CDG solar farm"},
  {Source: "gspt", nativeID: "601 Doremus CDG solar farm"},
  {Source: "gspt", nativeID: "CPG - Duke 5300A Holabird solar project"},
  {Source: "gspt", nativeID: "CPG - Duke 5300B Holabird solar project"},
  {Source: "gspt", nativeID: "CPG - Duke 5900 Holabird solar project"},
  {Source: "gspt", nativeID: "CPG - Duke 6000 Holabird solar project"},
  {Source: "gspt", nativeID: "Grand Prix Solar"},
  {Source: "gspt", nativeID: "Seminole solar farm"},
  {Source: "gspt", nativeID: "Daytona International Speedway Solar"},
  {Source: "gspt", nativeID: "Broadway 4 - Target Shafter solar farm"},
  {Source: "gspt", nativeID: "Francis Scott Key Mall solar farm"},
  {Source: "gspt", nativeID: "POM Plant 2 solar project"},
  {Source: "gspt", nativeID: "IKEA Live Oak Rooftop PV System solar farm"},
  {Source: "gspt", nativeID: "Sacket Lake Rd 2 Community Solar Farm"},
  {Source: "gspt", nativeID: "County of San Diego COC Hybrid solar farm"},
  {Source: "gspt", nativeID: "Lafayette 2 - MLK Jr. Hospital MLK solar farm"},
  {Source: "gspt", nativeID: "Renew Solar ABC Sacramento"},
  {Source: "gspt", nativeID: "Union Vale solar project"},
  {Source: "gspt", nativeID: "Macy's MD Joppa Solar Project"},
  {Source: "gspt", nativeID: "Westmont 301 solar farm"},
  {Source: "gspt", nativeID: "CBP Solar"},
  {Source: "gspt", nativeID: "Estrella Mountain PV solar farm"},
  {Source: "gspt", nativeID: "POM Beverage Solar"},
  {Source: "gspt", nativeID: "Garnet Solar NY"},
  {Source: "gspt", nativeID: "Xebec 1 solar farm"},
  {Source: "gspt", nativeID: "Lafayette 2 - Internal Services Dept solar farm"},
  {Source: "gspt", nativeID: "Emerald Marshfields, LLC solar project"},
  {Source: "gspt", nativeID: "Raritan ITS solar farm"},
  {Source: "gspt", nativeID: "Dennison solar farm"},
  {Source: "gspt", nativeID: "Rose Hill solar farm"},
  {Source: "gspt", nativeID: "205 Sturbridge A solar farm"},
  {Source: "gspt", nativeID: "201 Sturbridge B solar farm"},
  {Source: "gspt", nativeID: "Syncarpha Still River CSG solar farm"},
  {Source: "gspt", nativeID: "DG Foxborough Elm CSG solar farm"},
  {Source: "gspt", nativeID: "IKEA Joliet Rooftop PV System solar farm"},
  {Source: "gspt", nativeID: "Upton Community Solar"},
  {Source: "gspt", nativeID: "Broome County solar farm"},
  {Source: "gspt", nativeID: "Hinsdale Solar PV"},
  {Source: "gspt", nativeID: "Howell CSG solar farm"},
  {Source: "gspt", nativeID: "Fairhaven E solar farm"},
  {Source: "gspt", nativeID: "Fogarty CSG solar farm"},
  {Source: "gspt", nativeID: "SCS COUNTY 012631 Champaign solar farm"},
  {Source: "gspt", nativeID: "Steamboat Hills LP solar farm"},
  {Source: "gspt", nativeID: "Galena 2 Geothermal Power Plant solar farm"},
  {Source: "gspt", nativeID: "GSE NM1 solar farm"},
  {Source: "gspt", nativeID: "Galloway Landfill solar farm"},
  {Source: "gspt", nativeID: "SCS Randolph 012175 Somerset solar farm"},
  {Source: "gspt", nativeID: "Matrix Buildings A&B Perth Amboy Solar"},
  {Source: "gspt", nativeID: "Sol Phoenix solar farm"},
  {Source: "gspt", nativeID: "Augusta South Carolina solar farm"},
  {Source: "gspt", nativeID: "Blue Lake Solar"},
  {Source: "gspt", nativeID: "IOS II-LAX9 solar farm"},
  {Source: "gspt", nativeID: "Maple CSG solar farm"},
  {Source: "gspt", nativeID: "Westport B Community Solar Garden"},
  {Source: "gspt", nativeID: "GMP Solar/Storage-Essex Hybrid"},
  {Source: "gspt", nativeID: "GMP Solar - Panton Hybrid"},
  {Source: "gspt", nativeID: "Meadowlark Solar"},
  {Source: "gspt", nativeID: "Acme Solar"},
  {Source: "gspt", nativeID: "Auburn Solar Project"},
  {Source: "gspt", nativeID: "Old Mill Solar"},
  {Source: "gspt", nativeID: "Dodge Holdco Solar CSG"},
  {Source: "gspt", nativeID: "Floyd Road Solar Farm"},
  {Source: "gspt", nativeID: "Franklinton Solar"},
  {Source: "gspt", nativeID: "Wilson Solar Farm 2"},
  {Source: "gspt", nativeID: "Adirondack A and B Community Solar Garden"},
  {Source: "gspt", nativeID: "Moore II solar farm"},
  {Source: "gspt", nativeID: "GMP Solar/Storage-Ferrisburgh Hybrid"},
  {Source: "gspt", nativeID: "GMP Solar/Storage-Milton Hybrid"},
  {Source: "gspt", nativeID: "Sartell Holdco CSG solar farm"},
  {Source: "gspt", nativeID: "Phillips Route 82 Solar LLC"},
  {Source: "gspt", nativeID: "Urtica Solar Project"},
  {Source: "gspt", nativeID: "NorWest Energy 9 solar farm"},
  {Source: "gspt", nativeID: "SR Rattlesnake solar farm"},
  {Source: "gspt", nativeID: "Cottage Grove Solar"},
  {Source: "gspt", nativeID: "Rabbitbrush Solar"},
  {Source: "gspt", nativeID: "Springerville solar farm"},
  {Source: "gspt", nativeID: "Springerville solar project"},
  {Source: "gspt", nativeID: "Five Points Solar Station"},
  {Source: "gspt", nativeID: "Prescott Solar Plant"},
  {Source: "gspt", nativeID: "California Valley Solar Ranch"},
  {Source: "GPPDB", nativeID: "New Orleans Solar Power Plant"},
  {Source: "gspt", nativeID: "Naval Air Weapons Station China Lake solar farm"},
  {Source: "gspt", nativeID: "SunE CPS3 solar farm"}, 
  {Source: "gspt", nativeID: "Campo Verde Solar"}, 
  {Source: "gspt", nativeID: "Indy Solar III"},
  {Source: "gspt", nativeID: "Dalton 2 solar farm"},
  {Source: "gspt", nativeID: "Desert Green Solar Farm"},
  {Source: "gspt", nativeID: "Cibola solar farm"},
  {Source: "gspt", nativeID: "Tequesquite Landfill Solar PV Project"},
  {Source: "gspt", nativeID: "Howell Solar"},
  {Source: "gspt", nativeID: "Pfizer Peapack Solar"},
  {Source: "gspt", nativeID: "Solar Glynn"},
  {Source: "gspt", nativeID: "Williamston Speight Solar"},
  {Source: "gspt", nativeID: "Spartan solar farm"},
  {Source: "gspt", nativeID: "Adams Nielson Solar"},
  {Source: "gspt", nativeID: "Bartow Solar Energy"}, 
  {Source: "gspt", nativeID: "City of Gallup Solar"}, 
  {Source: "gspt", nativeID: "Ellis Solar"},  
  {Source: "gspt", nativeID: "KDC Solar PR1"}, 
  {Source: "gspt", nativeID: "Tungsten Mountain solar farm"}, 
  {Source: "gspt", nativeID: "Holstein 1 (Duke) solar farm"}, 
  {Source: "gspt", nativeID: "Tanglewood Solar"}, 
  {Source: "gspt", nativeID: "Turquoise solar farm"}, 
  {Source: "gspt", nativeID: "Electric City Solar"}, 
  {Source: "gspt", nativeID: "Midway Green Solar"},
  {Source: "gspt", nativeID: "Troupsburg solar farm"}, 
  {Source: "gspt", nativeID: "Briar Creek Solar"}, 
  {Source: "gspt", nativeID: "Corazon Energy solar farm"}, 
  {Source: "gspt", nativeID: "Concho Valley Solar"}, 
  {Source: "gspt", nativeID: "Jicarilla Solar"}, 
  {Source: "gspt", nativeID: "Mt. Olive Solar Field"}, 
  {Source: "gspt", nativeID: "BD Solar Ellsworth"},
  {Source: "gspt", nativeID: "Brainerd Airport solar project"},
  {Source: "gspt", nativeID: "Orioles solar farm"},
  {Source: "gspt", nativeID: "Stratford Solar Center"},
  {Source: "gspt", nativeID: "TPE King Solar Holdings1 CSG"},
  {Source: "gspt", nativeID: "Sycamore Solar"},
  {Source: "gspt", nativeID: "Yellow Pine Solar Project"},
  {Source: "gspt", nativeID: "Tequesquite Landfill Solar PV Project"},
  {Source: "gspt", nativeID: "Prescott Airport solar project"},
  {Source: "gspt", nativeID: "Prescott Solar Plant"},
  {Source: "gspt", nativeID: "Griffin Solar"},
  {Source: "gspt", nativeID: "Southwick Solar PV"},
  {Source: "gspt", nativeID: "Breckenridge Solar"},
  {Source: "gspt", nativeID: "East Brookfield Adams Road Solar CSG"},
  {Source: "gspt", nativeID: "Castalia Solar"},
  {Source: "gspt", nativeID: "Valencia Solar"},
  {Source: "gspt", nativeID: "MCRD Parris Island PV Hybrid solar project"}, 
  {Source: "GPPDB", nativeID: "Longboat Solar  LLC"},
  {Source: "GPPDB", nativeID: "Richland Solar Center"},
  {Source: "GPPDB", nativeID: "Caprock Solar 1 LLC"}, 
  {Source: "GPPDB", nativeID: "Correctional Solar LLC"},
  {Source: "GPPDB", nativeID: "Wilson Solar Farm 3"}, 
  {Source: "GPPDB", nativeID: "Wilson Solar Farm 4"}, 
  {Source: "GPPDB", nativeID: "Wilson Solar Farm 7"},
  {Source: "GPPDB", nativeID: "OlivePV"},
  {Source: "GPPDB", nativeID: "ANAD Solar Array"},
  {Source: "gspt", nativeID: "City of Tulare Water Facility solar farm"},
  {Source: "GPPDB", nativeID: "DWW Solar ll"},
  {Source: "GPPDB", nativeID: "FL Solar 4  LLC"},
  {Source: "gspt", nativeID: "National Raisin solar project"},
  {Source: "gspt", nativeID: "Onset West Community Solar Facility"},
  {Source: "gspt", nativeID: "Wyoming 2 CSG, LLC solar project"},
  {Source: "gspt", nativeID: "Manheim New Jersey solar project"},
  {Source: "gspt", nativeID: "Porterville 6 and 7 solar project"},
  {Source: "gspt", nativeID: "CSUF Nutwood Solar"},
  {Source: "gspt", nativeID: "P52ES 1755 Henryton Rd Phase 1 CSG solar farm"},
  {Source: "LBNLUSS", nativeID: "San Miguel I Solar Energy Center"},
  {Source: "LBNLUSS", nativeID: "San Miguel II Solar Energy Center"},
  {Source: "gspt", nativeID: "Coronus Adelanto West 1 solar farm"},
  {Source: "gspt", nativeID: "Coronus Adelanto West 2 solar farm"},
  {Source: "gspt", nativeID: "Ware Avra I solar farm"},
  {Source: "gspt", nativeID: "Ware Avra II solar farm"},
  {Source: "gspt", nativeID: "Kings Park Solar I"},
  {Source: "gspt", nativeID: "Kings Park Solar II"},
  {Source: "gspt", nativeID: "Newfield Community Solar LLC"},
  {Source: "gspt", nativeID: "St. Paul Intl Airport Red & Blue Parking solar project"},
  {Source: "gspt", nativeID: "Randall Solar Project Hybrid"},
  {Source: "gspt", nativeID: "Bantam Solar"},
  {Source: "gspt", nativeID: "DOCCS Greene solar project"},
  {Source: "gspt", nativeID: "Church Hill solar farm"},
  {Source: "gspt", nativeID: "Calipatria State Prison solar farm"},
  {Source: "gspt", nativeID: "Centinela State Prison solar farm"},
  {Source: "gspt", nativeID: "City of Pratt Solar"},
  {Source: "gspt", nativeID: "Newfield Community Solar"},
  {Source: "gspt", nativeID: "Newfield Community Solar LLC"},
  {Source: "gspt", nativeID: "Facebook 1 Solar Energy Center"},
  {Source: "gspt", nativeID: "Jackson (North Carolina) solar farm"},
  {Source: "gspt", nativeID: "Rio Rancho Solar Energy Center"},
  {Source: "gspt", nativeID: "Suntex Solar"},
  {Source: "gspt", nativeID: "Richmond Spider Solar"},
  {Source: "gspt", nativeID: "Cement City Solar"},
  {Source: "gspt", nativeID: "Southampton Solar"},
  {Source: "gspt", nativeID: "Fish Springs Ranch solar farm"},
  {Source: "LBNLUSS", nativeID: "Griffin Solar"},
  {Source: "gspt", nativeID: "Aspiration G solar farm"},
  {Source: "gspt", nativeID: "Luciana solar farm"},
  {Source: "gspt", nativeID: "Centaurus Community Solar"},
  {Source: "gspt", nativeID: "Antares Community Solar"},
  {Source: "gspt", nativeID: "Somonauk Road Solar 1"},
  {Source: "gspt", nativeID: "Capella Community Solar"},
  {Source: "gspt", nativeID: "Hazel solar farm"},
  {Source: "gspt", nativeID: "USS Chariot Solar"},
  {Source: "GPPDB", nativeID: "Red Horse 2"}, 
  {Source: "GPPDB", nativeID: "Red Horse III"},
  {Source: "LBNLUSS", nativeID: "SR Snipesville III"}, 
];

// Set list of nativeID's where no panels exist in imagery for InSPIRE dataset. Note, this is separate because we performed this dig+georef in version 1.0. 
var noPanelsPresentInSPIRE = [
  {Source: 'InSPIRE', nativeID: 'California: Habitat & Wildlife Monitoring'},
  {Source: 'InSPIRE', nativeID: 'SoliCulture Greenhouse'},
  {Source: 'InSPIRE', nativeID: 'Haywood Solar Farm'},
  {Source: 'InSPIRE', nativeID: 'Saffron in Vermont'},
  {Source: 'InSPIRE', nativeID: 'CSU Spur Campus - Rooftop Agrivoltaics'},
  {Source: 'InSPIRE', nativeID: 'LeGore Bridge Solar Center'},
  {Source: 'InSPIRE', nativeID: 'Summit Plant Labs'},
  {Source: 'InSPIRE', nativeID: 'Sunzaun Somerset Winery'},
  {Source: 'InSPIRE', nativeID: 'Joe Czajkowski Farm'},
  {Source: 'InSPIRE', nativeID: 'USDA-UGA AgSolar Synergy'},
  {Source: 'InSPIRE', nativeID: 'Growing Green - Spaces of Opportunity'},
  {Source: 'InSPIRE', nativeID: 'CSU Foothills Campus - Rooftop Agrivoltaics Research'},
  {Source: 'InSPIRE', nativeID: 'Abel'},
  {Source: 'InSPIRE', nativeID: 'Bunker Hill'},
  {Source: 'InSPIRE', nativeID: 'Giveback- Salsola mowing'},
  {Source: 'InSPIRE', nativeID: 'Goodrich Solar'},
  {Source: 'InSPIRE', nativeID: 'USS Peach'},
  {Source: 'InSPIRE', nativeID: 'Foxhound Solar'},
  {Source: 'InSPIRE', nativeID: 'Temple University Ambler Campus'},
  {Source: 'InSPIRE', nativeID: 'Putnam Solar'}
];

// Set list for exisiting solar arrays that are rooftop arrays
var rooftopIDs = [
  {Source: "sourceExample", nativeID: "nativeIDexample"},
  {Source: "SAM", nativeID: "61583_0"}, 
  {Source: "SAM", nativeID: "26700_0"}, 
  {Source: "SAM", nativeID: "29685_0"}, 
  {Source: "SAM", nativeID: "71854_0"}, 
  {Source: "OSM", nativeID: "6969"}, 
  {Source: "SAM", nativeID: "9550_0"}, 
  {Source: "SAM", nativeID: "81697_0"}, 
  {Source: "OSM", nativeID: "1226"}, 
  {Source: "OSM", nativeID: "1198"}, 
  {Source: "CCVPV", nativeID: "919"}, 
  {Source: "SAM", nativeID: "5064_0"}, 
  {Source: "SAM", nativeID: "15373_0"}, 
  {Source: "SAM", nativeID: "89473_0"}, 
  {Source: "SAM", nativeID: "86700_0"}, 
  {Source: "OSM", nativeID: "7639"}, 
  {Source: "OSM", nativeID: "7638"}, 
  {Source: "OSM", nativeID: "7647"}, 
  {Source: "OSM", nativeID: "7644"}, 
  {Source: "OSM", nativeID: "7643"}, 
  {Source: "SAM", nativeID: "67508_0"}, 
  {Source: "OSM", nativeID: "7642"}, 
  {Source: "SAM", nativeID: "24793_0"}, 
  {Source: "SAM", nativeID: "67708_1"}, 
  {Source: "OSM", nativeID: "7641"}, 
  {Source: "OSM", nativeID: "3083"}, 
  {Source: "OSM", nativeID: "3084"}, 
  {Source: "OSM", nativeID: "7327"}, 
  {Source: "OSM", nativeID: "7435"}, 
  {Source: "OSM", nativeID: "7326"}, 
  {Source: "SAM", nativeID: "24079_1"}, 
  {Source: "OSM", nativeID: "2157"}, 
  {Source: "OSM", nativeID: "1964"}, 
  {Source: "OSM", nativeID: "2157"}, 
  {Source: "OSM", nativeID: "2158"}, 
  {Source: "OSM", nativeID: "1965"}, 
  {Source: "OSM", nativeID: "1921"}, 
  {Source: "OSM", nativeID: "1963"}, 
  {Source: "OSM", nativeID: "1929"}, 
  {Source: "SAM", nativeID: "32121_1"}, 
  {Source: "SAM", nativeID: "89998_0"}, 
  {Source: "OSM", nativeID: "1966"}, 
  {Source: "OSM", nativeID: "1610"}, 
  {Source: "OSM", nativeID: "1202"}, 
  {Source: "OSM", nativeID: "4761"},
  {Source: "OSM", nativeID: "2051"},
  {Source: "SAM", nativeID: "40960_0"},
  {Source: "SAM", nativeID: "102509_0"},
  {Source: "SAM", nativeID: "60831_0"},
  {Source: "OSM", nativeID: "1207"},
  {Source: "SAM", nativeID: "35928_0"},
  {Source: "OSM", nativeID: "10499"},
];

// Function to combine Source and nativeID in main to digitize dataset
var arraysToDigitize = arraysToDigitize.map(function(f) {
  var combined = ee.String(f.get("Source")).cat("_").cat(ee.String(f.get("nativeID")));
  return f.set("SourceNativeID", combined);
});

// Create a single list for each list dictionary above with combined Source and Native ID, 
function buildSourceNativeIDList(dictList) {
  return dictList.map(function(d) {
    return d.Source + "_" + d.nativeID;
  });
}

// Create the exclusion lists by merging Source and nativeID dictionaries
var noPanelsPresent_prep = buildSourceNativeIDList(noPanelsPresent);
var noPanelsPresentInSPIRE_prep = buildSourceNativeIDList(noPanelsPresentInSPIRE);
var rooftopIDs_prep = buildSourceNativeIDList(rooftopIDs);

// Filter arraysToDigitize to exclude those in the lists above
var arraysRemaining = arraysToDigitize
  .filter(ee.Filter.inList("SourceNativeID", noPanelsPresent_prep).not())
  .filter(ee.Filter.inList("SourceNativeID", noPanelsPresentInSPIRE_prep).not())
  .filter(ee.Filter.inList("SourceNativeID", rooftopIDs_prep).not());

// ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
// ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ Compile and Export
// ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

/*
Notes: 
Goal Output: Digitized and existing georef with most complete metadata possible. 
The order of copying is critical, since the functions check for the existence of 
metadata before copying.
*/

///*
//################################################################\\
// Merge and Copy toDigitize Attributes to New and Existing Geoms \\ ~~~~~~~~~~~~~~~~~~~~ By state
//################################################################\\




// Function to separate process by grid cell (in this case, state). Have to create union first to address georeferencing with overlapping states
var exportDigGeorefByState = function(gridCellID){
  
  // ~~~~~~~~~~~~~~~~~~~ Prepare digitized and georefenced object subsets to address memory overload issues
  
  // Buffer and create a union of digitized and georeferenced objects. Then, split the unioned geometry back into individual geometries
  var digGeorefAllUnion = createUnionFC(digGeoref); 
  var newArraysAllUnion = createUnionFC(newArrays); 
  var dupPolysAllUnion = createUnionFC(dupPolys); 
  
  // Subset digGeoref, newArrays, and dupPoly - unioned objects - by gridded id (state shorthand)
  var gridCell = grid.filter(ee.Filter.eq(gridCellIDtag, gridCellID));
  var digGeorefAllUnionState = digGeorefAllUnion.filterBounds(gridCell);
  var newArraysAllUnionState = newArraysAllUnion.filterBounds(gridCell);
  var dupPolysAllUnionState = dupPolysAllUnion.filterBounds(gridCell);
  
  // Now, subset original featureCollections by unioned subsets (prevents dropping of cross-border georeferenced objects) - still have to check for overlap once pull dataset together
  var digGeorefSubset = digGeoref.filterBounds(digGeorefAllUnionState);
  var newArraysSubset = newArrays.filterBounds(newArraysAllUnionState);
  var dupPolysSubset = dupPolys.filterBounds(dupPolysAllUnionState);

  // ~~~~~~~~~~~~~~~~~~~ Prepare points and split digitized array bounds from georeferenced line-connectors
  
  // Merge dupPolys with arraysToDigitze - dupPolys are the updated arraysToDigitize points to prevent self-overlap and improper metadata attribution
  var arraysToDigitizeMerged = arraysRemaining.merge(dupPolysSubset);
  
  // Split digGeoref by georeferenced vs digitized objects by geometry type
  var digGeorefType = digGeorefSubset.map(function(f){return f.set({gtype: ee.String(ee.Algorithms.If(ee.Geometry(f.geometry(geomErrorMargin)).type().compareTo('LineString'), 'Polygon', 'LineString'))})});
  var georef = digGeorefType.filter(ee.Filter.eq("gtype", "LineString")); 
  var dig = digGeorefType.filter(ee.Filter.eq("gtype", "Polygon")); 
  
  // Get existingArrays that do and do not intersect with digitized polygons (dig)
  var digExistingArrays = existingArrays.filter(ee.Filter.intersects('.geo', dig.geometry(geomErrorMargin))); // existing arrays to remove
  var nonDigExistingArrays = existingArrays.filter(ee.Filter.intersects('.geo', dig.geometry(geomErrorMargin)).not()).filter(ee.Filter.intersects('.geo', georef.geometry(geomErrorMargin))); // existing arrays to keep
  
  // ~~~~~~~~~~~~~~~~~~~ Copy metadata from merged points to newly digitized array boundaries
  
  // Buffer and create a union of digitized and georeferenced objects. Then, split the unioned geometry back into individual geometries and map over each geometry to convert it into a feature
  var digGeorefUnion = createUnionFC(digGeorefType);
  
  // Copy metadata from points to the digGeorefUnion based on intersecting objects. Set Source as 'GMSEUSdigGeoref_version'. Then copy metadata to original dig
  var digGeorefWithAttributesBuffered = copyAttributes(arraysToDigitizeMerged, digGeorefUnion, attList);
  var digGeorefWithAttributes = copyAttributes(digGeorefWithAttributesBuffered, dig, attList).map(function(f){return f.set({Source: ee.String('GMSEUSdig_').cat(version)})});
  
  // ~~~~~~~~~~~~~~~~~~~ Copy metadata from merged points to kept existing array boundaries
  
  // Merge existingArrays with georeferenced line-connectors. Then, buffer and create a union of digitized and georeferenced objects. Then, split the unioned geometry back into individual geometries and features
  var existingArraysGeoref = digExistingArrays.merge(georef);
  var existingGeorefUnion = createUnionFC(existingArraysGeoref);
  
  // Copy metadata from digExistingArrays to dig based on intersecting objects. Set Source as 'GMSEUSdigGeoref_version'
  var existingGeorefWithAttributesBuffered = copyAttributes(arraysToDigitizeMerged, existingGeorefUnion, attList);
  var existingGeorefWithAttributes = copyAttributes(existingGeorefWithAttributesBuffered, nonDigExistingArrays, attList).map(function(f){return f.set({Source: ee.String('GMSEUSgeoref_').cat(version)})});
  
  // ~~~~~~~~~~~~~~~~~~~ Copy metadata from removed existing array boundaries to newly digitized array boundaries with attributes
  
  // Copy metadata from digExistingArrays to digGeorefWithAttributes based on intersecting objects. 
  var digGeorefWithAttributesAll = copyAttributes(digExistingArrays, digGeorefWithAttributes, attList);
  
  // ~~~~~~~~~~~~~~~~~~~ Compile into a single featureCollection, validate geometries, and export
  
  // Merge newly digitized and georeferenced boundaries 
  var mergedBoundariesWithAttributes = existingGeorefWithAttributes.merge(digGeorefWithAttributesAll); // Map.addLayer(mergedBoundariesWithAttributes)
  
  // Recalculate area and save as integer
  var mergedBoundariesWithAttributes_OUT = mergedBoundariesWithAttributes.map(function(f){return f.set({area: f.geometry(geomErrorMargin).area(geomErrorMargin).toInt()})})
  
  // Build out selectors
  var attNames  = attList.map(function(d){ return d.name; }); // ["AVtype","area",...]
  var outSelectors = ['Source', '.geo'].concat(attNames);
  
  // Merge newPanelRows from current script with previous version digitizations (digGeoref)
  Export.table.toAsset({
    collection: mergedBoundariesWithAttributes_OUT, 
    description: "assetExportFinalArraySHP_"+gridCellID, 
    assetId: assetFolder+"/GMSEUS"+version+"_digGeorefArrays_"+gridCellID, 
    maxVertices: 1e9});
  Export.table.toDrive({
    collection: mergedBoundariesWithAttributes_OUT,
    description:'GMSEUS'+version+'_digGeorefArrays_'+gridCellID,
    fileFormat: 'GeoJSON',
    folder: date+"digGeorefArrays_"+version,
    selectors: outSelectors});
}; 

// Create grid sequence and iterate over list
//var gridSequence = grid.aggregate_array(gridCellIDtag).getInfo();
var gridSequence = ['AL', 'AZ', 'AR', 'CA', 'CO', 'CT', 'DE', 'FL', 'GA', 'ID',
                    'IL', 'IN', 'IA', 'KS', 'KY', 'LA', 'ME', 'MD', 'MA', 'MI',
                    'MN', 'MS', 'MO', 'MT', 'NE', 'NV', 'NH', 'NJ', 'NM', 'NY',
                    'NC', 'ND', 'OH', 'OK', 'OR', 'PA', 'RI', 'SC', 'SD', 'TN',
                    'TX', 'UT', 'VT', 'VA', 'WA', 'WV', 'WI', 'WY', 'DC'];

// Iterate across states
gridSequence.forEach(function(cell){ 
  exportDigGeorefByState(cell); 
});
//*/