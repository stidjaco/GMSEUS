# Import Libraries
import geopandas as gpd
import pandas as pd
import numpy as np
import os
from shapely.ops import unary_union
import shapely.wkb as wkblib
from shapely.geometry import MultiPolygon, Point
import re
import json
import time
import hashlib
import requests

# Load OSM libraries and variables
import osmium as osm
import osmnx as ox
from osmnx._errors import InsufficientResponseError

ox.settings.use_cache = True
ox.settings.cache_folder = r"F:\OSM_Cache" # Create a local cache folder
ox.settings.overpass_url = 'https://overpass-api.de/api/interpreter' # "https://overpass.kumi.systems/api/interpreter"  # new name for endpoint

# Import gmseusUtils functions
import gmseusUtils as gu

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ Set Region and Country Name Dictionaries

# North America
UnitedStatesRegions = ['Alabama', 'Alaska', 'Arizona', 'Arkansas', 'California', 'Colorado', 'Connecticut', 'Delaware', 'Florida', 'Georgia', 'Hawaii', 'Idaho', 'Illinois', 'Indiana',
                        'Iowa', 'Kansas', 'Kentucky', 'Louisiana', 'Maine', 'Maryland', 'Massachusetts', 'Michigan', 'Minnesota', 'Mississippi', 'Missouri', 'Montana', 'Nebraska', 
                        'Nevada', 'New Hampshire', 'New Jersey', 'New Mexico', 'New York', 'North Carolina', 'North Dakota', 'Ohio', 'Oklahoma', 'Oregon', 'Pennsylvania', 'Rhode Island', 
                        'South Carolina', 'South Dakota', 'Tennessee', 'Texas', 'Utah', 'Vermont', 'Virginia', 'Washington', 'West Virginia', 'Wisconsin', 'Wyoming', "District of Columbia"]
CanadaRegions = ['Alberta', 'British Columbia', 'Manitoba', 'New Brunswick', 'Newfoundland and Labrador', 'Northwest Territories', 'Nova Scotia', 'Nunavut', 'Ontario', 
                 'Prince Edward Island', 'Quebec', 'Saskatchewan', 'Yukon']
MexicoRegions = ['Aguascalientes', 'Baja California', 'Baja California Sur', 'Campeche', 'Chiapas', 'Chihuahua', 'Coahuila de Zaragoza', 'Colima', 'Durango', 'Guanajuato', 'Guerrero', 
                 'Hidalgo', 'Jalisco', 'Michoacán de Ocampo', 'Morelos', 'Nayarit', 'Nuevo León', 'Oaxaca', 'Puebla', 'Querétaro', 'Quintana Roo', 'San Luis Potosí', 'Sinaloa', 'Sonora', 
                 'Tabasco', 'Tamaulipas', 'Tlaxcala', 'Veracruz de Ignacio de la Llave', 'Yucatán', 'Zacatecas']  
BelizeRegions = ['Belize District', 'Cayo District', 'Corozal District', 'Orange Walk District', 'Stann Creek District', 'Toledo District']
GuatemalaRegions = ['Alta Verapaz', 'Baja Verapaz', 'Chimaltenango', 'Chiquimula', 'El Progreso', 'Escuintla', 'Guatemala', 'Huehuetenango', 'Izabal', 'Jalapa', 'Jutiapa', 'Petén', 
                    'Quetzaltenango', 'Quiché', 'Retalhuleu', 'Sacatepéquez', 'San Marcos', 'Santa Rosa', 'Sololá', 'Suchitepéquez', 'Totonicapán', 'Zacapa'] 
HondurasRegions = ['Atlántida', 'Choluteca', 'Colón', 'Comayagua', 'Copán', 'Cortés', 'El Paraíso', 'Francisco Morazán', 'Gracias a Dios', 'Intibucá', 'Islas de la Bahía', 'La Paz', 
                   'Lempira', 'Ocotepeque', 'Olancho', 'Santa Bárbara', 'Valle', 'Yoro']
ElSalvadorRegions = ['Ahuachapán', 'Cabañas', 'Chalatenango', 'Cuscatlán', 'La Libertad', 'La Paz', 'La Unión', 'Morazán', 'San Miguel', 'San Salvador', 'San Vicente', 'Santa Ana', 
                     'Sonsonate', 'Usulután']
NicaraguaRegions = ['Boaco', 'Carazo', 'Chinandega', 'Chontales', 'Estelí', 'Granada', 'Jinotega', 'León', 'Madriz', 'Managua', 'Masaya', 'Matagalpa', 'Nueva Segovia', 'Rivas', 
                    'Río San Juan', 'Región Autónoma Costa Caribe Norte', 'Región Autónoma Costa Caribe Sur']
CostaRicaRegions = ['San José', 'Alajuela', 'Cartago', 'Heredia', 'Guanacaste', 'Puntarenas', 'Limón']
PanamaRegions = ['Bocas del Toro', 'Chiriquí', 'Coclé', 'Colón', 'Darién', 'Herrera', 'Los Santos', 'Panamá', 'Panamá Oeste', 'Veraguas', 'Ngäbe-Buglé Comarca', 'Guna Yala', 'Emberá-Wounaan']
CubaRegions = ['Pinar del Río', 'Artemisa', 'La Habana', 'Mayabeque', 'Matanzas', 'Cienfuegos', 'Villa Clara', 'Sancti Spíritus', 'Ciego de Ávila', 'Camagüey', 'Las Tunas', 'Holguín', 
               'Granma', 'Santiago de Cuba', 'Guantánamo', 'Isla de la Juventud']
JamaicaRegions = ['Kingston', 'Saint Andrew', 'Saint Thomas', 'Portland', 'Saint Mary', 'Saint Ann', 'Trelawny', 'Saint James', 'Hanover', 'Westmoreland', 'Saint Elizabeth', 'Manchester', 
                  'Clarendon', 'Saint Catherine']
HaitiRegions = ['Artibonite', 'Centre', 'Grand\'Anse', 'Nippes', 'Nord', 'Nord-Est', 'Nord-Ouest', 'Ouest', 'Sud', 'Sud-Est']
DominicanRepublicRegions = ['Azua', 'Baoruco', 'Barahona', 'Dajabón', 'Distrito Nacional', 'Duarte', 'Elías Piña', 'El Seibo', 'Espaillat', 'Hato Mayor', 'Hermanas Mirabal', 'Independencia', 
                            'La Altagracia', 'La Romana', 'La Vega', 'María Trinidad Sánchez', 'Monseñor Nouel', 'Monte Cristi', 'Monte Plata', 'Pedernales', 'Peravia', 'Puerto Plata', 
                            'Samaná', 'San Cristóbal', 'San José de Ocoa', 'San Juan', 'San Pedro de Macorís', 'Sánchez Ramírez', 'Santiago', 'Santiago Rodríguez', 'Valverde']
GreenlandRegions = ['Avannaata Kommunia', 'Kommuneqarfik Sermersooq', 'Qeqertalik', 'Qeqqata Kommunia', 'Kommune Kujalleq']
BermudaRegions = ['Devonshire Parish', 'Hamilton Parish', 'Paget Parish', 'Pembroke Parish', 'Sandys Parish', 'Smith\'s Parish', 'Southampton Parish', 'St. George\'s Parish', 'Warwick Parish']

# Create a dictionary of country names and their respective regions
countryRegionsDict = {
    'USA': UnitedStatesRegions, 'Canada': CanadaRegions, 'Mexico': MexicoRegions, 'Belize': BelizeRegions, 'Guatemala': GuatemalaRegions, 'Honduras': HondurasRegions, 'El Salvador': ElSalvadorRegions,
    'Nicaragua': NicaraguaRegions, 'Costa Rica': CostaRicaRegions, 'Panama': PanamaRegions, 'Cuba': CubaRegions, 'Jamaica': JamaicaRegions, 'Haiti': HaitiRegions, 'Dominican Republic': DominicanRepublicRegions,
    'Greenland': GreenlandRegions, 'Bermuda': BermudaRegions}



# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ Bulk (PBF) OpenStreetMap Functions
# Workflow for the bulk method (alternative to the Overpass API used by default):
#   1. downloadGeofabrikPBF()  -> download a regional extract (e.g., 'north-america') or use an existing planet.osm.pbf
#   2. extractSolarFromPBF()   -> ONE pass over the PBF that keeps only solar features and saves them to a small GeoPackage
#   3. processSolarOSMData(..., method='pbf', osmSolar=<GeoPackage path or loaded gdf>) clips that file per region
# NOTE: Geofabrik 'north-america' covers USA, Canada, Mexico, and Greenland. Central America/Caribbean countries are in 'central-america'. Planet covers all.

# Solar tags used for both methods (any feature with either tag is kept; arrays vs panels are split later by 'power')
solarTagFilter = {"plant:source": "solar", "generator:source": "solar"}

# Define a function to download an OSM extract from Geofabrik (https://download.geofabrik.de/)
def downloadGeofabrikPBF(geofabrikRegion, outDir, overwrite=False, checkMD5=True):
    # geofabrikRegion: Geofabrik path without '-latest.osm.pbf', e.g., 'north-america', 'north-america/us', 'north-america/canada', 'central-america', 'north-america/us/rhode-island'
    url = f"https://download.geofabrik.de/{geofabrikRegion}-latest.osm.pbf"
    gu.checkFolder(outDir)
    outPath = os.path.join(outDir, geofabrikRegion.split('/')[-1] + '-latest.osm.pbf')

    # Skip if already downloaded
    if os.path.exists(outPath) and not overwrite:
        print(f"PBF already exists, skipping download: {outPath}")
        return outPath

    # Stream to a temporary .part file, then rename when complete (avoids treating a partial download as finished)
    tmpPath = outPath + '.part'
    print(f"Downloading {url} -> {outPath}")
    with requests.get(url, stream=True, timeout=60) as r:
        r.raise_for_status()
        fileURL = r.url  # '-latest' redirects to a dated snapshot (e.g., .../rhode-island-261118.osm.pbf); its checksum lives next to it
        print(f"  Snapshot: {fileURL.split('/')[-1]}")
        totalBytes = int(r.headers.get('content-length', 0))
        doneBytes, nextReport, start = 0, 0, time.time()
        with open(tmpPath, 'wb') as f:
            for chunk in r.iter_content(chunk_size=16 * 1024 * 1024):
                f.write(chunk)
                doneBytes += len(chunk)
                if doneBytes >= nextReport:
                    pct = f" ({100 * doneBytes / totalBytes:.1f}%)" if totalBytes else ""
                    print(f"  {doneBytes / 1e9:.2f} GB{pct}, {(time.time() - start) / 60:.1f} min elapsed")
                    nextReport += 1e9  # report every ~1 GB

    # Optionally verify against Geofabrik's published MD5 checksum
    if checkMD5:
        md5Response = requests.get(fileURL + '.md5', timeout=60)
        md5Response.raise_for_status()
        expected = md5Response.text.split()[0]
        md5 = hashlib.md5()
        with open(tmpPath, 'rb') as f:
            for block in iter(lambda: f.read(64 * 1024 * 1024), b''):
                md5.update(block)
        if md5.hexdigest() != expected:
            raise ValueError(f"MD5 mismatch for {tmpPath} (expected {expected}, got {md5.hexdigest()}). Delete it and re-download.")
        print("  MD5 checksum verified.")

    os.replace(tmpPath, outPath)
    print(f"Download complete: {outPath}")
    return outPath

# Define a function that extracts all solar features from a PBF file (planet or regional extract) in a single pass and saves them to a GeoPackage
def extractSolarFromPBF(pbfPath, outPath, overwrite=False, keepFiltered=False):
    # pbfPath: path to .osm.pbf (e.g., planet-251124.osm.pbf or north-america-latest.osm.pbf)
    # outPath: output GeoPackage (.gpkg) holding all solar polygons (EPSG:4326) with columns: element, id, tags (JSON string), geometry

    if os.path.exists(outPath) and not overwrite:
        print(f"Solar extract already exists, skipping: {outPath}")
        return outPath
    gu.checkFolder(os.path.dirname(outPath))

    # Step 1: Filter the PBF down to solar-tagged ways/relations plus every node/way they reference (equivalent to 'osmium tags-filter').
    # Reading only ways and relations in this pass avoids decoding billions of nodes; BackReferenceWriter then adds the referenced nodes/member ways.
    filteredPBF = os.path.splitext(outPath)[0] + '_filtered.osm.pbf'
    start = time.time()
    print(f"Step 1/2: Filtering solar features from {pbfPath} (planet-sized files can take a few hours)...")
    solarFilter = osm.filter.TagFilter(*solarTagFilter.items())
    with osm.BackReferenceWriter(filteredPBF, ref_src=pbfPath, overwrite=True) as writer:
        for obj in osm.FileProcessor(pbfPath, osm.osm.WAY | osm.osm.RELATION).with_filter(solarFilter):
            writer.add(obj)
    print(f"  Filtered PBF written ({os.path.getsize(filteredPBF) / 1e6:.1f} MB) in {(time.time() - start) / 60:.1f} min")

    # Step 2: Assemble polygons (closed ways and multipolygon relations) from the small filtered file
    print("Step 2/2: Assembling solar polygons...")
    wkbfab = osm.geom.WKBFactory()
    rows, nFailed = [], 0
    for obj in osm.FileProcessor(filteredPBF).with_areas():
        if not obj.is_area():
            continue  # Non-closed ways (lines) and nodes are dropped downstream anyway
        tags = dict(obj.tags)
        if not any(tags.get(k) == v for k, v in solarTagFilter.items()):
            continue  # Untagged member ways of multipolygon relations also become areas; skip them
        try:
            geom = wkblib.loads(wkbfab.create_multipolygon(obj), hex=True)
        except Exception:
            nFailed += 1  # Broken/incomplete polygons (osmnx would also drop these)
            continue
        # Match osmnx: single-part polygons are returned as Polygon
        if isinstance(geom, MultiPolygon) and len(geom.geoms) == 1:
            geom = geom.geoms[0]
        rows.append({'element': 'way' if obj.from_way() else 'relation', 'id': obj.orig_id(),
                     'tags': json.dumps(tags, ensure_ascii=False), 'geometry': geom})

    solarGdf = gpd.GeoDataFrame(rows, geometry='geometry', crs='EPSG:4326')
    solarGdf.to_file(outPath, driver='GPKG')
    print(f"  {len(solarGdf)} solar polygons saved to {outPath} ({nFailed} invalid polygons skipped). Total {(time.time() - start) / 60:.1f} min")

    if not keepFiltered:
        os.remove(filteredPBF)
    return outPath

# Define a function to load the solar extract into the same structure osmnx returns (MultiIndex (element, id), one column per tag, EPSG:4326)
def loadSolarOSMExtract(extractPath):
    solarGdf = gpd.read_file(extractPath)
    tags = pd.DataFrame([json.loads(t) for t in solarGdf['tags']], index=solarGdf.index)
    solarGdf = pd.concat([solarGdf[['element', 'id', 'geometry']], tags], axis=1)
    solarGdf = gpd.GeoDataFrame(solarGdf, geometry='geometry', crs='EPSG:4326')
    return solarGdf.set_index(['element', 'id'])

# Define a function to select solar features for a region from the bulk extract (same place boundary and 'intersects' rule as ox.features_from_place)
def getRegionSolarFromExtract(place, solarGdf):
    aoiGeom = ox.geocode_to_gdf(place).to_crs('EPSG:4326').geometry.iloc[0]
    candidates = solarGdf.iloc[solarGdf.sindex.query(aoiGeom, predicate='intersects')]
    return candidates.dropna(axis=1, how='all')  # Drop tag columns unused in this region, as osmnx would

