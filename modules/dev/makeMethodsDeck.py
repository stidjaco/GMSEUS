r"""
Build the methods overview slide deck (12 slides) for the GM-SEUS generation and emissions modules.

Every figure is read from the files the notebooks save (in the shared theme, utils/figureTheme.py), and every
number on the slides is calculated here from the notebook outputs. Run after getGeneration (with its validation
cell), getGridEmissions, getUpstreamEmissions, and processGenEmissions:

    python modules/dev/makeMethodsDeck.py

Optional: --wd <project folder> (default S:\Users\stidjaco\R_files\BigPanel), --figures <figure folder> (default <wd>\Figures),
--out <pptx path>. Requires python-pptx (in envFiles/BigPanel.yml).
"""
import os, argparse
import numpy as np
import pandas as pd
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.chart.data import CategoryChartData
from pptx.enum.chart import XL_CHART_TYPE, XL_LABEL_POSITION

# ---------------------------------------------------------------- paths
ap = argparse.ArgumentParser()
ap.add_argument('--wd', default=r'S:\Users\stidjaco\R_files\BigPanel')
ap.add_argument('--figures', default=None)
ap.add_argument('--out', default=None)
ap.add_argument('--weather', default='pvgis')
args = ap.parse_args()
wd = args.wd; derived = os.path.join(wd, 'Data', 'Derived'); figRoot = args.figures or os.path.join(wd, 'Figures')
OUT = args.out or os.path.join(figRoot, 'genEmissions', 'GenEmissions_MethodsOverview.pptx')
figs = {
    'fleet': os.path.join(figRoot, 'genEmissions', 'fig1_fleetTimeseries.png'),
    'maps': os.path.join(figRoot, 'genEmissions', 'fig2_netAvoidedMaps.png'),
    'budget': os.path.join(figRoot, 'genEmissions', 'fig3_carbonBudget.png'),
    'gridRates': os.path.join(figRoot, 'genEmissions', 'panels', 'panel_gridRates.png'),
    'upstreamFactor': os.path.join(figRoot, 'genEmissions', 'panels', 'panel_upstreamFactor.png'),
    'payback': os.path.join(figRoot, 'genEmissions', 'panels', 'panel_payback.png'),
    'validation': os.path.join(figRoot, 'genValidation_LBNL_' + args.weather + '.png'),
}
missing = [p for p in figs.values() if not os.path.exists(p)]
assert not missing, 'Missing figures (run the notebooks first): ' + str(missing)

# ---------------------------------------------------------------- numbers from the notebook outputs
L = pd.read_csv(os.path.join(derived, 'genEmissions', 'GMSEUS_GenEmissions_Annual_Long_' + args.weather + '.csv'), dtype={'STATEFP': str})
V = pd.read_csv(os.path.join(derived, 'intermediateProducts', 'GMSEUS_Generation_Validation_LBNL_' + args.weather + '.csv'))
plr = pd.read_csv(os.path.join(derived, 'generation', 'GMSEUS_Generation_ModelInputs_' + args.weather + '.csv'), usecols=['plr'])['plr'].dropna()
versions = ['Avg', 'MarginalLR', 'MarginalSR']
yr1 = L[L['opYr'] == 1]
mounts = yr1['pvMount'].value_counts().reindex(['fixed', 'single_axis', 'dual_axis']).fillna(0).astype(int).to_dict()
cap = yr1['capMWDC'].sum()
avoided = {v: L['tCO2eAvoided' + v].sum() / 1e6 for v in versions}
net = {v: L['tCO2eNet' + v].sum() / 1e6 for v in versions}
up = L['tCO2eUpstreamCentral'].sum() / 1e6
payback = {v: (yr1['tCO2eUpstreamCentral'] / yr1['tCO2eAvoided' + v]).median() for v in versions}
plant = V.groupby('eiaID')[['cfModel', 'cfObs']].mean()
ny = yr1[yr1['STATEFP'] == '36']
fmt = lambda x, nd=0: ('{:,.' + str(nd) + 'f}').format(x)
S = {
    'nArrays': fmt(yr1['arrayID'].nunique()), 'capGW': fmt(cap / 1000), 'instMin': str(int(yr1['instYr'].min())), 'instMax': str(int(yr1['instYr'].max())),
    'plrMin': fmt(plr.min() * 100, 1), 'plrMax': fmt(plr.max() * 100, 1),
    'nPlants': fmt(len(plant)), 'valBias': '{:+.0f}%'.format(((plant['cfModel'] / plant['cfObs']).median() - 1) * 100),
    'futureShare': '{:.0f}%'.format(L.loc[L['calYr'] >= 2025, 'MWh'].sum() / L['MWh'].sum() * 100),
    'netAvg': fmt(net['Avg']), 'netLR': fmt(net['MarginalLR']), 'netSR': fmt(net['MarginalSR']),
    'netGtMin': fmt(min(net.values()) / 1000, 2), 'netGtMax': fmt(max(net.values()) / 1000, 2),
    'netGtMinR': fmt(min(net.values()) / 1000, 0), 'netGtMaxR': fmt(max(net.values()) / 1000, 0),
    'upMt': fmt(up), 'upShareMin': '{:.0f}'.format(up / max(avoided.values()) * 100), 'upShareMax': '{:.0f}%'.format(up / min(avoided.values()) * 100),
    'payMin': fmt(min(payback.values()), 1), 'payMax': fmt(max(payback.values()), 1),
    'payMinR': fmt(np.floor(min(payback.values())), 0), 'payMaxR': fmt(np.ceil(max(payback.values())), 0),
    'nyRate': fmt(ny['rateAvgKgMWh'].median()), 'allRate': fmt(yr1['rateAvgKgMWh'].median()),
    'nyPayLR': fmt((ny['tCO2eUpstreamCentral'] / ny['tCO2eAvoidedMarginalLR']).median(), 1),
}
print('Numbers used on the slides:', S)
def fill(t):
    for k, v in S.items(): t = t.replace('{' + k + '}', v)
    return t

