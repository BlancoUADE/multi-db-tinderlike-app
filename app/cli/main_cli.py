import sys
from datetime import datetime
from app.services.auth_service import AuthService
from app.services.profile_service import ProfileService
from app.services.match_service import MatchService
from app.services.event_service import EventService
from app.services.block_service import BlockService
from app.services.report_service import ReportService

class TinderCLI:
    def __init__(self):
        self.auth_service = AuthService()
        self.profile_service = ProfileService()
        self.match_service = MatchService()
        self.event_service = EventService()
        self.block_service = BlockService()
        self.report_service = ReportService()
        self.current_user = None
        self.token = None

    def print_header(self, title):
        print("\n" + "=" * 50)
        print(f" {title.upper()} ".center(50, "="))
        print("=" * 50)

    def print_menu_options(self, options):
        for key, value in options.items():
            print(f" [{key}] {value}")
        print("=" * 50)

    def run(self):
        while True:
            if not self.token:
                self.menu_inicial()
            else:
                self.menu_principal()

    # --- MENÚ INICIAL ---
    def menu_inicial(self):
        self.print_header("Tinderlike App - Menú Inicial")
        options = {
            "1": "Registrarse",
            "2": "Iniciar Sesión",
            "3": "Salir"
        }
        self.print_menu_options(options)
        choice = input("Seleccione una opción: ").strip()
        
        if choice == "1":
            self.registro_usuario()
        elif choice == "2":
            self.login_usuario()
        elif choice == "3":
            print("\n¡Gracias por usar Tinderlike App!")
            sys.exit(0)
        else:
            print("\nOpción inválida. Intente de nuevo.")

    def registro_usuario(self):
        self.print_header("Registro de Nuevo Usuario")
        try:
            nombre = input("Nombre: ").strip()
            if not nombre: raise ValueError("El nombre es obligatorio.")
            
            edad = int(input("Edad: ").strip())
            if edad < 18: raise ValueError("Debes ser mayor de 18 años.")
            
            genero = input("Género (M/F/Otro): ").strip().upper()
            if genero not in ("M", "F", "OTRO"): raise ValueError("Género inválido.")
            
            ubicacion = input("Ubicación (ej: CABA): ").strip()
            if not ubicacion: raise ValueError("La ubicación es obligatoria.")
            
            biografia = input("Biografía: ").strip()
            
            pref_edad_min = int(input("Preferencia edad mínima: ").strip())
            pref_edad_max = int(input("Preferencia edad máxima: ").strip())
            if pref_edad_min > pref_edad_max: raise ValueError("Edad mínima no puede ser mayor que máxima.")
            
            email = input("Email: ").strip().lower()
            if not email or "@" not in email: raise ValueError("Email inválido.")
            
            password = input("Contraseña (Debe tener al menos 6 caracteres): ").strip()
            if len(password) < 6: raise ValueError("La contraseña debe tener al menos 6 caracteres.")
            
            # Additional photos / interests during registration
            url_foto = input("URL de tu foto de perfil (principal): ").strip()
            if not url_foto:
                url_foto = "default_profile.jpg"

            user_data = {
                "nombre": nombre,
                "edad": edad,
                "genero": genero,
                "ubicacion": ubicacion,
                "biografia": biografia,
                "pref_edad_min": pref_edad_min,
                "pref_edad_max": pref_edad_max,
                "email": email,
                "password": password,
                "fecha_registro": datetime.now()
            }
            
            id_usuario = self.auth_service.registrar_usuario(user_data)
            
            # Add initial profile photo
            self.profile_service.agregar_foto(id_usuario, url_foto, True)
            
            # Initial interests
            intereses_input = input("Ingresá tus intereses (separados por coma, ej: cine, musica): ").strip()
            if intereses_input:
                for i_name in intereses_input.split(","):
                    if i_name.strip():
                        self.profile_service.agregar_interes(id_usuario, i_name.strip())
            
            print(f"\n¡Usuario registrado con éxito! Tu ID es {id_usuario}.")
            
        except Exception as e:
            print(f"\n[ERROR] No se pudo registrar el usuario: {e}")

    def login_usuario(self):
        self.print_header("Iniciar Sesión")
        email = input("Email: ").strip().lower()
        password = input("Contraseña: ").strip()
        
        try:
            res = self.auth_service.iniciar_sesion(email, password)
            if res:
                self.token, self.current_user = res
                print(f"\n¡Bienvenido/a de nuevo, {self.current_user['nombre']}!")
            else:
                print("\nCredenciales inválidas o cuenta inactiva.")
        except Exception as e:
            print(f"\n[ERROR] Error al iniciar sesión: {e}")

    # --- MENÚ PRINCIPAL ---
    def menu_principal(self):
        # Refresh current user notification badges
        contador_notif = self.match_service.obtener_contador_no_leidas(self.current_user["id_usuario"])
        badge = f" ({contador_notif} NO LEÍDAS)" if contador_notif > 0 else ""

        self.print_header(f"Tinderlike App - Menú Principal (Usuario: {self.current_user['nombre']})")
        options = {
            "1": "Mi Perfil",
            "2": "Buscar Perfiles Compatibles",
            "3": "Coincidencias, Mensajes y Citas",
            "4": "Bloqueos",
            "5": f"Notificaciones{badge}",
            "6": "Reportes Analíticos",
            "7": "Cerrar Sesión"
        }
        self.print_menu_options(options)
        choice = input("Seleccione una opción: ").strip()
        
        if choice == "1":
            self.menu_mi_perfil()
        elif choice == "2":
            self.buscar_perfiles()
        elif choice == "3":
            self.menu_matches_mensajes_citas()
        elif choice == "4":
            self.menu_bloqueos()
        elif choice == "5":
            self.menu_notificaciones()
        elif choice == "6":
            self.menu_reportes()
        elif choice == "7":
            self.auth_service.cerrar_sesion(self.token, self.current_user["id_usuario"])
            self.token = None
            self.current_user = None
            print("\nSesión cerrada con éxito.")
        else:
            print("\nOpción inválida.")

    # --- MI PERFIL ---
    def menu_mi_perfil(self):
        while True:
            self.print_header("Mi Perfil")
            options = {
                "1": "Ver Mi Perfil",
                "2": "Editar Datos Personales",
                "3": "Editar Preferencias de Búsqueda",
                "4": "Gestionar Fotos",
                "5": "Gestionar Intereses",
                "6": "Volver"
            }
            self.print_menu_options(options)
            choice = input("Seleccione una opción: ").strip()
            
            if choice == "1":
                self.ver_mi_perfil()
            elif choice == "2":
                self.editar_datos_personales()
            elif choice == "3":
                self.editar_preferencias_busqueda()
            elif choice == "4":
                self.gestionar_fotos()
            elif choice == "5":
                self.gestionar_intereses()
            elif choice == "6":
                break
            else:
                print("\nOpción inválida.")

    def ver_mi_perfil(self):
        uid = self.current_user["id_usuario"]
        perfil = self.profile_service.obtener_perfil(uid)
        
        self.print_header(f"Perfil de {perfil['nombre']}")
        print(f"ID: {uid}")
        print(f"Edad: {perfil['edad']}")
        print(f"Género: {perfil['genero']}")
        print(f"Ubicación: {perfil['ubicacion']}")
        print(f"Biografía: {perfil['biografia']}")
        print(f"Intereses: {', '.join(perfil['intereses']) if perfil['intereses'] else 'Sin intereses cargados.'}")
        
        print("\nFotos:")
        if perfil["fotos"]:
            for f in perfil["fotos"]:
                principal_tag = " [PRINCIPAL]" if f["principal"] else ""
                print(f" - {f['url']}{principal_tag}")
        else:
            print(" Sin fotos cargadas.")
        
        print(f"\nPreferencias de búsqueda de edad: {self.current_user['pref_edad_min']} - {self.current_user['pref_edad_max']} años")
        input("\nPresione ENTER para continuar...")

    def editar_datos_personales(self):
        self.print_header("Editar Datos Personales")
        try:
            nombre = input(f"Nombre [{self.current_user['nombre']}]: ").strip() or self.current_user['nombre']
            edad = input(f"Edad [{self.current_user['edad']}]: ").strip()
            edad = int(edad) if edad else self.current_user['edad']
            if edad < 18: raise ValueError("Debes ser mayor de 18 años.")
            
            genero = input(f"Género (M/F/Otro) [{self.current_user['genero']}]: ").strip().upper() or self.current_user['genero']
            ubicacion = input(f"Ubicación [{self.current_user['ubicacion']}]: ").strip() or self.current_user['ubicacion']
            biografia = input(f"Biografía [{self.current_user['biografia'] or ''}]: ").strip() or self.current_user['biografia']
            
            update_data = {
                "nombre": nombre,
                "edad": edad,
                "genero": genero,
                "ubicacion": ubicacion,
                "biografia": biografia,
                "pref_edad_min": self.current_user["pref_edad_min"],
                "pref_edad_max": self.current_user["pref_edad_max"],
                "email": self.current_user["email"]
            }
            
            self.profile_service.actualizar_datos_personales(self.current_user["id_usuario"], update_data)
            # Refresh local current user object
            self.current_user = self.auth_service.pg_repo.obtener_usuario_por_id(self.current_user["id_usuario"])
            print("\n¡Datos personales actualizados con éxito!")
        except Exception as e:
            print(f"\n[ERROR] No se pudo actualizar: {e}")

    def editar_preferencias_busqueda(self):
        self.print_header("Editar Preferencias de Búsqueda")
        try:
            pref_min = input(f"Edad Mínima [{self.current_user['pref_edad_min']}]: ").strip()
            pref_min = int(pref_min) if pref_min else self.current_user['pref_edad_min']
            
            pref_max = input(f"Edad Máxima [{self.current_user['pref_edad_max']}]: ").strip()
            pref_max = int(pref_max) if pref_max else self.current_user['pref_edad_max']
            
            if pref_min > pref_max: raise ValueError("Mínimo no puede ser mayor al máximo.")
            
            update_data = {
                "nombre": self.current_user["nombre"],
                "edad": self.current_user["edad"],
                "genero": self.current_user["genero"],
                "ubicacion": self.current_user["ubicacion"],
                "biografia": self.current_user["biografia"],
                "pref_edad_min": pref_min,
                "pref_edad_max": pref_max,
                "email": self.current_user["email"]
            }
            
            self.profile_service.actualizar_datos_personales(self.current_user["id_usuario"], update_data)
            self.current_user = self.auth_service.pg_repo.obtener_usuario_por_id(self.current_user["id_usuario"])
            print("\n¡Preferencias de búsqueda actualizadas con éxito!")
        except Exception as e:
            print(f"\n[ERROR] No se pudo actualizar: {e}")

    def gestionar_fotos(self):
        uid = self.current_user["id_usuario"]
        while True:
            self.print_header("Gestionar Fotos")
            options = {
                "1": "Ver Mis Fotos",
                "2": "Agregar Foto",
                "3": "Marcar Foto como Principal",
                "4": "Eliminar Foto",
                "5": "Volver"
            }
            self.print_menu_options(options)
            choice = input("Seleccione una opción: ").strip()
            
            if choice == "1":
                fotos = self.profile_service.obtener_fotos(uid)
                print("\nMis Fotos:")
                for f in fotos:
                    principal_tag = " [PRINCIPAL]" if f["es_principal"] else ""
                    print(f" [{f['id_foto']}] {f['url_archivo']}{principal_tag}")
                input("\nPresione ENTER para continuar...")
                
            elif choice == "2":
                url = input("URL/Ruta de archivo de la foto: ").strip()
                if not url:
                    print("La URL es obligatoria.")
                    continue
                principal_inp = input("¿Marcar como foto principal? (S/N): ").strip().upper()
                es_principal = (principal_inp == "S")
                
                try:
                    self.profile_service.agregar_foto(uid, url, es_principal)
                    print("\n¡Foto agregada con éxito!")
                except Exception as e:
                    print(f"\n[ERROR] No se pudo agregar la foto: {e}")
                    
            elif choice == "3":
                fotos = self.profile_service.obtener_fotos(uid)
                print("\nSeleccione la foto a marcar como principal:")
                for f in fotos:
                    print(f" [{f['id_foto']}] {f['url_archivo']}")
                fid = input("ID de Foto: ").strip()
                if fid:
                    try:
                        self.profile_service.marcar_foto_principal(uid, int(fid))
                        print("\n¡Foto principal actualizada!")
                    except Exception as e:
                        print(f"\n[ERROR] {e}")
                        
            elif choice == "4":
                fotos = self.profile_service.obtener_fotos(uid)
                print("\nSeleccione la foto a eliminar:")
                for f in fotos:
                    print(f" [{f['id_foto']}] {f['url_archivo']}")
                fid = input("ID de Foto: ").strip()
                if fid:
                    try:
                        self.profile_service.eliminar_foto(uid, int(fid))
                        print("\n¡Foto eliminada!")
                    except Exception as e:
                        print(f"\n[ERROR] {e}")
            elif choice == "5":
                break

    def gestionar_intereses(self):
        uid = self.current_user["id_usuario"]
        while True:
            self.print_header("Gestionar Intereses")
            options = {
                "1": "Ver Mis Intereses",
                "2": "Agregar Interés",
                "3": "Quitar Interés",
                "4": "Volver"
            }
            self.print_menu_options(options)
            choice = input("Seleccione una opción: ").strip()
            
            if choice == "1":
                intereses = self.profile_service.obtener_intereses(uid)
                print("\nMis Intereses:")
                for i in intereses:
                    print(f" - {i['nombre']}")
                input("\nPresione ENTER para continuar...")
                
            elif choice == "2":
                nombre_int = input("Nombre del interés: ").strip().lower()
                if nombre_int:
                    try:
                        self.profile_service.agregar_interes(uid, nombre_int)
                        print(f"\n¡Interés '{nombre_int}' agregado!")
                    except Exception as e:
                        print(f"\n[ERROR] {e}")
                        
            elif choice == "3":
                intereses = self.profile_service.obtener_intereses(uid)
                print("\nSeleccione el interés a quitar:")
                for idx, i in enumerate(intereses):
                    print(f" [{idx + 1}] {i['nombre']}")
                choice_idx = input("Número de interés: ").strip()
                if choice_idx:
                    try:
                        idx = int(choice_idx) - 1
                        if 0 <= idx < len(intereses):
                            self.profile_service.quitar_interes(uid, intereses[idx]["id_interes"], intereses[idx]["nombre"])
                            print(f"\n¡Interés '{intereses[idx]['nombre']}' quitado!")
                        else:
                            print("Número fuera de rango.")
                    except Exception as e:
                        print(f"\n[ERROR] {e}")
            elif choice == "4":
                break

    # --- BUSCAR PERFILES COMPATIBLES ---
    def buscar_perfiles(self):
        uid = self.current_user["id_usuario"]
        generos_permitidos = ["F"] if self.current_user["genero"] == "M" else ["M"] if self.current_user["genero"] == "F" else ["M", "F", "OTRO"]
        
        # Try to pull cached recommendations from Redis
        recomendados = self.auth_service.redis_repo.obtener_recomendaciones_cacheadas(uid)
        if not recomendados:
            # Calculate recommendation list via Neo4j
            try:
                recomendados = self.auth_service.neo4j_repo.buscar_usuarios_compatibles(
                    id_usuario=uid,
                    pref_edad_min=self.current_user["pref_edad_min"],
                    pref_edad_max=self.current_user["pref_edad_max"],
                    generos_permitidos=generos_permitidos
                )
                # Cache list in Redis for 5 minutes
                self.auth_service.redis_repo.cachear_recomendaciones(uid, recomendados)
            except Exception as e:
                print(f"[ERROR] No se pudo buscar en el grafo de recomendaciones: {e}")
                return

        if not recomendados:
            print("\nNo encontramos más perfiles compatibles con tus preferencias en este momento.")
            input("Presione ENTER para volver...")
            return

        current_index = 0
        while current_index < len(recomendados):
            target_id = recomendados[current_index]
            perfil = self.profile_service.obtener_perfil(target_id)
            if not perfil:
                current_index += 1
                continue
                
            self.print_header(f"Perfil sugerido ({current_index + 1}/{len(recomendados)})")
            print(f"ID: {target_id}")
            print(f"Nombre: {perfil['nombre']}")
            print(f"Edad: {perfil['edad']}")
            print(f"Género: {perfil['genero']}")
            print(f"Ubicación: {perfil['ubicacion']}")
            print(f"Biografía: {perfil['biografia']}")
            print(f"Intereses: {', '.join(perfil['intereses']) if perfil['intereses'] else 'Sin intereses.'}")
            print(f"Cantidad de Fotos: {perfil['cantidad_fotos']}")
            
            print("\nAcciones:")
            print(" [1] Dar Like")
            print(" [2] Saltar Perfil")
            print(" [3] Bloquear Perfil")
            print(" [4] Ver Siguiente")
            print(" [5] Volver")
            print("=" * 50)
            
            opt = input("Seleccione una opción: ").strip()
            if opt == "1":
                try:
                    es_match, id_coincidencia = self.match_service.dar_like(uid, target_id)
                    if es_match:
                        print(f"\n*** ¡Felicidades! Tuviste un MATCH con {perfil['nombre']} (Match ID: {id_coincidencia}) ***")
                    else:
                        print(f"\nLe diste like a {perfil['nombre']}.")
                except Exception as e:
                    print(f"\n[ERROR] {e}")
                current_index += 1
                
            elif opt == "2":
                print("\nPerfil saltado.")
                current_index += 1
                
            elif opt == "3":
                try:
                    self.block_service.bloquear_usuario(uid, target_id)
                    print(f"\nBloqueaste a {perfil['nombre']}.")
                except Exception as e:
                    print(f"\n[ERROR] {e}")
                current_index += 1
                
            elif opt == "4":
                current_index += 1
                
            elif opt == "5":
                break
            else:
                print("Opción inválida.")
        else:
            print("\nLlegaste al final de los perfiles recomendados.")
            input("Presione ENTER para volver...")

    # --- COINCIDENCIAS, MENSAJES Y CITAS ---
    def menu_matches_mensajes_citas(self):
        uid = self.current_user["id_usuario"]
        while True:
            # Show list of matches first
            matches = self.match_service.obtener_coincidencias(uid)
            self.print_header("Coincidencias (Matches)")
            if not matches:
                print(" Aún no tenés coincidencias.")
            else:
                print(f"{'Otro ID':<8} | {'Nombre':<15} | {'Fecha':<20} | {'Último Mensaje'}")
                print("-" * 75)
                for m in matches:
                    snippet = m["ultimo_mensaje"][:30] + "..." if m["ultimo_mensaje"] else "[Sin mensajes]"
                    print(f"{m['otro_id']:<8} | {m['otro_nombre']:<15} | {m['fecha_coincidencia'].strftime('%Y-%m-%d %H:%M'):<20} | {snippet}")
            
            print("\nOpciones:")
            options = {
                "1": "Ver conversación con una coincidencia",
                "2": "Enviar mensaje a una coincidencia",
                "3": "Proponer cita (evento)",
                "4": "Ver citas propuestas por mí",
                "5": "Ver citas pendientes recibidas",
                "6": "Ver citas aceptadas",
                "7": "Volver"
            }
            self.print_menu_options(options)
            choice = input("Seleccione una opción: ").strip()
            
            if choice == "1":
                tid = input("Ingrese el ID del otro usuario: ").strip()
                if tid:
                    try:
                        coin = self.match_service.pg_repo.obtener_coincidencia(uid, int(tid))
                        if not coin:
                            print("No existe una coincidencia con este usuario.")
                            continue
                        mensajes = self.match_service.obtener_conversacion(coin["id_coincidencia"], uid)
                        self.print_header(f"Chat con {int(tid)}")
                        for msg in mensajes:
                            hora = msg["fecha_envio"].strftime("%H:%M")
                            print(f"[{hora}] {msg['emisor_nombre']}: {msg['contenido']}")
                        input("\nPresione ENTER para continuar...")
                    except Exception as e:
                        print(f"\n[ERROR] {e}")
                        
            elif choice == "2":
                tid = input("Ingrese el ID del otro usuario: ").strip()
                if tid:
                    try:
                        coin = self.match_service.pg_repo.obtener_coincidencia(uid, int(tid))
                        if not coin:
                            print("No existe una coincidencia con este usuario.")
                            continue
                        msg_text = input("Escribí tu mensaje: ").strip()
                        if msg_text:
                            self.match_service.enviar_mensaje(coin["id_coincidencia"], uid, msg_text)
                            print("\nMensaje enviado.")
                    except Exception as e:
                        print(f"\n[ERROR] {e}")
                        
            elif choice == "3":
                tid = input("Ingrese el ID del otro usuario: ").strip()
                if tid:
                    try:
                        coin = self.match_service.pg_repo.obtener_coincidencia(uid, int(tid))
                        if not coin:
                            print("No existe una coincidencia con este usuario.")
                            continue
                        nombre_ev = input("Nombre de la cita/evento (ej: Cena romántica): ").strip()
                        if not nombre_ev:
                            print("El nombre de la cita es obligatorio.")
                            continue
                        
                        fecha_str = input("Fecha y hora (Formato AAAA-MM-DD HH:MM, ej: 2026-06-15 20:30): ").strip()
                        try:
                            fecha_dt = datetime.strptime(fecha_str, "%Y-%m-%d %H:%M")
                        except ValueError:
                            print("Formato de fecha inválido.")
                            continue
                            
                        ubicacion = input("Ubicación de la cita: ").strip()
                        if not ubicacion:
                            print("La ubicación es obligatoria.")
                            continue
                            
                        self.event_service.proponer_cita(
                            id_organizador=uid,
                            id_coincidencia=coin["id_coincidencia"],
                            nombre_evento=nombre_ev,
                            fecha=fecha_dt,
                            ubicacion=ubicacion
                        )
                        print("\n¡Propuesta de cita enviada exitosamente!")
                    except Exception as e:
                        print(f"\n[ERROR] {e}")
                        
            elif choice == "4":
                propuestas = self.event_service.obtener_citas_propuestas(uid)
                self.print_header("Citas Propuestas por Mí")
                if not propuestas:
                    print(" No propusiste citas aún.")
                else:
                    for p in propuestas:
                        print(f"Cita: {p['nombre_evento']}")
                        print(f" Invitado/a: {p['invitado_nombre']}")
                        print(f" Fecha: {p['fecha'].strftime('%Y-%m-%d %H:%M')}")
                        print(f" Ubicación: {p['ubicacion']}")
                        print(f" Estado de respuesta: {p['asistencia_estado']}")
                        print("-" * 40)
                input("\nPresione ENTER para continuar...")
                
            elif choice == "5":
                recibidas = self.event_service.obtener_citas_pendientes_recibidas(uid)
                self.print_header("Propuestas de Cita Recibidas")
                if not recibidas:
                    print(" No tenés propuestas de cita pendientes.")
                else:
                    for r in recibidas:
                        print(f"ID Cita/Evento: {r['id_evento']}")
                        print(f" Organizador: {r['organizador_nombre']}")
                        print(f" Evento: {r['nombre_evento']}")
                        print(f" Fecha: {r['fecha'].strftime('%Y-%m-%d %H:%M')}")
                        print(f" Ubicación: {r['ubicacion']}")
                        print("-" * 40)
                    
                    ev_choice = input("\nIngrese el ID de Cita para contestar (o ENTER para volver): ").strip()
                    if ev_choice:
                        resp = input("¿Aceptar o Rechazar? (A/R): ").strip().upper()
                        try:
                            if resp == "A":
                                self.event_service.aceptar_cita(uid, int(ev_choice))
                                print("\n¡Cita aceptada!")
                            elif resp == "R":
                                self.event_service.rechazar_cita(uid, int(ev_choice))
                                print("\nCita rechazada.")
                            else:
                                print("Opción inválida.")
                        except Exception as e:
                            print(f"\n[ERROR] {e}")
                input("\nPresione ENTER para continuar...")
                
            elif choice == "6":
                aceptadas = self.event_service.obtener_citas_aceptadas(uid)
                self.print_header("Citas Aceptadas")
                if not aceptadas:
                    print(" No hay citas confirmadas aún.")
                else:
                    for a in aceptadas:
                        print(f"Cita: {a['nombre_evento']}")
                        print(f" Con: {a['otro_nombre']}")
                        print(f" Fecha: {a['fecha'].strftime('%Y-%m-%d %H:%M')}")
                        print(f" Ubicación: {a['ubicacion']}")
                        print("-" * 40)
                input("\nPresione ENTER para continuar...")
                
            elif choice == "7":
                break

    # --- BLOQUEOS ---
    def menu_bloqueos(self):
        uid = self.current_user["id_usuario"]
        while True:
            self.print_header("Bloqueos de Usuarios")
            options = {
                "1": "Ver usuarios bloqueados",
                "2": "Bloquear usuario",
                "3": "Desbloquear usuario",
                "4": "Volver"
            }
            self.print_menu_options(options)
            choice = input("Seleccione una opción: ").strip()
            
            if choice == "1":
                bloqueados = self.block_service.obtener_bloqueados_activos(uid)
                print("\nUsuarios Bloqueados Activos:")
                if not bloqueados:
                    print(" No bloqueaste a nadie.")
                else:
                    for b in bloqueados:
                        print(f" ID: {b['id_bloqueado']} | Nombre: {b['nombre_bloqueado']} | Bloqueado el: {b['fecha_bloqueo'].strftime('%Y-%m-%d')}")
                input("\nPresione ENTER para continuar...")
                
            elif choice == "2":
                tid = input("Ingrese el ID del usuario a bloquear: ").strip()
                if tid:
                    try:
                        self.block_service.bloquear_usuario(uid, int(tid))
                        print("\n¡Usuario bloqueado con éxito!")
                    except Exception as e:
                        print(f"\n[ERROR] {e}")

            elif choice == "3":
                tid = input("Ingrese el ID del usuario a desbloquear: ").strip()
                if tid:
                    try:
                        self.block_service.desbloquear_usuario(uid, int(tid))
                        print("\n¡Usuario desbloqueado con éxito!")
                    except Exception as e:
                        print(f"\n[ERROR] {e}")
            elif choice == "4":
                break

    # --- NOTIFICACIONES ---
    def menu_notificaciones(self):
        uid = self.current_user["id_usuario"]
        while True:
            self.print_header("Notificaciones")
            options = {
                "1": "Ver notificaciones no leídas",
                "2": "Ver todas las notificaciones",
                "3": "Marcar todas como leídas",
                "4": "Volver"
            }
            self.print_menu_options(options)
            choice = input("Seleccione una opción: ").strip()
            
            if choice == "1":
                notifs = self.match_service.obtener_notificaciones(uid, solo_no_leidas=True)
                print("\nNotificaciones Pendientes:")
                if not notifs:
                    print(" No tenés notificaciones nuevas.")
                else:
                    for n in notifs:
                        print(f" [{n['id_notificacion']}] Tipo: {n['tipo']} | Fecha: {n['fecha_creacion'].strftime('%Y-%m-%d %H:%M')}")
                # Auto-read them
                self.match_service.marcar_notificaciones_leidas(uid)
                print("\nLas notificaciones fueron marcadas como leídas.")
                input("\nPresione ENTER para continuar...")
                
            elif choice == "2":
                notifs = self.match_service.obtener_notificaciones(uid, solo_no_leidas=False)
                print("\nHistorial de Notificaciones:")
                if not notifs:
                    print(" No tenés notificaciones.")
                else:
                    for n in notifs:
                        estado = "LEÍDA" if n["leida"] else "NUEVA"
                        print(f" [{n['id_notificacion']}] [{estado}] Tipo: {n['tipo']} | Creada: {n['fecha_creacion'].strftime('%Y-%m-%d %H:%M')}")
                input("\nPresione ENTER para continuar...")
                
            elif choice == "3":
                self.match_service.marcar_notificaciones_leidas(uid)
                print("\nTodas las notificaciones marcadas como leídas.")
            elif choice == "4":
                break

    # --- REPORTES ---
    def menu_reportes(self):
        uid = self.current_user["id_usuario"]
        while True:
            self.print_header("Reportes Analíticos")
            options = {
                "1": "Promedio de coincidencias por día (Cassandra)",
                "2": "Atributos más populares en perfiles (MongoDB)",
                "3": "Perfiles con más swipes a la derecha (Redis)",
                "4": "Cantidad promedio de mensajes antes de una cita (Cassandra)",
                "5": "Intereses más comunes en coincidencias (Neo4j)",
                "6": "Perfiles +10 fotos y +3 intereses en común (MongoDB/Neo4j)",
                "7": "Coincidencias en fin de semana / feriados (Cassandra)",
                "8": "Volver"
            }
            self.print_menu_options(options)
            choice = input("Seleccione una opción: ").strip()
            
            try:
                if choice == "1":
                    avg, total = self.report_service.reporte_promedio_coincidencias_por_dia()
                    print(f"\n--- Promedio de Coincidencias ---")
                    print(f" Cantidad total de coincidiencias registradas: {total}")
                    print(f" Promedio de coincidencias diario: {avg:.2f} por día.")
                    
                    ans = input("\n¿Desea ver el detalle de un rango de fechas/semanal? (S/N): ").strip().lower()
                    if ans == 's':
                        start_str = input("Ingrese la fecha de inicio (AAAA-MM-DD, ej: 2026-06-08): ").strip()
                        end_str = input("Ingrese la fecha de fin (AAAA-MM-DD, ej: 2026-06-14): ").strip()
                        if start_str and end_str:
                            try:
                                range_stats = self.report_service.reporte_coincidencias_por_rango(start_str, end_str)
                                print(f"\n--- Coincidencias para el rango {start_str} al {end_str} ---")
                                dias_nombre = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
                                for day in range_stats:
                                    f = day["fecha"]
                                    dia_semana = dias_nombre[f.weekday()]
                                    es_fds = "Fin de semana" if day['cantidad_fin_de_semana'] > 0 else ""
                                    es_fer = "Feriado" if day['cantidad_feriado'] > 0 else ""
                                    flags = " | ".join(filter(None, [es_fds, es_fer]))
                                    flags_str = f" ({flags})" if flags else ""
                                    print(f"  * {f.strftime('%Y-%m-%d')} ({dia_semana}): {day['cantidad_coincidencias']} coincidencias{flags_str}")
                                
                                total_rango = sum(d['cantidad_coincidencias'] for d in range_stats)
                                prom_rango = total_rango / len(range_stats) if range_stats else 0.0
                                print(f"\n Total coincidencias en el rango: {total_rango}")
                                print(f" Promedio diario en el rango: {prom_rango:.2f} por día.")
                            except ValueError as ve:
                                print(f"\n[ERROR] {ve}")
                    input("\nPresione ENTER para volver...")
                    
                elif choice == "2":
                    rep = self.report_service.reporte_atributos_mas_populares()
                    print(f"\n--- Distribución de Géneros ---")
                    for g in rep["distribucion_generos"]:
                        print(f"  {g['genero']}: {g['cantidad']}")
                    print(f"\n--- Distribución de Ubicaciones ---")
                    for u in rep["distribucion_ubicaciones"]:
                        print(f"  {u['ubicacion']}: {u['cantidad']}")
                    print(f"\n--- Estadísticas de Edad ---")
                    print(f"  Edad promedio: {rep['edad_promedio']} años")
                    print(f"  Edad mínima: {rep['edad_minima']} | Edad máxima: {rep['edad_maxima']}")
                    print(f"\n--- Intereses más Populares ---")
                    for i in rep["intereses_populares"]:
                        print(f"  {i['interes']}: {i['cantidad']}")
                    print(f"\n--- Fotos promedio por usuario: {rep['promedio_fotos']} fotos.")
                    input("\nPresione ENTER para volver...")
                    
                elif choice == "3":
                    rep = self.report_service.reporte_top_swipes()
                    print(f"\n--- Top Swipes del Día (Redis) ---")
                    if not rep["top_diario"]:
                        print("  Aún sin ranking diario hoy.")
                    else:
                        for idx, item in enumerate(rep["top_diario"]):
                            print(f"  [{idx+1}] {item['nombre']} (ID: {item['id_usuario']}): {item['swipes']} swipes recibidos.")
                    input("\nPresione ENTER para volver...")
                    
                elif choice == "4":
                    avg, total = self.report_service.reporte_duracion_promedio_conversacion_cita()
                    print(f"\n--- Cantidad Promedio de Mensajes antes de una Cita ---")
                    print(f" Citas propuestas analizadas: {total}")
                    print(f" Cantidad promedio de mensajes: {avg:.2f} mensajes.")
                    input("\nPresione ENTER para volver...")
                    
                elif choice == "5":
                    rep = self.report_service.reporte_intereses_comunes_coincidencias()
                    print(f"\n--- Intereses Comunes en Coincidencias (Neo4j) ---")
                    if not rep:
                        print("  Sin intereses compartidos en matches.")
                    else:
                        for idx, item in enumerate(rep):
                            print(f"  [{idx+1}] {item['interes']}: Compartido en {item['cantidad']} coincidencias.")
                    input("\nPresione ENTER para volver...")
                    
                elif choice == "6":
                    rep = self.report_service.reporte_perfiles_mas_diez_fotos_intereses_comunes(uid)
                    print(f"\n--- Perfiles +10 Fotos y >=3 Intereses Comunes ---")
                    if not rep:
                        print("  No se encontraron perfiles con más de 10 fotos y al menos 3 intereses en común con vos.")
                    else:
                        for u in rep:
                            print(f" - Nombre: {u['nombre']} (ID: {u['id_usuario']}) | Edad: {u['edad']} | Ubicación: {u['ubicacion']}")
                            print(f"   Intereses comunes contigo: {u['intereses_en_comun']} compartidos.")
                            print("-" * 50)
                    input("\nPresione ENTER para volver...")
                    
                elif choice == "7":
                    rep = self.report_service.reporte_coincidencias_fin_de_semana_feriados()
                    print(f"\n--- Métricas por Tipo de Día (Fines de Semana y Feriados) ---")
                    print(f" Coincidencias totales registradas: {rep['total_coincidencias']}")
                    print(f" Coincidencias en fines de semana: {rep['coincidencias_fin_de_semana']} ({rep['porcentaje_fin_de_semana']}%)")
                    print(f" Coincidencias en feriados: {rep['coincidencias_feriados']} ({rep['porcentaje_feriados']}%)")
                    input("\nPresione ENTER para volver...")
                    
                elif choice == "8":
                    break
            except Exception as e:
                print(f"\n[ERROR] Error al calcular el reporte: {e}")
                input("\nPresione ENTER para volver...")
