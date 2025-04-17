from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash 
from pymongo.errors import PyMongoError
from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi
import zipfile
import os
from datetime import datetime
import json
import re
from elasticsearch import Elasticsearch

app = Flask(__name__)
app.secret_key = 'MaiRoj2024+'  # Cambia esto por una clave secreta segura

# Agregar la función now al contexto de la plantilla
@app.context_processor
def inject_now():
    return {'now': datetime.now}

# Versión de la aplicación
VERSION_APP = "Versión 1 de 2025"
CREATOR_APP = "Maira Alejandra Rojas Diaz"
mongo_uri   = os.environ.get("MONGO_URI")

if not mongo_uri:
    #uri = "mongodb+srv://DbCentral:DbCentral2025@cluster0.vhltza7.mongodb.net/?appName=Cluster0"
    uri         = "mongodb+srv://DbCentral:DbCentral2025@cluster0.od4slcb.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0"
    mongo_uri   = uri

# Función para conectar a MongoDB
def connect_mongo():
    try:
        client = MongoClient(mongo_uri, server_api=ServerApi('1'))
        client.admin.command('ping')
        print("Conexión exitosa a MongoDB!")
        return client
    except Exception as e:
        print(f"Error al conectar a MongoDB: {e}")
        return None

# Configuración de Elasticsearch
client = Elasticsearch(
    "https://bigdata-d26ba1.es.us-east-1.aws.elastic.cloud:443",
    api_key="d0twcVBKY0JHYUVaNWhvZnhRUVg6S3l6VnI0VEwtZGdsZ1JHR0FRZGd4dw=="
)
INDEX_NAME = "base"

@app.route('/')
def index():
    return render_template('index.html', version=VERSION_APP,creador=CREATOR_APP)

@app.route('/about')
def about():
    return render_template('about.html', version=VERSION_APP,creador=CREATOR_APP)

@app.route('/contacto', methods=['GET', 'POST'])
def contacto():
    if request.method == 'POST':
        nombre = request.form.get('nombre')
        email = request.form.get('email')
        asunto = request.form.get('asunto')
        mensaje = request.form.get('mensaje')

        # Aquí va la lógica para enviar el mensaje a la base de datos de MongoDB
        client = connect_mongo()
        if client:
            db = client['administracion']
            contactos_collection = db['contactos']
            contactos_collection.insert_one({
                'nombre': nombre,
                'email': email,
                'asunto': asunto,
                'mensaje': mensaje
            })
            client.close()
        return redirect(url_for('contacto'))
    return render_template('contacto.html', version=VERSION_APP,creador=CREATOR_APP)


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        # Primero verificar la conectividad con MongoDB
        client = connect_mongo()
        if not client:
            return render_template('login.html', error_message='Error de conexión con la base de datos. Por favor, intente más tarde.', version=VERSION_APP,creador=CREATOR_APP)
        
        try:
            db = client['administracion']
            security_collection = db['seguridad']
            usuario = request.form['usuario']
            password = request.form['password']
            # Verificar credenciales en MongoDB
            user = security_collection.find_one({
                'usuario': usuario,
                'password': password
            })
            
            if user:
                session['usuario'] = usuario
                return redirect(url_for('gestion_proyecto'))
            else:
                return render_template('login.html', error_message='Usuario o contraseña incorrectos', version=VERSION_APP,creador=CREATOR_APP)
        except Exception as e:
            return render_template('login.html', error_message=f'Error al validar credenciales: {str(e)}', version=VERSION_APP,creador=CREATOR_APP)
            
        finally:
            client.close()
    
    return render_template('login.html', version=VERSION_APP,creador=CREATOR_APP)

@app.route('/listar-usuarios')
def listar_usuarios():
    try:
        client = connect_mongo()
        if not client:
            return jsonify({'error': 'Error de conexión con la base de datos'}), 500
        
        db = client['administracion']
        security_collection = db['seguridad']
        
        # Obtener todos los usuarios, excluyendo la contraseña por seguridad
        #usuarios = list(security_collection.find({}, {'password': 0}))

        usuarios = list(security_collection.find({}, {'password': 0}))
        
        # Convertir ObjectId a string para serialización JSON
        for usuario in usuarios:
            usuario['_id'] = str(usuario['_id'])
        
        return jsonify(usuarios)
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        if 'client' in locals():
            client.close()

