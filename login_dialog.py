from PyQt6.QtWidgets import QDialog, QVBoxLayout, QGridLayout, QLabel, QLineEdit, QPushButton, QCheckBox
from PyQt6.QtCore import Qt, QSettings

class LoginDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("로그인")
        self.setModal(True)
        self.setFixedSize(300, 200)

        layout = QVBoxLayout(self)
        
        form_layout = QGridLayout()
        form_layout.addWidget(QLabel("이메일:"), 0, 0)
        self.email_input = QLineEdit()
        form_layout.addWidget(self.email_input, 0, 1)

        form_layout.addWidget(QLabel("비밀번호:"), 1, 0)
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        form_layout.addWidget(self.password_input, 1, 1)
        
        layout.addLayout(form_layout)

        self.save_email_check = QCheckBox("이메일 기억하기")
        layout.addWidget(self.save_email_check)

        self.login_button = QPushButton("접속")
        self.login_button.clicked.connect(self.accept)
        layout.addWidget(self.login_button, alignment=Qt.AlignmentFlag.AlignCenter)
        
        self.password_input.returnPressed.connect(self.accept)
        
        self.settings = QSettings("PortfolioManager", "Login")
        saved_email = self.settings.value("email", "")
        if saved_email:
            self.email_input.setText(saved_email)
            self.save_email_check.setChecked(True)
            self.password_input.setFocus()
        else:
            self.email_input.setFocus()

    def accept(self):
        if self.save_email_check.isChecked():
            self.settings.setValue("email", self.email_input.text())
        else:
            self.settings.remove("email")
        super().accept()

    def get_credentials(self):
        return self.email_input.text(), self.password_input.text()