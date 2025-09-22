import os 
os.environ.setdefault('QT_QPA_PLATFORM','offscreen') 
from PyQt6.QtWidgets import QApplication, QWidget 
import sys 
app=QApplication(sys.argv[:1]) 
QWidget();print('Widget OK') 
