# app/forms.py
from __future__ import annotations
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, TextAreaField
from wtforms.validators import DataRequired, Length

class LoginForm(FlaskForm):
    username = StringField("Usuário", validators=[DataRequired(), Length(min=3, max=150)])
    password = PasswordField("Senha", validators=[DataRequired(), Length(min=6, max=128)])
    submit = SubmitField("Entrar")

class RegisterForm(FlaskForm):
    username = StringField("Usuário", validators=[DataRequired(), Length(min=3, max=150)])
    email = StringField("Email", validators=[DataRequired(), Length(min=5, max=150)])
    password = PasswordField("Senha", validators=[DataRequired(), Length(min=8, max=128)])
    submit = SubmitField("Criar conta")

class KeywordsForm(FlaskForm):
    keywords = StringField("Palavras-chave (separe por vírgula)")
    submit = SubmitField("Salvar")
