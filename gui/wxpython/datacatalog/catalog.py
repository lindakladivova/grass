"""
@package datacatalog::catalog

@brief Data catalog

Classes:
 - datacatalog::DataCatalog

(C) 2014-2018 by Tereza Fiedlerova, and the GRASS Development Team

This program is free software under the GNU General Public
License (>=v2). Read the file COPYING that comes with GRASS
for details.

@author Tereza Fiedlerova
"""

import wx
import os

from core.gthread import gThread
from core.debug import Debug
from core.gcmd import GError
from datacatalog.tree import DataCatalogTree
from datacatalog.toolbars import DataCatalogToolbar
from startup.guiutils import create_mapset_interactively
from grass.script import gisenv

from grass.pydispatch.signal import Signal


class DataCatalog(wx.Panel):
    """Data catalog panel"""

    def __init__(self, parent, giface=None, id=wx.ID_ANY,
                 title=_("Data catalog"), name='catalog', **kwargs):
        """Panel constructor  """
        self.showNotification = Signal('DataCatalog.showNotification')
        self.changeMapset = Signal('DataCatalog.changeMapset')
        self.changeLocation = Signal('DataCatalog.changeLocation')
        self.parent = parent
        self.baseTitle = title
        wx.Panel.__init__(self, parent=parent, id=id, **kwargs)
        self.SetName("DataCatalog")

        Debug.msg(1, "DataCatalog.__init__()")

        # toolbar
        self.toolbar = DataCatalogToolbar(parent=self)

        # tree with layers
        self.tree = DataCatalogTree(self, giface=giface)
        self.thread = gThread()
        self._loaded = False
        self.tree.showNotification.connect(self.showNotification)
        self.tree.changeMapset.connect(self.changeMapset)
        self.tree.changeLocation.connect(self.changeLocation)

        # some layout
        self._layout()

    def _layout(self):
        """Do layout"""
        sizer = wx.BoxSizer(wx.VERTICAL)

        sizer.Add(self.toolbar, proportion=0,
                  flag=wx.EXPAND)

        sizer.Add(self.tree.GetControl(), proportion=1,
                  flag=wx.EXPAND)

        self.SetAutoLayout(True)
        self.SetSizer(sizer)

        self.Layout()

    def LoadItems(self):
        if self._loaded:
            return

        self.thread.Run(callable=self.tree.InitTreeItems,
                        ondone=lambda event: self.LoadItemsDone())

    def LoadItemsDone(self):
        self._loaded = True
        self.tree.UpdateCurrentDbLocationMapsetNode()
        self.tree.ExpandCurrentMapset()

    def OnReloadTree(self, event):
        """Reload whole tree"""
        self.tree.ReloadTreeItems()
        self.tree.ExpandCurrentMapset()

    def OnReloadCurrentMapset(self, event):
        """Reload current mapset tree only"""
        self.tree.ReloadCurrentMapset()

    def OnAddGrassDB(self, event):
        """Add an existing grass database"""
        dlg = wx.DirDialog(self, _("Choose GRASS data directory:"),
                           os.getcwd(), wx.DD_DEFAULT_STYLE)
        if dlg.ShowModal() == wx.ID_OK:
            grassdatabase = dlg.GetPath()
            self.tree.InsertGrassDb(name=grassdatabase)

        dlg.Destroy()

    def OnCreateMapset(self, event):
        """Create new mapset in current location"""
        genv = gisenv()
        gisdbase = genv['GISDBASE']
        location = genv['LOCATION_NAME']
        try:
            mapset = create_mapset_interactively(self, gisdbase, location)
            if mapset:
                item = self.tree._model.SearchNodes(name=location,
                                                    type='location')
                self.tree.InsertMapset(name=mapset,
                                  location_node=item)
                self.tree.ReloadTreeItems()
        except Exception as e:
            GError(parent=self,
                   message=_("Unable to create new mapset: %s") % e,
                   showTraceback=False)

    def SetRestriction(self, restrict):
        """Allow editing other mapsets or restrict editing to current mapset"""
        self.tree.SetRestriction(restrict)

    def Filter(self, text):
        self.tree.Filter(text=text)
