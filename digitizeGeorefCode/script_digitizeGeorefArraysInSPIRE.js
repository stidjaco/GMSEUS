//########################################################################################################################################## 
//#                                                                                                                                      #\\
//#                                        Digitize Array Bounds for Existing Database Point Locations                                   #\\
//#                                                                                                                                      #\\
//##########################################################################################################################################
 
/*
-- Information --
Author: Jacob Stid
Date Created: 07-18-2024
Date Updated: 11-16-2024
Contact: stidjaco@msu.edu (Jacob Stid)
 
-- Notes --
* We can steal new array shapes from the existing array shape database if they exist. 
* This is optimal if available, and often the case for arrays outside 190m. 
* If this is the case, draw shapes within existing array shape associated with a toDigitize array, and draw a lineString connecting the shape with arraysToDigitize. We will copy attributes later.
* If only part of the array is covered by existing array shapes, finish digitization and ensure overlap with existing shape and draw the lineString. We will merge this later.
* Each new or existing shape should be intersected by A) the current array to digitize buffer or B) a "Draw a Line" line through the shape and the buffer. 

Initial tests for connecting line methods: 
* Kost Trail Solar, Snipesville II Solar Farm, Norelius Solar, Alden Road Harvard Solar 1, Bluff Country Solar  -- compare these to American Bottoms (no line)
* In the end, check Aspiration G and Giffen Solar Park, should be distinct even though very close togehter
* THE PERFECT PROXIMITY LINE TEST: ['Catskill View Solar Farm', 'Claverack Creek Solar Farm'] // May have to do initial buffer?
* check for other arrays which we might have to selectively connect to new shapes where nearest distance isnt a good enough metric
* Going to have to union new array, then union with intersecting existing arrays, then find intersecting or nearest toDigitize point location to connect attributes to. 

Auxiliary Note: 
* We originally digitized Hoot Lake Solar from InSPIRE, prior to V2.0 of USPVDB. However, V7 contains only the completed arrays as of 2023 (partial), we included additional newly digitized array area. Our digitization is thus more complete than USPVDB and we kept the added value. 
*/

//###################\\
//  Call Solar Data  \\
//###################\\

// Call in solar database to digitize
var toDigitizeID = 'projects/ee-stidjaco/assets/BigPanel/points_toDigitize';

// Call existing array shapes to see if buffer distance just did not catch existing shape
var existingArraysID = 'projects/ee-stidjaco/assets/BigPanel/existingDatasetArrayShapes'; 

// Call all existing points (to check after digitization process for removal of new array bounds)
var allPointsID = 'projects/ee-stidjaco/assets/BigPanel/points_all';

// Set date
var date = '101524';

// Call all digitized and georeferenced arrays from prior script iterations
var newDigGeoRef_v2_asset0 = 'projects/ee-asterellsworth/assets/newDigGeoRef_v2_asset_0';
var newArrays_v2_asset0 = 'projects/ee-asterellsworth/assets/newArrays_v2_asset_0';
var newDigGeoRef_v2_asset1 = 'projects/ee-asterellsworth/assets/newDigGeoRef_v2_asset_1';
var newArrays_v2_asset1 = 'projects/ee-asterellsworth/assets/newArrays_v2_asset_1';
var dupPolys_v2_asset1 = 'projects/ee-asterellsworth/assets/duplicatePolys_v2_asset_1'; 
var newDigGeoRef_v2_asset2 = 'projects/ee-asterellsworth/assets/newDigGeoRef_v2_asset_2';
var newArrays_v2_asset2 = 'projects/ee-asterellsworth/assets/newArrays_v2_asset_2';
var dupPolys_v2_asset2 = 'projects/ee-asterellsworth/assets/duplicatePolys_v2_asset_2'; 

//######################################\\
// Preparation and Cloud Mask Functions \\
//######################################\\

// Call the digitizing dataset
var arraysToDigitize = ee.FeatureCollection(toDigitizeID);
var arraysToDigitize = arraysToDigitize.filter(ee.Filter.eq("Source", "InSPIRE")); // For v1.0, we are only digitizing InSPIRE arrays as proof of concept. 

