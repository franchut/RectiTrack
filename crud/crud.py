import os
import uuid
import logging
from datetime import datetime
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_mysqldb import MySQL
from werkzeug.middleware.proxy_fix import ProxyFix
from werkzeug.security import check_password_hash, generate_password_hash

# Configuración del Logger
logging.basicConfig(format='%(asctime)s - RECTITRACK - %(levelname)s - %(message)s', level=logging.INFO)

app = Flask(__name__)

# Middleware para Proxy Inverso (Nginx/SWAG)
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

# Parámetros estáticos de Base de Datos y Sesión
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "rectitrack_secure_key_2026")
app.config["MYSQL_USER"] = "root"
app.config["MYSQL_PASSWORD"] = os.environ.get("MARIADB_ROOT_PASSWORD", "IoTJoa")
app.config["MYSQL_DB"] = "rectitrack_db"
app.config["MYSQL_HOST"] = "mariadb"
app.config['PERMANENT_SESSION_LIFETIME'] = 1800

mysql = MySQL(app)

# Decorador de Autorización
def require_gerente(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get("role") != "gerente":
            flash("Acceso denegado. Se requieren credenciales de Gerente.")
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# ==========================================
# RUTAS DE AUTENTICACIÓN
# ==========================================
@app.route('/')
def index():
    if session.get("role") == "gerente":
        return redirect(url_for('panel_gerente'))
    return redirect(url_for('login'))

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        usuario = request.form.get("usuario")
        password = request.form.get("password")
        rol = request.form.get("rol")

        if not usuario or not password:
            flash("Todos los campos son obligatorios.")
            return redirect(url_for('login'))

        cur = mysql.connection.cursor()
        
        if rol == "gerente":
            cur.execute("SELECT hash_password FROM Usuarios_Gerencia WHERE usuario = %s", (usuario,))
            row = cur.fetchone()
            cur.close()
            
            if row and check_password_hash(row[0], password):
                session.permanent = True
                session["user_id"] = usuario
                session["role"] = "gerente"
                logging.info(f"Autenticación exitosa - Gerente: {usuario}")
                return redirect(url_for('panel_gerente'))
            else:
                flash("Credenciales de Gerente incorrectas.")
        
        elif rol == "operario":
            cur.execute("SELECT id_operario, password, nombre, apellido FROM Operario WHERE login = %s", (usuario,))
            row = cur.fetchone()
            cur.close()
            
            if row and check_password_hash(row[1], password):
                session.permanent = True
                session["user_id"] = usuario
                session["role"] = "operario"
                session["operario_id"] = row[0]
                logging.info(f"Autenticación exitosa - Operario: {row[2]} {row[3]}")
                return "Interfaz de Operario (En desarrollo)"
            else:
                flash("Credenciales de Operario incorrectas.")
        else:
            cur.close()
            flash("Rol no válido.")

    return render_template('login.html')

@app.route("/registrar", methods=["GET", "POST"])
def registrar():
    if request.method == "POST":
        usuario = request.form.get("usuario")
        password = request.form.get("password")
        rol = request.form.get("rol")

        if not usuario or not password:
            flash("Todos los campos son obligatorios.")
            return redirect(url_for('registrar'))

        passhash = generate_password_hash(password, method='scrypt', salt_length=16)
        cur = mysql.connection.cursor()

        try:
            if rol == "gerente":
                cur.execute("INSERT INTO Usuarios_Gerencia (usuario, hash_password) VALUES (%s, %s)", (usuario, passhash))
            elif rol == "operario":
                cur.execute("INSERT INTO Operario (nombre, apellido, login, password) VALUES ('Nuevo', 'Operario', %s, %s)", (usuario, passhash))
            
            mysql.connection.commit()
            flash("Usuario registrado exitosamente.")
            return redirect(url_for('login'))
        except Exception as e:
            logging.error(f"Falla de persistencia en registro: {e}")
            flash("El nombre de usuario ya existe en la base de datos.")
        finally:
            cur.close()

    return render_template('registrar.html')

@app.route("/logout")
def logout():
    logging.info(f"Sesión cerrada - Usuario: {session.get('user_id')}")
    session.clear()
    return redirect(url_for('login'))

# ==========================================
# RUTAS DE MÓDULOS GERENCIALES
# ==========================================
@app.route('/panel-gerente')
@require_gerente
def panel_gerente():
    return render_template('panel_gerente.html')

@app.route('/panel-gerente/asignar', methods=['GET', 'POST'])
@require_gerente
def asignar_tareas():
    cur = mysql.connection.cursor()
    
    if request.method == 'POST':
        id_orden = request.form.get('id_orden')
        id_operario = request.form.get('id_operario')
        id_area = request.form.get('id_area')
        descripcion = request.form.get('descripcion')

        try:
            cur.execute("""
                INSERT INTO Tarea (descripcion_trabajo, estado_tarea, fecha_actualizacion, id_orden, id_operario, id_area)
                VALUES (%s, 'PENDIENTE', %s, %s, %s, %s)
            """, (descripcion, datetime.now(), id_orden, id_operario, id_area))
            mysql.connection.commit()
            flash('Tarea asignada y registrada con Éxito.')
        except Exception as e:
            logging.error(f"Falla DML al insertar Tarea: {e}")
            flash('Error técnico al registrar la asignación.')
        finally:
            cur.close()
        return redirect(url_for('asignar_tareas'))

    cur.execute("SELECT id_area, nombre_area FROM Area")
    areas = cur.fetchall()
    
    cur.execute("SELECT id_operario, nombre, apellido FROM Operario")
    operarios = cur.fetchall()

    cur.execute("""
        SELECT ot.id_orden, m.codigo_qr, m.marca, m.modelo 
        FROM OrdenTrabajo ot 
        JOIN Motor m ON ot.id_motor = m.id_motor 
        WHERE ot.id_orden NOT IN (
            SELECT id_orden FROM Tarea WHERE estado_tarea IN ('PENDIENTE', 'EN_PROCESO')
        )
    """)
    ordenes = cur.fetchall()
    cur.close()
    
    return render_template('asignar_tareas.html', areas=areas, operarios=operarios, ordenes=ordenes)


@app.route('/panel-gerente/ingreso', methods=['GET', 'POST'])
@require_gerente
def ingreso_motor():
    if request.method == 'POST':
        dni = request.form.get('dni')
        nombre_cliente = request.form.get('nombre_cliente')
        apellido_cliente = request.form.get('apellido_cliente')
        telefono = request.form.get('telefono')
        email = request.form.get('email')
        marca = request.form.get('marca')
        modelo = request.form.get('modelo')
        nro_serie_bloque = request.form.get('nro_serie_bloque')
        fecha_entrega_estimada = request.form.get('fecha_entrega_estimada')
        origen_repuestos = request.form.get('origen_repuestos')

        # Safe float parsing
        monto_total = float(request.form.get('monto_total') or 0.0)
        anticipo = float(request.form.get('anticipo') or 0.0)
        saldo = monto_total - anticipo

        # Programmatically generate unique QR code
        generated_qr = f"QR-{int(datetime.now().timestamp())}"

        cur = mysql.connection.cursor()
        try:
            # 1. Insert Client (if not exists)
            cur.execute("""
                INSERT IGNORE INTO Cliente (dni, nombre, apellido, telefono, email)
                VALUES (%s, %s, %s, %s, %s)
            """, (dni, nombre_cliente, apellido_cliente, telefono, email))
            
            # 2. Insert Motor
            cur.execute("""
                INSERT INTO Motor (codigo_qr, marca, modelo, nro_serie_bloque, dni_cliente)
                VALUES (%s, %s, %s, %s, %s)
            """, (generated_qr, marca, modelo, nro_serie_bloque, dni))
            id_motor = cur.lastrowid
            
            # 3. Insert Work Order (OrdenTrabajo)
            cur.execute("""
                INSERT INTO OrdenTrabajo (id_motor, fecha_ingreso, fecha_entrega_estimada, monto_total, saldo_pendiente, estado_general, origen_repuestos)
                VALUES (%s, NOW(), %s, %s, %s, 'EN_PROCESO', %s)
            """, (id_motor, fecha_entrega_estimada, monto_total, saldo, origen_repuestos))
            
            mysql.connection.commit()
            flash('Motor y Orden de Trabajo registrados exitosamente.')
            return redirect(url_for('panel_gerente'))
        except Exception as e:
            mysql.connection.rollback()
            logging.error(f"Falla en registro de motor/OT: {e}")
            flash('Error al intentar registrar el motor o la orden de trabajo. Verifique los datos.')
            return redirect(url_for('ingreso_motor'))
        finally:
            cur.close()

    return render_template('ingreso_motor.html')

@app.route('/panel-gerente/stock')
@require_gerente
def gestionar_stock():
    return render_template('gestionar_stock.html')

@app.route('/panel-gerente/pagos')
@require_gerente
def gestionar_pagos():
    cur = mysql.connection.cursor()
    cur.execute("""
        SELECT ot.id_orden, m.codigo_qr, c.nombre, c.apellido, ot.monto_total, 
               (ot.monto_total - ot.saldo_pendiente) AS anticipo, ot.saldo_pendiente
        FROM OrdenTrabajo ot 
        JOIN Motor m ON ot.id_motor = m.id_motor
        JOIN Cliente c ON m.dni_cliente = c.dni
    """)
    pagos = cur.fetchall()
    cur.close()
    return render_template('gestionar_pagos.html', pagos=pagos)

@app.route('/panel-gerente/progreso')
@require_gerente
def progreso_motores():
    cur = mysql.connection.cursor()
    cur.execute("""
        SELECT m.codigo_qr, o.nombre, o.apellido, 
               CASE 
                   WHEN ot.estado_general = 'HECHO' THEN 100 
                   WHEN ot.estado_general = 'EN_PROCESO' THEN 50 
                   ELSE 10 
               END AS porcentaje,
               ot.estado_general
        FROM OrdenTrabajo ot
        JOIN Motor m ON ot.id_motor = m.id_motor
        LEFT JOIN Tarea t ON ot.id_orden = t.id_orden
        LEFT JOIN Operario o ON t.id_operario = o.id_operario
        GROUP BY ot.id_orden
    """)
    progresos = cur.fetchall()
    cur.close()
    return render_template('progreso_motores.html', progresos=progresos)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)