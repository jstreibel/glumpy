# -----------------------------------------------------------------------------
# Copyright (c) 2009-2016 Nicolas P. Rougier. All rights reserved.
# Distributed under the (new) BSD License.
# -----------------------------------------------------------------------------
import csv, json
import numpy as np
from itertools import chain
from glumpy import app, gl, data
from glumpy.graphics.collections import PathCollection, PolygonCollection
from glumpy.transforms import GeoPosition, Position, OrthographicProjection, PanZoom, Viewport
from glumpy.transforms import ConicEqualArea, Albers


def relative_to_absolute(arc, scale=None, translate=None):
    if scale and translate:
        a, b = 0, 0
        for ax, bx in arc:
            a += ax
            b += bx
            yield scale[0]*a + translate[0], scale[1]*b + translate[1]
    else:
        for x, y in arc:
            yield x, y

def convert_coordinates(arcs, topology_arcs, scale=None, translate=None):
    if isinstance(arcs[0], int):
        coords = [
            list(
                relative_to_absolute(
                    topology_arcs[arc if arc >= 0 else ~arc],
                    scale,
                    translate )
                 )[::arc >= 0 or -1][i > 0:] \
            for i, arc in enumerate(arcs) ]
        return list(chain.from_iterable(coords))
    elif isinstance(arcs[0], (list, tuple)):
        return list(
            convert_coordinates(arc, topology_arcs, scale, translate) for arc in arcs)
    else:
        raise ValueError("Invalid input %s", arcs)

def geometry(obj, topology_arcs, scale=None, translate=None):
    return {
        "type": obj['type'],
        "coordinates": convert_coordinates(
            obj['arcs'], topology_arcs, scale, translate )}


window = app.Window(2*960, 2*600, color=(1,1,1,1))

@window.event
def on_draw(dt):
    window.clear()
    polys.draw()
    paths.draw()


Lower48 = ConicEqualArea(scale = 2*1285,
                         parallels = (29.5, 45.5),
                         rotate = (96,0),
                         translate = (0,0),
                         center = (0.38, -0.41),
                         clip = [-180, +180, -90, +90.0] )

Alaska = ConicEqualArea(scale=2*1285/3.0,
                        parallels = (55, 65),
                        rotate = (154, 0),
                        center = (.32, -.8),
                        clip = [-200, +200, +50, 100] )
     
Hawai = ConicEqualArea(scale=2*1285,
                        parallels = (8, 18),
                        rotate = (157, 0),
                        center = (.24, -.32),
                        clip = [-180, -140, -90, +90] )

transform = PanZoom(OrthographicProjection(
                 Position(Lower48(Hawai(Alaska(GeoPosition()))))))

fragment = """
#include "colormaps/colormaps.glsl"

varying float rate;
void main(void)
{
    gl_FragColor = vec4(colormap_autumn(1-rate),1.0);
}
"""

user_dtype = ('rate', (np.float32, 1), 'shared', 0.0),

paths = PathCollection("agg+", transform=transform, linewidth='shared', color="shared")
polys = PolygonCollection("raw", transform=transform, color="shared",
                          user_dtype=user_dtype, fragment=fragment)


with open(data.get("us.json"), 'r') as file:
    topology = json.load(file)

unemployment = {}
with open(data.get('us-unemployment.tsv'), 'r') as file:
    reader = csv.reader(file, delimiter='\t')
    next(reader, None) # skip the header
    for row in reader:
        key   = int(row[0])
        value = float(row[1]) / 0.16
        unemployment[key] = value

scale = topology['transform']['scale']
translate = topology['transform']['translate']
arcs = topology["arcs"]

linewidth = 2.5
color = 0.0,0.0,0.0,1.0
land = topology["objects"]["land"]

for coords in geometry(land, arcs, scale, translate)["coordinates"]:
    for path in coords:
        V = np.zeros((len(path),3))
        V[:,:2] = np.array(path)
        paths.append(V, closed=True, color=color, linewidth=linewidth)

linewidth = 1.0
color = 0.0,0.0,0.0,1.0
for state in topology["objects"]["states"]["geometries"]:
    if state["type"] == "Polygon":
        P = geometry(state, arcs, scale, translate)["coordinates"][0]
        V = np.zeros((len(P),3))
        V[:,:2] = P
        paths.append(V, closed=True, color=color, linewidth=linewidth)
    elif state["type"] == "MultiPolygon":
        for P in geometry(state, arcs, scale, translate)["coordinates"]:
            V = np.zeros((len(P[0]),3))
            V[:,:2] = P[0]
            paths.append(V, closed=True, color=color, linewidth=linewidth)

linewidth = 0.5
color = 0.5,0.5,0.5,1.0
for county in topology["objects"]["counties"]["geometries"]:

    if county["type"] == "Polygon":
        P = geometry(county, arcs, scale, translate)["coordinates"][0]
        V = np.zeros((len(P),3))
        V[:,:2] = P
        paths.append(V, closed=True, color=color, linewidth=linewidth)
        if len(V) > 3:
            key = county["id"]
            if key in unemployment.keys():
                c = 10*unemployment[county["id"]]
                rate = unemployment[county["id"]]
            else:
                rate = 0.0
            rgba = c,c,c,1
            polys.append(V[:-1], color=rgba, rate=rate)

    elif county["type"] == "MultiPolygon":
        for P in geometry(county, arcs, scale, translate)["coordinates"]:
            V = np.zeros((len(P[0]),3))
            V[:,:2] = P[0]
            paths.append(V, closed=True, color=color, linewidth=linewidth)
            if len(V) > 3:
                key = county["id"]
                if key in unemployment.keys():
                    c = 10*unemployment[county["id"]]
                    rate = unemployment[county["id"]]
                else:
                    rate = 0.0
                    # c = 1
                rgba = c,c,c,1
                polys.append(V[:-1], color=rgba, rate=rate)

window.attach(paths["transform"])
window.attach(paths["viewport"])
app.run()