// Call the existing dataset
var existingArrays = ee.FeatureCollection(existingArraysID);

// Call the all points dataset
var allPoints = ee.FeatureCollection(allPointsID);
var allPoints = allPoints.filter(ee.Filter.eq("Source", "InSPIRE")); // For v1.0, we are only digitizing InSPIRE arrays as proof of concept. 

// Get digitized and georeferenced arrays from previous script iterations
var digGeoref_0 = ee.FeatureCollection(newDigGeoRef_v2_asset0);
var newArrays_0 = ee.FeatureCollection(newArrays_v2_asset0);
var digGeoref_1 = ee.FeatureCollection(newDigGeoRef_v2_asset1);
var newArrays_1 = ee.FeatureCollection(newArrays_v2_asset1);
var dupPolys_1 = ee.FeatureCollection(dupPolys_v2_asset1);
var digGeoref_2 = ee.FeatureCollection(newDigGeoRef_v2_asset2);
var newArrays_2 = ee.FeatureCollection(newArrays_v2_asset2);
var dupPolys_2 = ee.FeatureCollection(dupPolys_v2_asset2);

// Bring together digGeoref, newArrays, and dupPolys to map
var digGeoref = digGeoref_0.merge(digGeoref_1).merge(digGeoref_2);
var newArrays = newArrays_0.merge(newArrays_1).merge(newArrays_1);
var dupPolys = dupPolys_1.merge(dupPolys_2);

// Cloud masking functions sentinel
function maskS2clouds(image) {
  var qa = image.select('QA60');
  // Bits 10 and 11 are clouds and cirrus, respectively.
  var cloudBitMask = 1 << 10;
  var cirrusBitMask = 1 << 11;
  // Both flags should be set to zero, indicating clear conditions.
  var mask = qa.bitwiseAnd(cloudBitMask).eq(0)
      .and(qa.bitwiseAnd(cirrusBitMask).eq(0));
  return image.updateMask(mask).divide(10000);}
  
// Cloud and Shadow masking landsat
function LSfmask(img) {
  var cloudShadowBitMask = 1 << 3;
  var cloudsBitMask = 1 << 5;
  var qa = img.select('QA_PIXEL');
  var mask = qa.bitwiseAnd(cloudShadowBitMask)
                 .eq(0)
                 .and(qa.bitwiseAnd(cloudsBitMask).eq(0));
  return img.updateMask(mask);
}
  
// Applies scaling factors.
function applyLS_ScaleFactors(image) {
  var opticalBands = image.select('SR_B.').multiply(0.0000275).add(-0.2);
  var thermalBands = image.select('ST_B.*').multiply(0.00341802).add(149.0);
  return image.addBands(opticalBands, null, true)
              .addBands(thermalBands, null, true);
}


// ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ When digitizing, uncomment



//##################################################\\
// Get toDigitize arrays without digitized boundary \\
//##################################################\\

//This is an iterative process, each time the script is run, the first missing boundary is displayed. 
//This ensures that all arrays are either digitized, or removed due to a lack of imagery. If array is 
//present in imagery, digitize array boundary (panels + spacing) following Fujita et al. (2023) logic. 
//If no panels are present, add nativeID to noPanelsPresent list. To start from scratch, create empty 
//lists