# ---------------------------------------------------------------- palette and fonts (matches the figure theme)
NAVY = RGBColor(0x14, 0x39, 0x6F); BLUE = RGBColor(0x44, 0x89, 0xD3); LBLUE = RGBColor(0xE6, 0xEF, 0xFA)
SLATE = RGBColor(0x6F, 0x7C, 0x88); RED = RGBColor(0xB0, 0x2A, 0x22); LRED = RGBColor(0xFB, 0xEC, 0xEA)
INK = RGBColor(0x22, 0x22, 0x22); GREY = RGBColor(0x55, 0x55, 0x55); LGREY = RGBColor(0xF2, 0xF3, 0xF5); WHITE = RGBColor(0xFF, 0xFF, 0xFF)
STEPC = {1: SLATE, 2: BLUE, 3: RED}
HEAD = 'Arial'; BODY = 'Arial'; EQ = 'Cambria Math'

prs = Presentation(); prs.slide_width = Inches(13.333); prs.slide_height = Inches(7.5)
BLANK = prs.slide_layouts[6]
SW, SH = 13.333, 7.5

def box(slide, x, y, w, h, fill=None, line=None, shape=MSO_SHAPE.RECTANGLE, radius=None, name=None):
    s = slide.shapes.add_shape(shape, Inches(x), Inches(y), Inches(w), Inches(h))
    if fill is None: s.fill.background()
    else: s.fill.solid(); s.fill.fore_color.rgb = fill
    if line is None: s.line.fill.background()
    else: s.line.color.rgb = line; s.line.width = Pt(1)
    if radius is not None and shape == MSO_SHAPE.ROUNDED_RECTANGLE: s.adjustments[0] = radius
    s.shadow.inherit = False
    if name: s.name = name
    return s

def text(slide, x, y, w, h, runs, size=16, color=INK, bold=False, align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.TOP, font=BODY, italic=False, spacing=None, name=None):
    """runs: str, or list of paragraphs; a paragraph is a str or a list of (text, {opts}) runs"""
    tb = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    if name: tb.name = name
    tf = tb.text_frame; tf.word_wrap = True; tf.vertical_anchor = anchor
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    paras = runs if isinstance(runs, list) else [runs]
    for i, p in enumerate(paras):
        para = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        para.alignment = align
        if spacing: para.space_after = Pt(spacing)
        bullet = False
        if isinstance(p, dict): bullet = p.get('bullet', False); p = p['runs']
        segs = [(p, {})] if isinstance(p, str) else p
        if bullet:
            segs = [('\u2022  ', {'color': GREY})] + list(segs)
        for t, o in segs:
            r = para.add_run(); r.text = fill(t)
            r.font.size = Pt(o.get('size', size)); r.font.bold = o.get('bold', bold); r.font.italic = o.get('italic', italic)
            r.font.color.rgb = o.get('color', color); r.font.name = o.get('font', font)
            if o.get('sub'): r.font._element.set('baseline', '-25000')
            if o.get('sup'): r.font._element.set('baseline', '30000')
    return tb

def title(slide, t, step=None, kicker=None):
    x = 0.6
    if step:
        c = box(slide, 0.6, 0.48, 0.62, 0.62, fill=STEPC[step], shape=MSO_SHAPE.Ofigs['validation'], name='Step badge')
        text(slide, 0.6, 0.48, 0.62, 0.62, str(step), size=22, bold=True, color=WHITE, align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE, font=HEAD)
        x = 1.4
    if kicker:
        text(slide, x, 0.38, 10, 0.3, kicker.upper(), size=11, bold=True, color=STEPC.get(step, BLUE) if step else BLUE, font=HEAD, name='Kicker')
    text(slide, x, 0.62, SW - x - 0.6, 0.7, t, size=30, bold=True, color=INK, font=HEAD, anchor=MSO_ANCHOR.TOP, name='Title')