@app.route('/gestion_proyecto', methods=['GET', 'POST'])
def gestion_proyecto():
    if 'usuario' not in session:
        return redirect(url_for('login'))
    
    try:
        client = connect_mongo()
        # Obtener lista de bases de datos
        databases = client.list_database_names()
        # Eliminar bases de datos del sistema
        system_dbs = ['admin', 'local', 'config', 'administracion']
        databases = [db for db in databases if db not in system_dbs]
        
        selected_db = request.form.get('database') if request.method == 'POST' else request.args.get('database')
        collections_data = []
        
        if selected_db:
            db = client[selected_db]
            collections = db.list_collection_names()
            for index, collection_name in enumerate(collections, 1):
                collection = db[collection_name]
                count = collection.count_documents({})
                collections_data.append({
                    'index': index,
                    'name': collection_name,
                    'count': count
                })
        
        return render_template('gestion/index.html',
                            databases=databases,
                            selected_db=selected_db,
                            collections_data=collections_data,
                            version=VERSION_APP,
                            creador=CREATOR_APP,
                            usuario=session['usuario'])
    except Exception as e:
        return render_template('gestion/index.html',
                            error_message=f'Error al conectar con MongoDB: {str(e)}',
                            version=VERSION_APP,
                            creador=CREATOR_APP,
                            usuario=session['usuario'])

@app.route('/crear-coleccion-form/<database>')
def crear_coleccion_form(database):
    if 'usuario' not in session:
        return redirect(url_for('login'))
    return render_template('gestion/crear_coleccion.html', 
                        database=database,
                        usuario=session['usuario'],
                        version=VERSION_APP,
                        creador=CREATOR_APP)