# Inverter tags (no settled OSM convention yet; see https://community.openstreetmap.org/t/creating-a-wiki-page-for-power-inverter/123380)
# power=inverter is the most used (~7.5k worldwide, Dec 2024); the others were proposed/used as alternatives. power=converter also covers HVDC converter stations.
inverterTagFilter = [('power', 'inverter'), ('power', 'converter'), ('power', 'inverter_station'), ('substation', 'inverter'), ('transformer', 'inverter')]

# Return the first inverter tag ('key=value') an OSM tag dict matches, or None
def matchInverterTag(tags):
    for k, v in inverterTagFilter:
        if tags.get(k) == v:
            return f'{k}={v}'
    return None

# Define a function that extracts all inverter features (nodes, ways, and relations) from a PBF file in a single pass and saves them to a GeoPackage
def extractInvertersFromPBF(pbfPath, outPath, overwrite=False, keepFiltered=False):
    # outPath: output GeoPackage (EPSG:4326) with columns: element, id, tags (JSON string), geometry (Point for nodes, Polygon/LineString for ways/relations)
    # NOTE: Unlike extractSolarFromPBF, this pass must also read nodes (most inverters are mapped as points), so it is slower (decodes every node in the file).

    if os.path.exists(outPath) and not overwrite:
        print(f"Inverter extract already exists, skipping: {outPath}")
        return outPath
    gu.checkFolder(os.path.dirname(outPath))

    # Step 1: Filter the PBF down to inverter-tagged objects plus every node/way they reference
    filteredPBF = os.path.splitext(outPath)[0] + '_filtered.osm.pbf'
    start = time.time()
    print(f"Step 1/2: Filtering inverter features from {pbfPath} (reads all nodes; expect longer than the solar extract)...")
    with osm.BackReferenceWriter(filteredPBF, ref_src=pbfPath, overwrite=True) as writer:
        for obj in osm.FileProcessor(pbfPath, osm.osm.NODE | osm.osm.WAY | osm.osm.RELATION).with_filter(osm.filter.TagFilter(*inverterTagFilter)):
            writer.add(obj)
    print(f"  Filtered PBF written ({os.path.getsize(filteredPBF) / 1e6:.1f} MB) in {(time.time() - start) / 60:.1f} min")

    # Step 2: Build geometries. Nodes -> Point; closed ways and multipolygon relations -> Polygon (via area assembly); open ways -> LineString
    print("Step 2/2: Building inverter geometries...")
    wkbfab = osm.geom.WKBFactory()
    rows, nFailed = [], 0
    for obj in osm.FileProcessor(filteredPBF).with_locations().with_areas():
        tags = dict(obj.tags)
        if matchInverterTag(tags) is None:
            continue  # Referenced nodes/member ways without inverter tags
        try:
            if obj.is_node():
                if not obj.location.valid():
                    continue
                element, osmID, geom = 'node', obj.id, Point(obj.location.lon, obj.location.lat)
            elif obj.is_area():
                element, osmID = ('way' if obj.from_way() else 'relation'), obj.orig_id()
                geom = wkblib.loads(wkbfab.create_multipolygon(obj), hex=True)
                if isinstance(geom, MultiPolygon) and len(geom.geoms) == 1:
                    geom = geom.geoms[0]
            elif obj.is_way() and not obj.is_closed():
                element, osmID, geom = 'way', obj.id, wkblib.loads(wkbfab.create_linestring(obj), hex=True)
            else:
                continue  # Closed ways are handled as areas; non-multipolygon relations are skipped
        except Exception:
            nFailed += 1
            continue
        rows.append({'element': element, 'id': osmID, 'tags': json.dumps(tags, ensure_ascii=False), 'geometry': geom})

    invGdf = gpd.GeoDataFrame(rows, geometry='geometry', crs='EPSG:4326')
    invGdf.to_file(outPath, driver='GPKG')
    print(f"  {len(invGdf)} inverter features saved to {outPath} ({nFailed} invalid geometries skipped). Total {(time.time() - start) / 60:.1f} min")
    print("  " + invGdf['element'].value_counts().to_string().replace('\n', ', '))

    if not keepFiltered:
        os.remove(filteredPBF)
    return outPath



# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ OpenStreetMap Functions