def footer(slide, num, src=None):
    text(slide, SW - 1.1, SH - 0.42, 0.5, 0.25, str(num), size=10, color=GREY, align=PP_ALIGN.RIGHT, name='Slide number')
    if src: text(slide, 0.6, SH - 0.45, SW - 2.0, 0.3, src, size=10, color=GREY, name='Source note')

def picture(slide, path, x, y, w=None, h=None, name=None, alt=''):
    p = slide.shapes.add_picture(path, Inches(x), Inches(y), Inches(w) if w else None, Inches(h) if h else None)
    p.name = name or os.path.basename(path)
    p._element.nvPicPr.cNvPr.set('descr', alt)
    return p

def eqbox(slide, x, y, w, h, paras, size=20, fill=LGREY, name='Equation'):
    box(slide, x, y, w, h, fill=fill, shape=MSO_SHAPE.ROUNDED_RECTANGLE, radius=0.08, name=name + ' background')
    text(slide, x + 0.3, y, w - 0.6, h, paras, size=size, color=INK, align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE, font=EQ, name=name)

def card(slide, x, y, w, h, head, body, accent=BLUE, size=14, fill=LGREY, headSize=16):
    box(slide, x, y, w, h, fill=fill, shape=MSO_SHAPE.ROUNDED_RECTANGLE, radius=0.06, name='Card: ' + head)
    text(slide, x + 0.25, y + 0.2, w - 0.5, 0.4, head, size=headSize, bold=True, color=accent, font=HEAD)
    text(slide, x + 0.25, y + 0.68, w - 0.5, h - 0.85, body, size=size, color=INK, spacing=4)

def stat(slide, x, y, w, big, small, color=NAVY, bigSize=40):
    text(slide, x, y, w, 0.75, big, size=bigSize, bold=True, color=color, font=HEAD, name='Stat: ' + small)
    text(slide, x, y + 0.78, w, 0.6, small, size=12, color=GREY)

def notes(slide, t): slide.notes_slide.notes_text_frame.text = fill(t)

def sub(t): return (t, {'sub': True})