@app.route('/crear-coleccion', methods=['POST'])
def crear_coleccion():
    # 1. Verificar sesión de usuario
    if 'usuario' not in session:
        flash('Debes iniciar sesión para crear colecciones.', 'warning')
        return redirect(url_for('login'))
    
    # Inicializar variables para asegurar que se cierren en el bloque finally
    client_mongo = None 
    temp_dir = None

    try:
        database = request.form.get('database')
        collection_name = request.form.get('collection_name')
        zip_file = request.files.get('zip_file')
        
        # 2. Validación inicial de campos
        if not all([database, collection_name, zip_file]):
            flash('Todos los campos (Base de datos, Nombre de colección, Archivo ZIP) son requeridos.', 'error')
            # Renderizar la plantilla con los datos que ya se habían ingresado
            return render_template('gestion/crear_coleccion.html',
                                   database=database, # Mantener el nombre de la DB si ya se ingresó
                                   usuario=session['usuario'],
                                   version=VERSION_APP,
                                   creador=CREATOR_APP)
        
        # 3. Conectar a MongoDB
        client_mongo = connect_mongo() # Asumiendo que connect_mongo() devuelve el cliente o None
        if not client_mongo:
            flash('Error de conexión con MongoDB. No se pudo crear la colección.', 'error')
            return render_template('gestion/crear_coleccion.html',
                                   database=database,
                                   usuario=session['usuario'],
                                   version=VERSION_APP,
                                   creador=CREATOR_APP)
        
        # Seleccionar la base de datos y la colección
        db = client_mongo[database]
        collection = db[collection_name]
        
        # 4. Procesar el archivo ZIP de forma más eficiente y segura
        # Crear un directorio temporal ÚNICO para almacenar el ZIP subido
        # y evitar conflictos si múltiples usuarios suben archivos
        temp_dir = os.path.join(os.path.dirname(__file__), 'temp_uploads', str(datetime.now().timestamp()))
        os.makedirs(temp_dir, exist_ok=True)
        
        # Guardar el archivo ZIP subido en el directorio temporal
        zip_path = os.path.join(temp_dir, zip_file.filename)
        zip_file.save(zip_path) # Guarda el archivo subido en el servidor
        
        inserted_count = 0 # Contador para los documentos insertados
        
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            # Iterar sobre los archivos dentro del ZIP sin extraerlos todos a la vez.
            # Esto es clave para reducir el consumo de memoria y disco.
            for file_in_zip in zip_ref.namelist():
                # Procesar solo archivos JSON y omitir directorios dentro del ZIP
                if file_in_zip.endswith('.json') and not file_in_zip.endswith('/'):
                    try:
                        # Abrir y leer el contenido del archivo JSON directamente desde el ZIP
                        with zip_ref.open(file_in_zip) as f:
                            json_data = json.load(f)
                            
                            # Si el JSON es una lista, insertar en lotes (batch insert)
                            # Esto es CRÍTICO para el rendimiento con muchos documentos
                            if isinstance(json_data, list):
                                batch_size = 1000 # Define un tamaño de lote adecuado
                                documents_to_insert = []
                                for doc in json_data:
                                    documents_to_insert.append(doc)
                                    if len(documents_to_insert) >= batch_size:
                                        collection.insert_many(documents_to_insert)
                                        inserted_count += len(documents_to_insert)
                                        documents_to_insert = [] # Resetear el lote
                                # Insertar cualquier documento restante en el último lote
                                if documents_to_insert:
                                    collection.insert_many(documents_to_insert)
                                    inserted_count += len(documents_to_insert)
                                    
                            else:
                                # Si es un solo documento JSON
                                collection.insert_one(json_data)
                                inserted_count += 1

                    except json.JSONDecodeError:
                        # Error si un archivo dentro del ZIP no es un JSON válido
                        print(f"Error: Archivo JSON inválido dentro del ZIP: {file_in_zip}")
                        flash(f'Advertencia: El archivo "{file_in_zip}" en el ZIP no es un JSON válido y fue ignorado.', 'warning')
                    except Exception as e:
                        # Otros errores durante la inserción
                        print(f"Error al procesar/insertar datos de {file_in_zip}: {str(e)}")
                        flash(f'Advertencia: Error al procesar "{file_in_zip}": {str(e)}. Algunos datos podrían no haberse insertado.', 'warning')
        
        flash(f'Colección "{collection_name}" creada y {inserted_count} documentos insertados exitosamente en la base de datos "{database}".', 'success')
        return redirect(url_for('gestion_proyecto', database=database))
        
    except PyMongoError as e:
        # Captura errores específicos de PyMongo (conexión, operaciones de DB, etc.)
        flash(f'Error de base de datos al crear la colección: {str(e)}', 'error')
        print(f"Error de PyMongo en crear_coleccion: {e}")
        return render_template('gestion/crear_coleccion.html',
                                database=database,
                                usuario=session['usuario'],
                                version=VERSION_APP,
                                creador=CREATOR_APP)
    except Exception as e:
        # Captura cualquier otra excepción inesperada
        flash(f'Error inesperado al crear la colección: {str(e)}', 'error')
        print(f"Error inesperado en crear_coleccion: {e}")
        return render_template('gestion/crear_coleccion.html',
                                database=database,
                                usuario=session['usuario'],
                                version=VERSION_APP,
                                creador=CREATOR_APP)
    finally:
        # Asegurarse de limpiar el directorio temporal y cerrar la conexión a MongoDB
        if temp_dir and os.path.exists(temp_dir):
            try:
                shutil.rmtree(temp_dir) # Elimina el directorio y todo su contenido
                print(f"Directorio temporal '{temp_dir}' limpiado.")
            except Exception as e:
                print(f"Error al limpiar el directorio temporal '{temp_dir}': {str(e)}")
        
        if client_mongo:
            client_mongo.close()
            print("Conexión a MongoDB cerrada.")

@app.route('/ver-registros/<database>/<collection>')
def ver_registros(database, collection):
    if 'usuario' not in session:
        return redirect(url_for('login'))
    
    try:
        client = connect_mongo()
        if not client:
            return render_template('gestion/index.html',
                                error_message='Error de conexión con MongoDB',
                                version=VERSION_APP,
                                creador=CREATOR_APP,
                                usuario=session['usuario'])
        
        db = client[database]
        collection_obj = db[collection]
        
        # Obtener los primeros 100 registros por defecto
        records = list(collection_obj.find().limit(100))
        
        # Convertir ObjectId a string para serialización JSON
        for record in records:
            record['_id'] = str(record['_id'])
        
        return render_template('gestion/ver_registros.html',
                            database=database,
                            collection_name=collection,
                            records=records,
                            version=VERSION_APP,
                            creador=CREATOR_APP,
                            usuario=session['usuario'])
    except Exception as e:
        return render_template('gestion/index.html',
                            error_message=f'Error al obtener registros: {str(e)}',
                            version=VERSION_APP,
                            creador=CREATOR_APP,
                            usuario=session['usuario'])
    finally:
        if 'client' in locals():
            client.close()