# Define a function that grabs all solar panel and array data from OSM for a given region
def getSolarOSMData(regionName, countryName, config, method='api', osmSolar=None):

    # config: dict from gu.load_config(), loaded once by the caller
    # method: 'api' (default) downloads from the Overpass API via osmnx; 'pbf' clips from a bulk solar extract built by extractSolarFromPBF()
    # osmSolar: (method='pbf' only) path to the solar extract GeoPackage, or the gdf already loaded with loadSolarOSMExtract()
    toCRS = config['to_crs']  # EPSG:6350 NAD83 (2011)
    toCRS = f'EPSG:{toCRS}'

    # Define your area of interest (e.g., 'Newfoundland and Labrador, Canada' or 'Michigan, USA')
    place = regionName + ', ' + countryName 

    # Define grouped tag for solar panels and arrays (NOTE: We will still have to filter out the arrays from panels)
    solarTags = solarTagFilter

    # API method: use OSMnx and Overpass API to download OSM solar data
    if method == 'api':
        # Retrieve the data from OSM
        try:
            # Try retrieving solar data
            print(f"{regionName}: Attempting to retrieve solar data...")
            solarData = ox.features_from_place(place, tags=solarTags)
        except InsufficientResponseError:
            print(f"No solar data found for {regionName}.")
            solarData = gpd.GeoDataFrame(geometry=[], crs=toCRS)
    # PBF method: select this region's features from the bulk solar extract (same structure as the osmnx output, so processing below is shared)
    elif method == 'pbf':
        if osmSolar is None:
            raise ValueError("method='pbf' requires osmSolar (path to the solar extract from extractSolarFromPBF, or the loaded gdf).")
        if isinstance(osmSolar, (str, os.PathLike)):
            osmSolar = loadSolarOSMExtract(osmSolar)
        print(f"{regionName}: Selecting solar data from bulk PBF extract...")
        solarData = getRegionSolarFromExtract(place, osmSolar)
        if solarData.empty:
            print(f"No solar data found for {regionName}.")
            solarData = gpd.GeoDataFrame(geometry=[], crs=toCRS)
    else:
        raise ValueError(f"Unknown method '{method}'. Use 'api' or 'pbf'.")

    # If solarData contains data, try to split into arrays and panels respectively. Otherwise build empty gdfs.
    # If only one exists and not the other (e.g., arrays but not panels), parse and build one empty gdf
    if solarData.empty:
        arrayData = gpd.GeoDataFrame(geometry=[], crs=toCRS)
        panelData = gpd.GeoDataFrame(geometry=[], crs=toCRS)
    else:
        # Prefer splitting by 'power'; fall back to which :source tag exists
        power = solarData.get("power")
        if power is not None:
            arrays_mask = power.eq("plant")
            panels_mask = power.eq("generator")
        else:
            arrays_mask = solarData.get("plant:source", "").eq("solar")
            panels_mask = solarData.get("generator:source", "").eq("solar")

        # Build outputs; if one mask yields zero rows, you still get a valid empty GeoDataFrame
        arrayData = solarData[arrays_mask].copy()
        panelData = solarData[panels_mask].copy()
 
    # First, check if 'geometry' column exists and clean DataFrames by removing non-Polygon geometries
    # Solves an issue where regions like West Virgina, do not have arrayData
    if 'geometry' in panelData.columns:
        panelData = panelData[panelData['geometry'].apply(lambda x: x.geom_type in ['Polygon', 'MultiPolygon'])]
    else:
        panelData = gpd.GeoDataFrame(columns=['geometry'])  # Empty GeoDataFrame if no geometry column
    if 'geometry' in arrayData.columns:
        arrayData = arrayData[arrayData['geometry'].apply(lambda x: x.geom_type in ['Polygon', 'MultiPolygon'])]
    else:
        arrayData = gpd.GeoDataFrame(columns=['geometry'])  # Empty GeoDataFrame if no geometry column

    ''' This code block tests for non-Polygon or MultiPolygon geometries in the dataframes.
    # Create the same if else structure but for not 'Polygon' or 'MultiPolygon' geometries
    # Solves an issue where regions like West Virgina, do not have arrayData
    if 'geometry' in panelData.columns:
        panelData = panelData[panelData['geometry'].apply(lambda x: x.geom_type not in ['Polygon', 'MultiPolygon'])]
    else:
        panelData = gpd.GeoDataFrame(columns=['geometry'])
    if 'geometry' in arrayData.columns:
        arrayData = arrayData[arrayData['geometry'].apply(lambda x: x.geom_type not in ['Polygon', 'MultiPolygon'])]
    else:
        arrayData = gpd.GeoDataFrame(columns=['geometry'])
    '''
    
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ arrayData

    # IF: arrayData is not empty, process arrayData
    if arrayData is not None and not arrayData.empty:

        # Set CRS as WGS84 (OSM native proj). Then, transform the data to toCRS CRS. Solves naive projection issues for emtpy array and panel
        arrayData = arrayData.set_crs('EPSG:4326')
        arrayData = arrayData.to_crs(toCRS)

        # Save the index as osmid
        arrayData['osmid'] = arrayData.index

        # Reset index
        arrayData = arrayData.reset_index(drop=True)

        # Save osmid as string
        arrayData['osmid'] = arrayData['osmid'].astype(str)

        # osmid column is currently structured as (way, 1155615180), we want only the number
        arrayData['osmid'] = arrayData['osmid'].str.split(', ').str[1].str.replace(')', '')

    # For arrayData, select the following columns: start_date, plant:method, osmid, source, name, plant:output:electricity, geometry
    # If any of these columns do not exist, create an empty column of NA values (as a string)
    # Rename them to: instYr, modType, nativeID, Source, ProjName, capMWDC, geometry
    # Ensure required columns exist, creating them with NA values if missing
    required_columns = {
        'start_date': 'instYr',
        'plant:method': 'modType',  
        'osmid': 'nativeID',
        'source': 'Source',
        'name': 'ProjName',
        'plant:output:electricity': 'capMWDC',
        'geometry': 'geometry'}
    for col, new_col in required_columns.items():
        if col not in arrayData.columns:
            arrayData[col] = pd.NA
        arrayData[new_col] = arrayData[col]
    
    # Select only the new columns
    arrayData = arrayData[list(required_columns.values())]

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ panelData

    # IF: panelData is not empty, process panelData
    if panelData is not None and not panelData.empty:

        # Set CRS as WGS84 (OSM native proj). Then, transform the data to toCRS CRS. Solves naive projection issues for emtpy array and panel
        panelData = panelData.set_crs('EPSG:4326')
        panelData = panelData.to_crs(toCRS)

        # Save the index as osmid
        panelData['osmid'] = panelData.index

        # Reset index
        panelData = panelData.reset_index(drop=True)

        # Save osmid as string
        panelData['osmid'] = panelData['osmid'].astype(str)

        # osmid column is currently structured as (way, 1155615180), we want only the number
        panelData['osmid'] = panelData['osmid'].str.split(', ').str[1].str.replace(')', '')

        '''If we want rooftop data, comment out this block and for any rooftop classification, do not do createArrayFromPanels. Otherwise, creates arrays that are rooftop solar connected across houses. Also, need to modify minPanelRowArea to prevent dropping of small panels.'''
        # From panelData, remove all rows where 'location', 'building', or 'generator:place' column is = 'roof'. 
        # If these columns are not present, do nothing.
        if 'location' in panelData.columns:
            panelData = panelData[~panelData['location'].isin(['roof'])]
        if 'building' in panelData.columns:
            panelData = panelData[~panelData['building'].isin(['roof'])]
        if 'generator:place' in panelData.columns:
            panelData = panelData[~panelData['generator:place'].isin(['roof'])]

    # Select the following columns for panelData: start_date, generator:method, osmid, source, name, geometry
    # If any of these columns do not exist, create an empty column of NA values (as a string)
    # Rename them to: instYr, modType, nativeID, Source, ProjName, geometry
    # Ensure required columns exist, creating them with NA values if missing
    # NOTE: there may be a 'generator:output:electricity' column, but we will ignore it for now and estiamte capacity from area and installation year later.
    required_columns = {
        'start_date': 'instYr',
        'generator:method': 'modType',
        'osmid': 'nativeID',
        'source': 'Source',
        'name': 'ProjName',
        'geometry': 'geometry'}
    for col, new_col in required_columns.items():
        if col not in panelData.columns:
            panelData[col] = pd.NA
        panelData[new_col] = panelData[col]

    # Select only the new columns
    panelData = panelData[list(required_columns.values())]

    return panelData, arrayData

