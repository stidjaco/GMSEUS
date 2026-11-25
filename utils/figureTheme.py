"""
Shared figure theme for GM-SEUS generation and emissions figures.

Style: Arial, 7 pt text, thin axes with outward ticks, no top or right spines, no legend frames, bold
lowercase panel letters. Widths follow Nature (89 mm single column, 183 mm double column). Colors:
carbon loss in reds and carbon gain in blues (binned, matching the land-use carbon maps), the three
grid versions in a grey-to-blue sequence, upstream emissions in red, and mounts in light grey / slate.

Use:
    import figureTheme as ft
    ft.apply()                       # set matplotlib rcParams
    fig, ax = plt.subplots(figsize=(ft.figWidth['single'], 60 * ft.mm))
    ...
    ft.saveFig(fig, figureFolder, 'name')   # PNG (600 dpi) + vector PDF
"""
import os
import numpy as np
import matplotlib as mpl
from matplotlib.colors import BoundaryNorm, ListedColormap

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ Sizes

mm = 1 / 25.4
figWidth = {'single': 89 * mm, 'onehalf': 120 * mm, 'double': 183 * mm} # Nature column widths (inches)

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ Colors

# Binned diverging carbon palette (loss -> neutral -> gain), matching the land-use carbon maps
lossColors = ['#6B1510', '#B02A22', '#D9533D', '#EA877B', '#F4B7AB'] # strongest loss first
neutralColor = '#E3E2DD'
gainColors = ['#B4D3F2', '#80B1E6', '#4489D3', '#2160AC', '#14396F'] # weakest gain first
ink = '#222222'
textGrey = '#555555'
lineGrey = '#7A7A7A'

# Grid versions (grey for attributional average, blues for the marginal bounds), upstream in red
versionColors = {'Avg': '#6F7C88', 'MarginalLR': '#4489D3', 'MarginalSR': '#14396F'}
versionLabels = {'Avg': 'Average', 'MarginalLR': 'Marginal, long-run', 'MarginalSR': 'Marginal, short-run'}
upstreamColor = '#B02A22'
upstreamDark = '#5A0F0B'
mountColors = {'fixed': '#D3D3D3', 'single_axis': '#7D8B99', 'dual_axis': '#3B4652'} # light grey / slate
mountLabels = {'fixed': 'Fixed', 'single_axis': 'Single-axis', 'dual_axis': 'Dual-axis'}

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ Style

rcParams = {
    'font.family': 'sans-serif', 'font.sans-serif': ['Arial', 'Helvetica', 'DejaVu Sans'], 'font.size': 7,
    'axes.titlesize': 7, 'axes.titleweight': 'bold', 'axes.labelsize': 7, 'axes.linewidth': 0.6, 'axes.edgecolor': ink,
    'axes.spines.top': False, 'axes.spines.right': False, 'axes.labelcolor': ink, 'axes.titlepad': 4,
    'xtick.labelsize': 6.5, 'ytick.labelsize': 6.5, 'xtick.direction': 'out', 'ytick.direction': 'out',
    'xtick.major.width': 0.6, 'ytick.major.width': 0.6, 'xtick.major.size': 2.5, 'ytick.major.size': 2.5, 'xtick.color': ink, 'ytick.color': ink,
    'legend.frameon': False, 'legend.fontsize': 6.5, 'legend.handlelength': 1.4, 'legend.handletextpad': 0.5,
    'lines.linewidth': 1.0, 'patch.linewidth': 0.4, 'hatch.linewidth': 0.4,
    'savefig.dpi': 600, 'savefig.bbox': 'tight', 'savefig.pad_inches': 0.02, 'pdf.fonttype': 42, 'ps.fonttype': 42, 'svg.fonttype': 'none',
}

def apply():
    """Set the shared matplotlib style."""
    mpl.rcParams.update(rcParams)

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ Helpers