@app.route('/obtener-registros', methods=['POST'])
def obtener_registros():
    if 'usuario' not in session:
        return jsonify({'error': 'No autorizado'}), 401
    
    try:
        database = request.form.get('database')
        collection = request.form.get('collection')
        limit = int(request.form.get('limit', 100))
        
        client = connect_mongo()
        if not client:
            return jsonify({'error': 'Error de conexión con MongoDB'}), 500
        
        db = client[database]
        collection_obj = db[collection]
        
        # Obtener los registros con el límite especificado
        records = list(collection_obj.find().limit(limit))
        
        # Convertir ObjectId a string para serialización JSON
        for record in records:
            record['_id'] = str(record['_id'])
        
        return jsonify({'records': records})
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        if 'client' in locals():
            client.close()

@app.route('/crear-base-datos-form')
def crear_base_datos_form():
    if 'usuario' not in session:
        return redirect(url_for('login'))
    return render_template('gestion/crear_base_datos.html',
                        version=VERSION_APP,
                        creador=CREATOR_APP,
                        usuario=session['usuario'])

@app.route('/crear-base-datos', methods=['POST'])
def crear_base_datos():
    if 'usuario' not in session:
        return redirect(url_for('login'))
    
    try:
        database_name = request.form.get('database_name')
        collection_name = request.form.get('collection_name')
        
        # Validar que los nombres no contengan caracteres especiales
        valid_pattern = re.compile(r'^[a-zA-Z0-9_]+$')
        if not valid_pattern.match(database_name) or not valid_pattern.match(collection_name):
            return render_template('gestion/crear_base_datos.html',
                                error_message='Los nombres no pueden contener tildes, espacios ni caracteres especiales',
                                version=VERSION_APP,
                                creador=CREATOR_APP,
                                usuario=session['usuario'])
        
        # Conectar a MongoDB
        client = connect_mongo()
        if not client:
            return render_template('gestion/crear_base_datos.html',
                                error_message='Error de conexión con MongoDB',
                                version=VERSION_APP,
                                creador=CREATOR_APP,
                                usuario=session['usuario'])
        
        # Crear la base de datos y la colección
        db = client[database_name]
        collection = db[collection_name]
        
        # Insertar un documento vacío para crear la colección
        collection.insert_one({})
        
        # Eliminar el documento vacío
        collection.delete_one({})
        
        return redirect(url_for('gestion_proyecto', database=database_name))
        
    except Exception as e:
        return render_template('gestion/crear_base_datos.html',
                            error_message=f'Error al crear la base de datos: {str(e)}',
                            version=VERSION_APP,
                            creador=CREATOR_APP,
                            usuario=session['usuario'])
    finally:
        if 'client' in locals():
            client.close()

@app.route('/logout')
def logout():
    # Limpiar todas las variables de sesión
    session.clear()
    # Redirigir al index principal
    return redirect(url_for('index'))

@app.route('/elasticAdmin')
def elasticAdmin():
    if 'usuario' not in session:
        return redirect(url_for('login'))
    
    try:
        # Obtener información del índice
        index_info = client.indices.get(index=INDEX_NAME)
        doc_count = client.count(index=INDEX_NAME)['count']
        
        return render_template('gestion/ver_elasticAdmin.html',
                            index_name=INDEX_NAME,
                            doc_count=doc_count,
                            version=VERSION_APP,
                            creador=CREATOR_APP,
                            usuario=session['usuario'])
    except Exception as e:
        return render_template('gestion/ver_elasticAdmin.html',
                            error_message=f'Error al conectar con Elasticsearch: {str(e)}',
                            version=VERSION_APP,
                            creador=CREATOR_APP,
                            usuario=session['usuario'])

