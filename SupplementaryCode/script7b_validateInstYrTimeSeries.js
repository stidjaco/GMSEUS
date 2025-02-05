//######################################################################################################## 
//#                                                                                                    #\\
//#                             LANDTRENDR PIXEL TIME SERIES PLOTTER GUI                               #\\
//#                                                                                                    #\\
//########################################################################################################


// date: 2018-06-11
// author: Justin Braaten | jstnbraaten@gmail.com
//         Zhiqiang Yang  | zhiqiang.yang@oregonstate.edu
//         Robert Kennedy | rkennedy@coas.oregonstate.edu
// website: https://github.com/eMapR/LT-GEE

// edit date: 2024-11-21
// edited: Jacob Stid | stidjaco@msu.edu

/*
NOTE: This code is from the LandTrendr group's public codebase, modified to include new solar indices. 
*/

var ltgee = require('users/stidjaco/SourceCode:LandTrendrSolarIndex.js');  


//####################################################################################
//########### FUNCTIONS ##############################################################
//####################################################################################

// function to get LT parameter setting
var getParams = function(){
  var prevOneYrRec = paramBoxes[3].getValue();
  if(typeof(prevOneYrRec) !== "boolean"){
    prevOneYrRec = prevOneYrRec.toLowerCase() != 'false';
  }
  
  return { 
    maxSegments:              parseInt(paramBoxes[0].getValue()),
    spikeThreshold:         parseFloat(paramBoxes[1].getValue()),
    vertexCountOvershoot:     parseInt(paramBoxes[2].getValue()),
    preventOneYearRecovery:                         prevOneYrRec,
    recoveryThreshold:      parseFloat(paramBoxes[4].getValue()),
    pvalThreshold:          parseFloat(paramBoxes[5].getValue()),
    bestModelProportion:    parseFloat(paramBoxes[6].getValue()),
    minObservationsNeeded:    parseInt(paramBoxes[7].getValue())
  };
};

// function to create a plot of source and fitted time series
var chartPoint = function(lt, pixel, index, indexFlip) {
  var pixelTimeSeriesData = ltgee.ltPixelTimeSeriesArray(lt, pixel, indexFlip);
  return ui.Chart(pixelTimeSeriesData.ts, 'LineChart',
            {
              'title' : 'Index: '+index + ' | Fit RMSE: '+ (Math.round(pixelTimeSeriesData.rmse * 100) / 100).toString(),
              'hAxis': 
                {
                  'format':'####'
                },
              'vAxis':
                {
                  'maxValue': 1000,
                  'minValue': -1000   
                }
            },
            {'columns': [0, 1, 2]}
          );
};


// function to draw plots of source and fitted time series to panel
var plotTimeSeries = function(x, y){  
  // clear the plot panel
  plotPanel = plotPanel.clear();
  
  // add a red pixel to the map where the user clicked or defined a coordinate
  var point = ee.Geometry.Point(x, y);
  var pixel = point.buffer(15).bounds();
  map.layers().set(0, ui.Map.Layer(pixel, {color: 'FF0000'}));
  
  // get values to define year and date window for image collection
  var startYear = startYearslider.getValue();
  var endYear = endYearslider.getValue();
  var startDay = startDayBox.getValue();
  var endDay = endDayBox.getValue();
  
  // get the indices that are checked
  var doTheseIndices = [];
  indexBox.forEach(function(name, index) {
    var isChecked = indexBox[index].getValue();
    if(isChecked){
      doTheseIndices.push([indexList[index][0],indexList[index][1]]);
    }
  });
  
  // make an annual SR collection
  var annualSRcollection = ltgee.buildSRcollection(startYear, endYear, startDay, endDay, pixel);

  // for each selected index, draw a plot to the plot panel
  doTheseIndices.forEach(function(name, index) {
    var annualLTcollection = ltgee.buildLTcollection(annualSRcollection, name[0], []);
    runParams.timeSeries = annualLTcollection;
    var lt = ee.Algorithms.TemporalSegmentation.LandTrendr(runParams);
    var chart = chartPoint(lt, pixel, name[0], name[1]);
    plotPanel.add(chart);
  });
};



