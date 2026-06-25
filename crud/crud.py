from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_mysqldb import MySQL
import os
import logging
from functools import wraps
from werkzeug.middleware.proxy_fix import ProxyFix
from datetime import datetime

logging.basicConfig(format='%(asctime)s - RECTITRACK - %(levelname)s - %(message)s', level=logging.INFO)

app = Flask(__name__)
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

app.secret_key = os.environ.get("FLASK_SECRET_KEY", "rectitrack_secure_key_2026")
app.config["MYSQL_USER"] = os.environ.get("MYSQL_USER", "root")
app.config["MYSQL_PASSWORD"] = os.environ.get("MYSQL_PASSWORD", "root")
app.config["MYSQL_DB"] = "rectitrack_db"
app.config["MYSQL_HOST"] = os.environ.get("MYSQL_HOST", "mariadb")
app.config['PERMANENT_SESSION_LIFETIME'] = 180

mysql = MySQL(app)

def require_gerente(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        session["user_id"] = "Gerente_Principal"
        session["role"] = "gerente"
        return f(*args, **kwargs)
    return decorated_function

@app.route('/')
@require_gerente
def index():
    return redirect(url_for('panel_gerente'))

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
            flash('Tarea asignada con Éxito.')
        except Exception as e:
            logging.error(f"Falla DML: {e}")
            flash('Error técnico al intentar persistir la tarea.', 'error')
        finally:
            cur.close()
        return redirect(url_for('asignar_tareas'))

    cur.execute("SELECT id_area, nombre_area FROM Area")
    areas = cur.fetchall()
    cur.execute("SELECT id_operario, nombre, apellido FROM Operario")
    operarios = cur.fetchall()
    cur.execute("""
        SELECT ot.id_orden, m.codigo_qr, m.marca, m.modelo 
        FROM OrdenTrabajo ot JOIN Motor m ON ot.id_motor = m.id_motor
    """)
    ordenes = cur.fetchall()
    cur.close()
    return render_template('asignar_tareas.html', areas=areas, operarios=operarios, ordenes=ordenes)

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
               CASE WHEN ot.estado_general = 'HECHO' THEN 100 WHEN ot.estado_general = 'EN_PROCESO' THEN 50 ELSE 10 END,
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