# Define Function to Process Solar OSM Data
def processSolarOSMData(regionName, countryName, wd, config, method='api', osmSolar=None):   
    # method / osmSolar: see getSolarOSMData ('api' = Overpass API, 'pbf' = bulk solar extract from extractSolarFromPBF)

    # config: dict from gu.load_config(), loaded once by the caller
    minPanelRowArea = config['minPanelRowArea'] # 15 m2, minimum area for a single panel row from the 1st percentile panel area from Stid et al., 2022
    maxPanelRowArea = config['maxPanelRowArea'] # 254 m2 95th perccentile for a single panel row from Stid et al., 2022. MSU Solar Carport has max 1890m2
    minNumPanelRows = config['minNumPanelRows'] # 3 panels, minimum number of panels rows to form a ground mounted solar array, definition from Stid et al., 2022
    minPmArRatio = config['minPmArRatio'] # 18.8%, 20% was minimum ratio of panel perimeter to area ratio for panels from Stid et al., 2022, MSU Solar Carport has min 18.9%
    panelArrayBuff = config['panelArrayBuff'] # 10m buffer, 20m maximum distance between panel rows to form an array. We used 5m in Stid et al., 2022, but there are lower packing factors at greater latitudes (nativeID: '1229957948')
    arrayArrayBuff = config['arrayArrayBuff'] # 20m buffer, 40m maximum distance between arrays subsections of the same mount type to form a complete array. In Stid et al., 2022, we used 50m, but we checked for same installation year in addition to mount type.
    toCRS = config['to_crs']  # EPSG:6350 NAD83 (2011)
    toCRS = f'EPSG:{toCRS}'

    # Set OSM data download and processing paths
    downloaded_path = os.path.join(wd, r'Data\Downloaded')
    osmDownloadPath = os.path.join(downloaded_path, r'SolarDB\OSM')
    osmCountryPath = os.path.join(osmDownloadPath, countryName)
    osmPanelsPath = os.path.join(osmCountryPath, r'Panels')
    osmArraysPath = os.path.join(osmCountryPath, r'Arrays')

    # Check if the required folder exist, if not create it.
    gu.checkFolder(downloaded_path)
    gu.checkFolder(osmDownloadPath)
    gu.checkFolder(osmCountryPath)
    gu.checkFolder(osmPanelsPath)
    gu.checkFolder(osmArraysPath)

    # Get the solar panel and array data from OSM
    panelData, arrayData = getSolarOSMData(regionName, countryName, config, method=method, osmSolar=osmSolar)

    #~~~~~~~~~~~~~~~~~~~~# 
    # Process Array Data # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    #~~~~~~~~~~~~~~~~~~~~#

    # If arrayData is not empty, process arrayData
    if arrayData is not None and not arrayData.empty:
        # Capacity (capMWDC) is currently formated as a string and contains: '1 GW', '1 MW', '1 kW', or 'yes'. 
        # Formatting can also include '1GW', '1MW', '1kW', or the lower case version of any of these. 
        # It may also contain other strings that should be treated as nan, including existing nan values, and may also only contain a float value (we assume this is MW).
        # If the string contains 'yes', set to -9999 (null value).
        # If the string contains GW, remove everything except the number and multiply by 1000.
        # If the string contais MW, remove everything except the number and leave as is.
        # If the string contains kW, remove everything except the number and divide by 1000.
        # If the string contains anything else, set to -9999 (null value).
        # Function to process capacity
        def process_capacity(value):
            if pd.isna(value):
                return np.nan
            value = str(value).lower().strip()  # Make the string lowercase for easier matching and strip whitespaces
            try:
                if value == 'yes':
                    return -9999
                elif 'gw' in value:
                    return float(value.replace('gw', '').strip()) * 1000
                elif 'mw' in value:
                    return float(value.replace('mw', '').strip())
                elif 'kw' in value:
                    return float(value.replace('kw', '').strip()) / 1000
                return float(value)  # Assume the value is in MW if it's just a number
            except ValueError:  # If the string cannot be converted to a float
                return -9999

        # Apply the function to the 'capMWDC' column dynamically. Round to 3 decimal places.
        arrayData['capMWDC'] = arrayData['capMWDC'].apply(process_capacity).round(3)

    # ~~~~~~~~~~~~~~~~~ Get Panel Boundaries In Array Data (e.g. MSU Solar Carport, and 1229957948)

        # Explode the MultiPolygons into individual Polygons
        arrayData = arrayData.explode(index_parts=False).reset_index(drop=True)

        # Filter out any rows where the geometry is invalid or empty
        arrayData = arrayData[arrayData.geometry.notna()]

        # Calculate the area of each array (in square meters)
        arrayData['area'] = arrayData['geometry'].apply(lambda x: x.area if x.is_valid and x.area > 0 else np.nan)

        # Calculate the perimeter-to-area ratio of each array
        arrayData['PmArRatio'] = arrayData['geometry'].apply(lambda x: x.length / x.area if x.is_valid and x.area > 0 else np.nan)

        # Drop rows where area or PmArRatio couldn't be calculated (NaN values)
        arrayData = arrayData.dropna(subset=['area', 'PmArRatio'])

        # IF: an array is less than minimum panel size, remove it (more likely to be rooftop or inverter station)
        arrayData = arrayData[arrayData['area'] >= minPanelRowArea]

        # IF: an array has a perimeter to area ratio greater than 0.188 AND area is less than the max panel row area, save it to an panelInArrayData dataframe. Then remove it from arrayData
        # OR is key here, otherwise small array shapes get assigned panel status incorrectly. We want high quality panel-row metadata, so it is critical to ensure we only get true panel-rows here.
        panelInArrayData = arrayData[(arrayData['PmArRatio'] > minPmArRatio) & (arrayData['area'] < maxPanelRowArea)].reset_index(drop=True)
        arrayData = arrayData[~arrayData['nativeID'].isin(panelInArrayData['nativeID'])]

    # Else, if arrayData is empty, return an empty gdf for arrayData and panelInArrayData
    else:
        arrayData = gpd.GeoDataFrame(columns=['instYr', 'modType', 'nativeID', 'Source', 'ProjName', 'capMWDC', 'geometry'])
        panelInArrayData = gpd.GeoDataFrame(columns=['instYr', 'modType', 'nativeID', 'Source', 'ProjName', 'geometry'])

    # IF: arrayData is not empty, process arrayData -- second check because we filter above
    if arrayData is not None and not arrayData.empty: 

        # Dissolve by nativeID to return to multipolygon
        arrayData = arrayData.dissolve(by = 'nativeID').reset_index()

        # Remove panelInArrayData shapes that are already in panelData, then merge the remaining dataframes
        # First, check if data exists, then clean DataFrames by dropping rows with invalid or empty geometries, then remove overlapping arrays
        if panelInArrayData is not None:
            panelInArrayData = panelInArrayData[panelInArrayData.geometry.notna()]
            if not panelInArrayData.empty:
                panelInArrayData = panelInArrayData[~panelInArrayData.intersects(unary_union(panelData.geometry))]
        panelData = pd.concat([panelData, panelInArrayData])
    
    # Else, if arrayData is empty, return an empty gdf for arrayData and panelInArrayData
    else:
        arrayData = gpd.GeoDataFrame(columns=['instYr', 'modType', 'nativeID', 'Source', 'ProjName', 'capMWDC', 'geometry'])
        panelInArrayData = gpd.GeoDataFrame(columns=['instYr', 'modType', 'nativeID', 'Source', 'ProjName', 'geometry'])

    #~~~~~~~~~~~~~~~~~~~~# 
    # Process Panel Data # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    #~~~~~~~~~~~~~~~~~~~~#

    # IF: panelData is not empty, process panelData
    if panelData is not None and not panelData.empty:
        # Explode the MultiPolygons into individual Polygons
        panelData = panelData.explode(index_parts=False).reset_index(drop=True)
        panelData['nativeID'] = panelData['nativeID'] + '_' + panelData.groupby('nativeID').cumcount().astype(str)

        # Filter out any rows where the geometry is invalid or empty
        panelData = panelData[panelData.geometry.notna()]

        # Calculate the area of each panel (in square meters)
        panelData['area'] = panelData['geometry'].apply(lambda x: x.area if x.is_valid and x.area > 0 else np.nan)

        # Calculate the perimeter-to-area ratio of each panel
        panelData['PmArRatio'] = panelData['geometry'].apply(lambda x: x.length / x.area if x.is_valid and x.area > 0 else np.nan)

        # Drop rows where area or PmArRatio couldn't be calculated (NaN values)
        panelData = panelData.dropna(subset=['area', 'PmArRatio'])

        # IF: a panel is less than the mimum panel row area, remove it (more likely to be rooftop or inverter station)
        panelData = panelData[panelData['area'] >= minPanelRowArea]

    # ~~~~~~~~~~~~~~~~~~ Get Array Boundaries In Panel Data

        # IF: a panel has a perimeter to area ratio less than 0.188 or area is greater than max panel row area, save it to an arrayPanelData dataframe. Then remove it from panelData.
        # We leave condition as OR here, allows for catching common occurance of panels+space between them being mapped as a single panel object when it should be array. Metadata for arrays is less strict (grouped attributes) so we can be more lenient here.
        arrayInPanelData = panelData[(panelData['PmArRatio'] < minPmArRatio) | (panelData['area'] > maxPanelRowArea)] 
        panelData = panelData[~panelData['nativeID'].isin(arrayInPanelData['nativeID'])]

        # IF any arrayInPanelData shape is within a 20m buffer (arrayArrayBuff) of another arrayInPanelData, merge them into a single array shape
        arrayInPanelData = gu.groupArrayByVariableAndProximity(arrayInPanelData, arrayArrayBuff, "") # no grouping variable set here

    # Else, if panelData is empty, return an empty gdf for panelData, arrayInPanelData, and arrayFromPanelData
    else:
        panelData = gpd.GeoDataFrame(columns=['instYr', 'modType', 'nativeID', 'Source', 'ProjName', 'geometry', 'mount'])
        arrayInPanelData = gpd.GeoDataFrame(columns=['instYr', 'modType', 'nativeID', 'Source', 'ProjName', 'geometry'])
        arrayFromPanelData = gpd.GeoDataFrame(columns=['instYr', 'modType', 'nativeID', 'Source', 'ProjName', 'geometry', 'mount', 'pnlNum'])

    # IF: panelData is not empty, process panelData -- second check because we filter above
    if panelData is not None and not panelData.empty: 

    # ~~~~~~~~~~~~~~~~~~ Get New Array Boudaries From Panel Data

        # Get the mount type for each panel based on the geometry. assignMountType returns multiple columns, so only return the mount column.
        panelData['mount'] = panelData.apply(gu.assignMountType, axis=1, args=(config,)).apply(lambda x: x[0]) # panelData['mount'] = panelData.apply(assignMountType, axis=1)
        # panelData[['mount', 'azimuth', 'length_ratio', 'short_edge', 'long_edge']] = panelData.apply(gu.assignMountType, axis=1, result_type='expand', args=(config,))
        # panelData = panelData.drop(columns=['azimuth', 'length_ratio', 'short_edge', 'long_edge'])

        # Create arrays from adjacent panel-rows
        arrayFromPanelData = gu.createArrayFromPanels(panelData, panelArrayBuff, '', config, '', False)

        # Save the most common mount type for each array based on panels that intersect with the array
        arrayFromPanelData['mount'] = arrayFromPanelData['geometry'].apply(lambda x: panelData[panelData.intersects(x)]['mount'].mode()[0])

        # Set nativeID as 'fromOSMpanels_' plus a unique number from zero to number of arrays minus one
        arrayFromPanelData = arrayFromPanelData.reset_index(drop=True)
        arrayFromPanelData['nativeID'] = 'fromOSMpanels_' + arrayFromPanelData.index.astype(str)

        # Drop all columns except nativeID, mount, and geometry
        arrayFromPanelData = arrayFromPanelData[['nativeID', 'mount', 'geometry']]

        # IF any arrayFromPanelData shape is within a 20m buffer (arrayArrayBuff) of another arrayFromPanelData, merge them into a single array shape
        arrayFromPanelData = gu.groupArrayByVariableAndProximity(arrayFromPanelData, arrayArrayBuff, 'mount')

        # Save the number of panels in each array based number of intersecting panels
        arrayFromPanelData['pnlNum'] = arrayFromPanelData['geometry'].apply(lambda x: len(panelData[panelData.intersects(x)]))

        # Assign each panel the correspondingtotal panel num in array by spatial join.
        panelData = gpd.sjoin(panelData, arrayFromPanelData[['pnlNum', 'geometry']], how='left', predicate='intersects').drop(columns='index_right')

        # Remove arrays and panels that do not meet the minimum number of panels in an array
        arrayFromPanelData = arrayFromPanelData[arrayFromPanelData['pnlNum'] >= minNumPanelRows]
        panelData = panelData[panelData['pnlNum'] >= minNumPanelRows]
    
    # Else, if panelData is empty, return an empty gdf for panelData, arrayInPanelData, and arrayFromPanelData
    else:
        panelData = gpd.GeoDataFrame(columns=['instYr', 'modType', 'nativeID', 'Source', 'ProjName', 'geometry', 'mount'])
        arrayInPanelData = gpd.GeoDataFrame(columns=['instYr', 'modType', 'nativeID', 'Source', 'ProjName', 'geometry'])
        arrayFromPanelData = gpd.GeoDataFrame(columns=['instYr', 'modType', 'nativeID', 'Source', 'ProjName', 'geometry', 'mount', 'pnlNum'])

    #~~~~~~~~~~~~~~~~~~# 
    # Merge Array Data # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    #~~~~~~~~~~~~~~~~~~# 

    # OSM array bounds are defined as the "entire plant area", often including the fenced-in area around the panels, our definition of plant/facility boundary. 
    # OSM panel bounds are defined as individual rows of the solar panel within the solar field. 
    # We have identified that some contributors have thus interpreted panels as the panel-rows and the space between them, our definition of array boundary (e.g., -84.673137, 42.500187; southwest of Eaton Rapids, MI).
    # Therefore, we have decided to preference arrayInPanelData and arrayFromPanelData over arrayData, because where they are present, they better represent the array boundary by our definition. 
    # HOWEVER, baseline arrayData likely contains the best attribute metadata (installation year, capacity, project name, etc), so we will fill missing attributes in arrayInPanelData and arrayFromPanelData with values from arrayData where possible.
    # Where this process fails, higher priority spatial datasets (e.g., USPVDB) can address, for example, arrays with only partially digitized panel-rows. 
    # We have also decided to retain the maxPanelRowArea and minPmArRatio thresholds to differentiate these objects from true panels, and for imagery classification QA/QC purposes.

    # Set keep columns for all array data
    keep_cols = ['instYr', 'modType', 'nativeID', 'Source', 'ProjName', 'capMWDC', 'geometry']
    keep_cols_types = {'instYr': 'num', 'modType': 'text', 'nativeID': 'text', 'Source': 'text', 'ProjName': 'text', 'capMWDC': 'num', 'geometry': 'geometry'}

    # Ensure all dataframes have the same columns. If a column is missing, add it with NaN values (except geometry, which is required), num cols as -9999, text cols as empty string.
    for df in [arrayInPanelData, arrayFromPanelData, arrayData]:
        for col, col_type in keep_cols_types.items():
            if col not in df.columns:
                if col_type == 'num':
                    df[col] = -9999
                elif col_type == 'text':
                    df[col] = ''
                # geometry column is required, so we do not add it if missing

    # For all array data, select the following columns: instYr, modType, nativeID, Source, ProjName, pnlNum, geometry
    arrayInPanelData = arrayInPanelData[keep_cols]
    arrayFromPanelData = arrayFromPanelData[keep_cols]
    arrayData = arrayData[keep_cols]

    # For arrayFromPanelData and arrayInPanelData, add a capMWDC column and set it to -9999
    arrayFromPanelData['capMWDC'] = -9999
    arrayInPanelData['capMWDC'] = -9999

    # Set gdf order preference
    pref1 = arrayInPanelData.copy()
    pref2 = arrayFromPanelData.copy()
    pref3 = arrayData.copy()

    # Fill metadata gaps in higher-preference datasets from lower-preference datasets, first: set aggregation config
    aggConfig = {
        'instYr':  ('mode',  'num', True),   # take mode of year; always override
        'capMWDC':  ('mean',  'num', True),  # fill missing capacity using mean
        'modType': ('mode',  'text', True), # most frequent module type
        'ProjName':('first', 'text', True), # first project name
        'Source':  ('mode',  'text', False)}  # most frequent source

    # Fill high-priority datasets from lower ones
    pref2 = gu.fillMetadataByOverlap(pref2, pref3, aggConfig)
    pref1 = gu.fillMetadataByOverlap(pref1, pref2, aggConfig)

    # Remove arrays with overlap in the following level of priority: arrayInPanelData, arrayFromPanelData, arrayData
    # This order maintains arrays composed of subarray sections (multipolygons)
    # First, check if data exists, then clean DataFrames by dropping rows with invalid or empty geometries, then remove overlapping arrays
    # Solves an issue where an array df is empty, or contains errant geometries
    if pref2 is not None:
        pref2 = pref2[pref2.geometry.notna()]
        if not pref2.empty and not pref1.empty:
            pref2 = pref2[~pref2.intersects(unary_union(pref1.geometry.values))]
    if pref3 is not None:
        pref3 = pref3[pref3.geometry.notna()]
        if not pref3.empty and not pref1.empty:
            pref3 = pref3[~pref3.intersects(unary_union(pref1.geometry.values))]
        if not pref3.empty and pref2 is not None and not pref2.empty:
            pref3 = pref3[~pref3.intersects(unary_union(pref2.geometry.values))]

    # Merge the array data
    # Skip empty frames and drop all-NA columns before concatenating (avoids pandas FutureWarning); reindex restores every column in its original order
    nonEmpty = [d for d in [pref1, pref2, pref3] if d is not None and not d.empty]
    allCols = list(dict.fromkeys(c for d in nonEmpty for c in d.columns))
    arrayData = (pd.concat([d.dropna(axis=1, how='all') for d in nonEmpty]).reindex(columns=allCols).reset_index(drop=True)
                 if nonEmpty else pref1.reset_index(drop=True))

    #~~~~~~~~~~~~~~~~~~~~~~~~~# 
    # Fill Gaps and Save Data # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    #~~~~~~~~~~~~~~~~~~~~~~~~~#

    # Assign a unique arrayID to each array, from 1 to number of arrays (use range)
    arrayData['arrayID'] = range(1, len(arrayData) + 1)

    # Save the final number of panels in each array based number of intersecting panels (overwrites initial count)
    arrayData['pnlNum'] = arrayData['geometry'].apply(lambda x: len(panelData[panelData.intersects(x)]))

    # For each array and each panel, calculate the area and save as a new column, round to 0 decimal places
    panelData['area'] = panelData.area.round(0)
    arrayData['area'] = arrayData.area.round(0)

    # instYr values are formatted in several ways: 'YYYY-MM' or 'YYYY-MM-DD', 'MM/YYYY', 'YYYY', m/d/YYYY, with additional examples of: 'October 2018', 'March 1, 2015', '6/11/2011', '11/2019', '20183', '2021.0'
    # We want to extract the year from these strings. If the year is not present, or if the year is not between 1900 and 2025, set to -9999
    # Set the instYr column to an integer type when finished.
    # Function to extract a valid year from various formats
    def extract_year(instYr):
        # Patterns to capture the year from different formats
        patterns = [
            r'(\b\d{4})[-/]\d{2}[-/]\d{2}',    # Match 'YYYY-MM-DD' or 'YYYY/MM/DD' (e.g., '2020-05-25')
            r'(\b\d{4})[-/]\d{2}',              # Match 'YYYY-MM' or 'YYYY/MM' (e.g., '2020-05')
            r'\b(\d{1,2})/\d{1,2}/(\d{4})\b',   # Match 'm/d/YYYY' or 'MM/DD/YYYY' (e.g., '6/11/2011')
            r'([A-Za-z]+\s+\d{1,2},?\s+)?(\d{4})',  # Match 'Month YYYY' (e.g., 'October 2018') or 'March 1, 2015'
            r'(\b\d{4}\b)'                      # Match standalone 'YYYY' (e.g., '2020')
        ]
        
        # Iterate through the patterns and try to match
        for pattern in patterns:
            match = re.search(pattern, str(instYr))
            if match:
                # Extract the year from the matched group
                year = int(match.group(1)) if len(match.groups()) == 1 else int(match.group(2))
                # Ensure the year is valid (between 1983 and 2025) -- 1983 is the install year of Solar One, the first commercial solar power plant in the US
                if 1983 <= year <= 2025:
                    return year
        # If no valid year is found, return -9999
        return -9999

    # Apply the function to the 'instYr' column for both panelData and arrayData
    panelData['instYr'] = panelData['instYr'].apply(extract_year).astype(int)
    arrayData['instYr'] = arrayData['instYr'].apply(extract_year).astype(int)
        
    # For both dataframes, fill missing Source and ProjName with 'Unknown'
    panelData['Source'] = panelData['Source'].fillna('Unknown')
    arrayData['Source'] = arrayData['Source'].fillna('Unknown')
    panelData['ProjName'] = panelData['ProjName'].fillna('Unknown')
    arrayData['ProjName'] = arrayData['ProjName'].fillna('Unknown')

    # For respective modType columns, replace 'photovoltaic' with 'c-Si' and 'thermal' with 'csp'. 
    panelData['modType'] = panelData['modType'].replace('photovoltaic', 'c-si')
    arrayData['modType'] = arrayData['modType'].replace('photovoltaic', 'c-si')
    panelData['modType'] = panelData['modType'].replace('thermal', 'csp')
    arrayData['modType'] = arrayData['modType'].replace('thermal', 'csp')

    # For both dataframes, fill missing modType with 'c-Si'
    panelData['modType'] = panelData['modType'].fillna('c-si')
    arrayData['modType'] = arrayData['modType'].fillna('c-si')

    # Assign each panel the corresponding arrayID by spatial join. Only if panelData is not empty and arrayData is not empty
    if not panelData.empty and not arrayData.empty:
        panelData = gpd.sjoin(panelData, arrayData[['arrayID', 'geometry']], how='left', predicate='intersects').drop(columns='index_right')

    # If dataframes are empty, ignore, otherwise save the data to a shapefile in the OSM download folder for the region
    if panelData is not None and not panelData.empty:
        panelData.to_file(os.path.join(osmPanelsPath, regionName + 'SolarPanels.gpkg'), driver='GPKG')
    if arrayData is not None and not arrayData.empty:
        arrayData.to_file(os.path.join(osmArraysPath, regionName + 'SolarArrays.gpkg'), driver='GPKG')

    # If desired, return the dataframes
    #return panelData, arrayData