// Set list of nativeID's where no panels exist in imagery. Take notes for each
var noPanelsPresent = [
  'California: Habitat & Wildlife Monitoring', // No apparent array, lots of parking lot and rooftop solar at US Davis
  'SoliCulture Greenhouse', // Not apparent in imagery, small possibly temp greenhouse, website: https://www.agrisolarclearinghouse.org/case-study-soliculture-research-greenhouse/
  'Haywood Solar Farm', // Not apparent array in imagery, web search reveals Haywood Solar Farm at Tennessee Welcome Center nearly 20 miles away: webstie: https://www.tnvacation.com/local/stanton-i-40-haywood-county-solar-farm-welcome-center
  'Saffron in Vermont', // Not apparent in imagery, a lot of solar in vermont, also, apparently this array is in New Haven, point locaiton is iSun (Burlington) so incorrect location, webstie: https://www.uvm.edu/~saffron/info/reports/FinalreportiSunFebruary22022.pdf
  'CSU Spur Campus - Rooftop Agrivoltaics', // Present in NAIP imagery, but rooftop
  'LeGore Bridge Solar Center', // Not present in NAIP imagery, likely to commense in 2024, website: https://www.power-technology.com/data-insights/power-plant-profile-legore-bridge-solar-project-us/
  'Summit Plant Labs', // Possibly present in imagery, small vertical bifacial array, website: https://www.agrisolarclearinghouse.org/case-study-summit-plant-labs/
  'Sunzaun Somerset Winery', // Winery is km from location, small vertical bifaical array, website: https://sunzaun.com/projects/
  'Joe Czajkowski Farm', // No NAIP -- 2023, small array, not apparent in Maxar, set to be completed in 2023, website: https://www.agrisolarclearinghouse.org/case-study-joe-czajkowski-farm/
  'USDA-UGA AgSolar Synergy', // 2023, small, not apparent in imagery
  'Growing Green - Spaces of Opportunity', // 2023, small, not apparent in imagery
  'CSU Foothills Campus - Rooftop Agrivoltaics Research', // Present in NAIP imagery, small array, within 190m, but rooftop
  'Abel', // Likely present in NAIP imagery, likely an array to the south based on https://x.com/Interco81562188/status/1267874876901081088, but cannot confirm
  'Bunker Hill', // Likely present in NAIP imagery, likely arrays to east or west, but no web-source able to confirm
  'Giveback- Salsola mowing', // No NAIP -- 2022 (naip:2021), no existing solar to assume adjacent to centroid, little information online
  'Goodrich Solar', // No NAIP -- 2022 (naip:2021), no existing array in database, possibly undocumented array to the north east, but not enough information online, website: https://www.gem.wiki/USS_Goodrich_Solar
  'USS Peach', // Not apparent in imegery or online, several nearby arrays but not enough information to confirm
  'Foxhound Solar', // There is recently cleared forestland just south of the array, very likely the project boundary, but not able to confirm with context
  'Temple University Ambler Campus', // (2023) Not apprent in imagery, very small array, too small for Sentinel-2 imagery, 
  'Putnam Solar', // Not apparent in imagery, not apparent online
];
 
