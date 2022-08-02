from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel
from kucher.version import __version__


class AboutWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.setGeometry(300, 300, 350, 50)
        self.setWindowTitle('About')
        layout = QVBoxLayout()
        version_string = "Version " + ".".join(map(str, __version__))
        self.label = QLabel(version_string)
        layout.addWidget(self.label)
        self.setLayout(layout)
        self.show()
