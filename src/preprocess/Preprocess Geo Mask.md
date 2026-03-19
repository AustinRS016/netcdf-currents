## Step 1

Download 'Water polygons' from https://osmdata.openstreetmap.de/data/water-polygons.html

## Step 2

Create layer in QGIS, draw bounding box over desired area

## Step 3

Clip 'Water polygons' with bounding box as overlay -> 'Water polygons clipped'

## Step 4

Dissolve grid structure in 'Water polygons clipped' -> 'Water polygons clipped disolved'

## Step 5

Perform Union on bounding box and 'Water polygons clipped disolved' -> 'Vector mask'

## Step 6

Ensure that 'id' has the value of 1 for land in the attribute table of 'Vector mask'

## Step 7

Reproject 'Vector mask' to epsg:3857

## Step 8

Rasterize 'Vector mask'

We choose the fixed value to burn as 0
Output raster size units are set to 'Georeferenced units' (meters)
Both resolutions are set to 10
Extent must come from the 'Vector mask'
For advanced parameters:

- COMPRESS=DEFLATE
- NBITS=1
  Output data type is 'Byte'
  {
  "area_units": "m2",
  "distance_units": "meters",
  "ellipsoid": "EPSG:7019",
  "inputs": {
  "BURN": 0.0,
  "CREATION_OPTIONS": "COMPRESS=DEFLATE|NBITS=1",
  "DATA_TYPE": 0,
  "EXTENT": "-13756420.998800000,-13587883.239700001,5934610.381000000,6307335.634200000 [EPSG:3857]",
  "EXTRA": "",
  "FIELD": "id",
  "HEIGHT": 10.0,
  "INIT": null,
  "INPUT": "puget_water_land_mask_reproj.geojson",
  "INVERT": false,
  "NODATA": null,
  "OUTPUT": "C:/Users/austi/Downloads/test_export_puget_mask.tif",
  "UNITS": 1,
  "USE_Z": false,
  "WIDTH": 10.0
  }
  }

console call:
gdal_rasterize -l puget_water_land_mask_reproj -a id -tr 10.0 10.0 -a_nodata 0.0 -te -13756420.9988 5934610.381 -13587883.2397 6307335.6342 -ot Byte -of GTiff -co COMPRESS=DEFLATE -co NBITS=1 puget_water_land_mask_reproj.geojson C:/Users/austi/AppData/Local/Temp/processing_JSbqXp/d0ce1aea0e794c2382cb2df7b17a5db6/OUTPUT.tif

Python command:
processing.run("gdal:rasterize", {'INPUT':'puget_water_land_mask_reproj.geojson','FIELD':'id','BURN':0,'USE_Z':False,'UNITS':1,'WIDTH':10,'HEIGHT':10,'EXTENT':'-13756420.998800000,-13587883.239700001,5934610.381000000,6307335.634200000 [EPSG:3857]','NODATA':0,'CREATION_OPTIONS':'COMPRESS=DEFLATE|NBITS=1','DATA_TYPE':0,'INIT':None,'INVERT':False,'EXTRA':'','OUTPUT':'TEMPORARY_OUTPUT'})