// Set list of nativeID's where array was digitized. Take notes for each.
var digitizedIDs = [
  'Monee Solar', //Present in NAIP imagery
  'Niagara University', // Counstruction boundary Present in NAIP imagery, https://news.niagara.edu/news/show/niagara-university-powers-up-on-campus-solar-array
  'Pivot Solar NY 4', // Present in NAIP imagery, https://der.nyserda.ny.gov/facilities/3444/?project=3301
  'Fountain', // Construction Boundary present in NAIP imagery, https://www.openstreetmap.org/way/1163126332
  'Falls Creek Garden', // Present in NAIP imagery
  'RE Adams East, LLC', // Present in NAIP imagery, https://www.openstreetmap.org/way/597046168
  'Animal Farm Cook Campus', // within 2.5km buffer, non-vertical array (website indicated that there also exists a vertical animal farm array), website: https://agrivoltaics.rutgers.edu/
  'Pivot Solar NY 5', // Present in Mazar imagery, construction boundaries present in sentinel imagery, https://dataint.s3.amazonaws.com/docs/proj_3314/database_notes-pivot_solar_ny5.pdf
  'Pivot Solar NY 6, LLC', // Present in Maxar imagery, partially built (2 of 3 sections), somewhat visible in 2023 sentinel imagery
  'Snyder Farm Pittstown', // Present in Maxar imagery, no other imagery, included space between two panel sections for ground cover, website: https://investors.solaredge.com/news-releases/news-release-details/rutgers-university-selects-solaredge-technologies-its
  'Spring Street Road II Solar Project', // Present in NAIP 2022, NAIP also taken in 2021, so had to subset for latest naip year, further than 190m, website: https://dec.ny.gov/news/environmental-notice-bulletin/2021-02-10/seqr/cayuga-county-the-village-of-union-springs-planning-board-as-lead-agency-has-determined-that-the-proposed-spring-street-road-ii-solar-project-will-not-have-a-significant-adverse-environmental-impact-the
  'University of Arizona Biosphere 2 Site', // Present in NAIP, best quality in NAIP 2019, small, difficult to delinate panels because so close
  'Massachusetts farm', // Present in NAIP imagery, single row of panels, through middle of farm
  'University of Massachusetts-Amherst', // Present in NAIP imagery, very small, three sets of split panels, website: https://ag.umass.edu/clean-energy/research-initiatives/solar-agriculture/researching-agricultural-economic-impacts-of-agrivoltaics-dual-use-solar
  'Melnik Farm', // Present in NAIP imagery, very small, 2 sets of panels
  'Cozy Cove Farm', // Present in NAIP imagery, 4 panel rows
  'Manzo Elementary School', // Present in NAIP imagery, 2 large panel rows
  'Red Horse', // Present in NAIP imagery, massive array, point location is 20km from installation, used USWTDB (known to be wind turbine adjacent) and website to find location: https://www.tep.com/red-horse-solar/
  'Five Points Solar Park', // Present in NAIP imagery, large array, just outside 190m, website: https://www.universityofcalifornia.edu/news/largest-university-solar-power-project-pushes-uc-toward-carbon-neutrality
  'Aspiration G', // Present in NAIP imagery, large array, in existing database, Giffen Solar Park is a different point to the southwest, website: https://www.gem.wiki/Aspiration_G_solar_farm
  'Giffen Solar Park', // Present in NAIP imagery, near aspiration G, but GEM has better accuracy location, website: https://www.gem.wiki/Giffen_Solar_Park
  'Frederick Urbana Solar', // Present in Maxar imagery, not NAIP imagery, visible in Sentinel-2 imagery
  'Seneca', // Present in NAIP imagery, just outside 190m, website: https://www.nexamp.com/project/seneca-solar
  'Colorado State University-ARDEC', // Present in NAIP imagery, under construction, ~300m away, website: https://source.colostate.edu/solar-installations-renewable-energy/
  'Gardiner Our Kids Farm', // Present in NAIP imagery, within 190m, small, website: https://green-ri.com/project/richmond-gardiner-our-kids-farm/
  'Hazel', // Under construction in NAIP imagery, ~250m from location, second array nearby (too small), website: https://www.gem.wiki/Hazel_solar_farm
  'Juno Solar Project', // Preset in NAIP imagery, 20km away, massive array (400+MW), website: https://www.google.com/maps/place/Juno+Solar+SB+Energy/@32.7627719,-101.6299153,8286m/data=!3m1!1e3!4m6!3m5!1s0x86fec73fba750e03:0x23d818789cdebdef!8m2!3d32.7671548!4d-101.6508095!16s%2Fg%2F11sgdw22tv?entry=ttu&g_ep=EgoyMDI0MDkwMi4xIKXMDSoASAFQAw%3D%3D
  'Skipjack Solar Center', // **Partially present in NAIP imagery (construction), 1km away, massive array, exists in existingArray dataset, website: https://www.openstreetmap.org/relation/15510796
  'Snipesville III Ranch', // 2023, had to make some assumptions about I vs II vs III, Present in Maxar and Sentinel, large, part of large interconnected array, website: https://www.gem.wiki/Snipesville_solar_farm
  'Townsend Road (CSG)', // Present in NAIP imagery, ~300m away
  'Luciana', // **Present in NAIP imagery, present in existing database, 2km away, website: https://www.gem.wiki/Luciana_solar_farm, moreso: https://www.google.com/maps/place/Luciana+Solar+Facility/@35.8117826,-119.0693141,8512m/data=!3m1!1e3!4m6!3m5!1s0x80eaed17e8ae26d7:0xbb776c3752cc4060!8m2!3d35.8126853!4d-119.0572842!16s%2Fg%2F11v0cr8hl6?entry=ttu&g_ep=EgoyMDI0MDkxMS4wIKXMDSoASAFQAw%3D%3D
  'Washington I', // Not present in NAIP imagery, but exsits in database, ~200m away, assumed to be both shapes
  'Solar Harvest', // 2023, Present in Maxar, three small separated sections
  'Verduin Community Solar Project', // 2023, Present in Maxar, not apparent online, present in existing database
  'Sagitta Community Solar', // Present in NAIP imagery, ~500m away, exists in existing database
  'Bighorn Solar', // Present in NAIP, 200m away, exists in existing database, large array
  'University of Minnesota Morris West Central Research and Outreach Center', // Exists in NAIP imagery, small 2 row array
  "Mauntel's Solar Sheep", // Exists in NAIP imagery, exists in database
  'Borner', // Exists in NAIP imagery, exists in database
  'Kirkland Project 1', // Exists in Maxar imagery, 300m away
  'Mennie South FC PV', // Exists in NAIP imagery, exists in database, website: https://www.nexamp.com/project/mennie-south-fc
  'OE Solar 2 Blazing Star', // Exists in NAIP imagery, 500m away
  'Shamrock/Blue Prarie', // Present in NAIP imagery, exists in database, webstie: https://s3.amazonaws.com/hoth.bizango/assets/23625/OneEnergy_CaseStudy_BluePrairie042622.pdf
  'York Solar', // Present in NAIP imagery, within 190m
  'Sussex Conservation District', // Present in NAIP imagery, small array, 4 panels
  'Marstons Mills', // Present in NAIP imagery, 250m meters from location, website: https://www.capecodcommission.org/resource-library/file?url=%2Fdept%2Fcommission%2Fteam%2FWebsite_Resources%2FProjectFiles%2FOldFalmouthRoadSolar%2F2016-08-15+Marstons+Mills+Solar+Appendix+R_Site+Plans.pdf
  'Domino Farms Solar Farm', // Present in NAIP imgagery, 500m away, website: https://www.jranck.com/project/dominos-farms/
  'Capella Community Solar', // Present in NAIP imagery, exists in database, website: https://www.pipestonestar.com/articles/second-solar-array-approved-for-rural-pipestone-county/
  'Crater Community Solar', // Present in NAIP imagery, 500m away, exists in database, website: https://www.gem.wiki/Crater_Community_Solar
  'Pegasus Community Solar', // Present in NAIP imagery, 1km away, exists in database, website: https://www.wctrib.com/business/minnesotas-largest-solar-farm-project-moving-ahead-in-far-southwestern-corner
  'Antares Community Solar', // Present in NAIP imagery, 200m away, exists in database
  'Cornillie', // Present in NAIP imagery, 220m away, exists in database, based on context, only one of the nearby systems, website: https://www.newenergyequity.com/Projects/?id=105
  'Delphinus Community Solar', // Present in NAIP imagery, 300m away, one existing, one new install, webstie: https://www.gem.wiki/Delphinus_Community_Solar
  'Rockpoint solar', // Present in NAIP imagery, 1km, website: https://www.us-solar.com/solar-garden/uss-rockpoint-solar-llc
  'Solar Dawn', // Present in NAIP imagery, 200m away
  'Aquarius Community Solar', // Present in NAIP imagery, exists in database, 1km away, website: https://www.mvp.usace.army.mil/Portals/57/docs/regulatory/approvjds_mn/2017-03674-JTB%20AJD.pdf?ver=2018-06-04-143951-773
  'University of Dayton - Curran Place', // Present in NAIP imagery, within 190m
  'Amherst Sunderland Road', // Present in NAIP imagery, 5km away, inferrred from website: https://www.google.com/maps/place/Sunderland+Rd,+Massachusetts/@42.4540171,-72.5639507,27548m/data=!3m1!1e3!4m6!3m5!1s0x89e6d296dc6a1fbb:0xbb5ade8ff9b96542!8m2!3d42.4193562!4d-72.5353044!16s%2Fg%2F1tdb9w5h?entry=ttu&g_ep=EgoyMDI0MDkwMi4xIKXMDSoASAFQAw%3D%3D
  'Cambridge Solar', // Present in NAIP imagery, within 190m
  'Cople', // Present in NAIP imagery, within 190m
  'Hockey Pad Solar', // Present in NAIP imagery, 500m, exists in database, website: https://www.us-solar.com/solar-garden/uss-hockey-pad-solar-llc
  'Kost Trail Solar', // Preset in NAIP imagery, exists in database, far away, website: https://www.openstreetmap.org/way/1159699147#map=14/45.49385/-92.87696
  'MSC-Empire01, LLC (Empire)', // Present in NAIP imagery, exists in database, 250m
  'Norelius Solar', // Present in NAIP imagery, exists in database, 250m away, OSM confirmed, other existing solar adjacent 
  'Solar Pollinator Habitat Discovery Trail', // Present in NAIP imagery, within 190m
  'Alden Road Harvard Solar 1', // Present in NAIP imagery, exists in database, ~250m away, website: https://www.nexamp.com/project/alden-road-harvard-solar 
  'American Bottoms', // Present in NAIP imagery, exists in databse, ~300m away, validated using Google Maps
  'Bluff Country Solar', // Present in NAIP imagery, exists in database, ~1km away, website: https://www.us-solar.com/solar-garden/uss-bluff-country-solar-llc
  'Cougar Solar', // Present in NAIP imagery, exists in database, ~300m away, website: https://www.us-solar.com/solar-garden/uss-cougar-solar-llc
  'Centaurus Community Solar', // Present in NAIP, nearly 100km away, incorrect location, website: https://www.gem.wiki/Centaurus_Community_Solar
  'Lyra Community Solar', // Present in NAIP imagery, ~1km away, website: https://www.openstreetmap.org/way/1160312880
  'FastSun 2', // Present in NAIP imagery, exists in database, ~300m away, website: https://www.openstreetmap.org/way/991389022#map=16/44.52893/-92.97227&layers=P
  'Georgetown Project', // Present in NAIP imagery, within 190m
  'JJ Clay Solar', // Present in NAIP imagery, exists in Database, ~500m, website: https://www.us-solar.com/solar-garden/uss-jj-clay-solar-llc
  'KVPV Solar', // Present in NAIP imagery, exists in database, ~195m, website: https://www.us-solar.com/solar-garden/uss-kvpv-solar-llc
  'Lunenburg Settlers Solar', // Present in NAIP imagery, exists in database, ~200m away, website: https://www.gem.wiki/Settlers_Solar
  'Penn State Whitetail 2', // Present in NAIP imagery, exists in database, ~250m away, website: https://www.gem.wiki/Whitetail_Solar
  'Pheasant Solar', // Present in NAIP imagery, exists in database, ~700m away, website: https://www.gem.wiki/USS_Pheasant_Solar_CSG
  'Westeros Solar', // Present in NAIP imagery, exists in database, ~400m away, website: https://www.us-solar.com/solar-garden/uss-westeros-solar-llc
  'Chariot Solar', // Present in NAIP imagery, exists in database, unidentified new arrays, websites: https://www.us-solar.com/solar-garden/uss-chariot-solar-llc
  'USS Danube', // Not present in NAIP imagery, exists in database, website: https://www.gem.wiki/USS_Danube_Solar
  'Easton Wastewater Treatment Plant', // Present in NAIP imagery, exists in database, assumed based on proximity to treatment plant and ponds
  'Geauga', // Present in NAIP imagery, within 190m
  'Kass Solar', // Present in NAIP imagery, ~200m away, exists in database, website: https://www.us-solar.com/solar-garden/uss-kass-solar-llc
  'Randolph Central Schools: Winchester Community High School', // Present in NAIP imagery, within 190m
  'Riverstart Solar Park', // (GREAT ALL AROUND EXAMPLE ARRAY) Present in NAIP imagery, initial location is close to MASSIVE phase III (according to GEM), based on OSM, eastern portions make up the 200 MW, ~1km away, partially exists in database, website: https://www.openstreetmap.org/relation/14489854#map=14/40.05640/-85.04980
  'Rockford CS LLC 2 PV', // Present in NAIP imagery, exists in database, ~195m away
  'Shelburne Museum South', // Not present in NAIP imagery, present in Maxar imagery, within 190m
  'Somonauk Road Solar 1', // Present in NAIP imagery, exists in database, ~230m away, 
  'SunVest Solar', // Present in NAIP imagery, within 190m
  'Sunflower I (Connexus Solar Baldwin 1BDN)', // Present in NAIP imagery, ~290m away, exists in database, website: https://www.gem.wiki/Connexus_Solar_Baldwin_1BDN
  'Swanton School - Megan and Tyler', // Present in NAIP imagery, within 190m
  'Trumbell', // Present in NAIP imagery, within 190m
  'USS Water Town', // Present in NAIP imagery, exists in database, not a lot of info online, but assumed based on proximity and size, ~280m away
  'Auburn Renewables Solar Array', // Present in NAIP imagery, exists in database, 192m away
  'Catskill View Solar Farm', // Present in NAIP imagery (only 2022, two years here), partially within 190m, large array, a couple panels intersect another toDigitize array and had to be omitted for current methods, assumed to be west array due to centroid location and website: https://edenrenewables.com/claverack-creek-catskill-view, https://www.nexamp.com/project/claverack-solar 
  'Claverack Creek Solar Farm', // Present in NAIP imagery (only 2022, two years here), adjacent to Catskill View Solar Farm (shared project), a couple panels intersect another toDigitize array and had to be omitted for current methods, assumed to be east array based on location of centroid and website: https://www.nexamp.com/project/claverack-solar 
  'Hodag', // Present in NAIP imagery, exists in database, ~191m away
  'James Madison University ISAT Solar Facility', // Not present in NAIP imagery, present in Maxar imagery, within 190m
  'Alliant Energy Solar Farm at Iowa State University', // Not present in imagery, but project boundary is present in Sentinel-2 imagery, within 190m, website: https://www.alliantenergy.com/cleanenergy/whatyoucando/customerhostedrenewables/iowastateuniversitysolar
  'Sherco Solar Phase 1', // (2023) Partially present in Maxar, underconstruction in Sentinel-2 imagery, assumed boundary based on S2 project boundary
  'Connexus Energy HQ: Solar Farmland for Emerging Farmers', // Present in NAIP imagery, within 190m
  'National Center for Appropriate Technology', // Present in NAIP imagery, within 190m, small two row array
  'Carter Farms', // Present in NAIP imagery, exists in database, ~400m away, website: https://inhabitat.com/jimmy-carter-built-a-new-solar-plant-on-his-old-peanut-farm/carter-farm-solar-panels-full-width-tall/
  'Organic Valley', // Present in NAIP imagery, exists in database, ~15km away, near wind turbine, website: https://www.wpr.org/economy/organic-valley-becomes-completely-reliant-renewable-power
  'Maple City', // Not present in NAIP imagery, present in Sentinel-2 imagery, ~500m away, website: https://www.google.com/maps/place/Maple+City+Solar,+LLC/@43.2717731,-92.7942064,1561m/data=!3m2!1e3!4b1!4m6!3m5!1s0x87f0f30f7615b7db:0xad20d7f9b09d031c!8m2!3d43.2717731!4d-92.7916315!16s%2Fg%2F11krgjw3wf?entry=ttu&g_ep=EgoyMDI0MDkxNS4wIKXMDSoASAFQAw%3D%3D
];


