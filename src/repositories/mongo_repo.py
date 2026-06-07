from datetime import datetime
from src.database.connection import get_mongodb_database

class MongoRepository:
    def __init__(self):
        # Obtain database connection
        self.db = get_mongodb_database()

    def create_profile(self, user_id):
        """Create an empty profile document for a user."""
        profile = {
            "user_id": user_id,
            "biografia": "",
            "fotos": [],
            "preferencias": {
                "edad_min": 18,
                "edad_max": 99,
                "genero_interes": "Cualquiera"
            },
            "caracteristicas": {},
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }
        self.db.perfiles.insert_one(profile)
        
        # Opcionalmente registrar un log de la creacion del perfil en MongoDB
        self.db.historial_cambios_perfil.insert_one({
            "user_id": user_id,
            "timestamp": datetime.utcnow(),
            "campo_modificado": "perfil",
            "valor_anterior": None,
            "valor_nuevo": "creacion_inicial"
        })

    def delete_profile(self, user_id):
        """Delete profile document for a user (used for rollback)."""
        self.db.perfiles.delete_one({"user_id": user_id})

    def log_login_attempt(self, email, user_id, success, motivo, ip="127.0.0.1"):
        """Log a login attempt in MongoDB."""
        attempt = {
            "email": email,
            "user_id": user_id,  # can be None
            "exito": success,
            "timestamp": datetime.utcnow(),
            "motivo": motivo,
            "ip": ip
        }
        self.db.historial_login.insert_one(attempt)

    def get_profile(self, user_id):
        """Retrieve user's profile document."""
        return self.db.perfiles.find_one({"user_id": user_id})

    def update_profile_fields(self, user_id, biografia, caracteristicas, preferencias, intereses):
        """Update profile document and log changes to database."""
        old_profile = self.get_profile(user_id) or {}
        
        # Perform update
        self.db.perfiles.update_one(
            {"user_id": user_id},
            {
                "$set": {
                    "biografia": biografia,
                    "caracteristicas": caracteristicas,
                    "preferencias": preferencias,
                    "intereses": intereses,
                    "updated_at": datetime.utcnow()
                }
            }
        )
        
        # Log differences
        self._log_diff(user_id, "biografia", old_profile.get("biografia"), biografia)
        self._log_diff(user_id, "caracteristicas", old_profile.get("caracteristicas"), caracteristicas)
        self._log_diff(user_id, "preferencias", old_profile.get("preferencias"), preferencias)
        self._log_diff(user_id, "intereses", old_profile.get("intereses"), intereses)

    def _log_diff(self, user_id, field_name, old_val, new_val):
        """Internal helper to log individual profile field change."""
        if old_val != new_val:
            self.db.historial_cambios_perfil.insert_one({
                "user_id": user_id,
                "timestamp": datetime.utcnow(),
                "campo_modificado": field_name,
                "valor_anterior": old_val,
                "valor_nuevo": new_val
            })

    def add_photo(self, user_id, photo_url):
        """Add photo URL to user's profile and log changes."""
        old_profile = self.get_profile(user_id) or {}
        old_photos = old_profile.get("fotos", [])
        
        self.db.perfiles.update_one(
            {"user_id": user_id},
            {
                "$push": {"fotos": photo_url},
                "$set": {"updated_at": datetime.utcnow()}
            }
        )
        
        new_photos = old_photos + [photo_url]
        self._log_diff(user_id, "fotos", old_photos, new_photos)

    def create_notification(self, user_id, message, notification_type):
        """Create a notification document for a user."""
        notif = {
            "user_id": user_id,
            "mensaje": message,
            "tipo": notification_type,
            "leido": False,
            "timestamp": datetime.utcnow()
        }
        self.db.notificaciones.insert_one(notif)
