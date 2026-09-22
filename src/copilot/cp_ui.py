"""Small UNO UI helpers shared by the panel, review and settings dialogs."""

import uno
import unohelper

from com.sun.star.awt import XActionListener
from com.sun.star.awt import XCallback
from com.sun.star.awt import XFocusListener
from com.sun.star.awt import XItemListener
from com.sun.star.datatransfer import DataFlavor
from com.sun.star.datatransfer import XTransferable


def log(message):
    import os
    import time

    try:
        path = os.path.join(
            os.path.expanduser("~"), ".config", "hailper", "hailper.log"
        )
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "a", encoding="utf-8") as handle:
            handle.write("%s %s\n" % (time.strftime("%Y-%m-%d %H:%M:%S"), message))
    except Exception:
        pass


def smgr(ctx):
    return ctx.getServiceManager()


def create_model(dialog_model, service, name, **props):
    """Create a child control model through the dialog model's factory.

    Creating the model this way aggregates com.sun.star.awt.UnoControlDialogElement,
    which provides the geometry properties (PositionX, Width, ...).
    """
    model = dialog_model.createInstance(service + "Model")
    model.setPropertyValue("Name", name)
    if "FontHeight" not in props:
        try:
            model.setPropertyValue("FontHeight", 8.0)
        except Exception:
            pass
    for key, value in props.items():
        model.setPropertyValue(key, value)
    return model


def set_string_list(control_model, values):
    uno.invoke(
        control_model, "setPropertyValue",
        ("StringItemList", uno.Any("[]string", tuple(values))),
    )


def payload(**values):
    from com.sun.star.beans import NamedValue

    items = []
    for name, value in values.items():
        item = NamedValue()
        item.Name = name
        item.Value = value
        items.append(item)
    return tuple(items)


def read_payload(data):
    result = {}
    try:
        for item in data or ():
            result[item.Name] = item.Value
    except Exception:
        pass
    return result


def set_text(dialog, name, value):
    control = dialog.getControl(name)
    if control is not None:
        control.setText(value)


def get_text(dialog, name):
    control = dialog.getControl(name)
    if control is None:
        return ""
    return control.getText()


def show_message_box(ctx, frame, title, message, kind="infobox"):
    try:
        toolkit = smgr(ctx).createInstanceWithContext("com.sun.star.awt.Toolkit", ctx)
        parent = None
        try:
            parent = frame.getContainerWindow()
        except Exception:
            parent = None
        rectangle = uno.createUnoStruct("com.sun.star.awt.Rectangle")
        rectangle.X = 0
        rectangle.Y = 0
        rectangle.Width = 300
        rectangle.Height = 200
        box = toolkit.createMessageBox(
            parent, rectangle, kind, "OK", title, message
        )
        box.execute()
    except Exception:
        pass


def confirm(ctx, frame, title, message):
    """Show a Yes/No box; returns True for Yes (and when unavailable)."""
    try:
        toolkit = smgr(ctx).createInstanceWithContext("com.sun.star.awt.Toolkit", ctx)
        parent = None
        try:
            parent = frame.getContainerWindow()
        except Exception:
            parent = None
        rectangle = uno.createUnoStruct("com.sun.star.awt.Rectangle")
        rectangle.X = 0
        rectangle.Y = 0
        rectangle.Width = 320
        rectangle.Height = 160
        box = toolkit.createMessageBox(
            parent, rectangle, "querybox", "yes_no", title, message
        )
        return box.execute() in (1, 2)  # OK or YES
    except Exception:
        return True


class ActionListener(unohelper.Base, XActionListener):
    def __init__(self, callback):
        self._callback = callback

    def actionPerformed(self, event):
        self._callback(event)

    def disposing(self, event):
        pass


class Callback(unohelper.Base, XCallback):
    def __init__(self, callback):
        self._callback = callback

    def notify(self, data):
        self._callback(data)


class FocusListener(unohelper.Base, XFocusListener):
    def __init__(self, gained=None, lost=None):
        self._gained = gained
        self._lost = lost

    def focusGained(self, event):
        if callable(self._gained):
            self._gained()

    def focusLost(self, event):
        if callable(self._lost):
            self._lost()

    def disposing(self, event):
        pass


class ItemListener(unohelper.Base, XItemListener):
    def __init__(self, callback):
        self._callback = callback

    def itemStateChanged(self, event):
        self._callback(event)

    def disposing(self, event):
        pass


class TextTransferable(unohelper.Base, XTransferable):
    def __init__(self, text):
        self._text = text
        flavor = DataFlavor()
        flavor.MimeType = "text/plain;charset=utf-16"
        flavor.HumanPresentableName = "Unicode text"
        flavor.DataType = uno.getTypeByName("string")
        self._flavor = flavor

    def getTransferData(self, flavor):
        return self._text

    def getTransferDataFlavors(self):
        return (self._flavor,)

    def isDataFlavorSupported(self, flavor):
        return flavor.MimeType == self._flavor.MimeType


def copy_to_clipboard(ctx, text):
    try:
        clipboard = smgr(ctx).createInstanceWithContext(
            "com.sun.star.datatransfer.clipboard.SystemClipboard", ctx
        )
        clipboard.setContents(TextTransferable(text), None)
        return True
    except Exception:
        return False
