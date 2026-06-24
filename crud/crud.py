from flask import Flask, render_template, request, redirect, url_for, flash, session
import os
import logging
from functools import wraps
from werkzeug.middleware.proxy_fix import ProxyFix
from werkzeug.security import check_password_hash, generate_password_hash

logging.basicConfig(format='%(asctime)s - CRUD_MOCK - %(levelname)s - %(message)s', level=logging.INFO)

app = Flask(__name__)

app.wsgi_app = ProxyFix(
    app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1
)

# Clave secreta estática para desarrollo local si la variable no existe
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "desarrollo_secret_key_12345")
app.config['PERMANENT_SESSION_LIFETIME'] = 180

# === BASE DE DATOS MOCK EN MEMORIA ===
# Simula las tablas de la base de datos para renderizar la UI con datos de prueba
MOCK_DISPOSITIVOS = [
    {"id_hardware": "ESP32_01", "nombre": "Termostato Central"},
    {"id_hardware": "PICO_W_02", "nombre": "Sensor Zona Mecanizado"},
    {"id_hardware": "AVR_AT328_03", "nombre": "Alarma Taller"}
]

MOCK_USUARIOS = {
    "root": generate_password_hash("root123", method='scrypt', salt_length=16)
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
    global MOCK_DISPOSITIVOS
    
    if request.method == 'POST':
        accion = request.form.get('action')
        
        if accion == 'vincular':
            id_hardware = request.form.get('id_hardware').strip()
            nombre_nodo = request.form.get('nombre_nodo').strip()
            
            if not id_hardware or not nombre_nodo:
                flash('Error: Campos obligatorios incompletos.')
                return redirect(url_for('panel_iot'))
            
            # Simulación de inserción
            if any(d['id_hardware'] == id_hardware for d in MOCK_DISPOSITIVOS):
                flash('Error: El ID ingresado ya existe en la base de datos simulada.')
            else:
                MOCK_DISPOSITIVOS.append({"id_hardware": id_hardware, "nombre": nombre_nodo})
                flash(f'Dispositivo {nombre_nodo} guardado con éxito en la memoria.')
            return redirect(url_for('panel_iot'))
            
        id_nodo = request.form.get('nodo')
        if not id_nodo:
            flash('Error: No se seleccionó ningún dispositivo.')
            return redirect(url_for('panel_iot'))
            
        # Simulación de comandos MQTT (Muted)
        if accion == 'blink':
            logging.info(f"[MOCK MQTT] Publicando destello a {id_nodo}/destello")
            flash(f"Destello enviado al ID: {id_nodo} (Simulado)")
        elif accion == 'setpoint':
            valor = request.form.get('valor_setpoint').replace(',', '.')
            logging.info(f"[MOCK MQTT] Publicando setpoint {valor} a {id_nodo}/setpoint")
            flash(f"Setpoint {valor}°C enviado al ID: {id_nodo} (Simulado)")
            
        return redirect(url_for('panel_iot'))
        
    # Convierte la lista de diccionarios a tuplas para mantener compatibilidad con tus plantillas .html actuales (cur.fetchall())
    nodos_tuples = [(d['id_hardware'], d['nombre']) for d in MOCK_DISPOSITIVOS]
    return render_template('iot.html', nodos=nodos_tuples)

@app.route("/registrar", methods=["GET", "POST"])
def registrar():
    if request.method == "POST":
        usuario = request.form.get("usuario")
        password = request.form.get("password")
        
        if not usuario:
            return "el campo usuario es obligatorio"
        elif not password:
            return "el campo contraseña es obligatorio"

        passhash = generate_password_hash(password, method='scrypt', salt_length=16)
        MOCK_USUARIOS[usuario] = passhash
        flash('Se agregó un usuario en memoria')
        logging.info(f"Usuario registrado en memoria: {usuario}")
        return redirect(url_for('panel_iot'))

    return render_template('registrar.html')

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        usuario = request.form.get("usuario")
        password = request.form.get("password")

        if not usuario:
            return "el campo usuario es obligatorio"
        elif not password:
            return "el campo contraseña es obligatorio"

        # Validación contra la estructura en memoria
        if usuario in MOCK_USUARIOS:
            if check_password_hash(MOCK_USUARIOS[usuario], password):
                session.permanent = True
                session["user_id"] = usuario
                logging.info("Autenticación mock correcta")
                return redirect(url_for('panel_iot'))
            
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
    global MOCK_DISPOSITIVOS
    MOCK_DISPOSITIVOS = [d for d in MOCK_DISPOSITIVOS if d['id_hardware'] != id]
    flash(f'Dispositivo {id} desvinculado de la memoria.')
    return redirect(url_for('panel_iot'))

@app.route('/iot/editar/<id>', methods=['GET', 'POST'])
@require_login
def editar_nodo(id):
    global MOCK_DISPOSITIVOS
    nodo_dict = next((d for d in MOCK_DISPOSITIVOS if d['id_hardware'] == id), NULL)
    
    if not nodo_dict:
        flash('Error: El dispositivo solicitado no existe.')
        return redirect(url_for('panel_iot'))
        
    if request.method == 'POST':
        nuevo_nombre = request.form.get('nombre_nodo').strip()
        if not nuevo_nombre:
            flash('Error: El nombre no puede estar vacío.')
            return redirect(url_for('panel_iot'))
            
        nodo_dict['nombre'] = nuevo_nombre
        flash(f'Nombre del dispositivo {id} actualizado a "{nuevo_nombre}" en memoria.')
        return redirect(url_for('panel_iot'))
        
    nodo_tuple = (nodo_dict['id_hardware'], nodo_dict['nombre'])
    return render_template('editar-nodo.html', nodo=nodo_tuple)

if __name__ == '__main__':
    # Permite ejecutar de forma independiente para testing visual inmediato
    app.run(host='0.0.0.0', port=5000, debug=True)