from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_mysqldb import MySQL
import os
import logging
from functools import wraps
from werkzeug.middleware.proxy_fix import ProxyFix

logging.basicConfig(format='%(asctime)s - RECTITRACK - %(levelname)s - %(message)s', level=logging.INFO)

app = Flask(__name__)

app.wsgi_app = ProxyFix(
    app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1
)

# Configuración de variables de entorno (Deben coincidir con tu compose.yaml)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "rectitrack_secret_key_2026")
app.config["MYSQL_USER"] = os.environ.get("MYSQL_USER", "root")
app.config["MYSQL_PASSWORD"] = os.environ.get("MYSQL_PASSWORD", "root") # Cambiar por tu MARIADB_ROOT_PASSWORD
app.config["MYSQL_DB"] = "rectitrack_db"
app.config["MYSQL_HOST"] = os.environ.get("MYSQL_HOST", "mariadb")
app.config['PERMANENT_SESSION_LIFETIME'] = 180

mysql = MySQL(app)

def require_gerente(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Fuerza el login automático como Gerente para desarrollo visual inmediato
        if not session.get("user_id"):
            session["user_id"] = "Gerente_Principal"
            session["role"] = "gerente"
        return f(*args, **kwargs)
    return decorated_function

@app.route('/')
@require_gerente
def index():
    return redirect(url_for('panel_iot'))

# Panel Principal del Gerente (Mapeado a iot.html)
@app.route('/iot', methods=['GET', 'POST'])
@require_gerente
def panel_iot():
    cur = mysql.connection.cursor()
    
    if request.method == 'POST':
        accion = request.form.get('action')
        
        # RF01: Registrar Ingreso de Motor y vincular datos técnicos
        if accion == 'vincular':
            id_motor_qr = request.form.get('id_hardware').strip() # Campo QR/ID del formulario
            detalles = request.form.get('nombre_nodo').strip()     # Campo Especificaciones
            
            if not id_motor_qr or not detalles:
                flash('Error: Campos obligatorios incompletos.')
                return redirect(url_for('panel_iot'))
            
            try:
                # Para testing rápido, asumimos un cliente genérico DNI 1 o creamos uno si no existe
                cur.execute("INSERT IGNORE INTO Cliente (dni, nombre, apellido, telefono, login, password) VALUES (1, 'Cliente', 'Genérico', '123', 'cli', '123')")
                
                # Insertar en la tabla Motor
                cur.execute(
                    "INSERT INTO Motor (codigo_qr, marca, modelo, nro_serie_bloque, dni_cliente) VALUES (%s, %s, %s, %s, %s)",
                    (id_motor_qr, "Marca_Ver", "Modelo_Ver", id_motor_qr, 1)
                )
                id_motor_insertado = cur.lastrowid
                
                # Crear la Orden de Trabajo base (RF03)
                cur.execute(
                    "INSERT INTO OrdenTrabajo (fecha_ingreso, fecha_entrega_estimada, monto_total, saldo_pendiente, estado_general, origen_repuestos, id_motor) VALUES (NOW(), NOW(), 0, 0, 'CREADO', 'RECTIFICADORA', %s)",
                    (id_motor_insertado,)
                )
                
                mysql.connection.commit()
                flash(f'Motor [{id_motor_qr}] registrado exitosamente en la base de datos.')
            except Exception as e:
                logging.error(f"Error al insertar motor: {e}")
                flash('Error: El ID de motor o número de serie ya existe en el sistema.')
            finally:
                cur.close()
            return redirect(url_for('panel_iot'))
            
    # Lectura de datos reales para poblar la tabla del Gerente
    try:
        cur.execute("SELECT codigo_qr, CONCAT(marca, ' ', modelo, ' - QR: ', codigo_qr) FROM Motor")
        motores_db = cur.fetchall()
    except Exception as e:
        logging.error(f"Error al leer base de datos: {e}")
        motores_db = []
    finally:
        cur.close()
        
    return render_template('iot.html', nodos=motores_db)

@app.route('/iot/borrar/<id>')
@require_gerente
def borrar_nodo(id):
    cur = mysql.connection.cursor()
    try:
        cur.execute("DELETE FROM Motor WHERE codigo_qr = %s", (id,))
        mysql.connection.commit()
        flash(f'Registro del motor {id} eliminado de la base de datos.')
    except Exception as e:
        logging.error(f"Error al eliminar motor: {e}")
        flash('Error: No se pudo eliminar el motor (Verifique restricciones de integridad).')
    finally:
        cur.close()
    return redirect(url_for('panel_iot'))

@app.route('/iot/editar/<id>', methods=['GET', 'POST'])
@require_gerente
def editar_nodo(id):
    cur = mysql.connection.cursor()
    
    if request.method == 'POST':
        nuevo_detalle = request.form.get('nombre_nodo').strip()
        if not nuevo_detalle:
            flash('Error: Las especificaciones no pueden estar vacías.')
            return redirect(url_for('panel_iot'))
            
        try:
            cur.execute("UPDATE Motor SET modelo = %s WHERE codigo_qr = %s", (nuevo_detalle, id))
            mysql.connection.commit()
            flash(f'Ficha técnica del motor {id} actualizada con éxito.')
        except Exception as e:
            logging.error(f"Error al actualizar motor: {e}")
            flash('Error: No se pudieron guardar los cambios.')
        finally:
            cur.close()
        return redirect(url_for('panel_iot'))
        
    cur.execute("SELECT codigo_qr, modelo FROM Motor WHERE codigo_qr = %s", (id,))
    nodo = cur.fetchone()
    cur.close()
    
    if not nodo:
        flash('Error: El motor solicitado no existe.')
        return redirect(url_for('panel_iot'))
        
    return render_template('editar-nodo.html', nodo=nodo)

@app.route("/login")
def login():
    return redirect(url_for('panel_iot'))

@app.route("/registrar")
def registrar():
    return redirect(url_for('panel_iot'))

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for('panel_iot'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)