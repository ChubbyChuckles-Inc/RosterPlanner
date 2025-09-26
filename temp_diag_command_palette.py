import traceback, sys
import sys as _s, os as _o; _s.path.insert(0, 'src')
try:
    from gui.views.command_palette import CommandPaletteDialog
    print('Imported OK:', CommandPaletteDialog)
except Exception as e:
    print('Import failed:', e)
    traceback.print_exc()
    sys.exit(1)
from PyQt6.QtWidgets import QApplication
app = QApplication(sys.argv)
try:
    dlg = CommandPaletteDialog()
    print('Instantiated OK')
    dlg._refresh_list('test')
    print('Refreshed OK')
except Exception as e:
    print('Runtime failure:', e)
    traceback.print_exc()
    sys.exit(2)
print('Done')
