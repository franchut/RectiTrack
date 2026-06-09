from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_mysqldb import MySQL
import os
import logging
import ssl
from functools import wraps
from werkzeug.middleware.proxy_fix import ProxyFix
from werkzeug.security import check_password_hash, generate_password_hash
import paho.mqtt.publish as publish

logging.basicConfig(format='%(asctime)s - CRUD - %(levelname)s - %(message)s', level=logging.INFO)

app = Flask(__name__)

app.wsgi_app = ProxyFix(
    app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1
)

app.secret_key = os.environ["FLASK_SECRET_KEY"]
app.config["MYSQL_USER"] = os.environ["MYSQL_USER"]
app.config["MYSQL_PASSWORD"] = os.environ["MYSQL_PASSWORD"]
app.config["MYSQL_DB"] = os.environ["MYSQL_DB"]
app.config["MYSQL_HOST"] = os.environ["MYSQL_HOST"]
app.config['PERMANENT_SESSION_LIFETIME'] = 180
mysql = MySQL(app)

MQTT_BROKER = os.environ["MQTT_BROKER"]
MQTT_PORT = int(os.environ["MQTT_PORT"])
MQTT_AUTH = {
    'username': os.environ["MQTT_USER"], 
    'password': os.environ["MQTT_PASS"]
}

MQTT_TLS = {
    'ca_certs': None,
    'cert_reqs': ssl.CERT_REQUIRED,
    'tls_version': ssl.PROTOCOL_TLS_CLIENT,
    'ciphers': None
}

def require_login(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get("user_id") is None:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/set_theme/<theme>')
@require_login
def set_theme(theme):
    if theme in ['light', 'dark']:
        session['theme'] = theme
    return redirect(request.referrer or url_for('panel_iot'))

# La ruta raíz ahora redirige o procesa directamente el panel IoT
@app.route('/')
@require_login
def index():
    return redirect(url_for('panel_iot'))

@app.route('/iot', methods=['GET', 'POST'])
@require_login
def panel_iot():
    cur = mysql.connection.cursor()
    
    if request.method == 'POST':
        id_nodo = request.form.get('nodo')
        accion = request.form.get('action')
        
        if not id_nodo:
            flash('Error: No se especificó un nodo destinatario.')
            return redirect(url_for('panel_iot'))
            
        try:
            if accion == 'blink':
                topic = f"{id_nodo}/destello"
                payload = "1"
                publish.single(
                    topic, payload=payload, hostname=MQTT_BROKER, 
                    port=MQTT_PORT, auth=MQTT_AUTH, tls=MQTT_TLS, qos=1
                )
                logging.info(f"MQTTS [OK] -> Publicado en {topic}")
                flash(f"Comando Destello enviado con éxito al nodo {id_nodo}")
                
            elif accion == 'setpoint':
                valor = request.form.get('valor_setpoint')
                valor_normalizado = valor.replace(',', '.')
                topic = f"{id_nodo}/setpoint"
                payload = str(float(valor_normalizado))
                
                publish.single(
                    topic, payload=payload, hostname=MQTT_BROKER, 
                    port=MQTT_PORT, auth=MQTT_AUTH, tls=MQTT_TLS, qos=1
                )
                logging.info(f"MQTTS [OK] -> Publicado en {topic} | Valor: {payload}")
                flash(f"Setpoint actualizado a {payload}°C en el nodo {id_nodo}")
                
        except Exception as e:
            logging.error(f"Falla en comunicación MQTTS: {e}")
            flash(f"Error de red: No se pudo despachar el comando por MQTTS.")
            
        return redirect(url_for('panel_iot'))
        
    try:
        cur.execute("SELECT id_hardware, nombre FROM dispositivos")
        nodos_db = cur.fetchall()
    except Exception as e:
        logging.error(f"Error al leer nodos de la DB: {e}")
        nodos_db = [('e663a837cb8d2c37', 'Nodo Principal (Pico_01)')]
    finally:
        cur.close()
        
    return render_template('iot.html', nodos=nodos_db)

@app.route("/registrar", methods=["GET", "POST"])
def registrar():
    if request.method == "POST":
        if not request.form.get("usuario"):
            return "el campo usuario es obligatorio"
        elif not request.form.get("password"):
            return "el campo contraseña es obligatorio"

        passhash = generate_password_hash(request.form.get("password"), method='scrypt', salt_length=16)
        cur = mysql.connection.cursor()
        cur.execute("INSERT INTO usuarios (usuario, hash) VALUES (%s,%s)", (request.form.get("usuario"), passhash[17:]))
        if mysql.connection.affected_rows():
            flash('Se agregó un usuario')
            logging.info("se agregó un usuario")
        mysql.connection.commit()
        return redirect(url_for('panel_iot'))

    return render_template('registrar.html')

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        if not request.form.get("usuario"):
            return "el campo usuario es obligatorio"
        elif not request.form.get("password"):
            return "el campo contraseña es obligatorio"

        cur = mysql.connection.cursor()
        cur.execute("SELECT * FROM usuarios WHERE usuario LIKE %s", (request.form.get("usuario"),))
        rows = cur.fetchone()
        if rows:
            if check_password_hash('scrypt:32768:8:1$' + rows[2], request.form.get("password")):
                session.permanent = True
                session["user_id"] = request.form.get("usuario")
                logging.info("se autenticó correctamente")
                return redirect(url_for('panel_iot'))
            else:
                flash('usuario o contraseña incorrecto')
                return redirect(url_for('login'))
    return render_template('login.html')

@app.route("/logout")
@require_login
def logout():
    logging.info("el usuario {} cerró su sesión".format(session.get("user_id")))
    session.clear()
    return redirect(url_for('panel_iot'))