# ================================================================ 1. Title (dark)
s = prs.slides.add_slide(BLANK)
s.background.fill.solid(); s.background.fill.fore_color.rgb = NAVY
text(s, 0.9, 1.6, 11.5, 0.4, 'GM-SEUS GENERATION AND EMISSIONS', size=14, bold=True, color=RGBColor(0xB4, 0xD3, 0xF2), font=HEAD)
text(s, 0.9, 2.1, 11.5, 1.6, 'From sunlight to carbon', size=54, bold=True, color=WHITE, font=HEAD)
text(s, 0.9, 3.3, 11.0, 1.0, 'How we estimate the lifetime carbon benefit of {nArrays} ground-mounted solar arrays in the United States', size=22, color=RGBColor(0xDD, 0xE6, 0xF2))
for i, (lab, c) in enumerate([('Generation', SLATE), ('Grid emissions', BLUE), ('Upstream emissions', RED)]):
    x = 0.9 + i * 3.7
    box(s, x, 5.0, 0.5, 0.5, fill=c, shape=MSO_SHAPE.Ofigs['validation'], name='Step ' + str(i + 1))
    text(s, x, 5.0, 0.5, 0.5, str(i + 1), size=16, bold=True, color=WHITE, align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
    text(s, x + 0.65, 5.0, 2.8, 0.5, lab, size=18, bold=True, color=WHITE, anchor=MSO_ANCHOR.MIDDLE)
notes(s, 'This talk walks through the three modeling steps behind the carbon numbers: how much electricity each array makes, how much grid emissions that electricity avoids, and how much was emitted to build the array in the first place.')

# ================================================================ 2. One equation
s = prs.slides.add_slide(BLANK)
title(s, 'The whole method is one subtraction', kicker='Overview')
eqbox(s, 0.6, 1.65, 12.13, 1.25, [[('Net carbon benefit  =  ', {}), ('\u03a3', {'size': 30}), (' over 25 years ( ', {}), ('Generation', {'color': SLATE, 'bold': True}), ('  \u00d7  ', {}), ('Grid emission rate', {'color': BLUE, 'bold': True}), (' )  \u2212  ', {}), ('Upstream emissions', {'color': RED, 'bold': True})]], size=21)
items = [(1, 'Generation', 'MWh per year', 'How much electricity does each array make? Modeled from weather, panel angle, and size.', 'getGeneration'),
         (2, 'Grid emission rate', 'kg CO\u2082e per MWh', 'How much pollution would the grid have made for that electricity instead?', 'getGridEmissions'),
         (3, 'Upstream emissions', 't CO\u2082e, once', 'How much was emitted to mine, make, ship, and build the array?', 'getUpstreamEmissions')]
for i, (k, head, unit, body, mod) in enumerate(items):
    x = 0.6 + i * 4.18
    box(s, x, 3.35, 3.77, 3.4, fill=LGREY, shape=MSO_SHAPE.ROUNDED_RECTANGLE, radius=0.06, name='Card: ' + head)
    box(s, x + 0.25, 3.6, 0.55, 0.55, fill=STEPC[k], shape=MSO_SHAPE.OVAL)
    text(s, x + 0.25, 3.6, 0.55, 0.55, str(k), size=18, bold=True, color=WHITE, align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
    text(s, x + 0.95, 3.58, 2.7, 0.35, head, size=18, bold=True, color=STEPC[k])
    text(s, x + 0.95, 3.92, 2.7, 0.3, unit, size=12, color=GREY)
    text(s, x + 0.25, 4.45, 3.3, 1.5, body, size=15)
    text(s, x + 0.25, 6.2, 3.3, 0.35, 'Notebook: ' + mod, size=11, color=GREY, italic=True)
footer(s, 2)
notes(s, 'Everything we report comes from this one line. For every array and every year, generation times the grid emission rate is the pollution that solar avoided. Add that up over the 25-year life, then subtract the one-time emissions from building the array. Each of the three parts is its own notebook, and a fourth notebook (processGenEmissions) combines them.')

# ================================================================ 3. The starting data
s = prs.slides.add_slide(BLANK)
title(s, 'We start with a map of every solar array', kicker='Data: GM-SEUS')
stat(s, 0.6, 1.75, 3.6, '{nArrays}', 'ground-mounted PV arrays modeled (CSP and arrays missing inputs excluded)')
stat(s, 0.6, 3.25, 3.6, '{capGW} GW', 'total DC capacity, installed {instMin}\u2013{instMax}')
text(s, 0.6, 4.8, 5.4, 2.2, [
    {'bullet': True, 'runs': [('Each array has: ', {'bold': True}), ('location, size (MW), install year, mount type, tilt, azimuth, module type', {})]},
    {'bullet': True, 'runs': [('Source: ', {'bold': True}), ('GM-SEUS v2.1, our national solar dataset built from USPVDB, OpenStreetMap, and aerial imagery (Stid et al. 2025, Scientific Data)', {})]}], size=14, spacing=8)
cd = CategoryChartData(); cd.categories = ['Fixed tilt', 'Single-axis tracker', 'Dual-axis tracker']
cd.add_series('Arrays', [mounts['fixed'], mounts['single_axis'], mounts['dual_axis']])
gf = s.shapes.add_chart(XL_CHART_TYPE.BAR_CLUSTERED, Inches(6.6), Inches(1.7), Inches(6.1), Inches(4.9), cd); gf.name = 'Chart: arrays by mount'
ch = gf.chart; ch.has_legend = False; ch.has_title = True
ch.chart_title.text_frame.text = 'Arrays by mount type'
tp = ch.chart_title.text_frame.paragraphs[0]; tp.runs[0].font.size = Pt(16); tp.runs[0].font.bold = True; tp.runs[0].font.color.rgb = INK; tp.runs[0].font.name = BODY
pl = ch.plots[0]; pl.gap_width = 60; pl.has_data_labels = True
dl = pl.data_labels; dl.number_format = '#,##0'; dl.number_format_is_linked = False; dl.position = XL_LABEL_POSITION.OUTSIDE_END; dl.font.size = Pt(14); dl.font.color.rgb = INK; dl.font.name = BODY
for i, c in enumerate([RGBColor(0xD3, 0xD3, 0xD3), RGBColor(0x7D, 0x8B, 0x99), RGBColor(0x3B, 0x46, 0x52)]):
    pt = pl.series[0].points[i]; pt.format.fill.solid(); pt.format.fill.fore_color.rgb = c; pt.format.line.color.rgb = INK; pt.format.line.width = Pt(0.5)
ca = ch.category_axis; ca.reverse_order = True; ca.tick_labels.font.size = Pt(14); ca.tick_labels.font.color.rgb = INK; ca.tick_labels.font.name = BODY; ca.format.line.color.rgb = INK; ca.has_major_gridlines = False
va = ch.value_axis; va.visible = False; va.has_major_gridlines = False; va.maximum_scale = mounts['fixed'] * 1.2
footer(s, 3)
notes(s, 'Our unit of analysis is the array. GM-SEUS gives us where each array is, how big it is, when it was built, and how its panels are mounted. Those few attributes drive everything downstream: weather and angle drive generation, location picks the grid region, and size and install year drive upstream emissions.')

# ================================================================ 4. Step 1 generation method
s = prs.slides.add_slide(BLANK)
title(s, 'A physics model turns sunlight into megawatt-hours', step=1, kicker='Step 1 \u00b7 Generation')
eqbox(s, 0.6, 1.6, 6.3, 1.0, [[('MWh', {}), sub('year 1'), ('  =  pvlib( weather, angles, mount, size )', {})]], size=19)
eqbox(s, 0.6, 2.8, 6.3, 1.0, [[('MWh', {}), sub('year n'), ('  =  MWh', {}), sub('year 1'), ('  \u00d7  ( 1 \u2212 PLR \u00d7 (n \u2212 1) )', {})]], size=19)
text(s, 0.6, 4.0, 6.3, 2.9, [
    {'bullet': True, 'runs': [('pvlib', {'bold': True}), (' is an open-source solar model: it moves the sun across the sky hour by hour and computes how much light hits the panel', {})]},
    {'bullet': True, 'runs': [('PLR', {'bold': True}), (' (performance loss rate) is how fast panels wear out: {plrMin}\u2013{plrMax}% per year, faster in hot climates', {})]},
    {'bullet': True, 'runs': [('Typical year:', {'bold': True}), (' one representative weather year (TMY) is used for all 25 years', {})]}], size=15, spacing=8)
rows = [('Input', 'Where it comes from'), ('Hourly weather (TMY)', 'PVGIS, European Commission'), ('Tilt, azimuth, mount', 'GM-SEUS (azimuth corrected)'),
        ('Inverter size (DC:AC ratio)', 'USPVDB, US Geological Survey'), ('Temperature and wear (PLR)', 'PV climate zones (pvcz)'), ('Lifetime', '25 years from install year')]
tbl = s.shapes.add_table(len(rows), 2, Inches(7.4), Inches(1.6), Inches(5.33), Inches(3.6)); tbl.name = 'Table: generation inputs'
t = tbl.table; t.columns[0].width = Inches(2.55); t.columns[1].width = Inches(2.78)
for i, (a, b) in enumerate(rows):
    for j, v in enumerate((a, b)):
        cell = t.cell(i, j); cell.text = v; p = cell.text_frame.paragraphs[0]; r = p.runs[0]
        r.font.size = Pt(13); r.font.name = BODY; r.font.bold = (i == 0); r.font.color.rgb = WHITE if i == 0 else INK
        cell.fill.solid(); cell.fill.fore_color.rgb = SLATE if i == 0 else (LGREY if i % 2 else WHITE)
        cell.margin_left = cell.margin_right = Inches(0.1)
text(s, 7.4, 5.5, 5.33, 1.3, [[('Output: ', {'bold': True}), ('MWh for each array and year, plus a month \u00d7 hour "shape" of when it generates (used in Step 2)', {})]], size=14, color=INK)
footer(s, 4)
notes(s, 'For each array we simulate one typical weather year with pvlib, using the array\'s own tilt, azimuth, and tracking. That gives year-one energy. Each later year is reduced by the panel wear rate. We also save the share of generation in each month and hour, which matters for Step 2 because grid emissions change through the day.')

# ================================================================ 5. Step 1 validation
s = prs.slides.add_slide(BLANK)
title(s, 'The model matches real plants within about 5%', step=1, kicker='Step 1 \u00b7 Check against observations')
picture(s, figs['validation'], 0.6, 1.6, w=8.5, name='Figure: generation validation', alt='Scatter of modeled vs observed capacity factor for 1,651 plants and median ratio by year')
stat(s, 9.5, 1.7, 3.3, '{nPlants}', 'utility plants matched to EIA records', bigSize=36)
stat(s, 9.5, 3.05, 3.3, '{valBias}', 'model runs slightly high (median plant)', color=BLUE, bigSize=36)
text(s, 9.5, 4.4, 3.3, 2.5, [
    {'bullet': True, 'runs': [('Why high: ', {'bold': True}), ('the model has no curtailment, outages, or grid limits', {})]},
    {'bullet': True, 'runs': [('Data: ', {'bold': True}), ('LBNL Utility-Scale Solar 2026 (from EIA Form 923)', {})]}], size=14, spacing=8)
footer(s, 5, 'Capacity factor = energy \u00f7 (capacity \u00d7 8,760 hours). a: each dot is one plant\'s multi-year average. b: plant-by-plant ratio for each year.')
notes(s, 'To check Step 1, we linked our arrays to EIA plant IDs and compared our modeled capacity factor with what each plant actually produced, as compiled by Berkeley Lab. Points near the 1:1 line mean a good match. We run about {valBias} high, which is expected because real plants lose output to curtailment and outages that we do not model. The rising ratio over time is consistent with growing curtailment, especially in California.')

# ================================================================ 6. Step 2 concepts
s = prs.slides.add_slide(BLANK)
title(s, 'Each solar MWh pushes a fossil MWh off the grid', step=2, kicker='Step 2 \u00b7 Grid emissions')
eqbox(s, 0.6, 1.6, 12.13, 0.95, [[('Avoided t CO\u2082e  =  MWh  \u00d7  grid emission rate (kg CO\u2082e/MWh)  \u00f7  1,000', {})]], size=21)
card(s, 0.6, 2.85, 3.85, 3.3, 'Average rate', [
    'All grid emissions \u00f7 all grid electricity.',
    [('Asks: ', {'bold': True}), ('what share of emissions does this electricity carry?', {})],
    [('Example: ', {'bold': True}), ('half nuclear, half gas \u2192 about 200 kg/MWh', {})]], accent=SLATE, size=14)
card(s, 4.74, 2.85, 3.85, 3.3, 'Marginal rate', [
    'Emissions of the power plant that actually turns down when solar turns on.',
    [('Asks: ', {'bold': True}), ('what did solar avoid?', {})],
    [('Same example: ', {'bold': True}), ('only gas turns down \u2192 about 400 kg/MWh', {})]], accent=BLUE, size=14)
card(s, 8.88, 2.85, 3.85, 3.3, 'Time of day matters', [
    [('Rate', {}), ('array', {'sub': True}), (' = \u03a3 share of generation in each month-hour \u00d7 rate in that month-hour', {})],
    'Solar runs at midday. In California, midday power is very clean, so solar\'s rate there is about half the daily average.'], accent=NAVY, size=14)
text(s, 0.6, 6.4, 12.1, 0.4, [[('We report both rates. ', {'bold': True}), ('They answer different questions, and both are valid.', {})]], size=14, color=INK)
footer(s, 6)
notes(s, 'The key question is which grid electricity solar replaced. The average rate spreads emissions evenly over every megawatt-hour, including nuclear and hydro. The marginal rate asks which plant actually backed off, which is usually gas. Both are legitimate; they answer different questions, so we report both. For future years we also weight the rate by when each array generates, because midday power can be much cleaner or dirtier than the daily average.')

# ================================================================ 7. Step 2 data sources
s = prs.slides.add_slide(BLANK)
title(s, 'Measured data for the past, projections for the future', step=2, kicker='Step 2 \u00b7 Data sources')
rows = [('Version', 'Before 2025 (measured)', '2025\u20132050 (projected)'),
        ('Average', 'EPA eGRID: annual average rate, 27 regions', 'NREL Cambium 2024: hourly average rate'),
        ('Marginal, long-run\n(primary, lower bound)', 'EPA AVERT: annual marginal rate for solar, 14 regions', 'Cambium long-run marginal rate (includes what gets built)'),
        ('Marginal, short-run\n(upper bound)', 'EPA AVERT (same as above)', 'Cambium short-run marginal rate (only existing plants)')]
tbl = s.shapes.add_table(4, 3, Inches(0.6), Inches(1.6), Inches(7.6), Inches(3.4)); tbl.name = 'Table: grid data by period'
t = tbl.table; t.columns[0].width = Inches(2.1); t.columns[1].width = Inches(2.75); t.columns[2].width = Inches(2.75)
rowC = [NAVY, SLATE, BLUE, NAVY]
for i, row in enumerate(rows):
    for j, v in enumerate(row):
        cell = t.cell(i, j); cell.text = fill(v)
        for p in cell.text_frame.paragraphs:
            for r in p.runs:
                r.font.size = Pt(12); r.font.name = BODY; r.font.bold = (i == 0 or j == 0)
                r.font.color.rgb = WHITE if i == 0 else (rowC[i] if j == 0 else INK)
        cell.fill.solid(); cell.fill.fore_color.rgb = NAVY if i == 0 else (LGREY if i % 2 else WHITE)
        cell.margin_left = cell.margin_right = Inches(0.08)
t.rows[0].height = Inches(0.45)
for i in range(1, 4): t.rows[i].height = Inches(0.95)
text(s, 0.6, 5.25, 7.6, 1.7, [
    {'bullet': True, 'runs': [('Gaps are filled by straight lines ', {'bold': True}), ('between data years (e.g., Cambium gives every 5th year)', {})]},
    {'bullet': True, 'runs': [('AVERT starts in 2017 for today\'s regions; ', {'bold': True}), ('2007\u20132016 use the older AVERT file\'s trend, held flat before 2007', {})]}], size=13, spacing=6)
picture(s, figs['gridRates'], 8.6, 1.5, h=5.2, name='Figure: grid emission rates', alt='Fleet generation-weighted grid emission rate by year for three versions')
footer(s, 7, 'eGRID: www.epa.gov/egrid \u00b7 AVERT: www.epa.gov/avert \u00b7 Cambium: Gagnon et al., NREL 2024')
notes(s, 'No single dataset covers the past and the future, so we join measured data for past years to NREL projections for future years. The average version is eGRID then Cambium average. The marginal version is AVERT then Cambium marginal, in two flavors. Long-run assumes the grid adjusts what it builds in response to solar, and is our primary marginal number. Short-run assumes solar only ever turns down existing gas plants, which is an upper bound. The drop at 2025 in the long-run line is that change of definition, not a data error; the short-run line is continuous.')

# ================================================================ 8. Step 2 results over time
s = prs.slides.add_slide(BLANK)
title(s, 'Most of the benefit is still ahead of us', step=2, kicker='Step 2 \u00b7 Results over time')
picture(s, figs['fleet'], 0.6, 1.45, h=5.6, name='Figure: fleet time series', alt='Annual generation, avoided and upstream emissions, and cumulative net by year')
stat(s, 6.0, 1.75, 6.5, '{futureShare}', 'of the fleet\'s 25-year generation happens in 2025 or later', bigSize=40)
text(s, 6.0, 3.25, 6.7, 3.6, [
    {'bullet': True, 'runs': [('Generation peaks around 2025 ', {'bold': True}), ('and then fades as arrays age and retire (a: bars)', {})]},
    {'bullet': True, 'runs': [('Avoided emissions shrink faster than generation, ', {'bold': True}), ('because the future grid is cleaner (b: lines)', {})]},
    {'bullet': True, 'runs': [('Upstream emissions happen up front, ', {'bold': True}), ('in each array\'s install year (b: red bars)', {})]},
    {'bullet': True, 'runs': [('Net benefit (c) ', {'bold': True}), ('ranges {netGtMin}\u2013{netGtMax} Gt CO\u2082e depending on the version', {})]}], size=15, spacing=8)
footer(s, 8)
notes(s, 'Panel a: generation by year. Panel b: avoided emissions by year for each version, with upstream emissions as negative red bars. Panel c: the running total of net benefit. Two lessons: most generation is still in the future, and the future grid is cleaner, so each future megawatt-hour avoids less. That is why the choice of future grid data matters so much.')

# ================================================================ 9. Step 3 upstream
s = prs.slides.add_slide(BLANK)
title(s, 'Building an array has a one-time carbon cost', step=3, kicker='Step 3 \u00b7 Upstream emissions')
eqbox(s, 0.6, 1.6, 7.6, 1.0, [[('Upstream t CO\u2082e  =  MW', {}), sub('DC'), ('  \u00d7  ( module + hardware ) kg/kW', {})]], size=19, fill=LRED)
rows = [('kg CO\u2082e per kW', 'Low', 'Central', 'High'), ('Silicon panel (2020)', '591', '753', '810'), ('Thin-film CdTe panel', '150', '271', '295'), ('Hardware, fixed / tracker', '42 / 47 per m\u00b2 of panel', '', '')]
tbl = s.shapes.add_table(4, 4, Inches(0.6), Inches(2.85), Inches(7.6), Inches(1.8)); tbl.name = 'Table: upstream factors'
t = tbl.table
for j, wv in enumerate([3.1, 1.5, 1.5, 1.5]): t.columns[j].width = Inches(wv)
t.cell(3, 1).merge(t.cell(3, 3))
for i, row in enumerate(rows):
    for j, v in enumerate(row):
        if i == 3 and j > 1: continue
        cell = t.cell(i, j); cell.text = v; p = cell.text_frame.paragraphs[0]; p.alignment = PP_ALIGN.LEFT if j == 0 else PP_ALIGN.CENTER
        r = p.runs[0]; r.font.size = Pt(13); r.font.name = BODY; r.font.bold = (i == 0 or j == 2); r.font.color.rgb = WHITE if i == 0 else INK
        cell.fill.solid(); cell.fill.fore_color.rgb = RED if i == 0 else (LGREY if i % 2 else WHITE)
text(s, 0.6, 4.9, 7.6, 2.1, [
    {'bullet': True, 'runs': [('Older panels cost more carbon: ', {'bold': True}), ('each time world solar capacity doubles, making a panel emits about 17% less (learning curve)', {})]},
    {'bullet': True, 'runs': [('Hardware ', {'bold': True}), ('= racking, trackers, inverters, cables, site work', {})]},
    {'bullet': True, 'runs': [('Not included: ', {'bold': True}), ('end of life (recycling, disposal) and land-use change', {})]}], size=14, spacing=6)
picture(s, figs['upstreamFactor'], 8.75, 1.5, h=5.2, name='Figure: upstream factor', alt='Upstream emissions per kW by installation year for silicon and CdTe')
footer(s, 9, 'IEA PVPS Task 12 (2023) \u00b7 Fthenakis et al. 2024, doi:10.1002/pip.3837 \u00b7 M\u00fcller et al. 2021, doi:10.1016/j.solmat.2021.111277 \u00b7 Louwen et al. 2016, doi:10.1038/ncomms13728')
notes(s, 'Upstream emissions are the carbon cost of mining, refining, manufacturing, shipping, and building. We estimate them per kilowatt of capacity from published life-cycle studies, with a low, central, and high value. Panel factors fall over time as manufacturing improves, which we capture with a learning curve tied to how much solar the world has built. Thin-film CdTe panels have much lower emissions than silicon. We book the whole upstream amount in the install year.')

# ================================================================ 10. Results: carbon budget and payback
s = prs.slides.add_slide(BLANK)
title(s, 'Arrays repay their carbon debt in {payMinR} to {payMaxR} years', kicker='Results \u00b7 Lifetime carbon budget')
picture(s, figs['budget'], 0.6, 1.55, w=6.2, name='Figure: carbon budget', alt='Avoided, upstream, and net lifetime emissions by version')
picture(s, figs['payback'], 7.0, 1.5, h=4.5, name='Figure: payback by mount', alt='Carbon payback time by mount type for average and long-run marginal versions')
stat(s, 10.75, 1.7, 2.3, '{upMt} Mt', 'upstream emissions (central)', color=RED, bigSize=30)
stat(s, 10.75, 3.05, 2.3, '{upShareMin}\u2013{upShareMax}', 'of lifetime avoided emissions', color=RED, bigSize=30)
stat(s, 10.75, 4.4, 2.3, '{payMin}\u2013{payMax} yr', 'median carbon payback', color=NAVY, bigSize=30)
text(s, 0.6, 6.25, 12.1, 0.6, [[('Payback = upstream \u00f7 first-year avoided emissions. ', {'bold': True}), ('Net benefit: {netAvg} Mt (average), {netLR} Mt (marginal long-run), {netSR} Mt (marginal short-run).', {})]], size=14)
footer(s, 10)
notes(s, 'Left: each bar is the lifetime budget for one version. Above zero is avoided emissions, darker for past years and lighter for future years. Below zero, in red, is upstream emissions, with the low-to-high range. The diamond is the net. Right: carbon payback time by mount. Trackers pay back faster because they generate more per kilowatt. Under every version, upstream emissions are a small share of what arrays avoid.')

# ================================================================ 11. Results: where
s = prs.slides.add_slide(BLANK)
title(s, 'Where the benefit lands depends on the local grid', kicker='Results \u00b7 Maps')
picture(s, figs['maps'], 0.6, 1.4, h=5.65, name='Figure: maps', alt='H3 hexagon maps of lifetime net avoided emissions for three versions and carbon payback time')
text(s, 8.5, 1.6, 4.2, 5.2, [
    {'bullet': True, 'runs': [('Blue = net carbon gain. ', {'bold': True}), ('Nearly every hexagon gains under every version', {})]},
    {'bullet': True, 'runs': [('Biggest totals ', {'bold': True}), ('are where the most solar is built: California, Texas, the Southeast, and the Midwest', {})]},
    {'bullet': True, 'runs': [('Upstate New York pays back slowest (d) ', {'bold': True}), ('because its grid is already clean (hydro and nuclear): about {nyRate} kg/MWh vs {allRate} nationally', {})]},
    {'bullet': True, 'runs': [('Under the marginal versions ', {'bold': True}), ('New York is ordinary ({nyPayLR} yr), because solar there displaces gas', {})]}], size=14, spacing=8)
footer(s, 11, 'Hexagons: Uber H3, resolution 4 (about 45 km across). Colors match the land-use carbon maps (red = loss, blue = gain).')
notes(s, 'Each hexagon sums the lifetime net benefit of the arrays inside it. Panels a to c are the three versions; d is carbon payback time. The New York result is a good example of why the version matters: on an average basis, solar there replaces clean hydro and nuclear, so payback is slow, but on a marginal basis it replaces gas and looks like everywhere else.')

# ================================================================ 12. Assumptions and takeaways (dark)
s = prs.slides.add_slide(BLANK)
s.background.fill.solid(); s.background.fill.fore_color.rgb = NAVY
text(s, 0.6, 0.5, 12, 0.8, 'What to remember', size=34, bold=True, color=WHITE, font=HEAD, name='Title')
cols = [('Key assumptions', [
            'One typical weather year, 25-year life, steady panel wear',
            'Measured grid data before 2025, NREL projections after',
            'Upstream booked in the install year; no end-of-life or land-use change',
            'Each array uses its own region: eGRID, AVERT, and Cambium regions differ']),
        ('Takeaways', [
            'Every version shows a large net carbon benefit: about {netGtMinR} to {netGtMaxR} Gt CO\u2082e',
            'Building arrays costs {upShareMin}\u2013{upShareMax} of what they avoid; payback is {payMinR}\u2013{payMaxR} years',
            'Most of the benefit is in the future, so grid projections matter most',
            'Average vs marginal is a choice of question, so report both'])]
for i, (head, lines) in enumerate(cols):
    x = 0.6 + i * 6.2
    box(s, x, 1.6, 5.9, 4.4, fill=RGBColor(0x1F, 0x4A, 0x86), shape=MSO_SHAPE.ROUNDED_RECTANGLE, radius=0.05, name='Card: ' + head)
    text(s, x + 0.35, 1.85, 5.2, 0.5, head, size=20, bold=True, color=RGBColor(0xB4, 0xD3, 0xF2))
    text(s, x + 0.35, 2.5, 5.2, 3.4, [[('•  ', {'color': RGBColor(0xB4, 0xD3, 0xF2)}), (l, {'color': WHITE})] for l in lines], size=16, color=WHITE, spacing=12)
text(s, 0.6, 6.85, 12, 0.4, 'Code: modules/dev/getGeneration \u00b7 getGridEmissions \u00b7 getUpstreamEmissions \u00b7 processGenEmissions', size=11, color=RGBColor(0xB4, 0xD3, 0xF2))
notes(s, 'If you remember one thing: the carbon benefit is large under every reasonable choice, and the upstream cost is small and paid back quickly. The biggest uncertainty is not the solar model but how clean the future grid will be, and which question (average or marginal) you want to answer.')

os.makedirs(os.path.dirname(OUT), exist_ok=True)
prs.save(OUT); print('Saved:', OUT, '|', len(prs.slides), 'slides')
