"""
@package history.tree

@brief History browser tree classes

Classes:
 - history::HistoryInfoDialog
 - history::HistoryBrowserTree

(C) 2023 by Linda Karlovska, and the GRASS Development Team

This program is free software under the GNU General Public
License (>=v2). Read the file COPYING that comes with GRASS
for details.

@author Linda Karlovska (Kladivova) linda.karlovska@seznam.cz
@author Anna Petrasova (kratochanna gmail com)
@author Tomas Zigo
"""

import re
import copy

import wx
import wx.lib.scrolledpanel as SP

from core import globalvar

from core.gcmd import GError, GException
from core.utils import (
    parse_mapcalc_cmd,
    replace_module_cmd_special_flags,
    split,
)
from gui_core.forms import GUI
from core.treemodel import TreeModel, ModuleNode
from gui_core.treeview import CTreeView
from gui_core.wrap import Menu, Button, StaticText

from grass.pydispatch.signal import Signal

from grass.grassdb.history import create_history_manager


class HistoryInfoDialog(wx.Dialog):
    def __init__(
        self,
        parent,
        command_info,
        title=("Command Info"),
        size=(-1, 400),
        style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER,
    ):
        wx.Dialog.__init__(self, parent=parent, id=wx.ID_ANY, title=title, style=style)

        self.parent = parent
        self.title = title
        self.size = size
        self.command_info = command_info

        # notebook
        self.notebook = wx.Notebook(parent=self, id=wx.ID_ANY, style=wx.BK_DEFAULT)
        # create notebook pages
        self._createGeneralInfoPage(parent=self.notebook)
        self._createRegionSettingsPage(parent=self.notebook)

        self.btnClose = Button(self, wx.ID_CLOSE)
        self.SetEscapeId(wx.ID_CLOSE)

        self._layout()

    def _layout(self):
        """Layout window"""
        # sizers
        btnStdSizer = wx.StdDialogButtonSizer()
        btnStdSizer.AddButton(self.btnClose)
        btnStdSizer.Realize()

        mainSizer = wx.BoxSizer(wx.VERTICAL)
        mainSizer.Add(self.notebook, proportion=1, flag=wx.EXPAND | wx.ALL, border=5)
        mainSizer.Add(btnStdSizer, proportion=0, flag=wx.EXPAND | wx.ALL, border=5)

        self.SetSizer(mainSizer)
        self.SetMinSize(self.GetBestSize())
        self.SetSize(self.size)

    def _createGeneralInfoPage(self, parent):
        """Create notebook page for general info about the command"""

        panel = SP.ScrolledPanel(parent=parent, id=wx.ID_ANY)
        panel.SetupScrolling(scroll_x=False, scroll_y=True)
        parent.AddPage(page=panel, text=_("General info"))

        # General settings
        self.sizer = wx.GridBagSizer(vgap=0, hgap=0)
        self.sizer.SetCols(5)
        self.sizer.SetRows(8)

        for index, (key, value) in enumerate(self.command_info.items()):
            if key != "Region settings":
                self.sizer.Add(
                    StaticText(
                        parent=panel,
                        id=wx.ID_ANY,
                        label=_("{0}:".format(key)),
                        style=wx.ALIGN_LEFT,
                    ),
                    flag=wx.ALIGN_LEFT | wx.ALL,
                    border=5,
                    pos=(index + 1, 0),
                )
                self.sizer.Add(
                    StaticText(
                        parent=panel,
                        id=wx.ID_ANY,
                        label=_("{0}".format(value)),
                        style=wx.ALIGN_LEFT,
                    ),
                    flag=wx.ALIGN_LEFT | wx.ALL,
                    border=5,
                    pos=(index + 1, 1),
                )

        self.sizer.AddGrowableCol(1)
        panel.SetSizer(self.sizer)

    def _createRegionSettingsPage(self, parent):
        """Create notebook page for displaying region settings of the command"""

        region_settings = self.command_info["Region settings"]

        panel = SP.ScrolledPanel(parent=parent, id=wx.ID_ANY)
        panel.SetupScrolling(scroll_x=False, scroll_y=True)
        parent.AddPage(page=panel, text=_("Region settings"))

        # General settings
        self.sizer = wx.GridBagSizer(vgap=0, hgap=0)
        self.sizer.SetCols(5)
        self.sizer.SetRows(8)

        for index, (key, value) in enumerate(region_settings.items()):
            self.sizer.Add(
                StaticText(
                    parent=panel,
                    id=wx.ID_ANY,
                    label=_("{0}:".format(key)),
                    style=wx.ALIGN_LEFT,
                ),
                flag=wx.ALIGN_LEFT | wx.ALL,
                border=5,
                pos=(index + 1, 0),
            )
            self.sizer.Add(
                StaticText(
                    parent=panel,
                    id=wx.ID_ANY,
                    label=_("{0}".format(value)),
                    style=wx.ALIGN_LEFT,
                ),
                flag=wx.ALIGN_LEFT | wx.ALL,
                border=5,
                pos=(index + 1, 1),
            )

        self.sizer.AddGrowableCol(1)
        panel.SetSizer(self.sizer)


