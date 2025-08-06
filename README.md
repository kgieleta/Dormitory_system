# Dormitory Visit Management System

A web application project developed as part of a university subject, enabling dormitory residents to schedule visits, extend their duration, and allowing administrators and council members to manage these visits.  
The system includes a full login and registration mechanism, role-based authorization, a meeting calendar, as well as an admin panel for managing users and generating reports. The project was carried out in a 6-person team.  

📄 The [Technical Documentation](Dormitory_system_technical_documentation.pdf) and [User Documentation](Dormitory_system_user_documentation.pdf) are available in Polish within the repository.

## Features

- Registration and login for residents, guests, administrators, and council members  
- Scheduling, reviewing, extending, and canceling visits  
- QR code support to start and end visits  
- Administrator panel with filtering, sorting, manual visit termination, and CSV report generation  
- Council member approval system for visit extension requests  

## Technologies

### Backend
- Python 3.12  
- Django 5.0.3  
- Django REST Framework  
- django-cors-headers  

### Frontend
- React 18  
- Redux Toolkit  
- React Router DOM  
- Bootstrap 5, React Bootstrap  
- Axios  
- Moment.js  

## Architecture

The application consists of two parts:

- **Backend (Django REST API)** – application logic, authorization, data models, request handling  
- **Frontend (React SPA)** – user interface, API communication, routing, and state management (Redux)  

## Application
### Main window
<img width="1278" height="709" alt="1" src="https://github.com/user-attachments/assets/7f954cec-ee4e-4bb8-a173-e2c64bfa06e0" />

### Registration
<img width="1078" height="666" alt="image" src="https://github.com/user-attachments/assets/f3e2b70c-78c1-44d7-888e-8469ba3eecaa" />

### Appointment calendar
<img width="982" height="794" alt="image" src="https://github.com/user-attachments/assets/b07de32f-3cad-42c0-84e6-93fe80be8c8e" />

### Planning new appointment
<img width="751" height="598" alt="image" src="https://github.com/user-attachments/assets/b7db6637-3c12-4c3e-9871-2338c82ab430" />

