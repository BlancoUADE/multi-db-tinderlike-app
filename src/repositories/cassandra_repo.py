import uuid
from datetime import datetime
from src.database.connection import get_cassandra_session

class CassandraRepository:
    def register_swipe(self, user_from, user_to, tipo):
        """
        Record a swipe event in swipes_por_dia and swipes_recibidos_por_perfil.
        """
        session = get_cassandra_session()
        swipe_id = uuid.uuid4()
        now_dt = datetime.utcnow()
        today_date = now_dt.date()

        # Insert in swipes_por_dia
        insert_by_day = session.prepare("""
            INSERT INTO swipes_por_dia (fecha, swipe_id, user_from, user_to, tipo)
            VALUES (?, ?, ?, ?, ?)
        """)
        session.execute(insert_by_day, [today_date, swipe_id, user_from, user_to, tipo])

        # Insert in swipes_recibidos_por_perfil
        insert_received = session.prepare("""
            INSERT INTO swipes_recibidos_por_perfil (user_to, tipo, swipe_id, user_from, fecha)
            VALUES (?, ?, ?, ?, ?)
        """)
        session.execute(insert_received, [user_to, tipo, swipe_id, user_from, now_dt])
        
        # Log activity in actividad_usuario_por_fecha
        insert_activity = session.prepare("""
            INSERT INTO actividad_usuario_por_fecha (user_id, fecha, timestamp, actividad)
            VALUES (?, ?, ?, ?)
        """)
        actividad_text = f"Realizó swipe {tipo} al usuario ID {user_to}"
        session.execute(insert_activity, [user_from, today_date, now_dt, actividad_text])

    def register_match(self, match_id, user_1, user_2):
        """
        Record a confirmed match event in matches_por_dia.
        """
        session = get_cassandra_session()
        now_dt = datetime.utcnow()
        today_date = now_dt.date()

        insert_match = session.prepare("""
            INSERT INTO matches_por_dia (fecha, match_id, user_1, user_2, timestamp)
            VALUES (?, ?, ?, ?, ?)
        """)
        session.execute(insert_match, [today_date, match_id, user_1, user_2, now_dt])

    def send_message(self, match_id, sender_id, text):
        """Send a message inside a conversation and log it to Cassandra."""
        session = get_cassandra_session()
        message_id = uuid.uuid4()
        now_dt = datetime.utcnow()
        today_date = now_dt.date()

        insert_msg = session.prepare("""
            INSERT INTO mensajes_por_conversacion (match_id, timestamp, message_id, sender_id, texto)
            VALUES (?, ?, ?, ?, ?)
        """)
        session.execute(insert_msg, [match_id, now_dt, message_id, sender_id, text])

        # Log activity
        insert_activity = session.prepare("""
            INSERT INTO actividad_usuario_por_fecha (user_id, fecha, timestamp, actividad)
            VALUES (?, ?, ?, ?)
        """)
        actividad_text = f"Envió un mensaje en match ID {match_id}"
        session.execute(insert_activity, [sender_id, today_date, now_dt, actividad_text])

    def get_messages(self, match_id):
        """Retrieve all messages for a match/conversation chronologically."""
        session = get_cassandra_session()
        stmt = session.prepare("""
            SELECT timestamp, sender_id, texto
            FROM mensajes_por_conversacion
            WHERE match_id = ?
        """)
        rows = session.execute(stmt, [match_id])
        results = []
        for row in rows:
            results.append({
                "timestamp": row.timestamp,
                "sender_id": row.sender_id,
                "texto": row.texto
            })
        return results
