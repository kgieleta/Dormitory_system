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