//####################################################################################
//########### DEFINE UI COMPONENTS ###################################################
//####################################################################################

// SET UP PRIMARY PANELS
// control panel
var controlPanel = ui.Panel({
  layout: ui.Panel.Layout.flow('vertical'),
  style: {width: '340px'}
});


// plot panel
var plotsPanelLabel = ui.Label('LandTrendr Time Series Plots', {fontWeight: 'bold', stretch: 'horizontal'});
var plotPanel = ui.Panel(null, null, {stretch: 'horizontal'});
var plotPanelParent = ui.Panel([plotsPanelLabel, plotPanel], null, {width: '480px'});


// map panel
var map = ui.Map();
map.style().set({cursor:'crosshair'});
map.setOptions('HYBRID');
var processingLabel = ui.Label('Processing, please wait...', {shown:false, position: 'top-center'});
map.add(processingLabel);



// SET UP SECONDARY PANELS
// years panel
var yearSectionLabel = ui.Label('Define Year Range',{fontWeight: 'bold'});

var startYearLabel = ui.Label('Start Year');
var startYearslider = ui.Slider({min:1984, max:2024, value:1985, step:1});
startYearslider.style().set('stretch', 'horizontal');

var endYearLabel = ui.Label('End Year');
var endYearslider = ui.Slider({min:1984, max:2024, value:2024, step:1});
endYearslider.style().set('stretch', 'horizontal');

var yearsPanel = ui.Panel(
  [
    yearSectionLabel,
    ui.Panel([startYearLabel, startYearslider], ui.Panel.Layout.Flow('horizontal'), {stretch: 'horizontal'}), //
    ui.Panel([endYearLabel  , endYearslider], ui.Panel.Layout.Flow('horizontal'), {stretch: 'horizontal'})
  ] 
);


// date panel
var dateSectionLabel = ui.Label('Define Date Range (month-day)',{fontWeight: 'bold'});
var startDayLabel = ui.Label('Start Date:');
var startDayBox = ui.Textbox({value:'01-01'});
startDayBox.style().set('stretch', 'horizontal');

var endDayLabel = ui.Label('End Date:');
var endDayBox = ui.Textbox({value:'12-31'});
endDayBox.style().set('stretch', 'horizontal');

var datesPanel = ui.Panel(
  [
    dateSectionLabel,
    ui.Panel(
      [startDayLabel, startDayBox, endDayLabel, endDayBox],
      ui.Panel.Layout.Flow('horizontal'), {stretch: 'horizontal'}
    )
  ]
);


// index panel
var indexList = [['NDPVI',-1], ['NBD',-1], ['BR',-1], ['NDWI',-1], ['NDVI',-1], ['EVI',-1], ['NBR',-1], ['NDMI',-1], ['NDSI', -1],
                 ['TCB',1], ['TCG',-1], ['TCW',-1], ['TCA' ,-1], 
                 ['B1' ,1], ['B2' , 1], ['B3' , 1], ['B4'  ,-1], ['B5'  , 1], ['B7' ,1]];

var indexBox = [];
indexList.forEach(function(name, index) {
  var checkBox = ui.Checkbox(name[0]);
  indexBox.push(checkBox);
});

var indexPanelLabel = ui.Label('Select Indices', {fontWeight : 'bold'});
var indexPanel = ui.Panel(
  [
    ui.Panel([indexBox[0], indexBox[4], indexBox[8], indexBox[12]], null, {stretch: 'horizontal'}),
    ui.Panel([indexBox[1], indexBox[5], indexBox[9]], null, {stretch: 'horizontal'}),
    ui.Panel([indexBox[2], indexBox[6], indexBox[10]], null, {stretch: 'horizontal'}),
    ui.Panel([indexBox[3], indexBox[7], indexBox[11]], null, {stretch: 'horizontal'})
  ],
  ui.Panel.Layout.Flow('horizontal'), {stretch: 'horizontal'}
);

