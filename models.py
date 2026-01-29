from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

class User(db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False)  # STUDENT, OPERATOR, ADMIN
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    tickets_operated = db.relationship('Ticket', backref='operator', foreign_keys='Ticket.operator_id')
    events = db.relationship('EventLog', backref='actor', foreign_keys='EventLog.actor_id')

class Service(db.Model):
    __tablename__ = 'services'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    avg_service_time_min = db.Column(db.Integer, default=10)
    is_active = db.Column(db.Boolean, default=True)

class Window(db.Model):
    __tablename__ = 'windows'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)

class Schedule(db.Model):
    __tablename__ = 'schedule'
    
    id = db.Column(db.Integer, primary_key=True)
    day_of_week = db.Column(db.Integer, nullable=False)  # 1-7 (Monday=1)
    time_from = db.Column(db.Time, nullable=False)
    time_to = db.Column(db.Time, nullable=False)

class Ticket(db.Model):
    __tablename__ = 'tickets'
    
    id = db.Column(db.Integer, primary_key=True)
    ticket_number = db.Column(db.String(20), unique=True, nullable=False)
    service_id = db.Column(db.Integer, db.ForeignKey('services.id'), nullable=False)
    status = db.Column(db.String(20), nullable=False, default='NEW')  # NEW, WAITING, CALLED, SERVED, CANCELED, NO_SHOW
    priority = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    called_at = db.Column(db.DateTime)
    ended_at = db.Column(db.DateTime)
    operator_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    window_id = db.Column(db.Integer, db.ForeignKey('windows.id'))
    
    service = db.relationship('Service', backref='tickets')
    window = db.relationship('Window', backref='tickets')
    events = db.relationship('EventLog', backref='ticket')

class EventLog(db.Model):
    __tablename__ = 'event_logs'
    
    id = db.Column(db.Integer, primary_key=True)
    event_type = db.Column(db.String(50), nullable=False)  # TICKET_CREATED, CALLED, SERVED, etc.
    ticket_id = db.Column(db.Integer, db.ForeignKey('tickets.id'), nullable=False)
    actor_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)