class HistoryBrowserTree(CTreeView):
    """Tree structure visualizing and managing history of executed commands.
    Uses virtual tree and model defined in core/treemodel.py.
    """

    def __init__(
        self,
        parent,
        model=None,
        giface=None,
        style=wx.TR_HIDE_ROOT
        | wx.TR_LINES_AT_ROOT
        | wx.TR_HAS_BUTTONS
        | wx.TR_FULL_ROW_HIGHLIGHT,
    ):
        """History Browser Tree constructor."""
        self._model = TreeModel(ModuleNode)
        self._orig_model = self._model
        super().__init__(parent=parent, model=self._model, id=wx.ID_ANY, style=style)

        self._giface = giface
        self.parent = parent

        self._initHistoryModel()

        self.showNotification = Signal("HistoryBrowserTree.showNotification")
        self.runIgnoredCmdPattern = Signal("HistoryBrowserTree.runIgnoredCmdPattern")

        self._giface.currentMapsetChanged.connect(self.UpdateHistoryModelFromScratch)
        self._giface.entryToHistoryAdded.connect(
            lambda entry: self.AppendNodeToHistoryModel(entry)
        )
        self._giface.entryInHistoryUpdated.connect(
            lambda entry: self.UpdateNodeInHistoryModel(entry)
        )

        self.SetToolTip(_("Double-click to open the tool"))
        self.selectionChanged.connect(self.OnItemSelected)
        self.itemActivated.connect(lambda node: self.Run(node))
        self.contextMenu.connect(self.OnRightClick)

    def _initHistoryModel(self):
        """Fill tree history model based on the current history log."""
        self.history_manager = create_history_manager()
        content_list = self.history_manager.get_content()
        print(content_list)
        for data in content_list:
            print(data)
            self._model.AppendNode(
                parent=self._model.root,
                label=data["command"].strip(),
                data=data,
            )
        self._refreshTree()

    def _refreshTree(self):
        """Refresh tree models"""
        self.SetModel(copy.deepcopy(self._model))
        self._orig_model = self._model

    def _getSelectedNode(self):
        selection = self.GetSelected()
        if not selection:
            return None
        return selection[0]

    def _confirmDialog(self, question, title):
        """Confirm dialog"""
        dlg = wx.MessageDialog(self, question, title, wx.YES_NO)
        res = dlg.ShowModal()
        dlg.Destroy()
        return res

    def _popupMenuLayer(self):
        """Create popup menu for commands"""
        menu = Menu()

        item = wx.MenuItem(menu, wx.ID_ANY, _("&Remove"))
        menu.AppendItem(item)
        self.Bind(wx.EVT_MENU, self.OnRemoveCmd, item)

        if self.history_manager.filetype == "json":
            item = wx.MenuItem(menu, wx.ID_ANY, _("&Show info"))
            menu.AppendItem(item)
            self.Bind(wx.EVT_MENU, self.OnShowInfo, item)

        self.PopupMenu(menu)
        menu.Destroy()

    def Filter(self, text):
        """Filter history
        :param str text: text string
        """
        if text:
            self._model = self._orig_model.Filtered(key=["command"], value=text)
        else:
            self._model = self._orig_model
        self.RefreshItems()

    def UpdateHistoryModelFromScratch(self):
        """Reload tree history model based on the current history log from scratch."""
        self._model.RemoveNode(self._model.root)
        self._initHistoryModel()

    def AppendNodeToHistoryModel(self, entry):
        """Append node to the model and refresh the tree.

        :param entry dict: entry with 'command' and 'command_info' keys
        """
        self._model.AppendNode(
            parent=self._model.root,
            label=entry["command"],
            data=entry,
        )
        self._refreshTree()

    def UpdateNodeInHistoryModel(self, entry):
        """Update last node in the model and refresh the tree.

        :param entry dict: entry with 'command' and 'command_info' keys
        """
        # Remove last node
        index = [self._model.GetLeafCount(self._model.root) - 1]
        tree_node = self._model.GetNodeByIndex(index)
        self._model.RemoveNode(tree_node)

        # Add new node to the model
        self.AppendNodeToHistoryModel(entry)

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
                self.runIgnoredCmdPattern.emit(cmd=split(command))
                return
            if re.compile(r"^r[3]?\.mapcalc").search(command):
                command = parse_mapcalc_cmd(command)
            command = replace_module_cmd_special_flags(command)
            lst = split(command)
            try:
                GUI(parent=self, giface=self._giface).ParseCommand(lst)
            except GException as e:
                GError(
                    parent=self,
                    message=str(e),
                    caption=_("Cannot be parsed into command"),
                    showTraceback=False,
                )

    def RemoveEntryFromHistory(self, del_line_number):
        """Remove entry from command history log.

        :param int del_line_number: index of the entry which should be removed
        """
        try:
            self.history_manager.remove_entry_from_history(del_line_number)
        except OSError as e:
            GError(str(e))

    def GetCommandInfo(self, index):
        """Get command info for the given command index.

        :param int index: index of the command
        """
        command_info = {}
        try:
            command_info = self.history_manager.get_content()[index]["command_info"]
        except OSError as e:
            GError(str(e))
        return command_info

    def OnRemoveCmd(self, event):
        """Remove cmd from the history file"""
        tree_node = self._getSelectedNode()
        cmd = tree_node.data["command"]
        question = _("Do you really want to remove <{}> command?").format(cmd)
        if self._confirmDialog(question, title=_("Remove command")) == wx.ID_YES:
            self.showNotification.emit(message=_("Removing <{}>").format(cmd))
            tree_index = self._model.GetIndexOfNode(tree_node)[0]
            self.RemoveEntryFromHistory(tree_index)
            self._giface.entryFromHistoryRemoved.emit(index=tree_index)
            self._model.RemoveNode(tree_node)
            self._refreshTree()
            self.showNotification.emit(message=_("<{}> removed").format(cmd))

    def OnShowInfo(self, event):
        """Show info about command in the small dialog"""
        tree_node = self._getSelectedNode()
        tree_index = self._model.GetIndexOfNode(tree_node)[0]
        command_info = self.GetCommandInfo(tree_index)
        dialog = HistoryInfoDialog(self, command_info)
        dialog.ShowModal()

    def OnItemSelected(self, node):
        """Item selected"""
        command = node.data["command"]
        self.showNotification.emit(message=command)

    def OnRightClick(self, node):
        """Display popup menu"""
        self._popupMenuLayer()
