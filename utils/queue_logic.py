from models import db, Ticket, Service
from datetime import datetime, timedelta

def generate_ticket_number(service_id):
    """Генерация номера талона в формате A001"""
    today = datetime.now().strftime('%y%m%d')
    last_ticket = Ticket.query.filter(
        Ticket.ticket_number.like(f'{service_id}{today}%')
    ).order_by(Ticket.id.desc()).first()
    
    if last_ticket:
        last_num = int(last_ticket.ticket_number[-3:])
        new_num = last_num + 1
    else:
        new_num = 1
    
    return f"{service_id}{today}{new_num:03d}"

def calculate_eta(ticket_id):
    """Расчёт примерного времени ожидания"""
    ticket = Ticket.query.get(ticket_id)
    if not ticket or ticket.status != 'WAITING':
        return None
    
    # Считаем талоны в очереди перед текущим
    waiting_tickets = Ticket.query.filter(
        Ticket.service_id == ticket.service_id,
        Ticket.status == 'WAITING',
        Ticket.created_at < ticket.created_at
    ).count()
    
    avg_time = ticket.service.avg_service_time_min
    eta_minutes = waiting_tickets * avg_time
    
    return {
        'position_in_queue': waiting_tickets + 1,
        'eta_minutes': eta_minutes,
        'estimated_time': (datetime.utcnow() + timedelta(minutes=eta_minutes)).isoformat()
    }

def get_next_ticket(operator_id, window_id):
    """Получение следующего талона для оператора"""
    # Ищем талон в статусе WAITING с самым ранним created_at
    next_ticket = Ticket.query.filter_by(status='WAITING').order_by(
        Ticket.created_at.asc()
    ).first()
    
    if not next_ticket:
        return None
    
    # Обновляем статус
    next_ticket.status = 'CALLED'
    next_ticket.operator_id = operator_id
    next_ticket.window_id = window_id
    next_ticket.called_at = datetime.utcnow()
    
    # Логируем событие
    from models import EventLog, User
    event = EventLog(
        event_type='TICKET_CALLED',
        ticket_id=next_ticket.id,
        actor_id=operator_id
    )
    db.session.add(event)
    db.session.commit()
    
    return next_ticket