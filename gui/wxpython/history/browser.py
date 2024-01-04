"""
@package history.browser

@brief History browser

Classes:
 - browser::HistoryBrowser

(C) 2023 by Linda Karlovska, and the GRASS Development Team

This program is free software under the GNU General Public
License (>=v2). Read the file COPYING that comes with GRASS
for details.

@author Linda Karlovska (Kladivova) linda.karlovska@seznam.cz
"""

import wx
import re
import copy

from core import globalvar
from core.gcmd import GError, GException
from gui_core.forms import GUI
from gui_core.treeview import CTreeView
from gui_core.wrap import Menu
from core.treemodel import TreeModel, ModuleNode

from grass.pydispatch.signal import Signal

from grass.grassdb.history import read_history, get_current_mapset_gui_history_path


class HistoryBrowser(wx.Panel):
    """History browser for executing the commands from history log.

    Signal:
        showNotification - attribute 'message'
    """

    def __init__(
        self,
        parent,
        giface,
        id=wx.ID_ANY,
        title=_("History browser"),
        name="history",
        **kwargs,
    ):
        self.parent = parent
        self._giface = giface

        self.showNotification = Signal("HistoryBrowser.showNotification")
        self.runIgnoredCmdPattern = Signal("HistoryBrowser.runIgnoredCmdPattern")
        wx.Panel.__init__(self, parent=parent, id=id, **kwargs)

        self._createTree()

        self._giface.currentMapsetChanged.connect(self.UpdateHistoryModelFromScratch)
        self._giface.addEntryToHistory.connect(
            lambda cmd: self.UpdateHistoryModelByCommand(cmd)
        )
        self._layout()

    def _layout(self):
        """Dialog layout"""
        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(
            self._tree, proportion=1, flag=wx.EXPAND | wx.LEFT | wx.RIGHT, border=5
        )

        self.SetSizerAndFit(sizer)
        self.SetAutoLayout(True)
        self.Layout()

    def _createTree(self):
        """Create tree based on the model"""
        self._model = TreeModel(ModuleNode)
        self._fillModel()
        self._tree = self._getTreeInstance()
        self._refreshTree()
        self._tree.SetToolTip(_("Double-click to open the tool"))
        self._tree.selectionChanged.connect(self.OnItemSelected)
        self._tree.itemActivated.connect(lambda node: self.Run(node))
        self._tree.contextMenu.connect(self.OnRightClick)

    def _confirmDialog(self, question, title):
        """Confirm dialog"""
        dlg = wx.MessageDialog(self, question, title, wx.YES_NO)
        res = dlg.ShowModal()
        dlg.Destroy()
        return res

    def _getTreeInstance(self):
        return CTreeView(model=self._getModel(), parent=self)

    def _getSelectedNode(self):
        selection = self._tree.GetSelected()
        if not selection:
            return None
        return selection[0]

    def _popupMenuLayer(self):
        """Create popup menu for commands"""
        menu = Menu()

        item = wx.MenuItem(menu, wx.ID_ANY, _("&Delete"))
        menu.AppendItem(item)
        self.Bind(wx.EVT_MENU, self.OnDeleteCmd, item)

        self.PopupMenu(menu)
        menu.Destroy()

    def _getModel(self):
        """Returns a deep copy of the model."""
        return copy.deepcopy(self._model)

    def _refreshTree(self):
        self._tree.SetModel(self._getModel())

    def _fillModel(self):
        """Fill tree history model based on the current history log from scratch."""
        self._model.RemoveNode(self._model.root)
        self._history_path = get_current_mapset_gui_history_path()
        if self._history_path:
            cmd_list = read_history(self._history_path)
            for label in cmd_list:
                data = {"command": label.strip()}
                self._model.AppendNode(
                    parent=self._model.root,
                    label=data["command"],
                    data=data,
                )

    def UpdateHistoryModelFromScratch(self):
        """Update tree history model based on the current history log from scratch."""
        self._fillModel()
        self._refreshTree()

    def UpdateHistoryModelByCommand(self, label):
        """Update the model by the command and refresh the tree.

        :param label: model node label"""
        data = {"command": label}
        self._model.AppendNode(
            parent=self._model.root,
            label=data["command"],
            data=data,
        )
        self._refreshTree()

    def OnDeleteCmd(self, event):
        """Delete cmd from the history file"""
        tree_node = self._getSelectedNode()
        cmd = tree_node.data["command"]
        question = _("Do you really want to delete <{}> command?").format(cmd)
        if self._confirmDialog(question, title=_("Delete command")) == wx.ID_YES:
            self.showNotification.emit(message=_("Deleting <{}>").format(cmd))
            model_tuple = self._model.GetIndexOfNode(tree_node)
            model_node = self._model.GetNodeByIndex(model_tuple)
            self._giface.removeEntryFromHistory.emit(index=model_tuple[0])
            self._model.RemoveNode(model_node)
            self._refreshTree()
            self.showNotification.emit(message=_("<{}> deleted").format(cmd))

    def OnItemSelected(self, node):
        """Item selected"""
        command = node.data["command"]
        self.showNotification.emit(message=command)

    def OnRightClick(self, node):
        """Display popup menu"""
        self._popupMenuLayer()

    def Run(self, node=None):
        """Parse selected history command into list and launch module dialog."""
        node = node or self._getSelectedNode()
        if node:
            command = node.data["command"]
            lst = re.split(r"\s+", command)
            if (
                globalvar.ignoredCmdPattern
                and re.compile(globalvar.ignoredCmdPattern).search(command)
                and "--help" not in command
                and "--ui" not in command
            ):
                self.runIgnoredCmdPattern.emit(cmd=lst)
                return
            try:
                GUI(parent=self, giface=self._giface).ParseCommand(lst)
            except GException as e:
                GError(
                    parent=self,
                    message=str(e),
                    caption=_("Cannot be parsed into command"),
                    showTraceback=False,
                )
