from PyQt6.QtWidgets import QDialog, QVBoxLayout, QGridLayout, QLabel, QLineEdit, QPushButton
from PyQt6.QtCore import Qt

class LoginDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("로그인")
        self.setModal(True)
        self.setFixedSize(300, 180)

        layout = QVBoxLayout(self)
        
        form_layout = QGridLayout()
        form_layout.addWidget(QLabel("이메일:"), 0, 0)
        self.email_input = QLineEdit()
        # self.email_input.setText("chunjaedm@gmail.com")
        form_layout.addWidget(self.email_input, 0, 1)

        form_layout.addWidget(QLabel("비밀번호:"), 1, 0)
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        form_layout.addWidget(self.password_input, 1, 1)
        
        layout.addLayout(form_layout)

        self.login_button = QPushButton("접속")
        self.login_button.clicked.connect(self.accept)
        layout.addWidget(self.login_button, alignment=Qt.AlignmentFlag.AlignCenter)
        
        self.password_input.returnPressed.connect(self.accept)
        self.password_input.setFocus()

    def get_credentials(self):
        return self.email_input.text(), self.password_input.text()