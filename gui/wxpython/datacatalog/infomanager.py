
import wx
import webbrowser

from grass.script import gisenv


class InfoManagerDataCatalog:
    """
    InfoBar Manager for Data Catalog
    """
    def __init__(self, infobar, sizer):
        self.infoBar = infobar
        self.sizer = sizer

    def ShowInfoBar1(self, buttons):
        self.sizer.Add(self.infoBar, wx.SizerFlags().Expand())
        self.infoBar.SetButtons(buttons)
        self.infoBar.ShowMessage(_(
            "GRASS GIS helps you organize your data using Locations (projects) "
            "which contain Mapsets (subprojects). All data in one Location is "
            "in the same coordinate reference system (CRS).\n\n"
            "You are currently in Mapset PERMANENT in Location {loc} which uses "
            "WGS 84 (EPSG:4326). Consider creating a new Location with a CRS "
            "specific to your area. You can do it now or anytime later from "
            "the toolbar above."
        ).format(loc=gisenv()['LOCATION_NAME']), wx.ICON_INFORMATION)

    def _onLearnMore(self, event):
        webbrowser.open("https://grass.osgeo.org/grass79/manuals/grass_database.html")
        event.Skip()