// Filter arraysToDigitize to exclude those in the lists above
var arraysRemaining = arraysToDigitize
  .filter(ee.Filter.inList("nativeID", noPanelsPresent).not())
  .filter(ee.Filter.inList("nativeID", digitizedIDs).not());
  
// If you need to compare lists, manually check lists, select for erroneously digitized arrays
//var existingDig = arraysToDigitize.aggregate_array('nativeID').sort(); print(existingDig)
//var digLists = ee.List(digitizedIDs).cat(noPanelsPresent).sort(); print(digLists);
//var digToRemove = digLists.filter(ee.Filter.inList('item', existingDig).not()); print(digToRemove);
//var checkDigID = "Winona II"; var checkDigArray = allPoints.filter(ee.Filter.eq("nativeID", checkDigID)); Map.addLayer(checkDigArray); Map.centerObject(checkDigArray); Map.addLayer(existingArrays, {}, "Existing Arrays", true)

/*
//###############################################\\
// Call, Process, and Display Imagery and Arrays \\
//###############################################\\

// Select current array to digitize. Get a buffer for clipping imagery. Print details. 
var currentArray = ee.Feature(arraysRemaining.first()); 
var currentBuffer = currentArray.geometry().buffer(20000); // 20km
print("Source: "+currentArray.get("Source").getInfo());
print("Installation Year: "+currentArray.get("instYr").getInfo());
print("nativeID: "+currentArray.get("nativeID").getInfo());
print("Capacity: "+currentArray.get("cap_mw").getInfo());

// Print number of arrays remaining
print("Arrays remaining: "+arraysRemaining.size().getInfo())
print(currentArray)

// Call in NAIP imagery
var naipStart = 2021;
var naipEnd = 2022;
var naip = ee.ImageCollection('USDA/NAIP/DOQQ').filterDate(naipStart+'-1-01', naipEnd+'-12-31').median().select("R", "G", "B").clip(currentBuffer); 

// Call in Landsat and Sentinel-2 and clip by array buffered boundary for efficiency
var start = 2023;
var end = 2023;
var ls = ee.ImageCollection('LANDSAT/LC09/C02/T1_L2').filterDate(start+'-5-01', end+'-10-31').map(LSfmask).map(applyLS_ScaleFactors).mean().select("SR_B4", "SR_B3", "SR_B2").clip(currentBuffer); 
var s2 = ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED").filterDate(start+'-5-01', end+'-10-31').filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE',10)).map(maskS2clouds).mean().select("B4", "B3", "B2").clip(currentBuffer); 

// Center on array and visualize
Map.centerObject(currentArray, 13)
Map.addLayer(naip, {}, "NAIP", false);
Map.addLayer(ls, {min: 0, max:0.3}, "Landsat", false);
Map.addLayer(s2, {min: 0, max:0.3}, "Sentinel-2", false);
Map.addLayer(existingArrays, {}, "Existing Arrays", true)
Map.addLayer(digGeoref.filterBounds(currentBuffer), {color: "blue"}, "Already digitized arrays", true); 
Map.addLayer(newArrays.filterBounds(currentBuffer), {color: "blue"}, "Already digitized new arrays", true); 
Map.addLayer(arraysToDigitize, {}, "Arrays to Digitize", true); 
Map.addLayer(currentArray, {}, "Current Array to Ditigize", true)

// Add USWTDB if using wind as a reference
//var USWTDB = ee.FeatureCollection('users/stidjaco/uswtdb_v6_1_20231128'); Map.addLayer(USWTDB, {}, 'USWTDB', false)
*/

// ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ EXPORT

/*
// Function to export newly digitized and georeferenced arrays to asset
var exportAsset = function(asset, name, scriptIter){
 Export.table.toAsset({
   collection: asset, 
   description: "Export_"+name+"_"+scriptIter, 
   assetId: name+"_asset_"+scriptIter, 
   maxVertices: 1e9, 
 });
};
 
// Export assets (once vertex limit is reached) -- then, save and start new script and add these as assets
exportAsset(newDigGeoRef_v2, "newDigGeoRef_v2", "inspire");
*/
