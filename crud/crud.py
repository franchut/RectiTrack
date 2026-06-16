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

@app.route('/')
@require_login
def index():
    return redirect(url_for('panel_iot'))

@app.route('/iot', methods=['GET', 'POST'])
@require_login
def panel_iot():
    cur = mysql.connection.cursor()
    
    if request.method == 'POST':
        accion = request.form.get('action')
        
        if accion == 'vincular':
            id_hardware = request.form.get('id_hardware').strip()
            nombre_nodo = request.form.get('nombre_nodo').strip()
            
            if not id_hardware or not nombre_nodo:
                flash('Error: Campos obligatorios incompletos.')
                return redirect(url_for('panel_iot'))
            
            try:
                cur.execute(
                    "INSERT INTO dispositivos (id_hardware, nombre) VALUES (%s, %s)",
                    (id_hardware, nombre_nodo)
                )
                mysql.connection.commit()
                flash(f'Dispositivo {nombre_nodo} guardado con éxito en la base de datos.')
            except Exception as e:
                logging.error(f"Error al insertar hardware: {e}")
                flash('Error: El ID ingresado ya existe en la base de datos.')
            finally:
                cur.close()
            return redirect(url_for('panel_iot'))
            
        id_nodo = request.form.get('nodo')
        if not id_nodo:
            flash('Error: No se seleccionó ningún dispositivo.')
            return redirect(url_for('panel_iot'))
            
        try:
            if accion == 'blink':
                topic = f"{id_nodo}/destello"
                publish.single(topic, payload="1", hostname=MQTT_BROKER, port=MQTT_PORT, auth=MQTT_AUTH, tls=MQTT_TLS, qos=1)
                flash(f"Destello enviado al ID: {id_nodo}")
            elif accion == 'setpoint':
                valor = request.form.get('valor_setpoint').replace(',', '.')
                topic = f"{id_nodo}/setpoint"
                payload = str(float(valor))
                publish.single(topic, payload=payload, hostname=MQTT_BROKER, port=MQTT_PORT, auth=MQTT_AUTH, tls=MQTT_TLS, qos=1)
                flash(f"Setpoint {payload}°C enviado al ID: {id_nodo}")
        except Exception as e:
            logging.error(f"Falla MQTT: {e}")
            flash("Error de comunicación con el broker seguro.")
            
        cur.close()
        return redirect(url_for('panel_iot'))
        
    try:
        cur.execute("SELECT id_hardware, nombre FROM dispositivos")
        nodos_db = cur.fetchall()
    except Exception as e:
        logging.error(f"Error DB: {e}")
        nodos_db = []
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

@app.route('/iot/borrar/<id>')
@require_login
def borrar_nodo(id):
    cur = mysql.connection.cursor()
    try:
        cur.execute("DELETE FROM dispositivos WHERE id_hardware = %s", (id,))
        mysql.connection.commit()
        flash(f'Dispositivo {id} desvinculado de la base de datos.')
    except Exception as e:
        logging.error(f"Error al eliminar hardware: {e}")
        flash('Error: No se pudo eliminar el dispositivo.')
    finally:
        cur.close()
    return redirect(url_for('panel_iot'))

@app.route('/iot/editar/<id>', methods=['GET', 'POST'])
@require_login
def editar_nodo(id):
    cur = mysql.connection.cursor()
    
    if request.method == 'POST':
        nuevo_nombre = request.form.get('nombre_nodo').strip()
        if not nuevo_nombre:
            flash('Error: El nombre no puede estar vacío.')
            return redirect(url_for('panel_iot'))
            
        try:
            cur.execute("UPDATE dispositivos SET nombre = %s WHERE id_hardware = %s", (nuevo_nombre, id))
            mysql.connection.commit()
            flash(f'Nombre del dispositivo {id} actualizado a "{nuevo_nombre}".')
        except Exception as e:
            logging.error(f"Error al actualizar hardware: {e}")
            flash('Error: No se pudieron guardar los cambios.')
        finally:
            cur.close()
        return redirect(url_for('panel_iot'))
        
    cur.execute("SELECT id_hardware, nombre FROM dispositivos WHERE id_hardware = %s", (id,))
    nodo = cur.fetchone()
    cur.close()
    
    if not nodo:
        flash('Error: El dispositivo solicitado no existe.')
        return redirect(url_for('panel_iot'))
        
    return render_template('editar-nodo.html', nodo=nodo)