@app.route('/elastic-agregar-documentos', methods=['GET', 'POST'])
def elastic_agregar_documentos():
    if 'usuario' not in session:
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        try:
            if 'zipFile' not in request.files:
                return render_template('gestion/elastic_agregar_documentos.html',
                                    error_message='No se ha seleccionado ningún archivo',
                                    index_name=INDEX_NAME,
                                    version=VERSION_APP,
                                    creador=CREATOR_APP,
                                    usuario=session['usuario'])
            
            zip_file = request.files['zipFile']
            if zip_file.filename == '':
                return render_template('gestion/elastic_agregar_documentos.html',
                                    error_message='No se ha seleccionado ningún archivo',
                                    index_name=INDEX_NAME,
                                    version=VERSION_APP,
                                    creador=CREATOR_APP,
                                    usuario=session['usuario'])
            
            # Crear directorio temporal
            temp_dir = os.path.join(os.path.dirname(__file__), 'temp')
            os.makedirs(temp_dir, exist_ok=True)
            
            # Guardar y extraer el archivo ZIP
            zip_path = os.path.join(temp_dir, zip_file.filename)
            zip_file.save(zip_path)
            
            with zipfile.ZipFile(zip_path) as zip_ref:
                zip_ref.extractall(temp_dir)
            
            # Procesar archivos JSON
            success_count = 0
            error_count = 0
            
            for root, _, files in os.walk(temp_dir):
                for file in files:
                    if file.endswith('.json'):
                        file_path = os.path.join(root, file)
                        try:
                            with open(file_path, 'r', encoding='utf-8') as f:
                                json_data = json.load(f)
                                if isinstance(json_data, list):
                                    for doc in json_data:
                                        client.index(index=INDEX_NAME, document=doc)
                                        success_count += 1
                                else:
                                    client.index(index=INDEX_NAME, document=json_data)
                                    success_count += 1
                        except Exception as e:
                            error_count += 1
                            print(f"Error procesando {file}: {str(e)}")
            
            # Limpiar archivos temporales
            for root, dirs, files in os.walk(temp_dir, topdown=False):
                for file in files:
                    os.remove(os.path.join(root, file))
                for dir in dirs:
                    os.rmdir(os.path.join(root, dir))
            os.rmdir(temp_dir)
            
            return render_template('gestion/elastic_agregar_documentos.html',
                                success_message=f'Se indexaron {success_count} documentos exitosamente. Errores: {error_count}',
                                index_name=INDEX_NAME,
                                version=VERSION_APP,
                                creador=CREATOR_APP,
                                usuario=session['usuario'])
            
        except Exception as e:
            return render_template('gestion/elastic_agregar_documentos.html',
                                error_message=f'Error al procesar el archivo: {str(e)}',
                                index_name=INDEX_NAME,
                                version=VERSION_APP,
                                creador=CREATOR_APP,
                                usuario=session['usuario'])
    
    return render_template('gestion/elastic_agregar_documentos.html',
                         index_name=INDEX_NAME,
                         version=VERSION_APP,
                         creador=CREATOR_APP,
                         usuario=session['usuario'])

@app.route('/elastic-listar-documentos')
def elastic_listar_documentos():
    if 'usuario' not in session:
        return redirect(url_for('login'))
    
    try:
        # Obtener los primeros 100 documentos
        response = client.search(
            index=INDEX_NAME,
            body={
                "query": {"match_all": {}},
                "size": 100
            }
        )
        
        documents = response['hits']['hits']
        
        return render_template('gestion/elastic_listar_documentos.html',
                            index_name=INDEX_NAME,
                            documents=documents,
                            version=VERSION_APP,
                            creador=CREATOR_APP,
                            usuario=session['usuario'])
    except Exception as e:
        return render_template('gestion/elastic_listar_documentos.html',
                            error_message=f'Error al obtener documentos: {str(e)}',
                            index_name=INDEX_NAME,
                            version=VERSION_APP,
                            creador=CREATOR_APP,
                            usuario=session['usuario'])