indexBox[0].setValue(1);


// coordinate panel
var coordSectionLabel = ui.Label('Define Pixel Coordinates (optional)',{fontWeight: 'bold'});

var latLabel = ui.Label('Latitude:');
var latBox = ui.Textbox({value:43.7929});
latBox.style().set('stretch', 'horizontal');

var lonLabel = ui.Label('Longitude:');
var lonBox = ui.Textbox({value:-122.8848});
lonBox.style().set('stretch', 'horizontal');

var latLonPanel = ui.Panel(
  [
    coordSectionLabel,
    ui.Panel([lonLabel, lonBox, latLabel, latBox],ui.Panel.Layout.Flow('horizontal'))
  ],
  null,
  {stretch: 'horizontal'}
);


// params panel
var runParams = [
  {label: 'Max Segments:', value: 6},
  {label: 'Spike Threshold:', value: 0.5},
  {label: 'Vertex Count Overshoot:', value: 3},
  {label: 'Prevent One Year Recovery:', value: true},
  {label: 'Recovery Threshold:', value: 0.1},
  {label: 'p-value Threshold:', value: 0.05},
  {label: 'Best Model Proportion:', value: 0.75},
  {label: 'Min Observations Needed:', value: 6},
];

var paramBoxes = [];
var paramPanels = [ui.Label('Define Segmentation Parameters',{fontWeight: 'bold'})];
runParams.forEach(function(param, index){
  var paramLabel = ui.Label(param.label);
  var paramBox = ui.Textbox({value:param.value});
  paramBox.style().set('stretch', 'horizontal');
  var paramPanel = ui.Panel([paramLabel,paramBox], ui.Panel.Layout.Flow('horizontal'));
  paramBoxes.push(paramBox);
  paramPanels.push(paramPanel);
});

var paramPanel = ui.Panel(paramPanels,null,{stretch: 'horizontal'});


// submit panel
var submitButton = ui.Button({label: 'Submit'});
submitButton.style().set('stretch', 'horizontal');






//####################################################################################
//########### BIND FUNCTIONS TO ACTIONS ##############################################
//####################################################################################

// plot time series for clicked point on map
map.onClick(function(coords) {
  var x = coords.lon;
  var y = coords.lat;
  lonBox.setValue(x);
  latBox.setValue(y);
  runParams = getParams();
  plotTimeSeries(x, y);
});


// plot time series for point defined as coordinates
submitButton.onClick(function(){
  var x = parseFloat(lonBox.getValue());
  var y = parseFloat(latBox.getValue());
  runParams = getParams();
  plotTimeSeries(x, y);
  map.setCenter(x, y, 16);
});






//####################################################################################
//########### ADD PANELS TO INTERFACE ################################################
//####################################################################################

controlPanel.add(yearsPanel);
controlPanel.add(datesPanel);
controlPanel.add(indexPanelLabel);
controlPanel.add(indexPanel);
controlPanel.add(latLonPanel);
controlPanel.add(paramPanel);
controlPanel.add(submitButton);

map.add(ui.Label({
  value: 'Click a point',
  style: {position: 'top-center'}
}));

map.add(ui.Label({
  value: 'Info: https://goo.gl/pQtpjR',
  style: {position: 'bottom-right'}
}));

// Centroids without YOD
//map.add(centroids.geometry)
map.layers().set(0, ui.Map.Layer(centroids.geometry()));

ui.root.clear();
ui.root.add(controlPanel);
ui.root.add(map);
ui.root.add(plotPanelParent);

map.layers().set(0, ui.Map.Layer(centroids.geometry()));
