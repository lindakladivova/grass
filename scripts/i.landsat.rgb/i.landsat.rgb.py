#!/usr/bin/env python

############################################################################
#
# MODULE:	i.landsat.rgb
#
# AUTHOR(S):	Markus Neteler. <neteler itc it>
#		Hamish Bowman, scripting enhancements
#               Converted to Python by Glynn Clements
#
# PURPOSE:      create pretty LANDSAT RGBs: the trick is to remove outliers 
#               using percentiles (area under the histogram curve)
#
# COPYRIGHT:	(C) 2006,2008 by the GRASS Development Team
#
#		This program is free software under the GNU General Public
#		License (>=v2). Read the file COPYING that comes with GRASS
#		for details.
#
# TODO: implement better brightness control
#############################################################################

#%Module
#%  description: Auto-balancing of colors for LANDSAT images
#%  keywords: raster, imagery, colors
#%End
#%option
#% key: red
#% type: string
#% gisprompt: old,cell,raster
#% description: LANDSAT red channel
#% required : yes
#%end
#%option
#% key: green
#% type: string
#% gisprompt: old,cell,raster
#% description: LANDSAT green channel
#% required : yes
#%end
#%option
#% key: blue
#% type: string
#% gisprompt: old,cell,raster
#% description: LANDSAT blue channel
#% required : yes
#%end
#%option
#% key: strength
#% type: integer
#% description: Cropping intensity (upper brightness level)
#% options: 0-100
#% answer : 98
#% required : no
#%end
#%flag
#% key: f
#% description: Extend colors to full range of data on each channel
#%end
#%flag
#% key: p
#% description: Preserve relative colors, adjust brightness only
#%end
#%flag
#% key: r
#% description: Reset to standard color range
#%end

import sys
import os
import string
import grass

def get_percentile(map, percentile):
    s = grass.read_command('r.univar', flags = 'ge', map = map, percentile = percentile)
    kv = grass.parse_key_val(s)
    return float(kv['percentile_%s' % percentile])

def set_colors(map, v0, v1):
    rules = [
	"0% black\n",
	"%f black\n" % v0,
	"%f white\n" % v1,
	"100% white\n"
	]
    rules = ''.join(rules)
    grass.write_command('r.colors', map = map, rules = '-', stdin = rules)

def main():
    red = options['red']
    green = options['green']
    blue = options['blue']
    brightness = options['strength']
    full = flags['f']
    preserve = flags['p']
    reset = flags['r']

    # 90 or 98? MAX value controls brightness
    # think of percent (0-100), must be positive or 0
    # must be more than "2" ?

    if full:
	for i in [red, green, blue]:
	    grass.run_command('r.colors', map = i, color = 'grey')
	sys.exit(0)

    if reset:
	for i in [red, green, blue]:
	    grass.run_command('r.colors', map = i, color = 'grey255')
	sys.exit(0)

    if not preserve:
	for i in [red, green, blue]:
	    grass.message("Processing <%s> ..." % i)
	    v0 = get_percentile(i, 2)
	    v1 = get_percentile(i, brightness)
	    grass.debug("<%s>:  min=%f   max=%f" % (i, v0, v1))
	    set_colors(i, v0, v1)
    else:
	all_max = 0
	all_min = 255
	for i in [red, green, blue]:
	    grass.message("Processing <%s> ..." % i)
	    v0 = get_percentile(i, 2)
	    v1 = get_percentile(i, brightness)
	    grass.debug("<%s>:  min=%f   max=%f" % (i, v0, v1))
	    all_min = min(all_min, v0)
	    all_max = max(all_max, v1)
	grass.debug("all_min=%f   all_max=%f" % (all_min, all_max))
	for i in [red, green, blue]:
	    set_colors(i, v0, v1)

    # write cmd history:
    for i in [red, green, blue]:
	grass.run_command('r.support', map = i, history = os.environ['CMDLINE'])

if __name__ == "__main__":
    options, flags = grass.parser()
    main()
