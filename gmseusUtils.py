# Import Libraries
import geopandas as gpd
import pandas as pd
import numpy as np
import os
#from shapely.geometry import MultiPolygon, Polygon, MultiPoint
from shapely.ops import unary_union
import re

# Load OSM libraries and variables
import osmnx as ox
from osmnx._errors import InsufficientResponseError
ox.settings.use_cache = True
ox.settings.cache_folder = r"F:\OSM_Cache" # Create a local cache folder
ox.settings.overpass_url = 'https://overpass-api.de/api/interpreter' # "https://overpass.kumi.systems/api/interpreter"  # new name for endpoint

# Function to load config file
def load_config(filename):
    config = {}
    with open(filename, 'r') as f:
        for line in f:
            # Strip whitespace and split by '='
            key, value = line.strip().split('=')
            # Try to convert to numeric values if possible
            try:
                value = float(value) if '.' in value else int(value)
            except ValueError:
                pass  # Leave as string if not a number
            config[key] = value
    return config