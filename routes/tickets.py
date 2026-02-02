from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from models import db, Ticket, Service, User, EventLog
from utils.queue_logic import generate_ticket_number, calculate_eta
from datetime import datetime
import uuid

tickets_bp = Blueprint('tickets', __name__)

# Маршрут для создания талона
@tickets_bp.route('/api/tickets', methods=['POST'])
@jwt_required()  # Требуется авторизация через JWT
def create_ticket():
    user_id = get_jwt_identity()
    data = request.get_json()
    
    service_id = data.get('service')
    if not service_id:
        return jsonify({'error': 'Требуется service'}), 400
    
    service = Service.query.get(service_id)
    if not service or not service.is_active:
        return jsonify({'error': 'Услуга не найдена или не активна'}), 404
    
    # Генерация номера талона
    ticket_number = generate_ticket_number(service_id)
    
    # Создание талона
    ticket = Ticket(
        ticket_number=ticket_number,
        service_id=service_id,
        status='NEW',
        created_at=datetime.utcnow()
    )
    
    # Через 1 секунду автоматически переводим в WAITING (имитация постановки в очередь)
    ticket.status = 'WAITING'
    
    db.session.add(ticket)
    
    # Логируем событие
    event = EventLog(
        event_type='TICKET_CREATED',
        ticket_id=ticket.id,
        actor_id=user_id
    )
    db.session.add(event)
    db.session.commit()
    
    return jsonify({
        'ticket': {
            'id': ticket.id,
            'ticket_number': ticket.ticket_number,
            'service_id': ticket.service_id,
            'service_name': service.name,
            'status': ticket.status,
            'created_at': ticket.created_at.isoformat()
        },
        'queue_info': calculate_eta(ticket.id)
    }), 201