# Define function to iterate through each region in a country and extract OSM solar data
def getCountrySolarOSMData(countryName, wd, config, processCountry=True, method='api', osmSolar=None):
    # method / osmSolar: see getSolarOSMData ('api' = Overpass API, 'pbf' = bulk solar extract from extractSolarFromPBF)

    # For the PBF method, load the solar extract once and reuse it for every region
    if method == 'pbf' and isinstance(osmSolar, (str, os.PathLike)):
        osmSolar = loadSolarOSMExtract(osmSolar)

    # Get regions within the country from the above dictionary
    regions = countryRegionsDict[countryName]

    # config: dict from gu.load_config(), loaded once by the caller
    toCRS = config['to_crs']  # EPSG:6350 NAD83 (2011)
    toCRS = f'EPSG:{toCRS}'

    # Set OSM data download and processing paths
    downloaded_path = os.path.join(wd, r'Data\Downloaded')
    osmDownloadPath = os.path.join(downloaded_path, r'SolarDB\OSM')
    osmCountryPath = os.path.join(osmDownloadPath, countryName)
    osmPanelsPath = os.path.join(osmCountryPath, r'Panels')
    osmArraysPath = os.path.join(osmCountryPath, r'Arrays')

    # First, check if the required folder exist, if not create it.
    gu.checkFolder(downloaded_path)
    gu.checkFolder(osmDownloadPath)
    gu.checkFolder(osmCountryPath)
    gu.checkFolder(osmPanelsPath)
    gu.checkFolder(osmArraysPath)

    # Loop through each region and get the solar data
    for region in regions:
        processSolarOSMData(region, countryName, wd, config, method=method, osmSolar=osmSolar)
        print(region + ' data has been downloaded and processed.')
    
    # If processCountry is True, load all data and print summary statistics, and export combined shapefiles
    if processCountry:
        # Load all solar panel and array data
        panels = gu.load_all_gdf(osmPanelsPath, 'gpkg', toCRS)
        arrays = gu.load_all_gdf(osmArraysPath, 'gpkg', toCRS)

        # Print the number of solar panels and arrays in countryName
        print(f'Total solar panels in {countryName}: {len(panels)}')
        print(f'Total solar arrays in {countryName}: {len(arrays)}')

        # Print sum of area of arrays and panels in km in countryName
        print(f'Total solar panels area in {countryName}: {panels.area.sum() / 1e6:.2f} km^2')
        print(f'Total solar arrays area in {countryName}: {arrays.area.sum() / 1e6:.2f} km^2')

        # Save the data to a shapefile in the OSM download folder, append with country name
        panels.to_file(os.path.join(osmCountryPath, 'OSMSolarPanels_' + countryName + '.gpkg'), driver='GPKG')
        arrays.to_file(os.path.join(osmCountryPath, 'OSMSolarArrays_' + countryName + '.gpkg'), driver='GPKG')



# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ OpenStreetMap Inverter Functions
# Inverters are returned as points (polygon footprints are reduced to their centroid; their area is kept as footArea).
# Each inverter is matched to the nearest OSM solar array (from the solar run above): distArray (m), inArray (touches/inside an array), nearArray (within bufferDist).

# OSM tags kept in the inverter outputs (when present)
inverterKeepTags = ['power', 'substation', 'transformer', 'converter', 'name', 'operator', 'ref', 'manufacturer', 'model', 'rating',
                    'capacity', 'voltage', 'frequency', 'plant:source', 'generator:source', 'location', 'start_date']

# Define a function that grabs inverter data from OSM for a given region and matches it to nearby solar arrays
def getInverterOSMData(regionName, countryName, config, method='api', osmInverters=None, arrays=None, bufferDist=100):
    # method: 'api' (Overpass API via osmnx) or 'pbf' (clip from the extract built by extractInvertersFromPBF)
    # osmInverters: (method='pbf' only) path to the inverter extract GeoPackage, or the gdf already loaded with loadSolarOSMExtract()
    # arrays: OSM solar arrays (any CRS, needs 'nativeID'); bufferDist: distance (m, in to_crs units) for nearArray
    toCRS = f"EPSG:{config['to_crs']}"
    place = regionName + ', ' + countryName

    # Retrieve inverter features (both methods return a MultiIndex (element, id) gdf with one column per tag)
    emptyGdf = gpd.GeoDataFrame(geometry=[], crs=toCRS)
    if method == 'api':
        osmnxTags = {}
        for k, v in inverterTagFilter:
            osmnxTags.setdefault(k, []).append(v)
        try:
            print(f"{regionName}: Attempting to retrieve inverter data...")
            inv = ox.features_from_place(place, tags=osmnxTags)
        except InsufficientResponseError:
            inv = emptyGdf
    elif method == 'pbf':
        if osmInverters is None:
            raise ValueError("method='pbf' requires osmInverters (path to the inverter extract from extractInvertersFromPBF, or the loaded gdf).")
        if isinstance(osmInverters, (str, os.PathLike)):
            osmInverters = loadSolarOSMExtract(osmInverters)  # same file structure as the solar extract
        print(f"{regionName}: Selecting inverter data from bulk PBF extract...")
        inv = getRegionSolarFromExtract(place, osmInverters)
    else:
        raise ValueError(f"Unknown method '{method}'. Use 'api' or 'pbf'.")
    if inv.empty:
        print(f"No inverter data found for {regionName}.")
        return emptyGdf

    # Standardize columns: osmID ('node/123', viewable at openstreetmap.org/<osmID>), matched inverter tag, and kept OSM tags
    inv = inv.reset_index()
    inv['osmID'] = inv['element'] + '/' + inv['id'].astype(str)
    inv['invTag'] = None
    for k, v in reversed(inverterTagFilter):  # first tag in inverterTagFilter wins
        if k in inv.columns:
            inv.loc[inv[k].eq(v), 'invTag'] = f'{k}={v}'
    inv = inv[inv['invTag'].notna()]  # osmnx can return untagged features (e.g., relation members)
    if inv.empty:
        print(f"No inverter data found for {regionName}.")
        return emptyGdf
    inv['region'] = regionName
    keep = ['osmID', 'element', 'invTag', 'region'] + [t for t in inverterKeepTags if t in inv.columns]
    inv = gpd.GeoDataFrame(inv[keep + ['geometry']], geometry='geometry', crs=inv.crs).to_crs(toCRS)

    # Footprint type and area (0 for points)
    inv['geomType'] = inv.geom_type
    inv['footArea'] = inv.area.round(1)

    # Match to the nearest solar array using the full footprint (so a polygon touching an array counts as inArray)
    inv = inv.reset_index(drop=True)
    if arrays is not None and not arrays.empty:
        near = gpd.sjoin_nearest(inv[['geometry']], arrays[['nativeID', 'geometry']].to_crs(toCRS), how='left', distance_col='distArray')
        near = near[~near.index.duplicated(keep='first')]  # ties: keep one array
        inv['arrNatID'] = near['nativeID']
        inv['distArray'] = near['distArray'].round(1)
    else:
        inv['arrNatID'] = None
        inv['distArray'] = np.nan
    inv['inArray'] = inv['distArray'].eq(0)
    inv['nearArray'] = inv['distArray'].le(bufferDist)

    # Reduce footprints to points (polygon/line centroids)
    inv['geometry'] = inv.geometry.centroid
    return inv