@app.route('/elastic-eliminar-documento', methods=['POST'])
def elastic_eliminar_documento():
    if 'usuario' not in session:
        return jsonify({'error': 'No autorizado'}), 401
    
    try:
        doc_id = request.form.get('doc_id')
        if not doc_id:
            return jsonify({'error': 'ID de documento no proporcionado'}), 400
        
        response = client.delete(index=INDEX_NAME, id=doc_id)
        
        if response['result'] == 'deleted':
            return jsonify({'success': True})
        else:
            return jsonify({'error': 'Error al eliminar el documento'}), 500
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/buscador', methods=['GET', 'POST'])
def buscador():
    if request.method == 'POST':
        try:
            # Obtener los parámetros del formulario
            search_type = request.form.get('search_type')
            search_text = request.form.get('search_text')
            fecha_desde = request.form.get('fecha_desde')
            fecha_hasta = request.form.get('fecha_hasta')

            # Nuevos parámetros para los filtros de la interfaz
            selected_categorias = request.form.getlist('categoria_filter') # Usa getlist para checkboxes
            selected_clasificaciones = request.form.getlist('clasificacion_filter') # Usa getlist para checkboxes
            selected_fechas_years = request.form.getlist('fecha_filter') # Años seleccionados (ej. '1984', '2025')


            # Establecer fechas por defecto si están vacías
            if not fecha_desde:
                fecha_desde = "1500-01-01"
            if not fecha_hasta:
                fecha_hasta = datetime.now().strftime("%Y-%m-%d")

            # Construir la consulta base
            query = {
                "query": {
                    "bool": {
                        "must": []
                    }
                },
                "aggs": {
                    "categoria": {
                        "terms": {
                            "field": "categoria",
                            "size": 10,
                            "order": {"_key": "asc"}
                        }
                    },
                    "clasificacion": {
                        "terms": {
                            "field": "clasificacion",
                            "size": 10,
                            "order": {"_key": "asc"}
                        }
                    },
                    "Fecha": {
                        "date_histogram": {
                            "field": "fecha",
                            "calendar_interval": "year",
                            "format": "yyyy"
                        }
                    }
                }
            }

            # Agregar condición de búsqueda según el tipo
            if search_type == 'texto':
                query["query"]["bool"]["must"].extend([
                    {
                        "query_string": {
                            "fields": ["texto"],  # El campo específico para 'texto'
                            "query": f"{search_text}",
                            "default_operator": "OR"
                        }
                    }
                ])
            else:
                query["query"]["bool"]["must"].append(
                    {
                        "query_string": {
                            "fields": [search_type],
                            "query": f"{search_text}",
                            "default_operator": "AND"
                        }
                    }
                )

            # Agregar rango de fechas
            range_query = {
                "range": {
                    "fecha": {
                        "format": "yyyy-MM-dd",
                        "gte": fecha_desde,
                        "lte": fecha_hasta
                    }
                }
            }
            query["query"]["bool"]["must"].append(range_query)

            # --- Agregar Filtros de la Interfaz ---

            # Filtro por Categoría
            if selected_categorias:
                query["query"]["bool"]["must"].append({
                    "terms": {
                        "categoria.keyword": selected_categorias
                    }
                })

            # Filtro por Clasificación
            if selected_clasificaciones:
                query["query"]["bool"]["must"].append({
                    "terms": {
                        "clasificacion.keyword": selected_clasificaciones
                    }
                })

            # Filtro por Fecha (años específicos seleccionados)
            if selected_fechas_years:
                # Si el usuario selecciona años específicos, sobrescribimos el rango de fechas
                # con un filtro OR para esos años.
                # Es crucial que tu campo 'fecha' en Elasticsearch sea de tipo 'date'.
                year_queries = []
                for year in selected_fechas_years:
                    year_queries.append({
                        "range": {
                            "fecha": {
                                "gte": f"{year}-01-01",
                                "lte": f"{year}-12-31",
                                "format": "yyyy-MM-dd"
                            }
                        }
                    })
                query["query"]["bool"]["must"].append({
                    "bool": {
                        "should": year_queries, # Usamos 'should' (OR) para los años seleccionados
                        "minimum_should_match": 1
                    }
                })
            else:
                # Si no hay años específicos seleccionados, aplicamos el rango de fechas general
                range_query = {
                    "range": {
                        "fecha": {
                            "format": "yyyy-MM-dd",
                            "gte": fecha_desde,
                            "lte": fecha_hasta
                        }
                    }
                }
                query["query"]["bool"]["must"].append(range_query)

            # Ejecutar la búsqueda en Elasticsearch
            response = client.search(
                index=INDEX_NAME,
                body=query
            )

            # Preparar los resultados para la plantilla
            hits         = response['hits']['hits']
            aggregations = response['aggregations']

            return render_template('buscador.html',
                                version=VERSION_APP,
                                creador=CREATOR_APP,
                                hits=hits,
                                aggregations=aggregations,
                                search_type=search_type,
                                search_text=search_text,
                                fecha_desde=fecha_desde,
                                fecha_hasta=fecha_hasta,
                                query=query)
        
        except Exception as e:
            return render_template('buscador.html',
                                version=VERSION_APP,
                                creador=CREATOR_APP,
                                error_message=f'Error en la búsqueda: {str(e)}')
    
    return render_template('buscador.html',
                        version=VERSION_APP,
                        creador=CREATOR_APP)

@app.route('/api/search', methods=['POST'])
def search():
    try:
        data = request.get_json()
        index_name = data.get('index', 'base')
        query = data.get('query')

        # Ejecutar la búsqueda en Elasticsearch
        response = client.search(
            index=index_name,
            body=query
        )

        return jsonify(response)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)