def panelLabel(ax, letter, x=-0.14, y=1.04):
    """Bold lowercase panel letter at the top left of an axis."""
    ax.text(x, y, letter, transform=ax.transAxes, fontsize=8, fontweight='bold', va='bottom', ha='left')

def markProjected(ax, year=2025, ypos=0.98, labels=True):
    """Dashed line at the historical / projected boundary (first projected year), optionally labeled."""
    ax.axvline(year - 0.5, color=lineGrey, lw=0.6, ls=(0, (3, 2)), zorder=0)
    if not labels: return
    ax.text(year - 0.5, ypos, ' Projected', transform=ax.get_xaxis_transform(), fontsize=6, color=textGrey, va='top', ha='left')
    ax.text(year - 0.5, ypos, 'Historical ', transform=ax.get_xaxis_transform(), fontsize=6, color=textGrey, va='top', ha='right')

def binnedDiverging(posEdges):
    """Binned diverging colormap and norm from symmetric positive bin edges (e.g., [1, 10, 100]). Returns cmap, norm, edges."""
    nBins = len(posEdges)
    colors = lossColors[-nBins:] + [neutralColor] + gainColors[:nBins]
    edges = [-np.inf] + [-e for e in posEdges[::-1]] + list(posEdges) + [np.inf]
    return ListedColormap(colors), BoundaryNorm(edges, len(colors)), edges

def binnedBar(fig, rect, cmap, edges, label, endLabels=('Carbon loss', 'Carbon gain'), fmt=lambda e: '{:g}'.format(e)):
    """Binned legend bar (discrete boxes, labels at the bin edges, bold end labels) like the land-use maps."""
    cax = fig.add_axes(rect)
    nC = cmap.N
    for i in range(nC):
        cax.add_patch(mpl.patches.Rectangle((i + 0.03, 0), 0.94, 1, color=cmap(i), lw=0))
    cax.set_xlim(0, nC); cax.set_ylim(0, 1)
    cax.set_xticks(np.arange(1, nC)); cax.set_xticklabels([fmt(e).replace('-', '−') for e in edges[1:-1]])
    cax.tick_params(axis='x', length=0, pad=2, labelsize=6, colors=textGrey); cax.set_yticks([])
    for s in cax.spines.values(): s.set_visible(False)
    cax.set_xlabel(label, fontsize=6.5, color=textGrey, labelpad=3)
    if endLabels:
        cax.text(0, 1.15, endLabels[0], transform=cax.transAxes, fontsize=6.5, fontweight='bold', ha='left', va='bottom')
        cax.text(1, 1.15, endLabels[1], transform=cax.transAxes, fontsize=6.5, fontweight='bold', ha='right', va='bottom')
    return cax

def kFormat(e):
    """Format a bin edge with a k suffix at 1,000 and above (e.g., 10000 -> '10k')."""
    return '{:g}k'.format(e / 1000) if abs(e) >= 1000 else '{:g}'.format(e)

def styleMap(ax, states, conus):
    """Map axis without a frame, with grey state lines and a dark CONUS outline (GeoDataFrames in the map CRS)."""
    states.boundary.plot(ax=ax, color='#9A9A9A', lw=0.25, zorder=3)
    conus.boundary.plot(ax=ax, color='#4A4A4A', lw=0.5, zorder=4)
    ax.set_axis_off(); ax.set_aspect('equal')

def saveFig(fig, folder, name, formats=('png', 'pdf')):
    """Save a figure as PNG (600 dpi) and vector PDF in folder."""
    os.makedirs(folder, exist_ok=True)
    for ext in formats:
        fig.savefig(os.path.join(folder, name + '.' + ext))
    print('Saved:', os.path.join(folder, name), '(' + ', '.join('.' + f for f in formats) + ')')

def fmtNum(v, nd=0):
    """Thousands separators and a unicode minus."""
    return ('{:,.' + str(nd) + 'f}').format(v).replace('-', '−')
