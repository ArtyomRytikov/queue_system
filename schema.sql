-- Создание таблиц для системы электронной очереди деканата

CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(100) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    role VARCHAR(20) NOT NULL CHECK (role IN ('STUDENT', 'OPERATOR', 'ADMIN')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE services (
    id SERIAL PRIMARY KEY,
    name VARCHAR(200) NOT NULL,
    avg_service_time_min INTEGER DEFAULT 10,
    is_active BOOLEAN DEFAULT TRUE
);

CREATE TABLE windows (
    id SERIAL PRIMARY KEY,
    name VARCHAR(50) NOT NULL
);

CREATE TABLE schedule (
    id SERIAL PRIMARY KEY,
    day_of_week INTEGER NOT NULL CHECK (day_of_week BETWEEN 1 AND 7),
    time_from TIME NOT NULL,
    time_to TIME NOT NULL
);

CREATE TABLE tickets (
    id SERIAL PRIMARY KEY,
    ticket_number VARCHAR(20) UNIQUE NOT NULL,
    service_id INTEGER REFERENCES services(id),
    status VARCHAR(20) NOT NULL CHECK (status IN ('NEW', 'WAITING', 'CALLED', 'SERVED', 'CANCELED', 'NO_SHOW')),
    priority INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    called_at TIMESTAMP,
    ended_at TIMESTAMP,
    operator_id INTEGER REFERENCES users(id),
    window_id INTEGER REFERENCES windows(id)
);

CREATE TABLE event_logs (
    id SERIAL PRIMARY KEY,
    event_type VARCHAR(50) NOT NULL,
    ticket_id INTEGER REFERENCES tickets(id),
    actor_id INTEGER REFERENCES users(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Вставка тестовых данных (без паролей - они будут созданы через API)
INSERT INTO services (name, avg_service_time_min) VALUES 
('Справка об обучении', 5),
('Академический отпуск', 15),
('Пересдача экзамена', 10),
('Консультация', 20);

INSERT INTO windows (name) VALUES 
('Окно 1'), ('Окно 2'), ('Окно 3');

INSERT INTO schedule (day_of_week, time_from, time_to) VALUES 
(1, '09:00', '17:00'),
(2, '09:00', '17:00'),
(3, '09:00', '17:00'),
(4, '09:00', '17:00'),
(5, '09:00', '16:00');