# Define a function to convert inverters to the standard inverter output format shared with other sources (e.g., PanelSeg): invType, Source, geometry (centroid points)
# OSM diagnostic columns (osmID, invTag, distArray, inArray, nearArray, arrNatID, ...) are kept after these for filtering
def toInverterOutput(inv):
    out = inv.copy()
    out['invType'] = 'unknown'  # unknown for now (OSM does not record central vs string)
    out['Source'] = 'OSM'
    out = out.set_geometry(out.geometry.centroid)
    first = ['invType', 'Source']
    return out[first + [c for c in out.columns if c not in first]].reset_index(drop=True)

# Define function to get inverter data for every region in a country, save per-region and combined files (standard format + OSM diagnostic columns), and print a feasibility summary
def getCountryInverterOSMData(countryName, wd, config, method='api', osmInverters=None, bufferDist=100, solarOnly=False, processCountry=True):
    # Requires the solar run (getCountrySolarOSMData) for this country first: arrays are read from OSMSolarArrays_<country>.gpkg (or the Arrays folder)
    # solarOnly: if True, drop inverters farther than bufferDist from an OSM solar array (OSM inverter tags do not say the source, so
    #            proximity to a mapped solar array is the only solar evidence). If False (default), keep all and use the nearArray flag.
    toCRS = f"EPSG:{config['to_crs']}"
    osmCountryPath = os.path.join(wd, r'Data\Downloaded\SolarDB\OSM', countryName)
    osmArraysPath = os.path.join(osmCountryPath, r'Arrays')
    osmInvertersPath = os.path.join(osmCountryPath, r'Inverters')
    gu.checkFolder(osmInvertersPath)

    # Load inputs once: the country's solar arrays (so inverters near state borders still match) and, for 'pbf', the inverter extract
    countryArraysFile = os.path.join(osmCountryPath, 'OSMSolarArrays_' + countryName + '.gpkg')
    arrays = gpd.read_file(countryArraysFile).to_crs(toCRS) if os.path.exists(countryArraysFile) else gu.load_all_gdf(osmArraysPath, 'gpkg', toCRS)
    if method == 'pbf' and isinstance(osmInverters, (str, os.PathLike)):
        osmInverters = loadSolarOSMExtract(osmInverters)

    # Loop through each region
    allInv = []
    for region in countryRegionsDict[countryName]:
        inv = getInverterOSMData(region, countryName, config, method=method, osmInverters=osmInverters, arrays=arrays, bufferDist=bufferDist)
        if solarOnly and not inv.empty:
            inv = inv[inv['nearArray']].reset_index(drop=True)
        if not inv.empty:
            toInverterOutput(inv).to_file(os.path.join(osmInvertersPath, region + 'SolarInverters.gpkg'), driver='GPKG')
            allInv.append(inv)
        nNear = int(inv['nearArray'].sum()) if not inv.empty else 0
        print(f"{region}: {len(inv)} inverters ({nNear} within {bufferDist} m of an OSM solar array).")

    if not processCountry or not allInv:
        return
    # Combine (features crossing a state border appear in both states; keep the first)
    inv = gpd.GeoDataFrame(pd.concat(allInv, ignore_index=True), crs=toCRS).drop_duplicates('osmID')
    toInverterOutput(inv).to_file(os.path.join(osmCountryPath, 'OSMSolarInverters_' + countryName + '.gpkg'), driver='GPKG')

    # Feasibility summary
    print(f"\nTotal OSM inverters in {countryName}: {len(inv)}")
    print("By tag:\n" + inv['invTag'].value_counts().to_string())
    print("By OSM element:\n" + inv['element'].value_counts().to_string())
    print(f"Inside/touching an OSM solar array: {inv['inArray'].sum()} ({100 * inv['inArray'].mean():.1f}%)")
    print(f"Within {bufferDist} m of an OSM solar array: {inv['nearArray'].sum()} ({100 * inv['nearArray'].mean():.1f}%)")
    print(f"OSM solar arrays with >=1 inverter within {bufferDist} m: {inv.loc[inv['nearArray'], 'arrNatID'].nunique()} of {len(arrays)}")
    return toInverterOutput(inv)