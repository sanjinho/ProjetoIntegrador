from flask import Flask, render_template, request, redirect, url_for
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from flask_mail import Mail, Message
from itsdangerous import URLSafeTimedSerializer as Serializer, BadSignature
import os
app = Flask(__name__)

if os.environ.get('FLASK_ENV') == 'production':
    app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL')  # Usando o PostgreSQL
else:
    app.config['SECRET_KEY'] = 'secret_key'
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'  # Usando SQLite localmente


# Configuração de e-mail
app.config['MAIL_SERVER'] = 'smtp.gmail.com'  # Use seu servidor de e-mail
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'your_email@gmail.com'  # Substitua pelo seu e-mail
app.config['MAIL_PASSWORD'] = 'your_email_password'  # Substitua pela sua senha de e-mail

db = SQLAlchemy(app)
mail = Mail(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# Defina o user_loader aqui
@login_manager.user_loader
def load_user(user_id):
    return Usuario.query.get(int(user_id))

#****************************************************************************************
class Usuario(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    senha = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), nullable=False)
    despesas = db.relationship('Despesa', backref='usuario', lazy=True)
    rendas = db.relationship('Renda', backref='usuario', lazy=True)
    
class Despesa(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), db.ForeignKey('usuario.username'), nullable=False)
    descricao = db.Column(db.String(100), nullable=False)
    valor = db.Column(db.Float, nullable=False)
    data_hora = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    
class Renda(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), db.ForeignKey('usuario.username'), nullable=False)
    descricao = db.Column(db.String(100), nullable=False)
    valor = db.Column(db.Float, nullable=False)
    data_hora = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

with app.app_context():
    db.create_all()

# Função para gerar o token de redefinição de senha
def generate_reset_token(email):
    serializer = Serializer(app.config['SECRET_KEY'])
    return serializer.dumps(email, salt='password-reset')

# Função para verificar o token
def verify_reset_token(token):
    serializer = Serializer(app.config['SECRET_KEY'])
    try:
        email = serializer.loads(token, salt='password-reset', max_age=3600)  # O token expira em 1 hora
    except BadSignature:
        return None
    return email

#***********************************************************************************************
#PAGINA INICIAL DO SITE
@app.route('/')
@app.route('/index')
def index():
    return render_template('index.html')

#PAGINA DE LOGIN
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        senha = request.form['senha']
        usuario = Usuario.query.filter_by(username=username).first()
        if usuario and usuario.senha == senha:
            login_user(usuario)
            return redirect(url_for('principal'))
        else:
            return render_template('login.html', mensagem='Usuário ou senha incorretos!')

    return render_template('login.html')


@app.template_filter()
def formatar_valor(valor):
    return ("R$ " + str(valor).replace(".", ",")+"0")

@app.route('/principal', methods=['GET', 'POST'])
@login_required
def principal():
    if request.method == 'POST':
        tipo = request.form['tipo']
        descricao = request.form['descricao']
        valor = request.form['valor']

        if tipo == 'despesa':
            despesa = Despesa(username=current_user.username, descricao=descricao, valor=valor, data_hora=datetime.now())
            db.session.add(despesa)
            db.session.commit()
        elif tipo == 'renda':
            renda = Renda(username=current_user.username, descricao=descricao, valor=valor, data_hora=datetime.now())
            db.session.add(renda)
            db.session.commit()

        return redirect(url_for('principal'))

    rendas = Renda.query.filter_by(username=current_user.username).all()
    despesas = Despesa.query.filter_by(username=current_user.username).all()

    total_rendas = sum(renda.valor for renda in rendas)
    total_despesas = sum(despesa.valor for despesa in despesas)
    total= total_rendas - total_despesas

    return render_template('principal.html', rendas=rendas, despesas=despesas, total_rendas=total_rendas, total_despesas=total_despesas, total=total)
    

#PAGINA PARA FAZER O CADASTRO
@app.route('/cadastro', methods=['GET', 'POST'])
def cadastro():
    if request.method == 'POST':
        username = request.form['username']
        senha = request.form['senha']
        email = request.form['email']
        if Usuario.query.filter_by(username=username).first():
            mensagem='Usuário já existe!'
            return render_template('cadastro.html', mensagem=mensagem)
        usuario = Usuario(username=username, senha=senha, email=email)
        db.session.add(usuario)
        db.session.commit()
        
        return redirect(url_for('login'))
    
    return render_template('cadastro.html')

#LOGOUT
@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

#DESPESAS
@app.route('/despesas')
@login_required
def despesas():
    despesas = Despesa.query.filter_by(username=current_user.username).all()
    total_despesas = sum(despesa.valor for despesa in despesas)
    return render_template('despesas.html', despesas=despesas,total_despesas=total_despesas)

#RENDAS
@app.route('/rendas')
@login_required
def rendas():
    rendas = Renda.query.filter_by(username=current_user.username).all()
    total_rendas = sum(renda.valor for renda in rendas)
    return render_template('rendas.html', rendas=rendas,total_rendas=total_rendas)

# Rota para recuperação de senha
@app.route('/recover', methods=['GET', 'POST'])
def recover():
    if request.method == 'POST':
        email = request.form['email']
        usuario = Usuario.query.filter_by(email=email).first()

        if usuario:
            # Gerar o token de redefinição
            token = generate_reset_token(email)
            reset_link = url_for('reset_password', token=token, _external=True)

            # Enviar e-mail com o link de redefinição
            msg = Message("Recuperação de Senha", sender='your_email@gmail.com', recipients=[email])
            msg.body = f'Clique no link abaixo para redefinir sua senha:\n{reset_link}'
            mail.send(msg)

            return render_template('recover.html', mensagem='Um e-mail com o link de recuperação foi enviado.')

        return render_template('recover.html', mensagem='E-mail não encontrado.')

    return render_template('recover.html')

# Rota para redefinir a senha
@app.route('/reset_password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    email = verify_reset_token(token)
    if not email:
        return render_template('reset_password.html', mensagem='O link de recuperação é inválido ou expirou.')

    usuario = Usuario.query.filter_by(email=email).first()

    if request.method == 'POST':
        nova_senha = request.form['senha']
        usuario.senha = nova_senha
        db.session.commit()
        return redirect(url_for('login'))

    return render_template('reset_password.html', token=token)