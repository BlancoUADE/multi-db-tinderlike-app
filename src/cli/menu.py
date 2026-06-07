import sys
from src.services.app_service import AppService

class TinderCLI:
    def __init__(self):
        self.service = AppService()
        self.session_token = None
        self.current_user = None

    def ask_text(self, prompt_text):
        while True:
            val = input(prompt_text).strip()
            if val:
                return val
            print("El valor no puede estar vacío.")

    def ask_int(self, prompt_text, minimum=None):
        while True:
            val_str = input(prompt_text).strip()
            try:
                val = int(val_str)
                if minimum is not None and val < minimum:
                    print(f"El valor debe ser al menos {minimum}.")
                    continue
                return val
            except ValueError:
                print("Ingrese un número entero válido.")

    def show_welcome(self):
        print("\n" + "="*50)
        print("          BIENVENIDO A TINDER CLI (TPO)")
        print("="*50)

    def run(self):
        self.show_welcome()
        while True:
            if not self.session_token:
                self.show_anonymous_menu()
            else:
                self.show_authenticated_menu()

    def show_anonymous_menu(self):
        print("\n--- MENÚ PRINCIPAL ---")
        print("1. Registrar nuevo usuario")
        print("2. Iniciar sesión")
        print("3. Salir")
        
        op = input("\nSeleccione una opción: ").strip()
        if op == "1":
            self.do_register()
        elif op == "2":
            self.do_login()
        elif op == "3":
            print("\n¡Hasta luego!")
            sys.exit(0)
        else:
            print("Opción inválida.")

    def show_authenticated_menu(self):
        print(f"\n--- SESIÓN ACTIVA: {self.current_user['nombre']} ---")
        print("1. Ver información de mi sesión")
        print("2. Ver / Editar mi Perfil")
        print("3. Subir Foto")
        print("4. Buscar Perfiles Compatibles (Recomendados)")
        print("5. Conversaciones y Mensajería")
        print("6. Bloquear a un Usuario")
        print("7. Eventos Sociales")
        print("8. Reportes Analíticos (Fase 6)")
        print("9. Cerrar sesión")
        print("10. Salir")
        
        op = input("\nSeleccione una opción: ").strip()
        if op == "1":
            self.show_session_info()
        elif op == "2":
            self.do_profile_menu()
        elif op == "3":
            self.do_upload_photo()
        elif op == "4":
            self.do_search_candidates()
        elif op == "5":
            self.do_conversations()
        elif op == "6":
            self.do_block_user()
        elif op == "7":
            self.do_events_menu()
        elif op == "8":
            self.do_reports_menu()
        elif op == "9":
            self.do_logout()
        elif op == "10":
            print("\n¡Hasta luego!")
            sys.exit(0)
        else:
            print("Opción inválida.")

    def do_register(self):
        print("\n>>> REGISTRO DE NUEVO USUARIO <<<")
        nombre = self.ask_text("Nombre: ")
        email = self.ask_text("Email: ")
        password = self.ask_text("Contraseña: ")
        edad = self.ask_int("Edad: ", minimum=18)
        genero = self.ask_text("Género (Masculino/Femenino/Otro): ")
        ubicacion = self.ask_text("Ubicación (Ciudad/Provincia): ")

        try:
            user_id = self.service.register_user(
                nombre=nombre,
                email=email,
                password=password,
                edad=edad,
                genero=genero,
                ubicacion=ubicacion
            )
            print(f"\n[ÉXITO] Usuario registrado correctamente con ID: {user_id}")
        except Exception as e:
            print(f"\n[ERROR] No se pudo completar el registro: {e}")

    def do_login(self):
        print("\n>>> INICIO DE SESIÓN <<<")
        email = self.ask_text("Email: ")
        password = self.ask_text("Contraseña: ")

        try:
            user_info = self.service.login_user(email=email, password=password)
            if user_info:
                self.session_token = user_info["token"]
                self.current_user = user_info
                print(f"\n[ÉXITO] Sesión iniciada. ¡Bienvenido/a {user_info['nombre']}!")
            else:
                print("\n[FALLO] Credenciales inválidas.")
        except Exception as e:
            print(f"\n[ERROR] Error al iniciar sesión: {e}")

    def show_session_info(self):
        print("\n>>> DETALLES DE SESIÓN ACTIVA <<<")
        print(f"Token: {self.session_token}")
        print(f"Usuario ID: {self.current_user['user_id']}")
        print(f"Nombre: {self.current_user['nombre']}")
        print(f"Email: {self.current_user['email']}")
        print(f"Edad: {self.current_user['edad']}")
        print(f"Género: {self.current_user['genero']}")
        print(f"Ubicación: {self.current_user['ubicacion']}")

    def do_logout(self):
        print("\n>>> CERRANDO SESIÓN <<<")
        try:
            success = self.service.logout_user(self.session_token)
            if success:
                print("\n[ÉXITO] Sesión cerrada correctamente.")
                self.session_token = None
                self.current_user = None
            else:
                print("\n[FALLO] No se encontró la sesión activa en el servidor.")
        except Exception as e:
            print(f"\n[ERROR] Error al cerrar sesión: {e}")

    def do_profile_menu(self):
        try:
            profile = self.service.get_user_profile(self.session_token)
        except Exception as e:
            print(f"\n[ERROR] No se pudo obtener el perfil: {e}")
            return

        while True:
            print("\n" + "="*40)
            print("             MI PERFIL TINDER")
            print("="*40)
            print(f"Nombre: {profile['nombre']} ({profile['edad']} años, {profile['genero']})")
            print(f"Ubicación: {profile['ubicacion']}")
            print(f"Biografía: {profile.get('biografia') or '[Sin biografía]'}")
            print(f"Fotos ({len(profile.get('fotos', []))}): {', '.join(profile.get('fotos', [])) or '[Sin fotos]'}")
            
            # Preferences
            prefs = profile.get("preferencias", {})
            print(f"Preferencias: Interés en '{prefs.get('genero_interes')}', Edades [{prefs.get('edad_min')} - {prefs.get('edad_max')}]")
            
            # Characteristics
            chars = profile.get("caracteristicas", {})
            chars_str = ", ".join(f"{k}: {v}" for k, v in chars.items())
            print(f"Características: {chars_str or '[Sin características]'}")
            
            # Interests
            print(f"Intereses (Neo4j): {', '.join(profile.get('intereses', [])) or '[Sin intereses]'}")
            print("="*40)
            
            print("1. Editar Biografía")
            print("2. Editar Preferencias de Búsqueda")
            print("3. Editar Características Físicas/Rasgos")
            print("4. Editar Intereses")
            print("5. Volver")
            
            op = input("\nSeleccione una opción: ").strip()
            if op == "5":
                break
            
            if op == "1":
                bio = input("Ingrese nueva biografía: ").strip()
                try:
                    self.service.update_profile(
                        token=self.session_token,
                        biografia=bio,
                        caracteristicas=profile.get("caracteristicas", {}),
                        preferencias=profile.get("preferencias", {}),
                        intereses=profile.get("intereses", [])
                    )
                    print("\n[ÉXITO] Biografía actualizada.")
                    profile = self.service.get_user_profile(self.session_token)
                except Exception as e:
                    print(f"\n[ERROR] No se pudo actualizar: {e}")
            elif op == "2":
                gen = self.ask_text("Interés en género (Masculino/Femenino/Cualquiera): ")
                emin = self.ask_int("Edad mínima: ", minimum=18)
                emax = self.ask_int("Edad máxima: ", minimum=emin)
                new_prefs = {
                    "genero_interes": gen,
                    "edad_min": emin,
                    "edad_max": emax
                }
                try:
                    self.service.update_profile(
                        token=self.session_token,
                        biografia=profile.get("biografia", ""),
                        caracteristicas=profile.get("caracteristicas", {}),
                        preferencias=new_prefs,
                        intereses=profile.get("intereses", [])
                    )
                    print("\n[ÉXITO] Preferencias de búsqueda actualizadas.")
                    profile = self.service.get_user_profile(self.session_token)
                except Exception as e:
                    print(f"\n[ERROR] No se pudo actualizar: {e}")
            elif op == "3":
                signo = input("Signo del zodíaco: ").strip()
                altura = self.ask_int("Altura (en cm): ", minimum=100)
                pelo = input("Color de pelo: ").strip()
                new_chars = {
                    "signo": signo,
                    "altura": altura,
                    "color_pelo": pelo
                }
                try:
                    self.service.update_profile(
                        token=self.session_token,
                        biografia=profile.get("biografia", ""),
                        caracteristicas=new_chars,
                        preferencias=profile.get("preferencias", {}),
                        intereses=profile.get("intereses", [])
                    )
                    print("\n[ÉXITO] Características actualizadas.")
                    profile = self.service.get_user_profile(self.session_token)
                except Exception as e:
                    print(f"\n[ERROR] No se pudo actualizar: {e}")
            elif op == "4":
                ints_str = input("Ingrese intereses separados por comas (ej: Cine, Rock, Fútbol): ").strip()
                intereses_list = [x.strip() for x in ints_str.split(",") if x.strip()]
                try:
                    self.service.update_profile(
                        token=self.session_token,
                        biografia=profile.get("biografia", ""),
                        caracteristicas=profile.get("caracteristicas", {}),
                        preferencias=profile.get("preferencias", {}),
                        intereses=intereses_list
                    )
                    print("\n[ÉXITO] Intereses actualizados.")
                    profile = self.service.get_user_profile(self.session_token)
                except Exception as e:
                    print(f"\n[ERROR] No se pudo actualizar: {e}")
            else:
                print("Opción inválida.")

    def do_upload_photo(self):
        print("\n>>> CARGAR NUEVA FOTO <<<")
        url = self.ask_text("Ingrese la URL o nombre del archivo de la foto: ")
        try:
            self.service.add_user_photo(self.session_token, url)
            print("\n[ÉXITO] Foto agregada a tu perfil correctamente.")
        except Exception as e:
            print(f"\n[ERROR] No se pudo cargar la foto: {e}")

    def do_search_candidates(self):
        print("\n>>> BUSCANDO PERFILES COMPATIBLES <<<")
        while True:
            try:
                candidate = self.service.get_next_candidate(self.session_token)
                if not candidate:
                    print("\n[INFORMACIÓN] No quedan más candidatos que coincidan con tus preferencias en este momento.")
                    break
                
                print("\n" + "="*50)
                print(f"CANDIDATO: {candidate['nombre']} ({candidate['edad']} años, {candidate['genero']})")
                print(f"Ubicación: {candidate['ubicacion']}")
                print(f"Biografía: {candidate.get('biografia') or '[Sin biografía]'}")
                print(f"Fotos ({len(candidate['fotos'])}): {', '.join(candidate['fotos']) or '[Sin fotos]'}")
                
                chars = candidate.get("caracteristicas", {})
                chars_str = ", ".join(f"{k}: {v}" for k, v in chars.items())
                print(f"Características: {chars_str or '[Sin datos rasgos]'}")
                
                # Shared interests
                shared = candidate.get("intereses_comunes", [])
                print(f"Intereses Comunes (Neo4j): {', '.join(shared) or '[Ninguno en común]'}")
                print("="*50)
                
                print("1. Dar Like (Swipe Derecho)")
                print("2. Dar Dislike (Swipe Izquierdo)")
                print("3. Siguiente candidato (Saltar)")
                print("4. Volver al menú principal")
                
                op = input("\nSeleccione una opción: ").strip()
                if op == "4":
                    break
                elif op == "1":
                    res = self.service.hacer_swipe(self.session_token, candidate["user_id"], positive=True)
                    if res["match"]:
                        print("\n" + "*"*50)
                        print("              ¡¡ES UN MATCH!! 🎉")
                        print("*"*50)
                        print(f"¡Tú y {candidate['nombre']} se gustan mutuamente!")
                        print("*"*50)
                    else:
                        print(f"\n[INFO] Le diste Like a {candidate['nombre']}.")
                elif op == "2":
                    self.service.hacer_swipe(self.session_token, candidate["user_id"], positive=False)
                    print(f"\n[INFO] Descartaste a {candidate['nombre']}.")
                elif op == "3":
                    print("\nSaltando al siguiente candidato...")
                else:
                    print("Opción inválida. Continuando al siguiente candidato.")
            except Exception as e:
                print(f"\n[ERROR] Error al buscar candidatos: {e}")
                break

    def do_conversations(self):
        print("\n>>> MIS CONVERSACIONES (MATCHES) <<<")
        try:
            matches = self.service.obtener_mis_matches(self.session_token)
            if not matches:
                print("\n[INFORMACIÓN] No tienes ningún match confirmado para chatear todavía.")
                return
            
            print("\nMatches activos:")
            for idx, m in enumerate(matches, 1):
                print(f"{idx}. {m['nombre']} (Match ID: {m['match_id']})")
                
            sel = self.ask_int("\nSeleccione el número del chat para ingresar (o 0 para salir): ", minimum=0)
            if sel == 0 or sel > len(matches):
                return
                
            selected_match = matches[sel - 1]
            self.chat_loop(selected_match)
        except Exception as e:
            print(f"\n[ERROR] No se pudieron obtener chats: {e}")

    def chat_loop(self, match_info):
        match_id = match_info["match_id"]
        nombre = match_info["nombre"]
        print("\n" + "="*50)
        print(f"       CHAT CON {nombre.upper()} (Escriba /back para salir)")
        print("="*50)
        
        # Load and print history
        try:
            msgs = self.service.obtener_mensajes(self.session_token, match_id)
            for m in msgs:
                # Format time
                time_str = m["timestamp"].strftime("%H:%M") if m.get("timestamp") else ""
                print(f"[{time_str}] {m['sender_nombre']}: {m['texto']}")
        except Exception as e:
            print(f"[ERROR] No se pudo cargar el historial: {e}")
            
        while True:
            text = input(f"\nTú a {nombre} > ").strip()
            if not text:
                continue
            if text.lower() == "/back":
                break
                
            try:
                self.service.enviar_mensaje(self.session_token, match_id, text)
                # print sent confirmation
                print("[Mensaje enviado]")
            except Exception as e:
                print(f"[ERROR] No se pudo enviar el mensaje: {e}")

    def do_block_user(self):
        print("\n>>> BLOQUEAR USUARIO <<<")
        user_id = self.ask_int("Ingrese el ID del usuario que desea bloquear: ", minimum=1)
        confirm = input(f"¿Está seguro de que desea bloquear al usuario ID {user_id}? (S/N): ").strip().upper()
        if confirm != "S":
            print("Bloqueo cancelado.")
            return
            
        try:
            self.service.bloquear_usuario(self.session_token, user_id)
            print(f"\n[ÉXITO] El usuario ID {user_id} ha sido bloqueado y eliminado de tu lista de contactos.")
        except Exception as e:
            print(f"\n[ERROR] No se pudo realizar el bloqueo: {e}")

    def do_events_menu(self):
        while True:
            print("\n--- EVENTOS SOCIALES ---")
            print("1. Ver eventos disponibles")
            print("2. Crear un evento social")
            print("3. Inscribirse a un evento")
            print("4. Volver al menú anterior")
            
            op = input("\nSeleccione una opción: ").strip()
            if op == "4":
                break
            
            if op == "1":
                self.show_events()
            elif op == "2":
                self.do_create_event()
            elif op == "3":
                self.do_register_event_attendance()
            else:
                print("Opción inválida.")

    def show_events(self):
        print("\n>>> EVENTOS DISPONIBLES <<<")
        try:
            events = self.service.obtener_eventos(self.session_token)
            if not events:
                print("\n[INFORMACIÓN] No hay eventos sociales programados.")
                return
            
            for idx, e in enumerate(events, 1):
                # format date
                date_str = e["fecha_hora"].strftime("%Y-%m-%d %H:%M") if e.get("fecha_hora") else ""
                print(f"\n{idx}. '{e['titulo']}' (Evento ID: {e['id']})")
                print(f"   Organiza: {e['organizador_nombre']} (ID: {e['organizador_id']})")
                print(f"   Fecha: {date_str} | Ubicación: {e['ubicacion']}")
                print(f"   Descripción: {e['descripcion']}")
        except Exception as e:
            print(f"\n[ERROR] No se pudieron listar eventos: {e}")

    def do_create_event(self):
        print("\n>>> CREAR EVENTO SOCIAL <<<")
        titulo = self.ask_text("Título del evento: ")
        desc = self.ask_text("Descripción: ")
        ub = self.ask_text("Ubicación: ")
        date_str = self.ask_text("Fecha y Hora (AAAA-MM-DD HH:MM): ")
        
        try:
            event_id = self.service.crear_evento(self.session_token, titulo, desc, ub, date_str)
            print(f"\n[ÉXITO] Evento social creado con ID: {event_id}")
        except Exception as e:
            print(f"\n[ERROR] No se pudo crear el evento: {e}")

    def do_register_event_attendance(self):
        print("\n>>> INSCRIBIRSE A EVENTO <<<")
        event_id = self.ask_int("Ingrese el ID del evento al que desea asistir: ", minimum=1)
        try:
            self.service.inscribirse_evento(self.session_token, event_id)
            print(f"\n[ÉXITO] Inscripción registrada correctamente. Ya puedes asistir al evento.")
        except Exception as e:
            print(f"\n[ERROR] No se pudo inscribir: {e}")

    def do_reports_menu(self):
        from src.analytics.reports import ReportService
        rep_service = ReportService()
        
        while True:
            print("\n--- REPORTES ANALÍTICOS (FASE 6) ---")
            print("1. Reporte 1: Promedio de coincidencias por día (Cassandra)")
            print("2. Reporte 2: Características más populares de perfiles (MongoDB)")
            print("3. Reporte 3: Perfiles con más swipes a la derecha (Cassandra + Python)")
            print("4. Reporte 4: Duración promedio de conversaciones antes de una cita (PG + Cassandra)")
            print("5. Reporte 5: Intereses más comunes en Matches (Neo4j)")
            print("6. Reporte 6: Candidatos con >10 fotos y >=3 intereses comunes (MongoDB + Neo4j)")
            print("7. Reporte 7: Matches en fines de semana / feriados (Cassandra + Python)")
            print("8. [DEMO] Poblar base de datos con datos demo semilla (Todas las bases)")
            print("9. Volver al menú principal")
            
            op = input("\nSeleccione una opción: ").strip()
            if op == "9":
                break
            
            try:
                if op == "1":
                    avg, detail = rep_service.get_avg_matches_per_day()
                    print("\n>>> REPORTE 1: PROMEDIO DE COINCIDENCIAS POR DÍA <<<")
                    print(f"Promedio general: {avg:.2f} matches por día.")
                    print("Detalle por fecha:")
                    for k, v in detail.items():
                        print(f"  * {k}: {v} match(es)")
                elif op == "2":
                    chars = rep_service.get_popular_characteristics()
                    print("\n>>> REPORTE 2: CARACTERÍSTICAS MÁS POPULARES <<<")
                    if not chars:
                        print("No hay características registradas.")
                    else:
                        for idx, c in enumerate(chars, 1):
                            print(f"{idx}. {c['clave'].capitalize()}: {c['valor']} ({c['cantidad']} usuario(s))")
                elif op == "3":
                    likes = rep_service.get_most_liked_profiles()
                    print("\n>>> REPORTE 3: TOP PERFILES POPULARES (MÁS LIKES RECIBIDOS) <<<")
                    if not likes:
                        print("No se registraron likes en el sistema.")
                    else:
                        for idx, l in enumerate(likes, 1):
                            print(f"{idx}. {l['nombre']} (ID: {l['user_id']}) - {l['likes']} likes recibidos.")
                elif op == "4":
                    avg, details = rep_service.get_avg_chat_duration_before_event()
                    print("\n>>> REPORTE 4: DURACIÓN PROMEDIO ANTES DE UNA CITA <<<")
                    print(f"Duración promedio general: {avg:.1f} horas.")
                    if details:
                        print("Detalle de parejas y citas:")
                        for d in details:
                            print(f"  * Match ID {d['match_id']} (Users {d['user_1']} & {d['user_2']}) en '{d['evento']}':")
                            print(f"    - Primer mensaje: {d['primera_conve']}")
                            print(f"    - Fecha del evento: {d['fecha_cita']}")
                            print(f"    - Tiempo transcurrido: {d['diferencia_horas']} horas")
                elif op == "5":
                    ints = rep_service.get_common_interests_in_matches()
                    print("\n>>> REPORTE 5: INTERESES MÁS COMUNES EN MATCHES <<<")
                    if not ints:
                        print("No hay matches o intereses en común registrados.")
                    else:
                        for idx, i in enumerate(ints, 1):
                            print(f"{idx}. Interés '{i['interes']}' - Compartido en {i['cantidad']} match(es).")
                elif op == "6":
                    pairs = rep_service.get_rich_profiles_with_shared_interests()
                    print("\n>>> REPORTE 6: PERFILES RICOS (>10 FOTOS) CON INTERESES COMUNES (>=3) <<<")
                    if not pairs:
                        print("No se encontraron parejas que cumplan con la condición.")
                    else:
                        for p in pairs:
                            print(f"  * {p['nombre_1']} (ID: {p['id_1']}) y {p['nombre_2']} (ID: {p['id_2']})")
                            print(f"    - Cantidad intereses en común: {p['cantidad']}")
                            print(f"    - Intereses compartidos: {', '.join(p['comunes'])}")
                elif op == "7":
                    matches = rep_service.get_holiday_matches()
                    print("\n>>> REPORTE 7: COINCIDENCIAS EN FINES DE SEMANA O FERIADOS <<<")
                    if not matches:
                        print("No se registraron matches en fines de semana o feriados.")
                    else:
                        for m in matches:
                            print(f"  * [{m['fecha']}] Match ID {m['match_id']}: {m['nombre_1']} (ID: {m['user_1']}) con {m['nombre_2']} (ID: {m['user_2']}) | Día: {m['tipo_dia']}")
                elif op == "8":
                    confirm = input("¿Está seguro de que desea limpiar y repoblar la base de datos con datos demo? (S/N): ").strip().upper()
                    if confirm == "S":
                        rep_service.seed_demo_data()
                        print("\n[ÉXITO] Bases de datos repobladas con éxito.")
                else:
                    print("Opción inválida.")
            except Exception as e:
                print(f"\n[ERROR] Error al generar el reporte: {e}")
