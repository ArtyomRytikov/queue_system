from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from models import db, Ticket, Service, User, EventLog
from utils.queue_logic import generate_ticket_number, calculate_eta
from datetime import datetime
import uuid

tickets_bp = Blueprint('tickets', __name__)

@tickets_bp.route('/api/tickets', methods=['POST'])
@jwt_required()
def create_ticket():
    user_id = get_jwt_identity()
    data = request.get_json()
    
    service_id = data.get('service_id')
    if not service_id:
        return jsonify({'error': 'Требуется service_id'}), 400
    
    service = Service.query.get(service_id)
    if not service or not service.is_active:
        return jsonify({'error': 'Услуга не найдена или не активна'}), 404
    
    # Генерируем номер талона
    ticket_number = generate_ticket_number(service_id)
    
    # Создаем талон
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

@tickets_bp.route('/api/tickets/<int:ticket_id>', methods=['GET'])
def get_ticket_status(ticket_id):
    ticket = Ticket.query.get(ticket_id)
    if not ticket:
        return jsonify({'error': 'Талон не найден'}), 404
    
    eta_info = calculate_eta(ticket_id)
    
    return jsonify({
        'ticket': {
            'id': ticket.id,
            'ticket_number': ticket.ticket_number,
            'service_id': ticket.service_id,
            'service_name': ticket.service.name,
            'status': ticket.status,
            'created_at': ticket.created_at.isoformat(),
            'called_at': ticket.called_at.isoformat() if ticket.called_at else None,
            'ended_at': ticket.ended_at.isoformat() if ticket.ended_at else None,
            'operator_id': ticket.operator_id,
            'window_id': ticket.window_id
        },
        'queue_info': eta_info
    }), 200

@tickets_bp.route('/api/tickets/<int:ticket_id>/cancel', methods=['POST'])
@jwt_required()
def cancel_ticket(ticket_id):
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    
    ticket = Ticket.query.get(ticket_id)
    if not ticket:
        return jsonify({'error': 'Талон не найден'}), 404
    
    # Проверяем, может ли пользователь отменить
    if user.role == 'STUDENT' and ticket.status not in ['NEW', 'WAITING']:
        return jsonify({'error': 'Нельзя отменить талон после вызова'}), 400
    
    if ticket.status in ['SERVED', 'CANCELED', 'NO_SHOW']:
        return jsonify({'error': 'Талон уже завершен'}), 400
    
    # Обновляем статус
    old_status = ticket.status
    ticket.status = 'CANCELED'
    ticket.ended_at = datetime.utcnow()
    
    # Логируем событие
    event = EventLog(
        event_type='TICKET_CANCELED',
        ticket_id=ticket.id,
        actor_id=user_id,
        metadata={'old_status': old_status}
    )
    db.session.add(event)
    db.session.commit()
    
    return jsonify({
        'message': 'Талон отменен',
        'ticket_id': ticket.id,
        'status': ticket.status
    }), 200

@tickets_bp.route('/api/tickets', methods=['GET'])
@jwt_required()
def get_tickets():
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    
    # Для студентов показываем только их талоны
    # Для простоты пока считаем, что студент = пользователь
    if user.role == 'STUDENT':
        # В реальной системе нужно связать студента с талоном
        tickets = Ticket.query.filter_by(operator_id=user_id).all()
    else:
        tickets = Ticket.query.all()
    
    result = []
    for ticket in tickets:
        result.append({
            'id': ticket.id,
            'ticket_number': ticket.ticket_number,
            'service_name': ticket.service.name,
            'status': ticket.status,
            'created_at': ticket.created_at.isoformat(),
            'called_at': ticket.called_at.isoformat() if ticket.called_at else None
        })
    
    return jsonify({'tickets': result}), 200