from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timezone

db = SQLAlchemy()


class User(UserMixin, db.Model):
    id            = db.Column(db.Integer, primary_key=True)
    username      = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    role          = db.Column(db.String(20), nullable=False, default='player')
    # role values: 'player', 'dm'

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def is_dm(self):
        return self.role == 'dm'


class SoundboardItem(db.Model):
    id         = db.Column(db.Integer, primary_key=True)
    user_id    = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    name       = db.Column(db.String(120), nullable=False)
    filename   = db.Column(db.String(256), nullable=False)  # on-disk filename
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    user = db.relationship('User', backref=db.backref('soundboard_items', lazy=True))


class ShareRequest(db.Model):
    id                = db.Column(db.Integer, primary_key=True)
    from_user_id      = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    to_user_id        = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    soundboard_item_id = db.Column(db.Integer, db.ForeignKey('soundboard_item.id'), nullable=False)
    status            = db.Column(db.String(20), nullable=False, default='pending')
    # status values: 'pending', 'accepted', 'declined'
    created_at        = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    from_user      = db.relationship('User', foreign_keys=[from_user_id])
    to_user        = db.relationship('User', foreign_keys=[to_user_id])
    soundboard_item = db.relationship('SoundboardItem', backref=db.backref('share_requests', lazy=True))
